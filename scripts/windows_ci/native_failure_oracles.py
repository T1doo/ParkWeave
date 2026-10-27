"""Bounded ENG071 native measurements. Publish only closed fixed vocabularies.
No ACL repair; owner calls are only original SESSION/CONFIG first-new tests.
The outer Job contains worker lifetime and permits independent inner Job gold.
"""
import argparse, contextlib, io, json, os
from pathlib import Path
import runpy, struct, sys, tempfile, time

REPO=Path(__file__).resolve().parents[2]
CASES={'SESSION','CONFIG','PORT','HTTP_LF_OLD','HTTP_LF_CURRENT','HTTP_CRLF_OLD','HTTP_CRLF_CURRENT','ORIGINAL_JOB_EXIT17','ORIGINAL_JOB_TIMEOUT','PARENT_EXIT17','PARENT_TIMEOUT'}
STAGES={'SETUP','CURRENT_USER','CREATE_NEW','INSPECT_BEFORE','SET_OWNER','INSPECT_AFTER','VERIFY_OWNER','PERMISSIONS_COMPARE','FD_TRANSFER','TEXT_WRAP','FIRST_BYTES','SECOND_REFUSAL','EXISTING_BYTES','PORT_BIND','PORT_OCCUPIED_GOLD','DATABASE_REFUSAL','DATABASE_GOLD','HTTP_SETUP','HTTP_READINESS','HTTP_STATUS','HTTP_HEADER','HTTP_CONTENT','HTTP_CLEANUP','PARENT_RUN','PRIMARY_GOLD','CLEANUP_GOLD','RECORD_READ','UNRELATED_EXACT_LEAF','DESCENDANT_EXACT_HANDLE','UNRELATED_SETUP','UNRELATED_LAUNCHER_GOLD','UNRELATED_OWNED_CLEANUP','QUERY_HANDLE_CLOSE','COMPLETE'}
CATEGORIES={'NONE','OTHER','AssertionError','OwnedJobError','IdentityRefused','FileNotFoundError','JSONDecodeError','OSError','AccessDenied','SessionOwnerError','FileExistsError','BoundaryError','TimeoutExpired'}
REASONS={'NONE','UNKNOWN','CHECK_REFUSED','WINDOWS_REQUIRED','TOKEN_QUERY_REFUSED','SESSION_CREATE_REFUSED','SESSION_INSPECTION_REFUSED','SESSION_OWNER_REFUSED','SESSION_OWNER_MISMATCH','SESSION_PERMISSIONS_CHANGED','OWNER_MUTATION_PAUSED','PORT_OCCUPIED','PORT_BIND_REFUSED','WINDOWS_REQUIRED','JOB_CREATE_REFUSED','JOB_LIMIT_REFUSED','CREATION_IDENTITY_REFUSED','JOB_BIND_REFUSED','JOB_MEMBERSHIP_REFUSED','THREAD_RESUME_REFUSED','PROCESS_WAIT_REFUSED','JOB_TERMINATE_REFUSED','JOB_QUERY_REFUSED','JOB_STOP_UNCONFIRMED'}
ENUMS={'primary':{'UNKNOWN','EXIT17','TIMEOUT','OTHER_EXIT'},'cleanup':{'UNKNOWN','OWNED_TREE_STOPPED','OWNED_TREE_STOP_UNCONFIRMED','SUSPENDED_CHILD_STOPPED','NOT_STARTED'},'record':{'UNKNOWN','AVAILABLE'},'unrelated':{'UNKNOWN','LIVE'},'descendant':{'UNKNOWN','LIVE','ABSENT','OLD_IDENTITY_ABSENT','SIGNALED'},'socket_error':{'UNKNOWN','EADDRINUSE','EACCES','WSAEADDRINUSE','WSAEACCES'},'database_error':{'OPERATIONAL_ERROR','CONNECTION_TIMEOUT','OTHER'}}
BOOLS={'owner_same','acl_equal','control_equal','owner_defaulted_changed','database_operational_family','database_phase_gold','database_category_gold','database_redaction_gold'}

def project(row):
    if not isinstance(row,dict) or row.get('case') not in CASES or row.get('stage') not in STAGES or row.get('status') not in {'PASS','FAIL','NOT_RUN'} or row.get('category') not in CATEGORIES or row.get('reason') not in REASONS:raise ValueError('FIXED_RECEIPT_REFUSED')
    result={k:row[k] for k in ('case','stage','status','category','reason')}
    for key,allowed in ENUMS.items():
        if key in row:
            if row[key] not in allowed:raise ValueError('FIXED_RECEIPT_REFUSED')
            result[key]=row[key]
    for key in BOOLS:
        if key in row:
            if type(row[key]) is not bool:raise ValueError('FIXED_RECEIPT_REFUSED')
            result[key]=row[key]
    return result

def worker():
    sys.path[:0]=[str(REPO),str(REPO/'src'),str(REPO/'tests'),str(REPO/'scripts/windows'),str(REPO/'scripts/windows_ci')]
    import pytest
    import parkweave.synthetic_session_file as owner
    import test_synthetic_session_file as sessions
    import test_synthetic_config_file as config
    import test_owned_job as jobs
    import test_lifecycle_diagnostics as ports
    import test_utf8_sources as http
    rows=[]
    def measure(case,callback):
        row={'case':case,'status':'FAIL','stage':'SETUP','category':'OTHER','reason':'CHECK_REFUSED'}
        failures=[]
        def stage(value):row['stage']=value
        # Trace only fixed source statements; no locals, paths or errors escape.
        def trace(frame,event,arg):
            name=frame.f_code.co_name
            if event=='line':
                import linecache
                text=linecache.getline(frame.f_code.co_filename,frame.f_lineno).strip()
                if name=='_create_owned_synthetic_file' and text.startswith('if before[2]!=after[2]'):stage('PERMISSIONS_COMPARE')
                if name=='test_native_session_owner_matches_current_user_and_existing_bytes_protected' or name=='test_native_config_first_creation_and_existing_bytes_protected':
                    if 'stream.write(' in text:stage('FIRST_BYTES')
                    if 'pytest.raises(FileExistsError)' in text:stage('SECOND_REFUSAL')
                    if 'assert path.read_bytes()' in text:stage('EXISTING_BYTES')
                if name=='test_real_loopback_refusal_and_occupied_port_are_distinct':
                    if 'owned.bind(' in text:stage('PORT_BIND')
                    if 'port_available(' in text:stage('PORT_OCCUPIED_GOLD')
                    if 'check_dsn_scope(' in text:stage('DATABASE_REFUSAL')
                    if "assert diagnostic.failure(refused.value)" in text or "assert str(port) not in diagnostic.command" in text:
                        observation=ports.diagnostic.database_refusal_observation(frame.f_locals['refused'].value,frame.f_locals['port'])
                        row.update(observation)
                        stage('DATABASE_GOLD')
                if name=='test_actual_chinese_UI_http_under_non_utf8_path_default':
                    if 'thread.start()' in text:stage('HTTP_SETUP')
                    if 'opener.open(' in text:stage('HTTP_READINESS')
                    if 'assert response is not None' in text:stage('HTTP_READINESS')
                    if 'assert response.status' in text:stage('HTTP_STATUS')
                    if "assert response.headers" in text:stage('HTTP_HEADER')
                    if 'assert response.read()' in text:stage('HTTP_CONTENT')
                    if 'server.should_exit=True' in text:stage('HTTP_CLEANUP')
                if name=='test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary':
                    if 'JOB.run(' in text:stage('PARENT_RUN')
                    if 'assert failure.value.cleanup' in text:stage('CLEANUP_GOLD')
                    if 'assert result.returncode' in text:stage('PRIMARY_GOLD')
                    if 'assert result.cleanup' in text:stage('CLEANUP_GOLD')
                    if 'assert unrelated.poll()' in text:stage('UNRELATED_LAUNCHER_GOLD')
                    if 'data=json.loads(record.read_text())' in text:stage('RECORD_READ')
                    if 'assert not recorded_child_alive' in text:stage('DESCENDANT_EXACT_HANDLE')
                    if 'unrelated.terminate()' in text:stage('UNRELATED_OWNED_CLEANUP')
            elif event=='exception':
                exc=arg[1]
                # Preserve earliest escaping failure before a finally changes stage.
                if name in {'test_native_session_owner_matches_current_user_and_existing_bytes_protected','test_native_config_first_creation_and_existing_bytes_protected','test_real_loopback_refusal_and_occupied_port_are_distinct','test_actual_chinese_UI_http_under_non_utf8_path_default','test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary'}:
                    if not any(previous is exc for previous,_ in failures):failures.append((exc,row['stage']))
                if name=='port_available' and isinstance(exc,OSError):
                    row['socket_error']={10048:'WSAEADDRINUSE',10013:'WSAEACCES'}.get(getattr(exc,'winerror',None),{10048:'WSAEADDRINUSE',10013:'WSAEACCES',98:'EADDRINUSE',13:'EACCES'}.get(exc.errno,'UNKNOWN'))
            return trace
        with tempfile.TemporaryDirectory(prefix='native-fixed-oracle-',dir=REPO/'.runtime') as td,pytest.MonkeyPatch.context() as mp:
            base=owner.WindowsSessionFile
            class Observed(base):
                def current_user(self):stage('CURRENT_USER');return super().current_user()
                def create(self,path):stage('CREATE_NEW');return super().create(path)
                def inspect(self,h):
                    n=getattr(self,'n',0)+1;self.n=n;stage('INSPECT_BEFORE' if n==1 else 'INSPECT_AFTER')
                    value=super().inspect(h)
                    if n==1:self.before=value
                    else:
                        row['acl_equal']=self.before[2]==value[2];row['control_equal']=(self.before[3]&~1)==(value[3]&~1);row['owner_defaulted_changed']=bool((self.before[3]^value[3])&1)
                    return value
                def set_owner(self,h,sid):stage('SET_OWNER');return super().set_owner(h,sid)
                def verify_owner(self,own,sid):
                    stage('VERIFY_OWNER');row['owner_same']=bool(self.a.EqualSid(own,sid));return super().verify_owner(own,sid)
                def transfer_fd(self,h):stage('FD_TRANSFER');return super().transfer_fd(h)
                def text_file(self,fd):stage('TEXT_WRAP');return super().text_file(fd)
            mp.setattr(owner,'WindowsSessionFile',Observed)
            previous=sys.gettrace()
            try:
                sys.settrace(trace);callback(Path(td),mp)
                row.update(status='PASS',stage='COMPLETE',category='NONE',reason='NONE')
            except (Exception,pytest.fail.Exception,pytest.skip.Exception) as e:
                row['stage']=next((value for previous,value in failures if previous is e),row['stage'])
                if isinstance(e,pytest.skip.Exception):row['status']='NOT_RUN'
                row['category']=type(e).__name__ if type(e).__name__ in CATEGORIES else 'OTHER'
                row['reason']=e.args[0] if isinstance(e,(owner.SessionOwnerError,jobs.JOB.OwnedJobError)) and len(e.args)==1 and e.args[0] in REASONS else 'CHECK_REFUSED'
                if isinstance(e,ports.lifecycle.BoundaryError):
                    reason=ports.diagnostic.failure(e).get('boundary_reason');row['reason']=reason if reason in REASONS else 'CHECK_REFUSED'
            finally:sys.settrace(previous)
        rows.append(project(row))
    measure('SESSION',lambda td,mp:sessions.test_native_session_owner_matches_current_user_and_existing_bytes_protected(td,mp))
    measure('CONFIG',lambda td,mp:config.test_native_config_first_creation_and_existing_bytes_protected(td,mp))
    measure('PORT',lambda td,mp:ports.test_real_loopback_refusal_and_occupied_port_are_distinct())
    for ending in ('LF','CRLF'):
        for legacy,expected in ((True,500),(False,200)):
            measure('HTTP_'+ending+('_OLD' if legacy else '_CURRENT'),lambda td,mp:http.test_actual_chinese_UI_http_under_non_utf8_path_default(td,mp,legacy,expected,line_ending=ending))
    for timed in (False,True):measure('ORIGINAL_JOB_TIMEOUT' if timed else 'ORIGINAL_JOB_EXIT17',lambda td,mp:jobs.test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary(td,timed))
    # Run the previously independently reviewed recipe without changing its logic.
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture):
        try:runpy.run_path(str(REPO/'scripts/windows_ci/minimal_native_job_oracle.py'),run_name='__main__')
        except SystemExit as e:
            if e.code not in (0,1):raise RuntimeError('MINIMAL_ORACLE_REFUSED') from None
    data=json.loads(capture.getvalue())
    if data.get('scope')!='MINIMAL_NATIVE_JOB_ORACLE' or len(data.get('results',[]))!=2:raise ValueError('FIXED_RECEIPT_REFUSED')
    rows.extend(project(row) for row in data['results'])
    print(json.dumps({'scope':'ENG071_NATIVE_FIXED_ORACLES','rows':rows},separators=(',',':')))
    return 0 if all(row['status']=='PASS' for row in rows) else 1

def main():
    if os.name!='nt' or sys.version_info[:2]!=(3,12) or struct.calcsize('P')!=8:raise SystemExit('NATIVE_PLATFORM_REQUIRED')
    if Path(sys.executable).resolve()!=(REPO/'.venv-windows/Scripts/python.exe').resolve():raise SystemExit('NATIVE_RUNTIME_BINDING_REFUSED')
    if '--worker' in sys.argv:return worker()
    sys.path.insert(0,str(REPO/'scripts/windows_ci'))
    from owned_job import run
    from job_budget import system_uptime_ms
    import subprocess
    cleanup='UNKNOWN';ok=False
    try:
        # Shared original epoch; never refresh the existing 25 minute budget.
        remaining=min(int(os.environ['PARKWEAVE_CI_JOB_STARTED'])+1290-time.time(),(int(os.environ['PARKWEAVE_CI_JOB_UPTIME'])+1290000-system_uptime_ms())/1000)-10
        if remaining<=0:raise RuntimeError('TOTAL_BUDGET_EXHAUSTED')
        with tempfile.TemporaryDirectory(prefix='native-fixed-parent-',dir=REPO/'.runtime') as td:
            with (Path(td)/'out').open('w+b') as out,(Path(td)/'err').open('wb') as err:
                result=run([sys.executable,str(Path(__file__).resolve()),'--worker'],cwd=REPO,timeout=min(90,remaining),stdout=out,stderr=err)
                cleanup=result.cleanup;out.seek(0);raw=out.read(16385)
            if len(raw)>16384:raise ValueError('FIXED_RECEIPT_REFUSED')
            data=json.loads(raw)
            if data.get('scope')!='ENG071_NATIVE_FIXED_ORACLES' or not isinstance(data.get('rows'),list) or len(data['rows'])!=11:raise ValueError('FIXED_RECEIPT_REFUSED')
            rows=[project(row) for row in data['rows']]
            if {row['case'] for row in rows}!=CASES:raise ValueError('FIXED_RECEIPT_REFUSED')
            commands=['::notice::'+json.dumps({'kind':'native_fixed_oracle_batch','rows':rows[i:i+3]},separators=(',',':')) for i in range(0,len(rows),3)]
            if len(commands)+1>8 or any(len((c+'\n').encode())>2048 for c in commands) or sum(len((c+'\n').encode()) for c in commands)>15*1024:raise ValueError('FIXED_RECEIPT_REFUSED')
            for command in commands:print(command)
            ok=result.returncode==0 and cleanup=='OWNED_TREE_STOPPED' and all(r['status']=='PASS' for r in rows)
    except subprocess.TimeoutExpired as e:cleanup=getattr(e,'cleanup','UNKNOWN')
    except Exception as e:cleanup=getattr(e,'cleanup','UNKNOWN')
    cleanup=cleanup if cleanup in ENUMS['cleanup'] else 'UNKNOWN'
    print('::notice::'+json.dumps({'kind':'native_fixed_oracle_cleanup','cleanup':cleanup,'status':'PASS' if ok else 'FAIL'},separators=(',',':')))
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
