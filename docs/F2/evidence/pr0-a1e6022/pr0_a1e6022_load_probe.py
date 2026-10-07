"""Read-only per-run provenance recorder; not an application/test modification."""
import hashlib,json,sys,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RECORDS={}
UNEXPECTED={}

def capture():
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if not path or not name.startswith(('parkweave','scripts.','test_')):
            continue
        source=Path(path).resolve()
        if source.suffix=='.pyc':
            try:
                from importlib.util import source_from_cache
                source=Path(source_from_cache(str(source)))
            except ValueError:continue
        if not source.is_file():continue
        key=(name,str(source))
        if key in RECORDS:continue
        item={'module':name,'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'first_seen_monotonic':time.monotonic()}
        RECORDS[key]=item
        if name=='parkweave' or name.startswith('parkweave.'):
            if not source.is_relative_to(ROOT/'src'/'parkweave'):
                UNEXPECTED[key]=item

def pytest_collection_finish(session):capture()
def pytest_runtest_teardown(item,nextitem):capture()
def pytest_sessionfinish(session,exitstatus):
    capture()
    report={'scope':'primary pytest process loaded source origins; child processes are separately covered by frozen source and original environment tests',
            'pid':os.getpid(),'python_executable':sys.executable,'exitstatus':int(exitstatus),'sys_path':sys.path,
            'loaded_modules':list(RECORDS.values()),'unexpected_parkweave_sources':list(UNEXPECTED.values())}
    (ROOT/'.runtime'/'pr0-a1e6022-loaded-source.json').write_text(json.dumps(report,indent=2)+'\n')
