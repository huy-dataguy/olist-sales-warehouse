"""Small, retry-safe stage entrypoints used by CLI and Airflow alike."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import psycopg

from .config import ROOT, connect, context, run_dir, save_context

STAGES = ("raw", "validate", "load", "lease", "build", "snapshot", "semantic", "publish", "finish")


def initialize(run_id, plan_id="full-v2", month=None, airflow_run_id=None):
    month = month or None
    UUID(str(run_id))
    path = run_dir(run_id) / "context.json"
    if not path.exists():
        save_context(run_id, plan_id=plan_id, month=month, airflow_run_id=airflow_run_id)
    with connect() as conn:
        conn.execute("INSERT INTO ops.pipeline_runs(pipeline_run_id,airflow_run_id,state) VALUES(%s,%s,'created') ON CONFLICT DO NOTHING", (run_id, airflow_run_id))
        conn.execute("UPDATE ops.pipeline_runs SET state='running' WHERE pipeline_run_id=%s AND state='created'", (run_id,))
        state = conn.execute("SELECT state FROM ops.pipeline_runs WHERE pipeline_run_id=%s", (run_id,)).fetchone()["state"]
        if state == "failed":
            raise ValueError("Failed run is immutable; start a new run with --resume-from")


def mark_failed(run_id, category):
    with connect() as conn:
        conn.execute("UPDATE ops.pipeline_runs SET state='failed',finished_at=clock_timestamp(),error_category=%s WHERE pipeline_run_id=%s AND state IN ('created','running')", (category, run_id))
    ctx_path = run_dir(run_id) / "context.json"
    if ctx_path.exists() and context(run_id).get("release_id"):
        with connect("snapshot") as conn:
            conn.execute("UPDATE ops.releases SET state='failed' WHERE release_id=%s AND state<>'published'", (context(run_id)["release_id"],))


def perform(stage, run_id):
    if stage == "raw":
        from .capacity import preflight
        preflight()
        from .raw_storage import preserve
        return preserve(run_id)
    if stage in {"validate", "load"}:
        from . import admission
        return getattr(admission, stage)(run_id)
    if stage == "lease":
        from .leases import acquire
        return acquire(run_id)
    if stage == "build":
        from .transform import build
        return build(run_id)
    if stage == "snapshot":
        from .capacity import preflight
        preflight()
        from .snapshot_release import snapshot
        return snapshot(run_id)
    if stage == "semantic":
        from .export_metrics import export
        return export(run_id)
    if stage == "publish":
        from .publish_release import publish
        return publish(run_id)
    if stage == "finish":
        from .leases import release
        from .publish_release import publish
        # A successful final task requires a committed publication. Replaying the
        # publication request also covers acknowledgement-loss recovery.
        acknowledgment = publish(run_id)
        if not acknowledgment.get("recovered_ack"):
            raise RuntimeError("Finish expected an already published release")
        with connect() as conn:
            conn.execute("UPDATE ops.pipeline_runs SET state='succeeded',finished_at=clock_timestamp() WHERE pipeline_run_id=%s AND state='running'", (run_id,))
        cleanup = "released"
        try:
            release(run_id)
        except psycopg.errors.RaiseException:
            # The durable publication has already succeeded. A late ACK must
            # not fail merely because its lease expired or a new owner took it.
            # release() checks owner/fence before touching the lease, so the new
            # owner's lease stays intact. Other SQL/connection errors propagate.
            cleanup = "already_expired_or_reassigned"
        return {"state": "succeeded", "release_id": context(run_id).get("release_id"), "publish_ack_replay": True, "lease_cleanup": cleanup}
    raise ValueError(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "doctor", "fail", *STAGES])
    parser.add_argument("--run-id")
    parser.add_argument("--airflow-run-id")
    parser.add_argument("--month")
    parser.add_argument("--plan-id", default="full-v2")
    parser.add_argument("--fail-at", choices=STAGES)
    parser.add_argument("--resume-from", help="New attempt from an already committed/validated batch; no source re-extraction")
    args = parser.parse_args()
    if args.month and not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", args.month):
        parser.error("month must be YYYY-MM")
    if args.command == "doctor":
        from .raw_storage import client
        from .config import settings
        with connect("bi") as conn:
            role = conn.execute("SELECT current_user AS role,current_database() AS db").fetchone()
        assert client().bucket_exists(settings()["s3"]["bucket"])
        print(json.dumps({"database": role, "s3_reachable": True}))
        return
    run_id = args.run_id or (str(uuid5(NAMESPACE_URL, "salesdw:" + args.airflow_run_id)) if args.airflow_run_id else str(uuid4()))
    if args.command == "fail":
        mark_failed(run_id, "airflow_task_failure")
        try:
            from .leases import release
            if context(run_id).get("fencing_token"):
                release(run_id)
        except Exception:
            pass  # A stale owner must never release someone else's lease.
        return
    initialize(run_id, args.plan_id, args.month, args.airflow_run_id)
    if args.resume_from:
        previous = context(args.resume_from)
        with connect() as conn:
            admitted = conn.execute("SELECT state,artifact_sha256 FROM ops.batches WHERE batch_id=%s", (previous.get("batch_id"),)).fetchone()
        if not admitted or admitted["state"] != "loaded" or admitted["artifact_sha256"] != previous.get("artifact_sha256"):
            raise ValueError("Resume requires a committed batch with matching artifact identity")
        save_context(run_id, **{k: previous[k] for k in ("plan_id", "month", "archive", "artifact_sha256", "batch_id", "source_counts", "validated")})
    print(json.dumps({"event": "run_context", "run_id": run_id}), flush=True)
    try:
        stages = STAGES[2:] if args.resume_from else STAGES
        for stage in stages if args.command == "run" else (args.command,):
            started = time.monotonic()
            print(json.dumps({"event": "stage_started", "stage": stage, "run_id": run_id}), flush=True)
            if stage == args.fail_at:
                raise RuntimeError("Injected failure at " + stage)
            result = perform(stage, run_id)
            evidence = {"stage": stage, "run_id": run_id, "elapsed_seconds": round(time.monotonic() - started, 3), "result": result, "passed": True}
            (run_dir(run_id) / (stage + ".json")).write_text(json.dumps(evidence, default=str, indent=2) + "\n")
            print(json.dumps({"event": "stage_succeeded", **evidence}, default=str), flush=True)
    except Exception as exc:
        # Error details stay in the bounded operator log; never print connection strings.
        print(json.dumps({"event": "stage_failed", "run_id": run_id, "stage": stage, "category": type(exc).__name__, "error": str(exc)[:1000]}), flush=True)
        if not args.airflow_run_id:
            mark_failed(run_id, type(exc).__name__)
            try:
                from .leases import release
                if "fencing_token" in context(run_id):
                    release(run_id)
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
