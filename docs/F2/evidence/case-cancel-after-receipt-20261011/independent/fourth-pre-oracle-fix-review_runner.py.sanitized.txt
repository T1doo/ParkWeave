"""Independent owned-fixture runner; captures raw output and source drift."""
import os,sys,json,hashlib,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave')
OUT=ROOT/'.runtime/case-cancel-after-receipt/independent-review'
FREEZE=Path(os.environ['PARKWEAVE_INDEPENDENT_REVIEW_MANIFEST'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def drift(m):return [p for p,h in m.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
name=sys.argv[1];modules=sys.argv[2:];manifest=json.loads(FREEZE.read_text());before=drift(manifest)
for suffix in ('-source-manifest.json','.xml','.log','-run.json'):
 if (OUT/(name+suffix)).exists():raise SystemExit('refuse to overwrite prior window '+name)
(OUT/(name+'-source-manifest.json')).write_bytes(FREEZE.read_bytes())
argv=[str(ROOT/'.venv/bin/python'),'-m','pytest',*modules,'-q','--tb=short','-p','no:cacheprovider','--junitxml='+str(OUT/(name+'.xml'))]
record={'phase':name,'source_head_parent_reported':os.environ.get('PARKWEAVE_INDEPENDENT_SOURCE_SHA','NOT_FINAL_UNCOMMITTED_WINDOW'),'source_manifest_sha256':sha(FREEZE),'source_file_count':len(manifest),'argv':argv,'source_drift_before':before,'started_utc':datetime.now(timezone.utc).isoformat(),'owned_fixture':'fresh independent pytest process using original conftest; no inherited DSN or parent DB','browser_attempts':0}
if before:raise SystemExit('frozen source drift before independent test window')
started=time.monotonic();env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=str(ROOT/'tests')+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
with (OUT/(name+'.log')).open('xb') as output:
 child=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT);record['pytest_pid']=child.pid
 (OUT/(name+'-run.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 record['exit_code']=child.wait()
record.update(elapsed_seconds=round(time.monotonic()-started,3),ended_utc=datetime.now(timezone.utc).isoformat(),source_drift_after=drift(manifest),log_sha256=sha(OUT/(name+'.log')))
xml=OUT/(name+'.xml')
if xml.exists():
 record['xml_sha256']=sha(xml);tests=list(ET.parse(xml).getroot().iter('testcase'))
 def status(x):return 'FAIL' if x.find('failure') is not None else 'ERROR' if x.find('error') is not None else 'SKIP' if x.find('skipped') is not None else 'PASS'
 record.update(tests=len(tests),unique_ids=len({x.attrib.get('classname','')+'::'+x.attrib['name']for x in tests}),**{s:sum(status(x)==s for x in tests)for s in ['PASS','FAIL','ERROR','SKIP']})
 record['failures']=[{'id':x.attrib.get('classname','')+'::'+x.attrib['name'],'outcome':status(x)}for x in tests if status(x) in ['FAIL','ERROR']]
record['atexit_cleanup_diagnostic']='Exception ignored in atexit callback' in (OUT/(name+'.log')).read_text(errors='replace')
(OUT/(name+'-run.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='argv'},ensure_ascii=False))
sys.exit(record['exit_code'] or bool(record['source_drift_after']))
