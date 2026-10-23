"""Actual Superset dashboard rendering, query success and native month selection."""
import argparse
import copy
import json
import os
import subprocess
from pathlib import Path
import time
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright
from verify_dashboard_navigation import verify_browser_navigation, verify_navigation
from verify_dashboard_presentation import verify_presentation

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--board',help='Verify only one page during layout iteration')
    parser.add_argument('--navigation-only',action='store_true',help='Iterate actual link clicks using prior same-catalog six-page observations; not a full browser handoff')
    parser.add_argument('--publish-transition',action='store_true',help='Keep pinned sales page open while a separately triggered pipeline publishes')
    args=parser.parse_args()
    state=json.loads((ROOT/'var/bi/superset-state.json').read_text())
    account=json.loads((ROOT/'var/secrets/superset_admin.json').read_text())
    folder=ROOT/'var/evidence/superset-screenshots'
    folder.mkdir(exist_ok=True)
    report={'passed':False,'release_id':state['release_id'],'catalog_sha256':state['catalog_sha256'],
            'dashboards':{},'native_month_changes':{}}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('SALES_DW_BROWSER','/opt/google/chrome/chrome'),headless=True,args=['--no-sandbox'])
        ctx=browser.new_context(viewport={'width':1720,'height':1100},device_scale_factor=1)
        page=ctx.new_page()
        page.goto('http://localhost:18088/login/',wait_until='domcontentloaded')
        page.locator('#username').fill(account['username'])
        page.locator('#password').fill(account['password'])
        page.locator('input[type=submit],button[type=submit]').first.click()
        page.wait_for_url('**/superset/welcome/**',timeout=60000)
        if args.navigation_only:
            previous=json.loads((ROOT/'var/evidence/superset-browser.json').read_text())
            assert previous['catalog_sha256']==state['catalog_sha256']
            assert set(previous['dashboards'])==set(state['dashboards'])
            proof=verify_browser_navigation(ctx,state,folder,previous['dashboards'])
            (ROOT/'var/evidence/superset-navigation.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False)+'\n')
            print('Navigation PASS: '+str(len(proof['clicked_routes']))+' actual clicks')
            browser.close()
            return
        for board,link in state['links'].items():
            if args.board and args.board!=board:continue
            answers,errors={},[]
            page=ctx.new_page()
            expected={v['id'] for v in state['charts'].values() if v['spec']['board']==board}
            def response(reply):
                if '/api/v1/chart/data' not in reply.url or reply.request.method!='POST':return
                try:
                    query=reply.request.post_data_json
                    chart_id=query.get('form_data',{}).get('slice_id')
                    if not chart_id:
                        form=parse_qs(urlparse(reply.url).query).get('form_data',['{}'])[0]
                        chart_id=json.loads(form).get('slice_id')
                    if not chart_id or int(chart_id) not in expected:return
                    body=reply.json()
                    if not reply.ok or any(row.get('status')!='success' for row in body.get('result',[])):
                        errors.append({'chart_id':chart_id,'status':reply.status,'body':body})
                    else:
                        answers[int(chart_id)]={'status':'success','rows':len(body['result'][0]['data']),'query':body['result'][0]['query'],'data':body['result'][0]['data']}
                except Exception as error:
                    errors.append(str(error))
            page.on('response',response)
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto(link,wait_until='domcontentloaded',timeout=90000)
            deadline=time.monotonic()+180
            while not expected<=set(answers) and time.monotonic()<deadline and not errors:
                page.mouse.wheel(0,650)
                page.wait_for_timeout(500)
                if page.evaluate('window.scrollY+window.innerHeight>=document.body.scrollHeight-10'):
                    page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(1500)
            if page.get_by_text('An error occurred while rendering the visualization',exact=False).count():
                errors.append('Chart visualization rendering failed')
            if page.locator('.ant-alert-error').count():
                errors.extend(page.locator('.ant-alert-error').all_text_contents())
            page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(250)
            report['dashboards'][board]={'url':link,'charts':copy.deepcopy(answers),'errors':errors,'screenshot':str(folder/(board+'.png'))}
            (ROOT/'var/evidence/superset-browser.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
            assert not errors,(board,errors[:3])
            assert expected<=set(answers),(board,'Missing chart answers',sorted(expected-set(answers)))
            nav=state['charts']['navigation@'+board]
            navigation=verify_navigation(answers[nav['id']]['data'],state,state['month'])
            report['dashboards'][board]['navigation']=navigation
            insight=state['charts']['insights@'+board]
            insight_id=insight['id']
            baseline_insights=copy.deepcopy(answers[insight_id]['data'])

            def assert_commentary_visible():
                assert len(answers[insight_id]['data'])==3
                for row in answers[insight_id]['data']:
                    cell=page.get_by_text(row['data_finding'],exact=True).first
                    cell.scroll_into_view_if_needed(timeout=15000)
                    assert cell.is_visible(), 'Narrative is not actually visible'
                    size=cell.evaluate('(el)=>({width:el.clientWidth,content:el.scrollWidth})')
                    assert size['content']<=size['width']+2, 'Narrative text overflows instead of wrapping'

            assert_commentary_visible()
            report['dashboards'][board]['commentary']={'three_answers_visible':True,'text_not_horizontally_clipped':True}
            # Capture the fully rendered baseline, not a transient blank grid
            # while React rehydrates after restoring a native filter.
            page.evaluate('window.scrollTo(0,0)')
            page.locator('a[href*="?native_filters="]').first.wait_for(state='visible',timeout=15000)
            page.locator('.dashboard-component-chart-holder').first.wait_for(state='visible',timeout=15000)
            page.wait_for_timeout(350)
            report['dashboards'][board]['presentation']=verify_presentation(page,state,board,first_viewport=board=='overview')
            page.screenshot(path=str(folder/(board+'.png')),full_page=True)
            if board in {'sales','overview'}:
                card=state['charts']['value@'+board]
                value=answers[card['id']]['data'][0][card['spec']['title']]
                assert value is not None,'Native month filter did not reach the KPI'
                assert state['month'] in answers[card['id']]['query'],'Native month missing from actual SQL'
            if board in state['commentary']['monthly_boards']:
                def select_month(month):
                    page.locator('.ant-select-selector').first.click()
                    page.locator('.ant-select input[role=combobox]').first.fill(month)
                    page.locator('.ant-select-item-option').filter(has_text=month).first.click()
                    page.get_by_role('button',name='Apply filters',exact=True).click()
                    page.evaluate('window.scrollTo(0,0)')
                    deadline=time.monotonic()+90
                    required=[insight_id,nav['id']]+([card['id']] if board in {'sales','overview'} else [])
                    while any(month not in answers[cid]['query'] for cid in required) and time.monotonic()<deadline:
                        page.wait_for_timeout(250)
                    assert all(month in answers[cid]['query'] for cid in required), 'Filter change did not reach actual chart/commentary SQL'
                    assert all(month[:7] in row['analysis_scope'] for row in answers[insight_id]['data'])
                    assert_commentary_visible()
                select_month('2018-06-01')
                assert baseline_insights!=answers[insight_id]['data'], 'Commentary stayed static after month change'
                report['native_month_changes'][board]={'from':state['month'],'to':'2018-06-01','commentary_period_and_findings_changed':True,'three_answers_visible':True}
            if board in {'sales','overview'}:
                result=json.loads((ROOT/'var/analysis/results.json').read_text())
                assert result['release']['release_id']==state['release_id']
                june=next(r for r in result['results']['monthly'] if r['month']=='2018-06-01')
                assert abs(answers[card['id']]['data'][0][card['spec']['title']]-float(june['delivered_merchandise_value']))<0.000001
                trend=state['charts']['value_trend@'+board]['id']
                assert answers[trend]['data']==report['dashboards'][board]['charts'][trend]['data'], 'Trend context changed with KPI month'
                report['native_month_change']={'from':state['month'],'to':'2018-06-01','value_matched_sql':True,'trend_context_preserved':True}
            if board in state['commentary']['monthly_boards']:
                select_month(state['month'])
                assert answers[insight_id]['data']==baseline_insights
                page.evaluate('window.scrollTo(0,0)')
                page.wait_for_timeout(1000)
                if args.publish_transition and board=='sales':
                    baseline=copy.deepcopy(answers)
                    compose=['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'infra/compose.yaml')]
                    deadline=time.monotonic()+480
                    while True:
                        current=subprocess.run([*compose,'exec','-T','postgres','psql','-XAt','-U','salesdw_backup','-d','sales_dw','-c',"SELECT release_id FROM ops.published_release WHERE channel='main'"],capture_output=True,text=True,check=True).stdout.strip()
                        if current!=state['release_id']:break
                        assert time.monotonic()<deadline,'No new publication observed'
                        page.wait_for_timeout(2000)
                    answers.clear()
                    page.reload(wait_until='domcontentloaded')
                    deadline=time.monotonic()+120
                    while not expected<=set(answers) and time.monotonic()<deadline:
                        page.mouse.wheel(0,600);page.wait_for_timeout(300)
                    assert expected<=set(answers) and not errors
                    for cid in expected:
                        assert answers[cid]['data']==baseline[cid]['data'], 'Pinned chart changed after publication'
                        assert state['release_id'] in answers[cid]['query']
                    report['publish_transition']={'pinned_release':state['release_id'],'new_current_release':current,'all_sales_charts_unchanged':True,'actual_new_publication_observed':True}
                    (ROOT/'var/evidence/superset-publish-transition.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
            assert not errors,(board,errors[:3])
            print(board+': browser PASS',flush=True)
            page.close()
        if not args.board and not args.publish_transition:
            report['navigation_clicks']=verify_browser_navigation(ctx,state,folder,report['dashboards'])
            print('Navigation: 14 actual clicks, fixed scopes and two viewport widths PASS',flush=True)
        browser.close()
    report['passed']=True
    if args.publish_transition:
        (ROOT/'var/evidence/superset-publish-transition.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'var/evidence/superset-browser.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':True,'dashboards':len(report['dashboards']),'screenshots':str(folder)}))


if __name__=='__main__':main()
