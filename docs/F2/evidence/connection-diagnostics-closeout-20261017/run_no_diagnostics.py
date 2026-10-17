"""Single original six-node run; witness reads flags/identities, never connections."""
from pathlib import Path
import hashlib,json,os,sys,time
import psycopg
import pytest

root=Path('/workspace/ParkWeave');out=root/'.runtime/runtime-diagnostic-closeout'
nodes=json.loads((out/'target-nodes.json').read_text())
original_connect=psycopg.Connection.connect.__func__
original_close=psycopg.Connection.close
for name in ('PARKWEAVE_WRITER_EVIDENCE_DIR','PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR'):
 os.environ.pop(name,None)
argv=[*nodes,'-q','--basetemp=/tmp/parkweave-closeout-six-v1','--junitxml='+str(out/'six-no-diagnostics.xml')]
meta=dict(argv=argv,process_id=os.getpid(),started_monotonic_ns=time.monotonic_ns(),
 helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 expected_source_sha='8ff6f34ad68c36c0c529957a6edaf2c25e5bbb38',
 observer_scope='flag/function identity checks only; no connect wrapper, SQL or PG logger',nodes_seen=[])

class Witness:
 def check(self,config):
  import owned_connection_diagnostics as diag
  assert config.getoption('--owned-connection-diagnostics') is None
  assert diag.current() is None
  assert getattr(config,'_owned_connection_diagnostics',None) is None
  assert psycopg.Connection.connect.__func__ is original_connect
  assert psycopg.Connection.close is original_close

 @pytest.hookimpl(trylast=True)
 def pytest_sessionstart(self,session):
  self.check(session.config);meta['sessionstart_diagnostics_disabled']=True

 def pytest_runtest_setup(self,item):
  self.check(item.config);meta['nodes_seen'].append(item.nodeid)

 @pytest.hookimpl(trylast=True)
 def pytest_sessionfinish(self,session,exitstatus):
  self.check(session.config);meta.update(sessionfinish_diagnostics_disabled=True,pytest_exit_status=int(exitstatus))

(out/'six-no-diagnostics-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
result=pytest.main(argv,plugins=[Witness()])
meta.update(exit_code=int(result),ended_monotonic_ns=time.monotonic_ns(),node_order_exact=meta['nodes_seen']==nodes)
(out/'six-no-diagnostics-invocation.json').write_text(json.dumps(meta,indent=2)+'\n')
sys.exit(result)
