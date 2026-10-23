"""SC-006: explicit synthetic revision, ONLY in an isolated restored database.

This tests downstream revision processing, not source CDC. The production Olist
connector deliberately rejects changed v2 payloads. This fixture has its own raw
artifact, scenario/revision provenance and receipt, and never changes real raw.
"""
import hashlib
import io
import json
from uuid import uuid4
from jsonschema import Draft202012Validator
from psycopg.types.json import Jsonb

from sales_dw import admission, leases
from sales_dw.cli import initialize, perform, mark_failed
from sales_dw.config import ROOT, settings, connect, context, save_context, run_dir
from sales_dw.raw_storage import client
from sales_dw.rollback_release import apply as rollback


def monthly(release, month):
    with connect("bi") as c:
        return c.execute("SELECT total_orders,delivered_orders,canceled_orders,delivered_merchandise_value,delivered_item_rows FROM reporting.validated_sales_monthly WHERE release_id=%s AND month=%s", (release, month)).fetchone()


def registry_signature():
    with connect("transform") as c:
        return c.execute("SELECT count(*) AS n,md5(string_agg(surrogate_key::text||namespace||natural_key||version_identity,',' ORDER BY surrogate_key)) AS hash FROM ops.dimension_key_registry").fetchone()


def main():
    assert settings()["dbname"].startswith("sales_dw_restore_"), "Isolated restored target required"
    run = str(uuid4())
    initialize(run, "simulated-status-correction-" + run)
    report = {"passed": False, "database": settings()["dbname"], "simulated_revision": True, "run_id": run}
    try:
        with connect("snapshot") as c:
            old_release = c.execute("SELECT release_id FROM ops.published_release WHERE channel='main'").fetchone()["release_id"]
            chosen = c.execute("""SELECT f.order_id,f.order_key,f.customer_key,f.item_merchandise_total,f.item_row_count,
                date_trunc('month',f.purchase_timestamp)::date AS month,s.natural_key,s.payload,s.source_version_id
                FROM warehouse_store.fct_orders f JOIN landing.source_versions s ON s.source_version_id=f.lineage_id
                WHERE f.release_id=%s AND f.delivered_order_count=1 AND NOT f.missing_delivery_timestamp
                AND f.item_row_count>0 ORDER BY f.order_id LIMIT 1""", (old_release,)).fetchone()
            old_metadata = c.execute("SELECT model_name,logical_content_sha256 FROM ops.snapshot_relations WHERE release_id=%s ORDER BY model_name", (old_release,)).fetchall()
        before, keys = monthly(old_release, chosen["month"]), registry_signature()
        payload = {**chosen["payload"], "order_status": "canceled"}
        feed = next(f for f in admission.feeds() if f["entity"] == "orders")
        Draft202012Validator(json.loads((ROOT / feed["schema"]).read_text()), format_checker=admission.FORMATS).validate(payload)
        body = json.dumps({"simulated": True, "scenario": "SC-006", "base_source_version": str(chosen["source_version_id"]), "declared_revision": "simulated-status-correction-v1", "payload": payload}, sort_keys=True).encode()
        sha = hashlib.sha256(body).hexdigest()
        key, bucket = "simulated/corrections/" + sha + ".json", settings()["s3"]["bucket"]
        client().put_object(bucket, key, io.BytesIO(body), len(body), content_type="application/json")
        response = client().get_object(bucket, key)
        try:
            assert hashlib.sha256(response.read()).hexdigest() == sha
        finally:
            response.close()
            response.release_conn()
        (run_dir(run) / "simulated-correction.json").write_bytes(body)
        batch = admission.fingerprint({"simulated": sha, "run": run})
        with connect() as c:
            c.execute("SELECT pg_advisory_xact_lock(52448122)")
            c.execute("INSERT INTO ops.artifacts(artifact_sha256,source_system,source_version,object_bucket,object_key,content_bytes,state,preserved_at) VALUES(%s,'simulated_operational_fixture','SC-006',%s,%s,%s,'preserved',clock_timestamp()) ON CONFLICT DO NOTHING", (sha, bucket, key, len(body)))
            c.execute("INSERT INTO ops.batches(batch_id,replay_plan_id,artifact_sha256,batch_sequence,schema_version,scenario_id,state,received_occurrences,accepted_occurrences) VALUES(%s,%s,%s,1,'1.0.0','SC-006_simulated_status_correction','loaded',1,1)", (batch, "simulated-correction-" + run, sha))
            cut = c.execute("INSERT INTO ops.source_commits(batch_id,committed_by_run) VALUES(%s,%s) RETURNING source_cut", (batch, run)).fetchone()["source_cut"]
            c.execute("INSERT INTO landing.source_versions(source_version_id,source_cut,entity,natural_key,declared_revision,revision_provenance,payload,record_sha256,artifact_sha256,file_member,source_row_number) VALUES(%s,%s,'orders',%s,'simulated-status-correction-v1','SC-006 isolated synthetic fixture; NOT source-native CDC',%s,%s,%s,'simulated-correction.json',1)", (uuid4(), cut, chosen["natural_key"], Jsonb(payload), admission.fingerprint(payload), sha))
            c.execute("INSERT INTO ops.receipts(receipt_id,batch_id,pipeline_run_id,attempt,state) VALUES(%s,%s,%s,1,'accepted')", (uuid4(), batch, run))
            c.execute("UPDATE ops.pipeline_runs SET source_cut=%s WHERE pipeline_run_id=%s", (cut, run))
        save_context(run, source_cut=cut, batch_id=batch, simulated=True, artifact_sha256=sha)
        report.update(original_release=str(old_release), source_cut=cut, before=before, original_registry=keys)
        for stage in ("lease", "build", "snapshot", "semantic", "publish", "finish"):
            result = perform(stage, run)
            report[stage] = result
            (run_dir(run) / (stage + ".json")).write_text(json.dumps({"passed": True, "result": result}, default=str, indent=2) + "\n")
            print(stage + ": PASS", flush=True)
        rid = context(run)["release_id"]
        after = monthly(rid, chosen["month"])
        assert after["total_orders"] == before["total_orders"]
        assert after["delivered_orders"] == before["delivered_orders"] - 1
        assert after["canceled_orders"] == before["canceled_orders"] + 1
        assert after["delivered_merchandise_value"] == before["delivered_merchandise_value"] - chosen["item_merchandise_total"]
        assert after["delivered_item_rows"] == before["delivered_item_rows"] - chosen["item_row_count"]
        assert registry_signature() == keys
        assert monthly(old_release, chosen["month"]) == before
        with connect("snapshot") as c:
            assert c.execute("SELECT model_name,logical_content_sha256 FROM ops.snapshot_relations WHERE release_id=%s ORDER BY model_name", (old_release,)).fetchall() == old_metadata
            changed = c.execute("SELECT order_key,customer_key,delivered_order_count,canceled_order_count FROM warehouse_store.fct_orders WHERE release_id=%s AND order_id=%s", (rid, chosen["order_id"])).fetchone()
            assert changed == {"order_key": chosen["order_key"], "customer_key": chosen["customer_key"], "delivered_order_count": 0, "canceled_order_count": 1}
            assert c.execute("SELECT bool_and(s.is_canceled) AS canceled FROM warehouse_store.fct_order_items i JOIN warehouse_store.dim_order_status s USING(release_id,order_status_key) WHERE i.release_id=%s AND i.order_id=%s", (rid, chosen["order_id"])).fetchone()["canceled"]
        report.update(after=after, stable_keys=True, old_release_unchanged=True, affected_items_reclassified=True)
        report["rollback"] = rollback(str(old_release), rid, "Isolated SC-006 drill: restore original consumer pointer")
        with connect("snapshot") as c:
            assert c.execute("SELECT release_id FROM ops.published_release WHERE channel='main'").fetchone()["release_id"] == old_release
        try:
            rollback(rid, rid, "Simulated stale rollback plan must be refused")
        except RuntimeError:
            report["stale_rollback_plan_rejected"] = True
        else:
            raise AssertionError("Stale rollback plan accepted")
        report["passed"] = True
    except Exception as error:
        mark_failed(run, type(error).__name__)
        try:
            leases.release(run)
        except Exception:
            pass
        raise
    finally:
        (ROOT / "var/evidence/correction.json").write_text(json.dumps(report, default=str, indent=2) + "\n")
    print(json.dumps({"passed": True, "run_id": run, "simulated": True, "old_release_unchanged": True, "rollback_passed": True}))


if __name__ == "__main__":
    main()
