"""Execute the portable CSV-reading notebook and record actual cell completion."""
import json
import importlib.metadata
import hashlib
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'output/analysis'
path=folder/'analysis.ipynb'
notebook=nbformat.read(path,as_version=4)
NotebookClient(notebook,timeout=90,kernel_name='python3',resources={'metadata':{'path':str(folder)}}).execute()
nbformat.write(notebook,path)
nbformat.write(notebook,ROOT/'var/analysis/analysis.ipynb')
cells=[c for c in notebook.cells if c.cell_type=='code']
assert len(cells)==9 and all(c.execution_count is not None for c in cells)
assert not any(o.output_type=='error' for c in cells for o in c.outputs)
proof={'passed':True,'code_cells_executed':len(cells),'scope':'Portable notebook reads the already SQL-verified CSV extracts; no DB secrets needed','path':str(path.relative_to(ROOT)),
       'notebook_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'release_id':json.loads((folder/'results.json').read_text())['release']['release_id'],
       'tool_versions':{p:importlib.metadata.version(p) for p in ('nbclient','nbformat','ipykernel')}}
(ROOT/'var/evidence/notebook.json').write_text(json.dumps(proof,indent=2)+'\n')
(ROOT/'docs/evidence/superset/notebook.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof))
