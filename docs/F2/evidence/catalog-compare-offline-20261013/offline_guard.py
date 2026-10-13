"""Select pure tests and reject physical actions; allow only known offline CLI."""
import json,os,socket,subprocess,sys
from pathlib import Path
import psycopg
import pytest

def pytest_collection_modifyitems(config,items):
    physical=[i for i in items if {'fixture','pg'} & set(i.fixturenames)]
    items[:]=[i for i in items if i not in physical]
    config.hook.pytest_deselected(items=physical)
    Path(os.environ['PW_CATALOG_NOT_RUN_PATH']).write_text(json.dumps(
        dict(qualification='PHYSICAL_PG_NOT_RUN',test_ids=[i.nodeid for i in physical]),indent=2)+'\n')

@pytest.fixture(autouse=True)
def no_physical_actions(monkeypatch):
    original=subprocess.Popen
    def forbidden(*a,**kw):pytest.fail('physical PG/OS/socket action forbidden in offline window')
    def offline_only(args,*a,**kw):
        if (isinstance(args,list) and args[:3]==[sys.executable,'-m','parkweave.native_run_access_preflight']
                and not kw.get('shell')):return original(args,*a,**kw)
        return forbidden()
    monkeypatch.setattr(subprocess,'Popen',offline_only)
    for obj,name in [(psycopg,'connect'),(psycopg.Connection,'connect'),(socket.socket,'connect'),
        (socket.socket,'bind'),(os,'chmod'),(os,'chown'),(os,'fchmod'),(os,'fchown'),
        (os,'umask'),(os,'memfd_create'),(os,'setuid'),(os,'setgid'),(os,'setgroups')]:
        monkeypatch.setattr(obj,name,forbidden)
