"""Bound local admission before disk pressure can make recovery unsafe."""
from pathlib import Path
import shutil

from .config import ROOT, connect

BUDGET = 70_000_000_000


def enforce(estimated_bytes, free_bytes, additional_bytes=1_000_000_000):
    if free_bytes < 5_000_000_000:
        raise RuntimeError("Capacity admission blocked: less than 5 GB free; retain source/releases and inspect capacity report")
    if estimated_bytes + additional_bytes >= int(BUDGET * 0.9):
        raise RuntimeError("Capacity admission blocked before 90% of the 70 GB project budget")
    return {"estimated_project_bytes": estimated_bytes, "free_bytes": free_bytes, "budget_bytes": BUDGET, "warning": estimated_bytes >= int(BUDGET * 0.8)}


def preflight():
    with connect() as c:
        databases = c.execute("SELECT coalesce(sum(pg_database_size(oid)),0) AS n FROM pg_database WHERE datname='sales_dw' OR datname LIKE 'sales_dw_restore_%'").fetchone()["n"]
    artifacts = sum(p.stat().st_size for folder in (ROOT / "var", ROOT / "data") for p in folder.rglob("*") if p.is_file() and not p.is_symlink())
    # Conservative fixed reservation covers pinned images, build cache and app
    # metadata. Host operations.py reports the actual Docker-wide upper bound.
    return enforce(int(databases) + artifacts + 25_000_000_000, shutil.disk_usage(ROOT).free)
