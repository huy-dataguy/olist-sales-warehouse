from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(os.environ.get("SALES_DW_ROOT", Path(__file__).resolve().parents[2]))


def settings():
    cfg = json.loads(Path(os.environ.get("SALES_DW_CONFIG", "/run/secrets/runtime.json")).read_text())
    target = os.environ.get("SALES_DW_DATABASE", cfg["dbname"])
    if target != "sales_dw" and not __import__('re').fullmatch(r"sales_dw_restore_[a-z0-9_]+", target):
        raise ValueError("Refusing non-project database")
    cfg["dbname"] = target
    return cfg


@contextmanager
def connect(role="ingest", *, release_id=None, autocommit=False, dbname=None):
    cfg = settings()
    database = dbname or cfg["dbname"]
    if database != "sales_dw" and not database.startswith("sales_dw_restore_"):
        raise ValueError("Refusing non-project database")
    account = cfg["roles"][role]
    options = "-c statement_timeout=600000 -c lock_timeout=30000"
    if release_id is not None:
        from uuid import UUID
        options += f" -c sales_dw.candidate_release_id={UUID(str(release_id))}"
    with psycopg.connect(host=cfg["host"], port=cfg["port"], dbname=database,
                         user=account["user"], password=account["password"],
                         options=options, row_factory=dict_row, autocommit=autocommit) as conn:
        yield conn


def run_dir(run_id):
    from uuid import UUID
    path = ROOT / "var/runs" / str(UUID(str(run_id)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_context(run_id, **changes):
    path = run_dir(run_id) / "context.json"
    data = json.loads(path.read_text()) if path.exists() else {"run_id": str(run_id)}
    data.update(changes)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, default=str) + "\n")
    temp.replace(path)
    return data


def context(run_id):
    return json.loads((run_dir(run_id) / "context.json").read_text())
