"""Read actual Airflow metadata and Warehouse audit; require success AND failure evidence."""
import json
from pathlib import Path
import subprocess
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "infra/compose.yaml")]


def query(db, statement):
    out = subprocess.run([*COMPOSE, "exec", "-T", "postgres", "psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-U", "salesdw_bootstrap", "-d", db, "-c", statement], capture_output=True, check=True, text=True)
    return json.loads(out.stdout)


def main():
    runs = query("airflow_meta", """SELECT coalesce(json_agg(x),'[]'::json) FROM (
      SELECT run_id,state,start_date,end_date,conf FROM dag_run
      WHERE dag_id='sales_warehouse_pipeline' ORDER BY id DESC) x""")
    successful = next(r for r in runs if r["state"] == "success" and r["conf"].get("fail_once") == "load")
    failed = next(r for r in runs if r["state"] == "failed" and r["conf"].get("fail_at") == "raw")
    tasks = query("airflow_meta", "SELECT json_agg(x) FROM (SELECT run_id,task_id,state,try_number FROM task_instance WHERE dag_id='sales_warehouse_pipeline' ORDER BY run_id,task_id) x")
    good = [t for t in tasks if t["run_id"] == successful["run_id"]]
    bad = [t for t in tasks if t["run_id"] == failed["run_id"]]
    assert len(good) == 9 and all(t["state"] == "success" for t in good)
    assert next(t for t in good if t["task_id"] == "load")["try_number"] == 2
    assert next(t for t in bad if t["task_id"] == "raw")["try_number"] == 3
    assert next(t for t in bad if t["task_id"] == "finish")["state"] == "upstream_failed"
    success_id, fail_id = [str(uuid5(NAMESPACE_URL, "salesdw:" + r["run_id"])) for r in (successful, failed)]
    audit = query("sales_dw", "SELECT json_agg(x) FROM (SELECT pipeline_run_id,state,error_category FROM ops.pipeline_runs WHERE pipeline_run_id IN ('" + success_id + "','" + fail_id + "')) x")
    assert {r["pipeline_run_id"]: r["state"] for r in audit} == {success_id: "succeeded", fail_id: "failed"}
    finish = json.loads((ROOT / "var/runs" / success_id / "finish.json").read_text())
    assert finish["result"]["publish_ack_replay"]
    publication = query("sales_dw", "SELECT json_agg(x) FROM (SELECT release_id,pipeline_run_id FROM ops.releases WHERE state='published') x")
    assert any(r["pipeline_run_id"] == success_id for r in publication)
    assert all(r["pipeline_run_id"] != fail_id for r in publication), "Failed run published a release"
    report = {"passed": True, "successful_retry": successful, "expected_terminal_failure": failed, "tasks": good + bad,
              "warehouse_audit": audit, "failed_run_did_not_publish": True, "publish_ack_replayed": True,
              "initial_debug_failures_retained": [r["run_id"] for r in runs if r["state"] == "failed" and r != failed]}
    (ROOT / "var/evidence/airflow.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "retry_run": successful["run_id"], "failure_run": failed["run_id"]}))


if __name__ == "__main__":
    main()
