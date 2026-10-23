"""Validate source-native records, then commit accepted versions atomically."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import io
import json
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from zipfile import ZipFile

from jsonschema import Draft202012Validator, FormatChecker
from psycopg.types.json import Jsonb

from .config import ROOT, connect, context, save_context

FORMATS = FormatChecker()


@FORMATS.checks("olist-timestamp", raises=ValueError)
def source_timestamp(value):
    datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return True


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def feeds():
    return json.loads((ROOT / "contracts/source-catalog.json").read_text())["feeds"]


def batch_identity(ctx):
    # CLI omission and Airflow's empty optional parameter mean the same full batch.
    return fingerprint({"artifact": ctx["artifact_sha256"], "plan": ctx["plan_id"], "month": ctx.get("month") or None, "schema": "1.0.0"})


def read_rows(archive, month=None):
    """Monthly replay is a declared extraction plan, not invented upstream CDC."""
    with ZipFile(archive) as z:
        members = {}
        for feed in feeds():
            stream = io.TextIOWrapper(z.open(feed["file_member"]), encoding="utf-8-sig", newline="")
            reader = csv.DictReader(stream)
            schema = json.loads((ROOT / feed["schema"]).read_text())
            if set(reader.fieldnames or []) != set(schema["required"]):
                raise ValueError("Schema drift in " + feed["entity"])
            members[feed["entity"]] = [(i, row) for i, row in enumerate(reader, 1)]
        selected = {r["order_id"] for _, r in members["orders"] if not month or r["order_purchase_timestamp"].startswith(month)}
        for feed in feeds():
            entity = feed["entity"]
            for number, row in members[entity]:
                if entity in {"orders", "order_items", "payments"} and row["order_id"] not in selected:
                    continue
                yield feed, number, row


def validate(run_id):
    ctx = context(run_id)
    batch_id = batch_identity(ctx)
    sequence = int(ctx["month"].replace("-", "")) if ctx.get("month") else 1
    with connect() as conn:
        conn.execute("INSERT INTO ops.batches(batch_id,replay_plan_id,artifact_sha256,batch_sequence,schema_version,state) VALUES(%s,%s,%s,%s,'1.0.0','discovered') ON CONFLICT DO NOTHING", (batch_id, ctx["plan_id"], ctx["artifact_sha256"], sequence))
        if not conn.execute("SELECT 1 FROM ops.batches WHERE batch_id=%s", (batch_id,)).fetchone():
            raise ValueError("Extraction identity conflicts with an existing plan sequence")
        conn.execute("UPDATE ops.batches SET state='raw_preserved' WHERE batch_id=%s AND state='discovered'", (batch_id,))
    validators = {f["entity"]: Draft202012Validator(json.loads((ROOT / f["schema"]).read_text()), format_checker=FORMATS) for f in feeds()}
    seen, counts, errors = {}, {}, []
    try:
        with open(ctx["archive"], "rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != ctx["artifact_sha256"]:
                raise ValueError("Immutable artifact checksum mismatch")
        for feed, number, row in read_rows(ctx["archive"], ctx.get("month")):
            entity = feed["entity"]
            counts[entity] = counts.get(entity, 0) + 1
            failures = list(validators[entity].iter_errors(row))
            natural_key = "olist:" + json.dumps([row.get(k) for k in feed["natural_key"]], separators=(",", ":"), ensure_ascii=False)
            previous = seen.get((entity, natural_key))
            record_hash = fingerprint(row)
            if failures or previous is not None and previous != record_hash:
                errors.append({"entity": entity, "row": number, "reason": "invalid_source_contract" if failures else "conflicting_duplicate_key",
                               "fields": ["/".join(map(str, e.path)) for e in failures]})
            seen[(entity, natural_key)] = record_hash
    except (ValueError, KeyError, csv.Error) as error:
        errors.append({"entity": "batch", "row": 0, "reason": "schema_or_artifact_mismatch", "category": type(error).__name__})
    received = sum(counts.values())
    with connect() as conn:
        if errors:
            conn.execute("UPDATE ops.batches SET state='failed',received_occurrences=%s,rejected_occurrences=%s WHERE batch_id=%s AND state<>'loaded'", (received, received, batch_id))
            conn.execute("INSERT INTO ops.receipts(receipt_id,batch_id,pipeline_run_id,attempt,state) SELECT %s,%s,%s,coalesce(max(attempt),0)+1,'rejected' FROM ops.receipts WHERE batch_id=%s", (uuid4(), batch_id, run_id, batch_id))
            for err in errors[:1000]:
                conn.execute("INSERT INTO ops.dq_issues(issue_id,pipeline_run_id,batch_id,rule_id,severity,reason_code,entity,scope_key,redacted_details) VALUES(%s,%s,%s,'DQ-CONTRACT-001','error',%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                             (uuid4(), run_id, batch_id, err["reason"], err["entity"], str(err["row"]), Jsonb(err)))
        else:
            conn.execute("UPDATE ops.batches SET state='validated' WHERE batch_id=%s AND state='raw_preserved'", (batch_id,))
    save_context(run_id, batch_id=batch_id, source_counts=counts, validated=not errors)
    if errors:
        raise ValueError(f"Batch rejected: {len(errors)} invalid occurrences; diagnostics preserved")
    return {"counts": counts, "received": received, "invalid": 0}


class AdmissionConflict(ValueError):
    pass


def load(run_id):
    try:
        return _load(run_id)
    except AdmissionConflict:
        ctx = context(run_id)
        batch = batch_identity(ctx)
        with connect() as conn:
            received = sum(ctx["source_counts"].values())
            conn.execute("UPDATE ops.batches SET state='failed',received_occurrences=%s,rejected_occurrences=%s WHERE batch_id=%s AND state<>'loaded'", (received, received, batch))
            conn.execute("INSERT INTO ops.receipts(receipt_id,batch_id,pipeline_run_id,attempt,state) SELECT %s,%s,%s,coalesce(max(attempt),0)+1,'rejected' FROM ops.receipts WHERE batch_id=%s", (uuid4(), batch, run_id, batch))
            conn.execute("INSERT INTO ops.dq_issues(issue_id,pipeline_run_id,batch_id,rule_id,severity,reason_code,entity,scope_key,affected_records,redacted_details) VALUES(%s,%s,%s,'DQ-REVISION-001','error','equal_revision_conflict','batch','admission',%s,%s) ON CONFLICT DO NOTHING", (uuid4(), run_id, batch, received, Jsonb({"policy": "entire conflicting batch rejected; accepted cut unchanged"})))
        raise


def _load(run_id):
    ctx = context(run_id)
    if not ctx.get("validated"):
        raise ValueError("Validation must succeed before load")
    with open(ctx["archive"], "rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != ctx["artifact_sha256"]:
            raise AdmissionConflict("Artifact changed after validation")
    batch = batch_identity(ctx)
    with connect() as conn:
        # Serialize admission through commit; identity sequences alone cannot order commits.
        conn.execute("SELECT pg_advisory_xact_lock(52448122)")
        row = conn.execute("SELECT * FROM ops.batches WHERE batch_id=%s FOR UPDATE", (batch,)).fetchone()
        if row is None:
            raise ValueError("Canonical batch is not registered; validation must precede admission")
        attempt = conn.execute("SELECT count(*)+1 AS n FROM ops.receipts WHERE batch_id=%s", (batch,)).fetchone()["n"]
        receipt = uuid4()
        if row["state"] == "loaded":
            conn.execute("INSERT INTO ops.receipts(receipt_id,batch_id,pipeline_run_id,attempt,state) VALUES(%s,%s,%s,%s,'duplicate')", (receipt, batch, run_id, attempt))
            cut = conn.execute("SELECT source_cut FROM ops.source_commits WHERE batch_id=%s", (batch,)).fetchone()["source_cut"]
            added, duplicates = 0, row["received_occurrences"]
        else:
            if row["state"] != "validated":
                raise ValueError("Batch not eligible for admission")
            existing = {(r["entity"], r["natural_key"]): r["record_sha256"] for r in conn.execute("SELECT DISTINCT ON(entity,natural_key) entity,natural_key,record_sha256 FROM landing.source_versions ORDER BY entity,natural_key,source_cut DESC")}
            accepted, duplicates, received = [], 0, 0
            for feed, number, payload in read_rows(ctx["archive"], ctx.get("month")):
                received += 1
                nk = "olist:" + json.dumps([payload[k] for k in feed["natural_key"]], separators=(",", ":"), ensure_ascii=False)
                sha = fingerprint(payload)
                key = feed["entity"], nk
                if key in existing:
                    if existing[key] != sha:
                        raise AdmissionConflict("Equal Olist snapshot revision conflicts with accepted payload")
                    duplicates += 1
                    continue
                existing[key] = sha
                accepted.append((feed, number, payload, nk, sha))
            cut = conn.execute("INSERT INTO ops.source_commits(batch_id,committed_by_run) VALUES(%s,%s) RETURNING source_cut", (batch, run_id)).fetchone()["source_cut"]
            with conn.cursor().copy("COPY landing.source_versions(source_version_id,source_cut,entity,natural_key,declared_revision,revision_provenance,payload,record_sha256,artifact_sha256,file_member,source_row_number) FROM STDIN") as cp:
                for feed, number, payload, nk, sha in accepted:
                    version_id = uuid5(NAMESPACE_URL, "salesdw:olist:v2:" + feed["entity"] + ":" + nk + ":" + sha)
                    cp.write_row((version_id, cut, feed["entity"], nk, "v2", "published Olist v2 snapshot; extraction plan=" + ctx["plan_id"], Jsonb(payload), sha, ctx["artifact_sha256"], feed["file_member"], number))
            added = len(accepted)
            conn.execute("INSERT INTO ops.receipts(receipt_id,batch_id,pipeline_run_id,attempt,state) VALUES(%s,%s,%s,%s,'accepted')", (receipt, batch, run_id, attempt))
            conn.execute("UPDATE ops.batches SET state='loaded',received_occurrences=%s,accepted_occurrences=%s,duplicate_occurrences=%s WHERE batch_id=%s", (received, added, duplicates, batch))
        # A replay of an earlier batch builds at the latest accepted cut, never rewinds work.
        cut = conn.execute("SELECT max(source_cut) AS cut FROM ops.source_commits").fetchone()["cut"]
        conn.execute("UPDATE ops.pipeline_runs SET source_cut=%s WHERE pipeline_run_id=%s", (cut, run_id))
    save_context(run_id, source_cut=cut, batch_id=batch)
    return {"source_cut": cut, "new_versions": added, "duplicate_occurrences": duplicates, "receipt_id": str(receipt)}
