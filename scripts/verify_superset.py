"""Real API queries, core KPI parity and explicit release checks for every chart."""
import copy
from decimal import Decimal
import json
import time
import requests

from sales_dw.config import ROOT, connect
from verify_dashboard_commentary import verify_commentary
from verify_dashboard_navigation import verify_navigation


def main():
    state=json.loads((ROOT/'var/bi/superset-state.json').read_text())
    credentials=json.loads(__import__('pathlib').Path('/run/secrets/superset_admin.json').read_text())
    session=requests.Session()
    base='http://superset:8088'
    login=session.post(base+'/api/v1/security/login',json={**{k:credentials[k] for k in ('username','password')},'provider':'db','refresh':True},timeout=30)
    login.raise_for_status()
    session.headers['Authorization']='Bearer '+login.json()['access_token']
    csrf=session.get(base+'/api/v1/security/csrf_token/',timeout=30)
    csrf.raise_for_status()
    session.headers.update({'X-CSRFToken':csrf.json()['result'],'Referer':base+'/'})
    report={'passed':False,'engine':state['engine'],'release_id':state['release_id'],'catalog_sha256':state['catalog_sha256'],
            'charts':{},'dashboards':state['links'],'commentary':{},'navigation':{},'methodology':{},'idempotency':state['idempotency']}
    with connect('bi') as c:
        c.execute('EXPLAIN (FORMAT JSON) SELECT * FROM reporting.validated_sales_monthly WHERE release_id=%s AND month=%s',(state['release_id'],state['month'])).fetchall()
        expected=c.execute('SELECT * FROM reporting.validated_sales_monthly WHERE release_id=%s AND month=%s',(state['release_id'],state['month'])).fetchone()
        c.execute('EXPLAIN (FORMAT JSON) SELECT count(*) AS n,count(*) FILTER(WHERE delivered_orders>=2)::numeric/nullif(count(*),0) AS repeat FROM reporting.analytic_customers WHERE release_id=%s',(state['release_id'],)).fetchall()
        customers=c.execute('SELECT count(*) AS n,count(*) FILTER(WHERE delivered_orders>=2)::numeric/nullif(count(*),0) AS repeat FROM reporting.analytic_customers WHERE release_id=%s',(state['release_id'],)).fetchone()
        delivery_sql='''SELECT sum(on_time_delivery_count)::numeric/nullif(sum(known_delivery_date_count),0) AS ontime,
          percentile_cont(0.5) WITHIN GROUP(ORDER BY delivery_days) FILTER(WHERE known_delivery_date_count=1) AS median_days
          FROM reporting.analytic_orders WHERE release_id=%s AND month=%s'''
        c.execute('EXPLAIN (FORMAT JSON) '+delivery_sql,(state['release_id'],state['month'])).fetchall()
        delivery=c.execute(delivery_sql,(state['release_id'],state['month'])).fetchone()
    keys={'value@sales':'delivered_merchandise_value','orders@sales':'delivered_orders','customers@sales':'delivered_unique_customers','aov@sales':'delivered_aov','cancellation@sales':'cancellation_rate'}
    keys.update({k.replace('@sales','@overview'):v for k,v in list(keys.items())})
    try:
        for key,chart in state['charts'].items():
            payload=copy.deepcopy(chart['query_context'])
            payload['force']=True
            if chart['spec'].get('month'):
                payload['queries'][0]['filters']=[{'col':'purchase_month','op':'IN','val':[state['month']]}]
            started=time.monotonic()
            response=session.post(base+'/api/v1/chart/data',json=payload,timeout=180)
            if not response.ok:
                raise AssertionError((key,response.status_code,response.text[:1400]))
            data=response.json()['result'][0]
            assert data.get('status')=='success', (key,data.get('error'),data.get('status'))
            if chart['spec']['source']!='attempts':
                expected_binding=state['pipeline_run_id'] if chart['spec']['source'] in {'producer','quality'} else state['release_id']
                assert expected_binding in data['query'], (key,'Missing pinned SQL context')
            if key in keys:
                value=data['data'][0][chart['spec']['title']]
                assert abs(Decimal(str(value))-Decimal(str(expected[keys[key]])))<Decimal('0.000000001'), (key,value,expected[keys[key]])
            if key=='observed@customers':
                assert data['data'][0][chart['spec']['title']]==customers['n']
            if key=='repeat@customers':
                assert abs(Decimal(str(data['data'][0][chart['spec']['title']]))-customers['repeat'])<Decimal('0.000000001')
            if key in {'ontime@overview','median_days@overview'}:
                value=data['data'][0][chart['spec']['title']]
                assert abs(Decimal(str(value))-Decimal(str(delivery[chart['spec']['key']])))<Decimal('0.000000001')
            report['charts'][key]={'id':chart['id'],'rows':len(data['data']),'seconds':round(time.monotonic()-started,3),'status':'success','query':data['query'],'data':data['data'][:3]}
            if chart['spec'].get('navigation'):
                board=chart['spec']['board']
                report['navigation'][board]=[verify_navigation(data['data'],state,state['month'])]
                trial=copy.deepcopy(payload)
                trial['queries'][0]['filters']=[{'col':'purchase_month','op':'IN','val':['2018-06-01']}]
                reply=session.post(base+'/api/v1/chart/data',json=trial,timeout=180)
                reply.raise_for_status()
                changed=reply.json()['result'][0]
                assert changed['status']=='success'
                report['navigation'][board].append(verify_navigation(changed['data'],state,'2018-06-01'))
            if chart['spec'].get('narrative'):
                board=chart['spec']['board']
                metadata=session.get(base+f"/api/v1/chart/{chart['id']}",timeout=30)
                metadata.raise_for_status()
                description=metadata.json()['result']['description']
                assert all(text in description for text in state['commentary']['guides'][board].values())
                assert state['release_id'] in description
                report['methodology'][board]={'passed':True,'full_guides_in_chart_description':True,'release_binding_preserved':True}
                with connect('bi') as connection:
                    report['commentary'][board]=[verify_commentary(connection,board,data['data'],state,state['month'])]
                    if chart['spec'].get('month'):
                        months=['2018-06-01','2016-09-01','2018-10-01'] if board in {'sales','overview'} else ['2018-06-01']
                        for month in months:
                            trial=copy.deepcopy(payload)
                            trial['queries'][0]['filters']=[{'col':'purchase_month','op':'IN','val':[month]}]
                            reply=session.post(base+'/api/v1/chart/data',json=trial,timeout=180)
                            reply.raise_for_status()
                            answer=reply.json()['result'][0]
                            assert answer['status']=='success'
                            assert state['release_id'] in answer['query'] and month in answer['query']
                            report['commentary'][board].append(verify_commentary(connection,board,answer['data'],state,month))
            print(key+': PASS',flush=True)
        report['saved_queries']={}
        for name,stored in state['saved_queries'].items():
            saved=session.get(base+f"/api/v1/saved_query/{stored['id']}",timeout=30)
            saved.raise_for_status()
            statement=saved.json()['result']['sql']
            assert state['release_id'] in statement or state['pipeline_run_id'] in statement
            response=session.post(base+'/api/v1/sqllab/execute/',json={'database_id':state['database_id'],'sql':statement,'schema':'reporting','runAsync':False,'queryLimit':10000},timeout=180)
            assert response.ok,(name,response.status_code,response.text[:1200])
            answer=response.json()
            assert answer.get('status')=='success',(name,answer.get('status'),list(answer))
            report['saved_queries'][name]={'id':stored['id'],'rows':len(answer['data']),'status':'success'}
            print('SQL Lab '+name+': PASS',flush=True)
        assert set(report['commentary'])==set(state['dashboards'])
        assert set(report['navigation'])==set(state['dashboards'])
        assert set(report['methodology'])==set(state['dashboards'])
        assert state['idempotency']['passed'],'Run unchanged bootstrap twice to prove metadata idempotency'
        report.update(passed=True,core_metricflow_parity=True,published_contexts_pinned=True,distinct_not_summed=True,commentary_numeric_parity=True)
    finally:
        (ROOT/'var/evidence/superset.json').write_text(json.dumps(report,indent=2,default=str,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':True,'charts':len(report['charts']),'dashboards':len(state['dashboards'])}))


if __name__=='__main__':main()
