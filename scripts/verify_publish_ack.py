"""Late committed-publication ACK must survive lease takeover without mutation."""
import json
from uuid import uuid4

from sales_dw.cli import initialize, perform, mark_failed
from sales_dw.config import ROOT, connect, settings
from sales_dw import leases


def main():
    assert settings()["dbname"].startswith("sales_dw_restore_"), "Isolated target required"
    with connect("publish") as c:
        original = c.execute("SELECT p.release_id,r.pipeline_run_id FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main'").fetchone()
        acknowledged = c.execute("SELECT release_id,pipeline_run_id FROM ops.releases WHERE state='published' AND release_id<>%s ORDER BY published_at DESC LIMIT 1", (original["release_id"],)).fetchone()
        assert acknowledged is not None, "Requires two retained ever-published releases"
        events_before = c.execute("SELECT count(*) AS n FROM ops.state_events WHERE new_state='published'").fetchone()["n"]
    old_run = str(acknowledged["pipeline_run_id"])
    guard = str(uuid4())
    initialize(guard, "simulated-lease-takeover-after-publication")
    leases.acquire(guard)
    report = {"passed": False, "database": settings()["dbname"], "published_run": old_run, "new_lease_owner": guard,
              "acknowledged_release": str(acknowledged["release_id"]), "current_pointer": str(original["release_id"])}
    try:
        report["publish_ack"] = perform("publish", old_run)
        assert report["publish_ack"]["recovered_ack"]
        report["finish_ack"] = perform("finish", old_run)
        assert report["finish_ack"]["lease_cleanup"] == "already_expired_or_reassigned"
        with connect("publish") as c:
            leases.assert_owned(c, guard)
            assert c.execute("SELECT release_id FROM ops.published_release WHERE channel='main'").fetchone()["release_id"] == original["release_id"]
            assert c.execute("SELECT count(*) AS n FROM ops.state_events WHERE new_state='published'").fetchone()["n"] == events_before
        report.update(passed=True, newer_owner_intact=True, pointer_unchanged=True, no_duplicate_publication=True)
    finally:
        leases.release(guard)
        mark_failed(guard, "expected_isolated_lease_takeover_fixture")
        (ROOT / "var/evidence/ack-recovery.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "late_ack_after_takeover": True, "new_owner_intact": True}))


if __name__ == "__main__":
    main()
