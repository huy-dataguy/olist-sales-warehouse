"""Build an evidence-bound interview kit without changing services or business data.

Reuse the original diagram primitives, not its obsolete design-only content.
Inputs are explicit public contracts, implementation files and bounded evidence.
No credentials, source records, volumes, SQL execution or network are accessed.
Run: python scripts/build_demo_kit.py (Pillow, Playwright, reportlab, pypdf).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
import hashlib
import json
from pathlib import Path
import re
import shutil
from string import Template
import subprocess
import zipfile

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image as DocImage, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

import build_project_visuals as base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/demo-kit"
QA = ROOT / "tmp/pdfs/demo-kit"
base.OUT = OUT
C = base.C
N = 10
DATE = datetime.now(timezone.utc).date().isoformat()


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vn(value, digits=0):
    return f"{Decimal(str(value)):,.{digits}f}".translate(str.maketrans(",.", ".,"))


def load_evidence():
    model = read("contracts/warehouse-model.json")
    analysis = read("output/analysis/results.json")
    api = read("var/evidence/superset.json")
    browser = read("var/evidence/superset-browser.json")
    health = read("var/evidence/health.json")
    runtime = read("docs/evidence/runtime/runtime-sales_dw.json")
    restore = read("docs/evidence/runtime/restore.json")
    air = read("docs/evidence/runtime/airflow.json")
    source = read("docs/evidence/source-profile.json")
    source_manifest = read("data/source-manifest.json")
    release = analysis["release"]["release_id"]
    assert analysis["passed"] and api["passed"] and browser["passed"] and health["passed"]
    assert api["release_id"] == browser["release_id"] == release
    assert api["catalog_sha256"] == browser["catalog_sha256"]
    assert len(api["charts"]) == 60 and len(api["saved_queries"]) == 8
    assert len(browser["dashboards"]) == 6
    assert len(browser["navigation_clicks"]["clicked_routes"]) == 14
    assert len(model["dimensions"]) == 7 and len(model["facts"]) == 3
    assert sum(r["rows"] for r in source["inventory"] if r["in_v1"]) == 451535
    assert runtime["checks"]["warehouse"]["result"]["release_id"] == release
    assert all(c["passed"] for c in runtime["checks"].values())
    assert restore["passed"] and restore["live_unchanged"] and air["passed"]
    # A changed DAG, table or BI contract requires a review, not a silent diagram.
    dag = (ROOT / "orchestration/dags/sales_warehouse_pipeline.py").read_text()
    stages = ("raw", "validate", "load", "lease", "build", "snapshot", "semantic", "publish", "finish")
    assert ', '.join('"'+s+'"' for s in stages) in dag
    for name in [d["name"] for d in model["dimensions"] + model["facts"]]:
        assert f"CREATE TABLE warehouse_store.{name}" in (ROOT / "db/migrations/001_schema.sql").read_text()
    return dict(model=model, analysis=analysis, api=api, browser=browser,
                health=health, runtime=runtime, restore=restore, airflow=air,
                source=source, source_manifest=source_manifest, release=release)


class Canvas(base.Canvas):
    def __init__(self, number, slug, title, subtitle, sources, notes):
        super().__init__(number, slug, title, subtitle, sources, notes)
        self.parts = [p.replace("Sơ đồ thiết kế; chưa nghiệm thu runtime.",
                                "Sơ đồ hệ thống đã triển khai; phạm vi demo local.")
                      .replace("DESIGN BASELINE 2.0  /  15.10.2026", "IMPLEMENTED DEMO  /  " + DATE)
                      .replace(f"THIẾT KẾ, CHƯA NGHIỆM THU HỆ THỐNG   |   {number:02d} / 09",
                               f"ĐỐI CHIẾU CODE VÀ EVIDENCE   |   {number:02d} / {N:02d}")
                      for p in self.parts]


def diagrams(e):
    slides = []
    def make(num, slug, title, subtitle, sources, notes):
        return Canvas(num, f"{num:02d}-{slug}", title, subtitle, sources, notes)
    def done(d):
        slides.append(d.finish())

    d = make(1, "business-input-output", "Bài toán và đầu ra của dự án",
             "Sales & Customer Analytics Warehouse | Portfolio Data Engineer | Olist thật, demo trên một máy.",
             ["README.md", "docs/analytics-design.md", "output/analysis/results.json"],
             "Mở đầu bằng kết quả: nhà phân tích cần số bán hàng, khách hàng và giao hàng nhất quán. Dự án có dữ liệu thật, báo cáo thật và bằng chứng chạy; không phải dự án nội bộ Abbott. Nêu giới hạn telesales ngoài v1.")
    for x, label, col in [(72, "INPUT", "blue"), (682, "NỀN TẢNG", "purple"), (1292, "OUTPUT ĐÃ CÓ", "teal")]:
        d.pill(x, 218, label, col)
    d.card(72, 278, 556, 365, "7 feed Olist v2", [
        "451.535 dòng nguồn; 99.441 orders", "Customer, product, seller, orders, items, payments, category translation",
        "ZIP bất biến + checksum + provenance", "Snapshot lịch sử; không phải CDC / OLTP"], size=23)
    d.card(682, 278, 556, 365, "Dữ liệu đúng và truy vết được", [
        "Python + MinIO + PostgreSQL", "dbt → Kimball: 7 dims, 3 facts", "MetricFlow + governed SQL analysis",
        "Airflow: lịch, retry, logs và publication"], color="purple", size=23)
    d.card(1292, 278, 556, 365, "Dữ liệu phục vụ quyết định", [
        "8 KPI lõi; 5 metric exports", "6 dashboard Superset; 60 đối tượng", "8 SQL analyses + notebook + CSV",
        "Lineage, DQ, replay và recovery evidence"], color="teal", size=23)
    for x in (628, 1238):
        d.line([(x+8, 460), (x+44, 460)], "blue", arrow=True)
    d.note(72, 678, 856, 143, "NGƯỜI DÙNG", "Business/BA: hiểu biến động, cơ cấu, khách hàng và giao hàng. DE: đối soát, truy nguồn, xem lỗi và khôi phục.", "blue", 23)
    d.note(960, 678, 888, 143, "TIÊU CHÍ THÀNH CÔNG", "KPI khớp SQL; không nhân đôi khi replay; lỗi không công bố dữ liệu dở; mọi chart cùng release đã kiểm chứng.", "teal", 23)
    d.note(72, 851, 1776, 121, "PHẠM VI CÓ CHỦ ĐÍCH", "Không telesales / dữ liệu bệnh nhân / streaming / MPP / HA. Không có cost, target hay lợi nhuận; không giả dữ liệu Olist thành dữ liệu dược phẩm.", "amber", 23)
    done(d)

    d = make(2, "system-architecture", "Kiến trúc hệ thống đang chạy",
             "Docker Compose project salesdw | PostgreSQL là analytical Warehouse; không có OLTP riêng trong v1.",
             ["infra/compose.yaml", "src/sales_dw/cli.py", "src/sales_dw/export_metrics.py", "bi/bootstrap_superset.py"],
             "Đọc hàng trên từ trái sang phải, hàng dưới từ phải sang trái theo số thứ tự. Airflow gọi các stage CLI; dbt và MetricFlow là tiến trình theo run, không phải container thường trực. Superset chỉ đọc reporting views của published releases. Metadata ứng dụng tách database.")
    d.rect(72, 213, 1776, 76, C["blue_bg"])
    d.text(98, 262, "APACHE AIRFLOW", 27, "blue", True)
    d.text(430, 262, "02:00 Asia/Ho_Chi_Minh • 9 tasks • retries • logs • trạng thái thực", 25, maxw=1370)
    xs = [72, 528, 984, 1440]
    top = [
        ("Olist snapshot", ["7 CSV trong ZIP v2", "SHA-256 cố định", "Không có source CDC"], "01  SOURCE", "blue"),
        ("Python + MinIO", ["Giữ nguyên raw archive", "Receipt / artifact metadata", "S3-compatible object storage"], "02  RAW / AUDIT", "blue"),
        ("Validate + landing", ["Schema / ID / conflict checks", "Accepted source versions", "Chốt source_cut"], "03  POSTGRESQL", "purple"),
        ("dbt Core", ["7 staging + 1 intermediate", "7 dims + 3 facts", "Tests / incremental / keys"], "04  WORKING MODELS", "purple"),
    ]
    bottom = [
        ("Apache Superset", ["6 dashboard + SQL Lab", "Read-only reporting views", "Cùng published release"], "08  CONSUMER", "teal"),
        ("Published reporting", ["5 MetricFlow exports", "Analytical SQL views", "Atomic publication gate"], "07  SERVING", "teal"),
        ("Local MetricFlow", ["8 KPI khai báo trong dbt", "Bind candidate release", "CLI + SQL oracle parity"], "06  SEMANTICS", "teal"),
        ("Kimball snapshot", ["warehouse_store schema", "7 dimensions + 3 facts", "Immutable, release-scoped"], "05  FREEZE / VALIDATE", "purple"),
    ]
    for x, row in zip(xs, top):
        title, body, k, col = row
        d.card(x, 326, 408, 257, title, body, col, k, 21, 27)
    for x in (480, 936, 1392):
        d.line([(x+6, 456), (x+42, 456)], "blue", arrow=True)
    d.line([(1644, 583), (1644, 633)], "purple", arrow=True)
    for x, row in zip(xs, bottom):
        title, body, k, col = row
        d.card(x, 637, 408, 257, title, body, col, k, 21, 27)
    for x in (528, 984, 1440):
        d.line([(x-6, 766), (x-42, 766)], "teal", arrow=True)
    d.rect(72, 921, 1776, 61, C["purple_bg"])
    d.text(98, 960, "POSTGRESQL", 21, "purple", True)
    d.text(303, 960, "sales_dw: landing / work / warehouse_store / semantic_input / reporting / ops", 22, maxw=1500)
    done(d)

    d = make(3, "data-layers-and-lineage", "Mỗi lớp dữ liệu có một trách nhiệm",
             "Raw → accepted versions → working models → immutable DWH → governed serving. Không phải Delta Lake.",
             ["db/migrations/001_schema.sql", "db/migrations/003_semantic_views.sql", "db/migrations/005_published_analysis.sql"],
             "Đây là DWH quan hệ trên PostgreSQL, có tư tưởng phân lớp nhưng không dùng Iceberg/Delta hay gọi MinIO là một lakehouse. Reporting cùng database, không phải DWH thứ hai. Chỉ mutable work được rebuild; consumer đọc snapshot đã publish.")
    layers = [
        ("RAW", "MinIO + original ZIP", "Byte gốc + SHA-256", "Audit, replay; không sửa bản gốc", "blue"),
        ("LANDING", "landing.source_versions", "Source cut + accepted payload", "Row lineage → file / dòng / hash", "blue"),
        ("TRANSFORM", "work.stg_* / int_* / dim_* / fct_*", "dbt models có thể build lại", "Tests; checkpoint; key registry", "purple"),
        ("WAREHOUSE", "warehouse_store.dim_* / fct_*", "Typed Kimball snapshot theo release", "PK / FK / grain / reconciliation", "purple"),
        ("SEMANTIC", "semantic_input + MetricFlow", "Release-bound query definitions", "8 KPI; 5 exports; SQL parity", "teal"),
        ("SERVING", "reporting.* → Superset / SQL", "Metric tables + analytical views", "Chỉ published; role BI read-only", "teal"),
    ]
    for i, (label, path, data, gate, col) in enumerate(layers):
        y = 222 + i * 112
        d.rect(72, y, 1776, 92, C["paper"], C["line"], 10)
        d.rect(72, y, 225, 92, C[col+"_bg"], radius=10)
        d.text(95, y+56, label, 22, col, True, maxw=185)
        d.text(326, y+36, path, 24, bold=True, maxw=1460)
        d.text(326, y+71, data, 22, "muted", maxw=640)
        d.text(1040, y+71, gate, 22, col, maxw=770)
        if i < len(layers)-1:
            d.line([(1805, y+94), (1805, y+109)], "muted", 2, True)
    d.note(72, 916, 1776, 66, "TRUY VẾT", "", "blue")
    d.text(270, 958, "Chart → query / release → fact / dimension → source version → file / row / checksum", 24, maxw=1530)
    done(d)

    d = make(4, "kimball-bus-matrix", "Kimball bus matrix và grain",
             "Ba business process chia sẻ conformed dimensions; mỗi process có star schema theo đúng grain.",
             ["contracts/warehouse-model.json", "specs/spec-package/03-data/kimball-design.md"],
             "Bus matrix là kế hoạch tích hợp các star, không thay thế star schema. Tất cả grain có source namespace. Purchase date ở payment là ngữ cảnh đơn, không phải timestamp thanh toán. Không phân bổ payment cho product/seller khi không có hợp đồng.")
    d.pill(72, 213, "PROCESS → GRAIN → DIMENSIONS → MEASURES", "purple")
    d.rect(72, 272, 1776, 328, C["paper"], C["line"])
    headers = [(650, ["Purchase", "date"]), (806, ["Milestone", "dates"]), (962, ["Customer"]),
               (1118, ["Product"]), (1274, ["Seller"]), (1430, ["Buyer", "geography"]),
               (1586, ["Order", "status"]), (1758, ["Payment", "method"])]
    d.text(100, 318, "PROCESS / FACT", 22, "blue", True)
    for cx, labels in headers:
        for j, text in enumerate(labels):
            d.text(cx, 310+j*29, text, 20, "blue", True, "middle", 150)
    for i, fact in enumerate((e["model"]["facts"][1], e["model"]["facts"][2], e["model"]["facts"][0])):
        y = 387 + i*86
        d.line([(96, y-31), (1822, y-31)], "line", 1)
        d.text(100, y, {"fct_orders":"Order fulfillment", "fct_order_items":"Sales lines", "fct_payments":"Payment records"}[fact["name"]], 25, bold=True, maxw=470)
        d.text(100, y+30, fact["name"], 21, "muted", maxw=470)
        fks = fact["foreign_keys"]
        present = ["purchase_date_key" in fks, "approved_date_key" in fks, "customer_key" in fks,
                   "product_key" in fks, "seller_key" in fks, "buyer_geography_key" in fks,
                   "order_status_key" in fks, "payment_method_key" in fks]
        for (cx, _), yes in zip(headers, present):
            d.text(cx, y+17, "X" if yes else "-", 27, "teal" if yes else "muted", bool(yes), "middle", 150)
    for x, title, grain, extra, col in [
        (72, "Một dòng hàng", "source + order_id + order_item_id", "Transaction fact; item_id là ordinal", "blue"),
        (676, "Một payment record", "source + order_id + payment_sequential", "Transaction fact; installments không cộng", "purple"),
        (1280, "Một đơn hàng", "source + order_id", "Accumulating snapshot; 5 date roles", "teal"),
    ]:
        d.card(x, 637, 568, 209, title, [grain, extra], col, size=21)
    d.note(72, 878, 1776, 101, "QUY TẮC BẤT BIẾN", "Integer dimension SKs ổn định • order_id là degenerate dimension • aggregate từng fact rồi drill-across • không join atomic facts để SUM.", "blue", 22)
    done(d)

    d = make(5, "dimensional-constellation", "Ba star dùng chung bảy dimensions",
             "Sơ đồ logic để trình bày. Dimension chung được lặp trên hình, không phải nhân bản bảng vật lý.",
             ["docs/warehouse-erd.md", "contracts/warehouse-model.json", "db/migrations/001_schema.sql"],
             "Đọc từng cột như một star. Date/customer/geography/status là cùng bốn dimension vật lý trên cả ba cột. Product/seller chỉ ở item star, method chỉ ở payment star. Không có đường nối giữa các fact; xem hình 10 để đọc khóa/cột vật lý.")
    stars = [(72, "fct_order_items", "items", "112.650 dòng hàng"),
             (676, "fct_orders", "orders", "99.441 đơn hàng"),
             (1280, "fct_payments", "payments", "103.886 payment records")]
    for x, name, kind, count in stars:
        d.rect(x, 224, 568, 600, C["paper"], C["line"])
        d.text(x+284, 266, "4 DIMENSIONS CONFORMED", 20, "blue", True, "middle", 520)
        for j, dim in enumerate(["dim_date", "dim_customer", "dim_buyer_geography", "dim_order_status"]):
            y = 288+j*43
            d.rect(x+48, y, 472, 35, C["blue_bg"], radius=7)
            d.text(x+284, y+25, dim, 21, "blue", True, "middle", 450)
        d.line([(x+284, 453), (x+284, 490)], "blue", 2, True)
        d.rect(x+28, 495, 512, 138, C["purple_bg"])
        d.text(x+284, 536, name, 28, "purple", True, "middle", 480)
        d.text(x+284, 576, count, 23, "ink", anchor="middle", maxw=480)
        d.text(x+284, 609, "release-scoped PK / FK", 20, "muted", anchor="middle", maxw=480)
        if kind == "items":
            for dx, dim in [(28, "dim_product"), (300, "dim_seller")]:
                d.rect(x+dx, 697, 240, 60, C["teal_bg"], radius=10)
                d.text(x+dx+120, 736, dim, 22, "teal", True, "middle", 222)
                d.line([(x+dx+120, 697), (x+dx+120, 670), (x+284, 670), (x+284, 637)], "teal", 2, True)
        elif kind == "payments":
            d.rect(x+96, 697, 376, 60, C["teal_bg"], radius=10)
            d.text(x+284, 736, "dim_payment_method", 24, "teal", True, "middle", 352)
            d.line([(x+284, 697), (x+284, 637)], "teal", 2, True)
        else:
            d.para(x+28, 695, "Một dim_date đóng 5 vai: purchase, approved, carrier, delivered, estimated.", 512, 24)
    d.note(72, 861, 856, 119, "KHÓA DIMENSION", "Registry cấp bigint SK; date key YYYYMMDD; Unknown = 0, N/A = -1. Inferred member được bổ sung mà giữ key.", "blue", 22)
    d.note(960, 861, 888, 119, "LỊCH SỬ NGUỒN", "Olist thật chỉ có snapshot Type 0/1. Type 2 có explicit effectivity được kiểm bằng fixture cô lập, không phải lịch sử Olist.", "teal", 22)
    done(d)

    d = make(6, "airflow-workflow", "Workflow thực tế của Airflow",
             "DAG sales_warehouse_pipeline | 9 tasks | 02:00 mỗi ngày | tối đa 2 retries, cách nhau 30 giây.",
             ["orchestration/dags/sales_warehouse_pipeline.py", "src/sales_dw/cli.py", "docs/evidence/runtime/airflow.json"],
             "Đọc 1-5 trên rồi 6-9 dưới từ phải sang trái. Raw đã gồm manifest/hash và bảo toàn archive; build bao gồm dbt và tests. Finish không gọi Superset bootstrap. Lịch được chạy nhiều lần nhưng nguồn Olist tĩnh không tạo sự kiện kinh doanh mới. Batch replay không phải CDC.")
    stages = [
        ("raw", "Raw + receipt", ["Hash, manifest, MinIO", "Giữ artifact nguyên gốc"]),
        ("validate", "Schema + key checks", ["Kiểu, null, trạng thái", "Lỗi → quarantine / fail"]),
        ("load", "Landing commit", ["Source versions + ledger", "Batch dedup / source cut"]),
        ("lease", "Owner + fencing", ["Khóa logic có hạn", "Cố định cut cho build"]),
        ("build", "dbt models + tests", ["Staging, dims, facts", "Incremental + checkpoint"]),
        ("snapshot", "Freeze Kimball", ["10 relations / release", "Grain, FK, hash, totals"]),
        ("semantic", "MetricFlow + parity", ["5 exports cùng release", "Native CLI + SQL oracle"]),
        ("publish", "Atomic publication", ["Mọi gate phải đạt", "Pointer + audit event"]),
        ("finish", "Run succeeded", ["Chỉ sau publish commit", "ACK retry an toàn"]),
    ]
    xs = [72, 438, 804, 1170, 1536]
    for i, (task, title, body) in enumerate(stages[:5]):
        d.card(xs[i], 239, 312, 244, title, body, "blue", f"{i+1:02d}  {task}", 20, 24)
        if i < 4:
            d.line([(xs[i]+318, 361), (xs[i]+358, 361)], "blue", 2, True)
    # The ninth task is at x=438; x=72 is the independent BI handoff.
    d.line([(1692, 483), (1692, 536)], "purple", 2, True)
    for i, (task, title, body) in enumerate(stages[5:]):
        x = xs[4-i]
        d.card(x, 540, 312, 244, title, body, "teal", f"{i+6:02d}  {task}", 20, 24)
        if i < 3:
            d.line([(x-6, 662), (x-45, 662)], "teal", 2, True)
    d.card(72, 540, 312, 244, "Superset handoff", ["Bước riêng, không task", "Giữ URL đã pin release"], "purple", "BI METADATA", 20, 24)
    d.line([(432, 662), (390, 662)], "purple", 2, True, True)
    d.note(72, 822, 856, 152, "FAILURE ĐƯỢC GHI ĐÚNG", "Task terminal fail → ledger failed; downstream upstream_failed; không đổi published release. Không có task thông báo che lỗi.", "red", 23)
    d.note(960, 822, 888, 152, "ĐÃ TÁI HIỆN TRÊN RUNTIME", "Load thử 1 lỗi, thử 2 thành công. Raw lỗi cả 3 lần → DAG failed. Replay và late-arrival kiểm riêng trong database cô lập.", "teal", 23)
    done(d)

    d = make(7, "semantic-and-serving", "Semantic Layer nằm ở đâu?",
             "Một DWH, hai đường serving được quản trị; không dựng Warehouse thứ hai và không dùng API semantic trả phí.",
             ["dbt/models/semantic/semantic_models.yml", "src/sales_dw/export_metrics.py", "db/migrations/005_published_analysis.sql"],
             "MetricFlow đọc candidate Kimball qua release-bound views, sinh và chạy SQL rồi xuất kết quả vào reporting tables. Phân tích cohort/delivery/payment dùng published SQL views riêng, không được gọi là MetricFlow mới. Superset đọc cả hai qua role readonly; không tính lại công thức lõi theo từng chart.")
    d.card(72, 353, 384, 300, "Kimball DWH", ["7 dims + 3 facts", "warehouse_store.*", "Snapshot theo release", "Facts giữ đúng grain"], "purple", size=24)
    d.card(548, 229, 578, 250, "Semantic models + MetricFlow", ["8 KPI: orders, value, AOV, distinct...", "Generated SQL + native CLI execution", "5 exports đã đối chiếu SQL oracle"], "blue", "CORE KPI PATH", 22, 26)
    d.card(548, 551, 578, 250, "Governed SQL analysis", ["Customer / cohort / delivery / payment", "Views chỉ đọc published Kimball", "Grain, cutoff và oracle riêng"], "purple", "EXTENDED ANALYSIS PATH", 22, 27)
    d.line([(462, 455), (502, 455), (502, 354), (540, 354)], "blue", 2, True)
    d.line([(462, 555), (502, 555), (502, 676), (540, 676)], "purple", 2, True)
    d.card(1210, 229, 638, 250, "reporting.* metric tables", ["sales_monthly / sales_daily", "product_monthly / seller_monthly", "buyer_state_monthly; có release_id"], "teal", size=23)
    d.card(1210, 551, 638, 250, "reporting.analytic_* views", ["Orders / payments / customers / cohorts", "Không copy thành một DWH mới", "SQL Lab / dashboards / CSV notebook"], "teal", size=23)
    for y in (354, 676):
        d.line([(1132, y), (1200, y)], "teal", 2, True)
    d.note(72, 848, 1776, 130, "SUPERSET READ-ONLY • PUBLISHED RELEASE ONLY", "AOV = tổng giá trị / tổng đơn delivered; mẫu số 0 → NULL. Distinct tính tại đúng kỳ, không SUM theo ngày. Không join atomic item × payment để tính tiền.", "teal", 24)
    done(d)

    d = make(8, "publication-quality-and-recovery", "Không công bố dữ liệu đang xử lý dở",
             "R0 / R1 là nhãn minh họa release. Publication là giao dịch trong PostgreSQL, không phải distributed transaction.",
             ["src/sales_dw/snapshot_release.py", "src/sales_dw/publish_release.py", "docs/evidence/runtime/pipeline-recovery.json"],
             "R0 tiếp tục phục vụ trong lúc R1 được build. Warehouse snapshot phải đầy đủ, cùng source cut, FK/grain đạt; semantic phải bind R1 và exports có parity. Chỉ khi tất cả đạt publisher mới đổi pointer dưới fencing. Superset URL R0 còn pin R0; muốn chọn R1 phải tạo/bàn giao assets riêng.")
    for x, title, body in [
        (72, "1  Build candidate R1", ["Fixed source_cut", "dbt tests + DQ gates"]),
        (528, "2  Snapshot R1", ["7 dims + 3 facts", "Same-release FK / hashes"]),
        (984, "3  Semantic R1", ["5 exports đầy đủ", "Binding + SQL parity"]),
        (1440, "4  Publish R1", ["Owner + fence hợp lệ", "Atomic pointer + event"]),
    ]:
        d.card(x, 250, 408, 226, title, body, "purple", size=23, title_size=27)
    for x in (480, 936, 1392):
        d.line([(x+6, 361), (x+42, 361)], "purple", 2, True)
    d.rect(72, 526, 1776, 157, C["teal_bg"])
    d.text(100, 574, "CONSUMER ĐỘC LẬP VỚI WORKING STATE", 23, "teal", True)
    d.text(100, 623, "Superset đang pin R0 → mọi chart tiếp tục đọc cùng R0", 30, bold=True, maxw=1690)
    d.text(100, 662, "Sau publish: bàn giao URL pin R1 là bước riêng; pipeline không tự sửa dashboard đang mở.", 24, maxw=1690)
    d.note(72, 728, 556, 245, "CHECK FAIL / EXPORT THIẾU", "R1 không được publish; giữ R0. Source warning được giải thích; schema, grain, FK, parity errors phải chặn.", "red", 24)
    d.note(682, 728, 556, 245, "RETRY / ACK MẤT", "Replay không nhân đôi source versions. Sau commit bị mất ACK: xác minh output đã lưu; không tự ghi lại hoặc reset.", "blue", 24)
    d.note(1292, 728, 556, 245, "RESTORE ĐÃ KIỂM RIÊNG", "DWH vào target mới: 102,056 giây; live không bị ghi đè. App restore / host-loss recovery chưa nghiệm thu.", "amber", 24)
    done(d)

    d = make(9, "dashboards-results-and-evidence", "Kết quả để trình bày trong buổi demo",
             "Tháng kinh doanh 07/2018 | Cutoff khách hàng 31/08/2018 | Release handoff " + e["release"][:8] + ".",
             ["output/analysis/results.json", "var/evidence/superset.json", "var/evidence/superset-browser.json", "docs/implementation-progress.md"],
             "Đọc KPI tháng 7 trước, sau đó dùng menu để đi sâu. Chứng cứ hiện tại: 6 trang, 60 đối tượng, 8 saved queries và 14 lượt bấm navigation thật. Không gọi khoản merchandise value là profit/net revenue; BRL là quy ước demo. Restore và retry là bằng chứng lịch sử, không phải chạy lại khi xuất tài liệu.")
    s = e["analysis"]["summary"]
    k = s["selected_month"]
    metrics = [("Giá trị hàng delivered", vn(k["delivered_merchandise_value"], 2), "BRL; chưa gồm freight"),
               ("Đơn delivered", vn(k["delivered_orders"]), "6.100 khách phân biệt"),
               ("AOV delivered", vn(k["delivered_aov"], 2), "BRL / delivered order"),
               ("Giao đúng hẹn", vn(Decimal(s["on_time_deliveries"])/s["delivery_eligible"]*100, 2)+"%", "5.948 / 6.156 eligible")]
    for x, (label, val, desc) in zip([72, 528, 984, 1440], metrics):
        d.rect(x, 226, 408, 157, C["paper"], C["line"])
        d.text(x+22, 266, label, 22, "muted", maxw=364)
        d.text(x+22, 319, val, 37, "teal", True, maxw=364)
        d.text(x+22, 356, desc, 20, "muted", maxw=364)
    boards = [("Tổng quan kinh doanh", "Quy mô, biến động và nên xem sâu ở đâu?"),
              ("Hiệu quả bán hàng", "Đơn / khách / AOV / MoM / YoY / hủy"),
              ("Sản phẩm & nhà bán hàng", "Category, seller và khu vực đóng góp"),
              ("Khách hàng & mua lại", "Repeat, recency, cohort; cutoff cố định"),
              ("Giao hàng & thanh toán", "Đúng hẹn, thời gian giao, phương thức"),
              ("Chất lượng dữ liệu & vận hành", "Published release, DQ và audit runs")]
    for i, (title, desc) in enumerate(boards):
        col, row = i%2, i//2
        x, y = 72+col*910, 417+row*128
        d.rect(x, y, 866, 106, C["paper"], C["line"], 10)
        d.text(x+22, y+41, title, 26, bold=True, maxw=822)
        d.text(x+22, y+80, desc, 22, "muted", maxw=822)
    d.note(72, 831, 856, 146, "KIỂM CHỨNG HIỆN TẠI", "60 chart queries + 8 SQL Lab queries; 6 browser pages; nhận xét đổi theo tháng ở 4 trang; 14 actual navigation clicks.", "teal", 23)
    d.note(960, 831, 888, 146, "GIỚI HẠN CỦA KẾT QUẢ", "Dữ liệu lịch sử Olist, không phải Abbott. Không target / cost / profit / lý do hủy. Single-host local; không tuyên bố production-ready.", "amber", 23)
    done(d)

    d = make(10, "warehouse-key-schema", "Thiết kế bảng và quan hệ Kimball",
             "Cột rút gọn từ migration 001. Khóa đầy đủ luôn có release_id; nét nối biểu diễn FK dimension → fact.",
             ["db/migrations/001_schema.sql", "contracts/warehouse-model.json"],
             "Bốn dimensions ở hàng trên kết nối độc lập tới cả ba facts; chúng được gom thành bốn thanh routing ngang để giữ hình dễ đọc. Các đường chỉ đi từ dimension tới fact, không có fact-to-fact FK. PK facts là text identity cộng release; dimension SK là integer. Xem ERD Mermaid đi kèm để đọc từng FK cụ thể.")
    # Four separate routing lanes; line intersections are not join points.
    dims = [(72, 224, 396, "dim_date", ["date_key int YYYYMMDD", "full_date, month_start", "day, month, quarter, year"]),
            (516, 224, 396, "dim_customer", ["customer_key bigint SK", "customer_unique_id", "source_system, is_inferred"]),
            (960, 224, 444, "dim_buyer_geography", ["buyer_geography_key bigint SK", "postal_prefix, city, state", "Order-time address tuple"]),
            (1452, 224, 396, "dim_order_status", ["order_status_key bigint SK", "status_code", "is_delivered, is_canceled"])]
    def table(x, y, w, h, name, fields, color="blue", size=20):
        d.rect(x, y, w, h, C["paper"], C["line"], 10)
        d.rect(x, y, w, 43, C[color+"_bg"], radius=10)
        d.text(x+15, y+30, name, 23, color, True, maxw=w-30)
        for j, field in enumerate(fields):
            d.text(x+15, y+73+j*29, field, size, "ink", maxw=w-30)
    for x,y,w,name,fields in dims:
        table(x,y,w,171,name,fields)
    # Shared conformance is a diagram routing convention, not a physical bus table.
    for i, (x,y,w,_,_) in enumerate(dims):
        yy = 418+i*17
        d.line([(x+w/2, 395), (x+w/2, yy)], "muted", 1.5)
        d.line([(96, yy), (1818, yy)], "muted", 1.5)
        for fx in (290, 950, 1610):
            d.line([(fx+i*10, yy), (fx+i*10, 496)], "muted", 1.2, False, True)
    facts = [
        (72, "fct_order_items", ["PK  release_id + order_item_key", "UK  source + order_id + item ordinal", "FK  customer / geography / status / date", "FK  product_key, seller_key", "merchandise_value, freight_value", "item_row_count = 1"], "items"),
        (680, "fct_orders", ["PK  release_id + order_key", "UK  source + order_id", "FK  customer / geography / status", "FK  5 role-playing date keys", "order / delivered / canceled counts", "child totals, milestone timestamps"], "orders"),
        (1288, "fct_payments", ["PK  release_id + payment_key", "UK  source + order_id + pay sequence", "FK  customer / geography / status / date", "FK  payment_method_key", "recorded_payment_value, record_count", "payment_installments (non-additive)"], "payments"),
    ]
    for x, name, fields, _ in facts:
        table(x, 499, 560, 251, name, fields, "purple", 19)
    table(72, 809, 267, 140, "dim_product", ["product_key bigint SK", "product_id, category", "valid_from / valid_to"], "teal", 18)
    table(365, 809, 267, 140, "dim_seller", ["seller_key bigint SK", "seller_id", "city, state, postal"], "teal", 18)
    table(1288, 809, 560, 140, "dim_payment_method", ["payment_method_key bigint SK", "payment_type"], "teal", 20)
    for x in (205, 498):
        d.line([(x, 809), (x, 759)], "teal", 2, True)
    d.line([(1568, 809), (1568, 759)], "teal", 2, True)
    d.para(680, 815, "PK/UK/FK: cùng release_id.\nMọi bảng có lineage / source_cut / run IDs.\nKhông nối facts để cộng số tiền.", 560, 21, "muted")
    done(d)
    return slides


def gallery(slides):
    figures = []
    for row in slides:
        figures.append(f'''<section class="slide" id="{row['slug']}">
<img src="{row['svg']}" width="1920" height="1080" alt="{escape(row['title'])}">
<div class="notes"><h2>{row['number']:02d} {escape(row['title'])}</h2>
<p>{escape(row['speaker_notes'])}</p><p><a href="{row['png']}">PNG 4K</a> · <a href="{row['svg']}">SVG vector</a></p></div></section>''')
    text = '''<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SalesDW interview demo kit</title>
<style>*{box-sizing:border-box}body{margin:0;background:#e9eef5;color:#15283e;font:16px "DejaVu Sans",sans-serif}
header,main{max-width:1440px;margin:auto}header{padding:30px 24px}h1{font-size:28px;margin:0 0 14px}
p{line-height:1.65}a{color:#2458b5}nav{display:flex;flex-wrap:wrap;gap:16px;align-items:center}
button{font:inherit;padding:10px 16px;border:1px solid #52647b;border-radius:6px;background:white;cursor:pointer}
main{padding:0 24px 36px}.slide{margin-bottom:32px;background:white;scroll-margin-top:15px}
.slide img{display:block;width:100%;height:auto}.notes{padding:4px 28px 20px}.notes h2{font-size:20px}
body.presenting header,body.presenting .notes{display:none}body.presenting main{max-width:none;padding:0}
body.presenting .slide{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
body.presenting .slide img{max-height:100vh;width:100%;object-fit:contain}
@media(max-width:600px){header,main{padding-left:12px;padding-right:12px}.notes{padding:4px 16px 16px}h1{font-size:23px}}
@page{size:1920px 1080px;margin:0}@media print{header,.notes{display:none!important}main{padding:0;max-width:none}
.slide,body.presenting .slide{width:1920px;height:1080px;min-height:0;margin:0;break-after:page;display:block}
.slide:last-child{break-after:auto}.slide img{width:1920px;height:1080px;max-height:none!important}}
</style></head><body><header><h1>Sales and Customer Analytics Warehouse</h1>
<p>Bộ trình bày hệ thống đã triển khai. Olist thật, Airflow, dbt, Kimball, MetricFlow và Superset.
Portfolio độc lập, không phải kiến trúc nội bộ Abbott hoặc Concentrix.</p>
<nav><button id="present" type="button">Chế độ trình bày</button><button id="print" type="button">In hoặc lưu PDF</button>
<a href="architecture-slides.pdf">PDF sơ đồ</a><a href="project-report.pdf">Báo cáo dự án</a><a href="README.md">Hướng dẫn</a></nav>
<p>Phím trái phải chuyển hình, Esc thoát. Hoạt động offline, không gọi CDN hoặc dịch vụ ngoài.</p></header><main>'''
    text += '\n'.join(figures)
    text += '''</main><script>const slides=[...document.querySelectorAll('.slide')];let current=0;
function go(n){current=Math.max(0,Math.min(slides.length-1,n));slides[current].scrollIntoView({behavior:'instant',block:'start'})}
document.getElementById('present').onclick=()=>{document.body.classList.add('presenting');go(0)};
document.getElementById('print').onclick=()=>window.print();document.addEventListener('keydown',e=>{
if(!document.body.classList.contains('presenting'))return;
if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();go(current+1)}
if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();go(current-1)}
if(e.key==='Escape'){document.body.classList.remove('presenting');go(current)}});</script></body></html>'''
    (OUT / "index.html").write_text(text)


def render_slides(slides):
    issues, checks = [], []
    chrome = shutil.which("google-chrome") or "/opt/google/chrome/chrome"
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=2)
        ctx.route(re.compile(r"https?://"), lambda route: route.abort())
        page = ctx.new_page()
        for row in slides:
            page.goto((OUT / row["svg"]).as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            overflow = page.locator("svg text").evaluate_all('''els=>els.flatMap(e=>{
              const b=e.getBBox(),w=Number(e.dataset.maxWidth);const why=[];
              if(b.width>w+2)why.push('width');
              if(b.x<0||b.y<0||b.x+b.width>1920||b.y+b.height>1080)why.push('bounds');
              return why.length?[{text:e.textContent,why,bbox:{x:b.x,y:b.y,width:b.width,height:b.height},allowed:w}]:[]})''')
            page.locator("svg").screenshot(path=str(OUT / row["png"]))
            assert Image.open(OUT / row["png"]).size == (3840,2160)
            checks.append({"slug":row["slug"],"text_overflow":overflow,"png_dimensions":[3840,2160]})
            if overflow:
                issues.append({"slug":row["slug"],"overflow":overflow})
        page.goto((OUT / "index.html").as_uri(), wait_until="load")
        assert page.locator(".slide img").evaluate_all("es=>es.every(e=>e.complete&&e.naturalWidth>0)")
        page.get_by_role("button",name="Chế độ trình bày").click()
        page.keyboard.press("ArrowRight")
        assert page.evaluate("current") == 1
        page.keyboard.press("Escape")
        page.pdf(path=str(OUT / "architecture-slides.pdf"),width="1920px",height="1080px",print_background=True,prefer_css_page_size=True)
        page.set_viewport_size({"width":390,"height":844})
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        browser.close()
    assert len(PdfReader(OUT / "architecture-slides.pdf").pages) == len(slides)
    sheet = Image.new("RGB",(1440,4*298),C["bg"])
    for i,row in enumerate(slides):
        im=Image.open(OUT / row["png"]).convert("RGB")
        im.thumbnail((464,261))
        x,y=(i%3)*480+8,(i//3)*298+6
        sheet.paste(im,(x,y))
        ImageDraw.Draw(sheet).text((x+3,y+267),row["slug"],font=base.font(13),fill=C["ink"])
    sheet.save(QA / "diagram-contact-sheet.png")
    (OUT / "visual-verification.json").write_text(json.dumps({"passed":not issues,"date":DATE,
        "scope":"Document bounds, offline presentation and export QA; not a new pipeline run",
        "checks":checks,"issues":issues,"gallery_controls":True,"mobile_gallery":True},indent=2,ensure_ascii=False)+'\n')
    assert not issues, json.dumps(issues,ensure_ascii=False)


def inline(text):
    text=escape(text)
    text=re.sub(r"`([^`]+)`",r'<font name="Mono">\1</font>',text)
    text=re.sub(r"\*\*([^*]+)\*\*",r'<b>\1</b>',text)
    text=re.sub(r"\[([^\]]+)\]\(([^)]+)\)",r'<link href="\2" color="#2458B5">\1</link>',text)
    return text


def report(e):
    for name, filename in [("Sans","DejaVuSans.ttf"),("Sans-Bold","DejaVuSans-Bold.ttf"),
                            ("Sans-Italic","DejaVuSans-Oblique.ttf"),("Mono","DejaVuSansMono.ttf")]:
        pdfmetrics.registerFont(TTFont(name,str(base.FONT_DIR / filename)))
    pdfmetrics.registerFontFamily("Sans",normal="Sans",bold="Sans-Bold",italic="Sans-Italic",boldItalic="Sans-Bold")
    s=e["analysis"]["summary"]; k=s["selected_month"]
    values=dict(date=DATE,release=e["release"],producer=e["analysis"]["release"]["pipeline_run_id"],
                month=k["month"][:7],value=vn(k["delivered_merchandise_value"],2),orders=vn(k["delivered_orders"]),
                customers=vn(k["delivered_unique_customers"]),aov=vn(k["delivered_aov"],2),
                cancel=vn(Decimal(str(k["cancellation_rate"]))*100,2),
                mom=vn(Decimal(k["value_mom"])*100,2),yoy=vn(Decimal(k["value_yoy"])*100,2),
                ontime=vn(Decimal(s["on_time_deliveries"])/s["delivery_eligible"]*100,2),
                restore=vn(e["restore"]["restore_seconds"],3),health_date=e["health"]["measured_at"][:10],
                raw_sha=e["source_manifest"]["sha256"])
    md=Template((ROOT / "docs/demo/report-short-template.md").read_text()).substitute(values)
    (OUT / "report.md").write_text(md)
    styles={
        "body":ParagraphStyle("body",fontName="Sans",fontSize=10.2,leading=15,spaceAfter=9,textColor=colors.HexColor("#15283E")),
        "title":ParagraphStyle("title",fontName="Sans-Bold",fontSize=25,leading=33,spaceAfter=18,textColor=colors.black),
        "h1":ParagraphStyle("h1",fontName="Sans-Bold",fontSize=19,leading=25,spaceAfter=15,textColor=colors.black),
        "h2":ParagraphStyle("h2",fontName="Sans-Bold",fontSize=12,leading=17,spaceBefore=8,spaceAfter=7,textColor=colors.black),
        "cell":ParagraphStyle("cell",fontName="Sans",fontSize=9,leading=13,spaceAfter=0,wordWrap="LTR"),
        "small":ParagraphStyle("small",fontName="Sans",fontSize=8.4,leading=12,textColor=colors.HexColor("#52647B")),
    }
    def header(canvas, doc):
        w,h=canvas._pagesize
        canvas.setFont("Sans",8)
        canvas.setFillColor(colors.HexColor("#52647B"))
        canvas.drawString(43,h-26,"SALESDW  |  DATA ENGINEER PORTFOLIO")
        canvas.drawRightString(w-43,h-26,DATE)
        canvas.setStrokeColor(colors.HexColor("#D7E1EB"))
        canvas.line(43,35,w-43,35)
        canvas.drawString(43,22,"Olist public data · Local demo · Không đại diện Abbott / Concentrix")
        canvas.drawRightString(w-43,22,str(doc.page))
    doc=BaseDocTemplate(str(OUT / "project-report.pdf"),pagesize=A4,leftMargin=43,rightMargin=43,
                        topMargin=47,bottomMargin=47,title="Sales and Customer Analytics Warehouse",author="Independent DE portfolio")
    for label,size in [("portrait",A4),("landscape",landscape(A4))]:
        w,h=size
        doc.addPageTemplates(PageTemplate(id=label,pagesize=size,frames=[Frame(43,47,w-86,h-94,id=label,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=header))
    flow=[]; lines=md.splitlines(); i=0; width=A4[0]-86
    while i<len(lines):
        line=lines[i].strip()
        if not line:
            i+=1;continue
        if line.startswith("<!-- pagebreak"):
            label="landscape" if "landscape" in line else "portrait"
            width=(landscape(A4) if label=="landscape" else A4)[0]-86
            flow += [NextPageTemplate(label),PageBreak()]
        elif line.startswith("!["):
            match=re.match(r"!\[([^]]*)\]\(([^)]+)\)",line)
            path=OUT / match[2]
            iw,ih=Image.open(path).size
            maxh=375 if width>600 else 350
            scale=min(width/iw,maxh/ih)
            flow.append(DocImage(str(path),width=iw*scale,height=ih*scale,hAlign="LEFT"))
            flow.append(Spacer(1,9))
            flow.append(Paragraph(inline(match[1]),styles["small"]))
            flow.append(Spacer(1,7))
        elif line.startswith("|"):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith("|"):
                cells=[c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[:\- ]+",c) for c in cells):
                    rows.append(cells)
                i+=1
            cols=len(rows[0])
            ratios={2:[0.30,0.70],3:[0.26,0.34,0.40],4:[0.24,0.24,0.26,0.26]}.get(cols,[1/cols]*cols)
            if rows[0][0] in {"Chỉ số","KPI"} and cols==3:
                ratios=[0.35,0.24,0.41]
            cells=[[Paragraph(inline(c),styles["cell"]) for c in row] for row in rows]
            table=Table(cells,colWidths=[width*r for r in ratios],repeatRows=1,hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF1FD")),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F4F7FB")]),
                ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#D9D9D9")),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),8),
                ("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),7),
                ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
            flow += [table,Spacer(1,12)]
            continue
        elif line.startswith("# "):
            flow.append(Paragraph(inline(line[2:]),styles["title"]))
        elif line.startswith("## "):
            flow.append(Paragraph(inline(line[3:]),styles["h1"]))
        elif line.startswith("### "):
            flow.append(Paragraph(inline(line[4:]),styles["h2"]))
        elif line.startswith("- "):
            flow.append(Paragraph("• "+inline(line[2:]),styles["body"]))
        else:
            paragraph=[line]
            while i+1<len(lines) and lines[i+1].strip() and not lines[i+1].lstrip().startswith(("#","|","- ","![","<!--")):
                i+=1;paragraph.append(lines[i].strip())
            flow.append(Paragraph(inline(" ".join(paragraph)),styles["body"]))
        i+=1
    doc.build(flow)
    pages=PdfReader(OUT / "project-report.pdf").pages
    intended=md.count("<!-- pagebreak")+1
    assert intended==5,"The current user-facing report must stay within five pages"
    assert len(pages)==intended,("Unexpected pagination",len(pages),intended)
    assert all(len(page.extract_text().strip())>100 for page in pages),"Blank page"


def notes_and_readme(slides,e):
    notes=["# Ghi chú trình bày\n", "Portfolio độc lập; nguồn Olist, không phải kiến trúc nội bộ Abbott hoặc Concentrix.\n",
           "## Lộ trình 7 phút\n", "- 0–1 phút: hình 01 và bài toán cùng đầu ra.\n- 1–2 phút: hình 02 và 03; giải thích ranh giới dữ liệu.\n- 2–3 phút: hình 04, 05 hoặc 10; grain và conformed dimensions.\n- 3–4 phút: hình 06–08; Airflow, semantic và publication.\n- 4–6 phút: mở Tổng quan Superset, đổi tháng 07 sang 06 rồi vào trang chuyên sâu.\n- 6–7 phút: hình 09; đưa evidence và nêu giới hạn.\n",
           "Không chạy failure injection hoặc restore trên sales_dw để trình bày; dùng bằng chứng và sandbox được duyệt riêng.\n"]
    notes += [f"## {s['number']:02d} {s['title']}\n\n{s['speaker_notes']}\n" for s in slides]
    (OUT / "presentation-notes.md").write_text('\n'.join(notes))
    rows='\n'.join(f"| {s['number']:02d} | {s['title']} | [PNG]({s['png']}) | [SVG]({s['svg']}) |" for s in slides)
    (OUT / "README.md").write_text(f'''# Bộ demo Sales and Customer Analytics Warehouse

Bản giao ngày {DATE}. Đây là **portfolio độc lập với Olist thật**, không phải hệ thống nội bộ Abbott hoặc Concentrix. Bộ này mô tả implementation hiện có; không thay thế design baseline ở docs/visuals.

## Dùng ngay

- [Báo cáo dự án PDF](project-report.pdf): bản gọn 5 trang, dùng ảnh kiến trúc người dùng cung cấp và giữ schema hiện có; tập trung nguồn dữ liệu, quy trình và kết quả.
- [Nội dung báo cáo Markdown](report.md): có thể chỉnh sửa trước khi gửi.
- [PDF sơ đồ](architecture-slides.pdf): 10 hình cho buổi trình bày.
- [Gallery offline](index.html): mở file bằng trình duyệt, chọn Chế độ trình bày; dùng phím trái/phải và Esc.
- [Ghi chú thuyết trình](presentation-notes.md): lộ trình 7 phút và lời giải thích từng hình.
- [ERD Mermaid](warehouse-schema.mmd): nguồn mô hình có từng FK; PNG/SVG hình 10 chỉ rút gọn cột.
- [Phân tích nghiệp vụ](business-analysis.md): số liệu cùng release và giới hạn kết luận.

Ảnh kiến trúc tại `assets/architecture-user.png` được dùng làm ảnh chính của repo và trong báo cáo; bộ 10 hình/PDF sơ đồ kỹ thuật vẫn được giữ. Chú thích dưới ảnh phân biệt 9 file trong archive với 7 feed thực sự nạp và xác định đúng nơi lưu dimensions/facts.

## Danh mục ảnh 4K

| Số | Nội dung | PNG 3840 × 2160 | Vector |
|---|---|---|---|
{rows}

## Đầu ra thật

Ảnh sáu dashboard nằm ở `screenshots/`. Release `{e['release']}`, source cut 1; tháng mặc định 2018-07, customer cutoff 2018-08-31. Tỷ lệ và cửa sổ khác nhau không gộp chung thành một KPI.

Business facts: 99.441 orders, 112.650 items, 103.886 payments. 6 dashboard có 60 active objects, không phải 60 chỉ số nghiệp vụ riêng. Metadata lịch sử có thể có nhiều assets hơn. Có 8 saved SQL analyses, 5 MetricFlow exports và 8 core metrics.

`manifest.json` ghi input/output hashes và phạm vi evidence. Current API/browser/health checks được đọc từ lần khởi động demo; retry/recovery/restore sử dụng chứng cứ lịch sử được ghi rõ ngày. Việc xuất kit không chạy lại pipeline hoặc thay release.

## Tái tạo

Từ project root: `python scripts/build_demo_kit.py`. Cần Pillow, Playwright, reportlab, pypdf và Chrome local. Script chỉ đọc các input allowlist; không tải nguồn, không đọc credential, không chạy DDL/SQL/Docker. Xem dependencies trong môi trường làm tài liệu; không thêm chúng vào runtime pipeline.

## Chia sẻ an toàn

Gửi `project-report.pdf` hoặc ZIP demo-kit ở thư mục cha. Kit không chứa raw records, credentials, backups, volumes hay private connection strings. Ảnh dashboard chỉ là aggregate published reports. Giữ attribution Olist CC BY-NC-SA 4.0; giấy phép dữ liệu không suy ra quyền triển khai thương mại cho khách hàng. Không dùng logo Abbott/Concentrix để ngụ ý dự án của họ.
''')


def schema_mermaid(e):
    lines=["erDiagram"]
    for dim in e["model"]["dimensions"]:
        lines += [f"    {dim['name'].upper()} {{", "        uuid release_id PK",f"        bigint {dim['primary_key']} PK"]
        lines += [f"        {'boolean' if col.startswith('is_') else 'text'} {col}" for col in dim["attributes"][:3] if col not in {"full_date","month_start","day","is_inferred"}]
        if dim["name"]=="dim_date":
            lines += ["        date full_date", "        date month_start"]
        lines += ["    }"]
    for fact in e["model"]["facts"]:
        name=fact["name"].upper()
        identity={"fct_orders":"order_key","fct_order_items":"order_item_key","fct_payments":"payment_key"}[fact["name"]]
        lines += [f"    {name} {{","        uuid release_id PK",f"        text {identity} PK","        text source_system", "        text order_id"]
        lines += [f"        int {key}" for key in fact["grain"] if key not in {"source_system","order_id"}]
        lines += [f"        bigint {key} FK" if not key.endswith("date_key") else f"        int {key} FK" for key in fact["foreign_keys"]]
        lines += [f"        {'numeric' if kind.startswith('numeric') else 'int'} {key}" for key,kind in list(fact["measures"].items())[:4]]
        lines += ["    }"]
        for key,target in fact["foreign_keys"].items():
            dim=target.split('.')[0].upper()
            lines.append(f"    {dim} ||--o{{ {name} : {key}")
    value='\n'.join(lines)+'\n'
    value=value.replace("bigint date_key PK","int date_key PK")
    (OUT / "warehouse-schema.mmd").write_text(value)
    ddl=(ROOT / "db/migrations/001_schema.sql").read_text()
    blocks=re.findall(r"    ([A-Z_]+) \{(.*?)\n    \}",value,re.S)
    assert len(blocks)==10
    for name,body in blocks:
        physical=re.search(r"CREATE TABLE warehouse_store\."+name.lower()+r" \((.*?)\n\);",ddl,re.S)[1]
        for col in re.findall(r"^\s+\w+ (\w+)",body,re.M):
            assert re.search(r"^\s+"+col+r"\s+",physical,re.M),(name,col)
    expected_edges=sum(len(f["foreign_keys"]) for f in e["model"]["facts"])
    assert value.count('||--o{')==expected_edges==19
    assert not re.search(r"^    FCT_\w+ \|\|--",value,re.M)
    verification=read(str((OUT/"visual-verification.json").relative_to(ROOT)))
    verification["schema_checks"]={"tables":10,"fk_edges":expected_edges,"columns_exist_in_migration":True,"no_fact_to_fact_fk":True}
    (OUT/"visual-verification.json").write_text(json.dumps(verification,indent=2,ensure_ascii=False)+'\n')


def package(slides,e):
    input_paths=["README.md","infra/compose.yaml","orchestration/dags/sales_warehouse_pipeline.py",
                 "db/migrations/001_schema.sql","db/migrations/005_published_analysis.sql",
                 "contracts/warehouse-model.json","contracts/metric-catalog.json",
                 "dbt/models/semantic/semantic_models.yml","src/sales_dw/export_metrics.py",
                 "docs/implementation-progress.md","docs/demo/report-short-template.md","docs/demo/assets/architecture-user.png","scripts/build_demo_kit.py","scripts/build_project_visuals.py",
                 "docs/evidence/source-profile.json","data/source-manifest.json","output/analysis/results.json",
                 "var/evidence/health.json","var/evidence/superset.json","var/evidence/superset-browser.json",
                 "docs/evidence/runtime/runtime-sales_dw.json","docs/evidence/runtime/airflow.json",
                 "docs/evidence/runtime/restore.json","docs/evidence/runtime/incremental.json",
                 "docs/evidence/runtime/pipeline-recovery.json"]
    manifest={"created_at_utc":datetime.now(timezone.utc).isoformat(),"release_id":e["release"],"source_cut":1,
              "title":"Sales and Customer Analytics Warehouse","scope":"Independent interview portfolio; local implemented demo; not internal Abbott/Concentrix architecture",
              "data_license":"Olist CC BY-NC-SA 4.0; maintain attribution and applicable derived-data conditions",
              "source_archive":{"sha256":e["source_manifest"]["sha256"],"bytes":e["source_manifest"]["bytes"],
                                "source_url":e["source_manifest"]["source_url"],"raw_included_in_kit":False},
              "report":{"pages":5,"architecture_image":"assets/architecture-user.png","image_policy":"Unmodified user-provided illustration with implementation scope clarifications below it","schema_unchanged":True},
              "evidence_scope":{"current_ui":"health, 60 chart queries, 8 SQL Lab queries, 6 rendered pages, 14 actual navigation clicks",
                                "historical_runtime":"2026-10-15 bounded DWH, semantic, retry, incremental, recovery and restore checks; not rerun by this exporter",
                                "not_accepted":["production/HA","source CDC","real Olist SCD2 history","Superset app restore","remote CI","off-host encrypted recovery"]},
              "slides":slides,"input_sha256":{p:sha(ROOT/p) for p in input_paths},
              "output_sha256":{str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='manifest.json'}}
    (OUT / "manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    archive=ROOT / "output/demo-kit.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():
                assert not any(token in str(p.relative_to(OUT)).lower() for token in ('secret','password','backup','.env'))
                bundle.write(p,'demo-kit/'+str(p.relative_to(OUT)))
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    for name,expected in manifest["output_sha256"].items():
        assert sha(OUT/name)==expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-only',action='store_true',help='Rebuild only the report and package; retain all schema/diagram assets byte-for-byte')
    args=parser.parse_args()
    for p in [OUT,OUT/"png",OUT/"svg",OUT/"screenshots",OUT/"assets",QA]:
        p.mkdir(parents=True,exist_ok=True)
    e=load_evidence()
    retained={}
    if args.report_only:
        prior=read(str((OUT/'manifest.json').relative_to(ROOT)))
        assert prior['release_id']==e['release'],'Report-only mode must retain the existing evidence release'
        slides=prior['slides']
        retained={name:digest for name,digest in prior['output_sha256'].items()
                  if name.startswith(('png/','svg/','screenshots/')) or name in {'warehouse-schema.mmd','architecture-slides.pdf','visual-verification.json','index.html'}}
        assert retained and all(sha(OUT/name)==digest for name,digest in retained.items())
    else:
        slides=diagrams(e)
        gallery(slides)
        render_slides(slides)
        for board in ("overview","sales","commercial","customers","service","trust"):
            shutil.copyfile(ROOT/"var/evidence/superset-screenshots"/(board+'.png'),OUT/"screenshots"/(board+'.png'))
        shutil.copyfile(ROOT/"output/analysis/business-analysis.md",OUT/"business-analysis.md")
        schema_mermaid(e)
    shutil.copyfile(ROOT/'docs/demo/assets/architecture-user.png',OUT/'assets/architecture-user.png')
    notes_and_readme(slides,e)
    report(e)
    assert all(sha(OUT/name)==digest for name,digest in retained.items()),'Report editing must not change the existing schema/diagram assets'
    package(slides,e)
    print(json.dumps({"passed":True,"diagrams":len(slides),"pdf_report_pages":len(PdfReader(OUT/"project-report.pdf").pages),
                      "folder":str(OUT),"archive":str(ROOT/"output/demo-kit.zip")},ensure_ascii=False))


if __name__=="__main__":
    main()
