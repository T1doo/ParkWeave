"""Keep the already-allowed offline CLI's caches/temp files within this review."""
import json
from pathlib import Path
import subprocess
import sys
import pytest

OUTPUT=Path('/workspace/ParkWeave/.runtime/catalog-only-independent-20261013')
observations=[]

@pytest.fixture(autouse=True)
def isolated_offline_cli_child(no_physical_actions,monkeypatch):
    original=subprocess.Popen
    def invoke(args,*a,**kw):
        if isinstance(args,list) and args[:3]==[sys.executable,'-m','parkweave.native_run_access_preflight']:
            kw['env']=dict(kw.get('env') or {},PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(OUTPUT/'system-tmp'))
            observations.append(dict(module='parkweave.native_run_access_preflight',bytecode_disabled=True,private_tmp=True))
        return original(args,*a,**kw)
    monkeypatch.setattr(subprocess,'Popen',invoke)

def pytest_sessionfinish(session,exitstatus):
    (OUTPUT/'offline-cli-observations.json').write_text(json.dumps(dict(
        allowed_offline_cli_invocations=len(observations),observations=observations,
        qualification='Only pre-existing offline preflight CLI may run; no PG/trial/package/network child is permitted.'),indent=2)+'\n')
