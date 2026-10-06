"""Read one current owned report; rebuild bounded public fields, never cat private logs."""
import json
import os
from pathlib import Path
import re
import stat
from diagnostics import CATEGORIES,PHASES,MAX_FAILURE_IDS,MAX_CLEANUP,_allowed_tests,browser_summary
from summary_report import SCHEMA,ROOT_PATTERN,current_binding

MAX_BYTES=64*1024
MAX_ROWS=32
CASES=frozenset({'suite_initialization','suite_exception','lifecycle_exception','final_Stop_owned_services','full_engineering_regression','Win11_guard_refuses_Server','separate_Server_candidate_oracles','Setup_native','Setup_refuses_existing_config','config_sessions_preserved','Doctor_native','Start_native','Status_native','actual_API_worker_local_case','Stop_native','Restart_native','data_read_after_restart','native_local_browser','API_browser_restart','lifecycle_API_browser'})
REASONS=frozenset({'OWNED_STATUS_NOT_CONFIRMED','START_FAILED','SETUP_FAILED'})
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
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:raise ValueError('invalid summary rows')
    allowed=_allowed_tests();result=base('SUMMARY_AVAILABLE');result.update(report_state=state,active_phase=phase)
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('case'),str) or row['case'] not in CASES or row.get('status') not in ('PASS','FAIL','NOT_RUN'):raise ValueError('invalid summary row')
        public={'case':row['case'],'status':row['status']}
        if 'exit_code' in row:
            value=row['exit_code']
            if type(value) is not int or not -(2**31)<=value<2**32:raise ValueError('invalid summary exit')
            public['exit_code']=value
        for key,values,fallback in (('phase',PHASES,'UNKNOWN'),('category',CATEGORIES,'OTHER'),('reason',REASONS,'UNKNOWN')):
            if key in row:public[key]=row[key] if isinstance(row[key],str) and row[key] in values else fallback
        if row['case']=='full_engineering_regression':
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
        result=project(json.loads(data.decode('utf-8'),object_pairs_hook=strict_object,parse_constant=invalid_constant),current_binding(root,source))
        if len(json.dumps(result).encode('utf-8'))>MAX_BYTES:return base('SUMMARY_INVALID')
        return result
    except FileNotFoundError:return base('SUMMARY_MISSING')
    except (UnicodeError,ValueError,TypeError,KeyError,RuntimeError,RecursionError):return base('SUMMARY_INVALID')
    except OSError:return base('SUMMARY_UNREADABLE')


def main(source=None):
    source=os.environ if source is None else source
    public=read_summary(source);text=json.dumps(public,indent=2);console_ok=True;summary_ok=False
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
    return 0 if console_ok and summary_ok and public['publication_state']=='SUMMARY_AVAILABLE' else 1


if __name__=='__main__':raise SystemExit(main())
