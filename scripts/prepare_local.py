"""Generate isolated local secrets once; never print secrets or overwrite existing ones."""
import json
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / "var"
for name in ("secrets", "runs", "evidence", "backups", "airflow-logs", "dbt", "bi", "source-cache", "docs", "superset", "analysis"):
    path = base / name
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700 if name == "secrets" else 0o770)

def write_once(name, value):
    path = base / "secrets" / name
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    with os.fdopen(fd, "w") as out:
        out.write(value + "\n")
    return value

passwords = {name: write_once(name + "_password", secrets.token_urlsafe(32)) for name in
             ("postgres", "ingest", "transform", "snapshot", "semantic", "publish", "analyst", "bi", "backup", "airflow", "metabase")}
write_once("minio_root_user", "salesdw_operator")
write_once("minio_root_password", secrets.token_urlsafe(32))
raw_password = write_once("raw_ingest_password", secrets.token_urlsafe(32))
roles = {r: {"user": "salesdw_" + r, "password": passwords[r]} for r in passwords if r not in ("postgres", "airflow", "metabase")}
runtime = {"host": "postgres", "port": 5432, "dbname": "sales_dw", "roles": roles,
           "s3": {"endpoint": "minio:9000", "access_key": "salesdw_ingest", "secret_key": raw_password, "bucket": "salesdw-raw"}}
write_once("runtime.json", json.dumps(runtime))
bootstrap = {"host": "postgres", "port": 5432, "dbname": "sales_dw", "user": "salesdw_bootstrap",
             "password": passwords["postgres"], "metadata": {n: passwords[n] for n in ("airflow", "metabase")},
             "s3_user": (base / "secrets/minio_root_user").read_text().strip(),
             "s3_password": (base / "secrets/minio_root_password").read_text().strip()}
write_once("bootstrap.json", json.dumps(bootstrap))
write_once("airflow_connection", f"postgresql+psycopg2://salesdw_airflow:{passwords['airflow']}@postgres:5432/airflow_meta")
write_once("bi_admin.json", json.dumps({"email": "demo@salesdw.local", "password": secrets.token_urlsafe(24)}))
write_once("superset.json", json.dumps({"metadata_password": secrets.token_urlsafe(32), "secret_key": secrets.token_urlsafe(64)}))
write_once("superset_admin.json", json.dumps({"username": "demo", "first_name": "Demo", "last_name": "Reviewer", "email": "demo@salesdw.local", "password": secrets.token_urlsafe(24)}))
current_runtime = json.loads((base / "secrets/runtime.json").read_text())
write_once("superset_warehouse.json", json.dumps({"host": current_runtime["host"], "port": current_runtime["port"], "dbname": current_runtime["dbname"], **current_runtime["roles"]["bi"]}))
env = ROOT / ".env"
if not env.exists():
    fd = os.open(env, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(f"LOCAL_UID={os.getuid()}\nAIRFLOW_JWT_SECRET={secrets.token_urlsafe(40)}\n")
print("Local secrets ready (values redacted). No services or migrations were executed.")
