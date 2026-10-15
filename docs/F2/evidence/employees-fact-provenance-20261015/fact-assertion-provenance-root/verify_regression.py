"""Final whole-module selection and immutable-input verification."""
from pathlib import Path
import json,subprocess,hashlib
base=Path('.runtime/fact-provenance-final');root=Path('.runtime/fact-assertion-provenance-root')
freeze=json.loads((root/'freeze.json').read_text());selection=json.loads((base/'selection.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==freeze['source_sha']
records={};nodes=[];modules=[]
for name,expected in selection['main_windows'].items():
 d=json.loads((base/(name+'.json')).read_text());assert d['modules']==expected and d['source_sha']==freeze['source_sha']
 assert d['exit_code']==0 and d['counts']['FAIL']==d['counts']['ERROR']==d['counts']['SKIP']==0
 assert not d['source_drift'] and not d['all_tracked_drift'] and not d['runner_drift']
 assert d['collection_junit_exact_match'] and d['unique_junit_nodes']
 assert len(d['collected_nodes'])==d['counts']['PASS'];nodes.extend(d['collected_nodes']);modules.extend(d['modules'])
 records[name]=dict(passes=d['counts']['PASS'],modules=len(d['modules']),elapsed_seconds=d['elapsed_seconds'],receipt=str(base/(name+'.json')))
assert len(modules)==len(set(modules))==103 and len(nodes)==len(set(nodes))
assert records['new']['passes']==61
ci=json.loads((base/'ci-metadata.json').read_text());assert ci['exit_code']==0 and ci['source_sha']==freeze['source_sha'] and not ci['source_drift'] and not ci['all_tracked_drift'] and ci['collection_junit_exact_match']
assert not ci['counts']['FAIL'] and not ci['counts']['ERROR']
for name,h in freeze['source_paths'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
for name,h in freeze['all_tracked_sha256'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
for name,h in freeze['runner_paths'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
record=dict(status='PASS',source_sha=freeze['source_sha'],modules=103,unique_passes=len(nodes),new_passes=61,windows=records,separate_ci=dict(modules=len(ci['modules']),counts=ci['counts'],receipt=str(base/'ci-metadata.json')),source_paths=len(freeze['source_paths']),all_tracked_paths=len(freeze['all_tracked_sha256']),runner_paths=4,all_inputs_stable=True,scope='Whole affected module selection; not the whole repository. New61 include4 actual HTTP HTML cases and1 controlled-client pytest with5 branches. Separate independent pure38 are repeated review evidence, not added.')
(root/'final-regression-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
