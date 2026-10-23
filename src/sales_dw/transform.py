"""Run dbt in its isolated interpreter and preserve per-run artifacts."""
import json
import os
from pathlib import Path
import subprocess
import sys

from .config import ROOT, context, run_dir, settings
from . import key_registry, leases


def dbt_env(role="transform", schema="work", release_id=None):
    cfg = settings()
    account = cfg["roles"][role]
    env = dict(os.environ)
    env.update(SALES_DBT_HOST=cfg["host"], SALES_DBT_USER=account["user"], SALES_DBT_PASSWORD=account["password"],
               SALES_DBT_DATABASE=cfg["dbname"], SALES_DBT_SCHEMA=schema, DBT_SEND_ANONYMOUS_USAGE_STATS="false")
    if release_id:
        from uuid import UUID
        # No search_path option in profiles: libpq PGOPTIONS applies to EVERY adapter connection.
        env["PGOPTIONS"] = f"-c sales_dw.candidate_release_id={UUID(str(release_id))} -c statement_timeout=600000"
    return env


def tool(name):
    return str(Path(sys.executable).parent / name)


def execute(args, *, cwd, env, log, timeout=900):
    with log.open("w") as out:
        process = subprocess.run(args, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
    if process.returncode:
        # SQL/logs contain no credentials; retain enough context for a useful failure.
        tail = "\n".join(log.read_text().splitlines()[-35:])
        raise RuntimeError(f"{Path(args[0]).name} exit {process.returncode}; {log}\n{tail}")
    return process


def build(run_id, full_refresh=False):
    leases.renew(run_id)
    ctx = context(run_id)
    allocated = key_registry.ensure(run_id)
    target = run_dir(run_id) / "dbt"
    target.mkdir(exist_ok=True)
    variables = {k: ctx[k] for k in ("source_cut", "fencing_token")}
    variables["pipeline_run_id"] = str(run_id)
    base = ["--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"), "--target-path", str(target), "--log-path", str(target / "logs"), "--vars", json.dumps(variables)]
    env = dbt_env()
    execute([tool("dbt"), "parse", *base], cwd=ROOT, env=env, log=target / "parse.log")
    execute([tool("dbt"), "build", *base, *(["--full-refresh"] if full_refresh else [])], cwd=ROOT, env=env, log=target / "build.log")
    results = json.loads((target / "run_results.json").read_text())
    failures = [r["unique_id"] for r in results["results"] if r["status"] in {"fail", "error", "skipped"}]
    if failures:
        raise RuntimeError("dbt results contain failed/skipped nodes: " + str(failures))
    leases.renew(run_id)
    return {"allocated_keys": allocated, "dbt_nodes": len(results["results"]), "failures": failures, "artifacts": str(target)}
