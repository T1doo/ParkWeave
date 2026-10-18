from pathlib import Path
from io import BytesIO
import hashlib,json,os,re,subprocess,tarfile,tempfile,time,zipfile
R=Path.cwd();D=R/'.runtime/local-synthetic-experience-package-20261018'
S='c047b9683f6808c9e22f2badf891695f2112b7fd';PY=R/'.venv/bin/python'
Z=R/'deliverables/local-synthetic-demo/ParkWeave-LOCAL-SYNTHETIC-c047b9683f68.zip'
def digest(b):return hashlib.sha256(b).hexdigest()
def archive_files(paths):
    raw=subprocess.check_output(['git','archive','--format=tar',S,'--',*paths],cwd=R)
    with tarfile.open(fileobj=BytesIO(raw)) as a:
        return {m.name:a.extractfile(m).read() for m in a if m.isfile()}
payload_paths=['src/parkweave','pyproject.toml','scripts/demo_preflight.py','scripts/package_local_synthetic_demo.py','docs/demo/LocalSyntheticExperience.md','docs/demo/LocalSyntheticWalk.html','docs/F2/LocalSyntheticDemoContract-20261017.md']
expected=archive_files(payload_paths)
with zipfile.ZipFile(Z) as a:
    assert a.testzip() is None
    assert len(a.namelist())==len(set(a.namelist()))==188
    payload={name:a.read(name) for name in a.namelist()}
bundle=json.loads(payload['BUNDLE.json']);assert bundle['source_commit']==S
assert set(payload)==set(expected)|{'BUNDLE.json','START_HERE.txt','Comparison.txt','SHA256SUMS'}
assert len(expected)==184
for name,raw in expected.items():
    assert raw==payload[name]
    assert bundle['tracked_source_files'][name]==dict(bytes=len(raw),sha256=digest(raw))
sums={line[66:]:line[:64] for line in payload['SHA256SUMS'].decode().splitlines()}
assert set(sums)==set(payload)-{'SHA256SUMS'}
for name,sha in sums.items():assert digest(payload[name])==sha
assert not any(any(part in ('.git','.runtime','.env','node_modules','PGDATA') for part in Path(name).parts) for name in payload)
environment={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE_')}
environment['PYTHONDONTWRITEBYTECODE']='1'
testroot=Path(tempfile.mkdtemp(prefix='parkweave-package-tests-'))
testfiles=archive_files(['src','scripts','tests/test_demo_preflight.py','docs/demo','docs/首次体验.md','docs/F2/LocalSyntheticDemoContract-20261017.md','pyproject.toml'])
for name,raw in testfiles.items():
    target=testroot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
environment['PYTHONPATH']=str(testroot/'src')
def invoke(name,argv,cwd,expected_exit):
    start=time.monotonic();p=subprocess.run(argv,cwd=cwd,env=environment,capture_output=True,text=True,timeout=30)
    (D/(name+'.stdout')).write_text(p.stdout);(D/(name+'.stderr')).write_text(p.stderr)
    result=dict(name=name,argv=[str(s) for s in argv],cwd=str(cwd),exit_code=p.returncode,elapsed_seconds=time.monotonic()-start)
    (D/(name+'-invocation.json')).write_text(json.dumps(result,indent=2)+'\n')
    assert p.returncode==expected_exit,(name,p.returncode)
    return p,result
p,unit=invoke('root-frozen-unittest',[PY,'tests/test_demo_preflight.py','-v'],testroot,0)
assert 'Ran 13 tests' in p.stderr and p.stderr.rstrip().endswith('OK')
nodes=re.findall(r'^(test_\w+) \(([^)]+)\) \.\.\. ok$',p.stderr,re.M);assert len(nodes)==13
unit.update(tests=13,passed=13,failed=0,errors=0,skipped=0,nodes=[n[1] for n in nodes],source_commit=S)
(D/'root-unit-result.json').write_text(json.dumps(unit,indent=2)+'\n')
extract=Path(tempfile.mkdtemp(prefix='parkweave-package-extracted-'))
for name,raw in payload.items():
    target=extract/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
environment['PYTHONPATH']=str(extract/'src')
before={str(p.relative_to(extract)):digest(p.read_bytes()) for p in extract.rglob('*') if p.is_file()}
commands=[]
for name,argv in [
 ('package-inventory',[PY,'scripts/demo_preflight.py','--local-synthetic','--json']),
 ('package-explicit-missing-probe',[PY,'scripts/demo_preflight.py','--local-synthetic','--check-existing-inputs','--json'])]:
    p,result=invoke(name,argv,extract,2);report=json.loads(p.stdout)
    assert report['status']=='BLOCKED_MISSING_EXISTING_INPUTS' and len(report['missing_input_names'])==4
    assert report['inventory_complete'] and report['database']=='NOT_PROBED' and report['business_ready'] is False
    assert report['model_calls_by_this_tool']==0
    commands.append(result|dict(status=report['status'],database=report['database']))
p,result=invoke('package-api-start-refusal',[PY,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port','8765'],extract,1)
assert 'PARKWEAVE_DSN required; no credential discovery' in p.stderr
assert 'Application startup complete' not in p.stderr
commands.append(result|dict(status='ORIGINAL_FACTORY_MISSING_DSN_REFUSAL'))
p,result=invoke('package-worker-start-refusal',[PY,'-m','parkweave.worker'],extract,2)
assert 'PARKWEAVE_DSN required' in p.stderr
commands.append(result|dict(status='ORIGINAL_WORKER_MISSING_DSN_REFUSAL'))
after={str(p.relative_to(extract)):digest(p.read_bytes()) for p in extract.rglob('*') if p.is_file()}
assert before==after
repeat=D/'repeat-source-package.zip'
p,result=invoke('reproducible-build',[PY,R/'scripts/package_local_synthetic_demo.py','--commit',S,'--output',repeat],R,0)
assert repeat.read_bytes()==Z.read_bytes()
result=dict(source_commit=S,zip_sha256=digest(Z.read_bytes()),zip_bytes=Z.stat().st_size,entries=len(payload),source_entries=len(expected),original_package_files=sum(n.startswith('src/parkweave/') for n in expected),source_bytes_match_frozen_commit=True,all_internal_sha256_valid=True,no_private_runtime_payload=True,reproducible_zip_bytes=True,extracted_payload_unchanged_after_checks=True,root_unit=unit,checks=commands,positive_existing_input_probe='NOT_RUN_MISSING_LEGAL_INPUTS',business_browser='NOT_RUN',windows_formal_at='NOT_RUN',real_business='NOT_RUN',test_root=str(testroot),extract_root=str(extract))
(D/'package-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
