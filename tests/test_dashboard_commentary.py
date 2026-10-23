"""Offline contract tests complement the real API/native-filter browser checks."""
from decimal import Decimal
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bi'))
sys.path.insert(0,str(ROOT/'scripts'))
from superset_catalog import BOARDS, CHARTS
from superset_narratives import GUIDES, NARRATIVE_COLUMNS, NARRATIVE_SOURCES, narrative_sql
from superset_navigation import MONTHLY_BOARDS
from verify_dashboard_commentary import formatted, percentage, ratio, signed_percentage

RID='87f01740-0523-5fd4-be0e-eb52acb2842a'
PRODUCER='5ac008ff-3041-54cf-b03a-b7e76a5fa82f'


def test_every_page_has_questions_actions_limits_and_a_query_backed_answer():
    assert set(GUIDES)=={board[0] for board in BOARDS}
    narratives=[chart for chart in CHARTS if chart.get('narrative')]
    assert len(narratives)==6
    for chart in narratives:
        assert chart['source'] in NARRATIVE_SOURCES
        assert chart['raw']==NARRATIVE_COLUMNS
        assert all(name.isidentifier() and name.isascii() for name in chart['raw'])
        assert bool(chart['month'])==(chart['board'] in MONTHLY_BOARDS)
        assert all(GUIDES[chart['board']][key] for key in ('output','read','limit'))


def test_dashboard_contract_counts_match_the_executable_catalog():
    contract=json.loads((ROOT/'contracts/dashboard-contract.json').read_text())
    for board in contract['dashboards']:
        assert board['charts']==sum(chart['board']==board['id'] for chart in CHARTS)
    assert contract['commentary']['implementation']=='bi/superset_narratives.py'


@pytest.mark.parametrize('name',NARRATIVE_SOURCES)
def test_narratives_are_release_bound_and_have_no_precomputed_business_numbers(name):
    sql=narrative_sql(name,RID,PRODUCER)
    assert RID in sql
    assert all(f'AS {column}' in sql for column in NARRATIVE_COLUMNS)
    assert '867953.46' not in sql and '93358' not in sql
    assert sql.count("('0")== (9 if name=='insights_overview_v3' else 3)
    if name=='insights_trust_v3':
        assert PRODUCER in sql and 'FROM reporting.pipeline_health' not in sql
    if name in {'insights_overview_v3','insights_sales_v3','insights_commercial_v3','insights_service_v3'}:
        assert 'month::text AS purchase_month' in sql


def test_sql_context_refuses_untrusted_literal_or_dataset():
    with pytest.raises(ValueError):
        narrative_sql('insights_sales_v3',"'); DELETE FROM example; --",PRODUCER)
    with pytest.raises(ValueError):
        narrative_sql('insights_trust_v3',RID,'not-a-run')
    with pytest.raises(ValueError):
        narrative_sql('arbitrary',RID,PRODUCER)


def test_missing_denominator_is_not_a_zero_rate_and_rounding_matches_numeric_sql():
    assert ratio(0,0) is None
    assert ratio(None,10) is None
    assert percentage(ratio(0,0))=='không đủ dữ liệu'
    assert percentage(ratio(0,10))=='0.00%'
    assert signed_percentage(None)=='không đủ dữ liệu'
    assert signed_percentage(Decimal('0.01387210270804106533'))=='+1.39%'
    assert formatted(Decimal('1.005'),2)=='1.01'
    assert formatted(None,1)=='không đủ dữ liệu'
