"""Fenced operator pointer switch to a retained, previously validated release.

No snapshot, source cut or dbt checkpoint is reset. Old pinned consumers remain
valid. The expected-current guard prevents applying a stale operator plan.
"""
from uuid import UUID, uuid4

from .config import connect, save_context
from .leases import acquire, assert_owned, release
from .publish_release import EXPORTS, REQUIRED


def plan(target_release, expected_current):
    target_release, expected_current = str(UUID(str(target_release))), str(UUID(str(expected_current)))
    with connect("publish") as conn:
        current = conn.execute("SELECT release_id FROM ops.published_release WHERE channel='main'").fetchone()
        if current is None or str(current["release_id"]) != expected_current:
            raise RuntimeError("Publication changed; obtain a new rollback plan")
        target = conn.execute("SELECT * FROM ops.releases WHERE release_id=%s", (target_release,)).fetchone()
        if target is None or target["state"] != "published":
            raise RuntimeError("Rollback only accepts an ever-published retained release")
        snapshots = conn.execute("SELECT count(*) AS n,bool_and(validated) AS valid FROM ops.snapshot_relations WHERE release_id=%s", (target_release,)).fetchone()
        checks = {r["check_id"] for r in conn.execute("SELECT check_id FROM ops.check_results WHERE release_id=%s AND state='passed'", (target_release,))}
        exports = {r["export_id"] for r in conn.execute("SELECT export_id FROM ops.export_queries WHERE release_id=%s", (target_release,))}
        if snapshots != {"n": 10, "valid": True} or not REQUIRED <= checks or exports != EXPORTS:
            raise RuntimeError("Retained release is missing its acceptance metadata")
    return {"operation": "rollback_publication_pointer", "expected_current": expected_current,
            "target_release": target_release, "target_source_cut": target["source_cut"],
            "data_deleted": False, "source_or_checkpoints_reset": False}


def apply(target_release, expected_current, reason):
    if len(reason.strip()) < 10:
        raise ValueError("A meaningful operator reason is required")
    proposal = plan(target_release, expected_current)
    run = str(uuid4())
    save_context(run, plan_id="operator-rollback", **proposal)
    with connect() as conn:
        conn.execute("INSERT INTO ops.pipeline_runs(pipeline_run_id,state,source_cut) VALUES(%s,'running',%s)", (run, proposal["target_source_cut"]))
    acquired = False
    try:
        fence = acquire(run)["fencing_token"]
        acquired = True
        with connect("publish") as conn:
            assert_owned(conn, run)
            current = conn.execute("SELECT release_id FROM ops.published_release WHERE channel='main' FOR UPDATE").fetchone()
            if str(current["release_id"]) != proposal["expected_current"]:
                raise RuntimeError("Concurrent publication invalidated the operator plan")
            conn.execute("UPDATE ops.published_release SET release_id=%s,updated_at=clock_timestamp() WHERE channel='main'", (proposal["target_release"],))
            conn.execute("INSERT INTO ops.state_events(pipeline_run_id,release_id,actor_role,previous_state,new_state,reason,fencing_token) VALUES(%s,%s,current_user,'published_pointer','rollback_pointer',%s,%s)",
                         (run, proposal["target_release"], f"from={proposal['expected_current']}; {reason.strip()}", fence))
        with connect() as conn:
            conn.execute("UPDATE ops.pipeline_runs SET state='succeeded',finished_at=clock_timestamp() WHERE pipeline_run_id=%s", (run,))
        return {**proposal, "operation_run_id": run, "applied": True}
    except Exception:
        with connect() as conn:
            conn.execute("UPDATE ops.pipeline_runs SET state='failed',finished_at=clock_timestamp(),error_category='operator_rollback_failure' WHERE pipeline_run_id=%s AND state='running'", (run,))
        raise
    finally:
        if acquired:
            release(run)
