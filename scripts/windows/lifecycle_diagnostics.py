"""Fixed, path-free lifecycle failure protocol; never classify exception messages."""
from contextlib import contextmanager
import functools
import json

PREFIX='PARKWEAVE_LIFECYCLE_DIAGNOSTIC '
MAX_BYTES=1024
PHASES=frozenset({'UNKNOWN','python_guard','configuration','private_acl','environment_binding','dsn_parse','database_connect','database_role','database_version','database_schema','dependency_freeze','doctor_output','process_record','port_check','service_log','process_spawn','process_identity','health_readiness','process_stop'})
CATEGORIES=frozenset({'OTHER','BoundaryError','OSError','FileNotFoundError','PermissionError','ValueError','TypeError','KeyError','AttributeError','JSONDecodeError','UnicodeDecodeError','UnicodeEncodeError','CalledProcessError','TimeoutExpired','ModuleNotFoundError','ImportError','OperationalError','InterfaceError','ProgrammingError','InsufficientPrivilege','UndefinedTable','InvalidPassword','InvalidCatalogName'})
REASONS=frozenset({'UNCLASSIFIED','BOUNDARY_REFUSED','ENVIRONMENT_REQUIRED','NATIVE_PLATFORM_REQUIRED','CONFIG_INVALID','CONFIG_SCOPE_REFUSED','PORT_INVALID','PYTHON_BINDING_REFUSED','PRIVATE_ROOT_MISMATCH','ACL_REFUSED','REPARSE_REFUSED','PYTHON_VERSION_REFUSED','DSN_SCOPE_REFUSED','APP_ROLE_REFUSED','CONFIG_MISSING','PORT_OCCUPIED','PROCESS_RECORD_EXISTS','SERVICE_EXITED','READINESS_TIMEOUT','DIAGNOSTIC_UNAVAILABLE'})
REASONS=REASONS|{'ACL_OWNER_MISMATCH','ACL_ALLOW_REFUSED','ACL_INHERITANCE_REFUSED','ACL_INSPECTION_FAILED'}


@contextmanager
def stage(name):
    try:yield
    except Exception as exc:
        try:
            if getattr(exc,'parkweave_lifecycle_phase',None) not in PHASES:
                exc.parkweave_lifecycle_phase=name if name in PHASES else 'UNKNOWN'
        except Exception:pass
        raise


def staged(name):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args,**kwargs):
            with stage(name):return function(*args,**kwargs)
        return wrapped
    return decorate


def failure(exc):
    attributes=vars(exc)
    phase=attributes.get('parkweave_lifecycle_phase')
    reason=attributes.get('parkweave_lifecycle_reason')
    category=type(exc).__name__
    return {'boundary_phase':phase if isinstance(phase,str) and phase in PHASES else 'UNKNOWN',
            'category':category if category in CATEGORIES else 'OTHER',
            'boundary_reason':reason if isinstance(reason,str) and reason in REASONS else 'UNCLASSIFIED'}


def command(action,exc):
    if action not in {'doctor','setup','start','status','stop','test'}:raise ValueError('unknown action')
    value={'schema':1,'action':action,**failure(exc)}
    primary=vars(exc).get('parkweave_lifecycle_primary')
    if isinstance(primary,dict) and set(primary)=={'boundary_phase','category','boundary_reason'} and all(isinstance(primary[k],str) and primary[k] in choices for k,choices in (('boundary_phase',PHASES),('category',CATEGORIES),('boundary_reason',REASONS))):
        value.update(primary,cleanup_category=value['category'])
    result=PREFIX+json.dumps(value,ensure_ascii=True,separators=(',',':'))
    if len((result+'\n').encode('ascii'))>MAX_BYTES:raise ValueError('diagnostic bound exceeded')
    return result


def parse(stderr,action):
    unavailable={'boundary_phase':'UNKNOWN','category':'OTHER','boundary_reason':'DIAGNOSTIC_UNAVAILABLE'}
    if action not in ('doctor','start','setup'):return unavailable
    if not isinstance(stderr,str) or len(stderr)>65536:return unavailable
    matches=[line for line in stderr.splitlines() if line.startswith(PREFIX)]
    if len(matches)!=1 or not matches[0].isascii() or len(matches[0])+1>MAX_BYTES:return unavailable
    try:
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('duplicate field')
                result[key]=value
            return result
        row=json.loads(matches[0][len(PREFIX):],object_pairs_hook=unique)
        expected={'schema','action','boundary_phase','category','boundary_reason'}
        if not isinstance(row,dict) or set(row) not in (expected,expected|{'cleanup_category'}) or type(row['schema']) is not int or row['schema']!=1 or row['action']!=action:return unavailable
        for key,choices in (('boundary_phase',PHASES),('category',CATEGORIES),('boundary_reason',REASONS),('cleanup_category',CATEGORIES)):
            if key in row and (not isinstance(row[key],str) or row[key] not in choices):return unavailable
        return {k:v for k,v in row.items() if k not in ('schema','action')}
    except (ValueError,TypeError,UnicodeError,RecursionError):return unavailable
