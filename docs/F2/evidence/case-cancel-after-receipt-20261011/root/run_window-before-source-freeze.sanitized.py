"""Actual pytest windows with immutable raw logs and source-byte timing records."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
name=sys.argv[1];modules=sys.argv[2:]
old=ROOT/'docs/F2/evidence/case-cancel-before-receipt-20261011'
if modules==['--full']:
 modules=[a for a in json.loads((old/'full-final-run.json').read_text())['argv'] if a.startswith('tests/')]
 modules.append('tests/test_case_cancellation_reconciliation.py')
assert modules and all(m.startswith('tests/') for m in modules)
assert not (OUT/(name+'.log')).exists(), 'never overwrite an actual prior window'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=set(json.loads((old/'final-source-manifest.json').read_text()))
paths.update(str(p) for d in ['src','tests','scripts'] for p in Path(d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.js','.html','.sql','.json','.ps1','.txt'])
before={p:sha(ROOT/p) for p in sorted(paths)}
manifest=OUT/(name+'-source-manifest.json');manifest.write_text(json.dumps(before,indent=2,sort_keys=True)+'\n')
status=subprocess.check_output(['git','status','--porcelain'],text=True)
argv=[str(ROOT/'.venv/bin/python'),'-m','pytest',*modules,'-q','--tb=short','--junitxml='+str(OUT/(name+'.xml'))]
record={'started_at_utc':datetime.now(timezone.utc).isoformat(),'base_git_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'uncommitted_source':bool(status),'source_manifest_sha256':sha(manifest),'source_file_count':len(before),'module_count':len(modules),'argv':argv,'browser_attempts':0}
run=OUT/(name+'-run.json');run.write_text(json.dumps(record,indent=2)+'\n');started=time.monotonic()
with (OUT/(name+'.log')).open('wb') as f:
 child=subprocess.Popen(argv,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 record['pytest_pid']=child.pid;run.write_text(json.dumps(record,indent=2)+'\n');code=child.wait()
record.update(exit_code=code,ended_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=round(time.monotonic()-started,3),source_drift=[p for p,h in before.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h],log_sha256=sha(OUT/(name+'.log')))
xml=OUT/(name+'.xml')
if xml.exists():
 cases=ET.parse(xml).getroot().findall('.//testcase')
 def identity(c):return c.attrib.get('classname','')+'::'+c.attrib['name']
 def state(c):return 'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
 counts=Counter(state(c) for c in cases);ids={identity(c) for c in cases}
 record.update({k:counts.get(k,0) for k in ('PASS','FAIL','ERROR','SKIP')});record.update(tests=len(cases),unique_test_id_count=len(ids),xml_sha256=sha(xml),failed_ids=[identity(c) for c in cases if state(c) in ('FAIL','ERROR')])
 if name.startswith('full'):
  previous={identity(c) for c in ET.parse(old/'root/full-final.sanitized.xml').getroot().findall('.//testcase')}
  record.update(prior_test_ids_missing=sorted(previous-ids),new_test_id_count=len(ids-previous))
record['atexit_cleanup_diagnostic']='Exception ignored in atexit' in (OUT/(name+'.log')).read_text(errors='replace')
run.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2),flush=True)
sys.exit(code or (1 if record['source_drift'] else 0))
