"""Signal only this newly created pytest PID; cleanup remains the frozen fixtures'."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time

root=Path('/workspace/ParkWeave');out=root/'.runtime/runtime-diagnostic-closeout'
for name in ('sigint-ready.json','sigint-smoke.log','sigint-diagnostics'):
 assert not (out/name).exists()
env=dict(os.environ)
env['PYTHONPATH']=str(root/'tests')+os.pathsep+str(root/'src')
for name in ('PARKWEAVE_WRITER_EVIDENCE_DIR','PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR'):env.pop(name,None)
argv=[str(root/'.venv/bin/python'),str(out/'run_sigint_pytest.py')]
meta=dict(argv=argv,helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          started_monotonic_ns=time.monotonic_ns(),signals_sent=[],unknown_processes_signalled=False)
def save(): (out/'sigint-controller.json').write_text(json.dumps(meta,indent=2)+'\n')
with (out/'sigint-smoke.log').open('xb') as sink:
 child=subprocess.Popen(argv,cwd=root,env=env,stdout=sink,stderr=subprocess.STDOUT)
 meta['pytest_pid']=child.pid;save()
 deadline=time.monotonic()+30;ready=None
 while time.monotonic()<deadline and child.poll() is None:
  try:ready=json.loads((out/'sigint-ready.json').read_text());break
  except (FileNotFoundError,json.JSONDecodeError):time.sleep(.05)
 if ready is None:
  meta.update(status='NO_READY_SIGNAL_NOT_SENT',observed_exit=child.poll());save()
  if child.poll() is None:
   try:child.wait(timeout=50)
   except subprocess.TimeoutExpired:meta['outcome']='PENDING_OWNED_PYTEST_NO_EXTRA_SIGNAL';save();sys.exit(1)
  meta['exit_code']=child.returncode;save();sys.exit(1)
 assert ready['pytest_pid']==child.pid
 cmd=(Path('/proc')/str(child.pid)/'cmdline').read_bytes().split(b'\0')
 assert str(out/'run_sigint_pytest.py').encode() in cmd
 writer_stat=(Path('/proc')/str(ready['writer_pid'])/'stat').read_text().rsplit(')',1)[1].split()
 assert int(writer_stat[1])==child.pid and writer_stat[19]==ready['writer_process_started']
 meta.update(ready=ready,verified_pytest_cmdline=True,verified_writer_parent_and_start=True)
 os.kill(child.pid,signal.SIGINT)
 meta['signals_sent'].append(dict(pid=child.pid,signal='SIGINT',monotonic_ns=time.monotonic_ns()));save()
 try:code=child.wait(timeout=30)
 except subprocess.TimeoutExpired:meta.update(status='PENDING_OWNED_PYTEST_AFTER_SIGINT');save();sys.exit(1)
 meta.update(status='PYTEST_EXITED_AND_REAPED',exit_code=code,ended_monotonic_ns=time.monotonic_ns(),
             pytest_proc_entry_exists=(Path('/proc')/str(child.pid)).exists(),
             writer_proc_entry_exists=(Path('/proc')/str(ready['writer_pid'])).exists())
 save()
 print(json.dumps(meta))
 assert code==2,'expected pytest INTERRUPTED, preserve log on any other outcome'
 assert not meta['pytest_proc_entry_exists'] and not meta['writer_proc_entry_exists']
