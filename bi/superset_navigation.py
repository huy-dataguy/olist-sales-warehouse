"""Release/month-bound navigation. No Javascript or arbitrary HTML from source data."""
from datetime import date
from html import escape
from urllib.parse import quote
from uuid import UUID

DESTINATIONS = {
    'overview': ('Tổng quan', 'Tổng quan kinh doanh'),
    'sales': ('Bán hàng', 'Hiệu quả bán hàng'),
    'commercial': ('Sản phẩm & seller', 'Sản phẩm và nhà bán hàng'),
    'customers': ('Khách hàng', 'Khách hàng và mua lại'),
    'service': ('Giao & thanh toán', 'Giao hàng và thanh toán'),
    'trust': ('Chất lượng dữ liệu', 'Chất lượng dữ liệu và vận hành'),
}
MONTHLY_BOARDS = {'overview', 'sales', 'commercial', 'service'}
NAVIGATION_COLUMNS = ['nav_' + board for board in DESTINATIONS]
NAVIGATION_SOURCES = {'navigation_' + board + '_v2': 'reporting.validated_sales_monthly'
                      for board in DESTINATIONS}


def filter_id(board):
    if board not in DESTINATIONS:
        raise ValueError('Unknown dashboard')
    return 'NATIVE_FILTER-month-' + board


def dashboard_path(board, release_id, month=None):
    """Superset 6.1 native_filters Rison URL, with a strict identifier/date boundary."""
    key = filter_id(board)
    rid = str(UUID(str(release_id)))
    path = f'/superset/dashboard/olist-{board}-{rid[:8]}/'
    if month is None:
        return path
    if month != '__MONTH__':
        parsed = date.fromisoformat(month)
        if parsed.day != 1 or parsed.isoformat() != month:
            raise ValueError('A navigation month must be an ISO month-start date')
    value = (f"({key}:(extraFormData:(filters:!((col:purchase_month,op:IN,val:!('{month}')))),"
             f"filterState:(label:'{month}',value:!('{month}')),id:{key},ownState:()))")
    return path + '?native_filters=' + quote(value, safe='')


def navigation_sql(board, release_id):
    filter_id(board)
    rid = str(UUID(str(release_id)))
    columns = []
    for target, (title, description) in DESTINATIONS.items():
        href = dashboard_path(target, rid, '__MONTH__')
        active = ' aria-current="page"' if target == board else ''
        anchor = f'<a href="{escape(href, quote=True)}" title="{escape(description, quote=True)}"{active}>{escape(title)}</a>'
        # Only the date originates in the read model, formatted by PostgreSQL;
        # no customer/category text, user SQL or markup is interpolated here.
        literal = anchor.replace("'", "''")
        columns.append(f"replace('{literal}','__MONTH__',to_char(month,'YYYY-MM-DD')) AS nav_{target}")
    return ("SELECT release_id,month::text AS purchase_month," + ','.join(columns)
            + f" FROM reporting.validated_sales_monthly WHERE release_id='{rid}'")


DASHBOARD_CSS = """
.dashboard-content {background:#f2f5fa;}
.dashboard-component-chart-holder {border-radius:12px; border:1px solid #e0e7ef;
  box-shadow:0 2px 8px #18354a0a;}
.dashboard-markdown {color:#354b60; font-size:14px; line-height:1.65;}
.dashboard-markdown h2,.dashboard-markdown h3 {color:#14364b; letter-spacing:-.3px;}
.dashboard-markdown a {color:#007f86; font-weight:600;}
.dashboard-component-chart-holder td a[href*="/superset/dashboard/olist-"] {
  display:block; padding:6px 8px; border-radius:7px; text-align:center;
  color:#31576b; background:#f2f6f9; border:1px solid #dce6ed;
  font-size:13px; font-weight:650; line-height:1.4; text-decoration:none; white-space:normal;}
.dashboard-component-chart-holder td a[aria-current="page"] {
  color:#fff; background:#086b74; border-color:#086b74;}
.dashboard-component-chart-holder td a[href*="/superset/dashboard/olist-"]:hover {
  background:#c9e9e6; color:#113b46;}
.dashboard-component-chart-holder td a[href*="/superset/dashboard/olist-"]:focus-visible {
  outline:3px solid #e2a446; outline-offset:2px;}
.dashboard-component-chart-holder:has(a[href*="/superset/dashboard/olist-"]) [data-test="slice-header"] {display:none;}
/* Superset's sticky-table sizer requires a nonzero THEAD height. Keep a
   one-pixel measurement row instead of display:none (which hides the body). */
.dashboard-component-chart-holder:has(a[href*="/superset/dashboard/olist-"]) thead {
  height:1px; opacity:0; pointer-events:none;}
.dashboard-component-chart-holder:has(a[href*="/superset/dashboard/olist-"]) thead th {
  height:1px; padding:0 8px; border:0; font-size:1px; line-height:1px;}
.dashboard-component-chart-holder:has(a[href*="/superset/dashboard/olist-"]) thead th > div {
  height:1px; min-height:0; overflow:hidden; line-height:1px;}
.dashboard-component-chart-holder:has(a[href*="/superset/dashboard/olist-"]) td {
  background:transparent; border:0; padding:3px 5px;}
.dashboard-component-chart-holder:has(a[href*="/superset/dashboard/olist-"]) {
  border:0; box-shadow:none; background:transparent;}
"""
