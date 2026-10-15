import json,os,re
from pathlib import Path
import pytest

_private=set()

def pytest_collection_finish(session):
 Path(os.environ['TYPED_COLLECTION']).write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')


def pytest_fixture_post_finalizer(fixturedef,request):
 # Only the already synthetic fixture's token dictionary; never query or print a credential.
 if fixturedef.argname not in {'fixture','preparation_fixture','receipt_fixture','link_fixture','fresh_chain','upgrade_case','template_consumption'} or not fixturedef.cached_result:return
 value=fixturedef.cached_result[0]
 if isinstance(value,dict) and isinstance(value.get('tokens'),dict):tokens=value['tokens']
 else:
  if isinstance(value,dict):value=value.get('f')
  if not isinstance(value,tuple) or len(value)<3 or not isinstance(value[2],dict):return
  tokens=value[2]
 values=[v for v in tokens.values() if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',v)]
 if not values:return
 _private.update(values)
 path=Path(os.environ['TYPED_PRIVATE']);path.write_text(json.dumps(sorted(_private))+'\n');path.chmod(0o600)


def pytest_collection_modifyitems(session,config,items):
 # Redirect only test artifact destinations into this run; frozen prior runtime
 # evidence and tracked test source remain unchanged. Never patch product logic.
 import hashlib
 target=Path(os.environ.get('AT_BATCH_ARTIFACT_ROOT','.runtime/manual-continuation-root/related-test-artifacts'))/os.environ.get('AT_BATCH_WINDOW','development')
 seen=set(); records=[]
 for item in items:
  module=item.module
  if id(module) in seen:continue
  seen.add(id(module))
  value=getattr(module,'OUT',None)
  if isinstance(value,Path) and (str(value).startswith('.runtime/') or '.runtime' in value.parts):
   replacement=target/module.__name__
   setattr(module,'OUT',replacement)
   records.append(dict(module=module.__name__,original=str(value),actual=str(replacement)))
 (Path(os.environ['TYPED_COLLECTION']).with_name(Path(os.environ['TYPED_COLLECTION']).stem+'-artifact-paths.json')).write_text(json.dumps(records,indent=2)+'\n')


_actual_http=[]
_attached_clients=set()
_client_refs=[]

def pytest_runtest_call(item):
 import httpx
 seen=set()
 def visit(value,depth=0):
  if depth>7 or id(value) in seen:return
  seen.add(id(value))
  if isinstance(value,httpx.Client) and value.base_url.host in {'127.0.0.1','localhost'} and id(value) not in _attached_clients:
   _attached_clients.add(id(value));_client_refs.append(value);label=item.nodeid
   value.event_hooks['request'].append(lambda request,label=label:_actual_http.append(dict(test=label,method=request.method,path=request.url.path,transport='ACTUAL_LOOPBACK_HTTP')))
  if isinstance(value,dict):
   for child in value.values():visit(child,depth+1)
  elif isinstance(value,(list,tuple)):
   for child in value:visit(child,depth+1)
 visit(item.funcargs)

def pytest_sessionfinish(session,exitstatus):
 Path(os.environ['TYPED_HTTP']).write_text(json.dumps(dict(count=len(_actual_http),requests=_actual_http,headers_or_tokens_saved=False),indent=2)+'\n')
