"""Host health and conservative capacity inventory. Never prunes or deletes data."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import re

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "infra/compose.yaml")]


def health():
    urls = {"superset": "http://localhost:18088/health", "airflow": "http://localhost:18080/api/v2/monitor/health"}
    result = {}
    for name, url in urls.items():
        deadline = time.monotonic() + 90
        while True:
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    raw = response.read()
                    body = json.loads(raw) if name=='airflow' else raw.decode().strip()
                if name == "superset":
                    assert body.lower() == 'ok'
                else:
                    assert all(body[k]["status"] == "healthy" for k in ("metadatabase", "scheduler", "dag_processor"))
                result[name] = body
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)
    rows = subprocess.run([*COMPOSE, "ps", "--format", "json"], check=True, text=True, capture_output=True).stdout
    services = [json.loads(line) for line in rows.splitlines() if line.strip()]
    required = {"postgres", "minio", "superset", "airflow-api", "airflow-scheduler", "airflow-dag-processor"}
    assert required <= {s["Service"] for s in services if s["State"] == "running"}
    for service in services:
        for port in service.get("Publishers") or []:
            assert port.get("PublishedPort", 0) == 0 or port.get("URL") == "127.0.0.1", port
    result.update(passed=True, private_database_port=True, services=[s["Service"] for s in services])
    return result


def capacity():
    disk = shutil.disk_usage(ROOT)
    # Docker's global summary is conservative: it includes any unrelated images.
    summary = subprocess.run(["docker", "system", "df", "--format", "{{json .}}"], check=True, text=True, capture_output=True).stdout
    stats = subprocess.run([*COMPOSE, "stats", "--no-stream", "--format", "json"], check=True, text=True, capture_output=True).stdout
    sizes = subprocess.run(["du", "-sb", str(ROOT / "var"), str(ROOT / "data")], check=True, text=True, capture_output=True).stdout
    inventory = [json.loads(s) for s in summary.splitlines()]
    def size_bytes(value):
        match = re.fullmatch(r"([0-9.]+)\s*([kMGT]?B)", value)
        if not match:
            raise ValueError("Unknown Docker size format: " + value)
        return int(float(match[1]) * {"B": 1, "kB": 1000, "MB": 10**6, "GB": 10**9, "TB": 10**12}[match[2]])
    docker_bytes = sum(size_bytes(row["Size"]) for row in inventory)
    artifact_bytes = sum(int(line.split()[0]) for line in sizes.splitlines())
    # Deliberately overcounts shared layers/cache and unrelated Docker objects.
    # Add 1 GB for rounded human sizes/logs/metadata not itemized by Docker df.
    conservative = docker_bytes + artifact_bytes + 10**9
    return {"free_bytes": disk.free, "total_bytes": disk.total, "global_docker_inventory": [json.loads(s) for s in summary.splitlines()],
            "project_container_stats": stats, "project_artifact_bytes": sizes, "hard_budget_gb": 70,
            "conservative_footprint_bytes": conservative, "below_70gb": conservative < 70*10**9,
            "footprint_method": "global Docker df + project var/data + 1 GB margin; overcounts shared/unrelated resources",
            "retention_mode": "inventory only; no deletions", "protected": ["immutable raw", "all retained published releases", "most recent verified backup"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("health", "capacity"))
    args = parser.parse_args()
    result = (health if args.command == "health" else capacity)()
    result["measured_at"] = datetime.now(timezone.utc).isoformat()
    (ROOT / "var/evidence" / (args.command + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
