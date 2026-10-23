"""Host-side logical backup and approved isolated restore drill. No overwrite/drop path.

Backups are private local files (0600), not encrypted/off-host backups. Metadata
database dumps have their own snapshot times; there is no cross-database transaction.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "infra/compose.yaml")]


def run(args, **kwargs):
    return subprocess.run(args, check=True, cwd=ROOT, **kwargs)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def query(database, statement):
    result = run([*COMPOSE, "exec", "-T", "postgres", "psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-U", "salesdw_bootstrap", "-d", database, "-c", statement], capture_output=True, text=True)
    return result.stdout.strip()


def signature(database):
    return json.loads(query(database, """SELECT json_build_object(
      'release_id',(SELECT release_id FROM ops.published_release WHERE channel='main'),
      'source_versions',(SELECT count(*) FROM landing.source_versions),
      'registry_rows',(SELECT count(*) FROM ops.dimension_key_registry),
      'registry_hash',(SELECT md5(string_agg(surrogate_key||':'||namespace||':'||natural_key||':'||version_identity,'|' ORDER BY surrogate_key)) FROM ops.dimension_key_registry),
      'snapshots',(SELECT json_agg(row_to_json(s) ORDER BY model_name) FROM ops.snapshot_relations s WHERE release_id=(SELECT release_id FROM ops.published_release WHERE channel='main')),
      'orders',(SELECT count(*) FROM warehouse.fct_orders),
      'items',(SELECT count(*) FROM warehouse.fct_order_items),
      'payments',(SELECT count(*) FROM warehouse.fct_payments),
      'delivered_value',(SELECT sum(delivered_merchandise_value) FROM reporting.validated_sales_monthly WHERE release_id=(SELECT release_id FROM ops.published_release WHERE channel='main'))
    )"""))


def backup():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "var/backups" / stamp
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {"created_at": stamp, "scope": "same-host logical recovery; metadata snapshots are separate", "encrypted": False,
                "source_signature": signature("sales_dw"), "databases": {}, "migrations": {p.name: sha(p) for p in sorted((ROOT / "db/migrations").glob("*.sql"))}}
    if not manifest["source_signature"]["release_id"]:
        raise RuntimeError("Publish and validate a release before backup acceptance")
    databases=["sales_dw", "airflow_meta", "metabase_meta"]
    if query('sales_dw',"SELECT count(*) FROM pg_database WHERE datname='superset_meta'")=='1':
        databases.append('superset_meta')
    for database in databases:
        path = folder / (database + ".dump")
        role = "salesdw_backup" if database == "sales_dw" else "salesdw_bootstrap"
        secret = "backup_password" if database == "sales_dw" else "postgres_password"
        env = {**os.environ, "PGPASSWORD": (ROOT / "var/secrets" / secret).read_text().strip()}
        started = time.monotonic()
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            run([*COMPOSE, "exec", "-T", "-e", "PGPASSWORD", "postgres", "pg_dump", "-h", "127.0.0.1", "-U", role, "-Fc", "--compress=3", database], env=env, stdout=stream)
        manifest["databases"][database] = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha(path), "seconds": round(time.monotonic()-started, 3), "role": role}
    raw = ROOT / "data/raw/olist/brazilian-ecommerce-v2.zip"
    copy = folder / raw.name
    shutil.copyfile(raw, copy)
    os.chmod(copy, 0o600)
    manifest["raw_archive"] = {"file": copy.name, "sha256": sha(copy), "bytes": copy.stat().st_size}
    manifest["postgres_version"] = query("sales_dw", "SHOW server_version")
    manifest["images"] = run([*COMPOSE, "images", "--format", "json"], capture_output=True, text=True).stdout
    if signature("sales_dw") != manifest["source_signature"]:
        raise RuntimeError("Publication changed during backup; rerun under an idle pipeline")
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "var/evidence/backup.json").write_text(json.dumps({"passed": True, "manifest": str(folder / "manifest.json"), "bytes": sum(p.stat().st_size for p in folder.iterdir())}, indent=2) + "\n")
    print(json.dumps({"backup": str(folder), "passed": True}))
    return folder


def restore(folder):
    folder = folder.resolve()
    if not folder.is_relative_to((ROOT / "var/backups").resolve()):
        raise ValueError("Backup must be inside this project's private backup directory")
    manifest = json.loads((folder / "manifest.json").read_text())
    for item in [*manifest["databases"].values(), manifest["raw_archive"]]:
        file = folder / item["file"]
        if file.parent != folder or sha(file) != item["sha256"]:
            raise RuntimeError("Backup checksum/path validation failed")
    before = signature("sales_dw")
    target = "sales_dw_restore_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    assert re.fullmatch(r"sales_dw_restore_[0-9_]+", target)
    started = time.monotonic()
    run([*COMPOSE, "run", "--rm", "migrate", "--apply", "--approved-project", "salesdw", "--restore-target", target])
    with (folder / manifest["databases"]["sales_dw"]["file"]).open("rb") as stream:
        run([*COMPOSE, "exec", "-T", "postgres", "pg_restore", "--exit-on-error", "--single-transaction", "-U", "salesdw_bootstrap", "-d", target], stdin=stream)
    # Controlled recovery DML only in the freshly created target. Live DB untouched.
    query(target, """BEGIN;
      INSERT INTO ops.state_events(pipeline_run_id,actor_role,previous_state,new_state,reason)
        SELECT pipeline_run_id,current_user,state,'failed','Isolated restore invalidated captured inflight run'
        FROM ops.pipeline_runs WHERE state IN ('created','running');
      UPDATE ops.pipeline_runs SET state='failed',finished_at=clock_timestamp(),error_category='restore_abandoned'
        WHERE state IN ('created','running');
      UPDATE ops.pipeline_leases SET heartbeat_at=clock_timestamp()-interval '2 seconds',expires_at=clock_timestamp()-interval '1 second',fencing_token=fencing_token+1;
      COMMIT;""")
    recovered = signature(target)
    if recovered != manifest["source_signature"] or signature("sales_dw") != before:
        raise AssertionError("Restored signature mismatch or live database changed")
    report = {"passed": True, "target": target, "restore_seconds": round(time.monotonic()-started, 3), "manifest": str(folder / "manifest.json"),
              "signature": recovered, "live_unchanged": True, "scope": "DWH schema/data/ACL restored; app database dumps retained but app restore not claimed", "rto_target_seconds": 1800}
    (ROOT / "var/evidence/restore.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "signature"}, indent=2))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("backup", "restore", "drill"))
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    folder = backup() if args.command in {"backup", "drill"} else args.backup
    if args.command in {"restore", "drill"}:
        if folder is None:
            parser.error("restore requires --backup")
        restore(folder)


if __name__ == "__main__":
    main()
