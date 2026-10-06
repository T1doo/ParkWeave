"""Read one current owned report; rebuild bounded public fields, never cat private logs."""
import json
import os
from pathlib import Path
import re
import stat
import sys
from diagnostics import CATEGORIES,PHASES,MAX_FAILURE_IDS,MAX_CLEANUP,TREE_CLEANUP,_allowed_tests,browser_summary
from summary_report import SCHEMA,ROOT_PATTERN,current_binding
from lifecycle_diagnostics import PHASES as BOUNDARY_PHASES,REASONS as BOUNDARY_REASONS,CATEGORIES as BOUNDARY_CATEGORIES,ACL_OBJECTS,start_observation
from regression_progress import PHASES as REGRESSION_PHASES,observation as regression_observation
from stage_result import read_command, failure as command_failure

MAX_BYTES=64*1024
MAX_ROWS=32
MAX_ANNOTATIONS=8
MAX_ANNOTATION_BYTES=2048  # Entire UTF-8 workflow command, including final LF.
MAX_ANNOTATION_TOTAL_BYTES=16*1024
CASES=frozenset({'suite_initialization','suite_exception','lifecycle_exception','final_Stop_owned_services','full_engineering_regression','Win11_guard_refuses_Server','separate_Server_candidate_oracles','Setup_native','Setup_refuses_existing_config','config_sessions_preserved','Doctor_native','Start_native','Status_native','actual_API_worker_local_case','Stop_native','Restart_native','data_read_after_restart','native_local_browser','API_browser_restart','lifecycle_API_browser'})
REASONS=frozenset({'OWNED_STATUS_NOT_CONFIRMED','START_FAILED','SETUP_FAILED','TOTAL_BUDGET_EXHAUSTED','CLEANUP_NOT_CONFIRMED','VALIDATION_NOT_COMPLETED'})
STATES=frozenset({'UNAVAILABLE','AVAILABLE','JUNIT_PATH_REFUSED','ALLOWLIST_UNAVAILABLE','JUNIT_MISSING','JUNIT_UNREADABLE_OR_OVERSIZE','JUNIT_FORMAT_REFUSED','JUNIT_INVALID','JUNIT_CASE_LIMIT','REPORT_MISSING'})


def base(state):
    return {'scope':'WINDOWS_SERVER_ENGINEERING_NOT_WIN11','publication_state':state,'cases':[],'real_model_calls':0,'real_budget':0,'production_R4':'DISABLED','whole_AT_EX':'NOT_RUN','Win11':'NOT_RUN'}


def number(value,maximum=10000):return type(value) is int and 0<=value<=maximum


def failure_diagnostics(value,allowed):
    invalid={'state':'DIAGNOSTIC_FIELDS_INVALID','failed_test_ids':[]}
    if not isinstance(value,dict):return invalid
    if 'state' not in value or 'failed_test_ids' not in value:return {'state':'DIAGNOSTIC_FIELDS_MISSING','failed_test_ids':[]}
    state=value.get('state')
    if not isinstance(state,str) or state not in STATES:return invalid
    ids=value.get('failed_test_ids')
    if not isinstance(ids,list) or len(ids)>MAX_FAILURE_IDS or any(not isinstance(x,str) or x not in allowed for x in ids):return invalid
    result={'state':state,'failed_test_ids':sorted(set(ids))}
    for key in ('test_cases_seen','failed_cases','unknown_failed_cases'):
        if key in value:
            if not number(value[key]):return invalid
            result[key]=value[key]
    if 'ids_truncated' in value:
        if type(value['ids_truncated']) is not bool:return invalid
        result['ids_truncated']=value['ids_truncated']
    return result


def project(record,binding):
    if not isinstance(record,dict) or type(record.get('diagnostic_schema')) is not int or record['diagnostic_schema']!=SCHEMA or binding is None or record.get('diagnostic_binding')!=binding:raise ValueError('invalid summary binding')
    for key,value in (('scope','WINDOWS_SERVER_ENGINEERING_NOT_WIN11'),('production_R4','DISABLED'),('whole_AT_EX','NOT_RUN'),('Win11','NOT_RUN')):
        if record.get(key)!=value:raise ValueError('invalid summary scope')
    if any(type(record.get(k)) is not int or record[k]!=0 for k in ('real_model_calls','real_budget')):raise ValueError('invalid summary scope')
    state=record.get('report_state');phase=record.get('active_phase')
    if state not in ('IN_PROGRESS','COMPLETED') or not isinstance(phase,str) or phase not in PHASES:raise ValueError('invalid summary stage')
    rows=record.get('cases')
    if 'native_stage' in record and record['native_stage'] not in ('lifecycle','validation'):raise ValueError('invalid native stage')
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:raise ValueError('invalid summary rows')
    allowed=_allowed_tests();result=base('SUMMARY_AVAILABLE');result.update(report_state=state,active_phase=phase)
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('case'),str) or row['case'] not in CASES or row.get('status') not in ('PASS','FAIL','NOT_RUN'):raise ValueError('invalid summary row')
        if record.get('native_stage')=='lifecycle' and row['case'] in ('full_engineering_regression','Win11_guard_refuses_Server','separate_Server_candidate_oracles'):raise ValueError('invalid lifecycle row')
        public={'case':row['case'],'status':row['status']}
        if 'exit_code' in row:
            value=row['exit_code']
            if type(value) is not int or not -(2**31)<=value<2**32:raise ValueError('invalid summary exit')
            public['exit_code']=value
        for key,values,fallback in (('phase',PHASES,'UNKNOWN'),('category',CATEGORIES,'OTHER'),('reason',REASONS,'UNKNOWN')):
            if key in row:public[key]=row[key] if isinstance(row[key],str) and row[key] in values else fallback
        for key,values,fallback in (('boundary_phase',BOUNDARY_PHASES,'UNKNOWN'),('boundary_reason',BOUNDARY_REASONS,'DIAGNOSTIC_UNAVAILABLE'),('cleanup_category',BOUNDARY_CATEGORIES,'OTHER')):
            if key in row:
                if row['case'] not in ('Doctor_native','Start_native','Setup_native'):raise ValueError('invalid lifecycle case')
                public[key]=row[key] if isinstance(row[key],str) and row[key] in values else fallback
        if 'acl_object' in row:
            if row['case'] not in ('Doctor_native','Start_native','Setup_native') or row.get('boundary_phase')!='private_acl' or not isinstance(row['acl_object'],str) or row['acl_object'] not in ACL_OBJECTS:raise ValueError('invalid ACL object')
            public['acl_object']=row['acl_object']
        if 'start_observation' in row:
            if row['case']!='Start_native':raise ValueError('invalid start observation case')
            public['start_observation']=start_observation(row['start_observation'])
        if row['case']=='full_engineering_regression':
            if 'regression_observation' in row:public['regression_observation']=regression_observation(row['regression_observation'])
            if 'owned_tree_cleanup' in row:
                if not isinstance(row['owned_tree_cleanup'],str) or row['owned_tree_cleanup'] not in TREE_CLEANUP:raise ValueError('invalid tree cleanup')
                public['owned_tree_cleanup']=row['owned_tree_cleanup']
            if 'regression_phase' in row:public['regression_phase']=row['regression_phase'] if isinstance(row['regression_phase'],str) and row['regression_phase'] in REGRESSION_PHASES else 'UNKNOWN'
            if 'active_test_id' in row:
                if not isinstance(row['active_test_id'],str) or row['active_test_id'] not in allowed or 'regression_phase' not in row:raise ValueError('invalid active test')
                public['active_test_id']=row['active_test_id']
            counts=row.get('counts')
            if isinstance(counts,dict) and set(counts)=={'PASS','FAIL','SKIP'} and all(number(v) for v in counts.values()):public['counts']=dict(counts)
            else:public['counts_state']='MISSING' if counts is None else 'INVALID'
        if 'whole_AT_EX' in row:
            if row['whole_AT_EX']!='NOT_RUN':raise ValueError('invalid acceptance claim')
            public['whole_AT_EX']='NOT_RUN'
        if 'failure_diagnostics' in row:public['failure_diagnostics']=failure_diagnostics(row['failure_diagnostics'],allowed)
        if 'summary' in row:public['summary']=browser_summary(row['summary'])
        if 'owned_browser_cleanup_failures' in row:
            cleanup=row['owned_browser_cleanup_failures']
            if not isinstance(cleanup,list) or len(cleanup)>MAX_CLEANUP:raise ValueError('invalid cleanup metadata')
            public['owned_browser_cleanup_failures']=[x if isinstance(x,str) and x in CATEGORIES else 'OTHER' for x in cleanup]
            if not number(row.get('cleanup_failures_count')) or type(row.get('cleanup_categories_truncated')) is not bool:raise ValueError('invalid cleanup metadata')
            public.update(cleanup_failures_count=row['cleanup_failures_count'],cleanup_categories_truncated=row['cleanup_categories_truncated'])
        if 'cleanup_diagnostics' in row:public['cleanup_diagnostics']='INVALID_METADATA'
        result['cases'].append(public)
    return result


def linked(path):
    info=path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024))


def strict_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate summary field')
        result[key]=value
    return result


def invalid_constant(value):raise ValueError('invalid JSON constant')


def read_summary(source):
    if not source.get('PARKWEAVE_CI_ROOT') or not source.get('RUNNER_TEMP'):return base('SUMMARY_MISSING')
    try:
        root=Path(source['PARKWEAVE_CI_ROOT']);temporary=Path(source['RUNNER_TEMP']);report=root/'engineering.json'
        if not root.is_absolute() or not temporary.is_absolute() or not re.fullmatch(ROOT_PATTERN,root.name) or root.parent!=temporary or root.resolve()!=root or temporary.resolve()!=temporary or linked(root) or linked(temporary):return base('SUMMARY_INVALID')
        if linked(report) or report.resolve()!=report:return base('SUMMARY_INVALID')
        with report.open('rb') as stream:data=stream.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:return base('SUMMARY_INVALID')
        record=json.loads(data.decode('utf-8'),object_pairs_hook=strict_object,parse_constant=invalid_constant)
        binding=current_binding(root,source);result=project(record,binding)
        if record.get('native_stage') in ('lifecycle','validation'):
            try:
                failure=command_failure(read_command(root/(record['native_stage']+'-command.json'),binding),'suite_exception')
            except (OSError,UnicodeError,ValueError,TypeError,KeyError,RuntimeError,RecursionError):
                failure={'case':'suite_exception','status':'FAIL','phase':'final_stop','category':'RuntimeError','reason':'CLEANUP_NOT_CONFIRMED'}
            if failure is not None:result['cases'].append(failure)
            if record['native_stage']=='lifecycle':result['cases'].append({'case':'full_engineering_regression','status':'NOT_RUN','phase':'regression_run','reason':'VALIDATION_NOT_COMPLETED'})
        if len(json.dumps(result).encode('utf-8'))>MAX_BYTES:return base('SUMMARY_INVALID')
        return result
    except FileNotFoundError:return base('SUMMARY_MISSING')
    except (UnicodeError,ValueError,TypeError,KeyError,RuntimeError,RecursionError):return base('SUMMARY_INVALID')
    except OSError:return base('SUMMARY_UNREADABLE')


def annotation_command(value):
    # One constant property, no file/line/location or caller-supplied title.
    data=json.dumps(value,ensure_ascii=True,separators=(',',':'))
    data=data.replace('%','%25').replace('\r','%0D').replace('\n','%0A')
    return '::notice title=ParkWeave safe diagnostics::'+data


def annotation_size(command):return len((command+'\n').encode('utf-8'))


def annotation_case(row,allowed):
    if not isinstance(row,dict) or row.get('case') not in CASES or row.get('status') not in ('PASS','FAIL','NOT_RUN'):raise ValueError('invalid case')
    value={'kind':'case','case':row['case'],'status':row['status']}
    if 'exit_code' in row:
        n=row['exit_code']
        if type(n) is not int or not -(2**31)<=n<2**32:raise ValueError('invalid exit')
        value['exit_code']=n
    for key,choices in (('phase',PHASES),('category',CATEGORIES),('reason',REASONS|{'UNKNOWN'}),('counts_state',{'MISSING','INVALID'})):
        if key in row:
            if not isinstance(row[key],str) or row[key] not in choices:raise ValueError('invalid enum')
            value[key]=row[key]
    for key,choices in (('boundary_phase',BOUNDARY_PHASES),('boundary_reason',BOUNDARY_REASONS),('cleanup_category',BOUNDARY_CATEGORIES)):
        if key in row:
            if row['case'] not in ('Doctor_native','Start_native','Setup_native') or not isinstance(row[key],str) or row[key] not in choices:raise ValueError('invalid lifecycle field')
            value[key]=row[key]
    if 'acl_object' in row:
        if row['case'] not in ('Doctor_native','Start_native','Setup_native') or row.get('boundary_phase')!='private_acl' or not isinstance(row['acl_object'],str) or row['acl_object'] not in ACL_OBJECTS:raise ValueError('invalid ACL object')
        value['acl_object']=row['acl_object']
    for key,case,validator in (('start_observation','Start_native',start_observation),('regression_observation','full_engineering_regression',regression_observation)):
        if key in row:
            if row['case']!=case:raise ValueError('invalid observation case')
            value[key]=validator(row[key])
    if 'owned_tree_cleanup' in row:
        if row['case']!='full_engineering_regression' or not isinstance(row['owned_tree_cleanup'],str) or row['owned_tree_cleanup'] not in TREE_CLEANUP:raise ValueError('invalid tree cleanup')
        value['owned_tree_cleanup']=row['owned_tree_cleanup']
    if 'regression_phase' in row:
        if row['case']!='full_engineering_regression' or not isinstance(row['regression_phase'],str) or row['regression_phase'] not in REGRESSION_PHASES:raise ValueError('invalid regression phase')
        value['regression_phase']=row['regression_phase']
    if 'active_test_id' in row:
        test=row['active_test_id']
        if row['case']!='full_engineering_regression' or 'regression_phase' not in row or not isinstance(test,str) or test not in allowed or not re.fullmatch(r'tests/test_[a-z0-9_]+\.py::test_[A-Za-z0-9_]+',test):raise ValueError('invalid active test')
        value['active_test_id']=test.removeprefix('tests/').replace('.py::','::')
    if 'counts' in row:
        counts=row['counts']
        if row['case']!='full_engineering_regression' or not isinstance(counts,dict) or set(counts)!={'PASS','FAIL','SKIP'} or not all(number(n) for n in counts.values()):raise ValueError('invalid counts')
        value['counts']=dict(counts)
    if 'failure_diagnostics' in row:
        d=row['failure_diagnostics'];states=STATES|{'DIAGNOSTIC_FIELDS_INVALID','DIAGNOSTIC_FIELDS_MISSING'}
        if not isinstance(d,dict) or d.get('state') not in states:raise ValueError('invalid diagnostic')
        ids=d.get('failed_test_ids')
        if not isinstance(ids,list) or len(ids)>MAX_FAILURE_IDS or any(not isinstance(x,str) or x not in allowed or not re.fullmatch(r'tests/test_[a-z0-9_]+\.py::test_[A-Za-z0-9_]+',x) for x in ids):raise ValueError('invalid IDs')
        # Stable allowlisted test identifiers, without repository/runtime paths.
        value['diagnostic_state']=d['state']
        value['failed_test_ids']=[x.split('::')[0].removeprefix('tests/').removesuffix('.py')+'::'+x.split('::')[1] for x in sorted(set(ids))]
        for key in ('test_cases_seen','failed_cases','unknown_failed_cases'):
            if key in d:
                if not number(d[key]):raise ValueError('invalid diagnostic count')
                value[key]=d[key]
        if 'ids_truncated' in d:
            if type(d['ids_truncated']) is not bool:raise ValueError('invalid truncation flag')
            value['ids_truncated']=d['ids_truncated']
    return value


def annotation_commands(public):
    """Prevalidate the entire batch; errors produce only one constant notice.

    At most seven FAIL/NOT_RUN rows, 25 test IDs across the entire batch. Drop
    whole IDs/rows with explicit omission counts, never truncate JSON or IDs.
    These notices report observations and cannot change the native result.
    """
    unavailable=annotation_command({'kind':'publication','state':'ANNOTATIONS_UNAVAILABLE'})
    try:
        if not isinstance(public,dict) or public.get('publication_state')!='SUMMARY_AVAILABLE':return [unavailable],False
        for key,expected in (('scope','WINDOWS_SERVER_ENGINEERING_NOT_WIN11'),('production_R4','DISABLED'),('whole_AT_EX','NOT_RUN'),('Win11','NOT_RUN')):
            if public.get(key)!=expected:raise ValueError('invalid scope')
        if any(type(public.get(k)) is not int or public[k]!=0 for k in ('real_model_calls','real_budget')):raise ValueError('invalid scope')
        if public.get('report_state') not in ('IN_PROGRESS','COMPLETED') or public.get('active_phase') not in PHASES:raise ValueError('invalid stage')
        rows=public.get('cases')
        if not isinstance(rows,list) or len(rows)>MAX_ROWS:raise ValueError('invalid rows')
        allowed=_allowed_tests();values=[annotation_case(row,allowed) for row in rows]
        candidates=[row for row in values if row['status']!='PASS']+[row for row in values if row['status']=='PASS' and ('start_observation' in row or 'regression_observation' in row)];remaining=MAX_FAILURE_IDS;commands=[]
        for row in candidates[:MAX_ANNOTATIONS-1]:
            original=len(row.get('failed_test_ids',[]))
            active_original=int('active_test_id' in row)
            active_kept=active_original if remaining else 0
            if active_original and not active_kept:row.pop('active_test_id')
            if 'failed_test_ids' in row:
                row['failed_test_ids']=row['failed_test_ids'][:remaining-active_kept]
                row['annotation_ids_omitted']=original-len(row['failed_test_ids'])
                row['ids_truncated']=row.get('ids_truncated',False) or row['annotation_ids_omitted']>0
            if active_original:
                row['annotation_ids_omitted']=row.get('annotation_ids_omitted',0)+active_original-active_kept
                row['ids_truncated']=row.get('ids_truncated',False) or not active_kept
            while True:
                command=annotation_command(row)
                if annotation_size(command)<=MAX_ANNOTATION_BYTES:break
                if not row.get('failed_test_ids'):raise ValueError('oversize row')
                row['failed_test_ids'].pop();row['annotation_ids_omitted']+=1;row['ids_truncated']=True
            remaining-=len(row.get('failed_test_ids',[]))+active_kept;commands.append(command)
        header={'kind':'publication','state':'SUMMARY_AVAILABLE','report_state':public['report_state'],'active_phase':public['active_phase'],
                'case_counts':{s:sum(row['status']==s for row in values) for s in ('PASS','FAIL','NOT_RUN')},'annotation_cases_omitted':len(candidates)-len(commands)}
        commands.insert(0,annotation_command(header))
        if len(commands)>MAX_ANNOTATIONS or any(annotation_size(c)>MAX_ANNOTATION_BYTES for c in commands) or sum(annotation_size(c) for c in commands)>MAX_ANNOTATION_TOTAL_BYTES:raise ValueError('oversize annotations')
        return commands,True
    except Exception:return [unavailable],False


def write_annotations(commands,stream=None):
    # Bypass Windows TextIOWrapper CRLF translation for exact UTF-8/LF limits.
    # Flush the preceding JSON text before using the same underlying buffer.
    if stream is None:
        sys.stdout.flush();stream=sys.stdout.buffer
    data=('\n'.join(commands)+'\n').encode('utf-8')
    if len(data)>MAX_ANNOTATION_TOTAL_BYTES or any(annotation_size(c)>MAX_ANNOTATION_BYTES for c in commands):raise ValueError('oversize annotation sink')
    if stream.write(data)!=len(data):raise OSError('incomplete annotation sink')
    stream.flush()


def main(source=None):
    source=os.environ if source is None else source
    public=read_summary(source);text=json.dumps(public,indent=2)
    if len(text.encode('utf-8'))>MAX_BYTES:text=json.dumps(public,separators=(',',':'))
    console_ok=True;summary_ok=False
    # Independent outputs: a console failure must not suppress the Job Summary.
    try:print(text)
    except (OSError,UnicodeError):console_ok=False
    try:
        target=source.get('GITHUB_STEP_SUMMARY')
        if target:
            path=Path(target)
            if path.resolve()!=path or (path.exists() and linked(path)):raise ValueError('summary output binding refused')
            with path.open('a',encoding='utf-8') as stream:stream.write('Windows Server safe engineering diagnostics (not Win11 acceptance)\n\n```json\n'+text+'\n```\n')
            summary_ok=True
    except (OSError,ValueError,TypeError,UnicodeError,RuntimeError,RecursionError):pass
    # Validate everything before printing any command. A failed annotation sink
    # must not suppress the independent safe console/Job Summary outputs.
    commands,annotations_ok=annotation_commands(public)
    try:write_annotations(commands)
    except Exception:annotations_ok=False
    return 0 if console_ok and summary_ok and annotations_ok and public['publication_state']=='SUMMARY_AVAILABLE' else 1


if __name__=='__main__':raise SystemExit(main())
