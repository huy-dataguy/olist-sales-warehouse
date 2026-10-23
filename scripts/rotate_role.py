"""Credential rotation helper, invoked ONLY by the controlled migrate entrypoint."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets

import psycopg
from psycopg import sql
import requests


def atomic_private(path, text):
    temporary = path.with_name(path.name + ".rotation-new")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def rotate_bi(root, bootstrap, runtime):
    account = runtime["roles"]["bi"]
    assert account["user"] == "salesdw_bi" and runtime["dbname"] == "sales_dw"
    old_password, new_password = account["password"], secrets.token_urlsafe(32)
    state = json.loads((root / "var/bi/state.json").read_text())
    admin = json.loads((root / "var/secrets/bi_admin.json").read_text())
    session = requests.Session()
    login = session.post("http://metabase:3000/api/session", json={"username": admin["email"], "password": admin["password"]}, timeout=30)
    login.raise_for_status()
    session.headers["X-Metabase-Session"] = login.json()["id"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    atomic_private(root / ("var/secrets/rotation-bi-" + stamp + ".json"), json.dumps({"role": account["user"], "old_password": old_password}) + "\n")
    kwargs = {k: bootstrap[k] for k in ("host", "port", "dbname", "user", "password")}

    def update_metabase(password):
        details = {"host": runtime["host"], "port": runtime["port"], "dbname": "sales_dw", "user": "salesdw_bi", "password": password, "ssl": False, "tunnel-enabled": False}
        reply = session.put(f"http://metabase:3000/api/database/{state['database_id']}", json={"details": details}, timeout=60)
        reply.raise_for_status()

    with psycopg.connect(**kwargs, autocommit=True) as operator:
        try:
            operator.execute(sql.SQL("ALTER ROLE salesdw_bi PASSWORD {}").format(sql.Literal(new_password)))
            probe = {"host": runtime["host"], "port": runtime["port"], "dbname": "sales_dw", "user": "salesdw_bi", "password": old_password, "connect_timeout": 5}
            try:
                with psycopg.connect(**probe):
                    pass
            except psycopg.OperationalError as error:
                if "password authentication failed" not in str(error):
                    raise
            else:
                raise AssertionError("Old credential still authenticates")
            with psycopg.connect(**{**probe, "password": new_password}) as connection:
                assert connection.execute("SELECT count(*) FROM reporting.validated_sales_monthly").fetchone()[0] > 0
            update_metabase(new_password)
            runtime["roles"]["bi"]["password"] = new_password
            atomic_private(root / "var/secrets/runtime.json", json.dumps(runtime) + "\n")
            atomic_private(root / "var/secrets/bi_password", new_password + "\n")
        except Exception:
            operator.execute(sql.SQL("ALTER ROLE salesdw_bi PASSWORD {}").format(sql.Literal(old_password)))
            runtime["roles"]["bi"]["password"] = old_password
            atomic_private(root / "var/secrets/runtime.json", json.dumps(runtime) + "\n")
            atomic_private(root / "var/secrets/bi_password", old_password + "\n")
            update_metabase(old_password)
            raise
    evidence = {"passed": True, "role": "salesdw_bi", "old_connection_denied": True, "new_connection_succeeded": True, "metabase_connection_updated": True,
                "rotated_at": stamp, "follow_up": "Recreate long-lived Airflow containers to remount the atomic runtime-secret file; no other credentials changed."}
    (root / "var/evidence/rotation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))
