"""One bounded atomic phase/timing/count checkpoint; no SQL, raw IDs or DSNs."""
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import time
import uuid
try:
    from .diagnostics import _allowed_tests
except ImportError:
    from diagnostics import _allowed_tests

PHASES=frozenset({'UNKNOWN','acceptance_bindings','pytest_launch','pytest_collect','pytest_setup','pytest_call','pytest_teardown','pytest_finish','report_summary','report_write'})
PATTERN=r'server-regression-([0-9a-f]{32})\.progress\.json'
MAX_BYTES=1024
FIXTURE_STAGES=frozenset({'NONE','CREATE_DB','MIGRATE','SEED','GRANTS','CLIENT','CLIENT_EXIT','DROP_DB','DONE'})
TIMINGS=frozenset({'elapsed_ms','setup_ms','call_ms','teardown_ms','phase_ms','fixture_ms','create_ms','migrate_ms','seed_ms','grants_ms','drop_ms'})
COUNTS=frozenset({'completed','collected','ordinal'})
DB_COUNTS=frozenset({'client_connections','fixture_connections','idle_txn','lock_waiters','blocked','fixture_databases'})


def observation(value):
    required=TIMINGS|COUNTS|{'fixture_stage','sample_attempts','sample_state'}
    optional=DB_COUNTS|{'sample_elapsed_ms','sample_cost_ms','checkpoint_age_ms'}
    if not isinstance(value,dict) or not required<=set(value)<=required|optional:raise ValueError('invalid regression observation')
    if any(type(value[k]) is not int or not 0<=value[k]<=900000 for k in TIMINGS|({'sample_elapsed_ms','sample_cost_ms','checkpoint_age_ms'}&set(value))):raise ValueError('invalid regression duration')
    if any(type(value[k]) is not int or not 0<=value[k]<=10000 for k in COUNTS|(DB_COUNTS&set(value))):raise ValueError('invalid regression count')
    if not value['completed']<=value['ordinal']<=value['collected']:raise ValueError('inconsistent completion counts')
    if type(value['sample_attempts']) is not int or not 0<=value['sample_attempts']<=20:raise ValueError('invalid sampling count')
    if not isinstance(value['fixture_stage'],str) or value['fixture_stage'] not in FIXTURE_STAGES or not isinstance(value['sample_state'],str) or value['sample_state'] not in ('NOT_SAMPLED','AVAILABLE','UNAVAILABLE'):raise ValueError('invalid observation state')
    sample_keys=set(value)&(DB_COUNTS|{'sample_elapsed_ms','sample_cost_ms'})
    expected=set() if value['sample_state']=='NOT_SAMPLED' else {'sample_elapsed_ms','sample_cost_ms'}|(DB_COUNTS if value['sample_state']=='AVAILABLE' else set())
    if sample_keys!=expected or (value['sample_state']=='NOT_SAMPLED')!=(value['sample_attempts']==0):raise ValueError('inconsistent sample evidence')
    return dict(value)


@lru_cache(maxsize=1)
def trusted_tests():return _allowed_tests()


def safe_test_id(nodeid):
    if not isinstance(nodeid,str):return None
    value=nodeid.split('[',1)[0].replace('\\','/')
    try:return value if value in trusted_tests() else None
    except Exception:return None


def write(path,phase,active_test_id=None,*,telemetry=None):
    if path is None:return
    temporary=None
    try:
        path=Path(path);match=re.fullmatch(PATTERN,path.name)
        if not match or phase not in PHASES:return
        row={'schema':1,'execution_id':match[1],'phase':phase,'active_test_id':safe_test_id(active_test_id)}
        if telemetry is not None:
            clean=observation(telemetry);clean.pop('checkpoint_age_ms',None)
            row.update(telemetry=clean,clock_ns=time.monotonic_ns())
        data=json.dumps(row,separators=(',',':'))+'\n'
        if len(data.encode('ascii'))>MAX_BYTES:return
        temporary=path.with_name('.progress-'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(data,encoding='ascii');os.replace(temporary,path)
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
        with path.open('rb') as stream:data=stream.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:return unknown
        row=json.loads(data.decode('ascii'),object_pairs_hook=unique)
        required={'schema','execution_id','phase','active_test_id'}
        if not isinstance(row,dict) or set(row) not in (required,required|{'telemetry','clock_ns'}) or type(row['schema']) is not int or row['schema']!=1 or row['execution_id']!=match[1] or not isinstance(row['phase'],str) or row['phase'] not in PHASES:return unknown
        value=row['active_test_id']
        if value is not None and (not isinstance(value,str) or value not in trusted_tests()):return unknown
        result={'regression_phase':row['phase']}
        if value is not None:result['active_test_id']=value
        if 'telemetry' in row:
            telemetry=observation(row['telemetry'])
            if 'checkpoint_age_ms' in telemetry or type(row['clock_ns']) is not int or not 0<=row['clock_ns']<2**63:return unknown
            age=(time.monotonic_ns()-row['clock_ns'])//1000000
            if 0<=age<=900000:telemetry['checkpoint_age_ms']=age
            result['regression_observation']=telemetry
        return result
    except Exception:return unknown


def read(path):return read_snapshot(path)['regression_phase']
