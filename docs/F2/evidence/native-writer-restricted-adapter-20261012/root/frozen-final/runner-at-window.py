from pathlib import Path
import hashlib,json,subprocess,time,os
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');own=root/'.runtime/native-writer-restricted-adapter-root-20261012';out=own/'frozen-final';out.mkdir(exist_ok=False)
expected=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
def put(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def capture():
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert head==expected
 tree=subprocess.check_output(['git','ls-tree','-r','--format=%(objectname) %(path)','HEAD'],cwd=root,text=True)
 objects={p:oid for oid,p in (r.split(' ',1) for r in tree.splitlines())}
 paths=sorted(p for p in objects if p.startswith(('src/','tests/','scripts/','.github/workflows/')) or p=='pyproject.toml')+['docs/F2/NativeRunAccessWriterContract.md','docs/F2/NativeRunAccessWriterInstallationPlan.md']
 hashes={}
 for p in paths:
  raw=(root/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==objects[p],p
  hashes[p]=hashlib.sha256(raw).hexdigest()
 return dict(source_sha=head,files=hashes,file_count=len(hashes),git_status=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True))
before=capture();put(out/'source-before.json',before)
old=json.loads((own/'frozen-original/run.json').read_text());argv=[a.replace('/frozen-original/','/frozen-final/') for a in old['argv']]
(out/'runner-at-window.py').write_bytes(Path(__file__).read_bytes())
start=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
with (out/'pytest.log').open('wb') as f:
 result=subprocess.run(argv,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT)
after=capture();put(out/'source-after.json',after)
cases=[]
for e in ET.parse(out/'results.xml').getroot().iter('testcase'):
 state='ERROR' if e.find('error') is not None else 'FAIL' if e.find('failure') is not None else 'SKIP' if e.find('skipped') is not None else 'PASS'
 cases.append(dict(classname=e.get('classname'),name=e.get('name'),time=e.get('time'),outcome=state))
counts={s:sum(c['outcome']==s for c in cases) for s in ['PASS','FAIL','ERROR','SKIP']}
record=dict(source_sha=expected,argv=argv,started_utc=start,ended_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-clock,exit_code=result.returncode,source_files=before['file_count'],source_drift=before!=after,counts=counts,cases=cases,unique_test_ids=len({(c['classname'],c['name']) for c in cases}),excluded_actual_PG_tests=old['excluded_actual_PG_tests'],actual_PG_connections=0,actual_writer_or_service_starts=0,actual_permission_or_credential_changes=False,browser_attempts=0,qualification=old['qualification'])
put(out/'run.json',record);print(json.dumps({k:record[k] for k in ['source_sha','exit_code','source_files','source_drift','counts','unique_test_ids','seconds']}));print((out/'pytest.log').read_text()[-2400:]);assert not record['source_drift'];raise SystemExit(result.returncode)
