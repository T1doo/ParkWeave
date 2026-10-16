"""Private collection-only redaction; does not patch product or assertions."""
import json,os
from pathlib import Path
import pytest
OUT=Path(os.environ['FRONTIER_PRIVATE_WINDOW_ROOT'])
VALUES=set()

def collect(value):
 candidate=value if isinstance(value,(tuple,list)) else value.get('f') if isinstance(value,dict) else None
 if isinstance(candidate,(tuple,list)) and len(candidate)>=3 and isinstance(candidate[2],dict):
  VALUES.update(v for v in candidate[2].values() if isinstance(v,str) and len(v)>=16)
 p=OUT/'sessions-redaction.private.json';p.write_text(json.dumps(sorted(VALUES))+'\n');p.chmod(0o600)

@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
 result=yield
 if result.excinfo is None:collect(result.get_result())

def pytest_runtest_logreport(report):
 if report.longrepr:
  value=str(report.longrepr)
  for token in VALUES:value=value.replace(token,'[REDACTED_PRIVATE_SESSION]')
  report.longrepr=value
