from .config import connect, save_context, context


def acquire(run_id):
    with connect("transform") as conn:
        row = conn.execute("""INSERT INTO ops.pipeline_leases(lease_name,owner_run_id,fencing_token,heartbeat_at,expires_at)
          VALUES('warehouse',%s,1,clock_timestamp(),clock_timestamp()+interval '20 minutes')
          ON CONFLICT(lease_name) DO UPDATE SET owner_run_id=excluded.owner_run_id,
          fencing_token=CASE WHEN pipeline_leases.owner_run_id=excluded.owner_run_id THEN pipeline_leases.fencing_token ELSE pipeline_leases.fencing_token+1 END,
          heartbeat_at=excluded.heartbeat_at,expires_at=excluded.expires_at
          WHERE pipeline_leases.owner_run_id=excluded.owner_run_id OR pipeline_leases.expires_at<=clock_timestamp()
          RETURNING fencing_token""", (run_id,)).fetchone()
        if row is None:
            raise RuntimeError("Another run owns the warehouse lease")
    save_context(run_id, fencing_token=row["fencing_token"])
    return row


def assert_owned(conn, run_id):
    token = context(run_id)["fencing_token"]
    conn.execute("SELECT ops.assert_lease(%s,%s)", (run_id, token))


def renew(run_id):
    with connect("transform") as conn:
        assert_owned(conn, run_id)
        conn.execute("UPDATE ops.pipeline_leases SET heartbeat_at=clock_timestamp(),expires_at=clock_timestamp()+interval '20 minutes' WHERE lease_name='warehouse'")


def release(run_id):
    with connect("transform") as conn:
        assert_owned(conn, run_id)
        conn.execute("UPDATE ops.pipeline_leases SET expires_at=clock_timestamp() WHERE lease_name='warehouse'")
