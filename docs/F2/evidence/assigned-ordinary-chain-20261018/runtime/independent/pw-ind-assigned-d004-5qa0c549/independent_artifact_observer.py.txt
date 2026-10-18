"""Evidence copying and Python import observation only; no business activity."""
import json,os,pathlib,shutil,sys
import pytest

DEST=pathlib.Path(os.environ['INDEPENDENT_ASSIGNED_EVIDENCE'])

def dump(name,value):
 (DEST/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def pytest_collection_modifyitems(session,config,items):
 dump('collected-nodes.json',[item.nodeid for item in items])

def copy_existing(config):
 base=pathlib.Path(config.option.basetemp)
 if not base.exists():return
 for path in base.rglob('*'):
  if path.is_file() and (path.name in ('ordinary-api.log','actual-assigned-full-chain.json','failure-traffic.json') or path.suffix=='.png'):
   target=DEST/'case-artifacts'/path.relative_to(base)
   target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(path,target)

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item,nextitem):
 yield
 try:copy_existing(item.config)
 except Exception as error:dump('artifact-copy-warning.json',dict(type=type(error).__name__,message=str(error)))

def pytest_sessionfinish(session,exitstatus):
 try:copy_existing(session.config)
 except Exception as error:dump('artifact-copy-warning.json',dict(type=type(error).__name__,message=str(error)))
 origins={name:str(pathlib.Path(module.__file__).resolve()) for name,module in sys.modules.items()
          if (name=='parkweave' or name.startswith('parkweave.')) and getattr(module,'__file__',None)}
 dump('module-origins.json',origins)
 dump('observer-settlement.json',dict(exitstatus=int(exitstatus),extra_tests=0,scope='Artifact copying and module-origin observation only; no requests, screenshots, product patches, deadline/assertion changes.'))
