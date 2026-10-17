"""Run the fixed 427-node collection; incremental PG log copy is file-only."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
root=Path('/workspace/ParkWeave');out=root/'.runtime/runtime-read-diagnostics'
freeze=json.loads((out/'freeze.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==freeze['source_sha']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
base=Path('/tmp/parkweave-connection-full-v1');assert not base.exists()
for name in ('full-v1-diagnostics','full-v1-writer','full-v1-activation','full-v1.log','full-v1.xml'):
 assert not (out/name).exists()
argv=[str(root/'.venv/bin/python'),'-m','pytest',*freeze['modules'],'-q','--basetemp='+str(base),
 '--junitxml='+str(out/'full-v1.xml'),'--owned-connection-diagnostics='+str(out/'full-v1-diagnostics')]
env=dict(os.environ)
env.update(PARKWEAVE_WRITER_EVIDENCE_DIR=str(out/'full-v1-writer'),PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR=str(out/'full-v1-activation'))
meta=dict(source_sha=freeze['source_sha'],argv=argv,started_utc_ns=time.time_ns(),started_monotonic_ns=time.monotonic_ns(),
 helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 evidence_environment={k:env[k] for k in ('PARKWEAVE_WRITER_EVIDENCE_DIR','PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR')},
 pg_observer='incremental file-only log copy; no PG object, SQL, connection or lifecycle reference')
source=base/'parkweave-pg0/data/log';offset=0
with (out/'full-v1.log').open('xb') as sink,(out/'full-v1-postgres-observed.log').open('xb') as pgout:
 child=subprocess.Popen(argv,cwd=root,env=env,stdout=sink,stderr=subprocess.STDOUT)
 meta['pytest_pid']=child.pid
 (out/'full-v1-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
 while child.poll() is None:
  try:
   with source.open('rb') as incoming:
    incoming.seek(offset);chunk=incoming.read(1048576)
   if chunk:pgout.write(chunk);pgout.flush();offset+=len(chunk)
  except FileNotFoundError:pass
  time.sleep(.5)
 result=child.wait()
meta.update(exit_code=result,ended_utc_ns=time.time_ns(),ended_monotonic_ns=time.monotonic_ns(),pg_log_bytes_copied=offset)
(out/'full-v1-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(meta));sys.exit(result)
