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
