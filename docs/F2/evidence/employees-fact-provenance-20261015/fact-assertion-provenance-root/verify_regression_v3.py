"""Whole-module effective selection; preserve complete failed attempts separately."""
from pathlib import Path
import json,subprocess,hashlib,xml.etree.ElementTree as ET,collections
B=Path('.runtime/fact-provenance-final-v2');R=Path('.runtime/fact-assertion-provenance-root')
load=lambda p:json.loads(p.read_text());freeze=load(R/'freeze-v2.json');planned=load(B/'selection.json');chosen=load(B/'final-main-selection.json')
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==freeze['source_sha']
expected=sum(planned['main_windows'].values(),[]);assert len(expected)==len(set(expected))==103

def identity(c):
 parts=c.get('classname','').split('.');pos=next(i for i,v in enumerate(parts) if v.startswith('test_'))
 return 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[c.get('name')])

def read(name):
 d=load(B/(name+'.json'));assert d['source_sha']==freeze['source_sha']
 assert not d['source_drift'] and not d['all_tracked_drift'] and not d['runner_drift']
 assert d['collection_junit_exact_match'] and d['unique_junit_nodes']
 assert load(B/(name+'-before.json'))==load(B/(name+'-after.json'))==freeze['source_paths']
 assert load(B/(name+'-all-tracked-before.json'))==load(B/(name+'-all-tracked-after.json'))==freeze['all_tracked_sha256']
 cases=list(ET.parse(B/(name+'.xml')).iter('testcase'));nodes={}
 for c in cases:
  n=identity(c);assert n not in nodes;nodes[n]='ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
 assert set(nodes)==set(d['collected_nodes']) and len(nodes)==len(d['collected_nodes'])
 assert collections.Counter(nodes.values())==collections.Counter({k:v for k,v in d['counts'].items() if v})
 return d,nodes

all_nodes={};all_modules=[];windows={}
for item in chosen:
 name=item['window'];selected=item['modules'];d,nodes=read(name)
 assert len(selected)==len(set(selected)) and set(selected)<=set(d['modules'])
 if set(selected)==set(d['modules']):assert d['exit_code']==0
 else:assert item.get('reason'),'whole-module exclusion must be explicit'
 subset={n:s for n,s in nodes.items() if n.split('::',1)[0] in selected}
 assert subset and set(subset.values())=={'PASS'} and {n.split('::',1)[0] for n in subset}==set(selected)
 assert not set(subset)&set(all_nodes);all_nodes.update(subset);all_modules.extend(selected)
 windows[name]=dict(passes=len(subset),modules=len(selected),elapsed_seconds=d['elapsed_seconds'],receipt=str(B/(name+'.json')),reason=item.get('reason'),raw_counts=d['counts'],raw_exit_code=d['exit_code'])
assert len(all_modules)==len(set(all_modules))==103 and set(all_modules)==set(expected)
new_set=set(planned['main_windows']['new']);new_nodes={n for n in all_nodes if n.split('::',1)[0] in new_set};assert len(new_nodes)==61
ci,ci_nodes=read('ci-metadata');assert ci['exit_code']==0 and set(ci_nodes.values())<={'PASS','SKIP'}
assert set(ci['modules'])==set(planned['separate_ci_window']) and not set(ci_nodes)&set(all_nodes)
for mapping in [freeze['source_paths'],freeze['all_tracked_sha256'],freeze['runner_paths']]:
 for p,h in mapping.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
record=dict(status='PASS',source_sha=freeze['source_sha'],modules=103,unique_passes=len(all_nodes),new_passes=61,windows=windows,separate_ci=dict(modules=len(ci['modules']),counts=ci['counts'],receipt=str(B/'ci-metadata.json')),source_paths=len(freeze['source_paths']),all_tracked_paths=len(freeze['all_tracked_sha256']),runner_paths=4,all_inputs_stable=True,effective_selection=chosen,scope='Whole affected modules only. Complete raw failed windows retained; replace whole module including its original passing cases, never cherry-pick test nodes. New61 and separate review38/client6 are not added twice.')
(R/'final-regression-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in {'windows','effective_selection'}}))
