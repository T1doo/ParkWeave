"""Synthetic local publication/command faults; never Windows native results."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
import pytest
from parkweave.process_env import minimal_environment
from test_windows_ci_preparation import module,ROOT

POISON='SYNTHETIC_PRIVATE_ERROR_ENV_DSN_PATH_TRACE'
KNOWN='tests/test_lifecycle.py::test_config_write_is_exclusive_and_no_secret_fields'


def console_json(text):
    return json.loads(text.split('\n::notice title=ParkWeave safe diagnostics::',1)[0])


@pytest.fixture
def publication(tmp_path):
    root=tmp_path/('parkweave-server-ci-'+str(uuid4()));root.mkdir()
    output=tmp_path/'summary.md';output.touch()
    source={'PARKWEAVE_CI_ROOT':str(root),'RUNNER_TEMP':str(tmp_path),'GITHUB_STEP_SUMMARY':str(output),'GITHUB_RUN_ID':'123456','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40,'GITHUB_TOKEN':POISON,'PARKWEAVE_OWNER_DSN':POISON}
    row={'case':'full_engineering_regression','status':'FAIL','exit_code':1,'counts':{'PASS':0,'FAIL':1,'SKIP':0},'whole_AT_EX':'NOT_RUN','failure_diagnostics':{'state':'AVAILABLE','failed_test_ids':[KNOWN],'test_cases_seen':1,'failed_cases':1,'unknown_failed_cases':0,'ids_truncated':False}}
    suite=module('native_suite');record=module('summary_report')
    assert record.persist(root/'engineering.json',suite.summary([row]),source,'COMPLETED')
    return source,root/'engineering.json',output


def test_publisher_rebuilds_only_white_fields_from_poisoned_report(publication,capsys):
    source,path,output=publication;m=module('publish_summary');record=json.loads(path.read_bytes())
    record.update(raw_error=POISON,environment=POISON,private_stdout=POISON)
    row=record['cases'][0];row.update(raw_error=POISON,phase=POISON,category=POISON,reason=POISON)
    row['failure_diagnostics'].update(raw_error=POISON,private_path=POISON)
    path.write_text(json.dumps(record),encoding='utf-8')
    assert m.main(source)==0
    text=capsys.readouterr().out;value=console_json(text)
    assert value['cases'][0]['phase']=='UNKNOWN' and value['cases'][0]['category']=='OTHER'
    assert value['cases'][0]['failure_diagnostics']['failed_test_ids']==[KNOWN]
    assert POISON not in text and POISON not in output.read_text(encoding='utf-8')
    assert 'diagnostic_binding' not in text and 'head_sha' not in text and '123456' not in text


@pytest.mark.parametrize('mode',['failed','timeout','missing','cleanup_failure'])
def test_actual_bounded_private_wrapper_then_independent_publisher(publication,tmp_path,monkeypatch,mode):
    source,path,output=publication;path.unlink();trace=tmp_path/'trace';trace.mkdir();wrapper=module('native_command')
    # All environment values here are synthetic. The wrapper's real inheritance
    # retains the summary destination; it suppresses console text through files.
    env=minimal_environment(os.environ,**source)
    code='import sys,os,time;from pathlib import Path;sys.path.insert(0,'+repr(str(ROOT/'scripts/windows_ci'))+');import native_suite as s;import summary_report as r;print('+repr(POISON)+',flush=True);print('+repr(POISON)+',file=sys.stderr,flush=True);'
    if mode=='missing':code+='raise SystemExit(1)'
    elif mode=='timeout':code+='r.persist(Path(os.environ["PARKWEAVE_CI_ROOT"])/"engineering.json",s.summary([]),os.environ,"IN_PROGRESS","regression_run");time.sleep(10)'
    else:
        code+='e=RuntimeError('+repr(POISON)+');'
        if mode=='cleanup_failure':code+='e.parkweave_owned_browser_cleanup=("TimeoutExpired","PermissionError");'
        code+='raise SystemExit(s.emit_summary(Path(os.environ["PARKWEAVE_CI_ROOT"])/"engineering.json",[s.exception_row("lifecycle_exception",e,"native_browser")]))'
    with patch.dict(os.environ,env,clear=True):
        result=wrapper.execute(sys.executable,['-c',code],'native_suite',.6 if mode=='timeout' else 15,trace)
    assert result['exit_code']==(124 if mode=='timeout' else 1)
    assert result['timed_out']==(mode=='timeout')
    assert 'stdout' not in result and 'stderr' not in result
    assert POISON in (trace/result['stdout_file']).read_text(encoding='utf-8')
    # Separate workflow step: no access to any of the private log files.
    done=subprocess.run([sys.executable,str(ROOT/'scripts/windows_ci/publish_summary.py')],env=env,capture_output=True,text=True,timeout=15)
    public=console_json(done.stdout)
    assert POISON not in done.stdout and done.stderr=='' and POISON not in output.read_text(encoding='utf-8')
    if mode=='missing':assert done.returncode==1 and public['publication_state']=='SUMMARY_MISSING' and public['cases']==[]
    elif mode=='timeout':
        assert done.returncode==0 and public['report_state']=='IN_PROGRESS' and public['active_phase']=='regression_run' and public['cases']==[]
        assert result['cleanup']==('OWNED_TREE_STOPPED' if os.name=='nt' else 'DIRECT_CHILD_STOPPED')
    else:
        assert done.returncode==0 and public['cases'][0]['status']=='FAIL' and public['report_state']=='COMPLETED'
        if mode=='cleanup_failure':assert public['cases'][0]['owned_browser_cleanup_failures']==['TimeoutExpired','PermissionError']
    # Publication cannot change the already observed native result.
    assert result['exit_code']==(124 if mode=='timeout' else 1)


@pytest.mark.parametrize('field,value',[('diagnostic_schema',2),('diagnostic_schema',True),('diagnostic_binding',None),('report_state',POISON),('active_phase',POISON),('real_budget',True),('scope',POISON)])
def test_version_scope_and_stage_refused_without_echo(publication,field,value):
    source,path,_=publication;record=json.loads(path.read_bytes());record[field]=value;path.write_text(json.dumps(record),encoding='utf-8')
    result=module('publish_summary').read_summary(source)
    assert result['publication_state']=='SUMMARY_INVALID' and result['cases']==[] and POISON not in json.dumps(result)


@pytest.mark.parametrize('field,value',[('run_id','654321'),('run_attempt','2'),('head_sha','b'*40),('cluster_id',str(uuid4())),('extra',POISON)])
def test_report_current_run_attempt_sha_cluster_binding_is_required(publication,field,value):
    source,path,_=publication;record=json.loads(path.read_bytes());record['diagnostic_binding'][field]=value;path.write_text(json.dumps(record),encoding='utf-8')
    assert module('publish_summary').read_summary(source)['publication_state']=='SUMMARY_INVALID'


@pytest.mark.parametrize('payload',[b'[]',b'{bad',b'{"scope":NaN}',b'{"scope":1,"scope":2}',b'x'*(64*1024+1),'{}'.encode('utf-16')],ids=['array','malformed','nonfinite','duplicate','oversize','utf16'])
def test_invalid_non_utf8_duplicate_and_oversize_report_has_fixed_state(publication,payload):
    source,path,_=publication;path.write_bytes(payload);result=module('publish_summary').read_summary(source)
    assert result['publication_state']=='SUMMARY_INVALID' and result['cases']==[]


def test_counts_ids_and_cleanup_metadata_never_echo_unapproved_values(publication):
    source,path,_=publication;m=module('publish_summary');record=json.loads(path.read_bytes())
    row=record['cases'][0];row['counts']['PASS']=True;row['failure_diagnostics']['failed_test_ids']=[POISON]
    path.write_text(json.dumps(record),encoding='utf-8');result=m.read_summary(source);public=result['cases'][0]
    assert public['status']=='FAIL' and public['exit_code']==1 and public['counts_state']=='INVALID'
    assert public['failure_diagnostics']=={'state':'DIAGNOSTIC_FIELDS_INVALID','failed_test_ids':[]} and POISON not in json.dumps(result)
    row.pop('counts');row['failure_diagnostics']={};path.write_text(json.dumps(record),encoding='utf-8');public=m.read_summary(source)['cases'][0]
    assert public['counts_state']=='MISSING' and public['failure_diagnostics']['state']=='DIAGNOSTIC_FIELDS_MISSING'
    row['owned_browser_cleanup_failures']=['TimeoutExpired']*7;path.write_text(json.dumps(record),encoding='utf-8')
    assert m.read_summary(source)['publication_state']=='SUMMARY_INVALID'


def test_case_id_limit_and_failure_id_limit_are_enforced(publication):
    source,path,_=publication;m=module('publish_summary');record=json.loads(path.read_bytes());original=deepcopy(record)
    record['cases']=record['cases']*33;path.write_text(json.dumps(record),encoding='utf-8');assert m.read_summary(source)['publication_state']=='SUMMARY_INVALID'
    original['cases'][0]['failure_diagnostics']['failed_test_ids']=[KNOWN]*26;path.write_text(json.dumps(original),encoding='utf-8')
    assert m.read_summary(source)['cases'][0]['failure_diagnostics']['state']=='DIAGNOSTIC_FIELDS_INVALID'


def test_root_outside_bound_runner_temp_and_report_links_refused(publication,tmp_path):
    source,path,_=publication;m=module('publish_summary')
    assert m.read_summary(dict(source,RUNNER_TEMP=str(tmp_path/'different')))['publication_state']=='SUMMARY_INVALID'
    assert m.read_summary(dict(source,PARKWEAVE_CI_ROOT=str(tmp_path)))['publication_state']=='SUMMARY_INVALID'
    assert m.read_summary({})['publication_state']=='SUMMARY_MISSING'
    other=tmp_path/'other.json';other.write_bytes(path.read_bytes());path.unlink()
    try:path.symlink_to(other)
    except OSError:pytest.skip('platform cannot create owned test symlink')
    assert m.read_summary(source)['publication_state']=='SUMMARY_INVALID'
    other.unlink();assert m.read_summary(source)['publication_state']=='SUMMARY_INVALID'


def test_reparse_attributes_are_refused_without_reading_target(monkeypatch):
    m=module('publish_summary');fake=SimpleNamespace(lstat=lambda:SimpleNamespace(st_mode=0,st_file_attributes=1024))
    assert m.linked(fake)


def test_unreadable_report_does_not_print_exception_or_path(publication,monkeypatch):
    source,path,_=publication;m=module('publish_summary');original=Path.open
    def denied(p,*a,**k):
        if p==path:raise PermissionError(POISON)
        return original(p,*a,**k)
    monkeypatch.setattr(Path,'open',denied);result=m.read_summary(source)
    assert result['publication_state']=='SUMMARY_UNREADABLE' and POISON not in json.dumps(result)


def test_console_failure_does_not_suppress_summary_file(publication,monkeypatch):
    source,_,output=publication;m=module('publish_summary')
    def fail(*a,**k):raise OSError(POISON)
    monkeypatch.setattr(m,'print',fail,raising=False)
    assert m.main(source)==1 and 'SUMMARY_AVAILABLE' in output.read_text(encoding='utf-8')


def test_summary_file_failure_does_not_suppress_safe_console(publication,monkeypatch,capsys):
    source,_,output=publication;m=module('publish_summary');original=Path.open
    def denied(p,*a,**k):
        if p==output:raise PermissionError(POISON)
        return original(p,*a,**k)
    monkeypatch.setattr(Path,'open',denied)
    assert m.main(source)==1;printed=capsys.readouterr().out
    assert console_json(printed)['publication_state']=='SUMMARY_AVAILABLE' and POISON not in printed


def test_suite_report_persistence_failure_still_attempts_public_outputs(publication,monkeypatch,capsys):
    source,path,output=publication;m=module('native_suite');path.unlink()
    monkeypatch.setattr(m.os,'environ',source);monkeypatch.setattr(m,'persist',lambda *a:False)
    assert m.emit_summary(path,[{'case':'lifecycle_exception','status':'FAIL','phase':'native_browser','category':'TimeoutExpired'}])==1
    assert not path.exists() and 'TimeoutExpired' in capsys.readouterr().out and 'TimeoutExpired' in output.read_text(encoding='utf-8')


def test_suite_console_failure_still_persists_report_and_step_summary(publication,monkeypatch):
    source,path,output=publication;m=module('native_suite');monkeypatch.setattr(m.os,'environ',source)
    def fail(*a,**k):raise OSError(POISON)
    monkeypatch.setattr(m,'print',fail,raising=False)
    assert m.emit_summary(path,[{'case':'lifecycle_exception','status':'FAIL','phase':'native_browser','category':'TimeoutExpired'}])==1
    assert json.loads(path.read_bytes())['report_state']=='COMPLETED' and 'TimeoutExpired' in output.read_text(encoding='utf-8')


def test_atomic_checkpoint_failure_keeps_previous_complete_record(publication,monkeypatch):
    source,path,_=publication;m=module('summary_report');before=path.read_bytes()
    def fail(*a,**k):raise PermissionError(POISON)
    monkeypatch.setattr(m.os,'replace',fail)
    assert not m.persist(path,{'cases':[]},source) and path.read_bytes()==before
    assert not list(path.parent.glob('.engineering-*.tmp'))


@pytest.mark.parametrize('mode',['deep_json','root_loop','output_loop'])
def test_real_publisher_CLI_deep_json_and_path_loops_have_no_traceback(publication,mode):
    source,path,output=publication
    if mode=='deep_json':path.write_bytes(b'['*2000+b'0'+b']'*2000)
    else:
        link=path.parent if mode=='root_loop' else output
        if mode=='root_loop':path.unlink();link.rmdir()
        else:link.unlink()
        try:link.symlink_to(link,target_is_directory=mode=='root_loop')
        except OSError:pytest.skip('platform cannot create owned test symlink')
    env=minimal_environment(os.environ,**source)
    result=subprocess.run([sys.executable,str(ROOT/'scripts/windows_ci/publish_summary.py')],env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode==1 and result.stderr=='' and POISON not in result.stdout
    public=console_json(result.stdout)
    assert public['publication_state']==('SUMMARY_AVAILABLE' if mode=='output_loop' else 'SUMMARY_INVALID')


def test_coordinator_checkpoints_cover_API_restart_browser_and_final_stop(publication,tmp_path,monkeypatch):
    source,path,_=publication;m=module('native_suite');m.REPO=tmp_path;m.require_server=lambda:None
    runtime=tmp_path/'.runtime';runtime.mkdir();(runtime/'synthetic-sessions.json').write_text('{"fixture-a":"SYNTHETIC-session"}',encoding='utf-8');(runtime/'windows-config.json').write_text('{}',encoding='utf-8')
    env={**source,'PARKWEAVE_OWNER_DSN':'host=127.0.0.1 dbname=parkweave user=park_ci_owner','PARKWEAVE_DSN':'host=127.0.0.1 dbname=parkweave user=parkweave_app','PARKWEAVE_TEST_OWNER_DSN':'host=127.0.0.1 dbname=postgres user=park_ci_owner'}
    monkeypatch.setattr(m.os,'environ',env);monkeypatch.setattr(m.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'));monkeypatch.setattr(m.sys,'argv',['suite','--report',str(path)])
    phases=[];original=m.persist
    def persist(report,summary,source,state='IN_PROGRESS',phase='UNKNOWN'):
        phases.append(phase);return original(report,summary,source,state,phase)
    monkeypatch.setattr(m,'persist',persist);setup_count=0;start_count=0;stop_count=0
    def run(command,**kwargs):
        nonlocal setup_count,start_count,stop_count
        active=json.loads(path.read_bytes())['active_phase']
        if any(str(x).endswith('Setup.ps1') for x in command):
            setup_count+=1
            assert active==('setup' if setup_count==1 else 'existing_config')
            return SimpleNamespace(returncode=0 if setup_count==1 else 1,stdout='',stderr='existing configuration protected')
        if any(str(x).endswith('Start.ps1') for x in command):
            start_count+=1;assert active==('start' if start_count==1 else 'restart')
        if any(str(x).endswith('Stop.ps1') for x in command):
            stop_count+=1;assert active==('stop' if stop_count==1 else 'final_stop')
        if any(str(x).endswith('Status.ps1') for x in command):
            return SimpleNamespace(returncode=0,stdout=json.dumps({'project':'ParkWeave','port':8765,'model':'DISABLED','processes':[{'pid':1,'identity_matches':True},{'pid':2,'identity_matches':True}]}),stderr='')
        if 'scripts/run_acceptance.py' in command:
            assert active=='regression_run'
            assert command[command.index('--source-head')+1]==source['GITHUB_SHA']
            Path(command[command.index('--report')+1]).write_text(json.dumps({'engineering_total_counts':{'PASS':1,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN',
                'source_binding':{'state':'AVAILABLE','head_sha':source['GITHUB_SHA']}}),encoding='utf-8')
        if 'scripts/windows/file_candidate_probe.py' in command:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr='')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    class Response:
        def __init__(self,request):self.request=request
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):
            active=json.loads(path.read_bytes())['active_phase']
            assert active in ('api_case_submit','api_case_wait','restart_read')
            return json.dumps({'run_id':'SYNTHETIC-run'} if self.request.method=='POST' else {'state':'SUCCEEDED','case':{'id':'SYNTHETIC-case','state':'NEEDS_INPUT','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}}).encode()
    class Opener:
        def open(self,request,timeout):return Response(request)
    def browser(*args):
        assert json.loads(path.read_bytes())['active_phase']=='native_browser';return {'case':'NEEDS_INPUT','clarification':'UNKNOWN'}
    monkeypatch.setattr(m,'run_owned_job',lambda command,**kwargs:run(command,**kwargs))
    monkeypatch.setattr(m.subprocess,'run',run);monkeypatch.setattr(m.urllib.request,'build_opener',lambda *args:Opener());monkeypatch.setitem(sys.modules,'browser_smoke',SimpleNamespace(run_browser=browser))
    assert m.main()==0
    for phase in ('api_case_submit','api_case_wait','restart_read','native_browser','final_stop'):assert phase in phases
    assert json.loads(path.read_bytes())['report_state']=='COMPLETED' and stop_count==2
    assert phases[-2]=='server_candidate' and phases[-1]=='UNKNOWN'
