"""Question-driven charts. Definitions are shared by bootstrap and verification."""
from superset_narratives import NARRATIVE_COLUMNS, NARRATIVE_SOURCES
from superset_navigation import MONTHLY_BOARDS, NAVIGATION_COLUMNS, NAVIGATION_SOURCES
from superset_presentation import PAGES

MONTH = '2018-07-01'
BOARDS = [
    ('overview', '00 · Executive Overview', 'Kinh doanh đang thế nào — cần xem sâu ở đâu?',
     'Tổng quan điều hành: quy mô và thay đổi bán hàng, danh mục/khu vực đóng góp, giao hàng và độ tin cậy. Chọn tháng rồi dùng menu để mở báo cáo chuyên sâu; không gộp các cửa sổ phân tích khác nhau thành một KPI.'),
    ('sales', '01 · Sales Overview', 'Doanh số giao thành công đang ở mức nào, thay đổi ra sao?',
     'Chọn một tháng cho KPI. Xu hướng hiển thị 01/2017–08/2018; kỳ cuối có thể chưa đầy đủ. Giá trị hàng chưa gồm freight; trạng thái là snapshot đã chấp nhận, không phải lịch sử tại ngày mua.'),
    ('commercial', '02 · Products & Sellers', 'Danh mục, người bán và khu vực nào đóng góp nhiều nhất?',
     'Phân tích ở grain dòng hàng. Category có thật từ nguồn; seller hiển thị mã ẩn danh. Không suy ra tên sản phẩm, lợi nhuận hoặc AOV cấp sản phẩm.'),
    ('customers', '03 · Customer Behavior', 'Khách hàng mua lại bao nhiêu, cohort nào còn quay lại?',
     'Toàn kỳ quan sát đến 31/08/2018. Cohort = tháng mua delivered đầu tiên được quan sát; repeat = ít nhất 2 đơn delivered. Không xem khách mua 1 lần là churn. Ô cohort tương lai để trống.'),
    ('service', '04 · Delivery & Payments', 'Giao hàng có đúng hẹn không, mất bao lâu, thanh toán bằng cách nào?',
     'Tỷ lệ đúng hẹn chỉ dùng đơn đủ ngày hợp lệ. Payment amount/record không phải doanh thu hay số đơn; một đơn có thể có nhiều payment records. Các số đo được phân loại theo tháng mua.'),
    ('trust', '05 · Data Trust & Pipeline', 'Số liệu có đáng tin và bản dữ liệu nào đang phục vụ báo cáo?',
     'Business datasets pin một published release. Cảnh báo nguồn được giữ và giải thích; lỗi pipeline phải chặn publication. Lịch sử run là operational audit live, không phải trạng thái đơn hàng.'),
]
BOARDS = [(board, PAGES[board]['title'], question, note) for board,title,question,note in BOARDS]

SOURCES = {
 'monthly': 'reporting.validated_sales_monthly', 'daily': 'reporting.validated_sales_daily',
 'products': 'reporting.validated_product_monthly', 'sellers': 'reporting.validated_seller_monthly',
 'states': 'reporting.validated_buyer_state_monthly', 'orders': 'reporting.analytic_orders',
 'payments': 'reporting.analytic_payments', 'customers': 'reporting.analytic_customers',
 'cohorts': 'reporting.analytic_cohorts', 'quality': 'reporting.quality_health',
 'producer': 'reporting.pipeline_health', 'attempts': 'reporting.pipeline_health',
 'release': 'reporting.release_metadata',
 'product_mix': 'reporting.validated_product_monthly',
 'growth': 'reporting.validated_sales_monthly',
}
SOURCES.update(NARRATIVE_SOURCES)
SOURCES.update(NAVIGATION_SOURCES)


def c(board, key, title, source, viz, expression=None, x=None, **kwargs):
    return dict(board=board, key=key, title=title, source=source, viz=viz, expression=expression, x=x, **kwargs)


CHARTS = [
 c('sales','value','Delivered merchandise · BRL','monthly','big_number_total','CASE WHEN count(*)=1 THEN max(delivered_merchandise_value) END',month=True,fmt=',.2f'),
 c('sales','orders','Delivered orders','monthly','big_number_total','CASE WHEN count(*)=1 THEN max(delivered_orders) END',month=True),
 c('sales','customers','Distinct delivered customers','monthly','big_number_total','CASE WHEN count(*)=1 THEN max(delivered_unique_customers) END',month=True),
 c('sales','aov','Delivered AOV · BRL/order','monthly','big_number_total','CASE WHEN count(*)=1 THEN max(delivered_aov) END',month=True,fmt=',.2f'),
 c('sales','cancellation','Cancellation rate','monthly','big_number_total','CASE WHEN count(*)=1 THEN max(cancellation_rate) END',month=True,fmt='.2%'),
 c('sales','mom','Merchandise change · vs previous month','growth','big_number_total','CASE WHEN count(*)=1 THEN max(value_mom) END',month=True,fmt='+.2%'),
 c('sales','yoy','Merchandise change · vs same month last year','growth','big_number_total','CASE WHEN count(*)=1 THEN max(value_yoy) END',month=True,fmt='+.2%'),
 c('sales','value_trend','Monthly delivered merchandise · 2017–Aug 2018','monthly','echarts_timeseries_line','SUM(delivered_merchandise_value)','purchase_month',sort_x=True,fixed_filters=[{'col':'purchase_month','op':'>=','val':'2017-01-01'},{'col':'purchase_month','op':'<','val':'2018-09-01'}]),
 c('sales','orders_trend','Monthly delivered orders · 2017–Aug 2018','monthly','echarts_timeseries_bar','SUM(delivered_orders)','purchase_month',sort_x=True,fixed_filters=[{'col':'purchase_month','op':'>=','val':'2017-01-01'},{'col':'purchase_month','op':'<','val':'2018-09-01'}]),
 c('sales','daily','Daily delivered merchandise · selected month','daily','echarts_timeseries_line','SUM(delivered_merchandise_value)','day_label',month=True,sort_x=True),
 c('commercial','category','Top 10 categories · merchandise value','products','echarts_timeseries_bar','SUM(delivered_merchandise_value)','category',month=True,limit=10,horizontal=True),
 c('commercial','seller','Top 10 sellers · merchandise value','sellers','table','SUM(delivered_merchandise_value)','seller_id',month=True,limit=10),
 c('commercial','state','Buyer state · merchandise value','states','echarts_timeseries_bar','SUM(delivered_merchandise_value)','state',month=True,limit=12,horizontal=True),
 c('commercial','category_items','Top 10 categories · delivered item rows','products','echarts_timeseries_bar','SUM(delivered_item_rows)','category',month=True,limit=10,horizontal=True),
 c('commercial','category_mix','Category contribution · top 5 + others','product_mix','pie','SUM(delivered_merchandise_value)','category',month=True,limit=6),
 c('commercial','state_aov','Delivered AOV by buyer state · BRL/order','states','echarts_timeseries_bar','SUM(delivered_merchandise_value)/NULLIF(SUM(delivered_orders),0)','state',month=True,limit=12,horizontal=True,fmt=',.2f'),
 c('customers','observed','Observed delivered customers','customers','big_number_total','COUNT(*)'),
 c('customers','repeat','Repeat customer share','customers','big_number_total','COUNT(*) FILTER(WHERE delivered_orders>=2)::numeric/NULLIF(COUNT(*),0)',fmt='.2%'),
 c('customers','repeat_value','Merchandise share from repeat customers','customers','big_number_total','SUM(observed_merchandise_value) FILTER(WHERE delivered_orders>=2)/NULLIF(SUM(observed_merchandise_value),0)',fmt='.2%'),
 c('customers','frequency','Observed delivered-order frequency','customers','echarts_timeseries_bar','COUNT(*)','frequency_segment',sort_x=True),
 c('customers','recency','Recency at 31 Aug 2018 · customers','customers','echarts_timeseries_bar','COUNT(*)','recency_segment',sort_x=True),
 c('customers','cohort','Return by cohort · months 1–6 (month 0 = 100%)','cohorts','heatmap_v2','MAX(observed_retention)','month_offset',y='cohort_label',fmt='.2%',fixed_filters=[{'col':'month_offset','op':'>','val':0},{'col':'cohort_label','op':'>=','val':'2017-01-01'}]),
 c('customers','retention','Observed return rate · months 1–6, eligible cohorts','cohorts','echarts_timeseries_line','SUM(active_customers)::numeric/NULLIF(SUM(cohort_size),0)','month_offset',sort_x=True,fmt='.2%',fixed_filters=[{'col':'month_offset','op':'>','val':0},{'col':'cohort_label','op':'>=','val':'2017-01-01'}]),
 c('service','ontime','On-time delivery · eligible orders','orders','big_number_total','SUM(on_time_delivery_count)::numeric/NULLIF(SUM(known_delivery_date_count),0)',month=True,fmt='.2%'),
 c('service','median_days','Median delivery · days','orders','big_number_total','percentile_cont(0.5) WITHIN GROUP(ORDER BY delivery_days) FILTER(WHERE known_delivery_date_count=1)',month=True,fmt=',.1f'),
 c('service','known','Eligible delivery observations','orders','big_number_total','SUM(known_delivery_date_count)',month=True),
 c('service','status','Accepted order status · orders','orders','pie','SUM(order_count)','order_status',month=True),
 c('service','state_days','Average delivery days · buyer states','orders','echarts_timeseries_bar','AVG(delivery_days) FILTER(WHERE known_delivery_date_count=1)','buyer_state',month=True,limit=15,horizontal=True,fmt=',.1f'),
 c('service','payment_method','Recorded payment amount by method · BRL','payments','pie','SUM(recorded_payment_value)','payment_method',month=True),
 c('service','installments','Installments · payment records','payments','echarts_timeseries_bar','SUM(payment_record_count)','payment_installments',month=True,sort_x=True),
 c('trust','producer','Producer run · publication context','producer','table',raw=['state','source_cut','started_at','finished_at','pipeline_run_id']),
 c('trust','publication','Published release · provenance','release','table',raw=['published_at','source_cut','model_version','release_id']),
 c('trust','warnings','Source warnings · affected occurrences','quality','echarts_timeseries_bar','SUM(affected_records)','rule_id',horizontal=True),
 c('trust','errors','Quality error occurrences · producer run','quality','big_number_total',"COALESCE(SUM(affected_records) FILTER(WHERE severity='error'),0)"),
 c('trust','attempts','Pipeline attempts · operational audit','attempts','echarts_timeseries_bar','COUNT(*)','state'),
 c('trust','history','Recent pipeline runs · operational audit','attempts','table',raw=['state','started_at','finished_at','error_category','pipeline_run_id'],limit=12),
]

OVERVIEW_KEYS = {
    'sales': ['value', 'orders', 'customers', 'aov', 'mom', 'cancellation', 'value_trend', 'orders_trend'],
    'commercial': ['category', 'state'],
    'service': ['ontime', 'median_days'],
}
OVERVIEW_TITLES = {
    'value': 'Giá trị hàng đã giao · BRL', 'orders': 'Đơn hàng đã giao',
    'customers': 'Khách mua hàng · phân biệt', 'aov': 'Giá trị bình quân đơn · BRL',
    'mom': 'Thay đổi giá trị · so tháng trước', 'cancellation': 'Tỷ lệ đơn hủy',
    'ontime': 'Giao đúng hẹn · đơn đủ điều kiện', 'median_days': 'Trung vị giao hàng · ngày',
    'value_trend': 'Xu hướng giá trị hàng · 2017–08/2018',
    'orders_trend': 'Xu hướng đơn đã giao · 2017–08/2018',
    'category': 'Danh mục dẫn đầu · giá trị hàng', 'state': 'Địa bàn người mua · giá trị hàng',
}
CHARTS.extend(dict(chart, board='overview', title=OVERVIEW_TITLES[chart['key']]) for chart in list(CHARTS)
              if chart['key'] in OVERVIEW_KEYS.get(chart['board'], []))

CHARTS.extend(
    c(board, 'insights', 'Điểm nhấn',
      f'insights_{board}_v3', 'table', x='business_question', raw=NARRATIVE_COLUMNS,
      narrative=True, month=board in MONTHLY_BOARDS, sort_x=True, limit=100)
    for board,title,_,_ in BOARDS
)

CHARTS.extend(
    c(board, 'navigation', 'Báo cáo',
      f'navigation_{board}_v2', 'table', raw=NAVIGATION_COLUMNS,
      navigation=True, month=True, limit=100)
    for board,_,_,_ in BOARDS
)
