from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,time,xml.etree.ElementTree as ET
root=Path('.runtime/native-run-access-20261011')
def manifest():
 paths=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml','requirements-linux-evidence.txt'],text=True).splitlines()
 return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(paths)}
def now():return datetime.now(timezone.utc).isoformat()
source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
before=manifest();(root/'frozen-source-manifest.json').write_text(json.dumps(before,sort_keys=True,indent=2)+'\n')
scope=json.loads((root/'full-module-scope.json').read_text())
argv=['.venv/bin/python','-m','pytest',*scope['modules'],'-q','--tb=short','--junitxml='+str(root/'full-final.xml')]
record=dict(source_sha=source_sha,started_at_utc=now(),source_file_count=len(before),module_count=len(scope['modules']),argv=argv,browser_attempts=0,source_manifest_sha256=hashlib.sha256((root/'frozen-source-manifest.json').read_bytes()).hexdigest())
start=time.monotonic()
with (root/'full-final.log').open('w') as log:
 p=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT)
 record['pid']=p.pid;(root/'full-final-run.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record),flush=True)
 rc=p.wait()
record.update(exit_code=rc,ended_at_utc=now(),elapsed_seconds=round(time.monotonic()-start,3))
after=manifest();record['source_drift']=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
(root/'frozen-source-after-manifest.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
xml=root/'full-final.xml'
if xml.exists():
 cases=ET.parse(xml).getroot().findall('.//testcase')
 ids=[t.attrib.get('classname','')+'::'+t.attrib['name'] for t in cases]
 record.update(tests=len(cases),unique_test_id_count=len(set(ids)),FAIL=sum(t.find('failure') is not None for t in cases),ERROR=sum(t.find('error') is not None for t in cases),SKIP=sum(t.find('skipped') is not None for t in cases))
 record['PASS']=len(cases)-record['FAIL']-record['ERROR']-record['SKIP']
 record['failed_ids']=[i for t,i in zip(cases,ids) if t.find('failure') is not None or t.find('error') is not None]
 (root/'full-final-test-ids.json').write_text(json.dumps(ids,indent=2)+'\n')
 record['xml_sha256']=hashlib.sha256(xml.read_bytes()).hexdigest()
record['log_sha256']=hashlib.sha256((root/'full-final.log').read_bytes()).hexdigest()
(root/'full-final-run.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
raise SystemExit(rc if not record['source_drift'] else 2)
