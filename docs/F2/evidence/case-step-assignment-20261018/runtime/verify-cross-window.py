from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
r=Path('/workspace/ParkWeave');raw=r/'.runtime/case-step-assignment-20261018';own=raw/'frozen-f6b76c5e';ind=r/'.runtime/case-step-assignments-20261018/independent';w=ind/'frozen-f6b76c5e-window2';first=ind/'frozen-f6b76c5e-window1';load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=load(own/'collection.json');items=load(w/'collection.json');b=[x['nodeid'] for x in items];assert len(a)==len(set(a))==124 and len(b)==len(set(b))==8
for phase in ('setup','call','teardown'):
 lines=[json.loads(s) for s in (w/'calls.jsonl').read_text().splitlines()];rows=[x for x in lines if x['when']==phase];assert len(rows)==8 and {x['nodeid'] for x in rows}==set(b) and all(x['outcome']=='passed' for x in rows)
x=ET.parse(w/'results.xml');assert len(x.findall('.//testcase'))==8 and not any(x.findall('.//'+k) for k in ('failure','error','skipped'))
assert {t.get('classname').replace('.','/')+'.py::'+t.get('name') for t in x.findall('.//testcase')}==set(b)
pre=load(own/'shared-before.json');assert len(pre)==789
for p in (first,w):
 for name in ('shared-before.json','shared-after.json','mirror-before.json','mirror-after.json'):assert load(p/name)==pre
 assert load(p/'independent-source-before.json')==load(p/'independent-source-after.json')
 report=load(p/'controller-result.json');assert report['actual_HEAD_at_start']==report['actual_HEAD_at_end']=='f6b76c5e030ffd7a055c7b4a3278bf911c05b4f1'
origins=load(w/'module-origins.json');private=load(w/'independent-source-before.json');proof=[]
for o in origins:
 path=Path(o['path']);assert o['within_mirror'] and sha(path)==o['sha256']
 expected=private['test_independent_case_step_probes.py'] if o['matches_independent_probe'] else pre[o['relative']]
 assert expected==o['sha256'];proof.append(o['name'])
old=ET.parse(first/'results.xml');oldcalls=[json.loads(l) for l in (first/'calls.jsonl').read_text().splitlines()];assert len(old.findall('.//error'))==8 and not old.findall('.//failure') and not [x for x in oldcalls if x['when']=='call']
overlap=sorted(set(a)&set(b));assert len(overlap)==3 and len(set(a)|set(b))==129
v=dict(tested_sha='f6b76c5e030ffd7a055c7b4a3278bf911c05b4f1',root_passed=124,independent_passed=8,independent_private_probes=5,overlap=overlap,overlap_count=3,final_unique_passed=129,final_failures=0,final_errors=0,final_skipped=0,root_and_independent_selected_inputs=789,all_input_maps_match=True,independent_origins=len(origins),independent_origin_hashes_verified=True,independent_source_before_after_equal=True,first_independent_window=dict(collection=8,setup_errors=8,actual_calls=0,business_failures=0,excluded_from_final_pass_counts=True,reason='controller basetemp outside required system /tmp; original proof correctly denied; single finite controller correction retained'))
(raw/'cross-window-verification.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
