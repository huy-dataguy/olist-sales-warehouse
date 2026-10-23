"""Run an offline dbt/MetricFlow compatibility probe and preserve evidence.

Run with dbt-core==1.12.6, dbt-postgres==1.11.0, dbt-metricflow==0.15.0.
This deliberately cannot connect to a database: its profile uses port 1.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "research/semantic_probe"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin-dir", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/semantic-probe.json")
    args = parser.parse_args()
    bins = {}
    for name in ("dbt", "mf"):
        candidate = str(args.bin_dir / name) if args.bin_dir else shutil.which(name)
        if not candidate or not Path(candidate).is_file():
            parser.error("dbt and mf are required; install the pinned probe packages in an isolated environment")
        bins[name] = candidate
    profile = (PROJECT / "profiles.yml").read_text()
    if not re.search(r"^\s+port: 1$", profile, re.MULTILINE):
        parser.error("offline probe must retain the deliberately unusable database port 1")
    import os
    env = {**os.environ, "DBT_PROFILES_DIR": str(PROJECT)}
    cases = [
        ("dbt_parse", [bins["dbt"], "parse", "--profiles-dir", str(PROJECT), "--no-partial-parse"], 0, None),
        ("metric_discovery", [bins["mf"], "list", "metrics"], 0, "delivered_aov"),
        ("cross_grain_ratio_sql", [bins["mf"], "query", "--metrics", "delivered_merchandise_value,delivered_orders,delivered_aov", "--group-by", "metric_time__month,buyer_geography__state", "--explain"], 0, "NULLIF"),
        ("item_category_sql", [bins["mf"], "query", "--metrics", "delivered_merchandise_value", "--group-by", "metric_time__month,product__category", "--explain"], 0, "dim_products"),
        ("reject_order_metric_product_fanout", [bins["mf"], "query", "--metrics", "delivered_orders", "--group-by", "product__category", "--explain"], 1, "does not match any of the available group-by-items"),
    ]
    results = []
    for name, command, expected, marker in cases:
        result = subprocess.run(command, cwd=PROJECT, env=env, capture_output=True, text=True, timeout=60)
        stdout = ANSI.sub("", result.stdout).replace("\r", "")
        stderr = ANSI.sub("", result.stderr).replace("\r", "")
        passed = result.returncode == expected and (marker is None or marker in stdout + stderr)
        if name == "cross_grain_ratio_sql":
            passed = passed and not re.search(r'JOIN\s+"compile_only"\."probe"\."fct_', stdout, re.IGNORECASE)
        results.append({"case": name, "command": command, "expected_exit": expected,
                        "actual_exit": result.returncode, "passed": passed,
                        "stdout": stdout, "stderr": stderr})
        print(f"{name}: {'PASS' if passed else 'FAIL'} (exit {result.returncode}, expected {expected})", flush=True)
        if not passed:
            break
    manifest = PROJECT / "target/semantic_manifest.json"
    metadata = json.loads((PROJECT / "target/manifest.json").read_text()).get("metadata", {}) if (PROJECT / "target/manifest.json").exists() else {}
    evidence = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Offline parse, discovery, PostgreSQL SQL generation and invalid-dimension rejection only; no warehouse connection, data execution or DDL.",
        "python": sys.version.split()[0],
        "package_pins": {"dbt-core": "1.12.6", "dbt-postgres": "1.11.0", "dbt-metricflow": "0.15.0", "metricflow": "0.213.0"},
        "manifest_dbt_version": metadata.get("dbt_version"),
        "semantic_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None,
        "checks": results,
        "passed": len(results) == len(cases) and all(r["passed"] for r in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
