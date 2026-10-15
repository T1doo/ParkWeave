from pathlib import Path
import hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as ET

ROOT=Path.cwd();BASE=ROOT/'.runtime/multifield-source-independent'
name=sys.argv[1];nodes=json.loads(Path(sys.argv[2]).read_text())
assert not (BASE/(name+'.log')).exists()
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
def manifest():
    paths={p for folder in ('src','tests','scripts') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    paths.add(ROOT/'pyproject.toml')
    paths.update((BASE/'work').glob('*.*'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()}
before=manifest();(BASE/(name+'-before.json')).write_text(json.dumps(before,indent=2)+'\n')
env=dict(os.environ,PYTHONPATH=str(BASE)+os.pathsep+str(ROOT/'tests')+os.pathsep+str(ROOT),
    XDG_CACHE_HOME=str(ROOT/'.runtime/xdg-cache'),AT_BATCH_WINDOW=name,AT_BATCH_ARTIFACT_ROOT=str(BASE/'artifacts'),
    TYPED_COLLECTION=str(BASE/(name+'-collection.json')),TYPED_PRIVATE=str(BASE/('redaction-'+name+'.private.json')),
    TYPED_HTTP=str(BASE/(name+'-http-traffic.json')))
fixture_plugin=[] if all(n.startswith('tests/') for n in nodes) else ['-p','conftest']
argv=[sys.executable,'-m','pytest','-q',*fixture_plugin,'-p','shared_capture',*nodes,
    '--basetemp=/tmp/parkweave-multifield-independent-'+name,'--junitxml='+str(BASE/(name+'.xml'))]
start=time.monotonic()
with (BASE/(name+'.log')).open('w') as stream:r=subprocess.run(argv,env=env,stdout=stream,stderr=subprocess.STDOUT)
after=manifest();(BASE/(name+'-after.json')).write_text(json.dumps(after,indent=2)+'\n')
counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
if (BASE/(name+'.xml')).exists():
    for c in ET.parse(BASE/(name+'.xml')).iter('testcase'):
        if not c.get('name') or not c.get('classname'):continue
        key='FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
        counts[key]+=1
result=dict(kind='DEVELOPMENT_WIP_NOT_FROZEN_GATE',source_sha=source,head_after=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    argv=argv,exit_code=r.returncode,counts=counts,elapsed_seconds=time.monotonic()-start,
    source_and_private_driver_paths=len(before),drift=[p for p in set(before)|set(after) if before.get(p)!=after.get(p)],
    real_model_calls=0,real_browser='NOT_RUN',Windows='NOT_RUN',production='NOT_RUN')
(BASE/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='argv'}));sys.exit(r.returncode)
