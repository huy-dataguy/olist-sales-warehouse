"""Check the visible business surface, not only the underlying chart requests."""


def verify_presentation(page, state, board, *, first_viewport=False):
    spec=state['presentation']['pages'][board]
    markdown='\n'.join(page.locator('.dashboard-markdown').all_text_contents())
    body=page.locator('body').inner_text()
    assert spec['title'] in body, (board,'Missing business title')
    assert spec['context'] in markdown and spec['footnote'] in markdown, (board,'Missing concise context/source note')
    for phrase in state['presentation']['forbidden_panels']:
        assert phrase not in body, (board,'Repeated instructional panel remains',phrase)
    for long_copy in state['commentary']['guides'][board].values():
        assert long_copy not in markdown, (board,'Methodology still dominates the report')
    if board!='trust':
        assert 'published release' not in body and 'Source cut' not in body and 'SQL Lab' not in body, (board,'Technical provenance leaked into business chrome')
    result={'passed':True,'concise_context_and_source':True,'repeated_panels_absent':True,
            'methodology_in_chart_descriptions':True,'technical_details_on_trust_page':True}
    if first_viewport:
        page.evaluate('window.scrollTo(0,0)')
        viewport=page.viewport_size
        kpis=[chart for chart in state['charts'].values() if chart['spec']['board']=='overview'
              and chart['spec']['viz']=='big_number_total']
        assert len(kpis)==8
        for chart in kpis:
            label=page.get_by_text(chart['spec']['title'],exact=True).first
            label.wait_for(state='visible',timeout=15000)
            box=label.evaluate('(el)=>{const r=el.closest(".dashboard-component-chart-holder").getBoundingClientRect();return {top:r.top,bottom:r.bottom}}')
            assert box['top']>=0 and box['bottom']<=viewport['height']+2, ('KPI pushed below first viewport',chart['spec']['key'],viewport,box)
        result['all_eight_kpis_in_first_viewport']=True
    return result
