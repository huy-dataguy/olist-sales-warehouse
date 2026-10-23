"""Real PostgreSQL/S3 acceptance checks; no DDL or destructive reset.

Each section records its actual bounded scope. Passing this suite alone does not
claim every operational scenario in the design has been exercised.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import statistics
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from minio.error import S3Error

from sales_dw.config import ROOT, connect, settings
from sales_dw.export_metrics import assert_parity, reference_query
from sales_dw.quality import MODELS
from sales_dw.raw_storage import client


def published():
    with connect("snapshot") as c:
        row = c.execute("SELECT r.* FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main'").fetchone()
    if not row or row["state"] != "published":
        raise AssertionError("No published release")
    return row


def raw():
    with connect() as c:
        artifacts = c.execute("SELECT * FROM ops.artifacts WHERE state='preserved' AND source_system='olist'").fetchall()
    assert artifacts
    evidence = []
    for artifact in artifacts:
        result = client().get_object(artifact["object_bucket"], artifact["object_key"])
        digest, size = hashlib.sha256(), 0
        try:
            for part in result.stream(1024*1024):
                digest.update(part)
                size += len(part)
        finally:
            result.close()
            result.release_conn()
        assert digest.hexdigest() == artifact["artifact_sha256"] and size == artifact["content_bytes"]
        evidence.append({"sha256": digest.hexdigest(), "bytes": size})
    return {"s3_roundtrip": evidence}


def warehouse():
    release = published()
    with connect("snapshot") as c:
        rows = c.execute("SELECT * FROM ops.snapshot_relations WHERE release_id=%s", (release["release_id"],)).fetchall()
        assert len(rows) == 10 and all(r["validated"] for r in rows)
        counts = {r["model_name"]: r["row_count"] for r in rows}
        for model, key in MODELS.items():
            check = c.execute(sql.SQL("SELECT count(*) AS n,count(DISTINCT {}) AS distinct_keys,min(source_cut) AS low,max(source_cut) AS high FROM warehouse_store.{} WHERE release_id=%s").format(sql.Identifier(key), sql.Identifier(model)), (release["release_id"],)).fetchone()
            assert check["n"] == check["distinct_keys"] == counts[model] and check["low"] == check["high"] == release["source_cut"]
        totals = c.execute("SELECT sum(delivered_order_count) AS delivered,count(DISTINCT customer_key) FILTER(WHERE delivered_order_count=1) AS customers FROM warehouse_store.fct_orders WHERE release_id=%s", (release["release_id"],)).fetchone()
        if counts["fct_orders"] == 99441:
            assert counts["fct_order_items"] == 112650 and counts["fct_payments"] == 103886
            assert totals == {"delivered": 96478, "customers": 93358}
        violations = c.execute("SELECT count(*) AS n FROM ops.batches WHERE state='loaded' AND received_occurrences<>accepted_occurrences+duplicate_occurrences+rejected_occurrences").fetchone()["n"]
        assert violations == 0
        unresolved = c.execute("SELECT count(*) AS n FROM ops.lineage_edges l LEFT JOIN landing.source_versions s USING(source_version_id) WHERE l.release_id=%s AND s.source_version_id IS NULL", (release["release_id"],)).fetchone()["n"]
        assert unresolved == 0
    return {"release_id": str(release["release_id"]), "counts": counts, "totals": totals, "occurrence_accounting": True, "lineage_resolves": True}


def semantic():
    release = published()
    specs = json.loads((ROOT / "contracts/metric-catalog.json").read_text())["exports"]
    outputs = {}
    with connect("semantic", release_id=release["release_id"]) as c:
        for spec in specs:
            rows = c.execute(sql.SQL("SELECT * FROM reporting.{} WHERE release_id=%s").format(sql.Identifier(spec["id"])), (release["release_id"],)).fetchall()
            expected = c.execute(reference_query(spec["id"])).fetchall()
            assert_parity(rows, expected, [k for k in spec["grain"] if k != "release_id"], spec["metrics"])
            outputs[spec["id"]] = {"rows": len(rows), "oracle_parity": True}
        zeros = c.execute("SELECT count(*) AS n FROM reporting.sales_monthly WHERE release_id=%s AND delivered_orders=0 AND delivered_aov IS NOT NULL", (release["release_id"],)).fetchone()["n"]
        assert zeros == 0
        money = c.execute("SELECT sum(delivered_merchandise_value) AS n FROM reporting.sales_monthly WHERE release_id=%s", (release["release_id"],)).fetchone()["n"]
    return {"exports": outputs, "delivered_value": money, "zero_denominator_null": True}


def security():
    rejected = []
    tests = [
        ("bi", "SELECT * FROM landing.source_versions LIMIT 1"),
        ("bi", "SELECT * FROM work.fct_orders LIMIT 1"),
        ("bi", "SELECT * FROM warehouse_store.fct_orders LIMIT 1"),
        ("bi", "UPDATE reporting.sales_monthly SET total_orders=total_orders WHERE false"),
        ("ingest", "UPDATE landing.source_versions SET entity=entity WHERE false"),
        ("publish", "UPDATE warehouse_store.fct_orders SET order_count=order_count WHERE false"),
        ("semantic", "SELECT * FROM semantic_input.metric_orders LIMIT 1"),
    ]
    for role, statement in tests:
        try:
            with connect(role) as c:
                c.execute(statement)
        except psycopg.Error as error:
            # Privilege denial or the deliberate fail-closed binding exception only.
            allowed = {"P0001", "42704"} if role == "semantic" else {"42501"}
            assert error.sqlstate in allowed, error.sqlstate
            rejected.append({"role": role, "statement": statement, "sqlstate": error.sqlstate})
        else:
            raise AssertionError("Unauthorized path succeeded: " + role + " " + statement)
    with connect("bi") as c:
        assert c.execute("SELECT count(*) AS n FROM reporting.validated_sales_monthly").fetchone()["n"] > 0
        privileges = c.execute("SELECT rolname,rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname LIKE 'salesdw_%' AND rolname<>'salesdw_bootstrap'").fetchall()
        assert all(not r["rolsuper"] and not r["rolcreatedb"] and not r["rolcreaterole"] for r in privileges)
        assert not c.execute("SELECT has_schema_privilege(current_user,'public','CREATE') AS allowed").fetchone()["allowed"]
    try:
        client().remove_object(settings()["s3"]["bucket"], "security-probe-never-created/" + str(uuid4()))
    except S3Error as error:
        assert error.code == "AccessDenied"
    else:
        raise AssertionError("Raw ingest role unexpectedly has DELETE")
    assert not (ROOT / "var/secrets/bootstrap.json").exists(), "Operator secret exposed in worker"
    return {"denials": rejected, "allowed_bi_read": True, "roles_unprivileged": True, "s3_delete_denied": True, "operator_secret_unmounted": True}


def performance():
    rid = published()["release_id"]
    queries = {
        "expression_filter": "SELECT count(*),sum(item_merchandise_total) FROM warehouse_store.fct_orders WHERE release_id=%s AND left(purchase_date_key::text,6)='201808'",
        "range_filter": "SELECT count(*),sum(item_merchandise_total) FROM warehouse_store.fct_orders WHERE release_id=%s AND purchase_date_key>=20180801 AND purchase_date_key<20180901",
    }
    report, answers = {}, []
    with connect("snapshot") as c:
        for name, statement in queries.items():
            c.execute("EXPLAIN (FORMAT JSON) " + statement, (rid,)).fetchall()
            answers.append(c.execute(statement, (rid,)).fetchone())
            plans = [c.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + statement, (rid,)).fetchone()["QUERY PLAN"][0] for _ in range(3)]
            report[name] = {"median_ms": statistics.median(p["Execution Time"] for p in plans), "plans": plans, "cache_condition": "warm/shared cache, no cache eviction performed"}
        assert answers[0] == answers[1]
    timings = []
    with connect("bi") as c:
        for _ in range(20):
            start = time.perf_counter()
            c.execute("SELECT * FROM reporting.validated_sales_monthly WHERE release_id=%s AND month='2018-08-01'", (rid,)).fetchall()
            timings.append((time.perf_counter()-start)*1000)
    report["monthly_export_query_p95_ms"] = sorted(timings)[18]
    report["same_output"] = True
    return report


def isolation():
    rid = published()["release_id"]
    with connect("bi") as c:
        hidden = c.execute("SELECT count(*) AS n FROM reporting.release_metadata WHERE state<>'published'").fetchone()["n"]
        assert hidden == 0
    try:
        with connect("publish") as c:
            c.execute("SELECT ops.assert_lease(%s,%s)", (uuid4(), 1))
    except psycopg.Error as error:
        assert error.sqlstate == "P0001"
    else:
        raise AssertionError("Stale owner accepted")
    return {"candidate_invisible_to_bi": True, "stale_owner_rejected": True, "release_id": str(rid)}


CHECKS = {"raw": raw, "warehouse": warehouse, "semantic": semantic, "security": security, "performance": performance, "isolation": isolation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("section", choices=["all", *CHECKS], default="all", nargs="?")
    args = parser.parse_args()
    report = {"database": settings()["dbname"], "checks": {}, "passed": False}
    suffix = "" if args.section == "all" else "-" + args.section
    output = ROOT / "var/evidence" / ("runtime-" + settings()["dbname"] + suffix + ".json")
    try:
        for name, check in CHECKS.items():
            if args.section not in {"all", name}:
                continue
            start = time.monotonic()
            result = check()
            report["checks"][name] = {"passed": True, "seconds": round(time.monotonic()-start, 3), "result": result}
            print(name + ": PASS", flush=True)
        report["passed"] = True
    finally:
        output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({"passed": report["passed"], "evidence": str(output)}))


if __name__ == "__main__":
    main()
