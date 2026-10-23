"""Deliberate bad inputs, fencing and physical SCD2 constraints in isolated restore DB.

Generated tiny archives are labelled simulated in object keys and the artifact
ledger. They are never admitted to the real-source database or baseline.
"""
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime
import hashlib
import io
import json
from threading import Barrier
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

import psycopg

from sales_dw import admission, leases
from sales_dw.cli import initialize, mark_failed
from sales_dw.config import ROOT, settings, connect, context, save_context, run_dir
from sales_dw.effectivity import insert_effective, as_of
from sales_dw.raw_storage import client
from sales_dw.raw_storage import preserve


def signature():
    with connect() as c:
        return c.execute("SELECT (SELECT count(*) FROM landing.source_versions) AS versions,(SELECT max(source_cut) FROM ops.source_commits) AS cut,(SELECT release_id FROM ops.published_release WHERE channel='main') AS published").fetchone()


def source_loss():
    run = str(uuid4())
    initialize(run, "simulated-local-source-unavailable")
    evidence = preserve(run, local_artifact=run_dir(run) / "intentionally-absent.zip")
    assert evidence["put_get_verified"]
    corrupted = run_dir(run) / "simulated-corrupted.zip"
    corrupted.write_bytes(b"simulated invalid raw content")
    try:
        preserve(run, local_artifact=corrupted)
    except ValueError:
        pass
    else:
        raise AssertionError("Conflicting raw payload accepted")
    mark_failed(run, "expected_source_loss_fixture")
    return {"recovered_from_s3": True, "corrupt_local_artifact_rejected": True, "real_archive_untouched": True}


def reject_archive(scenario):
    run_id = str(uuid4())
    initialize(run_id, "simulated-" + scenario + "-" + run_id)
    folder = run_dir(run_id)
    target = folder / ("simulated-" + scenario + ".zip")
    original = ROOT / "data/raw/olist/brazilian-ecommerce-v2.zip"
    with ZipFile(original) as source, ZipFile(target, "w", ZIP_DEFLATED) as output:
        for feed in admission.feeds():
            with source.open(feed["file_member"]) as member:
                reader = csv.DictReader(io.TextIOWrapper(member, encoding="utf-8-sig"))
                columns, row = list(reader.fieldnames), next(reader)
            rows = [row]
            if feed["entity"] == "orders":
                if scenario == "unknown_schema":
                    columns.append("unexpected_column")
                    row["unexpected_column"] = "synthetic"
                if scenario == "bad_status":
                    row["order_status"] = "SIMULATED_INVALID"
                if scenario == "duplicate_conflict":
                    rows.append({**row, "order_status": "canceled" if row["order_status"] != "canceled" else "delivered"})
                if scenario == "equal_revision":
                    row["order_status"] = "canceled" if row["order_status"] != "canceled" else "delivered"
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            output.writestr(feed["file_member"], stream.getvalue())
    with target.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    key = "simulated/negative-fixtures/" + sha + ".zip"
    bucket = settings()["s3"]["bucket"]
    client().fput_object(bucket, key, str(target))
    with connect() as c:
        c.execute("INSERT INTO ops.artifacts(artifact_sha256,source_system,source_version,object_bucket,object_key,content_bytes,state,preserved_at) VALUES(%s,'simulated_operational_fixture',%s,%s,%s,%s,'preserved',clock_timestamp()) ON CONFLICT DO NOTHING", (sha, scenario, bucket, key, target.stat().st_size))
    save_context(run_id, archive=str(target), artifact_sha256=sha, simulated=True)
    before = signature()
    try:
        admission.validate(run_id)
        admission.load(run_id)
    except ValueError:
        mark_failed(run_id, "expected_simulated_rejection")
    else:
        raise AssertionError("Deliberately invalid batch was admitted: " + scenario)
    with connect() as c:
        batch = context(run_id)["batch_id"]
        c.execute("UPDATE ops.batches SET scenario_id=%s WHERE batch_id=%s", ("simulated:" + scenario, batch))
        evidence = c.execute("SELECT state,received_occurrences,rejected_occurrences FROM ops.batches WHERE batch_id=%s", (batch,)).fetchone()
        assert evidence["state"] == "failed"
        assert c.execute("SELECT count(*) AS n FROM ops.dq_issues WHERE pipeline_run_id=%s AND severity='error'", (run_id,)).fetchone()["n"] > 0
        assert c.execute("SELECT count(*) AS n FROM ops.receipts WHERE pipeline_run_id=%s AND state='rejected'", (run_id,)).fetchone()["n"] > 0
    assert signature() == before
    return {"run_id": run_id, "batch": evidence, "source_cut_and_publication_unchanged": True, "raw_sha256": sha}


def fences():
    runs = [str(uuid4()), str(uuid4())]
    for run in runs:
        initialize(run, "simulated-concurrent-owner")
    barrier = Barrier(2)
    def compete(run):
        barrier.wait(timeout=10)
        try:
            leases.acquire(run)
            return run, True
        except RuntimeError:
            return run, False
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(compete, runs))
    assert sum(won for _, won in result) == 1
    winner = next(run for run, won in result if won)
    loser = next(run for run, won in result if not won)
    old_token = context(winner)["fencing_token"]
    leases.release(winner)
    leases.acquire(loser)
    assert context(loser)["fencing_token"] > old_token
    try:
        with connect("publish") as c:
            leases.assert_owned(c, winner)
    except psycopg.Error as error:
        assert error.sqlstate == "P0001"
    else:
        raise AssertionError("Stale owner was accepted after takeover")
    leases.release(loser)
    for run in runs:
        mark_failed(run, "expected_isolated_fence_fixture")
    return {"one_concurrent_winner": True, "fence_increased": True, "stale_owner_denied": True}


def scd2():
    run = str(uuid4())
    initialize(run, "simulated-explicit-business-effectivity")
    rid = uuid4()
    expected = json.loads((ROOT / "tests/fixtures/kimball/expected.json").read_text())["scd2_versions"]
    def allocate(when):
        with connect("transform") as c:
            return c.execute("INSERT INTO ops.dimension_key_registry(namespace,natural_key,version_identity,allocated_by_run) VALUES('simulated:product',%s,%s,%s) RETURNING surrogate_key", (run + ":p1", str(when), run)).fetchone()["surrogate_key"]
    versions = []
    for index in (0, 2, 1):
        row = expected[index]
        versions = insert_effective(versions, datetime.fromisoformat(row["valid_from"]), row["category"], allocate)
    with connect("snapshot") as c:
        cut = c.execute("SELECT max(source_cut) AS n FROM ops.source_commits").fetchone()["n"]
        c.execute("INSERT INTO ops.releases(release_id,pipeline_run_id,source_cut,contract_version,model_version,fencing_token,state) VALUES(%s,%s,%s,'2.0.0','simulated-scd2',1,'building')", (rid, run, cut))
        statement = """INSERT INTO warehouse_store.dim_product(release_id,product_key,source_system,product_id,version_identity,category,category_missing,
          valid_from,valid_to,is_current,business_effectivity_known,is_inferred,attribute_sha256,created_run_id,last_changed_run_id,source_cut)
          VALUES(%s,%s,'system','simulated:p1',%s,%s,false,%s,%s,%s,true,false,%s,%s,%s,%s)"""
        for v in versions:
            c.execute(statement, (rid, v.surrogate_key, str(v.valid_from), v.category, v.valid_from, v.valid_to, v.is_current, "0"*64, run, run, cut))
        for row in expected:
            when = datetime.fromisoformat(row["valid_from"])
            actual = c.execute("SELECT product_key FROM warehouse_store.dim_product WHERE release_id=%s AND valid_from<=%s AND (valid_to IS NULL OR %s<valid_to)", (rid, when, when)).fetchall()
            assert len(actual) == 1 and actual[0]["product_key"] == as_of(versions, when)
        try:
            with c.transaction():
                c.execute(statement, (rid, 999999999, "overlap", "invalid", datetime(2024, 1, 10), datetime(2024, 2, 20), False, "0"*64, run, run, cut))
        except psycopg.errors.ExclusionViolation:
            pass
        else:
            raise AssertionError("Physical SCD2 overlap constraint did not reject")
        c.rollback()  # Synthetic candidate/rows never survive or become consumer data.
    mark_failed(run, "isolated_effectivity_fixture_rolled_back")
    return {"late_interval_split": True, "as_of_boundaries": True, "postgres_overlap_denied": True, "candidate_rolled_back": True}


def main():
    assert settings()["dbname"].startswith("sales_dw_restore_"), "Synthetic faults require an isolated restore target"
    before = signature()
    assert before["published"] is not None
    report = {"database": settings()["dbname"], "simulated": True, "passed": False, "checks": {}}
    try:
        for scenario in ("unknown_schema", "bad_status", "duplicate_conflict", "equal_revision"):
            report["checks"][scenario] = reject_archive(scenario)
            print(scenario + ": expected rejection PASS", flush=True)
        report["checks"]["fencing"] = fences()
        report["checks"]["effectivity"] = scd2()
        report["checks"]["source_loss"] = source_loss()
        assert signature() == before
        report["passed"] = True
    finally:
        (ROOT / "var/evidence/faults.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({"passed": True, "checks": list(report["checks"])}))


if __name__ == "__main__":
    main()
