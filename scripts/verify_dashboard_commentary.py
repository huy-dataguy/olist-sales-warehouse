"""Independent arithmetic checks for the actual Superset narrative responses."""
from decimal import Decimal, ROUND_HALF_UP
import hashlib

from sales_dw.config import ROOT


def formatted(value, places=0):
    if value is None:
        return 'không đủ dữ liệu'
    value = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f'{value:,.{places}f}'


def ratio(numerator, denominator):
    return None if numerator is None or not denominator else Decimal(str(numerator))/Decimal(str(denominator))


def percentage(value):
    return 'không đủ dữ liệu' if value is None else formatted(100*Decimal(str(value)),2)+'%'


def signed_percentage(value):
    return ('+' if value is not None and value>=0 else '')+percentage(value)


def verify_commentary(connection, board, rows, state, month):
    """Check all numeric findings, not just the fact that a table returned rows."""
    assert len(rows)==3, (board,'Expected three business answers',rows)
    rows=sorted(rows,key=lambda row:row['business_question'])
    assert len({r['business_question'] for r in rows})==3
    assert all(all(r.get(key) for key in ('analysis_scope','business_question','data_finding','follow_up')) for r in rows)
    params={'release_id':state['release_id'],'pipeline_run_id':state['pipeline_run_id'],'month':month}
    hashes=[]

    def query(sql):
        connection.execute('EXPLAIN (FORMAT JSON) '+sql,params).fetchall()
        answer=connection.execute(sql,params).fetchall()
        hashes.append(hashlib.sha256(sql.encode()).hexdigest())
        return answer

    def analysis(name):
        return query((ROOT/'analysis/sql'/f'{name}.sql').read_text())

    if board=='overview':
        expected=next(r for r in analysis('monthly') if str(r['month'])==month)
        categories=analysis('categories')
        top=categories[0] if categories else None
        delivery=analysis('delivery')
        eligible=sum(r['eligible_deliveries'] for r in delivery)
        on_time=sum(r['on_time_deliveries'] for r in delivery)
        observed=query('''SELECT sum(delivered_order_count) AS delivered,
          percentile_cont(0.5) WITHIN GROUP(ORDER BY delivery_days) FILTER(WHERE known_delivery_date_count=1) AS median
          FROM reporting.analytic_orders WHERE release_id=%(release_id)s AND month=%(month)s''')[0]
        fragments=[
            [formatted(expected['delivered_merchandise_value'],2)+' BRL',formatted(expected['delivered_orders'])+' đơn',
             formatted(expected['delivered_unique_customers'])+' khách',formatted(expected['delivered_aov'],2)+' BRL/đơn',
             'MoM '+signed_percentage(expected['value_mom']),'YoY '+signed_percentage(expected['value_yoy'])],
            [top['category'],formatted(top['delivered_merchandise_value'],2)+' BRL',percentage(top['value_share'])] if top else ['Không có category','không đủ dữ liệu'],
            [formatted(on_time)+'/'+formatted(eligible),percentage(ratio(on_time,eligible)),
             formatted(observed['median'],1)+' ngày',formatted(eligible)+'/'+formatted(observed['delivered'])],
        ]
    elif board=='sales':
        expected=next(r for r in analysis('monthly') if str(r['month'])==month)
        fragments=[
            [formatted(expected['delivered_merchandise_value'],2)+' BRL',formatted(expected['delivered_orders'])+' đơn',
             formatted(expected['delivered_unique_customers'])+' khách',formatted(expected['delivered_aov'],2)+' BRL/đơn'],
            ['MoM '+signed_percentage(expected['value_mom']),'YoY '+signed_percentage(expected['value_yoy'])],
            [formatted(expected['canceled_orders'])+'/'+formatted(expected['total_orders']),percentage(expected['cancellation_rate'])],
        ]
    elif board=='commercial':
        categories,sellers=analysis('categories'),analysis('sellers')
        states=query('''SELECT buyer_state,sum(delivered_merchandise_value) AS value FROM reporting.analytic_orders
          WHERE release_id=%(release_id)s AND month=%(month)s GROUP BY buyer_state ORDER BY value DESC,buyer_state''')
        # The no-delivered category/seller set is empty; its shares are unknown,
        # never replaced by 0%. State may have orders but no delivered value.
        top=categories[0] if categories else None
        fragments=[
            [top['category'],formatted(top['delivered_merchandise_value'],2)+' BRL',percentage(top['value_share'])] if top else ['Không có category','không đủ dữ liệu'],
            [percentage(sum((r['value_share'] for r in sellers[:10]),Decimal(0))) if sellers else 'không đủ dữ liệu',
             formatted(len(sellers))+' seller' if sellers else 'không đủ dữ liệu'],
            [states[0]['buyer_state'],formatted(states[0]['value'],2)+' BRL',percentage(ratio(states[0]['value'],sum(r['value'] for r in states)))] if states else ['Không có state'],
        ]
    elif board=='customers':
        totals=query('''WITH customers AS (
          SELECT customer_key,count(*) AS n,sum(delivered_merchandise_value) AS value
          FROM reporting.analytic_orders WHERE release_id=%(release_id)s AND delivered_order_count=1
            AND customer_key>0 AND purchase_timestamp<'2018-09-01' GROUP BY customer_key)
          SELECT count(*) AS customers,count(*) FILTER(WHERE n>=2) AS repeat,count(*) FILTER(WHERE n=1) AS single,
            sum(value) AS value,sum(value) FILTER(WHERE n>=2) AS repeat_value FROM customers''')[0]
        cohorts=[r for r in analysis('cohorts') if r['month_offset']==1 and str(r['cohort_month'])>='2017-01-01']
        active=sum(r['active_customers'] for r in cohorts)
        eligible=sum(r['cohort_size'] for r in cohorts)
        fragments=[
            [formatted(totals['repeat'])+'/'+formatted(totals['customers']),percentage(ratio(totals['repeat'],totals['customers']))],
            [percentage(ratio(totals['repeat_value'],totals['value'])),formatted(totals['single'])+' khách'],
            [formatted(active)+'/'+formatted(eligible),percentage(ratio(active,eligible)),formatted(len(cohorts))+' cohort'],
        ]
        assert all('31/08/2018' in r['analysis_scope'] for r in rows)
    elif board=='service':
        delivery,payments=analysis('delivery'),analysis('payments')
        eligible=sum(r['eligible_deliveries'] for r in delivery)
        on_time=sum(r['on_time_deliveries'] for r in delivery)
        observed=query('''SELECT sum(delivered_order_count) AS delivered,
          percentile_cont(0.5) WITHIN GROUP(ORDER BY delivery_days) FILTER(WHERE known_delivery_date_count=1) AS median
          FROM reporting.analytic_orders WHERE release_id=%(release_id)s AND month=%(month)s''')[0]
        top=payments[0] if payments else None
        fragments=[
            [formatted(on_time)+'/'+formatted(eligible),percentage(ratio(on_time,eligible))],
            [formatted(observed['median'],1)+' ngày',formatted(eligible)+'/'+formatted(observed['delivered']),percentage(ratio(eligible,observed['delivered']))],
            [top['payment_method'],formatted(top['recorded_payment_value'],2)+' BRL',
             percentage(ratio(top['recorded_payment_value'],sum(r['recorded_payment_value'] for r in payments))),
             formatted(top['payment_records'])+' payment records'] if top else ['Không có payment'],
        ]
    else:
        quality=analysis('quality')
        errors=sum(r['affected_records'] for r in quality if r['severity']=='error')
        warnings=[r for r in quality if r['severity']=='warning' and r['affected_records']>0]
        top=sorted(warnings,key=lambda r:(-r['affected_records'],r['rule_id']))[0] if warnings else None
        producer=query('SELECT state FROM reporting.pipeline_health WHERE pipeline_run_id=%(pipeline_run_id)s')[0]
        fragments=[
            [state['release_id'][:8],'source cut '+str(state['source_cut']),'producer state: '+producer['state']],
            [formatted(errors)+' error occurrences',formatted(len({r['rule_id'] for r in warnings}))+' warning rules'],
            [top['rule_id'],formatted(top['affected_records'])+' occurrences'] if top else ['Không có warning'],
        ]
        assert all(state['release_id'][:8] in r['analysis_scope'] for r in rows)
    if board in {'overview','sales','commercial','service'}:
        assert all(month[:7] in r['analysis_scope'] for r in rows), 'Commentary period mismatches month filter'
    for row,expected in zip(rows,fragments):
        for fragment in expected:
            assert fragment in row['data_finding'],(board,month,fragment,row['data_finding'])
    return {'passed':True,'period':month if board in {'overview','sales','commercial','service'} else rows[0]['analysis_scope'],
            'matched_fragments':fragments,'oracle_sql_sha256':hashes,'rows':rows}
