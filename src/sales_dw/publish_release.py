"""The only runtime path that advances the published pointer."""
from .config import connect, context
from .leases import assert_owned

EXPORTS = {"sales_monthly", "sales_daily", "product_monthly", "seller_monthly", "buyer_state_monthly"}
REQUIRED = {"V-004", "V-005", "V-007", "V-013", "V-017"}


def publish(run_id):
    ctx = context(run_id)
    rid = ctx["release_id"]
    with connect("publish") as conn:
        release = conn.execute("SELECT * FROM ops.releases WHERE release_id=%s", (rid,)).fetchone()
        if release is None:
            raise RuntimeError("Candidate does not exist")
        if release["pipeline_run_id"] != __import__('uuid').UUID(str(run_id)) or release["fencing_token"] != ctx["fencing_token"]:
            raise RuntimeError("Candidate ownership does not match the fenced run")
        # Acknowledging a durable commit performs no publication mutation and
        # remains valid after lease expiry/takeover or a newer publication.
        if release["state"] == "published":
            return {"release_id": rid, "state": "published", "recovered_ack": True}
        assert_owned(conn, run_id)
        release = conn.execute("SELECT * FROM ops.releases WHERE release_id=%s FOR UPDATE", (rid,)).fetchone()
        if release["state"] == "published":
            return {"release_id": rid, "state": "published", "recovered_ack": True}
        if release["state"] != "metrics_validated":
            raise RuntimeError("Candidate is not metrics-validated")
        checks = {r["check_id"] for r in conn.execute("SELECT check_id FROM ops.check_results WHERE release_id=%s AND state='passed'", (rid,))}
        snapshots = conn.execute("SELECT count(*) AS n,bool_and(validated) AS valid FROM ops.snapshot_relations WHERE release_id=%s", (rid,)).fetchone()
        exports = {r["export_id"] for r in conn.execute("SELECT export_id FROM ops.export_queries WHERE release_id=%s", (rid,))}
        if not REQUIRED <= checks or snapshots != {"n": 10, "valid": True} or exports != EXPORTS:
            raise RuntimeError("Missing snapshot, checks or exports; publication blocked")
        previous = conn.execute("SELECT r.source_cut FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main' FOR UPDATE OF p").fetchone()
        if previous and previous["source_cut"] > release["source_cut"]:
            raise RuntimeError("Source cut regression blocked")
        conn.execute("UPDATE ops.releases SET state='published',published_at=clock_timestamp() WHERE release_id=%s", (rid,))
        conn.execute("INSERT INTO ops.published_release(channel,release_id) VALUES('main',%s) ON CONFLICT(channel) DO UPDATE SET release_id=excluded.release_id,updated_at=clock_timestamp()", (rid,))
        conn.execute("INSERT INTO ops.state_events(pipeline_run_id,release_id,actor_role,previous_state,new_state,reason,fencing_token) VALUES(%s,%s,current_user,'metrics_validated','published','All required model and metric gates passed',%s)", (run_id, rid, ctx["fencing_token"]))
    return {"release_id": rid, "state": "published", "atomic_boundary": "PostgreSQL only; Metabase delivery separate"}
