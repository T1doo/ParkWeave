"""One bounded atomic last-recorded phase/allowlisted test snapshot; no raw IDs."""
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import uuid
try:
    from .diagnostics import _allowed_tests
except ImportError:
    from diagnostics import _allowed_tests

PHASES=frozenset({'UNKNOWN','acceptance_bindings','pytest_launch','pytest_collect','pytest_setup','pytest_call','pytest_teardown','pytest_finish','report_summary','report_write'})
PATTERN=r'server-regression-([0-9a-f]{32})\.progress\.json'


@lru_cache(maxsize=1)
def trusted_tests():
    return _allowed_tests()


def safe_test_id(nodeid):
    if not isinstance(nodeid,str):return None
    value=nodeid.split('[',1)[0].replace('\\','/')
    try:return value if value in trusted_tests() else None
    except Exception:return None


def write(path,phase,active_test_id=None):
    if path is None:return
    temporary=None
    try:
        path=Path(path);match=re.fullmatch(PATTERN,path.name)
        if not match or phase not in PHASES:return
        row={'schema':1,'execution_id':match[1],'phase':phase,'active_test_id':safe_test_id(active_test_id)}
        data=json.dumps(row,separators=(',',':'))+'\n'
        if len(data.encode('ascii'))>512:return
        temporary=path.with_name('.progress-'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(data,encoding='ascii')
        os.replace(temporary,path)
    except Exception:pass  # Telemetry cannot change a test's result or cleanup.
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate checkpoint field')
        result[key]=value
    return result


def read_snapshot(path):
    unknown={'regression_phase':'UNKNOWN'}
    try:
        path=Path(path);match=re.fullmatch(PATTERN,path.name)
        if not match or path.resolve()!=path.absolute():return unknown
        with path.open('rb') as stream:data=stream.read(513)
        if len(data)>512:return unknown
        row=json.loads(data.decode('ascii'),object_pairs_hook=unique)
        if not isinstance(row,dict) or set(row)!={'schema','execution_id','phase','active_test_id'} or type(row['schema']) is not int or row['schema']!=1 or row['execution_id']!=match[1] or not isinstance(row['phase'],str) or row['phase'] not in PHASES:return unknown
        value=row['active_test_id']
        if value is not None and (not isinstance(value,str) or value not in trusted_tests()):return unknown
        result={'regression_phase':row['phase']}
        if value is not None:result['active_test_id']=value
        return result
    except Exception:return unknown


def read(path):return read_snapshot(path)['regression_phase']
