"""Build presentation diagrams from the frozen design, not runtime screenshots.

Run with Python 3 and the optional visual tooling documented in docs/visuals/README.md.
The SVG source is deterministic. Chrome renders PNG/PDF and measures every label.
No warehouse, network service, migration, or business pipeline is started.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/visuals"
PDF = ROOT / "output/pdf/project-architecture.pdf"
W, H = 1920, 1080
C = {
    "bg": "#F4F7FB", "paper": "#FFFFFF", "ink": "#15283E",
    "muted": "#52647B", "line": "#D7E1EB", "blue": "#2458B5",
    "blue_bg": "#EAF1FD", "teal": "#087E79", "teal_bg": "#E5F5F1",
    "amber": "#966119", "amber_bg": "#FFF3DD", "red": "#AE3949",
    "red_bg": "#FCECEF", "purple": "#6650A8", "purple_bg": "#F0ECFA",
}
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
FONTS = {}


def font(size, bold=False):
    key = size, bold
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype(
            str(FONT_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size
        )
    return FONTS[key]


def wrap(value, width, size=25, bold=False):
    result = []
    for paragraph in value.split("\n"):
        line = ""
        for word in paragraph.split():
            attempt = (line + " " + word).strip()
            if line and font(size, bold).getlength(attempt) > width:
                result.append(line)
                line = word
            else:
                line = attempt
        result.append(line)
    return result


class Canvas:
    def __init__(self, number, slug, title, subtitle, sources, notes):
        self.number, self.slug, self.title = number, slug, title
        self.sources, self.notes = sources, notes
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title>',
            f'<desc id="desc">{escape(subtitle)}. Sơ đồ thiết kế; chưa nghiệm thu runtime.</desc>',
            '<defs>',
            *[f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" '
              f'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
              f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{C[k]}"/></marker>'
              for k in ("muted", "blue", "teal", "red", "purple")],
            '</defs>',
        ]
        self.rect(0, 0, W, H, C["bg"], radius=0)
        self.rect(0, 0, 18, H, C["blue"], radius=0)
        self.text(72, 53, "SALES & CUSTOMER ANALYTICS WAREHOUSE", 19, "blue", True)
        self.text(1848, 53, "DESIGN BASELINE 2.0  /  15.10.2026", 17, "muted", anchor="end")
        self.text(72, 123, title, 49, bold=True, maxw=1776)
        self.text(72, 169, subtitle, 24, "muted", maxw=1776)
        self.line([(72, 1007), (1848, 1007)], "line", 2)
        self.text(72, 1046, "Portfolio độc lập • Olist • Không đại diện kiến trúc Abbott / Concentrix", 18, "muted")
        self.text(1848, 1046, f"THIẾT KẾ, CHƯA NGHIỆM THU HỆ THỐNG   |   {number:02d} / 09", 17, "muted", anchor="end")

    def rect(self, x, y, w, h, fill, stroke=None, radius=18, dash=False):
        attrs = f' stroke="{stroke}" stroke-width="2"' if stroke else ""
        attrs += ' stroke-dasharray="8 6"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                          f'rx="{radius}" fill="{fill}"{attrs}/>')

    def text(self, x, y, value, size=25, color="ink", bold=False, anchor="start", maxw=None):
        if maxw is None:
            maxw = (W - x - 40) if anchor == "start" else (x - 40)
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="DejaVu Sans" font-size="{size}" '
            f'font-weight="{700 if bold else 400}" fill="{C.get(color, color)}" '
            f'text-anchor="{anchor}" data-max-width="{maxw}">{escape(str(value))}</text>'
        )

    def para(self, x, y, value, maxw, size=25, color="muted", bold=False, gap=None):
        gap = gap or size * 1.45
        lines = wrap(value, maxw, size, bold)
        for i, line in enumerate(lines):
            self.text(x, y + i * gap, line, size, color, bold, maxw=maxw)
        return y + len(lines) * gap

    def line(self, points, color="muted", width=3, arrow=False, dash=False):
        pts = " ".join(f"{x},{y}" for x, y in points)
        attrs = f' marker-end="url(#arrow-{color})"' if arrow else ""
        attrs += ' stroke-dasharray="8 7"' if dash else ""
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{C[color]}" '
                          f'stroke-width="{width}" stroke-linejoin="round"{attrs}/>')

    def pill(self, x, y, value, color="blue", width=None):
        width = width or int(font(19, True).getlength(value) + 32)
        self.rect(x, y, width, 36, C[color + "_bg"], radius=10)
        self.text(x + 16, y + 25, value, 19, color, True, maxw=width - 32)

    def card(self, x, y, w, h, title, body=(), color="blue", kicker=None, size=25, title_size=29):
        self.rect(x, y, w, h, C["paper"], C["line"])
        self.rect(x, y + 20, 5, h - 40, C[color], radius=2)
        top = y + 44
        if kicker:
            self.text(x + 26, top, kicker, 18, color, True, maxw=w - 52)
            top += 40
        top = self.para(x + 26, top, title, w - 52, title_size, "ink", True, title_size * 1.31) + 13
        for item in body:
            top = self.para(x + 26, top, item, w - 52, size, "muted", gap=size * 1.38) + 16
        if body and top - 16 - size * 1.38 + size * 0.3 > y + h - 15:
            raise ValueError(f"Card overflows vertically: {self.slug}: {title}: {top} > {y+h}")

    def note(self, x, y, w, h, title, body, color="blue", size=24):
        self.rect(x, y, w, h, C[color + "_bg"])
        self.text(x + 24, y + 38, title, 23, color, True, maxw=w - 48)
        end = self.para(x + 24, y + 70, body, w - 48, size, "ink")
        if body and end - size * 1.45 + size * 0.3 > y + h - 10:
            raise ValueError(f"Note overflows: {self.slug}: {title}")

    def finish(self):
        self.parts.append("</svg>")
        value = "\n".join(self.parts)
        ET.fromstring(value)
        dest = OUT / "svg" / f"{self.slug}.svg"
        dest.write_text(value + "\n", encoding="utf-8")
        return {
            "number": self.number, "slug": self.slug, "title": self.title,
            "svg": f"svg/{self.slug}.svg", "png": f"png/{self.slug}.png",
            "sources": self.sources, "speaker_notes": self.notes,
        }


def diagrams():
    source = json.loads((ROOT / "docs/evidence/source-profile.json").read_text())
    rows = sum(item["rows"] for item in source["inventory"] if item["in_v1"])
    assert rows == 451535
    assert json.loads((ROOT / "docs/evidence/design-contracts.json").read_text())["check_count"] == 137
    result = []

    d = Canvas(1, "01-objectives-input-output", "Từ dữ liệu rời rạc đến số liệu đáng tin cậy",
               "Mục tiêu: cùng một định nghĩa, cùng một phiên bản dữ liệu, có thể đối soát và khôi phục.",
               ["docs/PRODUCTION_DESIGN.md", "contracts/dashboard-contract.json", "docs/evidence/source-profile.json"],
               "Mở đầu bằng kết quả doanh nghiệp cần: số đơn, giá trị hàng, khách hàng và hiệu quả sản phẩm đáng tin cậy. "
               "Nguồn là Olist thật; đây là portfolio độc lập, không phải kiến trúc đã biết của Abbott hay Concentrix. "
               "Nêu ba lớp đầu ra: dữ liệu phân tích, KPI thống nhất và bằng chứng vận hành. Các đầu ra runtime vẫn là mục tiêu nghiệm thu.")
    for x, word, c in [(72, "01  INPUT", "blue"), (682, "02  HỆ THỐNG", "purple"), (1292, "03  OUTPUT MỤC TIÊU", "teal")]:
        d.pill(x, 213, word, c)
    d.card(72, 270, 556, 380, "Dữ liệu kinh doanh thật", [
        "Olist v2 • 7 feed • 451.535 dòng", "Customer, product, seller, order, item, payment, category translation",
        "Snapshot + checksum + provenance", "Fixture lỗi/cập nhật tách riêng dữ liệu thật"], size=24)
    d.card(682, 270, 556, 380, "Một nguồn phân tích nhất quán", [
        "Ingest → kiểm tra → hợp nhất", "Kimball Warehouse + dbt", "Semantic Layer + metric exports",
        "Airflow + kiểm thử + audit + recovery"], color="purple", size=24)
    d.card(1292, 270, 556, 380, "Dữ liệu và kết quả có thể dùng", [
        "7 dimensions + 3 facts", "8 KPI dùng chung, 5 metric exports", "3 dashboard: sales, commercial, health",
        "SQL phân tích + lineage + evidence"], color="teal", size=24)
    for start in (628, 1238):
        d.line([(start + 8, 455), (start + 44, 455)], "blue", arrow=True)
    d.note(72, 689, 856, 142, "AI DÙNG VÀ ĐỂ LÀM GÌ?", "Business/Analyst: xem bán hàng, khách hàng, danh mục. DE/Operator: truy vết, xử lý lỗi, chạy lại và khôi phục.")
    d.note(960, 689, 888, 142, "THÀNH CÔNG ĐƯỢC ĐO BẰNG GÌ?", "Số liệu đối soát đúng; replay không nhân đôi; lỗi không được publish; SQL, semantic và BI cùng định nghĩa.", "teal")
    d.note(72, 857, 1776, 112, "NGOÀI PHẠM VI", "Telesales • dữ liệu bệnh nhân • MPP • streaming • HA đa máy. Không gán ngành dược cho dữ liệu thương mại Olist.", "amber", 23)
    result.append(d.finish())

    d = Canvas(2, "02-source-data-and-baseline", "Dữ liệu thật đủ để làm và đối soát",
               "Một nhà công bố, bảy domain feeds; không gọi bảy file là bảy hệ thống độc lập.",
               ["data/source-manifest.json", "docs/evidence/source-profile.json", "contracts/source-catalog.json"],
               "Cho thấy dự án có dữ liệu thật trước khi nói công nghệ. Phân biệt customer_id theo tham chiếu đơn với customer_unique_id bền vững. "
               "Baseline trên hình được tính trực tiếp từ nguồn, chưa phải kết quả Warehouse. Các cảnh báo dữ liệu là đặc tính cần giải thích, không tự ý xóa cho sạch. "
               "Không có CDC, timestamp cập nhật nguồn hay lịch sử business-effective; thay đổi vận hành được mô phỏng có nhãn riêng.")
    d.rect(72, 220, 1045, 568, C["paper"], C["line"])
    d.text(100, 265, "FEED NGUỒN", 22, "blue", True)
    d.text(762, 265, "SỐ DÒNG", 22, "blue", True, anchor="end")
    d.text(800, 265, "VAI TRÒ", 22, "blue", True)
    inventory = [
        ("customers", 99441, "Tham chiếu khách/địa chỉ"), ("orders", 99441, "Đơn và milestone"),
        ("order_items", 112650, "Dòng hàng, giá, freight"), ("payments", 103886, "Bản ghi thanh toán"),
        ("products", 32951, "Danh mục sản phẩm"), ("sellers", 3095, "Người bán"),
        ("category_translation", 71, "Dịch tên category"),
    ]
    for i, (name, count, role) in enumerate(inventory):
        y = 313 + i * 59
        d.line([(100, y + 18), (1089, y + 18)], "line", 1)
        d.text(100, y, name, 25, bold=True, maxw=440)
        d.text(762, y, f"{count:,}".replace(",", "."), 26, anchor="end", maxw=175)
        d.text(800, y, role, 20, "muted", maxw=290)
    d.text(100, 758, "TỔNG TRONG PHẠM VI", 23, "blue", True)
    d.text(762, 758, "451.535", 30, "blue", True, anchor="end")
    d.note(1150, 220, 698, 168, "BASELINE TÍNH TRỰC TIẾP TỪ NGUỒN", "96.478 đơn delivered\n93.358 khách có đơn delivered\n13.221.498,11 giá trị hàng, chưa gồm freight", "teal", 23)
    d.note(1150, 410, 698, 245, "CẢNH BÁO THỰC TẾ ĐÃ PHÁT HIỆN", "775 đơn không có items; 1 đơn không có payment\n610 sản phẩm thiếu category\n8 đơn delivered thiếu ngày nhận\n303 matched orders lệch tiền trên 0,01", "amber", 23)
    d.note(1150, 677, 698, 111, "IDENTITY KHÔNG ĐƯỢC NHẦM", "99.441 customer references → 96.096 khách phân biệt", "blue", 22)
    d.note(72, 818, 1045, 151, "GIỮ NGUYÊN BẢN GỐC", "ZIP 44.717.580 bytes + SHA-256 + manifest. Geolocation/reviews ngoài phạm vi; không lấy số dòng đó để phóng đại số giao dịch.", "blue", 23)
    d.note(1150, 818, 698, 151, "GIỚI HẠN VÀ QUYỀN SỬ DỤNG", "Không có currency/timezone/CDC; BRL là quy ước demo. Olist: CC BY-NC-SA 4.0, giữ attribution.", "purple", 23)
    result.append(d.finish())

    d = Canvas(3, "03-system-architecture", "Kiến trúc tổng thể: nguồn → Warehouse → BI",
               "Airflow điều phối; dbt quản lý transformation; MetricFlow sở hữu logic KPI dùng chung.",
               ["specs/spec-package/02-architecture/production-local.md", "specs/spec-package/03-data/semantic-and-metrics.md"],
               "Đi theo số thứ tự 1 đến 8. Hàng trên tiếp nhận và lưu phiên bản nguồn; hàng dưới đi từ phải sang trái để mô tả xử lý đến consumer. "
               "Working models không được BI đọc. MetricFlow thực thi trên một release cụ thể; Metabase đọc exports đã công bố, không giả định native connector. "
               "Atomic publication chỉ là giao dịch PostgreSQL; cập nhật link Metabase nằm ngoài giao dịch đó.")
    d.rect(72, 212, 1776, 76, C["blue_bg"])
    d.text(98, 260, "APACHE AIRFLOW", 27, "blue", True)
    d.text(430, 260, "Schedule • dependencies • retries • logs • trạng thái đúng • failure handling", 25, "ink")
    xs = [72, 528, 984, 1440]
    top = [
        ("Nguồn Olist", ["7 CSV nghiệp vụ", "Manifest + SHA-256", "Fixture tổng hợp tách riêng"], "01  SOURCE", "blue"),
        ("Python ingestion", ["Schema / row validation", "Batch, receipt, record hash", "Reject → quarantine"], "02  INGEST", "blue"),
        ("MinIO raw", ["Source-native bất biến", "Audit, replay từ bản gốc", "Artifact identity"], "03  PRESERVE", "blue"),
        ("PostgreSQL landing", ["Accepted source versions", "Load transaction + ledger", "Chốt source_cut"], "04  ADMIT", "purple"),
    ]
    for x, (title, body, k, col) in zip(xs, top):
        d.card(x, 328, 408, 260, title, body, col, k, 22)
    for x in (480, 936, 1392):
        d.line([(x + 6, 456), (x + 42, 456)], "blue", arrow=True)
    bottom = [
        ("Metabase / SQL", ["Published releases only", "Mọi card pin release_id", "Analyst read-only views"], "08  CONSUME", "teal"),
        ("MetricFlow + exports", ["Bind một release", "5 exports + SQL parity", "Publish sau mọi gate"], "07  SEMANTICS / PUBLISH", "teal"),
        ("Warehouse snapshot", ["7 dimensions + 3 facts", "Typed, immutable release", "FK trong cùng release"], "06  FREEZE", "purple"),
        ("dbt working models", ["Staging → intermediate", "Kimball dims / facts", "Tests + checkpoints"], "05  TRANSFORM", "purple"),
    ]
    d.line([(1644, 588), (1644, 636)], "purple", arrow=True)
    for x, (title, body, k, col) in zip(xs, bottom):
        d.card(x, 636, 408, 260, title, body, col, k, 22)
    for x in (528, 984, 1440):
        d.line([(x - 5, 765), (x - 42, 765)], "teal", arrow=True)
    d.rect(72, 922, 1776, 60, C["purple_bg"])
    d.text(98, 961, "XUYÊN SUỐT", 21, "purple", True)
    d.text(294, 961, "Contracts • DQ • lineage • least privilege • lease fencing • backup / restore • retention", 23, maxw=1515)
    result.append(d.finish())

    d = Canvas(4, "04-kimball-bus-matrix", "Kimball: thiết kế theo business process và grain",
               "Bus matrix tích hợp ba process bằng conformed dimensions; không phải ba star schema rời rạc.",
               ["specs/spec-package/03-data/kimball-design.md", "contracts/warehouse-model.json"],
               "Giải thích bốn bước Kimball: chọn process, khai báo grain, chọn dimensions, chọn facts. "
               "Ngày trên payment là purchase context, không phải ngày thanh toán vì nguồn không có. "
               "Product/seller chỉ thuộc sales-line grain; không phân bổ payment về sản phẩm khi chưa có hợp đồng. "
               "Order ID là degenerate dimension, không phải lý do để join các fact nguyên tử.")
    d.pill(72, 210, "BUSINESS PROCESS → GRAIN → DIMENSIONS → FACTS", "purple")
    d.rect(72, 270, 1776, 333, C["paper"], C["line"])
    headers = [(650, ["Purchase", "date"]), (806, ["Other", "dates"]), (962, ["Customer"]),
               (1118, ["Product"]), (1274, ["Seller"]), (1430, ["Buyer", "geography"]),
               (1586, ["Order", "status"]), (1758, ["Payment", "method"])]
    d.text(100, 317, "BUSINESS PROCESS / FACT", 22, "blue", True)
    for cx, words in headers:
        for j, word in enumerate(words):
            d.text(cx, 308 + j * 29, word, 21, "blue", True, "middle", 150)
    matrix = [
        ("Sales lines", "fct_order_items", [1, 0, 1, 1, 1, 1, 1, 0]),
        ("Payment records", "fct_payments", [1, 0, 1, 0, 0, 1, 1, 1]),
        ("Order fulfillment", "fct_orders", [1, 1, 1, 0, 0, 1, 1, 0]),
    ]
    for i, (label, name, present) in enumerate(matrix):
        y = 388 + i * 86
        d.line([(96, y - 31), (1822, y - 31)], "line", 1)
        d.text(100, y, label, 25, bold=True, maxw=470)
        d.text(100, y + 30, name, 21, "muted", maxw=470)
        for (cx, _), yes in zip(headers, present):
            d.text(cx, y + 17, "X" if yes else "-", 27, "teal" if yes else "muted", bool(yes), "middle", 150)
    d.card(72, 636, 568, 202, "Một dòng hàng", ["source + order_id + order_item_id", "Transaction fact"], "blue", size=22)
    d.card(676, 636, 568, 202, "Một payment record", ["source + order_id + payment_sequential", "Transaction fact; không phân bổ về item"], "purple", size=21)
    d.card(1280, 636, 568, 202, "Một đơn hàng", ["source + order_id", "Accumulating snapshot; 5 date roles"], "teal", size=22)
    d.note(72, 868, 1776, 111, "NGUYÊN TẮC TÍCH HỢP", "Integer surrogate keys ổn định • date key YYYYMMDD • order_id là degenerate dimension • aggregate riêng từng fact rồi drill-across.", "blue", 23)
    result.append(d.finish())

    d = Canvas(5, "05-dimensional-constellation", "Warehouse constellation: ba fact, bảy dimension",
               "Dimension lặp lại trên hình để dễ đọc; trong Warehouse chúng là cùng một định nghĩa và key registry.",
               ["docs/warehouse-erd.md", "specs/spec-package/03-data/kimball-design.md", "db/design/001_warehouse_schema.sql"],
               "Đây là sơ đồ logic rút gọn, không phải toàn bộ DDL. Bốn dimension chung ở phía trên kết nối độc lập vào mỗi fact. "
               "Product và seller chỉ nối vào item fact; payment method chỉ nối payment fact. "
               "Mỗi FK vật lý gồm release_id và dimension key; không có FK fact-to-fact. "
               "SCD2 chỉ minh chứng bằng fixture có thời điểm hiệu lực rõ ràng, không gán lịch sử giả cho snapshot Olist.")
    for col, title, fact, keylines, special in [
        (0, "SALES LINES", "fct_order_items", ["order_id + order_item_id", "price • freight • item_count"], "items"),
        (1, "PAYMENT RECORDS", "fct_payments", ["order_id + payment_sequential", "payment_value • installments*"], "payments"),
        (2, "ORDER FULFILLMENT", "fct_orders", ["order_id", "order_count • milestone flags"], "orders"),
    ]:
        x = 72 + col * 604
        d.rect(x, 218, 568, 614, C["paper"], C["line"])
        d.text(x + 26, 259, title, 21, "blue", True)
        for dx, dy, name in [(26, 287, "dim_customer"), (298, 287, "dim_date"),
                             (26, 373, "dim_buyer_geography"), (298, 373, "dim_order_status")]:
            d.rect(x + dx, dy, 244, 59, C["blue_bg"], radius=10)
            d.text(x + dx + 122, dy + 37, name, 18, "blue", True, "middle", 232)
        for dx, bottom in [(148, 346), (420, 346)]:
            lane = x + (12 if dx == 148 else 556)
            d.line([(x + dx, bottom), (lane, bottom), (lane, 460), (x + 284, 460), (x + 284, 488)], "blue", 2, True)
        for dx in (148, 420):
            d.line([(x + dx, 432), (x + dx, 460), (x + 284, 460), (x + 284, 488)], "blue", 2, True)
        d.rect(x + 36, 490, 496, 146, C["purple_bg"])
        d.text(x + 284, 532, fact, 29, "purple", True, "middle", 460)
        for j, value in enumerate(keylines):
            d.text(x + 284, 576 + j * 31, value, 21, "ink", anchor="middle", maxw=460)
        if special == "items":
            for dx, name in [(26, "dim_product"), (298, "dim_seller")]:
                d.rect(x + dx, 711, 244, 61, C["teal_bg"], radius=10)
                d.text(x + dx + 122, 750, name, 23, "teal", True, "middle", 232)
                d.line([(x + dx + 122, 711), (x + dx + 122, 677), (x + 284, 677), (x + 284, 640)], "teal", 2, True)
        elif special == "payments":
            d.rect(x + 114, 711, 340, 61, C["teal_bg"], radius=10)
            d.text(x + 284, 750, "dim_payment_method", 23, "teal", True, "middle", 316)
            d.line([(x + 284, 711), (x + 284, 640)], "teal", 2, True)
            d.text(x + 26, 808, "* Installments không phải measure cộng dồn.", 18, "muted", maxw=516)
        else:
            d.para(x + 26, 694, "Date roles: purchase, approved, carrier, delivered, estimated.", 516, 23)
            d.para(x + 26, 774, "Ngày thiếu: key 0, timestamp null.", 516, 22)
    d.note(72, 859, 856, 121, "KHÓA VÀ LỊCH SỬ", "Registry cấp integer SK; Unknown = 0; N/A = -1; inferred giữ nguyên key khi bổ sung thuộc tính.", "blue", 23)
    d.note(960, 859, 888, 121, "RANH GIỚI CHÍNH XÁC", "FK cùng release_id; không fact-to-fact join. Olist Type 0/1; Type 2 kiểm tra bằng fixture có effectivity.", "teal", 23)
    result.append(d.finish())

    d = Canvas(6, "06-airflow-pipeline-and-recovery", "Pipeline: mỗi bước có trách nhiệm và điểm kiểm soát",
               "Luồng logic dự kiến do Airflow điều phối; không phải ảnh chụp DAG đã triển khai.",
               ["specs/spec-package/02-architecture/production-local.md", "contracts/operational-scenarios.json", "contracts/state-machines.json"],
               "Trình bày happy path, sau đó chỉ vào đường lỗi. Lỗi schema hoặc business invariant không được retry mù hay đánh dấu thành công. "
               "Raw/object storage và load DB không phải một distributed transaction. Receipt, batch, source cut và release là các identity khác nhau. "
               "Chứng minh sau triển khai: replay không tăng business rows, model checkpoint chỉ tiến khi thành công và failed tasks không bị notification che khuất.")
    xs = [72, 438, 804, 1170, 1536]
    stages = [
        ("01", "Kiểm tra nguồn", ["File, hash, manifest", "Đúng contract version"]),
        ("02", "Giữ raw + receipt", ["Immutable object", "Audit mọi lần nhận"]),
        ("03", "Validate / admit", ["Schema, key, version", "Quarantine nếu sai"]),
        ("04", "Load transaction", ["Append source versions", "Batch state + ledger"]),
        ("05", "Lease + source cut", ["Owner, fence, heartbeat", "Một cut cho mọi model"]),
    ]
    for x, (k, title, body) in zip(xs, stages):
        d.card(x, 239, 312, 239, title, body, "blue", k, 21, 25)
    for x in xs[:-1]:
        d.line([(x + 318, 357), (x + 358, 357)], "blue", arrow=True)
    # The lower row returns right to left, preserving one readable continuous path.
    below = [
        ("10", "Bàn giao / audit", ["Pin BI release_id", "Ghi trạng thái thực"]),
        ("09", "Publish atomically", ["Mọi gate phải đạt", "Pointer + release state"]),
        ("08", "Semantic + parity", ["Bind candidate release", "Exports + đối soát SQL"]),
        ("07", "Freeze Warehouse", ["7 dims + 3 facts", "Same-release FK gates"]),
        ("06", "dbt build / tests", ["Dims, facts, marts", "Checkpoint từng model"]),
    ]
    d.line([(1692, 478), (1692, 531)], "blue", arrow=True)
    for x, (k, title, body) in zip(xs, below):
        d.card(x, 532, 312, 239, title, body, "purple" if k in {"06", "07", "08"} else "teal", k, 21, 25)
    for x in xs[1:]:
        d.line([(x - 6, 650), (x - 45, 650)], "teal", arrow=True)
    d.note(72, 811, 856, 158, "KHI LỖI Ở BẤT KỲ BƯỚC NÀO", "Giữ bản published trước; log + failed state; không promote candidate lỗi. Chẩn đoán rồi retry/resume đúng batch/cut.", "red", 24)
    d.note(960, 811, 888, 158, "CHẠY LẠI AN TOÀN", "Same revision + hash → no-op nghiệp vụ. Receipt vẫn được audit. Source conflict → quarantine; stale fence → từ chối publish.", "teal", 24)
    result.append(d.finish())

    d = Canvas(7, "07-semantic-layer-and-correct-metrics", "Semantic Layer: định nghĩa một lần, tính đúng grain",
               "Ví dụ AOV: tổng giá trị hàng delivered / số đơn delivered, không lấy trung bình các AOV con.",
               ["specs/spec-package/03-data/semantic-and-metrics.md", "contracts/metric-catalog.json", "tests/fixtures/kimball/expected.json"],
               "Hai fact không join nguyên tử. Từng fact được aggregate theo purchase period và buyer state, rồi drill-across ở cùng grain. "
               "Ví dụ nhỏ là fixture tổng hợp, không phải số liệu Olist: một đơn có hai item tổng 150 và hai payment; join chéo thành 300. "
               "Metabase nhận kết quả từ MetricFlow exports. Distinct phải query tại đúng kỳ; order-level AOV không được group product/seller theo hợp đồng hiện tại.")
    d.card(72, 232, 456, 170, "fct_order_items", ["SUM(price), status = delivered"], "blue", size=22)
    d.card(72, 456, 456, 170, "fct_orders", ["SUM(delivered_order_count)"], "blue", size=21)
    d.card(596, 232, 534, 170, "Aggregate tại grain chung", ["purchase month + buyer state"], "purple", size=23)
    d.card(596, 456, 534, 170, "Aggregate tại grain chung", ["purchase month + buyer state"], "purple", size=23)
    for y in (317, 541):
        d.line([(536, y), (584, y)], "blue", arrow=True)
    d.line([(1140, 317), (1171, 317), (1171, 428), (1201, 428)], "purple", arrow=True)
    d.line([(1140, 541), (1171, 541), (1171, 428), (1201, 428)], "purple", arrow=True)
    d.card(1212, 282, 636, 290, "Drill-across → metric", ["Join kết quả đã aggregate, không join fact rows", "AOV = tổng tử số / tổng mẫu số", "Mẫu số 0 → null; làm tròn khi hiển thị"], "teal", "METRICFLOW", 23)
    d.line([(1530, 572), (1530, 639)], "teal", arrow=True)
    d.rect(1212, 647, 636, 110, C["teal_bg"])
    d.text(1240, 689, "5 VERSIONED EXPORTS → METABASE", 23, "teal", True, maxw=580)
    d.text(1240, 731, "KPI chung; không viết lại công thức từng chart", 22, maxw=580)
    d.note(72, 671, 1058, 155, "VÍ DỤ TỔNG HỢP: JOIN NHÂN SỐ LIỆU", "1 đơn × 2 item × 2 payment: tổng item đúng = 150; join chéo ra 300. Giữ nguyên grain và aggregate riêng để loại fanout.", "red", 24)
    d.note(72, 851, 1058, 127, "DIMENSION PHẢI PHÙ HỢP METRIC", "Item metrics dùng category/seller. AOV và tổng đơn chỉ dùng dimension chung theo hợp đồng; không tự phân bổ xuống item.", "blue", 23)
    d.note(1212, 795, 636, 183, "DISTINCT KHÔNG CỘNG DỒN", "Khách xuất hiện nhiều ngày/bang vẫn là một khách ở tổng kỳ. Query trực tiếp tại đúng period/group; không SUM các distinct con.", "amber", 23)
    result.append(d.finish())

    d = Canvas(8, "08-release-publication-and-isolation", "Không để pipeline chạy dở làm sai báo cáo",
               "Một release gắn cả dimensions, facts và metric exports; dữ liệu candidate chưa được BI nhìn thấy.",
               ["specs/spec-package/02-architecture/production-local.md", "contracts/release.schema.json", "contracts/dashboard-contract.json"],
               "Dùng R0 và R1 làm nhãn release minh họa. R0 tiếp tục phục vụ trong lúc R1 được build và kiểm tra. "
               "MetricFlow phải bind R1 trên mọi connection; thiếu binding thì fail closed. "
               "Publish đổi pointer bằng giao dịch DB dưới lease fence. Browser ghim một release cho tất cả card để tránh chart A đọc R0 và chart B đọc R1. "
               "Metabase API không nằm trong giao dịch PostgreSQL; delivery lag được theo dõi riêng. Chưa có chứng cứ runtime cho các cơ chế này.")
    d.pill(72, 213, "CANDIDATE PATH  /  R1 LÀ VÍ DỤ", "purple")
    cards = [
        (72, "Chốt source_cut", ["Nguồn và version cố định", "Working build + DQ gates"]),
        (528, "Freeze snapshot R1", ["7 dims + 3 facts bất biến", "PK / grain / same-release FK"]),
        (984, "MetricFlow bind R1", ["5 exports cùng release", "SQL / semantic parity đạt"]),
        (1440, "Fenced publication", ["Kiểm tra owner + fence", "DB transaction: publish + pointer"]),
    ]
    for x, title, body in cards:
        d.card(x, 273, 408, 235, title, body, "purple", size=22)
    for x in (480, 936, 1392):
        d.line([(x + 7, 389), (x + 42, 389)], "purple", arrow=True)
    d.rect(72, 560, 1776, 149, C["teal_bg"])
    d.text(100, 605, "CONSUMER PATH", 22, "teal", True)
    d.text(100, 651, "R0 vẫn phục vụ trong khi R1 được kiểm tra", 29, bold=True, maxw=840)
    d.line([(953, 640), (1030, 640)], "teal", arrow=True)
    d.text(1060, 624, "Sau publish: link mới pin R1", 28, "teal", True, maxw=740)
    d.text(1060, 670, "Mọi card cùng release_id; link R0 còn hợp lệ khi được giữ lại", 22, maxw=740)
    d.line([(1644, 508), (1644, 547)], "teal", arrow=True)
    d.note(72, 753, 556, 216, "R1 LỖI / EXPORT THIẾU", "Không đổi pointer. Giữ R0. Candidate + logs còn để chẩn đoán và chạy lại có kiểm soát.", "red", 24)
    d.note(682, 753, 556, 216, "STALE OWNER / ACK BỊ MẤT", "Fence hết hạn không được publish. Mất ACK sau commit: tra release đã publish, không giả định rollback.", "amber", 24)
    d.note(1292, 753, 556, 216, "RANH GIỚI GIAO DỊCH", "Atomic trong PostgreSQL. Metabase link/API là bước bàn giao riêng; lỗi bàn giao ghi nhận delivery lag.", "blue", 24)
    result.append(d.finish())

    d = Canvas(9, "09-evidence-operations-and-success", "Đầu ra phải có bằng chứng, không chỉ có sơ đồ",
               "Tách ba lớp: đã kiểm chứng offline • gate runtime phải chạy sau • mục tiêu vận hành phải đo.",
               ["docs/evidence/README.md", "docs/evidence/design-contracts.json", "docs/evidence/semantic-probe.json", "specs/spec-package/08-operations/operating-model.md"],
               "Kết thúc bằng trạng thái trung thực: 137 checks là kiểm tra thiết kế, không phải 137 kiểm thử hệ thống. "
               "Năm semantic checks hiện tại không kết nối database. 22 kịch bản vận hành đã được đặc tả, chưa chạy. "
               "RPO/RTO và thời gian pipeline là mục tiêu trên một host khỏe, không phải SLA đã đo; backup cùng máy không bảo vệ mất host. "
               "Khi demo sau triển khai, chạy một happy path, một replay và một failure recovery rồi trình bày output + evidence.")
    d.card(72, 230, 856, 423, "Đã có bằng chứng thật", [
        "Nguồn đã tải + checksum + profile", "451.535 dòng đã kiểm tra source contracts", "137 kiểm tra thiết kế / fixture / DDL tĩnh",
        "5 semantic checks offline, không kết nối DB", "20 requirements + 20 work items có traceability"], "teal", "CURRENT / OFFLINE", 25)
    d.card(960, 230, 888, 423, "Phải chứng minh khi triển khai", [
        "Docker boot + controlled migration + dữ liệu vào DB", "MetricFlow thực thi thật, source / SQL / KPI parity", "Replay, failure recovery, concurrent publication",
        "3 dashboard pin release + quyền truy cập đúng", "22 scenario đã đặc tả; restore drill có đo thời gian"], "amber", "PLANNED / RUNTIME GATES", 24)
    targets = [
        (72, "≤ 10 phút", "Batch accepted → published"),
        (528, "p95 ≤ 5 giây", "Query dashboard • 1-2 người xem"),
        (984, "RPO ≤ 24 giờ", "Logical failure; backup + raw"),
        (1440, "RTO ≤ 30 phút", "Restore trên host khỏe"),
    ]
    d.text(72, 707, "MỤC TIÊU THIẾT KẾ - CHƯA PHẢI KẾT QUẢ ĐÃ ĐO", 23, "blue", True)
    for x, value, label in targets:
        d.rect(x, 735, 408, 132, C["paper"], C["line"])
        d.text(x + 24, 783, value, 31, "blue", True, maxw=360)
        d.para(x + 24, 825, label, 360, 21, gap=28)
    d.note(72, 897, 1776, 82, "GIỚI HẠN VẬN HÀNH", "", "blue")
    d.text(482, 947, "<70 GB toàn bộ footprint • Một máy, không HA • Backup cùng host không bảo vệ mất host", 24, maxw=1318)
    result.append(d.finish())
    return result


def gallery(slides):
    figures = []
    for row in slides:
        figures.append(
            f'<section id="{row["slug"]}" class="slide"><img src="{row["svg"]}" '
            f'alt="{escape(row["title"])}" width="1920" height="1080">'
            f'<div class="notes"><h2>{row["number"]:02d}. {escape(row["title"])}</h2>'
            f'<p>{escape(row["speaker_notes"])}</p><p><a href="{row["png"]}">PNG 4K</a> · '
            f'<a href="{row["svg"]}">SVG vector</a></p></div></section>'
        )
    value = '''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sales Warehouse - Architecture &amp; Design</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#e7edf5;color:#15283e;font-family:"DejaVu Sans",sans-serif}
header,main{max-width:1440px;margin:auto}header{padding:32px 24px}h1{font-size:28px;margin:0 0 14px}
p{line-height:1.65}header p{max-width:1050px}a{color:#2458b5}nav{display:flex;flex-wrap:wrap;gap:14px}
button{font:inherit;border:1px solid #52647b;background:white;border-radius:6px;padding:10px 16px;cursor:pointer}
main{padding:0 24px 40px}.slide{margin-bottom:36px;scroll-margin-top:15px;background:white;box-shadow:0 4px 24px #15283e12}
.slide img{display:block;width:100%;height:auto}.notes{padding:4px 28px 22px}.notes h2{font-size:20px}
body.presenting header,body.presenting .notes{display:none}body.presenting main{max-width:none;padding:0}
body.presenting .slide{margin:0;box-shadow:none;background:#f4f7fb;min-height:100vh;display:flex;align-items:center;justify-content:center}
body.presenting .slide img{max-height:100vh;width:100%;object-fit:contain}
@media(max-width:600px){header,main{padding-left:12px;padding-right:12px}.notes{padding:4px 16px 16px}h1{font-size:23px}}
@page{size:1920px 1080px;margin:0}
@media print{body{background:white}header,.notes{display:none!important}main{max-width:none;padding:0!important}
.slide,body.presenting .slide{width:1920px;height:1080px;min-height:0;margin:0;box-shadow:none;break-after:page;display:block}
.slide:last-child{break-after:auto}.slide img{width:1920px;height:1080px;max-height:none!important}}
</style></head><body><header><h1>Sales &amp; Customer Analytics Warehouse</h1>
<p>9 sơ đồ theo specs đã chốt. Đây là thiết kế portfolio trên một host, không phải kiến trúc nội bộ Abbott/Concentrix.
Nguồn Olist thật; Warehouse, pipeline và dashboard chưa nghiệm thu runtime.</p>
<nav><button id="present" type="button">Chế độ trình bày</button><button id="print" type="button">In / lưu PDF</button>
<a href="../../output/pdf/project-architecture.pdf">PDF 9 trang</a><a href="README.md">Hướng dẫn &amp; ghi chú</a></nav>
<p>Dùng phím trái/phải để chuyển hình, Esc để thoát chế độ trình bày.</p></header><main>'''
    value += "\n".join(figures)
    value += '''</main><script>
const slides=[...document.querySelectorAll('.slide')];let current=0;
function go(n){current=Math.max(0,Math.min(slides.length-1,n));slides[current].scrollIntoView({behavior:'instant',block:'start'});}
document.getElementById('present').addEventListener('click',()=>{document.body.classList.add('presenting');go(0)});
document.getElementById('print').addEventListener('click',()=>window.print());
document.addEventListener('keydown',e=>{if(!document.body.classList.contains('presenting'))return;
if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();go(current+1)}
if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();go(current-1)}
if(e.key==='Escape'){document.body.classList.remove('presenting');go(current)}});
</script></body></html>'''
    (OUT / "index.html").write_text(value, encoding="utf-8")


def render(slides, scale):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("Chrome/Chromium required; no browser download is performed")
    checks, problems = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=scale)
        context.route("http://**/*", lambda route: route.abort())
        context.route("https://**/*", lambda route: route.abort())
        page = context.new_page()
        for row in slides:
            page.goto((OUT / row["svg"]).as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            overflow = page.locator("svg text").evaluate_all('''els=>els.flatMap(e=>{
              const b=e.getBBox(),w=Number(e.dataset.maxWidth);const reasons=[];
              if(b.width>w+2)reasons.push('label-width');
              if(b.x<0||b.y<0||b.x+b.width>1920||b.y+b.height>1080)reasons.push('canvas-bounds');
              return reasons.length?[{text:e.textContent,reasons,bbox:{x:b.x,y:b.y,width:b.width,height:b.height},allowedWidth:w}]:[]
            })''')
            if overflow:
                problems.append({"slide": row["slug"], "overflow": overflow})
            # Screenshot the root SVG, not a rescaled browser-document image.
            page.locator("svg").screenshot(path=str(OUT / row["png"]))
            image = Image.open(OUT / row["png"])
            assert image.size == (int(W * scale), int(H * scale)), image.size
            checks.append({"slide": row["slug"], "labels": page.locator("svg text").count(),
                           "text_overflow": overflow, "png_dimensions": list(image.size)})
        page.goto((OUT / "index.html").as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        assert page.locator(".slide img").evaluate_all("els=>els.every(e=>e.complete && e.naturalWidth>0)")
        page.get_by_role("button", name="Chế độ trình bày").click()
        page.keyboard.press("ArrowRight")
        assert page.evaluate("current") == 1
        page.keyboard.press("Escape")
        assert not page.locator("body").evaluate("e=>e.classList.contains('presenting')")
        PDF.parent.mkdir(parents=True, exist_ok=True)
        page.pdf(path=str(PDF), width="1920px", height="1080px", print_background=True, prefer_css_page_size=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile gallery overflow"
        browser_version = browser.version
        browser.close()
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        raise RuntimeError("Poppler pdfinfo is required for PDF page-count and size verification")
    pdf_metadata = subprocess.run([pdfinfo, str(PDF)], capture_output=True, text=True, check=True).stdout
    page_count = int(re.search(r"^Pages:\s+(\d+)$", pdf_metadata, re.MULTILINE)[1])
    page_size = re.search(r"^Page size:\s+([\d.]+) x ([\d.]+) pts", pdf_metadata, re.MULTILINE)
    assert page_count == len(slides), (page_count, len(slides))
    assert tuple(float(page_size[i]) for i in (1, 2)) == (1440, 810)
    # A review sheet is only a QA aid; full-resolution PNGs are the deliverables.
    thumbs = Image.new("RGB", (1440, 3 * 320), "#e7edf5")
    for i, row in enumerate(slides):
        im = Image.open(OUT / row["png"]).convert("RGB")
        im.thumbnail((464, 261), Image.Resampling.LANCZOS)
        x, y = (i % 3) * 480 + 8, (i // 3) * 320 + 8
        thumbs.paste(im, (x, y))
        ImageDraw.Draw(thumbs).text((x + 4, y + 269), f'{i+1:02d}  {row["slug"][3:]}', fill="#15283e", font=font(15))
    thumbs.save(OUT / "contact-sheet.png")
    evidence = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "Diagram export/label bounds, file render and presentation controls only. Not system runtime proof.",
                "slide_count": len(slides), "source_rows_in_scope": 451535,
                "tooling": {"chrome": browser_version, "pillow": importlib.metadata.version("pillow"),
                            "playwright": importlib.metadata.version("playwright")},
                "checks": checks, "gallery_controls_passed": True, "mobile_gallery_no_overflow": True,
                "pdf": str(PDF.relative_to(ROOT)), "pdf_pages": page_count,
                "pdf_page_points": [1440, 810], "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
                "passed": not problems, "issues": problems}
    (OUT / "visual-verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"slides": len(slides), "png_size": f"{int(W*scale)}x{int(H*scale)}", "passed": not problems, "issues": problems}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=float, default=2, help="2 produces 3840x2160 PNGs")
    args = parser.parse_args()
    for folder in (OUT, OUT / "svg", OUT / "png"):
        folder.mkdir(parents=True, exist_ok=True)
    slides = diagrams()
    (OUT / "manifest.json").write_text(json.dumps({"design_baseline": "2.0.0", "slides": slides}, ensure_ascii=False, indent=2) + "\n")
    gallery(slides)
    render(slides, args.scale)


if __name__ == "__main__":
    main()
