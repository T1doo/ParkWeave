"""Fixed, path-free lifecycle failure protocol; never classify exception messages."""
from contextlib import contextmanager
import functools
import json
from server_identity import validate_identity_refusal

PREFIX='PARKWEAVE_LIFECYCLE_DIAGNOSTIC '
MAX_BYTES=1024
ACL_OBJECTS=frozenset({'ROOT','SESSIONS','CONFIG','FILES','PROCESS_RECORD','SERVICE_LOG'})
PHASES=frozenset({'UNKNOWN','python_guard','configuration','private_acl','environment_binding','dsn_parse','database_connect','database_role','database_version','database_schema','dependency_freeze','doctor_output','process_record','port_check','service_log','process_spawn','process_identity','health_readiness','process_stop'})
CATEGORIES=frozenset({'OTHER','BoundaryError','OSError','FileNotFoundError','PermissionError','ValueError','TypeError','KeyError','AttributeError','JSONDecodeError','UnicodeDecodeError','UnicodeEncodeError','CalledProcessError','TimeoutExpired','ModuleNotFoundError','ImportError','OperationalError','InterfaceError','ProgrammingError','InsufficientPrivilege','UndefinedTable','InvalidPassword','InvalidCatalogName'})
REASONS=frozenset({'UNCLASSIFIED','BOUNDARY_REFUSED','ENVIRONMENT_REQUIRED','NATIVE_PLATFORM_REQUIRED','CONFIG_INVALID','CONFIG_SCOPE_REFUSED','PORT_INVALID','PYTHON_BINDING_REFUSED','PRIVATE_ROOT_MISMATCH','ACL_REFUSED','REPARSE_REFUSED','PYTHON_VERSION_REFUSED','DSN_SCOPE_REFUSED','APP_ROLE_REFUSED','CONFIG_MISSING','PORT_OCCUPIED','PROCESS_RECORD_EXISTS','SERVICE_EXITED','READINESS_TIMEOUT','DIAGNOSTIC_UNAVAILABLE'})
REASONS=REASONS|{'ACL_OWNER_MISMATCH','ACL_ALLOW_REFUSED','ACL_INHERITANCE_REFUSED','ACL_INSPECTION_FAILED'}
REASONS=REASONS|{'PORT_CHECK_REFUSED'}


START_STATES=frozenset({'NOT_CREATED','RUNNING','EXIT_ZERO','EXIT_NONZERO','UNKNOWN'})
START_LAST=frozenset({'NOT_PROBED','CHILD_EXITED','CONNECTION_REFUSED','TRANSPORT_TIMEOUT','HTTP_NON_SUCCESS','TRANSPORT_OTHER','HEALTH_MISMATCH','HEALTH_MATCH'})
START_SMALL=frozenset({'created','cleanup_attempted','stopped','absent','foreign'})
START_COUNTS=frozenset({'attempts','responses','refused','timeouts','http_errors','other_errors','mismatches','alive_refused'})
START_STATE_KEYS=frozenset({'api','worker','after_api','after_worker'})
START_MATCHES=frozenset({'mode_matches','model_matches','process_matches'})


def start_observation(value):
    required=START_SMALL|START_COUNTS|START_STATE_KEYS|{'last'}
    relation_keys={'server_pid_valid','server_relation'}
    if not isinstance(value,dict) or not required<=set(value)<=required|START_MATCHES|relation_keys|{'identity_refusal'}:raise ValueError('invalid start observation')
    if any(type(value[k]) is not int or not 0<=value[k]<=2 for k in START_SMALL):raise ValueError('invalid start count')
    if any(type(value[k]) is not int or not 0<=value[k]<=50 for k in START_COUNTS):raise ValueError('invalid request count')
    if any(not isinstance(value[k],str) or value[k] not in START_STATES for k in START_STATE_KEYS) or not isinstance(value['last'],str) or value['last'] not in START_LAST:raise ValueError('invalid start state')
    if value['responses']>value['attempts'] or value['mismatches']>value['responses'] or value['alive_refused']>value['refused']:raise ValueError('inconsistent request counts')
    if sum(value[k] for k in ('responses','refused','timeouts','http_errors','other_errors'))>value['attempts']:raise ValueError('inconsistent attempt counts')
    if value['stopped']+value['absent']+value['foreign']>value['cleanup_attempted'] or value['cleanup_attempted']>value['created']:raise ValueError('inconsistent cleanup counts')
    present=START_MATCHES&set(value)
    if present!=(START_MATCHES if value['responses'] else set()) or any(type(value[k]) is not bool for k in present):raise ValueError('invalid health matching evidence')
    if relation_keys&set(value):
        if not relation_keys<=set(value) or not value['responses'] or type(value['server_pid_valid']) is not bool or value['server_relation'] not in ('ROOT','DIRECT_CHILD','REFUSED'):raise ValueError('invalid server relation')
        verified=value['server_relation'] in ('ROOT','DIRECT_CHILD')
        if verified!=value['process_matches'] or verified and not value['server_pid_valid']:raise ValueError('inconsistent server relation')
    if 'identity_refusal' in value:
        if value.get('server_relation')!='REFUSED' or not value['responses']:raise ValueError('invalid refusal context')
        value={**value,'identity_refusal':validate_identity_refusal(value['identity_refusal'])}
    return dict(value)


def start_status_command(observation):
    # On exit0, the suite consumes only observation; boundary slots are neutral.
    value={'schema':1,'action':'start','boundary_phase':'health_readiness','category':'OTHER','boundary_reason':'UNCLASSIFIED','start_observation':start_observation(observation)}
    result=PREFIX+json.dumps(value,ensure_ascii=True,separators=(',',':'))
    if len((result+'\n').encode('ascii'))>MAX_BYTES:raise ValueError('diagnostic bound exceeded')
    return result


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
    result={'boundary_phase':phase if isinstance(phase,str) and phase in PHASES else 'UNKNOWN',
            'category':category if category in CATEGORIES else 'OTHER',
            'boundary_reason':reason if isinstance(reason,str) and reason in REASONS else 'UNCLASSIFIED'}
    obj=attributes.get('parkweave_acl_object')
    if result['boundary_phase']=='private_acl' and isinstance(obj,str) and obj in ACL_OBJECTS:result['acl_object']=obj
    observation=attributes.get('parkweave_start_observation')
    if observation is not None:
        try:result['start_observation']=start_observation(observation)
        except ValueError:pass
    identity=attributes.get('parkweave_identity_refusal')
    if identity is not None:
        try:result['identity_refusal']=validate_identity_refusal(identity)
        except ValueError:pass
    return result


def command(action,exc):
    if action not in {'doctor','setup','start','status','stop','test'}:raise ValueError('unknown action')
    value={'schema':1,'action':action,**failure(exc)}
    primary=vars(exc).get('parkweave_lifecycle_primary')
    expected={'boundary_phase','category','boundary_reason'}
    if isinstance(primary,dict) and expected<=set(primary)<=expected|{'acl_object','start_observation','identity_refusal'} and all(isinstance(primary[k],str) and primary[k] in choices for k,choices in (('boundary_phase',PHASES),('category',CATEGORIES),('boundary_reason',REASONS))) and ('acl_object' not in primary or (primary['boundary_phase']=='private_acl' and isinstance(primary['acl_object'],str) and primary['acl_object'] in ACL_OBJECTS)):
        value.pop('acl_object',None);value.pop('start_observation',None)
        cleanup_identity=value.pop('identity_refusal',None)
        if 'start_observation' in primary:primary={**primary,'start_observation':start_observation(primary['start_observation'])}
        if 'identity_refusal' in primary:primary={**primary,'identity_refusal':validate_identity_refusal(primary['identity_refusal'])}
        value.update(primary,cleanup_category=value['category'])
        if cleanup_identity is not None:value['cleanup_identity_refusal']=cleanup_identity
    if action!='start':value.pop('start_observation',None)
    if action not in ('start','stop'):value.pop('identity_refusal',None);value.pop('cleanup_identity_refusal',None)
    result=PREFIX+json.dumps(value,ensure_ascii=True,separators=(',',':'))
    if len((result+'\n').encode('ascii'))>MAX_BYTES:raise ValueError('diagnostic bound exceeded')
    return result


def parse(stderr,action):
    unavailable={'boundary_phase':'UNKNOWN','category':'OTHER','boundary_reason':'DIAGNOSTIC_UNAVAILABLE'}
    if action not in ('doctor','start','setup','stop'):return unavailable
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
        if not isinstance(row,dict) or not expected<=set(row)<=expected|{'cleanup_category','acl_object','start_observation','identity_refusal','cleanup_identity_refusal'} or type(row['schema']) is not int or row['schema']!=1 or row['action']!=action:return unavailable
        for key,choices in (('boundary_phase',PHASES),('category',CATEGORIES),('boundary_reason',REASONS),('cleanup_category',CATEGORIES)):
            if key in row and (not isinstance(row[key],str) or row[key] not in choices):return unavailable
        if 'acl_object' in row and (row['boundary_phase']!='private_acl' or not isinstance(row['acl_object'],str) or row['acl_object'] not in ACL_OBJECTS):return unavailable
        if 'start_observation' in row:
            if action!='start':return unavailable
            row['start_observation']=start_observation(row['start_observation'])
        for key in ('identity_refusal','cleanup_identity_refusal'):
            if key in row:
                if action not in ('start','stop') or (key=='cleanup_identity_refusal' and (action!='start' or 'cleanup_category' not in row)):return unavailable
                row[key]=validate_identity_refusal(row[key])
        return {k:v for k,v in row.items() if k not in ('schema','action')}
    except (ValueError,TypeError,UnicodeError,RecursionError):return unavailable


def database_refusal_observation(exc,port):
    """Split a fixture's three golds; no exception text, DSN or port publication."""
    import psycopg
    row=failure(exc)
    exact=type(exc)
    kind='OPERATIONAL_ERROR' if exact is psycopg.OperationalError else 'CONNECTION_TIMEOUT' if exact is psycopg.errors.ConnectionTimeout else 'OTHER'
    # Observations preserve today's exact-type classifier; never accept OTHER.
    safe=command('start',exc)
    valid_port=type(port) is int and 1<=port<=65535
    return {'database_error':kind,'database_operational_family':isinstance(exc,psycopg.OperationalError),'database_phase_gold':row['boundary_phase']=='database_connect','database_category_gold':row['category']=='OperationalError','database_redaction_gold':valid_port and str(port) not in safe}
