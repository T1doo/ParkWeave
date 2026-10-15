import json,os
from pathlib import Path
import pytest
P=Path(__file__).parent/'synthetic-redaction.private.json'
values=set()
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
 outcome=yield
 if outcome.excinfo is None:
  result=outcome.get_result()
  if fixturedef.argname=='fixture' and isinstance(result,tuple) and len(result)>2 and isinstance(result[2],dict):
   values.update(v for v in result[2].values() if isinstance(v,str))
   fd=os.open(P,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
   with os.fdopen(fd,'w') as f:json.dump({'synthetic_private_values':sorted(values)},f)
   os.chmod(P,0o600)

import sys,hashlib
def loaded_sources():
 return {n:{'path':str(Path(sys.modules['parkweave.'+n].__file__).resolve()),'sha256':hashlib.sha256(Path(sys.modules['parkweave.'+n].__file__).read_bytes()).hexdigest()} for n in ('api','plan_source_conflicts','service_case_steps','material_package_continuation') if 'parkweave.'+n in sys.modules}
def pytest_sessionstart(session):
 global source_before
 source_before=loaded_sources()
def pytest_sessionfinish(session,exitstatus):
 after=loaded_sources()
 (Path(__file__).parent/'execution-source-resolution.json').write_text(json.dumps({'actual_imports_before':source_before,'actual_imports_after':after,'unchanged':source_before==after,'scope':'shared WIP sources, not formal frozen SHA','exitstatus':exitstatus},indent=2)+'\n')
