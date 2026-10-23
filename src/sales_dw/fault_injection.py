"""Explicit operational fault injection, restricted to isolated restore targets."""
import os
from .config import settings


def enabled(point):
    if os.environ.get("SALES_DW_FAULT_POINT") != point:
        return False
    if not settings()["dbname"].startswith("sales_dw_restore_"):
        raise RuntimeError("Internal fault injection is restricted to an isolated restore database")
    return True


def hit(point):
    if enabled(point):
        raise RuntimeError("Simulated internal failure: " + point)
