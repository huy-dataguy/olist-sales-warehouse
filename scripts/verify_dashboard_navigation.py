"""Independent parsing checks for actual query-backed navigation responses."""
from html.parser import HTMLParser
import json
import time
from urllib.parse import parse_qs, unquote, urlparse
from uuid import UUID
from verify_dashboard_presentation import verify_presentation

BOARD_IDS = ('overview', 'sales', 'commercial', 'customers', 'service', 'trust')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs).get('href'))


def verify_navigation(rows, state, month):
    assert len(rows) == 1, ('Expected one navigation row for one month', rows)
    checked = {}
    rid = str(UUID(state['release_id']))
    for board in BOARD_IDS:
        html = rows[0]['nav_' + board]
        assert '<script' not in html.lower() and 'javascript:' not in html.lower()
        parser = Links()
        parser.feed(html)
        assert len(parser.hrefs) == 1
        parsed = urlparse(parser.hrefs[0])
        assert not parsed.scheme and not parsed.netloc, 'Navigation must stay on this origin'
        assert parsed.path == f'/superset/dashboard/olist-{board}-{rid[:8]}/'
        params = parse_qs(parsed.query)
        assert set(params) == {'native_filters'}
        rison = unquote(params['native_filters'][0])
        assert 'NATIVE_FILTER-month-' + board in rison
        assert "val:!('" + month + "')" in rison
        assert "value:!('" + month + "')" in rison
        assert 'extraFormData:' in rison and 'filterState:' in rison
        checked[board] = parser.hrefs[0]
    return {'passed': True, 'month': month, 'same_release': rid, 'links': checked}


def verify_browser_navigation(context, state, folder, baseline):
    """Click real anchors; URL existence alone is not navigation/filter proof."""
    page = context.new_page()
    answers, errors = {}, []
    report = {'passed': False, 'month': '2018-06-01', 'clicked_routes': [],
              'fixed_scopes_preserved': {}, 'viewport_checks': {}}
    all_ids = {c['id'] for c in state['charts'].values()}

    def response(reply):
        if '/api/v1/chart/data' not in reply.url or reply.request.method != 'POST':
            return
        try:
            request = reply.request.post_data_json
            chart_id = request.get('form_data', {}).get('slice_id')
            if not chart_id:
                chart_id = json.loads(parse_qs(urlparse(reply.url).query).get('form_data', ['{}'])[0]).get('slice_id')
            if not chart_id or int(chart_id) not in all_ids:
                return
            body = reply.json()
            if not reply.ok or any(r.get('status') != 'success' for r in body.get('result', [])):
                errors.append({'chart': chart_id, 'status': reply.status, 'body': body})
            else:
                answers[int(chart_id)] = body['result'][0]
        except Exception as error:
            errors.append(str(error))

    page.on('response', response)
    page.on('pageerror', lambda error: errors.append(str(error)))

    def settle(board, month):
        nav_id = state['charts']['navigation@' + board]['id']
        insight_id = state['charts']['insights@' + board]['id']
        required = {nav_id, insight_id}
        if board == 'overview':
            required.add(state['charts']['value@overview']['id'])
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline and not errors:
            ready = required <= set(answers) and month in answers[nav_id]['query']
            if ready and board not in {'customers','trust'}:
                ready = month in answers[insight_id]['query'] and all(
                    month[:7] in row['analysis_scope'] for row in answers[insight_id]['data'])
            if ready and board == 'overview':
                ready = month in answers[state['charts']['value@overview']['id']]['query']
            if ready:
                ready = month in page.locator('.ant-select-selector').first.inner_text()
            if ready:
                break
            page.mouse.wheel(0, 500)
            page.wait_for_timeout(250)
            if page.evaluate('window.scrollY+window.innerHeight>=document.body.scrollHeight-10'):
                page.evaluate('window.scrollTo(0,0)')
        assert not errors, errors[:2]
        assert required <= set(answers), (board, 'Navigation target did not load', required-set(answers))
        nav = verify_navigation(answers[nav_id]['data'], state, month)
        assert month in answers[nav_id]['query'], 'Navigation month was not applied in actual SQL'
        selection=page.locator('.ant-select-selector').first.inner_text()
        if month not in selection:
            page.screenshot(path=str(folder/('navigation-failure-'+board+'.png')),full_page=True)
        assert month in selection, (board,month,selection,'Filter UI and SQL disagree',page.url)
        findings = answers[insight_id]['data']
        if board in {'customers', 'trust'}:
            expected = (baseline[board]['charts'].get(insight_id) or baseline[board]['charts'].get(str(insight_id)))['data']
            assert findings == expected, 'Navigation month changed fixed-scope business findings'
            report['fixed_scopes_preserved'][board] = True
        else:
            assert all(month[:7] in row['analysis_scope'] for row in findings)
            assert month in answers[insight_id]['query']
        if board == 'overview':
            card = state['charts']['value@overview']
            results = json.loads((folder.parents[1] / 'analysis/results.json').read_text())
            assert results['release']['release_id'] == state['release_id']
            expected = next(r for r in results['results']['monthly'] if r['month'] == month)
            assert abs(answers[card['id']]['data'][0][card['spec']['title']]-float(expected['delivered_merchandise_value'])) < .000001
        page.evaluate('window.scrollTo(0,0)')
        for target in BOARD_IDS:
            selector = f'a[href^="/superset/dashboard/olist-{target}-{state["release_id"][:8]}/?native_filters="]'
            assert page.locator(selector).count() == 1, (board, target, 'Missing/duplicate real anchor')
        return nav

    def click(source, target, month):
        selector = f'a[href^="/superset/dashboard/olist-{target}-{state["release_id"][:8]}/?native_filters="]'
        anchor = page.locator(selector)
        anchor.scroll_into_view_if_needed()
        href = anchor.get_attribute('href')
        answers.clear()
        anchor.click()
        path = f'/superset/dashboard/olist-{target}-{state["release_id"][:8]}/'
        page.wait_for_url(lambda url: urlparse(str(url)).path == path, timeout=60000)
        settle(target, month)
        report['clicked_routes'].append({'from': source, 'to': target, 'month': month,
                                         'release_id': state['release_id'], 'href': href})

    # Start via the default entry; use the visible selector, not a constructed
    # target URL, to establish the non-default context before clicking links.
    page.goto(state['links']['overview'], wait_until='domcontentloaded', timeout=90000)
    settle('overview', state['month'])
    page.locator('.ant-select-selector').first.click()
    page.locator('.ant-select input[role=combobox]').first.fill(report['month'])
    page.locator('.ant-select-item-option').filter(has_text=report['month']).first.click()
    page.get_by_role('button', name='Apply filters', exact=True).click()
    settle('overview', report['month'])
    for target in BOARD_IDS[1:]:
        click('overview', target, report['month'])
        if target in {'customers', 'trust'}:
            for month in (state['month'], report['month']):
                page.locator('.ant-select-selector').first.click()
                page.locator('.ant-select input[role=combobox]').first.fill(month)
                page.locator('.ant-select-item-option').filter(has_text=month).first.click()
                page.get_by_role('button', name='Apply filters', exact=True).click()
                settle(target, month)
        click(target, 'overview', report['month'])
    for source, target in [('overview','sales'), ('sales','commercial'), ('commercial','service'), ('service','overview')]:
        click(source, target, report['month'])
    for width in (1720, 1366):
        page.set_viewport_size({'width': width, 'height': 1000})
        page.evaluate('window.scrollTo(0,0)')
        page.wait_for_timeout(1000)
        sizes = page.evaluate('({page:document.documentElement.scrollWidth,viewport:window.innerWidth})')
        assert sizes['page'] <= sizes['viewport'] + 2, ('Page horizontal overflow', sizes)
        for target in BOARD_IDS:
            anchor = page.locator(f'a[href^="/superset/dashboard/olist-{target}-{state["release_id"][:8]}/?native_filters="]')
            box = anchor.bounding_box()
            assert box and box['x'] >= 0 and box['x'] + box['width'] <= width + 2, ('Clipped navigation', width, target, box)
        findings=answers[state['charts']['insights@overview']['id']]['data']
        for row in findings:
            for field in ('business_question','data_finding','follow_up'):
                cell=page.get_by_text(row[field],exact=True).first
                bounds=cell.bounding_box()
                assert bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=width+2, ('Clipped narrative column',width,field,bounds)
                size=cell.evaluate('(el)=>({width:el.clientWidth,content:el.scrollWidth})')
                assert size['content']<=size['width']+2, ('Unwrapped narrative text',width,field,size)
        presentation=verify_presentation(page,state,'overview',first_viewport=True)
        image = folder / f'overview-navigation-{width}.png'
        page.screenshot(path=str(image), full_page=True)
        report['viewport_checks'][str(width)] = {'no_horizontal_overflow': True, 'all_six_links_fit': True,
                                               'questions_findings_actions_fit':True,'presentation':presentation,'screenshot': str(image)}
    assert len(report['clicked_routes']) == 14 and not errors
    report['passed'] = True
    page.close()
    return report
