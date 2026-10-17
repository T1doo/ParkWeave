"""Pytest child; wrap sessionfinish without changing the frozen plugin order."""
from pathlib import Path
import errno,json,os,sys,time,hashlib
import pytest

root=Path('/workspace/ParkWeave');out=root/'.runtime/runtime-diagnostic-closeout'
argv=[str(out/'sigint-case/test_owned_interrupt.py'),'-p','owned_connection_diagnostics','-q',
      '--basetemp=/tmp/parkweave-closeout-sigint-v1','--junitxml='+str(out/'sigint-smoke.xml'),
      '--owned-connection-diagnostics='+str(out/'sigint-diagnostics')]
meta=dict(argv=argv,process_id=os.getpid(),started_monotonic_ns=time.monotonic_ns(),
          helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
def save(): (out/'sigint-pytest-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')

class Witness:
 def pytest_keyboard_interrupt(self,excinfo):
  meta.update(keyboard_interrupt_type=excinfo.typename,keyboard_interrupt_monotonic_ns=time.monotonic_ns());save()

 @pytest.hookimpl(hookwrapper=True,tryfirst=True)
 def pytest_sessionfinish(self,session,exitstatus):
  import owned_connection_diagnostics as diagnostic
  current=diagnostic.current()
  meta.update(sessionfinish_enter_monotonic_ns=time.monotonic_ns(),sessionfinish_exit_status=int(exitstatus),
              diagnostic_present_before_finish=current is not None)
  if current is not None:os.fstat(current.fd)
  save()
  yield
  closed=False
  if current is not None:
   try:os.fstat(current.fd)
   except OSError as error:closed=error.errno==errno.EBADF
  meta.update(sessionfinish_exit_monotonic_ns=time.monotonic_ns(),diagnostic_cleared_after_finish=diagnostic.current() is None,
              diagnostic_fd_closed_after_finish=closed)
  save()
  assert meta['diagnostic_cleared_after_finish'] and closed

save()
result=pytest.main(argv,plugins=[Witness()])
meta.update(exit_code=int(result),ended_monotonic_ns=time.monotonic_ns());save();sys.exit(result)
