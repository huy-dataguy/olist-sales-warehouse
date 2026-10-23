"""Business copy stays concise; methodology remains available, not deleted."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bi'))

from superset_catalog import BOARDS, CHARTS
from superset_narratives import GUIDES
from superset_navigation import navigation_sql
from superset_presentation import PAGES, FORBIDDEN_PANELS


def test_every_report_has_short_business_context_and_essential_source_note():
    assert set(PAGES)==set(GUIDES)=={board[0] for board in BOARDS}
    assert len({page['context'] for page in PAGES.values()})==6
    for board,page in PAGES.items():
        assert len(page['context'])<110 and len(page['footnote'])<170
        assert page['title']==next(b[1] for b in BOARDS if b[0]==board)
        copy=' '.join(page.values())
        assert all(text not in copy for text in FORBIDDEN_PANELS)
        assert not any(text in copy for text in ('Source cut','published release','SQL Lab','Dùng để'))
        assert 'Nguồn: Olist' in page['footnote']
        assert all(GUIDES[board][key] for key in ('output','read','limit'))
    assert '31/08/2018' in PAGES['customers']['context']


def test_navigation_is_buttons_not_repeated_table_headings_and_instructions():
    for board in PAGES:
        sql=navigation_sql(board,'87f01740-0523-5fd4-be0e-eb52acb2842a')
        assert '<br' not in sql and sql.count('<a href=')==6
        assert sql.count('aria-current="page"')==1
        chart=next(c for c in CHARTS if c['board']==board and c.get('navigation'))
        assert chart['source'].endswith('_v2')
    assert all(c['title']=='Điểm nhấn' for c in CHARTS if c.get('narrative'))
