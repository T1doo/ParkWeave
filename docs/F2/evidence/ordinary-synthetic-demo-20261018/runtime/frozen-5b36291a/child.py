import sys,json,hashlib
from pathlib import Path
import pytest
out=Path(sys.argv[1]);mirror=Path.cwd()
tokens=set()
class Record:
 @pytest.hookimpl(hookwrapper=True)
 def pytest_fixture_setup(self,fixturedef,request):
  outcome=yield
  if outcome.excinfo:return
  value=outcome.get_result()
  def collect(value):
   if isinstance(value,tuple):
    if len(value)>2 and isinstance(value[2],dict):tokens.update(v for v in value[2].values() if isinstance(v,str) and len(v)==43)
    for item in value:
     if isinstance(item,tuple):collect(item)
  collect(value)
 def pytest_collection_finish(self,session):
  (out/'collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
 def pytest_runtest_logreport(self,report):
  with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))+'\n')
code=pytest.main(sys.argv[2:],plugins=[Record()])
(out/'private-synthetic-tokens.json').write_text(json.dumps(sorted(tokens))+'\n')
origins={}
for name,m in tuple(sys.modules.items()):
 file=getattr(m,'__file__',None)
 if file and (name.startswith('parkweave') or name.startswith('test_') or name in ('owned_connection_diagnostics','ordinary_case_step_support','service_release_acceptance_support','conftest')):
  path=Path(file).resolve()
  if path.is_file():origins[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),within_mirror=path.is_relative_to(mirror))
(out/'module-origins.json').write_text(json.dumps(origins,indent=2)+'\n')
raise SystemExit(code)
