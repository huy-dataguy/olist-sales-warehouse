"""Exercise transaction rollback, parity blocking and recovery against real services.

Only an isolated restored database is accepted. Source and main database remain
unchanged. Internal injected failures model retries, not forced state resets.
"""
import json
import os
import subprocess
import sys
from uuid import uuid4

from sales_dw.cli import initialize, perform
from sales_dw.config import ROOT, settings, connect, context, save_context, run_dir


def pointer():
    with connect("snapshot") as c:
        return c.execute("SELECT release_id FROM ops.published_release WHERE channel='main'").fetchone()["release_id"]


def main():
    assert settings()["dbname"].startswith("sales_dw_restore_")
    old_release = pointer()
    with connect("snapshot") as c:
        base_run = c.execute("SELECT pipeline_run_id FROM ops.releases WHERE release_id=%s", (old_release,)).fetchone()["pipeline_run_id"]
        original_source = c.execute("SELECT count(*) AS n FROM landing.source_versions").fetchone()["n"]
    failed_run = str(uuid4())
    log = run_dir(failed_run) / "expected-build-failure.log"
    with log.open("w") as stream:
        attempt = subprocess.run([sys.executable, "-m", "sales_dw.cli", "run", "--run-id", failed_run, "--resume-from", str(base_run), "--fail-at", "build"], stdout=stream, stderr=subprocess.STDOUT, timeout=60)
    assert attempt.returncode != 0 and pointer() == old_release
    with connect() as c:
        assert c.execute("SELECT state FROM ops.pipeline_runs WHERE pipeline_run_id=%s", (failed_run,)).fetchone()["state"] == "failed"
        assert c.execute("SELECT count(*) AS n FROM landing.source_versions").fetchone()["n"] == original_source
    run = str(uuid4())
    previous = context(failed_run)
    initialize(run, "simulated-transaction-recovery")
    save_context(run, **{k: previous[k] for k in ("plan_id", "month", "archive", "artifact_sha256", "batch_id", "source_counts", "validated")})
    report = {"passed": False, "database": settings()["dbname"], "run_id": run, "failed_run": failed_run, "checks": {"load_commit_survived": True}}
    try:
        report["load"] = perform("load", run)
        assert report["load"]["new_versions"] == 0
        perform("lease", run)
        report["build"] = perform("build", run)
        os.environ["SALES_DW_FAULT_POINT"] = "snapshot.after.dim_product"
        try:
            perform("snapshot", run)
        except RuntimeError as error:
            assert "Simulated internal failure" in str(error)
        else:
            raise AssertionError("Snapshot fault not reached")
        os.environ.pop("SALES_DW_FAULT_POINT")
        rid = context(run)["release_id"]
        with connect("snapshot") as c:
            assert not c.execute("SELECT 1 FROM ops.releases WHERE release_id=%s", (rid,)).fetchone()
            assert c.execute("SELECT count(*) AS n FROM warehouse_store.dim_customer WHERE release_id=%s", (rid,)).fetchone()["n"] == 0
        assert pointer() == old_release
        report["checks"]["snapshot_transaction_rolled_back"] = True
        print("snapshot partial copy: rollback PASS", flush=True)
        report["snapshot"] = perform("snapshot", run)
        for point, exception in (("semantic.after.sales_monthly", RuntimeError), ("parity_result", AssertionError)):
            os.environ["SALES_DW_FAULT_POINT"] = point
            try:
                perform("semantic", run)
            except exception:
                pass
            else:
                raise AssertionError("Semantic fault not rejected: " + point)
            finally:
                os.environ.pop("SALES_DW_FAULT_POINT", None)
            with connect("snapshot") as c:
                assert c.execute("SELECT count(*) AS n FROM ops.export_queries WHERE release_id=%s", (rid,)).fetchone()["n"] == 0
                assert c.execute("SELECT state FROM ops.releases WHERE release_id=%s", (rid,)).fetchone()["state"] == "snapshotted"
            try:
                perform("publish", run)
            except RuntimeError:
                pass
            else:
                raise AssertionError("Failed metric attempt could publish")
            assert pointer() == old_release
            report["checks"][point] = {"rollback": True, "publication_blocked": True}
            print(point + ": rollback and publication block PASS", flush=True)
        os.environ["SALES_DW_FAULT_POINT"] = "semantic.after_commit"
        try:
            perform("semantic", run)
        except RuntimeError as error:
            assert "Simulated internal failure" in str(error)
        else:
            raise AssertionError("Post-commit semantic fault not reached")
        finally:
            os.environ.pop("SALES_DW_FAULT_POINT", None)
        assert pointer() == old_release
        report["semantic"] = perform("semantic", run)
        assert report["semantic"]["recovered_commit"]
        report["checks"]["semantic_commit_acknowledgement_recovered"] = True
        report["publish"] = perform("publish", run)
        report["ack"] = perform("publish", run)
        assert report["ack"]["recovered_ack"]
        report["finish"] = perform("finish", run)
        assert str(pointer()) == rid
        with connect("snapshot") as c:
            assert c.execute("SELECT count(*) AS n FROM landing.source_versions").fetchone()["n"] == original_source
            assert c.execute("SELECT count(*) AS n FROM ops.state_events WHERE release_id=%s AND new_state='published'", (rid,)).fetchone()["n"] == 1
        report["passed"] = True
    finally:
        os.environ.pop("SALES_DW_FAULT_POINT", None)
        (ROOT / "var/evidence/pipeline-recovery.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({"passed": True, "run_id": run, "release_id": rid, "checks": list(report["checks"])}))


if __name__ == "__main__":
    main()
