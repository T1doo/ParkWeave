from pathlib import Path
from hashlib import sha256
from io import BytesIO
import json,os,subprocess,tarfile,tempfile,time
R=Path.cwd();D=R/'.runtime/ordinary-runtime-write-20261018';S='d62cfb996b1377a92ab686bb4fa0c9a4362e9c20'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
raw=subprocess.check_output(['git','archive','--format=tar',S,'--','src','pyproject.toml','tests/test_ordinary_runtime_write.py','docs/F2/OrdinaryRuntimeWrite-20261018.md'])
mirror=Path(tempfile.mkdtemp(prefix='pw-root-ordinary-write-'));payload={}
with tarfile.open(fileobj=BytesIO(raw)) as archive:
 for m in archive:
  if not m.isfile():continue
  assert not m.name.startswith('/') and '..' not in Path(m.name).parts
  data=archive.extractfile(m).read();payload[m.name]=data;p=mirror/m.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
assert len(payload)==182
before={n:sha256(data).hexdigest() for n,data in payload.items()}
def verify():
 for n,data in payload.items():
  assert (R/n).read_bytes()==data,n
  assert (mirror/n).read_bytes()==data,n
verify();env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE_')};env.update(PYTHONPATH=str(mirror/'src'),PYTHONDONTWRITEBYTECODE='1')
argv=[str(R/'.venv/bin/python'),'-B',str(mirror/'tests/test_ordinary_runtime_write.py')]
start=time.monotonic();p=subprocess.run(argv,cwd=mirror,env=env,capture_output=True,text=True,timeout=60);elapsed=time.monotonic()-start
(D/'frozen.stdout').write_text(p.stdout);(D/'frozen.stderr').write_text(p.stderr)
verify();assert p.returncode==0
assert 'Ran 21 tests' in p.stderr and p.stderr.rstrip().endswith('OK')
result=dict(source_sha=S,mirror=str(mirror),argv=argv,exit_code=p.returncode,elapsed_seconds=elapsed,unittest_methods=21,passed=21,failed=0,errors=0,skipped=0,input_files=182,shared_and_mirror_input_drift=0,input_sha256=before,scope='PURE_OFFLINE_MEMORY_CONNECTION_PROTECTED_BINDER_AND_RPC_DI',real_database_service_installation_activation_browser_models=0,independent_test_overlap='ALL_21',limitations=['RPC expired/revoked/permission/replay refusals are injected endpoint responses, not real authority verification','No real IPC, PostgreSQL locks/atomicity, installation or managed assignment written','Root pin positive path uses DI; actual unprotected temporary file is refused'])
(D/'frozen-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='input_sha256'}))
