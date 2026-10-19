import sys,json,hashlib
from pathlib import Path
import pytest
out=Path(sys.argv[1]);mirror=Path.cwd()
class Record:
 def pytest_collection_finish(self,session):(out/'collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
 def pytest_runtest_logreport(self,report):
  with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))+'\n')
 @pytest.hookimpl(hookwrapper=True)
 def pytest_fixture_setup(self,fixturedef,request):
  outcome=yield
  if fixturedef.argname=='preparation_fixture' and outcome.excinfo is None:
   value=outcome.get_result();p=out/'private-fixture-session-values.json'
   prior=json.loads(p.read_text()) if p.exists() else []
   p.write_text(json.dumps(sorted(set(prior)|set(value[2].values())),indent=2)+'\n');p.chmod(0o600)
code=pytest.main(sys.argv[2:],plugins=[Record()]);origins={}
for name,m in tuple(sys.modules.items()):
 p=getattr(m,'__file__',None)
 if p and (name.startswith(('parkweave','scripts.','test_')) or name in ('conftest','owned_connection_diagnostics')):
  p=Path(p).resolve()
  if p.is_file():origins[name]=dict(path=str(p),within_mirror=p.is_relative_to(mirror),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(out/'module-origins.json').write_text(json.dumps(origins,indent=2)+'\n');raise SystemExit(code)
