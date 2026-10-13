from pathlib import Path
import hashlib,json,subprocess,time,os
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
root=Path.cwd();out=root/'.runtime/catalog-only-candidate-20261013/final-candidate';out.mkdir(exist_ok=False)
expected='17cf9cdbff28ae759e68b7f66878e1c396ec6f0d'
def put(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def capture():
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==expected
 objects={p:oid for oid,p in (r.split(' ',1) for r in subprocess.check_output(['git','ls-tree','-r','--format=%(objectname) %(path)',expected],text=True).splitlines())}
 files={}
 for p,oid in objects.items():
  if p.startswith(('src/','tests/','scripts/','.github/workflows/')) or p=='pyproject.toml':
   raw=(root/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid,p;files[p]=hashlib.sha256(raw).hexdigest()
 return dict(head=expected,files=files,git_status=subprocess.check_output(['git','status','--porcelain'],text=True))
before=capture();put(out/'source-before.json',before);clock=time.monotonic();start=datetime.now(timezone.utc).isoformat()
argv=[str(root/'.venv/bin/python'),'-m','pytest','tests/test_catalog_only_candidate.py','tests/test_linux_trial_catalog.py','tests/test_native_run_access_preflight.py','tests/test_restricted_linux_trial_contract.py','tests/test_native_run_access_restricted_adapter.py','tests/test_ci_diagnostics.py','-q','-p','no:cacheprovider','-p','offline_guard','--tb=short','--junitxml='+str(out/'results.xml')]
with (out/'pytest.log').open('wb') as f:r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(root/'.runtime/catalog-only-candidate-20261013'),PW_CATALOG_NOT_RUN_PATH=str(out/'physical-not-run.json')))
after=capture();put(out/'source-after.json',after);counts={s:0 for s in ['PASS','FAIL','ERROR','SKIP']};cases=[]
for e in ET.parse(out/'results.xml').getroot().iter('testcase'):
 s='ERROR' if e.find('error') is not None else 'FAIL' if e.find('failure') is not None else 'SKIP' if e.find('skipped') is not None else 'PASS';counts[s]+=1;cases.append(dict(classname=e.get('classname'),name=e.get('name'),time=e.get('time'),outcome=s))
record=dict(source_sha=expected,argv=argv,started_utc=start,ended_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-clock,exit_code=r.returncode,counts=counts,cases=cases,source_file_count=len(before['files']),source_drift=before!=after,qualification='PURE_CONTRACT_AND_DI_ONLY; GitHub trigger/VM/trial NOT_RUN',actual_trial_triggers=0,actual_PG_connections=0,actual_privilege_changes=0)
put(out/'run.json',record);print(json.dumps({k:record[k] for k in ['source_sha','exit_code','counts','source_file_count','source_drift','seconds']}));assert before==after;raise SystemExit(r.returncode)
