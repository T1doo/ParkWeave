import json,os,re
from pathlib import Path
import pytest

_private=set()

def pytest_collection_finish(session):
 Path(os.environ['TYPED_COLLECTION']).write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')


def pytest_fixture_post_finalizer(fixturedef,request):
 # Only the already synthetic fixture's token dictionary; never query or print a credential.
 if fixturedef.argname not in {'fixture','preparation_fixture','receipt_fixture','link_fixture','fresh_chain','upgrade_case'} or not fixturedef.cached_result:return
 value=fixturedef.cached_result[0]
 if isinstance(value,dict):value=value.get('f')
 if not isinstance(value,tuple) or len(value)<3 or not isinstance(value[2],dict):return
 values=[v for v in value[2].values() if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',v)]
 if not values:return
 _private.update(values)
 path=Path(os.environ['TYPED_PRIVATE']);path.write_text(json.dumps(sorted(_private))+'\n');path.chmod(0o600)
