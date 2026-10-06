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
from diagnostics import exception_row,read_report,failure_tests,browser_summary
from summary_report import persist
from regression_progress import read as regression_phase

def owned_status(stdout):
    """A successful read command alone does not prove both owned services exist."""
    try:
        state=json.loads(stdout);rows=state['processes']
        return (state['project']=='ParkWeave' and state['model']=='DISABLED' and
                state['port']==8765 and len(rows)==2 and
                all(type(row['pid']) is int and row['pid']>0 and row['identity_matches'] is True for row in rows) and
                len({row['pid'] for row in rows})==2)
    except (ValueError,KeyError,TypeError):return False

def summary(rows):
    return {'scope':'WINDOWS_SERVER_ENGINEERING_NOT_WIN11','cases':rows,'real_model_calls':0,'real_budget':0,'production_R4':'DISABLED','whole_AT_EX':'NOT_RUN','Win11':'NOT_RUN'}

def emit_summary(report,rows):
    public=summary(rows);ok=persist(report,public,os.environ,'COMPLETED')
    try:print(json.dumps(public))
    except (OSError,UnicodeError):ok=False
    # Report persistence and public outputs are independent; keep the original failure.
    if 'GITHUB_STEP_SUMMARY' in os.environ:
        try:
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a',encoding='utf-8') as f:f.write('Windows Server engineering (not Win11 acceptance)\n\n```json\n'+json.dumps(public,indent=2)+'\n```\n')
        except (OSError,UnicodeError):ok=False
    return 0 if ok and rows and all(r['status']=='PASS' for r in rows) else 1

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True,type=Path);args=parser.parse_args()
    try:require_server()
    except RuntimeError as exc:print(str(exc));return 2
    # Only names of explicitly created temporary cluster config. No model env access.
    rows=[];started=False;phase='configuration'
    def checkpoint(phase):persist(args.report,summary(rows),os.environ,'IN_PROGRESS',phase)
    checkpoint(phase)
    try:
        config={key:os.environ[key] for key in ('PARKWEAVE_OWNER_DSN','PARKWEAVE_DSN','PARKWEAVE_TEST_OWNER_DSN')}
        phase='managed_python';checkpoint(phase);managed=REPO/'.venv-windows/Scripts/python.exe'
        if Path(sys.executable).resolve()!=managed.resolve():raise RuntimeError('prepared managed Python required')
    except Exception as exc:return emit_summary(args.report,[exception_row('suite_initialization',exc,phase)])
    def script(label,path,*extra,expected=0,timeout=120,required_error=None,validate=None):
        child_phase='file_probe' if path.name=='ServerFileTest.ps1' else path.stem.lower()
        env=command_environment(os.environ,config,child_phase)
        proc=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(path),'-Python',str(managed),*extra],cwd=REPO,env=env,capture_output=True,text=True,timeout=timeout)
        ok=proc.returncode==expected and (required_error is None or required_error in proc.stderr)
        if ok and validate is not None:ok=validate(proc.stdout)
        rows.append({'case':label,'status':'PASS' if ok else 'FAIL','exit_code':proc.returncode})
        if not ok and label in ('Doctor_native','Start_native','Setup_native'):
            rows[-1].update(lifecycle_failure(proc.stdout,path.stem.lower()))
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
        with opener.open(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=3) as r:return json.load(r)
    wrappers=REPO/'scripts/windows'
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
    # Failures in one independent phase do not suppress the others.
    try:
        phase='regression_run';checkpoint(phase);report=REPO/'.runtime'/('server-regression-'+uuid.uuid4().hex+'.json');report.parent.mkdir(exist_ok=True)
        progress=report.with_suffix('.progress.json')
        proc=subprocess.run([str(managed),'scripts/run_acceptance.py','--progress',str(progress),'--report',str(report)],cwd=REPO,env=command_environment(os.environ,config,'regression'),capture_output=True,text=True,timeout=600)
        rows.append({'case':'full_engineering_regression','status':'PASS' if proc.returncode==0 else 'FAIL','exit_code':proc.returncode})
        if report.exists():
            phase='regression_report';checkpoint(phase);parsed,counts=read_report(report)
            rows[-1]['counts']=counts;rows[-1]['whole_AT_EX']='NOT_RUN'
            rows[-1]['failure_diagnostics']=failure_tests(REPO,parsed.get('private_junit'))
        else:rows[-1]['failure_diagnostics']={'state':'REPORT_MISSING','failed_test_ids':[]}
    except Exception as exc:
        row=exception_row('full_engineering_regression',exc,phase)
        if phase=='regression_run' and 'progress' in locals():row['regression_phase']=regression_phase(progress)
        rows.append(row)
    try:
        phase='win11_guard';checkpoint(phase)
        # Verify original Win11 entry guard really refuses Server before any mutation.
        guard=subprocess.run([str(managed),'scripts/windows/file_candidate_probe.py','--fixture-dir',str(REPO/'.runtime/nonexistent-win11-guard-fixture')],cwd=REPO,env=command_environment(os.environ,config,'guard'),capture_output=True,text=True,timeout=15)
        guard_ok=guard.returncode==1 and 'NOT_RUN: explicit native Windows11' in guard.stdout
        rows.append({'case':'Win11_guard_refuses_Server','status':'PASS' if guard_ok else 'FAIL','exit_code':guard.returncode})
        assert not (REPO/'.runtime/nonexistent-win11-guard-fixture').exists()
    except Exception as exc:rows.append(exception_row('Win11_guard_refuses_Server',exc,'win11_guard'))
    try:
        phase='server_candidate';checkpoint(phase);script('separate_Server_candidate_oracles',REPO/'scripts/windows_ci/ServerFileTest.ps1',timeout=180)
    except Exception as exc:rows.append(exception_row('separate_Server_candidate_oracles',exc,'server_candidate'))
    return emit_summary(args.report,rows)

if __name__=='__main__':raise SystemExit(main())
