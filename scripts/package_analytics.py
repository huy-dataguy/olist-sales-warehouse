"""Shareable allowlisted Superset reports; never includes connection secrets."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis-only',action='store_true',help='Export verified analytical outputs independently of browser handoff')
    args=parser.parse_args()
    source=ROOT/'var/analysis'
    target=ROOT/'output/analysis'
    target.mkdir(parents=True,exist_ok=True)
    results=json.loads((source/'results.json').read_text())
    assert results['passed']
    for name in ['business-analysis.md','analysis.ipynb','results.json',*[p.name for p in source.glob('*.csv')]]:
        shutil.copyfile(source/name,target/name)
    if args.analysis_only:
        print(json.dumps({'analysis_exported':str(target),'release_id':results['release']['release_id']}))
        return
    evidence=ROOT/'docs/evidence/superset'
    evidence.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name in ('superset','superset-browser','superset-publish-transition','analytics','notebook'):
        path=ROOT/'var/evidence'/(name+'.json')
        if not path.exists():continue
        payload=json.loads(path.read_text())
        if name=='notebook' and payload.get('notebook_sha256')!=hashlib.sha256((target/'analysis.ipynb').read_bytes()).hexdigest():
            continue  # Analysis was regenerated; do not reuse old execution proof.
        assert payload['passed'], 'Do not package failed evidence: '+name
        content=json.dumps(payload,indent=2,ensure_ascii=False).replace(str(ROOT)+'/', '').replace('/workspace/','')
        (evidence/path.name).write_text(content+'\n')
        hashes[path.name]=hashlib.sha256((evidence/path.name).read_bytes()).hexdigest()
    screenshots=ROOT/'var/evidence/superset-screenshots'
    (evidence/'screenshots').mkdir(exist_ok=True)
    for path in screenshots.glob('*.png'):
        shutil.copyfile(path,evidence/'screenshots'/path.name)
    state=json.loads((ROOT/'var/bi/superset-state.json').read_text())
    assert state['release_id']==results['release']['release_id']
    browser=json.loads((ROOT/'var/evidence/superset-browser.json').read_text())
    api=json.loads((ROOT/'var/evidence/superset.json').read_text())
    assert browser['passed'] and set(browser['dashboards'])==set(state['dashboards']), 'Full six-page browser verification required'
    assert api['passed'] and set(api['charts'])==set(state['charts']), 'All current charts must have actual API proof'
    assert browser['release_id']==api['release_id']==state['release_id'], 'Evidence release mismatch'
    assert browser['catalog_sha256']==api['catalog_sha256']==state['catalog_sha256'], 'Evidence catalog mismatch'
    assert api['idempotency']['passed'] and state['idempotency']['passed'], 'Metadata replay proof required'
    assert browser.get('navigation_clicks',{}).get('passed'), 'Actual forward/back/sibling clicks required'
    assert len(browser['navigation_clicks']['clicked_routes'])==14
    viewports=browser['navigation_clicks']['viewport_checks']
    assert set(viewports)=={'1720','1366'}
    assert all(v.get('questions_findings_actions_fit') and v.get('all_six_links_fit') for v in viewports.values()), 'Questions, findings, actions and navigation must fit both viewports'
    assert all(v.get('presentation',{}).get('all_eight_kpis_in_first_viewport') for v in viewports.values()), 'Overview KPIs must fit the first viewport'
    assert api.get('commentary_numeric_parity') and set(api['commentary'])==set(state['dashboards']), 'All findings require numeric parity'
    assert set(browser['native_month_changes'])==set(state['commentary']['monthly_boards']), 'Monthly commentary must change on all four business-month boards'
    assert all(board.get('commentary',{}).get('three_answers_visible') for board in browser['dashboards'].values()), 'Visible narrative proof required'
    assert all(board.get('presentation',{}).get('repeated_panels_absent') for board in browser['dashboards'].values()), 'Business presentation proof required on every page'
    assert set(api['methodology'])==set(state['dashboards']), 'Methodology must remain available outside the main layout'
    outputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}
    screenshots_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (evidence/'screenshots').glob('*.png')}
    manifest={'release_id':state['release_id'],'engine':state['engine'],'dashboards':state['links'],
              'charts':len(state['charts']),'analysis_cutoff':results['analysis_cutoff'],'selected_month':state['month'],
              'catalog_sha256':state['catalog_sha256'],'entry_url':state['experience']['entry_url'],
              'navigation':{'actual_clicks':14,'month_and_release_preserved':True,
                            'fixed_customer_trust_scope_preserved':browser['navigation_clicks']['fixed_scopes_preserved'],
                            'viewport_checks':{width:{**check,'screenshot':'docs/evidence/superset/screenshots/'+Path(check['screenshot']).name}
                                               for width,check in browser['navigation_clicks']['viewport_checks'].items()}},
              'metadata_idempotency':api['idempotency'],
              'report':'output/analysis/business-analysis.md','notebook':'output/analysis/analysis.ipynb',
              'commentary':{'implementation':'bi/superset_narratives.py','numeric_parity':True,
                            'native_month_changes':browser['native_month_changes'],
                            'answers_per_page':3,'guides_on_all_pages':False,
                            'methodology_location':'chart descriptions and docs; technical provenance on trust page',
                            'repeated_instructional_panels_absent':True,
                            'publication_drill_scope':'Historical proof: original 10 sales charts; new narrative tables verified by pinned SQL/API/native filters.'},
              'evidence_sha256':hashes,'output_sha256':outputs,'screenshot_sha256':screenshots_sha,
              'data_license':'Olist CC BY-NC-SA 4.0; derived data retains attribution and applicable terms'}
    (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'packaged':str(target),'charts':manifest['charts'],'evidence':str(evidence)}))


if __name__=='__main__':main()
