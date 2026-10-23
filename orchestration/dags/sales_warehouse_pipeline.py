"""Stage boundaries are real runtime CLI calls; XCom never carries source rows."""
from datetime import timedelta
import os
import subprocess

import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


def record_failure(context):
    subprocess.run(["/opt/sales-venv/bin/python", "-m", "sales_dw.cli", "fail",
                    "--airflow-run-id", context["run_id"]], check=True, timeout=30,
                   env={**os.environ, "PYTHONPATH": "/workspace/src"})


with DAG(
    dag_id="sales_warehouse_pipeline", schedule="0 2 * * *",
    start_date=pendulum.datetime(2026, 10, 1, tz="Asia/Ho_Chi_Minh"), catchup=False,
    max_active_runs=1, tags=["olist", "kimball", "dbt", "production-local"],
    default_args={"retries": 2, "retry_delay": timedelta(seconds=30),
                  "execution_timeout": timedelta(minutes=15), "on_failure_callback": record_failure},
    description="Immutable Olist raw → fixed source cut → Kimball → MetricFlow → fenced publication",
) as dag:
    previous = None
    for stage in ("raw", "validate", "load", "lease", "build", "snapshot", "semantic", "publish", "finish"):
        command = f'''set -euo pipefail
args=({stage} --airflow-run-id "$SALES_AIRFLOW_RUN_ID" --month "$SALES_BATCH_MONTH" --plan-id "$SALES_PLAN_ID")
if [ "$SALES_FAIL_STAGE" = "{stage}" ]; then args+=(--fail-at "{stage}"); fi
if [ "$SALES_FAIL_ONCE" = "{stage}" ] && [ "$SALES_TRY_NUMBER" = "1" ]; then args+=(--fail-at "{stage}"); fi
/opt/sales-venv/bin/python -m sales_dw.cli "${{args[@]}}"
'''
        task = BashOperator(
            task_id=stage, bash_command=command, cwd="/workspace", append_env=True,
            env={"SALES_AIRFLOW_RUN_ID": "{{ run_id }}",
                 "SALES_BATCH_MONTH": "{{ dag_run.conf.get('month', '') }}",
                 "SALES_PLAN_ID": "{{ dag_run.conf.get('plan_id', 'full-v2') }}",
                 "SALES_FAIL_ONCE": "{{ dag_run.conf.get('fail_once', '') }}",
                 "SALES_TRY_NUMBER": "{{ ti.try_number }}",
                 "SALES_FAIL_STAGE": "{{ dag_run.conf.get('fail_at', '') }}"},
            do_xcom_push=False,
        )
        if previous is not None:
            previous >> task
        previous = task
