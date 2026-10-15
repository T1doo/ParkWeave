from pathlib import Path
import hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/shared-source-cases-review';SHA='bc4f384fa32817ddf3b332f898d59b5b994bfe2f';prefix='schema-'+SHA[:8]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
paths=[p for p in subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml'],cwd=ROOT).decode().split('\0') if p]
paths += [str(p.relative_to(ROOT)) for p in (ROOT/'src/parkweave.egg-info').glob('*') if p.is_file()]
allpaths=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p]
def manifest(names):return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names}
def save(suffix,value):(OUT/(prefix+'-'+suffix+'.json')).write_text(json.dumps(value,indent=2)+'\n')
before=manifest(paths);full_before=manifest(allpaths);save('source-before',before);save('alltracked-before',full_before)
freeze=json.loads((ROOT/'.runtime/shared-source-cases/freeze.json').read_text());assert freeze['source_sha']==SHA and all(before[p]==v for p,v in freeze['hashes'].items())
probe=OUT/'test_graph_schema_probes.py';probe_sha=hashlib.sha256(probe.read_bytes()).hexdigest()
args=[sys.executable,'-m','pytest','-q','-p','shared_review_capture',str(probe),'--basetemp=/tmp/pw-shared-schema-'+SHA[:8],'--junitxml='+str(OUT/(prefix+'.xml'))]
env=os.environ.copy();env['PYTHONPATH']='.:src:tests:'+str(OUT)+os.pathsep+env.get('PYTHONPATH','');env['SHARED_REVIEW_COLLECTION']=str(OUT/(prefix+'-collection.json'));env['XDG_CACHE_HOME']=str(ROOT/'.runtime/xdg-cache')
start=time.monotonic()
with (OUT/(prefix+'.log')).open('w') as log:code=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
after=manifest(paths);full_after=manifest(allpaths);save('source-after',after);save('alltracked-after',full_after)
cases=list(ET.parse(OUT/(prefix+'.xml')).iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
for t in cases:counts['ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS']+=1
col=json.loads((OUT/(prefix+'-collection.json')).read_text());actual=[t.get('name') for t in cases]
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();suite=ET.parse(OUT/(prefix+'.xml')).getroot().find('testsuite')
r={'source_sha':SHA,'head_after':head,'argv':args,'module':str(probe.relative_to(ROOT)),'probe_sha256':probe_sha,'probe_unchanged':hashlib.sha256(probe.read_bytes()).hexdigest()==probe_sha,'counts':counts,'exit_code':code,'junit_seconds':float(suite.get('time')),'elapsed_seconds':time.monotonic()-start,'collected':len(col),'executed':len(cases),'same_invocation_test_names_exact':sorted(n.split('::',1)[1] for n in col)==sorted(actual),'source_manifest_paths':len(paths),'source_changes':[p for p in paths if before[p]!=after[p]],'alltracked_count':len(allpaths),'alltracked_before_after_equal':full_before==full_after,'separate_from_formal64_modules':True,'scope':'Injected future graph header negative seam over actual HTTP/ASGI/owned PG; not real browser/model/Windows/AT/production'}
save('result',r);print(json.dumps(r));sys.exit(code or int(head!=SHA or before!=after or full_before!=full_after or not r['probe_unchanged'] or not r['same_invocation_test_names_exact']))
