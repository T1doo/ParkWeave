from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as E
root=Path.cwd();base=root/'.runtime/native-run-access-writer-20261012';label=sys.argv[1];out=base/label;assert not out.exists();out.mkdir()
paths=subprocess.check_output(['rg','--files','src','tests','scripts','.github']).decode().splitlines()+['pyproject.toml','docs/F2/NativeRunAccessWriterContract.md']
paths=sorted(set(p for p in paths if '__pycache__' not in p and (p.endswith(('.py','.js','.sql','.html','.ps1','.json','.toml','.yml','.md')))))
sha=lambda b:hashlib.sha256(b).hexdigest();snapshot=lambda:{p:sha((root/p).read_bytes()) for p in paths}
before=snapshot();(out/'source-before.json').write_text(json.dumps(before,indent=2)+'\n');env=dict(os.environ);env['PARKWEAVE_WRITER_EVIDENCE_DIR']=str(out/'observations');env['PARKWEAVE_T07_EVIDENCE_DIR']=str(out/'t07-observations');env['PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR']=str(out/'activation-observations');(out/'runner-at-window.py').write_bytes(Path(__file__).read_bytes())
argv=[str(root/'.venv/bin/python'),'-m','pytest',*sys.argv[2:],'--junitxml='+str(out/'results.xml'),'-q']
start=datetime.now(timezone.utc).isoformat();tick=time.monotonic()
with (out/'stdout.log').open('w') as log:
 process=subprocess.Popen(argv,env=env,stdout=log,stderr=subprocess.STDOUT);(out/'running.json').write_text(json.dumps(dict(argv=argv,pid=process.pid,start_utc=start),indent=2)+'\n');code=process.wait()
after=snapshot();(out/'source-after.json').write_text(json.dumps(after,indent=2)+'\n');rows=[]
if (out/'results.xml').exists():
 for t in E.parse(out/'results.xml').iter('testcase'):
  status='FAIL' if t.find('failure') is not None else 'ERROR' if t.find('error') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS';rows.append({'classname':t.get('classname'),'name':t.get('name'),'status':status})
counts=dict(Counter(r['status'] for r in rows));result=dict(argv=argv,pid=process.pid,source_head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),source_files=len(before),source_manifest_sha256=sha(json.dumps(before,sort_keys=True).encode()),source_drift=[p for p in before if before[p]!=after[p]],start_utc=start,end_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-tick,exit_code=code,counts=counts,junit_ids=len(rows),outcomes=rows,artifacts_sha256={f:sha((out/f).read_bytes()) for f in ['results.xml','stdout.log'] if (out/f).exists()},scope='OWNED_SYNTHETIC_REFERENCE_WRITER_PG_ASGI_SUBPROCESSES',production_installation=False,production_privilege_changes=False,browser_attempts=0,formal_AT35=False)
(out/'run.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['outcomes','argv']}));sys.exit(code)
