"""Isolated real-source monthly replay, late-child delivery and full-rebuild proof.

The delayed payment is an explicitly simulated delivery sequence. Its payload
comes unchanged from the preserved Olist archive. No fabricated source CDC.
Requires an empty sales_dw_restore_* database provisioned by migrate.py.
"""
from __future__ import annotations
import json
from uuid import uuid4

from sales_dw import admission, leases, transform
from sales_dw.cli import initialize, perform, mark_failed
from sales_dw.config import ROOT, settings, connect, context
from sales_dw.quality import logical_hash, MODELS, check_work


def registry():
    with connect("transform") as c:
        return {(r["namespace"], r["natural_key"], r["version_identity"]): r["surrogate_key"] for r in c.execute("SELECT * FROM ops.dimension_key_registry")}


def hashes():
    with connect("snapshot") as c:
        return {name: logical_hash(c, "work", name) for name in MODELS}


def main():
    assert settings()["dbname"].startswith("sales_dw_restore_"), "Isolated target required"
    with connect() as c:
        assert c.execute("SELECT count(*) AS n FROM landing.source_versions").fetchone()["n"] == 0, "Fresh target required; no reset permitted"
    report = {"database": settings()["dbname"], "simulated_delivery": True, "source_payloads_unchanged": True, "phases": [], "passed": False}
    original = admission.read_rows
    archive = ROOT / "data/raw/olist/brazilian-ecommerce-v2.zip"
    payments = [(number, row) for feed, number, row in original(archive, "2017-02") if feed["entity"] == "payments"]
    delayed_number, delayed_payload = payments[-1]
    inferred_product = next(row["product_id"] for feed, _, row in original(archive, "2017-01") if feed["entity"] == "order_items")

    def phase(month, plan, hold=False, hold_product=False):
        run_id = str(uuid4())
        initialize(run_id, plan, month)
        try:
            perform("raw", run_id)
            def rows(path, selected_month=None):
                for feed, number, row in original(path, selected_month):
                    if hold and feed["entity"] == "payments" and number == delayed_number:
                        continue
                    if hold_product and feed["entity"] == "products" and row["product_id"] == inferred_product:
                        continue
                    yield feed, number, row
            admission.read_rows = rows
            validation = perform("validate", run_id)
            with connect() as c:
                c.execute("UPDATE ops.batches SET scenario_id=%s WHERE batch_id=%s", ("SC-005_simulated_delivery" if hold or plan.endswith("late-child") else "SC-002_monthly_replay", context(run_id)["batch_id"]))
            loading = perform("load", run_id)
            perform("lease", run_id)
            built = perform("build", run_id)
            with connect("snapshot") as c:
                quality = check_work(c, run_id)
            report["phases"].append({"run_id": run_id, "month": month, "plan": plan, "validation": validation, "load": loading, "build": built, "quality": quality})
            leases.release(run_id)
            mark_failed(run_id, "isolated_build_only_fixture")
            print(json.dumps({"phase": plan, "run_id": run_id, "new_versions": loading["new_versions"], "checks_passed": True}), flush=True)
            return run_id
        except Exception as error:
            mark_failed(run_id, type(error).__name__)
            try:
                leases.release(run_id)
            except Exception:
                pass
            raise
        finally:
            admission.read_rows = original

    try:
        phase("2017-01", "integration-monthly-inferred", hold_product=True)
        with connect("snapshot") as c:
            inferred = c.execute("SELECT product_key,is_inferred FROM work.dim_product WHERE product_id=%s", (inferred_product,)).fetchone()
            assert inferred["is_inferred"] and inferred["product_key"] > 0
            assert c.execute("SELECT count(*) AS n FROM work.fct_order_items WHERE product_key=%s", (inferred["product_key"],)).fetchone()["n"] > 0
        original_keys = registry()
        first_count = hashes()["fct_orders"]["n"]
        phase("2017-02", "integration-monthly-withheld", hold=True)
        with connect("snapshot") as c:
            enriched = c.execute("SELECT product_key,is_inferred FROM work.dim_product WHERE product_id=%s", (inferred_product,)).fetchone()
            assert not enriched["is_inferred"] and enriched["product_key"] == inferred["product_key"]
        report["inferred_enrichment"] = {"before": inferred, "after": enriched, "same_key": True, "fact_reference_preserved": True}
        assert hashes()["fct_orders"]["n"] > first_count
        with connect("snapshot") as c:
            before = c.execute("SELECT payment_record_count,recorded_payment_total FROM work.fct_orders WHERE order_id=%s", (delayed_payload["order_id"],)).fetchone()
        latest = phase("2017-02", "integration-late-child")
        assert report["phases"][-1]["load"]["new_versions"] == 1
        with connect("snapshot") as c:
            after = c.execute("SELECT payment_record_count,recorded_payment_total FROM work.fct_orders WHERE order_id=%s", (delayed_payload["order_id"],)).fetchone()
        assert after["payment_record_count"] == before["payment_record_count"] + 1
        report["late_child"] = {"order_id": delayed_payload["order_id"], "before": before, "after": after, "parent_recomputed": True}
        current_keys = registry()
        assert all(current_keys[key] == sk for key, sk in original_keys.items())
        before_replay = hashes()
        phase("2017-02", "integration-late-child")
        assert report["phases"][-1]["load"]["new_versions"] == 0 and hashes() == before_replay
        # New audit identity: a terminal build-only fixture is never reopened.
        from sales_dw.config import save_context
        rebuild_run = str(uuid4())
        initialize(rebuild_run, "simulated-full-refresh-verification")
        save_context(rebuild_run, **{k: context(latest)[k] for k in ("source_cut", "batch_id")})
        with connect() as c:
            c.execute("UPDATE ops.pipeline_runs SET source_cut=%s WHERE pipeline_run_id=%s", (context(latest)["source_cut"], rebuild_run))
        # Rebuild only the mutable working area under its lease, never consumer releases.
        leases.acquire(rebuild_run)
        transform.build(rebuild_run, full_refresh=True)
        after_rebuild = hashes()
        leases.release(rebuild_run)
        mark_failed(rebuild_run, "isolated_build_only_fixture")
        assert after_rebuild == before_replay and registry() == current_keys
        report.update(passed=True, replay_identical=True, full_incremental_equivalent=True, stable_registry=True, logical_hashes=after_rebuild)
    finally:
        (ROOT / "var/evidence/incremental.json").write_text(json.dumps(report, default=str, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "database": report["database"], "phases": len(report["phases"]), "late_child_recomputed": True, "full_incremental_equivalent": True}), flush=True)


if __name__ == "__main__":
    main()
