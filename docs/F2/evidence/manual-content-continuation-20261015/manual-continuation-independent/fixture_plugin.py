"""Original owned-PG fixtures and private synthetic-session capture only."""
import importlib.util
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('manual_continuation_original_fixtures',ROOT/'tests/conftest.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
pg=module.pg
fixture=module.fixture
_private=set()


def pytest_collection_finish(session):
    target=os.environ.get('MANUAL_COLLECTION')
    if target:Path(target).write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')


def pytest_fixture_post_finalizer(fixturedef,request):
    if fixturedef.argname not in {'fixture','preparation_fixture','receipt_fixture','link_fixture','fresh_chain'} or not fixturedef.cached_result:return
    value=fixturedef.cached_result[0]
    if isinstance(value,dict):value=value.get('f')
    if not isinstance(value,tuple) or len(value)<3 or not isinstance(value[2],dict):return
    _private.update(v for v in value[2].values() if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',v))
    path=Path(__file__).parent/('redaction-'+os.environ.get('MANUAL_WINDOW','development')+'.private.json')
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w') as stream:stream.write(json.dumps(sorted(_private))+'\n')
    path.chmod(0o600)
