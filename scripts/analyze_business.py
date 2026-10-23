"""Reproducible, release-bound findings and independently checked analytics.

Writes a Vietnamese report, CSV results, executed SQL with hashes, and a notebook
that reads the same extracts. No generated business records or source updates.
"""
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from sales_dw.config import ROOT, connect
from sales_dw.export_metrics import assert_parity

MONTH='2018-07-01'


def md_table(rows, fields, limit=10):
    lines=['| '+' | '.join(fields)+' |','| '+' | '.join('---' for _ in fields)+' |']
    for row in rows[:limit]:
        values=[]
        for key in fields:
            v=row[key]
            if v is None:
                values.append('—')
            elif key.endswith(('_rate','_share')):
                values.append(f'{v:.2%}')
            elif key in {'customers','delivered_orders','eligible_deliveries','payment_records','orders_using_method','affected_records','delivered_item_rows'}:
                values.append(f'{v:,.0f}')
            else:
                values.append(f'{v:,.2f}' if isinstance(v,(Decimal,float)) else str(v))
        lines.append('| '+' | '.join(values)+' |')
    return '\n'.join(lines)


def main():
    with connect('publish') as c:
        pinned=ROOT/'var/bi/superset-context.json'
        if pinned.exists():
            selected=json.loads(pinned.read_text())
            current=c.execute("SELECT release_id,pipeline_run_id,source_cut FROM ops.releases WHERE release_id=%s AND state='published'",(selected['release_id'],)).fetchone()
        else:
            current=c.execute("SELECT p.release_id,r.pipeline_run_id,r.source_cut FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main'").fetchone()
    assert current
    params={**current,'month':MONTH}
    folder=ROOT/'var/analysis'
    folder.mkdir(exist_ok=True)
    result={'passed':False,'release':current,'selected_month':MONTH,'analysis_cutoff':'2018-08-31','captured_at':datetime.now(timezone.utc).isoformat(),'queries':{},'results':{}}
    with connect('bi') as c:
        for path in sorted((ROOT/'analysis/sql').glob('*.sql')):
            statement=path.read_text()
            c.execute('EXPLAIN (FORMAT JSON) '+statement,params).fetchall()
            rows=c.execute(statement,params).fetchall()
            result['queries'][path.stem]={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(statement.encode()).hexdigest(),'rows':len(rows)}
            result['results'][path.stem]=rows
            with (folder/(path.stem+'.csv')).open('w',newline='') as stream:
                if rows:
                    writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
                    writer.writeheader(); writer.writerows(rows)
        # Independent monthly aggregation from the published order grain.
        oracle=c.execute("""SELECT month,sum(order_count) AS total_orders,sum(delivered_order_count) AS delivered_orders,
          sum(canceled_order_count) AS canceled_orders,sum(canceled_order_count)::numeric/nullif(sum(order_count),0) AS cancellation_rate,
          sum(delivered_merchandise_value) AS delivered_merchandise_value,
          sum(delivered_merchandise_value)/nullif(sum(delivered_order_count),0) AS delivered_aov,
          count(DISTINCT customer_key) FILTER(WHERE delivered_order_count=1 AND customer_key>0) AS delivered_unique_customers,
          sum(item_row_count) FILTER(WHERE delivered_order_count=1) AS delivered_item_rows
          FROM reporting.analytic_orders WHERE release_id=%(release_id)s GROUP BY month""",params).fetchall()
        metrics=['total_orders','delivered_orders','canceled_orders','cancellation_rate','delivered_merchandise_value','delivered_aov','delivered_unique_customers','delivered_item_rows']
        # Months with no delivered orders have zero item rows, not fabricated data.
        oracle=[{**r,'delivered_item_rows':r['delivered_item_rows'] or 0} for r in oracle]
        assert_parity(result['results']['monthly'],oracle,['month'],metrics)
        totals=c.execute("SELECT count(*) AS customers,sum(delivered_orders) AS delivered_orders,sum(observed_merchandise_value) AS value,count(*) FILTER(WHERE delivered_orders>=2) AS repeat_customers,sum(observed_merchandise_value) FILTER(WHERE delivered_orders>=2) AS repeat_value FROM reporting.analytic_customers WHERE release_id=%(release_id)s",params).fetchone()
        assert totals['customers']==93358 and totals['delivered_orders']==96478 and totals['value']==Decimal('13221498.11')
        # Cohort oracle is independently derived from order-level observations.
        cohorts=c.execute("""WITH firsts AS (
          SELECT customer_key,min(month) AS cohort FROM reporting.analytic_orders
          WHERE release_id=%(release_id)s AND delivered_order_count=1 AND customer_key>0 AND purchase_timestamp<'2018-09-01' GROUP BY customer_key
        ) SELECT f.cohort AS cohort_month,((extract(year FROM o.month)-extract(year FROM f.cohort))*12+extract(month FROM o.month)-extract(month FROM f.cohort))::integer AS month_offset,
          count(DISTINCT o.customer_key) AS n
          FROM reporting.analytic_orders o JOIN firsts f USING(customer_key)
          WHERE o.release_id=%(release_id)s AND o.delivered_order_count=1 AND o.purchase_timestamp<'2018-09-01'
          GROUP BY f.cohort,o.month""",params).fetchall()
        reference={(r['cohort_month'],r['month_offset']):r['n'] for r in cohorts}
        for row in result['results']['cohorts']:
            assert row['active_customers']==reference.get((row['cohort_month'],row['month_offset']),0)
            assert Decimal(0)<=row['observed_retention']<=Decimal(1)
            if row['month_offset']==0:
                assert row['active_customers']==row['cohort_size']
        payment=c.execute("SELECT count(*) AS n,sum(recorded_payment_value) AS value FROM reporting.analytic_payments WHERE release_id=%(release_id)s",params).fetchone()
        assert payment['n']==103886
    selected=next(r for r in result['results']['monthly'] if str(r['month'])==MONTH)
    category=result['results']['categories'][0]
    top10=sum(r['value_share'] for r in result['results']['sellers'][:10])
    repeat=Decimal(totals['repeat_customers'])/totals['customers']
    repeat_value=totals['repeat_value']/totals['value']
    delivery=result['results']['delivery']
    eligible=sum(r['eligible_deliveries'] for r in delivery)
    on_time=sum(r['on_time_deliveries'] for r in delivery)
    result['summary']={'selected_month':selected,'customer_totals':totals,'repeat_customer_share':repeat,'repeat_value_share':repeat_value,
                       'top10_seller_share':top10,'delivery_eligible':eligible,'on_time_deliveries':on_time,'payment_totals':payment}
    result['checks']={'eight_core_metrics_match_order_grain':True,'customer_counts_and_value_reconcile':True,'cohort_oracle_and_denominators':True,'payment_grain_count':True}
    result['passed']=True
    report=f'''# Phân tích Sales & Customer — Olist

Release `{current['release_id']}` · source cut {current['source_cut']} · tháng phân tích **{MONTH[:7]}** · cutoff khách hàng **31/08/2018**.

## 1. Bán hàng đang ở mức nào?

Tháng được chọn có **{selected['delivered_merchandise_value']:,.2f} BRL** giá trị hàng thuộc đơn delivered, **{selected['delivered_orders']:,}** đơn và **{selected['delivered_unique_customers']:,}** khách hàng phân biệt. AOV **{selected['delivered_aov']:,.2f} BRL/đơn**; cancellation rate **{selected['cancellation_rate']:.2%}**.

Giá trị hàng thay đổi **{selected['value_mom']:.2%}** so với đúng tháng trước và **{selected['value_yoy']:.2%}** so với cùng tháng năm trước. Đây là mô tả snapshot, chưa kiểm soát độ đầy đủ của nguồn hoặc thay đổi cơ cấu; không suy ra quan hệ nhân quả. Kỳ cuối 2018-08 cần thận trọng về right-censoring nên không được dùng mặc định để kết luận doanh nghiệp suy giảm.

## 2. Nên chú ý danh mục/người bán nào?

Category đứng đầu là **{category['category']}**, chiếm **{category['value_share']:.2%}** giá trị delivered của tháng. Top 10 sellers chiếm **{top10:.2%}**. Có thể dùng danh sách này để chọn đối tượng kiểm tra vận hành/nguồn cung trước; dataset không có cost, margin hoặc inventory để khuyến nghị tăng lợi nhuận hay bổ sung tồn kho.

{md_table(result['results']['categories'],['category','delivered_merchandise_value','delivered_item_rows'],5)}

## 3. Khách hàng có mua lại không?

Có **{totals['repeat_customers']:,}/{totals['customers']:,}** khách từng có ít nhất hai đơn delivered, tương đương **{repeat:.2%}**. Nhóm này đóng góp **{repeat_value:.2%}** merchandise value quan sát. Tỷ lệ này bị giới hạn bởi cửa sổ dữ liệu và định danh nguồn; không gọi nhóm một đơn là churn, không suy ra customer lifetime value tương lai.

Cohort dựa trên lần mua delivered đầu được quan sát; khách được đếm distinct lại trong từng tháng tuổi cohort. Mỗi cell chia cho cohort size gốc; chỉ tạo cell nằm trong cửa sổ đã quan sát. Các ô không có hoạt động trong cửa sổ là 0, ô tương lai không được tạo.

{md_table(result['results']['customer_segments'],['frequency_segment','customers','delivered_orders','observed_merchandise_value'])}

## 4. Giao hàng và thanh toán có gì đáng chú ý?

Trong tháng có **{eligible:,}** đơn đủ điều kiện ngày giao; **{on_time:,}** đơn đúng hẹn (**{Decimal(on_time)/eligible:.2%}**). Ngày hứa giao được so theo ngày lịch, đúng quy tắc fact. Các bang có ít quan sát cần được xem cùng sample size; không xếp hạng chỉ từ trung bình.

{md_table(delivery,['buyer_state','eligible_deliveries','on_time_rate','median_delivery_days'],8)}

{md_table(result['results']['payments'],['payment_method','payment_records','orders_using_method','recorded_payment_value'])}

Payment records không phải số đơn: một đơn có thể có nhiều records/phương thức. Recorded amount có thể gồm freight hoặc thuộc trạng thái khác; không gọi đây là doanh thu thuần, tiền đã thu hay refunds.

## 5. Chất lượng dữ liệu có làm sai kết luận không?

{md_table(result['results']['quality'],['rule_id','severity','affected_records'])}

Những cảnh báo này được giữ nguyên từ nguồn. Lỗi schema/grain/relationship/parity mới chặn publication. Thiếu items/payment không bị tự điền tiền để cân số. Không cộng affected occurrences giữa các rule thành số bản ghi lỗi phân biệt.

## 6. Tái lập và giới hạn

`make analyze` chạy SQL trong `analysis/sql/`, EXPLAIN trước execute, ghi CSV, query SHA và kiểm oracle vào `var/analysis/results.json`. Notebook đi kèm đọc chính các CSV đã xuất. Các core KPI đối soát với MetricFlow; cohort/recency/payment là governed SQL analysis và không được trình bày như metric MetricFlow mới.

Nguồn: Olist v2, CC BY-NC-SA 4.0; portfolio độc lập. BRL là quy ước vì CSV không có currency. Không có tên khách/sản phẩm, chi phí, clinical/telesales hoặc lịch sử trạng thái tại ngày mua. Phân tích mô tả các quan sát trong snapshot, không đại diện tình hình hiện tại của Abbott/Concentrix.
'''
    (folder/'business-analysis.md').write_text(report)
    (folder/'results.json').write_text(json.dumps(result,indent=2,default=str,ensure_ascii=False)+'\n')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':[]}
    def cell(kind,body):
        record={'id':hashlib.sha256((kind+body).encode()).hexdigest()[:12],'cell_type':kind,'metadata':{},'source':body.splitlines(True)}
        if kind=='code':record.update(execution_count=None,outputs=[])
        notebook['cells'].append(record)
    cell('markdown',report)
    cell('code',"from pathlib import Path\nimport csv, json\nbase = Path('.')\nresults = json.loads((base / 'results.json').read_text())\nassert results['passed']\nprint(results['release'])\nprint(results['checks'])\n")
    for name in result['results']:
        cell('markdown',f'### {name}\nSQL: `analysis/sql/{name}.sql`; số dòng: {len(result["results"][name])}.')
        cell('code',f"with (base / '{name}.csv').open() as stream:\n    rows = list(csv.DictReader(stream))\nprint('Rows:', len(rows))\nrows[:10]\n")
    (folder/'analysis.ipynb').write_text(json.dumps(notebook,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'var/evidence/analytics.json').write_text(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2,default=str,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':True,'release_id':str(current['release_id']),'customer_repeat_share':str(repeat),'report':str(folder/'business-analysis.md')}))


if __name__=='__main__':main()
