"""Navigation safety, semantic scope and overview reuse; no services required."""
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bi'))
sys.path.insert(0, str(ROOT / 'scripts'))
from superset_catalog import BOARDS, CHARTS
from superset_navigation import (DESTINATIONS, MONTHLY_BOARDS, NAVIGATION_COLUMNS,
                                 dashboard_path, navigation_sql)
from verify_dashboard_navigation import verify_navigation

RID = '87f01740-0523-5fd4-be0e-eb52acb2842a'


def test_overview_is_entry_and_reuses_exact_existing_metric_expressions():
    assert BOARDS[0][0] == 'overview'
    core = [c for c in CHARTS if c['board']=='overview' and c.get('expression')]
    assert len(core)==12
    assert sum(c['viz']=='big_number_total' for c in core)==8
    for chart in core:
        original = next(c for c in CHARTS if c['board']!='overview'
                        and (c['key'],c['source'])==(chart['key'],chart['source']))
        assert chart['expression']==original['expression']
        assert chart['title']!=original['title']  # separate chart identity


def test_all_pages_have_one_navigation_chart_and_fixed_scopes_are_not_filtered():
    assert set(DESTINATIONS)=={b[0] for b in BOARDS}
    for board in DESTINATIONS:
        nav=[c for c in CHARTS if c['board']==board and c.get('navigation')]
        assert len(nav)==1 and nav[0]['month'] and nav[0]['raw']==NAVIGATION_COLUMNS
        if board not in MONTHLY_BOARDS:
            assert [c for c in CHARTS if c['board']==board and c.get('month')]==nav
    contract=json.loads((ROOT/'contracts/dashboard-contract.json').read_text())
    assert contract['navigation']['entry']=='overview'
    assert sum(d['charts'] for d in contract['dashboards'])==len(CHARTS)==60


@pytest.mark.parametrize('month',['2018-06-01','2018-07-01'])
def test_navigation_response_parser_checks_each_real_link(month):
    from html import escape
    row={'nav_'+board:'<a href="'+escape(dashboard_path(board,RID,month),quote=True)+'">Open</a>'
         for board in DESTINATIONS}
    result=verify_navigation([row],{'release_id':RID},month)
    assert result['passed'] and len(result['links'])==6
    for board in DESTINATIONS:
        sql=navigation_sql(board,RID)
        assert RID in sql and all('AS '+c in sql for c in NAVIGATION_COLUMNS)
        assert 'reporting.validated_sales_monthly' in sql


@pytest.mark.parametrize('month',['2018-06-02',"2018-07-01'); DELETE FROM x;--",'2018-7-01'])
def test_navigation_refuses_untrusted_or_non_month_dates(month):
    with pytest.raises(ValueError):
        dashboard_path('sales',RID,month)


def test_navigation_refuses_untrusted_identifiers_and_other_releases():
    with pytest.raises(ValueError):
        dashboard_path('arbitrary',RID)
    with pytest.raises(ValueError):
        navigation_sql('sales','not-a-release')
    encoded=parse_qs(urlparse(dashboard_path('sales',RID,'2018-06-01')).query)['native_filters'][0]
    assert "val:!('2018-06-01')" in encoded and 'filterState' in encoded
    row={'nav_'+board:'<a href="'+dashboard_path(board,RID,'2018-06-01')+'">Open</a>'
         for board in DESTINATIONS}
    row['nav_sales']=row['nav_sales'].replace(RID[:8],'00000000')
    with pytest.raises(AssertionError):
        verify_navigation([row],{'release_id':RID},'2018-06-01')
