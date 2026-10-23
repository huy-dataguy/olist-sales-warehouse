"""Deterministic, query-backed dashboard commentary; no generated business facts.

Monthly narratives have one row per question/month, so the native month filter
selects the findings as well as the charts. Fixed-window narratives state their
cutoff. Joins below are between aggregated read models, never atomic facts.
"""
from uuid import UUID

NARRATIVE_COLUMNS = ['analysis_scope', 'business_question', 'data_finding', 'follow_up']
NARRATIVE_LABELS = ['Kỳ', 'Nội dung', 'Kết quả', 'Theo dõi']
NARRATIVE_SOURCES = {
    'insights_overview_v3': 'reporting.validated_sales_monthly',
    'insights_sales_v3': 'reporting.validated_sales_monthly',
    'insights_commercial_v3': 'reporting.validated_product_monthly',
    'insights_customers_v3': 'reporting.analytic_customers',
    'insights_service_v3': 'reporting.analytic_orders',
    'insights_trust_v3': 'reporting.quality_health',
}

# These are reading/decision guides, not findings or claims of causal impact.
GUIDES = {
    'overview': {
        'output': 'Nắm quy mô, biến động và cơ cấu bán hàng; xem giao hàng cùng độ phủ, rồi chọn trang chuyên sâu để điều tra.',
        'read': 'Chọn một tháng rồi Apply filters. Đọc KPI, ba câu trả lời và xu hướng trước; dùng menu sáu trang để đi sâu, giữ nguyên tháng và release. Khách hàng luôn chốt 31/08/2018; ở trang Khách hàng/Độ tin cậy, tháng chỉ phục vụ điều hướng.',
        'limit': 'Đây là dữ liệu Olist lịch sử, không phải hoạt động hiện tại hay dữ liệu Abbott. Không có budget, target, cost hoặc lý do hủy nên không gắn KPI đạt/trượt, profit hay nguyên nhân. Giá trị hàng delivered chưa gồm freight; giao hàng dùng tập đủ mốc ngày. Tháng cuối có thể thiếu quan sát.',
    },
    'sales': {
        'output': 'Đánh giá quy mô và biến động bán hàng; chọn tháng cần phân tích sâu.',
        'read': 'Đọc merchandise cùng số đơn và AOV; MoM so đúng tháng trước, YoY so đúng tháng năm trước. Hai biểu đồ xu hướng giữ toàn kỳ khi đổi tháng KPI.',
        'limit': 'Giá trị hàng delivered chưa gồm freight, không phải lợi nhuận hay doanh thu kế toán. Snapshot trạng thái cuối nguồn, không phải trạng thái lịch sử tại ngày mua. Kỳ biên có thể thiếu quan sát; không suy ra nguyên nhân tăng/giảm.',
    },
    'commercial': {
        'output': 'Xác định category, seller và địa bàn đóng góp lớn để ưu tiên điều tra kinh doanh/vận hành.',
        'read': 'So tỷ trọng giá trị với số dòng hàng; top 10 seller chia cho toàn bộ seller trong tháng, không chỉ 10 dòng đang hiển thị. State là địa chỉ người mua theo đơn.',
        'limit': 'Đóng góp cao không đồng nghĩa hiệu quả hay lợi nhuận cao. Không có cost, inventory hoặc market size để kết luận margin, thiếu hàng hay thị phần. Seller là mã ẩn danh, không phải vendor telesales.',
    },
    'customers': {
        'output': 'Mô tả mức mua lại và chọn nhóm/cohort cần khảo sát thêm về trải nghiệm khách hàng.',
        'read': 'Repeat = ít nhất 2 đơn delivered trong cửa sổ. Heatmap mỗi ô chia cho cohort size gốc; M1 là quay lại ở tháng kế tiếp, không phải tỷ lệ mua lại toàn đời. Đường M1–M6 dùng các cohort đủ thời gian quan sát ở mỗi mốc.',
        'limit': 'Chốt quan sát 31/08/2018; không đổi theo tháng ở trang khác. Ô tương lai để trống, không phải 0. Thời gian theo dõi khác nhau giữa cohort; một đơn không có nghĩa churn. Không có bằng chứng nhân quả hay CLV tương lai.',
    },
    'service': {
        'output': 'Đánh giá độ phủ đo lường giao hàng, việc đúng hẹn và cơ cấu thanh toán; chọn địa bàn cần kiểm tra.',
        'read': 'Đúng hẹn dùng đơn đủ mốc ngày hợp lệ; median/trung bình tính trên cùng tập đủ điều kiện. Phân loại theo tháng mua, không phải tháng giao hay tháng thu tiền. Khi so bang, mở SQL Lab delivery để xem cả sample size.',
        'limit': 'Chưa đặt SLA/mục tiêu nên không tự gắn tốt/xấu. Payment amount không phải merchandise, tiền đã thu hay refunds; một đơn có nhiều payment records/phương thức. Không cộng distinct orders giữa các phương thức.',
    },
    'trust': {
        'output': 'Quyết định có thể dùng số liệu nào và truy vết về release, producer và cảnh báo nguồn.',
        'read': 'Nhận xét và bảng provenance gắn release/producer đang xem. Hai biểu đồ operational audit là lịch sử live, có thể có run lỗi mới hơn nhưng không đổi release của báo cáo này.',
        'limit': '0 error occurrence không có nghĩa nguồn sạch tuyệt đối. Warning được giữ theo chính sách chấp nhận; occurrence giữa rule có thể trùng bản ghi. Publish bị chặn khi hard gate lỗi; không suy ra SLA/uptime chỉ từ số lần run.',
    },
}


def number(expression, decimals=0):
    pattern = 'FM999,999,999,999,990' + ('.' + '0' * decimals if decimals else '')
    return f"COALESCE(to_char(({expression})::numeric,'{pattern}'),'không đủ dữ liệu')"


def percent(expression):
    return f"CASE WHEN ({expression}) IS NULL THEN 'không đủ dữ liệu' ELSE {number(f'100*({expression})', 2)}||'%' END"


def change(expression):
    return f"CASE WHEN ({expression})>=0 THEN '+' ELSE '' END||({percent(expression)})"


def narrative_sql(name, release_id, producer_id):
    """Compile read-only SQL; literal identifiers must be validated UUIDs."""
    if name not in NARRATIVE_SOURCES:
        raise ValueError('Unknown commentary dataset: ' + name)
    rid, producer = str(UUID(str(release_id))), str(UUID(str(producer_id)))
    board = name.removeprefix('insights_').removesuffix('_v3')
    if board == 'overview':
        # Reuse governed findings, joining only the same release/month/question
        # aggregates. No new metric or atomic fact-to-fact join is introduced.
        sales = narrative_sql('insights_sales_v3', rid, producer)
        commercial = narrative_sql('insights_commercial_v3', rid, producer)
        service = narrative_sql('insights_service_v3', rid, producer)
        return f"""WITH sales AS ({sales}), commercial AS ({commercial}), service AS ({service})
          SELECT a.release_id,a.purchase_month,a.analysis_scope,
            '01 · Bán hàng đang ở mức nào, thay đổi ra sao?' AS business_question,
            a.data_finding||' '||b.data_finding AS data_finding,
            'Xem Bán hàng để so số đơn, giá trị bình quân và kỳ trước.' AS follow_up
          FROM sales a JOIN sales b USING(release_id,purchase_month)
          WHERE a.business_question LIKE '01%' AND b.business_question LIKE '02%'
          UNION ALL
          SELECT release_id,purchase_month,analysis_scope,
            '02 · Danh mục nào đóng góp lớn nhất?' AS business_question,data_finding,
            'Xem Sản phẩm & seller để phân tích đóng góp theo danh mục và khu vực.' AS follow_up
          FROM commercial WHERE business_question LIKE '01%'
          UNION ALL
          SELECT a.release_id,a.purchase_month,a.analysis_scope,
            '03 · Giao hàng ra sao, đo được bao nhiêu?' AS business_question,
            a.data_finding||' '||b.data_finding AS data_finding,
            'Xem Giao & thanh toán để đối chiếu thời gian giao và độ phủ số liệu.' AS follow_up
          FROM service a JOIN service b USING(release_id,purchase_month)
          WHERE a.business_question LIKE '01%' AND b.business_question LIKE '02%'"""
    if board == 'sales':
        cte = f"""WITH base AS (
          SELECT m.*, (m.delivered_merchandise_value-p.delivered_merchandise_value)/nullif(p.delivered_merchandise_value,0) AS mom,
            (m.delivered_merchandise_value-y.delivered_merchandise_value)/nullif(y.delivered_merchandise_value,0) AS yoy
          FROM reporting.validated_sales_monthly m
          LEFT JOIN reporting.validated_sales_monthly p ON p.release_id=m.release_id AND p.month=m.month-interval '1 month'
          LEFT JOIN reporting.validated_sales_monthly y ON y.release_id=m.release_id AND y.month=m.month-interval '1 year'
          WHERE m.release_id='{rid}')"""
        values = f"""
          ('01 · Bán được bao nhiêu?',
           {number('delivered_merchandise_value',2)}||' BRL hàng delivered; '||{number('delivered_orders')}||' đơn; '||{number('delivered_unique_customers')}||' khách phân biệt. AOV '||{number('delivered_aov',2)}||' BRL/đơn.',
           'Đối chiếu số đơn và giá trị bình quân với tháng trước.'),
          ('02 · Biến động ra sao?',
           'Giá trị hàng: MoM '||({change('mom')})||'; YoY '||({change('yoy')})||'.',
           'Phân tích biến động theo danh mục và khu vực người mua.'),
          ('03 · Hủy đơn bao nhiêu?',
           {number('canceled_orders')}||'/'||{number('total_orders')}||' đơn có trạng thái canceled ('||({percent('cancellation_rate')})||'). Mẫu số gồm mọi trạng thái đơn.',
           'So sánh tỷ lệ hủy và cơ cấu trạng thái giữa các tháng.')"""
        source, period = 'base', "'Tháng '||to_char(month,'YYYY-MM')"
    elif board == 'commercial':
        cte = f"""WITH cats AS (
          SELECT *,row_number() OVER(PARTITION BY month ORDER BY delivered_merchandise_value DESC,category) AS rank,
            sum(delivered_merchandise_value) OVER(PARTITION BY month) AS category_total
          FROM reporting.validated_product_monthly WHERE release_id='{rid}'), ranked_sellers AS (
          SELECT *,row_number() OVER(PARTITION BY month ORDER BY delivered_merchandise_value DESC,seller_id) AS rank
          FROM reporting.validated_seller_monthly WHERE release_id='{rid}'), seller_summary AS (
          SELECT month,count(*) AS sellers,sum(delivered_merchandise_value) AS seller_total,
            sum(delivered_merchandise_value) FILTER(WHERE rank<=10) AS top10_value
          FROM ranked_sellers GROUP BY month), states AS (
          SELECT *,row_number() OVER(PARTITION BY month ORDER BY delivered_merchandise_value DESC,state) AS rank,
            sum(delivered_merchandise_value) OVER(PARTITION BY month) AS state_total
          FROM reporting.validated_buyer_state_monthly WHERE release_id='{rid}'), base AS (
          SELECT m.release_id,m.month,c.category,c.delivered_merchandise_value AS category_value,c.category_total,
            s.sellers,s.seller_total,s.top10_value,g.state,g.delivered_merchandise_value AS state_value,g.state_total
          FROM reporting.validated_sales_monthly m
          LEFT JOIN cats c ON c.month=m.month AND c.rank=1
          LEFT JOIN seller_summary s ON s.month=m.month
          LEFT JOIN states g ON g.month=m.month AND g.rank=1
          WHERE m.release_id='{rid}')"""
        values = f"""
          ('01 · Category nào dẫn đầu?',
           COALESCE(category,'Không có category')||': '||{number('category_value',2)}||' BRL, chiếm '||({percent('category_value/nullif(category_total,0)')})||' giá trị hàng delivered của tháng.',
           'Đối chiếu giá trị với số dòng hàng của các danh mục dẫn đầu.'),
          ('02 · Tập trung vào seller không?',
           'Top 10 seller chiếm '||({percent('top10_value/nullif(seller_total,0)')})||' giá trị; tổng '||{number('sellers')}||' seller có quan sát trong tháng.',
           'Theo dõi tỷ trọng nhóm dẫn đầu và thay đổi cơ cấu nhà bán hàng.'),
          ('03 · Khách ở đâu đóng góp lớn?',
           COALESCE(state,'Không có state')||': '||{number('state_value',2)}||' BRL, chiếm '||({percent('state_value/nullif(state_total,0)')})||' giá trị delivered theo buyer state.',
           'Đối chiếu số đơn và giá trị bình quân tại các khu vực đóng góp lớn.')"""
        source, period = 'base', "'Tháng '||to_char(month,'YYYY-MM')"
    elif board == 'customers':
        cte = f"""WITH customer_totals AS (
          SELECT count(*) AS customers,count(*) FILTER(WHERE delivered_orders>=2) AS repeat_customers,
            count(*) FILTER(WHERE delivered_orders=1) AS single_customers,
            sum(observed_merchandise_value) AS total_value,
            sum(observed_merchandise_value) FILTER(WHERE delivered_orders>=2) AS repeat_value
          FROM reporting.analytic_customers WHERE release_id='{rid}'), m1 AS (
          SELECT sum(active_customers) AS active,sum(cohort_size) AS eligible,count(*) AS cohorts
          FROM reporting.analytic_cohorts WHERE release_id='{rid}' AND month_offset=1 AND cohort_month>='2017-01-01'), base AS (
          SELECT '{rid}'::uuid AS release_id,c.*,m1.* FROM customer_totals c CROSS JOIN m1)"""
        values = f"""
          ('01 · Bao nhiêu khách mua lại?',
           {number('repeat_customers')}||'/'||{number('customers')}||' khách có ít nhất 2 đơn delivered ('||({percent('repeat_customers::numeric/nullif(customers,0)')})||').',
           'So sánh mức quay lại giữa các nhóm có cùng thời gian theo dõi.'),
          ('02 · Nhóm mua lại đóng góp gì?',
           'Khách mua lại đóng góp '||({percent('repeat_value/nullif(total_value,0)')})||' merchandise toàn kỳ. '||{number('single_customers')}||' khách chỉ có 1 đơn được quan sát.',
           'Xem cơ cấu mua lại và phân bố số lần mua của khách hàng.'),
          ('03 · Có quay lại ở tháng kế?',
           'M1: '||{number('active')}||'/'||{number('eligible')}||' khách ('||({percent('active::numeric/nullif(eligible,0)')})||'), gộp '||{number('cohorts')}||' cohort từ 2017 đủ thời gian quan sát.',
           'Đối chiếu mức quay lại cùng quy mô và thời gian theo dõi của từng nhóm.')"""
        source, period = 'base', "'Toàn kỳ đến 31/08/2018'"
    elif board == 'service':
        cte = f"""WITH orders AS (
          SELECT month,sum(delivered_order_count) AS delivered,sum(known_delivery_date_count) AS eligible,
            sum(on_time_delivery_count) AS on_time,
            percentile_cont(0.5) WITHIN GROUP(ORDER BY delivery_days) FILTER(WHERE known_delivery_date_count=1) AS median_days
          FROM reporting.analytic_orders WHERE release_id='{rid}' GROUP BY month), methods AS (
          SELECT month,payment_method,sum(recorded_payment_value) AS amount,count(*) AS records
          FROM reporting.analytic_payments WHERE release_id='{rid}' GROUP BY month,payment_method), ranked AS (
          SELECT *,sum(amount) OVER(PARTITION BY month) AS total_amount,
            row_number() OVER(PARTITION BY month ORDER BY amount DESC,payment_method) AS rank FROM methods), base AS (
          SELECT '{rid}'::uuid AS release_id,o.*,p.payment_method,p.amount,p.total_amount,p.records
          FROM orders o LEFT JOIN ranked p ON p.month=o.month AND p.rank=1)"""
        values = f"""
          ('01 · Giao có đúng hẹn?',
           {number('on_time')}||'/'||{number('eligible')}||' đơn đủ điều kiện giao đúng hẹn ('||({percent('on_time::numeric/nullif(eligible,0)')})||').',
           'So sánh tỷ lệ đúng hẹn giữa các tháng và khu vực có đủ quan sát.'),
          ('02 · Mất bao lâu, đo được bao nhiêu?',
           'Median '||{number('median_days',1)}||' ngày. Có '||{number('eligible')}||'/'||{number('delivered')}||' đơn delivered đủ mốc ngày hợp lệ ('||({percent('eligible::numeric/nullif(delivered,0)')})||').',
           'Đối chiếu thời gian giao và số đơn quan sát theo khu vực.'),
          ('03 · Thanh toán chủ yếu bằng gì?',
           COALESCE(payment_method,'Không có payment')||': '||{number('amount',2)}||' BRL ('||({percent('amount/nullif(total_amount,0)')})||' recorded amount), '||{number('records')}||' payment records.',
           'Theo dõi cơ cấu phương thức và số kỳ thanh toán.')"""
        source, period = 'base', "'Tháng mua '||to_char(month,'YYYY-MM')"
    else:
        cte = f"""WITH quality AS (
          SELECT coalesce(sum(affected_records) FILTER(WHERE severity='error'),0) AS errors,
            count(DISTINCT rule_id) FILTER(WHERE severity='warning' AND affected_records>0) AS warning_rules
          FROM reporting.quality_health WHERE pipeline_run_id='{producer}'), largest AS (
          SELECT rule_id,affected_records FROM reporting.quality_health
          WHERE pipeline_run_id='{producer}' AND severity='warning' AND affected_records>0
          ORDER BY affected_records DESC,rule_id LIMIT 1), base AS (
          SELECT r.release_id,r.source_cut,p.state,q.errors,q.warning_rules,l.rule_id,l.affected_records
          FROM reporting.release_metadata r
          JOIN reporting.pipeline_health p ON p.pipeline_run_id='{producer}'
          CROSS JOIN quality q LEFT JOIN largest l ON true WHERE r.release_id='{rid}')"""
        values = f"""
          ('01 · Đang xem bản dữ liệu nào?',
           'Release '||left(release_id::text,8)||'; source cut '||source_cut::text||'; producer state: '||state||'. Publication mới không tự thay bản này.',
           'Đối chiếu provenance trước khi so báo cáo. Operational audit phía dưới là live, không phải producer của mọi release.'),
          ('02 · Có lỗi/cảnh báo gì?',
           {number('errors')}||' error occurrences; '||{number('warning_rules')}||' warning rules có ảnh hưởng trong producer đã pin. 0 error không có nghĩa nguồn hoàn toàn sạch.',
           'Đọc chính sách chấp nhận từng rule; không cộng occurrences giữa rule thành số bản ghi lỗi phân biệt.'),
          ('03 · Cảnh báo nào lớn nhất?',
           COALESCE(rule_id,'Không có warning có ảnh hưởng')||': '||{number('affected_records')}||' occurrences. '||CASE WHEN rule_id='DQ-COV-001' THEN 'Đơn nguồn thiếu item; giữ lại để đo coverage.' ELSE 'Đọc định nghĩa rule và grain trong quality policy.' END,
           'Truy về nguồn và xem độ phủ metric bị ảnh hưởng; không tự điền tiền hoặc bỏ warning để làm dashboard đẹp.')"""
        source, period = 'base', "'Release '||left(release_id::text,8)||' · producer'"
    month_column = 'month::text' if board in {'sales', 'commercial', 'service'} else 'NULL::text'
    return f"""{cte}
      SELECT release_id,{month_column} AS purchase_month,{period} AS analysis_scope,
        n.question AS business_question,n.finding AS data_finding,n.follow_up AS follow_up
      FROM {source} CROSS JOIN LATERAL (VALUES {values}) AS n(question,finding,follow_up)"""
