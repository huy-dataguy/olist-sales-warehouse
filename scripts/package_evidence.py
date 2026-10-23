"""Create a shareable, allowlisted demo bundle from actual completed local runs.

Only public Olist aggregate outputs and test reports are copied. Never enumerate
or copy secrets, raw archives, connection files, backups or database volumes.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "infra/compose.yaml")]
REPORTS = ["airflow", "bi", "browser", "browser-publish-transition", "capacity", "health", "faults", "incremental", "pipeline-recovery", "ack-recovery", "restore", "rotation", "correction", "runtime-sales_dw"]


def psql(statement):
    return subprocess.run([*COMPOSE, "exec", "-T", "postgres", "psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-U", "salesdw_backup", "-d", "sales_dw", "-c", statement], check=True, capture_output=True, text=True).stdout


def main():
    out = ROOT / "docs/evidence/runtime"
    out.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name in REPORTS:
        path = ROOT / "var/evidence" / (name + ".json")
        payload = json.loads(path.read_text())
        if name not in {"capacity", "browser-publish-transition"}:
            assert payload.get("passed") is True, f"Unsuccessful evidence: {name}"
        if name == "capacity":
            assert payload["below_70gb"], "Capacity budget exceeded"
        if name == "browser-publish-transition":
            assert payload["passed"] and payload["publish_transition"]["refreshed_cards_unchanged"]
        # Convert environment-specific absolute paths to repository-relative ones.
        encoded = json.dumps(payload, indent=2, ensure_ascii=False).replace(str(ROOT) + "/", "")
        encoded = encoded.replace("/workspace/", "")
        (out / path.name).write_text(encoded + "\n")
        artifacts[path.name] = hashlib.sha256((out / path.name).read_bytes()).hexdigest()
    current = json.loads(psql("SELECT row_to_json(r) FROM (SELECT p.release_id,r.pipeline_run_id,r.source_cut,r.published_at FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main') r"))
    rid = str(UUID(current["release_id"]))
    runtime = json.loads((out / "runtime-sales_dw.json").read_text())
    assert runtime["checks"]["warehouse"]["result"]["release_id"] == rid, "Run runtime verification against the current release first"
    assert json.loads((out / "browser.json").read_text())["release_id"] == rid, "Refresh browser evidence against current release first"
    exports = json.loads((ROOT / "contracts/metric-catalog.json").read_text())["exports"]
    reports_dir = ROOT / "output/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    exported = {}
    for spec in exports:
        name = spec["id"]
        assert name in {"sales_monthly", "sales_daily", "product_monthly", "seller_monthly", "buyer_state_monthly"}
        columns = spec["grain"] + spec["metrics"]
        assert all(c.replace("_", "").isalnum() for c in columns)
        statement = f"COPY (SELECT {','.join(columns)} FROM reporting.validated_{name} WHERE release_id='{rid}' ORDER BY {','.join(spec['grain'])}) TO STDOUT WITH CSV HEADER"
        content = psql(statement)
        target = reports_dir / (name + ".csv")
        target.write_text(content)
        count = len(list(csv.DictReader(io.StringIO(content))))
        assert count == runtime["checks"]["semantic"]["result"]["exports"][name]["rows"]
        exported[name] = {"rows": count, "path": str(target.relative_to(ROOT)), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (out / "screenshots").mkdir(exist_ok=True)
    screenshots = {}
    for name in ("sales_overview", "commercial_performance", "data_pipeline_health"):
        original = ROOT / "var/evidence/screenshots" / (name + ".png")
        shutil.copyfile(original, out / "screenshots" / original.name)
        screenshots[name] = {"path": str((out / "screenshots" / original.name).relative_to(ROOT)), "sha256": hashlib.sha256(original.read_bytes()).hexdigest()}
    result = json.loads((ROOT / "var/runs" / current["pipeline_run_id"] / "dbt/run_results.json").read_text())
    assert all(r["status"] in {"success", "pass"} for r in result["results"])
    duration = json.loads(psql(f"SELECT row_to_json(x) FROM (SELECT state,extract(epoch FROM finished_at-started_at) AS elapsed_seconds FROM ops.pipeline_runs WHERE pipeline_run_id='{UUID(current['pipeline_run_id'])}') x"))
    assert duration["state"] == "succeeded"
    manifest = {"captured_at": datetime.now(timezone.utc).isoformat(), "scope": "Actual local runtime evidence; not certification of all enterprise acceptance gates",
                "publication": current, "pipeline": duration, "dbt_nodes_passed": len(result["results"]), "source_rows": 451535,
                "evidence_sha256": artifacts, "exports": exported, "screenshots": screenshots,
                "data_license": "Olist CC BY-NC-SA 4.0; attribution and downstream terms apply to derived exports",
                "limitations": ["Single-host, no HA", "Local unencrypted backups, no host-loss RPO", "App metadata restore not exercised", "Remote GitHub CI not executed", "Retention inventory, no automated deletion", "No upstream Olist CDC; correction/effectivity fixtures isolated"]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"release_id": rid, "dbt_nodes": len(result["results"]), "csv_exports": {k: v["rows"] for k, v in exported.items()}, "evidence": str(out)}))


if __name__ == "__main__":
    main()
