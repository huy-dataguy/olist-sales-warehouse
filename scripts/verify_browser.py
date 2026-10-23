"""Host browser acceptance for real Metabase dashboards; saves private local PNGs."""
import json
from pathlib import Path
import time
import argparse
import subprocess
import os

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-transition", action="store_true")
    args = parser.parse_args()
    admin = json.loads((ROOT / "var/secrets/bi_admin.json").read_text())
    state = json.loads((ROOT / "var/bi/state.json").read_text())
    response = requests.post("http://localhost:13000/api/session", json={"username": admin["email"], "password": admin["password"]}, timeout=30)
    response.raise_for_status()
    token = response.json()["id"]
    output = ROOT / "var/evidence/screenshots"
    output.mkdir(exist_ok=True)
    evidence = {"passed": False, "release_id": state["release_id"], "dashboards": {}}
    with sync_playwright() as p:
        executable = os.environ.get("SALES_DW_BROWSER")
        if executable is None and Path("/opt/google/chrome/chrome").exists():
            executable = "/opt/google/chrome/chrome"
        # Otherwise use Playwright's installed Chromium; do not hardcode this host.
        browser = p.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        context.add_cookies([{"name": "metabase.SESSION", "value": token, "url": "http://localhost:13000", "httpOnly": True, "sameSite": "Lax"}])
        for name, link in state["links"].items():
            page = context.new_page()
            queries = []
            def record(reply):
                if reply.request.method == "POST" and reply.url.split("?")[0].endswith("/query") and "/api/" in reply.url:
                    queries.append(reply)
            page.on("response", record)
            page.goto(link, wait_until="domcontentloaded", timeout=90000)
            page.get_by_test_id("dashboard-header").wait_for(timeout=90000)
            # Wait for actual card answers rather than arbitrary page-load timing.
            expected = 6 if name == "sales_overview" else 4
            deadline = time.monotonic() + 120
            while len(queries) < expected and time.monotonic() < deadline:
                page.wait_for_timeout(500)
            assert len(queries) >= expected, (name, "cards did not request results", len(queries))
            answers = []
            for reply in queries:
                assert reply.ok, (name, reply.status)
                body = reply.json()
                assert body.get("status") == "completed", (name, reply.url, list(body), body.get("error"), body.get("status"))
                params = reply.request.post_data_json.get("parameters", [])
                # API parameter IDs refer to the dashboard control, not card-local values.
                release_params = [v for v in params if v.get("id") == "release_id" or "release_id" in str(v.get("target", ""))]
                if release_params:
                    assert all(v["value"] in (state["release_id"], [state["release_id"]]) for v in release_params)
                answers.append({"status": body["status"], "rows": len(body["data"]["rows"]), "has_release_parameter": bool(release_params)})
            page.wait_for_timeout(1000)
            errors = page.get_by_text("There was a problem", exact=False).count()
            assert errors == 0
            page.screenshot(path=str(output / (name + ".png")), full_page=True)
            evidence["dashboards"][name] = {"url": link, "cards": answers, "screenshot": str(output / (name + ".png"))}
            if args.publish_transition and name == "sales_overview":
                compose = ["docker", "compose", "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "infra/compose.yaml")]
                deadline = time.monotonic() + 120
                while True:
                    current = subprocess.run([*compose, "exec", "-T", "postgres", "psql", "-XAt", "-U", "salesdw_bootstrap", "-d", "sales_dw", "-c", "SELECT release_id FROM ops.published_release WHERE channel='main'"], check=True, text=True, capture_output=True).stdout.strip()
                    if current != state["release_id"]:
                        break
                    if time.monotonic() > deadline:
                        raise AssertionError("No publication transition observed within the test window")
                    page.wait_for_timeout(1000)
                before = {r.url: r.json()["data"]["rows"] for r in queries}
                queries.clear()
                page.reload(wait_until="domcontentloaded")
                deadline = time.monotonic() + 90
                while len(queries) < expected and time.monotonic() < deadline:
                    page.wait_for_timeout(500)
                assert len(queries) >= expected
                for reply in queries:
                    assert reply.json()["data"]["rows"] == before[reply.url]
                    params = reply.request.post_data_json["parameters"]
                    assert any(v.get("id") == "release_id" and v["value"] in (state["release_id"], [state["release_id"]]) for v in params)
                evidence["publish_transition"] = {"pinned_release": state["release_id"], "new_current_release": current, "refreshed_cards_unchanged": True}
            page.close()
        browser.close()
    evidence["passed"] = True
    if args.publish_transition:
        (ROOT / "var/evidence/browser-publish-transition.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (ROOT / "var/evidence/browser.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"passed": True, "dashboards": len(evidence["dashboards"]), "screenshots": str(output)}))


if __name__ == "__main__":
    main()
