"""Pure CI contract tests only; never start trial processes/PG or modify identities."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]


def module():
    spec=importlib.util.spec_from_file_location('pwci_bootstrap_contract',ROOT/'scripts/linux_trial/bootstrap.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def clean(m):
    return dict(source_sha='a'*40,phase='PREFLIGHT',error='NONE',cases={c:'NOT_RUN' for c in m.CASES},cleanup=True,setup_diagnostic=None)


@pytest.mark.parametrize('field',['source_sha','phase','error','cases','extra','setup_diagnostic'])
def test_ci_public_output_never_serializes_private_poison(field):
    m=module();value=clean(m);poison='SYNTHETIC_PRIVATE_PASSWORD_KEY_PATH_TOKEN'
    if field=='cases':value[field][m.CASES[0]]=poison
    else:value[field]=poison
    with pytest.raises(ValueError) as error:m.public_summary(value)
    assert poison not in str(error.value)


def test_ci_public_projection_has_fixed_status_keys_and_zero_paid_resources():
    m=module();value=clean(m);output=m.public_summary(value)
    assert output['paid_services']==output['artifact_uploads']==output['cache_uploads']==0
    assert output['production_deployment'] is False
    assert len(output['cases'])==17 and set(output['cases'].values())=={'NOT_RUN'}


@pytest.mark.parametrize('change',[dict(TRIAL_REPOSITORY='other/repo'),dict(TRIAL_REF='refs/heads/main'),
    dict(TRIAL_EVENT='pull_request'),dict(TRIAL_ATTEMPT='2'),dict(TRIAL_NUMBER='2'),dict(RUNNER_ENVIRONMENT='self-hosted')])
def test_ci_context_refuses_wrong_or_repeated_scope_before_bootstrap(change):
    m=module();env=dict(TRIAL_REPOSITORY='T1doo/ParkWeave',TRIAL_REF=m.BRANCH,TRIAL_EVENT='push',
        TRIAL_ATTEMPT='1',TRIAL_NUMBER='1',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux')
    assert m.approved_context(env,0,'a'*40)
    env.update(change);assert not m.approved_context(env,0,'a'*40)
    assert not m.approved_context(env,1000,'a'*40)


def test_ci_workflow_uses_single_free_standard_job_without_upload_or_dispatch():
    text=(ROOT/'.github/workflows/restricted-linux-trial-once.yml').read_text()
    assert 'runs-on: ubuntu-24.04' in text and 'timeout-minutes: 25' in text
    assert 'github.run_attempt == 1 && github.run_number == 1' in text
    assert 'github.event.repository.private == false' in text and 'persist-credentials: false' in text
    assert 'branches: [dev/f2-restricted-linux-trial-20261012]' in text
    assert 'dev/f2-restricted-linux-setup-diagnostics-20261012' not in text
    for denied in ('workflow_dispatch:','pull_request:','upload-artifact','actions/cache','actions/setup-python','self-hosted','matrix:','secrets.'):
        assert denied not in text


def test_ci_private_trial_inputs_do_not_use_credentials_in_command_or_environment():
    controller=(ROOT/'scripts/linux_trial/controller.py').read_text();worker=(ROOT/'scripts/linux_trial/worker.py').read_text()
    assert 'pass_fds=(fd,)' in controller and "env={'LANG':'C.UTF-8'}" in controller
    assert 'pwfile=' in controller and 'passwords[\'pwci_owner\']' not in controller.split('subprocess.Popen([str(binaries')[1].split('finally:out.close()')[0]
    assert 'host.bind_api' in worker and 'ROOT_SEALED_INPUT_REQUIRED' in worker
    assert "if set(config)!={'api_uid','api_gid','ipc_gid','app_dsn','tokens','binding_path','binding_sha256','writer_private_path'}" in worker


@pytest.mark.parametrize('change',[{'substage':'SYNTHETIC_PRIVATE_SQL_DSN'},
    {'check_id':'SYNTHETIC_PRIVATE_SQL_DSN'},{'status_code':'SYNTHETIC_PRIVATE_SQL_DSN'},
    {'status_code':True},{'status_code':403.0},{'status_code':599},{'extra':'SYNTHETIC_PRIVATE_SQL_DSN'},
    {'substage':'ACL'},{'check_id':'POLICY','substage':'POLICY','status_code':403}])
def test_ci_setup_diagnostic_rejects_poison_types_and_wrong_combinations(change):
    m=module();value=dict(substage='SYNTHETIC',check_id='PREPARATION_CREATE',status_code=403);value.update(change)
    with pytest.raises(ValueError) as error:m.setup_diagnostic(value)
    assert str(error.value)=='SETUP_DIAGNOSTIC_CONTRACT'
    public=clean(m);public['setup_diagnostic']=value
    with pytest.raises(ValueError):m.public_summary(public)


@pytest.mark.parametrize('status,observed',[(201,201),(403,403),(599,0),(True,0),('PRIVATE',0)])
def test_ci_setup_http_status_is_allowlisted_without_response_body(status,observed):
    m=module();observation=m.SetupObservation()
    class Response:
        status_code=status
        def json(self):
            assert status==201
            return {'synthetic':'private success payload'}
    with observation.check('PREPARATION_CREATE'):
        if type(status) is int and status==201:assert observation.response(Response(),201)['synthetic']
        else:
            with pytest.raises(AssertionError) as error:observation.response(Response(),201)
            assert str(error.value)=='SYNTHETIC_SETUP_STATUS'
    assert m.setup_diagnostic(observation.value)==dict(substage='SYNTHETIC',check_id='PREPARATION_CREATE',status_code=observed)


def test_ci_setup_check_precedes_failure_and_resets_http_observation():
    m=module();observation=m.SetupObservation()
    with pytest.raises(RuntimeError):
        with observation.check('MIGRATION'):
            assert observation.value==dict(substage='MIGRATION',check_id='MIGRATION',status_code=0)
            raise RuntimeError('SYNTHETIC_PRIVATE_SQL_DSN')
    assert 'PRIVATE' not in json.dumps(observation.value)
    with observation.check('RUN_CREATE'):observation.value['status_code']=202
    with observation.check('CATALOG_COMPARE'):assert observation.value['status_code']==0


@pytest.mark.parametrize('outcome,code,has_payload,check_id',[
    ('PASS',1,True,'RESULT'),('FAIL',0,False,'MIGRATION'),('FAIL',1,True,'MIGRATION'),
    ('PASS',0,False,'RESULT'),('PASS',0,True,'MIGRATION'),('PASS',False,True,'RESULT')])
def test_ci_setup_frame_refuses_exit_outcome_or_private_payload_conflicts(outcome,code,has_payload,check_id):
    m=module();frame=dict(outcome=outcome,diagnostic=dict(substage=m.SETUP_CHECKS[check_id],check_id=check_id,status_code=0))
    if has_payload:frame['result']={'password':'SYNTHETIC_PRIVATE_SQL_DSN'}
    with pytest.raises(ValueError) as error:m.setup_frame(json.dumps(frame).encode(),code)
    assert str(error.value)=='SETUP_FRAME_CONTRACT'


@pytest.mark.parametrize('raw',[b'',b'PRIVATE',b'{}\n{}',b'{"outcome":"FAIL","outcome":"PASS"}',b'x'*524289,b'\xff','{}'.encode('utf-16')])
def test_ci_setup_frame_requires_single_bounded_unambiguous_json(raw):
    m=module()
    with pytest.raises(ValueError) as error:m.setup_frame(raw,1)
    assert str(error.value)=='SETUP_FRAME_CONTRACT'


def test_ci_setup_success_payload_stays_private_and_legacy_summary_still_reads():
    m=module();poison='SYNTHETIC_PRIVATE_SQL_DSN'
    frame=dict(outcome='PASS',diagnostic=dict(substage='OUTPUT',check_id='RESULT',status_code=0),result={'writer_dsn':poison})
    outcome,diagnostic,result=m.setup_frame(json.dumps(frame).encode(),0)
    assert outcome=='PASS' and result['writer_dsn']==poison
    public=clean(m);public['setup_diagnostic']=diagnostic
    assert poison not in json.dumps(m.public_summary(public))
    del public['setup_diagnostic'];assert 'setup_diagnostic' not in m.public_summary(public)


@pytest.mark.parametrize('boundary,expected',[('sealed','SEALED_INPUT'),('uid','PG_OWNER'),('proof','CLUSTER_PROOF')])
def test_ci_setup_worker_failure_reports_check_without_private_exception(monkeypatch,capsys,boundary,expected):
    import importlib
    # Pure synthetic observations; no real FD/PG call or identity modification.
    monkeypatch.syspath_prepend(str(ROOT));worker=importlib.import_module('scripts.linux_trial.worker');m=module()
    poison='SYNTHETIC_PRIVATE_SQL_DSN'
    config=dict(pg_uid=7001,data='/synthetic',owner_maintenance_dsn=poison,database='fixture_'+'a'*32)
    def refused(*args):raise RuntimeError(poison)
    monkeypatch.setattr(sys,'argv',['helper','SETUP','42'])
    monkeypatch.setattr(worker,'sealed_input',refused if boundary=='sealed' else lambda fd:config)
    monkeypatch.setattr(worker.os,'geteuid',lambda:7002 if boundary=='uid' else 7001)
    monkeypatch.setattr(worker,'capture_fixture_cluster',refused)
    assert worker.main()==1
    captured=capsys.readouterr();outcome,diagnostic,result=m.setup_frame(captured.out.encode(),1)
    assert outcome=='FAIL' and diagnostic['check_id']==expected and result is None
    assert poison not in captured.out
    if boundary!='uid':assert poison in captured.err
    public=clean(m);public['setup_diagnostic']=diagnostic
    assert poison not in json.dumps(m.public_summary(public))


def test_ci_setup_worker_success_and_child_entry_preserve_exit_status(monkeypatch,capsys):
    import importlib
    monkeypatch.syspath_prepend(str(ROOT));worker=importlib.import_module('scripts.linux_trial.worker');m=module()
    monkeypatch.setattr(sys,'argv',['helper','SETUP','42']);monkeypatch.setattr(worker,'sealed_input',lambda fd:{})
    def success(config,observation):
        with observation.check('RESULT'):return {'writer_dsn':'SYNTHETIC_PRIVATE_SQL_DSN'}
    monkeypatch.setattr(worker,'setup',success)
    assert worker.main()==0
    captured=capsys.readouterr();assert captured.err==''
    assert m.setup_frame(captured.out.encode(),0)[0]=='PASS'
    text=(ROOT/'scripts/linux_trial/controller.py').read_text()
    assert 'from scripts.linux_trial.worker import main;raise SystemExit(main())' in text


def second_env(m):
    return dict(TRIAL_REPOSITORY='T1doo/ParkWeave',TRIAL_REF=m.SECOND_BRANCH,TRIAL_ENTRY=m.SECOND_ENTRY,
        TRIAL_EVENT='push',TRIAL_ATTEMPT='1',TRIAL_NUMBER='1',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux')


@pytest.mark.parametrize('key,value',[
    ('TRIAL_REPOSITORY','other/repo'),('TRIAL_REF','refs/heads/main'),
    ('TRIAL_REF','refs/heads/dev/f2-restricted-linux-trial-20261012'),
    ('TRIAL_ENTRY','FIRST_ONCE'),('TRIAL_EVENT','workflow_dispatch'),
    ('TRIAL_ATTEMPT','2'),('TRIAL_NUMBER','2'),('TRIAL_NUMBER',1),
    ('RUNNER_ENVIRONMENT','self-hosted'),('RUNNER_OS','Windows')])
def test_ci_second_entry_rejects_each_wrong_or_missing_scope(key,value):
    m=module();env=second_env(m)
    assert m.approved_second_context(env,0,'a'*40)
    assert not m.approved_context(env,0,'a'*40)
    env[key]=value;assert not m.approved_second_context(env,0,'a'*40)
    del env[key];assert not m.approved_second_context(env,0,'a'*40)


@pytest.mark.parametrize('uid,sha',[(1000,'a'*40),(False,'a'*40),(0.0,'a'*40),(0,''),(0,'A'*40),(0,'a'*39),(0,None)])
def test_ci_second_entry_requires_root_and_exact_source_type(uid,sha):
    m=module();assert not m.approved_second_context(second_env(m),uid,sha)


@pytest.mark.parametrize('entry,approval,allowed',[
    ('ABSENT','OLD',True),('SECOND','NEW',True),('ABSENT','NEW',False),
    ('SECOND','OLD',False),('UNKNOWN','NEW',False),(None,'OLD',False),('SECOND',None,False)])
def test_ci_controller_rejects_cross_approval_pairs(entry,approval,allowed):
    m=module();value=dict(approval=m.SECOND_APPROVAL if approval=='NEW' else
        'USER_CONFIRMED_ONE_FREE_GITHUB_VM_2026-10-12T12:49:49Z' if approval=='OLD' else approval)
    if entry!='ABSENT':value['entry']=m.SECOND_ENTRY if entry=='SECOND' else entry
    assert m.controller_approved(value,0) is allowed
    for uid in (1000,False,0.0):assert not m.controller_approved(value,uid)


@pytest.mark.parametrize('args,expected_sha,second',[
    (['a'*40],'a'*40,False),(['a'*40,'--second-once-20261013'],'a'*40,True),
    ([], '',False),(['a'*40,'--second-once'],'',False),
    (['a'*40,'--second-once-20261013','extra'],'',False),
    (['--second-once-20261013','a'*40],'',False)])
def test_ci_command_routes_only_the_explicit_second_entry(monkeypatch,args,expected_sha,second):
    m=module();calls=[]
    def capture(sha,**kw):calls.append((sha,kw));return 19
    monkeypatch.setattr(m,'bootstrap',capture)
    assert m.main(args)==19
    assert calls==[(expected_sha,{'entry':m.SECOND_ENTRY} if second else {})]


@pytest.mark.parametrize('change,entry',[
    ({'TRIAL_ATTEMPT':'2'},'SECOND'),({'TRIAL_NUMBER':'2'},'SECOND'),
    ({'TRIAL_REF':'refs/heads/dev/f2-restricted-linux-trial-20261012'},'SECOND'),
    ({},None),({},'UNKNOWN')])
def test_ci_denied_entry_stops_before_any_filesystem_or_child(monkeypatch,capsys,change,entry):
    m=module();env=second_env(m);env.update(change)
    monkeypatch.setattr(m.os,'environ',env);monkeypatch.setattr(m.os,'geteuid',lambda:0)
    def forbidden(*a,**kw):pytest.fail('denied entry reached physical operation')
    monkeypatch.setattr(m.Path,'cwd',forbidden)
    monkeypatch.setattr(m.subprocess,'check_output',forbidden)
    monkeypatch.setattr(m.subprocess,'Popen',forbidden)
    assert m.bootstrap('a'*40,entry=m.SECOND_ENTRY if entry=='SECOND' else entry)==1
    output=json.loads(capsys.readouterr().out)
    assert output['phase']=='PREFLIGHT' and output['error']=='OS_REFUSED' and output['cleanup'] is True
    assert output['cases']['PROTECTED_RUNTIME']=='FAIL'
    assert all(v=='NOT_RUN' for k,v in output['cases'].items() if k!='PROTECTED_RUNTIME')


def test_ci_second_workflow_has_its_own_exact_once_free_context():
    text=(ROOT/'.github/workflows/restricted-linux-second-trial-once.yml').read_text()
    assert text.count('runs-on:')==1 and 'runs-on: ubuntu-24.04' in text
    assert 'timeout-minutes: 25' in text and 'timeout-minutes: 23' in text
    assert 'branches: [dev/f2-restricted-linux-second-trial-20261013]' in text
    assert "github.ref == 'refs/heads/dev/f2-restricted-linux-second-trial-20261013'" in text
    assert "github.repository == 'T1doo/ParkWeave'" in text and "github.event_name == 'push'" in text
    assert 'github.event.repository.private == false' in text
    assert 'github.run_attempt == 1 && github.run_number == 1' in text
    assert 'group: parkweave-restricted-linux-second-trial-once' in text
    assert 'TRIAL_ENTRY: SECOND_ONCE_20261013' in text and 'TRIAL_ENTRY="$TRIAL_ENTRY"' in text
    assert 'bootstrap.py "$TRIAL_SOURCE_SHA" --second-once-20261013' in text
    assert 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' in text
    assert 'persist-credentials: false' in text and 'sudo -n env -i LANG=C.UTF-8' in text
    for denied in ('workflow_dispatch:','pull_request:','upload-artifact','actions/cache','actions/setup-python',
                   'self-hosted','matrix:','secrets.','dev/f2-restricted-linux-trial-20261012'):
        assert denied not in text
