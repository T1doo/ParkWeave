from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,collections,datetime,subprocess
p=Path('/workspace/ParkWeave/.runtime/specialist-material-review');root=p.parents[1]
f=json.loads((p/'freeze.json').read_text());m=json.loads((p/'final-v1-invocation.json').read_text());assert m['exit_code']==0 and m['source_sha']==f['source_sha'] and m['uncommitted_source_diff_sha256']==hashlib.sha256(b'').hexdigest()
r=ET.parse(p/'final-v1.xml').getroot();cases=r.findall('.//testcase');nodes=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases];expected=json.loads((p/'final-nodes.json').read_text());assert nodes==expected and len(nodes)==len(set(nodes))==267
assert not r.findall('.//failure') and not r.findall('.//error') and not r.findall('.//skipped')
assert all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in f['files'].items());assert hashlib.sha256((root/'docs/F2/SpecialistMaterialReviewContract-20261017.md').read_bytes()).hexdigest()==f['contract_sha256']
old=json.loads((p/'inherited-evidence-blobs.json').read_text())
for n,h in old.items():
 b=(root/n).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==h
assert subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)==''
seconds=sum(float(s.get('time')) for s in r.findall('.//testsuite'));counts=dict(collections.Counter(n.split('::')[0] for n in nodes));assert counts['tests/test_material_review_comparison.py']==30 and counts['tests/test_material_review_comparison_browser.py']==22
v=dict(source_sha=f['source_sha'],testcases=267,unique=267,passed=267,failures=0,errors=0,skipped=0,JUnit_seconds=seconds,modules=counts,source_inputs=len(f['files']),source_drift=0,contract_drift=0,inherited_F2_git_blobs_checked=len(old),inherited_F2_drift=0,worktree_porcelain='',closed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),real_business_and_Windows_formal_AT=False)
(p/'final-validation.json').write_text(json.dumps(v,indent=2)+'\n');l=json.loads((p/'failure-ledger.json').read_text());l['windows']['final-v1']=dict(testcases=267,passed=267,failures=0,errors=0,seconds=seconds,scope='Exact frozen source, all12 selected complete modules; new52 included; no WIP/probe counts added');(p/'failure-ledger.json').write_text(json.dumps(l,ensure_ascii=False,indent=2)+'\n')
x=json.loads((p/'continuation.json').read_text());x.update(state='VALIDATED_NOT_YET_DELIVERED',full_regression_pending=False,final_unique=267,new_unique=52,remote_push_pending=True);(p/'continuation.json').write_text(json.dumps(x,indent=2)+'\n');(p/'continuation-at-final-validation.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(v))
