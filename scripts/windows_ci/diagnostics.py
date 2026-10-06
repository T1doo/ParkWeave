"""Bounded public diagnosis from trusted identifiers; never echo private evidence."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
from lifecycle_diagnostics import CATEGORIES as LIFECYCLE_CATEGORIES

MAX_REPORT_BYTES=512*1024
MAX_JUNIT_BYTES=4*1024*1024
MAX_TEST_CASES=10000
MAX_FAILURE_IDS=25
MAX_CLEANUP=6
TREE_CLEANUP=frozenset({'NOT_STARTED','SUSPENDED_CHILD_STOPPED','OWNED_TREE_STOPPED','OWNED_TREE_STOP_UNCONFIRMED'})
CATEGORIES=frozenset({'AssertionError','AttributeError','KeyError','TypeError','ValueError','RuntimeError','OSError','FileNotFoundError','PermissionError','TimeoutError','ConnectionError','ConnectionRefusedError','JSONDecodeError','UnicodeDecodeError','TimeoutExpired','CalledProcessError','HTTPError','URLError','UnsupportedOperation','NotImplementedError','IndexError','ImportError','ModuleNotFoundError','BrokenPipeError','ProcessLookupError','LookupError','OverflowError','OTHER'})
PHASES=frozenset({'UNKNOWN','configuration','managed_python','setup','existing_config','config_preservation','doctor','start','status','session_read','api_case_submit','api_case_wait','stop','stop_record_check','restart','restart_read','native_browser','final_stop','regression_run','regression_report','win11_guard','server_candidate','browser_guard','browser_driver_binding','browser_start','browser_driver_ready','browser_session','browser_navigation','browser_case_create','browser_case_read','browser_render','browser_fact_parent','browser_fact_review','browser_clarification','browser_child_review','browser_cancel','browser_cleanup'})
CATEGORIES=CATEGORIES|LIFECYCLE_CATEGORIES
CATEGORIES=CATEGORIES|{'OwnedJobError'}
CASES=frozenset({'suite_initialization','suite_exception','lifecycle_exception','final_Stop_owned_services','full_engineering_regression','Win11_guard_refuses_Server','separate_Server_candidate_oracles'})
ACCEPTANCE_REASONS={
    'INPUT_CONTRACT':frozenset({'INPUT_CONTRACT_INVALID'}),
    'SOURCE_BINDING':frozenset({'SOURCE_BINDING_INVALID','SOURCE_HEAD_UNAVAILABLE','SOURCE_HEAD_MISMATCH','GIT_BLOB_UNAVAILABLE','GIT_BLOB_MISMATCH'}),
    'ACCEPTANCE_BINDINGS':frozenset({'ACCEPTANCE_BINDINGS_INVALID'}),
    'JOB_BUDGET':frozenset({'JOB_BUDGET_REFUSED'}),
    'MANIFEST':frozenset({'MANIFEST_SCHEMA_REFUSED','MANIFEST_READ_FAILED','MANIFEST_SOURCE_SET_MISMATCH','MANIFEST_HASH_MISMATCH'}),
    'REGRESSION_EXECUTION':frozenset({'REGRESSION_EXECUTION_FAILED'}),
    'REPORT_SUMMARY':frozenset({'REPORT_SUMMARY_FAILED'}),'REPORT_WRITE':frozenset({'REPORT_WRITE_FAILED'})}


def acceptance_failure(value):
    if not isinstance(value,dict) or set(value)!={'stage','reason','category'} or not isinstance(value['stage'],str) or value['stage'] not in ACCEPTANCE_REASONS or not isinstance(value['reason'],str) or value['reason'] not in ACCEPTANCE_REASONS[value['stage']] or not isinstance(value['category'],str) or value['category'] not in CATEGORIES:raise ValueError('invalid acceptance failure')
    return dict(value)


def source_binding(value):
    if not isinstance(value,dict) or not isinstance(value.get('state'),str):raise ValueError('invalid source binding')
    if value['state']=='UNAVAILABLE' and set(value)=={'state'}:return dict(value)
    if value['state'] not in ('HEAD_ONLY','AVAILABLE') or set(value)!={'state','head_sha'} or not isinstance(value['head_sha'],str) or not re.fullmatch(r'[0-9a-f]{40}',value['head_sha']):raise ValueError('invalid source binding')
    return dict(value)


def category(value):return value if isinstance(value,str) and value in CATEGORIES else 'OTHER'


def exception_row(case,exc,phase='UNKNOWN'):
    try:attributes=vars(exc)
    except Exception:attributes={}
    if not isinstance(attributes,dict):attributes={}
    explicit=attributes.get('parkweave_diagnostic_phase')
    phase=explicit if isinstance(explicit,str) and explicit in PHASES else phase
    row={'case':case if isinstance(case,str) and case in CASES else 'suite_exception','status':'FAIL','phase':phase if isinstance(phase,str) and phase in PHASES else 'UNKNOWN','category':category(type(exc).__name__)}
    tree=attributes.get('parkweave_owned_tree_cleanup')
    if case=='full_engineering_regression' and isinstance(tree,str) and tree in TREE_CLEANUP:row['owned_tree_cleanup']=tree
    cleanup=attributes.get('parkweave_owned_browser_cleanup',())
    if isinstance(cleanup,(tuple,list)):
        if not cleanup:return row
        row['owned_browser_cleanup_failures']=[category(x) for x in cleanup[:MAX_CLEANUP]]
        row['cleanup_failures_count']=min(len(cleanup),MAX_TEST_CASES)
        row['cleanup_categories_truncated']=len(cleanup)>MAX_CLEANUP
    elif cleanup is not None:row['cleanup_diagnostics']='INVALID_METADATA'
    return row


def tag_phase(exc,phase):
    if isinstance(phase,str) and phase in PHASES:exc.parkweave_diagnostic_phase=phase
    return exc


def _bounded_bytes(path,limit):
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('diagnostic input too large')
    return data


def read_report(path):
    data=json.loads(_bounded_bytes(path,MAX_REPORT_BYTES))
    if not isinstance(data,dict):raise ValueError('invalid diagnostic report structure')
    counts=data['engineering_total_counts']
    if not isinstance(counts,dict) or set(counts)!={'PASS','FAIL','SKIP'} or any(type(x) is not int or not 0<=x<=MAX_TEST_CASES for x in counts.values()) or data['whole_AT_EX']!='NOT_RUN':raise ValueError('invalid diagnostic report metadata')
    if 'source_binding' in data:source_binding(data['source_binding'])
    if 'acceptance_failure' in data:acceptance_failure(data['acceptance_failure'])
    return data,dict(counts)


def _allowed_tests():
    value=json.loads(_bounded_bytes(Path(__file__).with_name('diagnostic-test-ids.json'),256*1024))
    if not isinstance(value,dict) or set(value)!={'schema','test_ids'} or type(value['schema']) is not int or value['schema']!=1:raise ValueError('invalid allowlist')
    ids=value['test_ids']
    if not isinstance(ids,list) or not 0<len(ids)<=3000 or any(not isinstance(x,str) or len(x)>256 or not re.fullmatch(r'tests/test_[a-z0-9_]+\.py::test_[A-Za-z0-9_]+',x) for x in ids) or len(set(ids))!=len(ids):raise ValueError('invalid allowlist')
    return frozenset(ids)


def failure_tests(repo,private_junit):
    result={'state':'UNAVAILABLE','failed_test_ids':[],'test_cases_seen':0,'failed_cases':0,'unknown_failed_cases':0,'ids_truncated':False}
    if not isinstance(private_junit,str) or len(private_junit)>128 or not re.fullmatch(r'\.runtime[/\\]pytest-[0-9a-f]{32}\.xml',private_junit):return {**result,'state':'JUNIT_PATH_REFUSED'}
    runtime=Path(repo).resolve()/'.runtime';path=runtime/private_junit.replace('\\','/').split('/')[-1]
    try:
        if runtime.resolve()!=runtime or path.resolve()!=path:return {**result,'state':'JUNIT_PATH_REFUSED'}
        allowed=_allowed_tests()
    except (OSError,ValueError,TypeError,KeyError):return {**result,'state':'ALLOWLIST_UNAVAILABLE'}
    try:data=_bounded_bytes(path,MAX_JUNIT_BYTES)
    except FileNotFoundError:return {**result,'state':'JUNIT_MISSING'}
    except (OSError,ValueError):return {**result,'state':'JUNIT_UNREADABLE_OR_OVERSIZE'}
    try:xml=data.decode('utf-8')
    except UnicodeDecodeError:return {**result,'state':'JUNIT_FORMAT_REFUSED'}
    # NUL rejects UTF-16 without BOM as well as invalid XML; parse text, never auto-detect bytes.
    declaration=re.match(r'<\?xml\b[^?]*\?>',xml.lstrip('\ufeff'))
    encoding=re.search(r'\bencoding\s*=\s*[\"\']([^\"\']+)',declaration.group(0),re.I) if declaration else None
    if '\x00' in xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper() or (encoding and encoding.group(1).lower() not in ('utf-8','utf8','us-ascii')):return {**result,'state':'JUNIT_FORMAT_REFUSED'}
    try:root=ET.fromstring(xml)
    except (ET.ParseError,ValueError):return {**result,'state':'JUNIT_INVALID'}
    if root.tag not in ('testsuite','testsuites'):return {**result,'state':'JUNIT_FORMAT_REFUSED'}
    ids=set();result['state']='AVAILABLE'
    for entry in root.iter('testcase'):
        if result['test_cases_seen']>=MAX_TEST_CASES:return {**result,'state':'JUNIT_CASE_LIMIT','failed_test_ids':sorted(ids)[:MAX_FAILURE_IDS],'ids_truncated':True}
        result['test_cases_seen']+=1
        if entry.find('failure') is None and entry.find('error') is None:continue
        result['failed_cases']+=1
        classname=entry.get('classname','');name=entry.get('name','')
        # Parameters, traceback, message, properties and stdout never become identifiers.
        if len(classname)>128 or len(name)>512:
            result['unknown_failed_cases']+=1;continue
        name=name.split('[',1)[0]
        module=classname.removeprefix('tests.')
        candidate='tests/'+module+'.py::'+name
        if candidate in allowed and classname in (module,'tests.'+module):ids.add(candidate)
        else:result['unknown_failed_cases']+=1
    result['failed_test_ids']=sorted(ids)[:MAX_FAILURE_IDS];result['ids_truncated']=len(ids)>MAX_FAILURE_IDS
    return result


def browser_summary(value):
    # No arbitrary versions, environment strings, goal text or additional keys.
    result={}
    if not isinstance(value,dict):return result
    for field,expected in (('case','NEEDS_INPUT'),('clarification','UNKNOWN')):
        if value.get(field)==expected:result[field]=expected
    for field in ('cancel_only_followup','injection_text_only'):
        if type(value.get(field)) is bool:result[field]=value[field]
    n=value.get('grouped_questions')
    if type(n) is int and 0<=n<=100:result['grouped_questions']=n
    return result


SHARD_REASONS=frozenset({'NOT_STARTED','IN_PROGRESS','TOTAL_BUDGET_EXHAUSTED','CLEANUP_NOT_CONFIRMED','CLEANUP_UNCONFIRMED','COMPLETE','COVERAGE_MISMATCH','SHARD_ERROR','SOURCE_CHANGED','PRECHECK_FAILED','EXECUTION_RECORDED'})

def shard_summary(rows, *, projected=False):
    """Four fixed rows only; elapsed covers each invocation and result parsing.

    It excludes global collection and final report writing. Null means no
    observation; missing cleanup never becomes confirmed cleanup.
    """
    if not isinstance(rows,list) or len(rows)!=4:raise ValueError('four shard rows required')
    result=[]
    internal={'id','status','reason','expected_cases','counts','elapsed_ms','owned_tree_cleanup','coverage_complete','exit_code','category'}
    compact={'id','status','reason','counts','ms','cleanup','coverage','exit','category'}
    for index,row in enumerate(rows,1):
        if not isinstance(row,dict) or set(row)-(compact if projected else internal) or row.get('id')!='S'+str(index):raise ValueError('invalid shard identity')
        status=row.get('status');reason=row.get('reason')
        if not isinstance(status,str) or status not in ('NOT_RUN','RUNNING','PASS','FAIL') or not isinstance(reason,str) or reason not in SHARD_REASONS:raise ValueError('invalid shard status')
        counts=row.get('counts')
        if counts is not None and (not isinstance(counts,dict) or set(counts)!={'PASS','FAIL','SKIP'} or any(type(v) is not int or not 0<=v<=MAX_TEST_CASES for v in counts.values())):raise ValueError('invalid shard counts')
        elapsed=row.get('ms' if projected else 'elapsed_ms')
        if elapsed is not None and (type(elapsed) is not int or not 0<=elapsed<=1500000):raise ValueError('invalid shard time')
        cleanup=row.get('cleanup' if projected else 'owned_tree_cleanup','UNAVAILABLE')
        if not isinstance(cleanup,str) or cleanup not in TREE_CLEANUP|{'UNAVAILABLE'}:raise ValueError('invalid shard cleanup')
        coverage=row.get('coverage' if projected else 'coverage_complete')
        if coverage is not None and type(coverage) is not bool:raise ValueError('invalid shard coverage')
        code=row.get('exit' if projected else 'exit_code')
        if code is not None and (type(code) is not int or not -(2**31)<=code<2**32):raise ValueError('invalid shard exit')
        public={'id':row['id'],'status':status,'reason':reason,'counts':dict(counts) if counts is not None else None,'ms':elapsed,'cleanup':cleanup,'coverage':coverage,'exit':code}
        if 'category' in row:public['category']=category(row['category'])
        result.append(public)
    return result
