"""Prepared Server runner only: native lifecycle, full engineering, local browser.
Never configures UAC, enables LIVE/file production dispatch or uploads artifacts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid
from server_candidate_probe import require_server

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'src'))
sys.path.insert(0,str(REPO/'scripts/windows'))
from lifecycle_diagnostics import parse as lifecycle_failure
from child_environment import command_environment
from diagnostics import exception_row,read_report,failure_tests,browser_summary,shard_summary
from summary_report import persist, current_binding
from job_budget import JobBudget
from publish_summary import project as project_summary
from stage_result import read_command, failure as command_failure
from regression_progress import read_snapshot as regression_snapshot
from owned_job import run as run_owned_job


def run_regression(managed, report, progress, env, *, shards=None, budget=600, deadline=None, uptime_deadline=None, source_head=None):
    if shards is not None:
        if deadline is not None and uptime_deadline is None:raise ValueError('shared uptime cutoff required')
        ceiling=900 if deadline is None else JobBudget(deadline,uptime_deadline=uptime_deadline).remaining()
        if deadline is not None and ceiling<=0:
            result=subprocess.CompletedProcess([],1);result.not_run_reason='TOTAL_BUDGET_EXHAUSTED'
            return result
        if not 0<budget<=ceiling:raise ValueError('bounded regression budget required')
    command=[str(managed),'scripts/run_acceptance.py','--progress',str(progress)]
    if source_head is not None:command.extend(['--source-head',source_head])
    command.extend(['--report',str(report)])
    if shards is not None:command.extend(['--shards',str(shards),'--shard-budget',str(budget)])
    else:budget=600
    if deadline is not None:command.extend(['--job-test-deadline',str(deadline),'--job-test-uptime',str(uptime_deadline)])
    if os.name != 'nt':
        # Portable fault-injection harness only; the actual suite requires Server.
        return subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True,timeout=budget)
    prefix=report.stem+'-'+uuid.uuid4().hex
    with (report.parent/(prefix+'.stdout')).open('xb') as out,(report.parent/(prefix+'.stderr')).open('xb') as err:
        return run_owned_job(command,cwd=REPO,env=env,stdout=out,stderr=err,timeout=budget)

def owned_status(stdout):
    """A successful read command alone does not prove both owned services exist."""
    try:
        state=json.loads(stdout);rows=state['processes']
        return (state['project']=='ParkWeave' and state['model']=='DISABLED' and
                state['port']==8765 and len(rows)==2 and
                all(type(row['pid']) is int and row['pid']>0 and row['identity_matches'] is True for row in rows) and
                len({row['pid'] for row in rows})==2)
    except (ValueError,KeyError,TypeError):return False

def summary(rows, stage=None):
    return {**({'native_stage':stage} if stage else {}),'scope':'WINDOWS_SERVER_ENGINEERING_NOT_WIN11','cases':rows,'real_model_calls':0,'real_budget':0,'production_R4':'DISABLED','whole_AT_EX':'NOT_RUN','Win11':'NOT_RUN'}

def emit_summary(report,rows,stage=None):
    public=summary(rows,stage);ok=persist(report,public,os.environ,'COMPLETED')
    try:print(json.dumps(public))
    except (OSError,UnicodeError):ok=False
    # Report persistence and public outputs are independent; keep the original failure.
    if 'GITHUB_STEP_SUMMARY' in os.environ:
        try:
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a',encoding='utf-8') as f:f.write('Windows Server engineering (not Win11 acceptance)\n\n```json\n'+json.dumps(public,indent=2)+'\n```\n')
        except (OSError,UnicodeError):ok=False
    return 0 if ok and rows and all(r['status']=='PASS' for r in rows) else 1

def main():
    suite_started=time.monotonic()
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--regression-shards',type=Path,help='Fixed shards; default all keeps 900 seconds, explicit stages share job cutoff')
    parser.add_argument('--stage',choices=('all','lifecycle','validation'),default='all')
    parser.add_argument('--job-test-deadline',type=float)
    parser.add_argument('--job-test-uptime',type=int)
    args=parser.parse_args()
    if args.stage!='all' and (args.job_test_deadline is None or args.job_test_uptime is None or args.regression_shards is None):parser.error('staged execution requires wall/uptime cutoffs and shard manifest')
    if args.stage=='all' and (args.job_test_deadline is not None or args.job_test_uptime is not None):parser.error('job cutoff requires explicit stage')
    job=JobBudget(args.job_test_deadline,uptime_deadline=args.job_test_uptime) if args.stage!='all' else None
    try:require_server()
    except RuntimeError as exc:print(str(exc));return 2
    # Only names of explicitly created temporary cluster config. No model env access.
    rows=[];started=False;phase='configuration';isolation_ready=True
    if args.stage=='validation':
        try:
            with args.report.open('rb') as stream:data=stream.read(512*1024+1)
            prior=json.loads(data) if len(data)<=512*1024 else None
            binding=current_binding(args.report.parent,os.environ)
            if not isinstance(prior,dict) or prior.get('native_stage')!='lifecycle':raise ValueError('current lifecycle report required')
            projected=project_summary(prior,binding)
            if any(r['case'] in ('full_engineering_regression','Win11_guard_refuses_Server','separate_Server_candidate_oracles') for r in projected['cases']):raise ValueError('lifecycle rows required')
            rows.extend(projected['cases'])
            if prior['report_state']!='COMPLETED':rows.append(exception_row('suite_initialization',RuntimeError('lifecycle incomplete'),prior['active_phase']))
        except Exception as exc:rows.append(exception_row('suite_initialization',exc,'configuration'))
        isolation_ready=False
        try:
            binding=current_binding(args.report.parent,os.environ)
            command=read_command(args.report.with_name('lifecycle-command.json'),binding)
            isolation_ready=command['cleanup']=='OWNED_TREE_STOPPED'
            failure=command_failure(command,'lifecycle_exception')
            if failure is not None:rows.append(failure)
        except Exception as exc:
            row=exception_row('lifecycle_exception',exc,'final_stop');row['reason']='CLEANUP_NOT_CONFIRMED';rows.append(row)
    def checkpoint(phase):persist(args.report,summary(rows,args.stage if job else None),os.environ,'IN_PROGRESS',phase)
    checkpoint(phase)
    try:
        config={key:os.environ[key] for key in ('PARKWEAVE_OWNER_DSN','PARKWEAVE_DSN','PARKWEAVE_TEST_OWNER_DSN')}
        phase='managed_python';checkpoint(phase);managed=REPO/'.venv-windows/Scripts/python.exe'
        if Path(sys.executable).resolve()!=managed.resolve():raise RuntimeError('prepared managed Python required')
    except Exception as exc:return emit_summary(args.report,rows+[exception_row('suite_initialization',exc,phase)],args.stage if job else None)
    def script(label,path,*extra,expected=0,timeout=120,required_error=None,validate=None):
        if not isolation_ready:
            rows.append({'case':label,'status':'NOT_RUN','reason':'CLEANUP_NOT_CONFIRMED'});checkpoint(phase);return False
        if job is not None:
            timeout=job.limit(timeout,10)
            if timeout<=0:
                rows.append({'case':label,'status':'NOT_RUN','reason':'TOTAL_BUDGET_EXHAUSTED'});checkpoint(phase);return False
        child_phase='file_probe' if path.name=='ServerFileTest.ps1' else path.stem.lower()
        env=command_environment(os.environ,config,child_phase)
        proc=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(path),'-Python',str(managed),*extra],cwd=REPO,env=env,capture_output=True,text=True,timeout=timeout)
        ok=proc.returncode==expected and (required_error is None or required_error in proc.stderr)
        if ok and validate is not None:ok=validate(proc.stdout)
        rows.append({'case':label,'status':'PASS' if ok else 'FAIL','exit_code':proc.returncode})
        if label=='Start_native':
            observation=lifecycle_failure(proc.stdout,'start').get('start_observation')
            if observation is not None:rows[-1]['start_observation']=observation
        if not ok and label in ('Doctor_native','Start_native','Setup_native'):
            rows[-1].update(lifecycle_failure(proc.stdout,path.stem.lower()))
        if not ok and label in ('Stop_native','final_Stop_owned_services'):
            stop=lifecycle_failure(proc.stdout,'stop')
            rows[-1].update({key:stop[key] for key in ('identity_refusal','category') if key in stop})
        if proc.returncode==expected and validate is not None and not ok:rows[-1]['reason']='OWNED_STATUS_NOT_CONFIRMED'
        checkpoint('final_stop' if label=='final_Stop_owned_services' else phase)
        # Persist no raw subprocess logs in public summary; Doctor output has safe versions.
        if not ok:return False
        return True
    def local(path,method='GET',body=None,token=None,key=None):
        url='http://127.0.0.1:8765'+path
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        if key:headers['Idempotency-Key']=key
        data=json.dumps(body).encode() if body is not None else None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        timeout=3 if job is None else job.limit(3,10)
        if timeout<=0:raise TimeoutError('job test budget exhausted')
        with opener.open(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=timeout) as r:return json.load(r)
    wrappers=REPO/'scripts/windows'
    if args.stage!='validation':
        try:
            phase='setup';checkpoint(phase);setup=script('Setup_native',wrappers/'Setup.ps1')
            if setup:
                sessions=REPO/'.runtime/synthetic-sessions.json';configuration=REPO/'.runtime/windows-config.json'
                phase='existing_config';checkpoint(phase);original=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (sessions,configuration)]
                script('Setup_refuses_existing_config',wrappers/'Setup.ps1',expected=1,required_error='existing configuration protected')
                phase='config_preservation';checkpoint(phase);assert original==[hashlib.sha256(p.read_bytes()).hexdigest() for p in (sessions,configuration)]
                rows.append({'case':'config_sessions_preserved','status':'PASS'})
                phase='doctor';checkpoint(phase);script('Doctor_native',wrappers/'Doctor.ps1')
                phase='start';checkpoint(phase);started=script('Start_native',wrappers/'Start.ps1')
                if started:
                    phase='status';checkpoint(phase);script('Status_native',wrappers/'Status.ps1',validate=owned_status)
                    phase='session_read';checkpoint(phase);token=json.loads(sessions.read_text(encoding='utf-8'))['fixture-a']
                    phase='api_case_submit';checkpoint(phase);run=local('/api/runs','POST',{'goal':'SYNTHETIC Server persistence case'},token,uuid.uuid4().hex)['run_id']
                    phase='api_case_wait';checkpoint(phase)
                    for _ in range(100):
                        record=local('/api/runs/'+run,token=token)
                        if record['state']=='SUCCEEDED':break
                        time.sleep(.1)
                    assert record['state']=='SUCCEEDED' and record['case']['state']=='NEEDS_INPUT'
                    assert record['case']['external_acceptance']=='NOT_SUBMITTED' and record['case']['offline_fulfillment']=='NO_EVIDENCE'
                    case_id=record['case']['id'];rows.append({'case':'actual_API_worker_local_case','status':'PASS'})
                    phase='stop';checkpoint(phase);assert script('Stop_native',wrappers/'Stop.ps1');started=False
                    phase='stop_record_check';checkpoint(phase);assert not (REPO/'.runtime/windows-processes.json').exists()
                    phase='restart';checkpoint(phase);assert script('Restart_native',wrappers/'Start.ps1');started=True
                    phase='restart_read';checkpoint(phase);assert local('/api/runs/'+run,token=token)['case']['id']==case_id
                    rows.append({'case':'data_read_after_restart','status':'PASS'})
                    phase='native_browser';checkpoint(phase);from browser_smoke import run_browser
                    browser=run_browser(REPO,token)
                    rows.append({'case':'native_local_browser','status':'PASS','summary':browser_summary(browser)})
                else:rows.append({'case':'API_browser_restart','status':'NOT_RUN','reason':'START_FAILED'})
            else:rows.append({'case':'lifecycle_API_browser','status':'NOT_RUN','reason':'SETUP_FAILED'})
        except Exception as exc:rows.append(exception_row('lifecycle_exception',exc,phase))
        finally:
            checkpoint('final_stop')
            if started or (REPO/'.runtime/windows-processes.json').exists():
                try:script('final_Stop_owned_services',wrappers/'Stop.ps1',timeout=60)
                except Exception as exc:rows.append(exception_row('final_Stop_owned_services',exc,'final_stop'))
    if args.stage=='lifecycle':return emit_summary(args.report,rows,args.stage)
    def independent_validation():
        nonlocal phase
        try:
            phase='win11_guard';checkpoint(phase)
            # Verify original Win11 entry guard really refuses Server before any mutation.
            guard_timeout=15 if job is None else job.limit(15,10)
            if guard_timeout<=0 or not isolation_ready:
                rows.append({'case':'Win11_guard_refuses_Server','status':'NOT_RUN','reason':'TOTAL_BUDGET_EXHAUSTED' if isolation_ready else 'CLEANUP_NOT_CONFIRMED'})
            else:
                guard=subprocess.run([str(managed),'scripts/windows/file_candidate_probe.py','--fixture-dir',str(REPO/'.runtime/nonexistent-win11-guard-fixture')],cwd=REPO,env=command_environment(os.environ,config,'guard'),capture_output=True,text=True,timeout=guard_timeout)
                guard_ok=guard.returncode==1 and 'NOT_RUN: explicit native Windows11' in guard.stdout
                rows.append({'case':'Win11_guard_refuses_Server','status':'PASS' if guard_ok else 'FAIL','exit_code':guard.returncode})
                assert not (REPO/'.runtime/nonexistent-win11-guard-fixture').exists()
        except Exception as exc:rows.append(exception_row('Win11_guard_refuses_Server',exc,'win11_guard'))
        try:
            phase='server_candidate';checkpoint(phase);script('separate_Server_candidate_oracles',REPO/'scripts/windows_ci/ServerFileTest.ps1',timeout=180)
        except Exception as exc:rows.append(exception_row('separate_Server_candidate_oracles',exc,'server_candidate'))
    if args.stage=='validation':independent_validation()
    # Failures in one independent phase do not suppress the others.
    try:
        phase='regression_run';checkpoint(phase);report=REPO/'.runtime'/('server-regression-'+uuid.uuid4().hex+'.json');report.parent.mkdir(exist_ok=True)
        progress=report.with_suffix('.progress.json')
        proc=None
        binding=current_binding(args.report.parent,os.environ)
        expected_head=binding['head_sha'] if binding else None
        if args.regression_shards is None:
            proc=run_regression(managed,report,progress,command_environment(os.environ,config,'regression'),source_head=expected_head)
        else:
            # Preserve capacity for the independent 15s/180s stages and cleanup.
            budget=900-(time.monotonic()-suite_started)-210 if job is None else job.limit(1290,10)
            if budget<=0 or not isolation_ready:
                rows.append({'case':'full_engineering_regression','status':'NOT_RUN','exit_code':1,'phase':'regression_run',
                             'reason':'TOTAL_BUDGET_EXHAUSTED' if isolation_ready else 'CLEANUP_NOT_CONFIRMED'})
            else:
                proc=run_regression(managed,report,progress,command_environment(os.environ,config,'regression'),shards=args.regression_shards,budget=budget,source_head=expected_head,**({'deadline':args.job_test_deadline,'uptime_deadline':args.job_test_uptime} if job else {}))
        if proc is not None and getattr(proc,'not_run_reason',None)=='TOTAL_BUDGET_EXHAUSTED':
            rows.append({'case':'full_engineering_regression','status':'NOT_RUN','exit_code':1,'phase':'regression_run','reason':'TOTAL_BUDGET_EXHAUSTED'})
            proc=None
        if proc is not None:
            rows.append({'case':'full_engineering_regression','status':'PASS' if proc.returncode==0 else 'FAIL','exit_code':proc.returncode})
            rows[-1].update(regression_snapshot(progress))
            if hasattr(proc,'cleanup'):
                rows[-1]['owned_tree_cleanup']=proc.cleanup
                if proc.cleanup!='OWNED_TREE_STOPPED':rows[-1]['status']='FAIL'
            if report.exists():
                phase='regression_report';checkpoint(phase);parsed,counts=read_report(report)
                if parsed.get('counts_scope')!='UNAVAILABLE':rows[-1]['counts']=counts
                else:rows[-1]['counts_state']='MISSING'
                rows[-1]['whole_AT_EX']='NOT_RUN'
                if args.regression_shards is not None:
                    try:
                        rows[-1]['shards']=shard_summary(parsed.get('shards'))
                        if any(row['status']!='PASS' or row['counts'] is None or row['counts']['FAIL']!=0 or row['coverage'] is not True or row['exit']!=0 or row['cleanup']!='OWNED_TREE_STOPPED' for row in rows[-1]['shards']):rows[-1]['status']='FAIL'
                    except ValueError:rows[-1].update(shard_summary_state='UNAVAILABLE',status='FAIL')
                claimed=parsed.get('source_binding',{'state':'UNAVAILABLE'});rows[-1]['source_binding']=claimed
                if expected_head is None or claimed.get('state')!='AVAILABLE' or claimed.get('head_sha')!=expected_head:
                    rows[-1].update(status='FAIL',reason='SOURCE_BINDING_UNAVAILABLE' if expected_head is None or claimed.get('state')!='AVAILABLE' else 'SOURCE_BINDING_MISMATCH')
                if 'acceptance_failure' in parsed:
                    rows[-1].update(status='FAIL',acceptance_failure=parsed['acceptance_failure'],reason=parsed['acceptance_failure']['reason'])
                rows[-1]['failure_diagnostics']=failure_tests(REPO,parsed.get('private_junit'))
                if job is not None and (parsed.get('coverage_complete') is not True or parsed.get('execution_exit_code')!=0):rows[-1]['status']='FAIL'
            else:
                if args.regression_shards is not None:rows[-1]['shard_summary_state']='UNAVAILABLE'
                rows[-1]['failure_diagnostics']={'state':'REPORT_MISSING','failed_test_ids':[]}
                rows[-1]['status']='FAIL'
    except Exception as exc:
        row=exception_row('full_engineering_regression',exc,phase)
        if phase=='regression_run' and 'progress' in locals():row.update(regression_snapshot(progress))
        rows.append(row)
    if args.stage=='all':independent_validation()
    return emit_summary(args.report,rows,args.stage if job else None)

if __name__=='__main__':raise SystemExit(main())
