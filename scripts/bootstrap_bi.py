"""Idempotently create three OSS Metabase dashboards from versioned contracts.

Uses normal card/dashboard APIs, not paid serialization endpoints. Credentials
are read from scoped secret files and never written to exported dashboard state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import requests

from sales_dw.config import ROOT, connect, settings

BASE = os.environ.get("METABASE_URL", "http://metabase:3000")


def main():
    admin = json.loads(Path("/run/secrets/bi_admin.json").read_text())
    session = requests.Session()

    def call(method, path, body=None):
        r = session.request(method, BASE + path, json=body, timeout=120)
        if not r.ok:
            raise RuntimeError(f"Metabase API {path}: HTTP {r.status_code}: {r.text[:1500]}")
        return r.json() if r.content else {}

    properties = call("GET", "/api/session/properties")
    token = properties.get("setup-token")
    if token:
        result = call("POST", "/api/setup", {"token": token, "user": {"email": admin["email"], "password": admin["password"], "first_name": "Portfolio", "last_name": "Reviewer"},
                                             "prefs": {"site_name": "SalesDW - Kimball Analytics", "site_locale": "en", "allow_tracking": False}})
    else:
        result = call("POST", "/api/session", {"username": admin["email"], "password": admin["password"]})
    session.headers["X-Metabase-Session"] = result["id"]
    with connect("snapshot") as conn:
        release = conn.execute("SELECT r.release_id,r.pipeline_run_id FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main'").fetchone()
    if release is None:
        raise RuntimeError("No published release; refusing to create empty business dashboards")
    rid, run_id = str(release["release_id"]), str(release["pipeline_run_id"])
    state_path = ROOT / "var/bi/state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"cards": {}, "dashboards": {}}
    databases = call("GET", "/api/database")["data"]
    database = next((d for d in databases if d["name"] == "SalesDW Published Readonly"), None)
    cfg = settings()
    detail = {"host": cfg["host"], "port": cfg["port"], "dbname": cfg["dbname"], "user": cfg["roles"]["bi"]["user"],
              "password": cfg["roles"]["bi"]["password"], "ssl": False, "tunnel-enabled": False}
    if database is None:
        database = call("POST", "/api/database", {"name": "SalesDW Published Readonly", "engine": "postgres", "details": detail})
    state["database_id"] = database["id"]
    collections = call("GET", "/api/collection")
    collection = next((c for c in collections if c["name"] == "SalesDW Portfolio"), None)
    if collection is None:
        collection = call("POST", "/api/collection", {"name": "SalesDW Portfolio", "description": "Real Olist data, Kimball Warehouse, release-pinned metrics. Independent portfolio, not company-internal data."})
    collection_id = collection["id"]
    existing_dashboards = call("GET", "/api/dashboard")
    existing_cards = call("GET", "/api/card")
    cards = {
        "delivered_value": ("Delivered value (BRL)", "scalar", "SELECT delivered_merchandise_value FROM reporting.validated_sales_monthly", "monthly"),
        "delivered_orders": ("Delivered orders", "scalar", "SELECT delivered_orders FROM reporting.validated_sales_monthly", "monthly"),
        "delivered_aov": ("Delivered AOV", "scalar", "SELECT delivered_aov FROM reporting.validated_sales_monthly", "monthly"),
        "delivered_customers": ("Distinct delivered customers", "scalar", "SELECT delivered_unique_customers FROM reporting.validated_sales_monthly", "monthly"),
        "cancellation_rate": ("Cancellation rate", "scalar", "SELECT cancellation_rate FROM reporting.validated_sales_monthly", "monthly"),
        "daily_value_trend": ("Daily delivered merchandise value", "line", "SELECT day,delivered_merchandise_value FROM reporting.validated_sales_daily", "daily"),
        "category_value": ("Top 10 categories by delivered value", "row", "SELECT category,delivered_merchandise_value FROM reporting.validated_product_monthly", "category"),
        "seller_value": ("Top 10 sellers by delivered value", "table", "SELECT seller_id,delivered_merchandise_value FROM reporting.validated_seller_monthly", "seller"),
        "buyer_state_value": ("Delivered value by buyer state", "bar", "SELECT state,delivered_merchandise_value FROM reporting.validated_buyer_state_monthly", "state"),
        "category_rows": ("Top 10 categories by delivered item rows", "row", "SELECT category,delivered_item_rows FROM reporting.validated_product_monthly", "category"),
        "pipeline_state": ("Pipeline attempts and state", "table", "SELECT state,source_cut,round(extract(epoch FROM finished_at-started_at),1) AS elapsed_seconds,finished_at,pipeline_run_id,error_category FROM reporting.pipeline_health", "run"),
        "published_at": ("Published release and timestamp", "table", "SELECT state,published_at,source_cut,release_id FROM reporting.release_metadata", "release"),
        "source_coverage_warnings": ("Source warnings - occurrences in selected run", "table", "SELECT rule_id,severity,affected_records FROM reporting.quality_health", "quality"),
        "quality_failures": ("Error occurrences in selected run", "scalar", "SELECT coalesce(sum(affected_records),0) AS error_occurrences FROM reporting.quality_health", "quality_errors"),
    }
    contract = json.loads((ROOT / "contracts/dashboard-contract.legacy-metabase.json").read_text())
    test_results, links = {}, {}
    for board in contract["dashboards"]:
        board_id = board["id"]
        title = {"sales_overview": "01 - Sales Overview", "commercial_performance": "02 - Commercial Performance", "data_pipeline_health": "03 - Data Quality & Pipeline Health"}[board_id]
        if board_id not in state["dashboards"]:
            dashboard = next((d for d in existing_dashboards if d["name"] == title and d.get("collection_id") == collection_id), None)
            if dashboard is None:
                dashboard = call("POST", "/api/dashboard", {"name": title, "collection_id": collection_id,
                                 "description": "Source: Olist v2. Status is accepted snapshot, not point-in-time. Business cards share a published release. Default month: 2018-08."})
            state["dashboards"][board_id] = dashboard["id"]
            state_path.write_text(json.dumps(state, indent=2) + "\n")
        dashboard_id = state["dashboards"][board_id]
        parameters = [
            {"id": "release_id", "name": "Published release", "slug": "release_id", "type": "string/=", "default": rid, "required": True},
            {"id": "purchase_month", "name": "Purchase month", "slug": "purchase_month", "type": "date/single", "default": "2018-08-01", "required": True},
        ] if board_id != "data_pipeline_health" else [
            {"id": "release_id", "name": "Published release", "slug": "release_id", "type": "string/=", "default": rid, "required": True},
            {"id": "pipeline_run_id", "name": "Pipeline run", "slug": "pipeline_run_id", "type": "string/=", "default": run_id, "required": True},
        ]
        dashcards = []
        for index, card in enumerate(board["cards"]):
            card_id = card["id"]
            name, display, query, kind = cards[card_id]
            tags = {}
            defaults = {"release_id": rid, "purchase_month": "2018-08-01", "pipeline_run_id": run_id}
            if kind in {"run", "quality", "quality_errors"}:
                query += " WHERE pipeline_run_id={{pipeline_run_id}}::uuid"
                tag_names = ["pipeline_run_id"]
                if kind == "quality_errors":
                    query += " AND severity='error'"
                if kind != "quality_errors":
                    query += " ORDER BY " + ("started_at DESC" if kind == "run" else "rule_id")
            else:
                query += " WHERE release_id={{release_id}}::uuid"
                tag_names = ["release_id"]
                if kind != "release":
                    query += " AND " + ("date_trunc('month',day)::date" if kind == "daily" else "month") + "={{purchase_month}}::date"
                    tag_names.append("purchase_month")
                if kind == "daily":
                    query += " ORDER BY day"
                if kind in {"category", "seller", "state"}:
                    query += " ORDER BY 2 DESC" + (" LIMIT 10" if kind in {"seller", "category"} else "")
            for tag in tag_names:
                tags[tag] = {"id": str(uuid4()), "name": tag, "display-name": tag.replace("_", " "),
                             "type": "date" if tag == "purchase_month" else "text", "required": True, "default": defaults[tag]}
            payload = {"name": name, "collection_id": collection_id, "display": display,
                       "description": "KPI logic comes from governed MetricFlow exports; no chart-local metric redefinition.",
                       "dataset_query": {"type": "native", "database": database["id"], "native": {"query": query, "template-tags": tags}},
                       "visualization_settings": ({"scalar.scale": 100, "scalar.decimals": 2, "scalar.suffix": "%"} if card_id == "cancellation_rate" else {})}
            state_key = board_id + "/" + card_id
            if state_key not in state["cards"]:
                prior = next((c for c in existing_cards if c["name"] == name and c.get("collection_id") == collection_id), None)
                if prior:
                    state["cards"][state_key] = prior["id"]
            if state_key in state["cards"]:
                result = call("PUT", f"/api/card/{state['cards'][state_key]}", payload)
            else:
                result = call("POST", "/api/card", payload)
                state["cards"][state_key] = result["id"]
            cid = result["id"]
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            mappings = [{"parameter_id": tag, "card_id": cid, "target": ["variable", ["template-tag", tag]]} for tag in tag_names]
            if board_id == "sales_overview" and index < 5:
                row, col, sx, sy = (0 if index < 4 else 4), (index % 4) * 6, 6, 4
            elif board_id == "sales_overview":
                row, col, sx, sy = 4, 6, 18, 8
            else:
                row, col, sx, sy = (index // 2) * 8, (index % 2) * 12, 12, 8
            dashcards.append({"id": -(index + 1), "card_id": cid, "row": row, "col": col, "size_x": sx, "size_y": sy, "parameter_mappings": mappings, "visualization_settings": {}})
            api_params = [{"id": tags[tag]["id"], "type": "date/single" if tag == "purchase_month" else "category", "target": ["variable", ["template-tag", tag]], "value": defaults[tag]} for tag in tag_names]
            answer = call("POST", f"/api/card/{cid}/query", {"parameters": api_params})
            if answer.get("status") != "completed":
                raise RuntimeError("BI query failed: " + json.dumps(answer.get("error", answer.get("status"))))
            test_results[state_key] = {"card_id": cid, "status": answer["status"], "rows": len(answer["data"]["rows"]), "required_parameters": tag_names}
            state_path.write_text(json.dumps(state, indent=2) + "\n")
        call("PUT", f"/api/dashboard/{dashboard_id}", {"name": title, "parameters": parameters, "dashcards": dashcards})
        check = call("GET", f"/api/dashboard/{dashboard_id}")
        assert len(check["dashcards"]) == len(board["cards"]), (board_id, len(check["dashcards"]))
        links[board_id] = f"http://localhost:13000/dashboard/{dashboard_id}?release_id={rid}&purchase_month=2018-08-01&pipeline_run_id={run_id}"
    state.update(release_id=rid, pipeline_run_id=run_id, links=links)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    evidence = {"passed": True, "metabase_version": properties.get("version"), "release_id": rid, "dashboards": links, "cards": test_results,
                "scope": "API-created OSS dashboards, native card query success and explicit parameter mappings. Browser acceptance is separate."}
    (ROOT / "var/evidence/bi.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"dashboards": links, "cards_verified": len(test_results), "passed": True}, indent=2))


if __name__ == "__main__":
    main()
