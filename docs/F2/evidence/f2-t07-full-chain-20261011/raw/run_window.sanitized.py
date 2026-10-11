"""Capture separate actual pytest windows; never overwrite raw failures."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, os, subprocess, sys, time, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
name=sys.argv[1];modules=sys.argv[2:]
old=ROOT/'.runtime/case-cancel-after-receipt'
if modules==['--full']:
    modules=[a for a in json.loads((old/'full-final-run.json').read_text())['argv'] if a.startswith('tests/')]
    modules.append('tests/test_f2_t07_full_chain.py')
assert modules and all(m.startswith('tests/') for m in modules)
assert not (OUT/(name+'.log')).exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=set(json.loads((old/'final-source-manifest.json').read_text()))
paths.update(str(p) for d in ['src','tests','scripts'] for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.js','.html','.sql','.json','.ps1','.txt'] for p in [p.relative_to(ROOT)])
before={p:sha(ROOT/p) for p in sorted(paths)}
manifest=OUT/(name+'-source-manifest.json');manifest.write_text(json.dumps(before,indent=2,sort_keys=True)+'\n')
status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
argv=[str(ROOT/'.venv/bin/python'),'-m','pytest',*modules,'-q','--tb=short','--junitxml='+str(OUT/(name+'.xml'))]
record=dict(started_at_utc=datetime.now(timezone.utc).isoformat(),base_git_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),uncommitted_source=bool(status),source_manifest_sha256=sha(manifest),source_file_count=len(before),complete_module_count=len(modules) if not any('::' in m for m in modules) else None,argv=argv,browser_attempts=0,driver_sha256=sha(Path(__file__)))
record['source_sha']=None if status else record['base_git_sha']
run=OUT/(name+'-run.json');run.write_text(json.dumps(record,indent=2)+'\n')
env=dict(os.environ,PARKWEAVE_T07_EVIDENCE_DIR=str(OUT/'windows'/name))
started=time.monotonic()
with (OUT/(name+'.log')).open('wb') as f:
    child=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
    record['pytest_pid']=child.pid;run.write_text(json.dumps(record,indent=2)+'\n');code=child.wait()
record.update(exit_code=code,ended_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=round(time.monotonic()-started,3),source_drift=[p for p,h in before.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h],log_sha256=sha(OUT/(name+'.log')))
if (OUT/(name+'.xml')).exists():
    cases=ET.parse(OUT/(name+'.xml')).getroot().findall('.//testcase')
    identity=lambda c:c.attrib.get('classname','')+'::'+c.attrib['name']
    state=lambda c:'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
    counts=Counter(state(c) for c in cases);ids={identity(c) for c in cases}
    record.update({k:counts.get(k,0) for k in ['PASS','FAIL','ERROR','SKIP']});record.update(tests=len(cases),unique_test_id_count=len(ids),xml_sha256=sha(OUT/(name+'.xml')),failed_ids=[identity(c) for c in cases if state(c) in ['FAIL','ERROR']])
    if name.startswith('full'):
        prior={identity(c) for c in ET.parse(old/'full-final.xml').getroot().findall('.//testcase')}
        record.update(prior_test_ids_missing=sorted(prior-ids),new_test_id_count=len(ids-prior))
record['atexit_cleanup_diagnostic']='Exception ignored in atexit' in (OUT/(name+'.log')).read_text(errors='replace')
run.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2),flush=True)
sys.exit(code or (1 if record['source_drift'] else 0))
