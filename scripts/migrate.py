"""Controlled, checksummed additive migration entrypoint for project-owned databases.

Default is plan-only. --apply requires --approved-project salesdw. This specific
target was explicitly approved by the user; no DROP/TRUNCATE/reset exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import re

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from minio import Minio, MinioAdmin
from minio.credentials import StaticProvider

ROOT = Path("/workspace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-project")
    parser.add_argument("--restore-target", help="Create a NEW isolated sales_dw_restore_<suffix> database; never overwrite")
    parser.add_argument("--initialize-empty", action="store_true", help="Apply migrations to the new isolated target for integration testing")
    parser.add_argument("--rotate-role", choices=["bi"], help="Rotate the dedicated BI credential and its Metabase connection, with rollback on failure")
    parser.add_argument("--superset", action="store_true", help="Provision isolated superset_meta / salesdw_superset for the user-requested BI replacement")
    args = parser.parse_args()
    migrations = sorted((ROOT / "db/migrations").glob("[0-9]*.sql"))
    plan = [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in migrations]
    print(json.dumps({"project": "salesdw", "database": args.restore_target or "sales_dw", "additional_metadata": ["superset_meta"] if args.superset else [], "destructive": False, "rotate_role": args.rotate_role, "migrations": plan}, indent=2))
    if not args.apply:
        return
    if args.approved_project != "salesdw":
        raise SystemExit("Explicit --approved-project salesdw required")
    cfg = json.loads(Path("/run/secrets/bootstrap.json").read_text())
    runtime = json.loads(Path("/run/secrets/runtime.json").read_text())
    if cfg["host"] != "postgres" or cfg["dbname"] != "sales_dw" or cfg["user"] != "salesdw_bootstrap":
        raise SystemExit("Unexpected target; refusing migration")
    kwargs = {k: cfg[k] for k in ("host", "port", "dbname", "user", "password")}
    if args.rotate_role:
        if args.restore_target:
            raise SystemExit("Rotation and restore provisioning are separate operations")
        from rotate_role import rotate_bi
        rotate_bi(ROOT, cfg, runtime)
        return
    if args.restore_target:
        if not re.fullmatch(r"sales_dw_restore_[a-z0-9_]{1,40}", args.restore_target):
            raise SystemExit("Invalid isolated target name")
        with psycopg.connect(**kwargs, autocommit=True) as conn:
            if conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (args.restore_target,)).fetchone():
                raise SystemExit("Target already exists; refusing to overwrite")
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER salesdw_bootstrap").format(sql.Identifier(args.restore_target)))
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(args.restore_target)))
            for account in runtime["roles"].values():
                conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(args.restore_target), sql.Identifier(account["user"])))
            conn.execute(sql.SQL("GRANT TEMPORARY ON DATABASE {} TO salesdw_transform").format(sql.Identifier(args.restore_target)))
        print("Created isolated target:", args.restore_target)
        if not args.initialize_empty:
            return
        kwargs["dbname"] = args.restore_target
    with psycopg.connect(**kwargs, autocommit=True, row_factory=dict_row) as conn:
        conn.execute("SELECT pg_advisory_lock(52448121)")
        conn.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations (name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        existing = {r["name"]: r["sha256"] for r in conn.execute("SELECT name,sha256 FROM public.schema_migrations")}
        for path, item in zip(migrations, plan):
            if path.name in existing:
                if existing[path.name] != item["sha256"]:
                    raise RuntimeError("Applied migration checksum changed: " + path.name)
                continue
            with conn.transaction():
                conn.execute(path.read_text(), prepare=False)
                conn.execute("INSERT INTO public.schema_migrations(name,sha256) VALUES (%s,%s)", (path.name, item["sha256"]))
            print("Applied", path.name)
        # Roles and app databases belong exclusively to this new Compose project.
        accounts = dict(runtime["roles"])
        accounts.update({n: {"user": "salesdw_" + n, "password": pw} for n, pw in cfg["metadata"].items()})
        if args.superset:
            superset = json.loads((ROOT / "var/secrets/superset.json").read_text())
            accounts["superset"] = {"user": "salesdw_superset", "password": superset["metadata_password"]}
        for role, account in accounts.items():
            name = account["user"]
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,)).fetchone():
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Identifier(name), sql.Literal(account["password"])))
        for name in ("airflow", "metabase", *(["superset"] if args.superset else [])):
            dbname = name + "_meta"
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,)).fetchone():
                conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(dbname), sql.Identifier("salesdw_" + name)))
                if name == "superset":
                    conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
        grants = (ROOT / "db/security/grants.sql").read_text().replace("ON DATABASE sales_dw ", "ON DATABASE " + kwargs["dbname"] + " ")
        conn.execute(grants, prepare=False)
        conn.execute("SELECT pg_advisory_unlock(52448121)")
    s3 = Minio("minio:9000", access_key=cfg["s3_user"], secret_key=cfg["s3_password"], secure=False)
    if not s3.bucket_exists(runtime["s3"]["bucket"]):
        s3.make_bucket(runtime["s3"]["bucket"])
    admin = MinioAdmin(endpoint="minio:9000", credentials=StaticProvider(cfg["s3_user"], cfg["s3_password"]), secure=False)
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:GetBucketLocation", "s3:ListBucket"], "Resource": ["arn:aws:s3:::salesdw-raw"]},
        {"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"], "Resource": ["arn:aws:s3:::salesdw-raw/*"]}]}
    policy_path = ROOT / "var/secrets/raw-policy.json"
    policy_path.write_text(json.dumps(policy))
    admin.policy_add("salesdw-raw-ingest", str(policy_path))
    admin.user_add(runtime["s3"]["access_key"], runtime["s3"]["secret_key"])
    admin.policy_set("salesdw-raw-ingest", user=runtime["s3"]["access_key"])
    (ROOT / "var/evidence/migration.json").write_text(json.dumps({"passed": True, "project": "salesdw", "migrations": plan}, indent=2) + "\n")
    print("Isolated migrations, scoped roles, metadata databases and S3 policy ready. Secrets redacted.")


if __name__ == "__main__":
    main()
