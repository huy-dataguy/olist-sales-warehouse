"""Build actual dbt catalog/lineage and serve a static bundle without credentials."""
import json
import shutil
from sales_dw.config import ROOT, connect, context
from sales_dw.transform import dbt_env, tool, execute


def main():
    with connect("snapshot") as c:
        row = c.execute("SELECT r.pipeline_run_id FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main'").fetchone()
    ctx = context(row["pipeline_run_id"])
    target = ROOT / "var/docs"
    target.mkdir(exist_ok=True)
    variables = {k: ctx[k] for k in ("source_cut", "fencing_token")}
    variables["pipeline_run_id"] = str(row["pipeline_run_id"])
    execute([tool("dbt"), "docs", "generate", "--static", "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt"), "--target-path", str(target), "--log-path", str(target / "logs"), "--vars", json.dumps(variables)],
            cwd=ROOT, env=dbt_env(), log=target / "generate.log")
    manifest = json.loads((target / "manifest.json").read_text())
    catalog = json.loads((target / "catalog.json").read_text())
    assert len(manifest["sources"]) == 1 and len(catalog["nodes"]) >= 18
    assert (target / "static_index.html").stat().st_size > 1000
    print(json.dumps({"passed": True, "sources": len(manifest["sources"]), "catalog_nodes": len(catalog["nodes"]), "url": "http://localhost:18081/static_index.html"}))


if __name__ == "__main__":
    main()
