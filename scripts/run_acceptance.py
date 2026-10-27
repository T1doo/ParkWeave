"""Engineering execution with fixed bindings; whole AT/EX never inferred from pytest."""
import os
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from parkweave.process_env import minimal_environment
sys.path.insert(0,str(Path(__file__).resolve().parent/'windows_ci'))
from regression_progress import write as progress_write,read_snapshot as progress_read

ROOT=Path(__file__).resolve().parents[1]


def validate_bindings(bindings,spec):
    expected={c['id'] for c in spec['cases']};rows=bindings['cases']
    if len(rows)!=len(expected) or {c['id'] for c in rows}!=expected:raise ValueError('missing/duplicate fixed acceptance IDs')
    for row in rows:
        if row['whole_status']!='NOT_RUN':raise ValueError('whole acceptance status cannot be prefilled PASS')
        for selector in row['engineering_selectors']:
            if not re.fullmatch(r'tests/test_[a-z0-9_]+\.py::test_[a-z0-9_]+',selector):raise ValueError('unsafe selector')
            if not (ROOT/selector.split('::')[0]).is_file():raise ValueError('missing bound test file')
    return rows


def summarize(rows,junit,exit_code):
    results={}
    for case in ET.parse(junit).getroot().iter('testcase'):
        classname=case.get('classname','').split('.')[-1]
        selector='tests/'+classname+'.py::'+case.get('name','').split('[')[0]
        outcome='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        results.setdefault(selector,[]).append(outcome)
    reports=[]
    for row in rows:
        statuses=[s for selector in row['engineering_selectors'] for s in results.get(selector,[])]
        missing=[s for s in row['engineering_selectors'] if s not in results]
        state='NOT_RUN' if not statuses else 'FAIL' if 'FAIL' in statuses else 'INCOMPLETE' if missing else 'SKIP' if all(s=='SKIP' for s in statuses) else 'PARTIAL_PASS_WITH_SKIPS' if 'SKIP' in statuses else 'PARTIAL_PASS'
        reports.append({'id':row['id'],'stage':row['stage'],'whole_status':'NOT_RUN','engineering_subset':state,
                        'counts':{s:statuses.count(s) for s in ('PASS','FAIL','SKIP')},'missing_selectors':missing,'gate':row['gate']})
    all_statuses=[s for values in results.values() for s in values]
    return {'execution_exit_code':exit_code,'whole_AT_EX':'NOT_RUN','engineering_total_counts':{s:all_statuses.count(s) for s in ('PASS','FAIL','SKIP')},'cases':reports,
            'note':'Selectors can overlap; do not sum per-AT counts. Local/mock PASS never completes LIVE/native/business acceptance.'}


FAILURE_REASONS={'INPUT_CONTRACT':'INPUT_CONTRACT_INVALID','SOURCE_BINDING':'SOURCE_BINDING_INVALID',
                 'ACCEPTANCE_BINDINGS':'ACCEPTANCE_BINDINGS_INVALID','JOB_BUDGET':'JOB_BUDGET_REFUSED',
                 'MANIFEST':'MANIFEST_SCHEMA_REFUSED','REGRESSION_EXECUTION':'REGRESSION_EXECUTION_FAILED',
                 'REPORT_SUMMARY':'REPORT_SUMMARY_FAILED','REPORT_WRITE':'REPORT_WRITE_FAILED'}


def source_binding(head):
    if head is None:return {'state':'UNAVAILABLE'}
    if not isinstance(head,str) or not re.fullmatch(r'[0-9a-f]{40}',head):raise ValueError('source binding refused')
    from source_bytes import verify_head
    return {'state':'HEAD_ONLY','head_sha':verify_head(ROOT,head)}


def write_report(path,value):
    path=Path(path);temporary=path.with_name('.acceptance-'+uuid.uuid4().hex+'.tmp')
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary.write_text(json.dumps(value,ensure_ascii=True,indent=2)+'\n',encoding='ascii')
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def rejected_report(args,stage,error,binding,code=None,context=None):
    from diagnostics import category,acceptance_failure,shard_summary
    original_stage=stage
    reason=getattr(error,'acceptance_failure_reason',getattr(error,'reason',FAILURE_REASONS[stage]))
    stage=getattr(error,'acceptance_failure_stage',stage)
    if reason in ('SOURCE_HEAD_UNAVAILABLE','SOURCE_HEAD_MISMATCH','GIT_BLOB_UNAVAILABLE','GIT_BLOB_MISMATCH'):stage='SOURCE_BINDING'
    failure={'stage':stage,'reason':reason,'category':'ValueError' if isinstance(error,ValueError) else category(type(error).__name__)}
    try:failure=acceptance_failure(failure)
    except ValueError:failure={'stage':original_stage,'reason':FAILURE_REASONS[original_stage],'category':category(type(error).__name__)}
    if code is None and isinstance(context,dict):code=context.get('execution_exit_code')
    exit_code=code if type(code) is int and code!=0 else 1
    report={'execution_exit_code':exit_code,'whole_AT_EX':'NOT_RUN','engineering_total_counts':{'PASS':0,'FAIL':0,'SKIP':0},
            'counts_scope':'OBSERVED','observed_cases':0,'coverage_complete':False,'full_regression':False,
            'source_binding':binding,'acceptance_failure':failure,
            'cases':[],'shards':[{'id':'S'+str(i),'status':'NOT_RUN','reason':'PRECHECK_FAILED','counts':{'PASS':0,'FAIL':0,'SKIP':0},'elapsed_ms':None,'owned_tree_cleanup':'NOT_STARTED'} for i in range(1,5)] if args.shards else []}
    if isinstance(context,dict):
        counts=context.get('engineering_total_counts')
        if isinstance(counts,dict) and set(counts)=={'PASS','FAIL','SKIP'} and all(type(v) is int and 0<=v<=10000 for v in counts.values()):
            report['engineering_total_counts']=dict(counts);report['observed_cases']=sum(counts.values())
        else:report.update(counts_scope='UNAVAILABLE',observed_cases=None)
        if args.shards:
            for row in report['shards']:
                row.update(status='FAIL',reason='EXECUTION_RECORDED',counts=None,elapsed_ms=None,owned_tree_cleanup='UNAVAILABLE')
        context_rows=context.get('shards')
        if args.shards and isinstance(context_rows,list):
            for index,row in enumerate(context_rows[:4]):
                if not isinstance(row,dict) or row.get('id')!='S'+str(index+1):continue
                candidate={**report['shards'][index],**row}
                if 'counts' not in row:candidate['counts']=None
                if 'reason' not in row:candidate['reason']='EXECUTION_RECORDED'
                if 'owned_tree_cleanup' not in row:candidate['owned_tree_cleanup']='UNAVAILABLE'
                try:
                    batch=list(report['shards']);batch[index]=candidate
                    safe=shard_summary(batch)[index]
                except ValueError:continue
                report['shards'][index]={'id':safe['id'],'status':safe['status'],'reason':safe['reason'],'counts':safe['counts'],
                    'elapsed_ms':safe['ms'],'owned_tree_cleanup':safe['cleanup'],'coverage_complete':safe['coverage'],'exit_code':safe['exit'],
                    **({'category':safe['category']} if 'category' in safe else {})}
    elif original_stage in ('REPORT_SUMMARY','REPORT_WRITE') and code is not None:
        report.update(counts_scope='UNAVAILABLE',observed_cases=None)
    saved=True
    try:write_report(args.report,report)
    except Exception:saved=False
    print(json.dumps({'whole_AT_EX':'NOT_RUN','engineering_exit_code':exit_code,'report_state':'AVAILABLE' if saved else 'UNAVAILABLE',
                      'acceptance_failure':report['acceptance_failure'],'source_binding':binding}))
    raise SystemExit(exit_code)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,default=ROOT/'.runtime/engineering-acceptance.json')
    parser.add_argument('--ids',help='Optional comma-separated fixed IDs; default runs full engineering regression')
    parser.add_argument('--progress',type=Path,help='Optional private fixed-phase diagnostic checkpoint')
    parser.add_argument('--shards',type=Path,help='Opt-in fixed-file shard manifest; default remains unsharded')
    parser.add_argument('--shard-budget',type=float,default=900,help='Total seconds: default maximum 900, explicit staged cutoff maximum 1290')
    parser.add_argument('--job-test-deadline',type=float,help='Explicit staged job cutoff; default limits remain unchanged')
    parser.add_argument('--job-test-uptime',type=int,help='Shared kernel uptime cutoff in milliseconds')
    parser.add_argument('--source-head',help='Explicit parent source SHA; missing local binding is unavailable')
    args=parser.parse_args()
    stage='SOURCE_BINDING';binding={'state':'UNAVAILABLE'};code=None
    try:
        binding=source_binding(args.source_head)
        stage='INPUT_CONTRACT'
        if args.shards and args.ids:raise ValueError('shards require complete engineering collection, not selected AT IDs')
        stage='JOB_BUDGET'
        if args.job_test_deadline is not None:
            if not args.shards or args.job_test_uptime is None:raise ValueError('job cutoff requires fixed shards and shared uptime')
            from job_budget import JobBudget
            JobBudget(args.job_test_deadline,uptime_deadline=args.job_test_uptime)
        elif args.job_test_uptime is not None:raise ValueError('uptime cutoff requires wall cutoff')
        if args.shards and not ((0<=args.shard_budget if args.job_test_deadline is not None else 0<args.shard_budget) and args.shard_budget<=(1290 if args.job_test_deadline is not None else 900)):raise ValueError('shard budget exceeds bounded stage envelope')
        stage='ACCEPTANCE_BINDINGS'
        progress_write(args.progress,'acceptance_bindings')
        bindings=json.loads((ROOT/'docs/F1/ATBindings.json').read_text(encoding='utf-8'));spec=json.loads((ROOT/'docs/验收规格.json').read_text(encoding='utf-8'))
        rows=validate_bindings(bindings,spec)
        if args.ids:
            ids=set(args.ids.split(','))
            if not ids<={r['id'] for r in rows}:raise ValueError('unknown fixed acceptance ID')
            rows=[r for r in rows if r['id'] in ids]
        stage='REPORT_WRITE'
        private=ROOT/'.runtime';private.mkdir(mode=0o700,exist_ok=True)
        junit=private/('pytest-'+uuid.uuid4().hex+'.xml');log=private/('pytest-'+uuid.uuid4().hex+'.log')
        selectors=sorted({s for r in rows for s in r['engineering_selectors']}) if args.ids else ['tests']
        code=0
        shard_result=None
        if args.shards:
            stage='MANIFEST'
            from regression_shards import execute
            env=minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src'),**({'PARKWEAVE_TEST_OWNER_DSN':os.environ['PARKWEAVE_TEST_OWNER_DSN']} if os.name=='nt' and 'PARKWEAVE_TEST_OWNER_DSN' in os.environ else {}))
            shard_result=execute(ROOT,sys.executable,args.shards,private,args.report,env=env,progress=args.progress,total_seconds=args.shard_budget,**({'deadline':args.job_test_deadline,'uptime_deadline':args.job_test_uptime} if args.job_test_deadline is not None else {}),**({'source_head':binding['head_sha']} if binding['state']=='HEAD_ONLY' else {}))
            if binding['state']=='HEAD_ONLY' and shard_result.get('source_blobs_verified') is True:binding={'state':'AVAILABLE','head_sha':binding['head_sha']}
            code=shard_result['execution_exit_code'];junit=ROOT/shard_result['private_junit']
        elif selectors:
            if binding['state']=='HEAD_ONLY':
                stage='SOURCE_BINDING'
                from source_bytes import verify_head_test_sources
                hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tests').rglob('test_*.py')}
                verify_head_test_sources(ROOT,binding['head_sha'],hashes);binding={'state':'AVAILABLE','head_sha':binding['head_sha']}
            stage='REGRESSION_EXECUTION'
            with log.open('w',encoding='utf-8') as f:
                progress_write(args.progress,'pytest_launch')
                telemetry=['-p','scripts.windows_ci.regression_plugin','--parkweave-progress',str(args.progress)] if args.progress is not None else []
                process=subprocess.run([sys.executable,'-m','pytest','-q','--junitxml',str(junit),*telemetry,*selectors],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=minimal_environment(os.environ,**({'PARKWEAVE_TEST_OWNER_DSN':os.environ['PARKWEAVE_TEST_OWNER_DSN']} if os.name=='nt' and 'PARKWEAVE_TEST_OWNER_DSN' in os.environ else {})))
            code=process.returncode
        stage='REPORT_SUMMARY'
        if not junit.is_file():raise ValueError('JUnit evidence unavailable')
        telemetry=progress_read(args.progress).get('regression_observation') if args.progress is not None else None
        progress_write(args.progress,'report_summary',telemetry=telemetry);report=summarize(rows,junit,code)
        if shard_result is None and selectors and sum(report['engineering_total_counts'].values())==0:
            # An empty document cannot establish that the requested tests ran.
            report=None
            raise ValueError('JUnit evidence empty')
        if shard_result is not None:report.update(shard_result)
        report.update(source_binding=binding,environment=sys.platform,model_calls=0,native_windows='NOT_RUN: native manual gates not auto-graded',
                      full_regression=binding['state']=='AVAILABLE' and not bool(args.ids) and (shard_result is None or shard_result['coverage_complete']),private_junit=str(junit.relative_to(ROOT)))
        if shard_result is None:report['private_log']=str(log.relative_to(ROOT))
        source_files=sorted(p for folder in ('src/parkweave','tests','scripts') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.ps1','.psm1','.sql','.html'))
        report['tested_source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
        stage='REPORT_WRITE'
        progress_write(args.progress,'report_write',telemetry=telemetry);write_report(args.report,report)
        print(json.dumps({'whole_AT_EX':'NOT_RUN','engineering_exit_code':code,'report':str(args.report),'native_windows':'NOT_RUN','model_calls':0},ensure_ascii=False))
        raise SystemExit(code)
    except Exception as error:rejected_report(args,stage,error,binding,code,getattr(error,'acceptance_report_context',None) or locals().get('report') or locals().get('shard_result'))


if __name__=='__main__':main()
