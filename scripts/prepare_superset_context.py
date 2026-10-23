"""Resolve publication once before generating release-specific BI assets."""
import json
from sales_dw.config import ROOT, connect

with connect('publish') as c:
    row=c.execute("SELECT p.release_id,r.pipeline_run_id,r.source_cut FROM ops.published_release p JOIN ops.releases r USING(release_id) WHERE p.channel='main' AND r.state='published'").fetchone()
    assert row, 'A published release is required'
(ROOT/'var/bi/superset-context.json').write_text(json.dumps(row,default=str,indent=2)+'\n')
print('Pinned BI context:', row['release_id'])
