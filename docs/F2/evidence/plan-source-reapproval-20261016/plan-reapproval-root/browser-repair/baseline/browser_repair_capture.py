from pathlib import Path
import os,json,sys,re,hashlib
values=set()
def pytest_configure(config):
 import parkweave
 actual=Path(parkweave.__file__).resolve();expected=Path(os.environ['REPAIR_PROJECT'])/'src/parkweave/__init__.py';assert actual==expected
 Path(os.environ['REPAIR_OUT'],'actual-package.json').write_text(json.dumps(dict(actual=str(actual),expected=str(expected),sha256=hashlib.sha256(actual.read_bytes()).hexdigest()),indent=2)+'\n')
def pytest_collection_finish(session):
 out=Path(os.environ['REPAIR_OUT']);out.joinpath('collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n');routes=[]
 for name,module in list(sys.modules.items()):
  value=getattr(module,'OUT',None) if name.startswith('test_') else None
  if isinstance(value,Path) and ('.runtime' in value.parts or str(value).startswith('.runtime/')):
   target=out/'artifacts'/name;setattr(module,'OUT',target);routes.append(dict(module=name,original=str(value),actual=str(target)))
 out.joinpath('artifact-routing.json').write_text(json.dumps(dict(product_logic_changed=False,before_fixtures=True,routes=routes),indent=2)+'\n')
def pytest_fixture_post_finalizer(fixturedef,request):
 if fixturedef.argname not in {'fixture','preparation_fixture','receipt_fixture','link_fixture','fresh_chain'} or not fixturedef.cached_result:return
 value=fixturedef.cached_result[0]
 if isinstance(value,dict):value=value.get('f',value.get('tokens'))
 tokens=value[2] if isinstance(value,tuple) and len(value)>2 and isinstance(value[2],dict) else value if isinstance(value,dict) else {}
 values.update(v for v in tokens.values() if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',v))
 path=Path(os.environ['REPAIR_OUT'],'redaction.private.json');path.write_text(json.dumps(sorted(values))+'\n');path.chmod(0o600)
