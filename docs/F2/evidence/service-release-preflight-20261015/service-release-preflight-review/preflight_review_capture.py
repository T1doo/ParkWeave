from pathlib import Path
import json,os,re
_PRIVATE=set()
def pytest_collection_finish(session):
    Path(os.environ['PREFLIGHT_REVIEW_COLLECTION']).write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')
def pytest_runtest_call(item):
    seen=set()
    def visit(value,depth=0):
        if depth>6 or id(value) in seen:return
        seen.add(id(value))
        if isinstance(value,dict):
            if 'fixture-a' in value:
                _PRIVATE.update(v for v in value.values() if isinstance(v,str) and re.fullmatch('[A-Za-z0-9_-]{43}',v))
            for v in value.values():visit(v,depth+1)
        elif isinstance(value,(list,tuple)):
            for v in value:visit(v,depth+1)
    visit(item.funcargs)
    Path(os.environ['PREFLIGHT_REVIEW_PRIVATE']).write_text(json.dumps(sorted(_PRIVATE))+'\n')
