"""Copy original test evidence; observe imports and pytest reports without business activity."""
import json,os,pathlib,shutil,sys
import pytest

DEST=pathlib.Path(os.environ['INDEPENDENT_ACCEPT_EVIDENCE'])
ROWS=[]
def dump(name,value):(DEST/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def pytest_collection_modifyitems(session,config,items):dump('collected-nodes.json',[i.nodeid for i in items])
def pytest_runtest_logreport(report):
 ROWS.append(dict(nodeid=report.nodeid,phase=report.when,outcome=report.outcome,seconds=report.duration))
 dump('phase-results.json',ROWS)
def copy_existing(config):
 base=pathlib.Path(config.option.basetemp)
 if not base.exists():return
 for p in base.rglob('*'):
  rel=p.relative_to(base)
  if any(part in ('data','__pycache__') or part.startswith('parkweave-pg') for part in rel.parts):continue
  if p.is_file() and (p.suffix in ('.json','.jsonl','.xml','.png','.log','.stdout','.stderr','.txt')):
   target=DEST/'case-artifacts'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item,nextitem):
 yield
 try:copy_existing(item.config)
 except Exception as e:dump('artifact-copy-warning.json',dict(type=type(e).__name__,message=str(e)))
def pytest_sessionfinish(session,exitstatus):
 try:copy_existing(session.config)
 except Exception as e:dump('artifact-copy-warning.json',dict(type=type(e).__name__,message=str(e)))
 origins={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.items() if (n=='parkweave' or n.startswith('parkweave.')) and getattr(m,'__file__',None)}
 dump('module-origins.json',origins)
 dump('observer-settlement.json',dict(exitstatus=int(exitstatus),extra_tests=0,
  scope='Original reports, pytest module file origins and copies of existing non-PG test artifacts only; no product patches, added requests/screenshots, or original assertion/timeout changes.'))
