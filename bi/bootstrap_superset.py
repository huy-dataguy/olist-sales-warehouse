"""Idempotent, release-specific Superset metadata assets; no Warehouse writes."""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote_plus
from uuid import UUID

from flask_login import login_user
from sqlalchemy import text
from superset.app import create_app
from superset import db, security_manager

from superset_catalog import BOARDS, SOURCES, CHARTS, MONTH
from superset_narratives import GUIDES, NARRATIVE_SOURCES, NARRATIVE_LABELS, narrative_sql
from superset_presentation import PAGES, FORBIDDEN_PANELS, copy_for
from superset_navigation import (DASHBOARD_CSS, DESTINATIONS, MONTHLY_BOARDS,
                                 NAVIGATION_COLUMNS, NAVIGATION_SOURCES,
                                 dashboard_path, filter_id, navigation_sql)

ROOT = Path('/workspace')


def metric(spec):
    return {'expressionType':'SQL','sqlExpression':spec['expression'],'label':spec['title'],'optionName':'metric_'+spec['key']}


def chart_config(spec, dataset):
    m = metric(spec) if spec.get('expression') else None
    columns = spec.get('raw') or ([spec['x']] if spec.get('x') else [])
    if spec.get('y'):
        columns = [spec['x'],spec['y']]
    query = {'time_range':'No filter','filters':list(spec.get('fixed_filters',[])), 'extras':{'having':'','where':''},'columns':columns,'metrics':[m] if m else [],
             'orderby':[[spec['x'],True]] if spec.get('sort_x') else ([[m,False]] if m and columns else []),
             'row_limit':spec.get('limit',1000),'series_limit':0,'order_desc':True,'is_timeseries':False}
    params = {'datasource':f'{dataset.id}__table','viz_type':spec['viz'],'slice_id':None,'time_range':'No filter',
              'adhoc_filters':[{'clause':'WHERE','expressionType':'SIMPLE','subject':f['col'],'operator':f['op'],'comparator':f['val']} for f in spec.get('fixed_filters',[])], 'row_limit':query['row_limit'],'color_scheme':'supersetColors','show_legend':False,
              'x_axis':spec.get('x'),'x_axis_sort_asc':bool(spec.get('sort_x')),
              'x_axis_sort':spec.get('x') if spec.get('sort_x') else (spec['title'] if m else spec.get('x')),
              'metrics':[m] if m else [],'metric':m,'groupby':[],'all_columns':columns,
              'query_mode':'raw' if spec.get('raw') else 'aggregate','y_axis_format':spec.get('fmt',',.0f'),
              'number_format':spec.get('fmt',',.0f'),'y_axis_title':'','show_value':spec['viz']!='echarts_timeseries_line','rich_tooltip':True,
              'orientation':'horizontal' if spec.get('horizontal') else 'vertical','zoomable':False,
              'truncate_metric':False,'header_font_size':0.42,'subheader_font_size':0.12,
              'date_format':'smart_date','x_axis_label_rotation':45 if spec.get('sort_x') else 0,
              'legendType':'scroll','legendOrientation':'bottom','show_labels':True,'label_type':'key_percent',
              'donut':True,'innerRadius':55,'outerRadius':85, 'page_length':12,'include_search':False,
              'x_axis_sort_series':'name' if spec.get('sort_x') else 'sum','x_axis_sort_series_ascending':bool(spec.get('sort_x'))}
    if spec['viz']=='pie':
        params['groupby'] = [spec['x']]
    if spec['viz']=='table' and m:
        params['groupby'] = columns
        params['percent_metrics'] = []
    if spec.get('narrative'):
        params.update(page_length=0,allow_render_html=False,show_cell_bars=False,
                      order_by_cols=[json.dumps([spec['x'],True])],
                      column_config={name:{'columnWidth':width,'truncateLongCells':False,'customColumnName':label}
                                     for name,label,width in zip(spec['raw'],NARRATIVE_LABELS,[115,165,330,300])})
    if spec.get('navigation'):
        params.update(page_length=0, allow_render_html=True, show_cell_bars=False,
                      column_config={name:{'columnWidth':145,'truncateLongCells':False,
                                           'customColumnName':DESTINATIONS[name.removeprefix('nav_')][0]}
                                     for name in NAVIGATION_COLUMNS})
    if spec['viz']=='heatmap_v2':
        params.update(x_axis=spec['x'],groupby=spec['y'],metric=m,linear_color_scheme='superset_seq_1',normalize_across='heatmap',show_legend=True,show_percentage=False,show_values=True,xscale_interval=1,yscale_interval=1,legend_type='continuous',legendType='continuous',left_margin=100,bottom_margin=45,sort_y_axis='alpha_desc')
    return params, {'datasource':{'id':dataset.id,'type':'table'},'force':False,'queries':[query],
                    'result_format':'json','result_type':'full','form_data':params}


def main():
    state_path=ROOT/'var/bi/superset-state.json'
    previous=json.loads(state_path.read_text()) if state_path.exists() else {}
    catalog_hash=hashlib.sha256(b''.join((ROOT/'bi'/name).read_bytes() for name in
        ('bootstrap_superset.py','superset_catalog.py','superset_narratives.py','superset_navigation.py','superset_presentation.py'))).hexdigest()
    app = create_app()
    with app.app_context(), app.test_request_context():
        from superset.connectors.sqla.models import SqlaTable
        from superset.models.core import Database
        from superset.models.dashboard import Dashboard
        from superset.models.slice import Slice
        from superset.models.sql_lab import SavedQuery
        admin = security_manager.find_user(username='demo')
        login_user(admin)
        cfg = json.loads(Path('/run/secrets/superset_warehouse.json').read_text())
        uri = f"postgresql+psycopg2://{cfg['user']}:{quote_plus(cfg['password'])}@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
        database = db.session.query(Database).filter_by(database_name='SalesDW · Published readonly').first()
        if database is None:
            database = Database(database_name='SalesDW · Published readonly',sqlalchemy_uri=uri,expose_in_sqllab=True,allow_dml=False)
            db.session.add(database)
            db.session.commit()
        with database.get_sqla_engine() as engine, engine.connect() as conn:
            release = dict(conn.execute(text("SELECT release_id,source_cut,published_at FROM reporting.release_metadata ORDER BY published_at DESC LIMIT 1")).mappings().one())
            # Resolve CURRENT pointer through the existing analyst-facing release
            # metadata is not sufficient after rollback. A supplied context is
            # written by the worker's verifier from ops.published_release.
        selected = json.loads((ROOT/'var/bi/superset-context.json').read_text())
        rid, producer = str(UUID(selected['release_id'])),str(UUID(selected['pipeline_run_id']))
        with database.get_sqla_engine() as engine, engine.connect() as conn:
            assert conn.execute(text('SELECT count(*) FROM reporting.release_metadata WHERE release_id=:rid'),{'rid':rid}).scalar_one()==1
        state={'engine':'Apache Superset 6.1.0','catalog_sha256':catalog_hash,'database_id':database.id,'release_id':rid,'pipeline_run_id':producer,'source_cut':selected['source_cut'],'month':MONTH,'datasets':{},'charts':{},'dashboards':{},'links':{}}
        datasets={}
        for name, relation in SOURCES.items():
            condition = f"pipeline_run_id='{producer}'" if name in {'producer','quality'} else ("true" if name=='attempts' else f"release_id='{rid}'")
            extras = ''
            if name in {'monthly','products','sellers','states','orders','payments'}:
                extras=',month::text AS purchase_month'
            if name=='daily':
                extras=",date_trunc('month',day)::date::text AS purchase_month,day::text AS day_label"
            if name=='cohorts':
                extras=',cohort_month::text AS cohort_label'
            sql_query=f'SELECT *{extras} FROM {relation} WHERE {condition}'
            if name=='product_mix':
                sql_query=f"""WITH ranked AS (
                  SELECT *,row_number() OVER(PARTITION BY month ORDER BY delivered_merchandise_value DESC,category) AS rank
                  FROM {relation} WHERE {condition})
                  SELECT release_id,month,month::text AS purchase_month,CASE WHEN rank<=5 THEN category ELSE 'Other categories' END AS category,
                  sum(delivered_merchandise_value) AS delivered_merchandise_value
                  FROM ranked GROUP BY release_id,month,CASE WHEN rank<=5 THEN category ELSE 'Other categories' END"""
            if name=='growth':
                sql_query=f"""SELECT m.release_id,m.month,m.month::text AS purchase_month,
                  (m.delivered_merchandise_value-p.delivered_merchandise_value)/nullif(p.delivered_merchandise_value,0) AS value_mom,
                  (m.delivered_merchandise_value-y.delivered_merchandise_value)/nullif(y.delivered_merchandise_value,0) AS value_yoy
                  FROM {relation} m LEFT JOIN {relation} p ON p.release_id=m.release_id AND p.month=m.month-interval '1 month'
                  LEFT JOIN {relation} y ON y.release_id=m.release_id AND y.month=m.month-interval '1 year'
                  WHERE m.release_id='{rid}'"""
            if name in NARRATIVE_SOURCES:
                sql_query=narrative_sql(name,rid,producer)
            if name in NAVIGATION_SOURCES:
                sql_query=navigation_sql(name.removeprefix('navigation_').removesuffix('_v2'),rid)
            if name in NARRATIVE_SOURCES or name in NAVIGATION_SOURCES:
                # The BI connection is read-only. Plan before metadata admission.
                with database.get_sqla_engine() as engine, engine.connect() as conn:
                    conn.execute(text('EXPLAIN (FORMAT JSON) '+sql_query)).all()
            table_name=f'olist_{name}_{rid[:8]}'
            ds=db.session.query(SqlaTable).filter_by(table_name=table_name,database_id=database.id).first()
            if ds is None:
                ds=SqlaTable(table_name=table_name,database=database,sql=sql_query,schema='reporting',owners=[admin])
                db.session.add(ds)
                db.session.commit()
                ds.fetch_metadata()
                db.session.commit()
            else:
                assert ds.sql==sql_query, 'A retained release dataset changed definition'
            datasets[name]=ds
            state['datasets'][name]={'id':ds.id,'sql':sql_query,'sql_sha256':hashlib.sha256(sql_query.encode()).hexdigest()}
        for board_id,title,question,note in BOARDS:
            slug=f'olist-{board_id}-{rid[:8]}'
            board=db.session.query(Dashboard).filter_by(slug=slug).first()
            if board is None:
                board=Dashboard(dashboard_title=title,slug=slug,owners=[admin],published=True)
                db.session.add(board)
                db.session.commit()
            specs=[s for s in CHARTS if s['board']==board_id]
            slices=[]
            for spec in specs:
                full_name=spec['title']+' · '+rid[:8]
                retained=previous.get('charts',{}).get(spec['key']+'@'+board_id) if previous.get('release_id')==rid else None
                chart=db.session.get(Slice,retained['id']) if retained else None
                if chart is None:
                    chart=db.session.query(Slice).filter_by(slice_name=full_name).first()
                params,context=chart_config(spec,datasets[spec['source']])
                if chart is None:
                    chart=db.session.query(Slice).filter_by(slice_name=spec['title'],datasource_id=datasets[spec['source']].id).first()
                if chart is None:
                    chart=Slice(slice_name=full_name,datasource_id=datasets[spec['source']].id,datasource_type='table',viz_type=spec['viz'],owners=[admin])
                    db.session.add(chart)
                    db.session.flush()
                params['slice_id']=chart.id
                chart.datasource_id=datasets[spec['source']].id
                chart.datasource_type='table'
                chart.slice_name=spec['title']
                chart.created_by=admin
                chart.changed_by=admin
                chart.params=json.dumps(params)
                chart.query_context=json.dumps(context)
                chart.description=f"{question}\n{note}\n"+'\n'.join(GUIDES[board_id][key] for key in ('output','read','limit'))+f"\nRelease: {rid}. Metric/view: {SOURCES[spec['source']]}."
                slices.append(chart)
                state['charts'][spec['key']+'@'+board_id]={'id':chart.id,'dataset_id':datasets[spec['source']].id,'spec':spec,'query_context':context}
            db.session.flush()
            pos={'DASHBOARD_VERSION_KEY':'v2','ROOT_ID':{'type':'ROOT','id':'ROOT_ID','children':['GRID_ID']},
                 'GRID_ID':{'type':'GRID','id':'GRID_ID','children':[],'parents':['ROOT_ID']},
                 'HEADER_ID':{'type':'HEADER','id':'HEADER_ID','meta':{'text':title}}}
            rows=[]
            intro_id='MARKDOWN-'+board_id
            presentation=copy_for(board_id)
            rows.append([(intro_id,{'type':'MARKDOWN','id':intro_id,'meta':{'code':presentation['context'],'height':7,'width':12}})])
            nav=[(s,sp) for s,sp in zip(slices,specs) if sp.get('navigation')]
            for ch,sp in nav:
                rows.append([(f'CHART-{ch.id}',{'type':'CHART','id':f'CHART-{ch.id}',
                             'meta':{'chartId':ch.id,'sliceName':sp['title'],'width':12,'height':13}})])
            insights=[(s,sp) for s,sp in zip(slices,specs) if sp.get('narrative')]
            kpis=[(s,sp) for s,sp in zip(slices,specs) if sp['viz']=='big_number_total']
            plots=[(s,sp) for s,sp in zip(slices,specs) if sp['viz']!='big_number_total' and not sp.get('narrative') and not sp.get('navigation')]
            per_row=4 if board_id in {'overview','sales'} else 3
            for start in range(0,len(kpis),per_row):
                group=kpis[start:start+per_row]
                rows.append([(f'CHART-{ch.id}',{'type':'CHART','id':f'CHART-{ch.id}','meta':{'chartId':ch.id,'sliceName':sp['title'],'width':12//len(group),'height':21}}) for ch,sp in group])
            for ch,sp in insights:
                rows.append([(f'CHART-{ch.id}',{'type':'CHART','id':f'CHART-{ch.id}','meta':{'chartId':ch.id,'sliceName':sp['title'],'width':12,'height':42 if board_id=='overview' else 36}})])
            for start in range(0,len(plots),2):
                group=plots[start:start+2]
                if any(sp['viz']=='heatmap_v2' for _,sp in group):
                    for ch,sp in group:
                        rows.append([(f'CHART-{ch.id}',{'type':'CHART','id':f'CHART-{ch.id}','meta':{'chartId':ch.id,'sliceName':sp['title'],'width':12,'height':64 if sp['viz']=='heatmap_v2' else 42}})])
                else:
                    rows.append([(f'CHART-{ch.id}',{'type':'CHART','id':f'CHART-{ch.id}','meta':{'chartId':ch.id,'sliceName':sp['title'],'width':12//len(group),'height':48}}) for ch,sp in group])
            rows.append([(f'MARKDOWN-note-{board_id}',{'type':'MARKDOWN','id':f'MARKDOWN-note-{board_id}',
                         'meta':{'code':presentation['footnote'],'width':12,'height':7}})])
            for i,row in enumerate(rows):
                row_id=f'ROW-{board_id}-{i}'
                pos['GRID_ID']['children'].append(row_id)
                pos[row_id]={'type':'ROW','id':row_id,'children':[key for key,_ in row],'parents':['ROOT_ID','GRID_ID'],'meta':{'background':'BACKGROUND_TRANSPARENT'}}
                for key,node in row:
                    node['parents']=['ROOT_ID','GRID_ID',row_id]
                    pos[key]=node
            metadata={'color_scheme':'supersetColors','refresh_frequency':0,'expanded_slices':{},'label_colors':{},'timed_refresh_immune_slices':[], 'cross_filters_enabled':False}
            if board_id in DESTINATIONS:
                filtered=[ch.id for ch,sp in zip(slices,specs) if sp.get('month')]
                excluded=[ch.id for ch,sp in zip(slices,specs) if not sp.get('month')]
                target=next(sp for sp in specs if sp.get('month'))['source']
                filter_label='Tháng đặt hàng' if board_id in MONTHLY_BOARDS else 'Tháng chuyển trang'
                metadata['native_filter_configuration']=[{'id':filter_id(board_id),'name':filter_label,'filterType':'filter_select','type':'NATIVE_FILTER',
                  'description':'Chọn tháng cho các liên kết; không thay đổi phạm vi toàn kỳ của trang này.' if board_id not in MONTHLY_BOARDS else 'Tháng đặt hàng dùng cho KPI và điểm nhấn; biểu đồ xu hướng giữ toàn kỳ.',
                  'targets':[{'datasetId':datasets[target].id,'column':{'name':'purchase_month'}}],
                  'defaultDataMask':{'extraFormData':{'filters':[{'col':'purchase_month','op':'IN','val':[MONTH]}]},'filterState':{'value':[MONTH],'label':MONTH}},
                  'cascadeParentIds':[],'scope':{'rootPath':['ROOT_ID'],'excluded':excluded},
                  'controlValues':{'multiSelect':False,'enableEmptyFilter':False,'inverseSelection':False,'searchAllOptions':False},'chartsInScope':filtered}]
            board.json_metadata=json.dumps(metadata)
            board.dashboard_title=title
            board.created_by=admin
            board.changed_by=admin
            board.position_json=json.dumps(pos)
            board.slices=slices
            board.css=DASHBOARD_CSS
            db.session.commit()
            state['dashboards'][board_id]=board.id
            state['links'][board_id]=f'http://localhost:18088/superset/dashboard/{slug}/'
        state['commentary']={'version':'1.1.0','guides':GUIDES,
                            'monthly_boards':[b for b in DESTINATIONS if b in MONTHLY_BOARDS],
                            'customer_cutoff':'2018-08-31','trust_context':'pinned producer; operational audit live'}
        state['presentation']={'version':'1.0.0','pages':PAGES,'forbidden_panels':list(FORBIDDEN_PANELS),
                               'methodology_location':'chart descriptions and docs; provenance on trust page'}
        state['experience']={'version':'1.0.0','entry':'overview','entry_url':state['links']['overview'],
                             'navigation_month_boards':list(DESTINATIONS),
                             'fixed_business_scope':['customers','trust'],
                             'navigation_policy':'same retained release and selected month; fixed customer/trust business scope'}
        security_manager.sync_role_definitions()
        state['saved_queries']={}
        for path in sorted((ROOT/'analysis/sql').glob('*.sql')):
            label='Olist analysis · '+path.stem+' · '+rid[:8]
            saved=db.session.query(SavedQuery).filter_by(label=label,user_id=admin.id).first()
            if saved is None:
                saved=SavedQuery(label=label,user_id=admin.id,db_id=database.id,schema='reporting')
                db.session.add(saved)
            statement=path.read_text()
            for key,value in {'release_id':rid,'pipeline_run_id':producer,'month':MONTH}.items():
                statement=statement.replace('%('+key+')s',"'"+value+"'")
            saved.sql=statement
            saved.created_by=admin
            saved.changed_by=admin
            saved.description='Read-only, published release '+rid+'. Definition: analysis/sql/'+path.name
            db.session.commit()
            state['saved_queries'][path.stem]={'id':saved.id,'url':f'http://localhost:18088/sqllab/?savedQueryId={saved.id}'}
        state['asset_counts']={
            'datasets':db.session.query(SqlaTable).filter(SqlaTable.table_name.endswith('_'+rid[:8])).count(),
            'charts':db.session.query(Slice).filter(Slice.datasource_type=='table',Slice.datasource_id.in_([d.id for d in datasets.values()])).count(),
            'dashboards':db.session.query(Dashboard).filter(Dashboard.slug.in_(['olist-'+b+'-'+rid[:8] for b in DESTINATIONS])).count(),
        }
        unchanged=previous.get('catalog_sha256')==catalog_hash and previous.get('release_id')==rid
        if unchanged:
            assert previous['asset_counts']==state['asset_counts'],'Rebootstrap changed asset counts'
            assert previous['dashboards']==state['dashboards'],'Rebootstrap duplicated dashboards'
            for kind in ('charts','datasets'):
                assert {k:v['id'] for k,v in previous[kind].items()}=={k:v['id'] for k,v in state[kind].items()},'Rebootstrap changed '+kind+' identities'
        state['idempotency']={'passed':unchanged,'same_catalog_and_context':unchanged,
                              'asset_counts':state['asset_counts']}
        state_path.write_text(json.dumps(state,indent=2,default=str)+'\n')
        print(json.dumps({'dashboards':state['links'],'charts':len(CHARTS),'release_id':rid}))


if __name__=='__main__':
    main()
