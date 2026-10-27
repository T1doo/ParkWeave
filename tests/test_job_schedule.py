"""Synthetic stage/deadline oracles; no native runner or process mutation."""
import json
import sys
from types import SimpleNamespace
import pytest
from test_windows_ci_preparation import module
from test_summary_publication import publication


def test_job_cutoff_is_finite_bounded_and_monotonic():
    budget = module('job_budget')
    now = [50]
    job = budget.JobBudget(1200, wall=lambda: 1000, clock=lambda: now[0])
    assert job.limit(600, 10) == 190
    now[0] = 245
    assert job.limit(600, 10) == 0
    now[0] = 260
    assert job.remaining() == 0
    for invalid in (float('inf'), float('nan'), 2291):
        with pytest.raises(ValueError): budget.JobBudget(invalid, wall=lambda: 1000, clock=lambda: 0)


def validation_fixture(tmp_path, monkeypatch, *, prior=True, available=1100, cleanup='OWNED_TREE_STOPPED'):
    suite = module('native_suite'); suite.REPO = tmp_path
    report = tmp_path / 'report.json'; binding = {'run_id': '1', 'run_attempt': '1', 'head_sha': 'a'*40, 'cluster_id': 'synthetic'}
    report.with_name('lifecycle-command.json').write_text(json.dumps({'schema':1,'diagnostic_binding':binding,'exit_code':0,'timed_out':False,'cleanup':'OWNED_TREE_STOPPED'}))
    if prior:
        report.write_text(json.dumps({**suite.summary([]),'diagnostic_schema': 1, 'diagnostic_binding': binding, 'native_stage': 'lifecycle','active_phase':'start',
                                     'report_state': 'COMPLETED', 'cases': [{'case': 'Start_native', 'status': 'FAIL', 'exit_code': 17}]}))
    monkeypatch.setattr(suite, 'current_binding', lambda *args: binding)
    monkeypatch.setattr(suite, 'require_server', lambda: None)
    monkeypatch.setattr(sys, 'executable', str(tmp_path/'.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(sys, 'argv', ['native_suite', '--stage', 'validation', '--job-test-deadline', '1234', '--job-test-uptime','1600000','--regression-shards', 'synthetic.json', '--report', str(report)])
    monkeypatch.setattr(suite, 'os', SimpleNamespace(environ={k:'synthetic' for k in ('PARKWEAVE_OWNER_DSN','PARKWEAVE_DSN','PARKWEAVE_TEST_OWNER_DSN')}))
    remaining=[available];calls=[];records=[]
    class Budget:
        def __init__(self, deadline, **kwargs): assert deadline==1234 and kwargs['uptime_deadline']==1600000
        def limit(self, maximum, reserve=0): return min(maximum,max(0,remaining[0]-reserve))
    monkeypatch.setattr(suite,'JobBudget',Budget)
    def run(command, **kwargs):
        calls.append(('guard' if 'scripts/windows/file_candidate_probe.py' in command else 'candidate',kwargs['timeout']))
        remaining[0]-=2 if calls[-1][0]=='guard' else 3
        return SimpleNamespace(returncode=1 if calls[-1][0]=='guard' else 0,stdout='NOT_RUN: explicit native Windows11',stderr='')
    monkeypatch.setattr(suite.subprocess,'run',run)
    def regression(*args,**kwargs):
        calls.append(('regression',kwargs['budget']));assert kwargs['deadline']==1234
        return SimpleNamespace(returncode=0,cleanup=cleanup)
    monkeypatch.setattr(suite,'run_regression',regression)
    monkeypatch.setattr(suite,'regression_snapshot',lambda *args:{})
    monkeypatch.setattr(suite,'persist',lambda path,record,*args:records.append(json.loads(json.dumps(record))) or True)
    return suite,calls,records


@pytest.mark.parametrize('prior',[True,False])
def test_validation_runs_independent_evidence_and_preserves_lifecycle_failure(tmp_path,monkeypatch,prior):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch,prior=prior)
    assert suite.main()==1
    assert calls==[('guard',15),('candidate',180),('regression',1085)]
    cases=records[-1]['cases']
    assert cases[0]['status']=='FAIL' and cases[0]['case']==('Start_native' if prior else 'suite_initialization')
    assert records[-1]['native_stage']=='validation'


def test_expired_job_never_launches_any_validation_child(tmp_path,monkeypatch):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch,available=0)
    assert suite.main()==1 and calls==[]
    rows=records[-1]['cases'][1:]
    assert len(rows)==3 and all(r['status']=='NOT_RUN' and r['reason']=='TOTAL_BUDGET_EXHAUSTED' for r in rows)


def test_validation_cleanup_refusal_cannot_pass(tmp_path,monkeypatch):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch,cleanup='OWNED_TREE_STOP_UNCONFIRMED')
    assert suite.main()==1
    row=next(r for r in records[-1]['cases'] if r['case']=='full_engineering_regression')
    assert row['status']=='FAIL' and row['exit_code']==0 and row['owned_tree_cleanup']=='OWNED_TREE_STOP_UNCONFIRMED'


@pytest.mark.parametrize('field,value',[('diagnostic_binding',None),('native_stage','validation'),('scope','OTHER'),('cases',[{'case':'raw private text','status':'PASS'}])])
def test_validation_refuses_old_or_unbound_merge_but_runs_current_stages(tmp_path,monkeypatch,field,value):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch)
    path=tmp_path/'report.json';old=json.loads(path.read_text());old[field]=value;path.write_text(json.dumps(old))
    assert suite.main()==1 and len(calls)==3
    assert records[-1]['cases'][0]['case']=='suite_initialization'
    assert not any(r['case']=='Start_native' for r in records[-1]['cases'])


def test_partial_lifecycle_keeps_failure_and_cleanup_metadata(tmp_path,monkeypatch):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch)
    path=tmp_path/'report.json';old=json.loads(path.read_text());old['report_state']='IN_PROGRESS'
    old['cases'][0].update(boundary_phase='health_readiness',boundary_reason='READINESS_TIMEOUT',cleanup_category='BoundaryError',raw_private='must be stripped')
    path.write_text(json.dumps(old));assert suite.main()==1 and len(calls)==3
    rows=records[-1]['cases'];assert rows[0]['case']=='Start_native' and rows[0]['exit_code']==17 and rows[0]['boundary_reason']=='READINESS_TIMEOUT'
    assert rows[0]['cleanup_category']=='BoundaryError' and 'raw_private' not in rows[0]
    assert rows[1]['case']=='suite_initialization' and rows[1]['status']=='FAIL'


def test_lifecycle_stage_never_launches_validation(tmp_path,monkeypatch):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch)
    argv=list(sys.argv);argv[argv.index('validation')]='lifecycle';monkeypatch.setattr(sys,'argv',argv)
    monkeypatch.setattr(suite.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout='',stderr=''))
    assert suite.main()==1 and calls==[]
    assert records[-1]['native_stage']=='lifecycle'
    assert not any(r['case']=='full_engineering_regression' for r in records[-1]['cases'])


@pytest.mark.parametrize('platform',['posix','nt'])
def test_regression_extended_budget_requires_explicit_bounded_cutoff(tmp_path,monkeypatch,platform):
    suite=module('native_suite');calls=[]
    monkeypatch.setattr(suite,'os',SimpleNamespace(name=platform))
    monkeypatch.setattr(suite,'run_owned_job',lambda command,**kwargs:calls.append((command,kwargs)) or SimpleNamespace(returncode=0,cleanup='OWNED_TREE_STOPPED'))
    monkeypatch.setattr(suite,'JobBudget',lambda deadline,**kwargs:SimpleNamespace(remaining=lambda:1100))
    monkeypatch.setattr(suite.subprocess,'run',lambda command,**kwargs:calls.append((command,kwargs)) or SimpleNamespace(returncode=0))
    suite.run_regression('python',tmp_path/'report.json',tmp_path/'progress.json',{},shards='manifest.json',budget=1000,deadline=1234,uptime_deadline=1600000)
    assert calls[0][1]['timeout']==1000 and '--job-test-deadline' in calls[0][0]
    with pytest.raises(ValueError):suite.run_regression('python',tmp_path/'r',tmp_path/'p',{},shards='manifest.json',budget=1000)
    with pytest.raises(ValueError):suite.run_regression('python',tmp_path/'r',tmp_path/'p',{},shards='manifest.json',budget=1101,deadline=1234,uptime_deadline=1600000)


def test_shared_uptime_caps_new_stage_after_wall_clock_rollback():
    budget=module('job_budget');uptime=[1000000];wall=[1000]
    first=budget.JobBudget(1800,uptime_deadline=1800000,wall=lambda:wall[0],clock=lambda:0,uptime=lambda:uptime[0])
    assert first.remaining()==800
    uptime[0]+=600000;wall[0]=1100  # Real 600s elapsed; wall advanced only 100s.
    second=budget.JobBudget(1800,uptime_deadline=1800000,wall=lambda:wall[0],clock=lambda:0,uptime=lambda:uptime[0])
    assert second.remaining()==200
    for invalid in (-1,True,1800000.0,2**63):
        with pytest.raises(ValueError):budget.JobBudget(1800,uptime_deadline=invalid,wall=lambda:1100,clock=lambda:0,uptime=lambda:1600000)


def test_actual_expired_job_budget_preserves_prior_evidence_without_children(tmp_path,monkeypatch):
    budget=module('job_budget')
    assert budget.JobBudget(100,uptime_deadline=100000,wall=lambda:200,clock=lambda:0,uptime=lambda:200000).remaining()==0
    suite,calls,records=validation_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(suite,'JobBudget',lambda deadline,**kwargs:budget.JobBudget(deadline,wall=lambda:2000,uptime=lambda:2000000,clock=lambda:0,**kwargs))
    assert suite.main()==1 and calls==[]
    assert records[-1]['cases'][0]['case']=='Start_native' and records[-1]['cases'][0]['exit_code']==17
    assert all(r['reason']=='TOTAL_BUDGET_EXHAUSTED' for r in records[-1]['cases'][1:])


def test_regression_expiring_between_phase_check_and_launch_returns_not_run(tmp_path,monkeypatch):
    suite=module('native_suite');monkeypatch.setattr(suite,'JobBudget',lambda *args,**kwargs:SimpleNamespace(remaining=lambda:0))
    monkeypatch.setattr(suite.subprocess,'run',lambda *args,**kwargs:pytest.fail('expired child'))
    result=suite.run_regression('python',tmp_path/'r',tmp_path/'p',{},shards='manifest.json',budget=1,deadline=100,uptime_deadline=100000)
    assert result.returncode==1 and result.not_run_reason=='TOTAL_BUDGET_EXHAUSTED'


@pytest.mark.parametrize('mode',['missing','binding','cleanup','type'])
def test_unconfirmed_lifecycle_outer_cleanup_isolates_all_validation(tmp_path,monkeypatch,mode):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch);path=tmp_path/'lifecycle-command.json'
    if mode=='missing':path.unlink()
    else:
        row=json.loads(path.read_text())
        if mode=='binding':row['diagnostic_binding']=None
        elif mode=='cleanup':row['cleanup']='OWNED_TREE_STOP_UNCONFIRMED'
        else:row['timed_out']=1
        path.write_text(json.dumps(row))
    assert suite.main()==1 and calls==[]
    rows=records[-1]['cases'];assert rows[0]['case']=='Start_native' and rows[0]['exit_code']==17
    later=[r for r in rows if r['status']=='NOT_RUN'];assert len(later)==3 and all(r['reason']=='CLEANUP_NOT_CONFIRMED' for r in later)


def test_confirmed_cleanup_after_outer_timeout_preserves_failure_and_runs_validation(tmp_path,monkeypatch):
    suite,calls,records=validation_fixture(tmp_path,monkeypatch);path=tmp_path/'lifecycle-command.json';row=json.loads(path.read_text());row.update(exit_code=17,timed_out=True);path.write_text(json.dumps(row))
    assert suite.main()==1 and len(calls)==3
    row=next(r for r in records[-1]['cases'] if r['case']=='lifecycle_exception')
    assert row['exit_code']==17 and row['category']=='TimeoutExpired' and row['status']=='FAIL'


@pytest.mark.parametrize('mode',['success','missing','binding','timeout','cleanup'])
def test_publisher_validation_outer_result_keeps_original_failure(publication,mode):
    source,path,_=publication;publisher=module('publish_summary');record=json.loads(path.read_text());record['native_stage']='validation';path.write_text(json.dumps(record));control=path.with_name('validation-command.json')
    row={'schema':1,'diagnostic_binding':record['diagnostic_binding'],'exit_code':0,'timed_out':False,'cleanup':'OWNED_TREE_STOPPED'}
    if mode=='binding':row['diagnostic_binding']=None
    elif mode=='timeout':row.update(exit_code=17,timed_out=True)
    elif mode=='cleanup':row['cleanup']='OWNED_TREE_STOP_UNCONFIRMED'
    if mode!='missing':control.write_text(json.dumps(row))
    result=publisher.read_summary(source);assert result['cases'][0]['case']=='full_engineering_regression' and result['cases'][0]['status']=='FAIL'
    assert len(result['cases'])==(1 if mode=='success' else 2)
    if mode!='success':assert result['cases'][-1]['case']=='suite_exception' and result['cases'][-1]['status']=='FAIL'
    if mode in ('missing','binding','cleanup'):assert result['cases'][-1]['reason']=='CLEANUP_NOT_CONFIRMED'


def test_publisher_compacts_pretty_console_above_existing_limit(monkeypatch,capsys):
    publisher=module('publish_summary');public=publisher.base('SUMMARY_AVAILABLE');public.update(report_state='COMPLETED',active_phase='UNKNOWN')
    public['padding']=[0]*20000
    assert len(json.dumps(public).encode())<publisher.MAX_BYTES<len(json.dumps(public,indent=2).encode())
    monkeypatch.setattr(publisher,'read_summary',lambda source:public)
    monkeypatch.setattr(publisher,'annotation_commands',lambda value:([],True))
    monkeypatch.setattr(publisher,'write_annotations',lambda commands:None)
    assert publisher.main({})==1  # No summary sink, independent bounded console survives.
    output=capsys.readouterr().out;assert len(output.encode())<=publisher.MAX_BYTES+1 and json.loads(output)==public


@pytest.mark.parametrize('control_exists',[True,False])
def test_lifecycle_only_publication_requires_outer_result_and_marks_validation_missing(publication,control_exists):
    source,path,_=publication;publisher=module('publish_summary');record=json.loads(path.read_text());record.update(native_stage='lifecycle',cases=[{'case':'Start_native','status':'PASS'}]);path.write_text(json.dumps(record))
    if control_exists:path.with_name('lifecycle-command.json').write_text(json.dumps({'schema':1,'diagnostic_binding':record['diagnostic_binding'],'exit_code':0,'timed_out':False,'cleanup':'OWNED_TREE_STOPPED'}))
    result=publisher.read_summary(source);assert result['cases'][0]=={'case':'Start_native','status':'PASS'}
    assert result['cases'][-1]['case']=='full_engineering_regression' and result['cases'][-1]['status']=='NOT_RUN' and result['cases'][-1]['reason']=='VALIDATION_NOT_COMPLETED'
    assert len(result['cases'])==(2 if control_exists else 3)


def test_publisher_rejects_unknown_staged_marker(publication):
    source,path,_=publication;record=json.loads(path.read_text());record['native_stage']='future';path.write_text(json.dumps(record))
    assert module('publish_summary').read_summary(source)['publication_state']=='SUMMARY_INVALID'


@pytest.mark.parametrize('mode',['duplicate','constant','oversize','symlink'])
def test_stage_command_parser_refuses_ambiguous_or_unbounded_input(tmp_path,mode):
    parser=module('stage_result');path=tmp_path/'command.json';binding={'run_id':'synthetic'}
    valid={'schema':1,'diagnostic_binding':binding,'exit_code':0,'timed_out':False,'cleanup':'OWNED_TREE_STOPPED'}
    if mode=='duplicate':path.write_text(json.dumps(valid)[:-1]+',"exit_code":17}')
    elif mode=='constant':path.write_text(json.dumps(valid).replace('"exit_code": 0','"exit_code": NaN'))
    elif mode=='oversize':path.write_bytes(b'x'*(16*1024+1))
    else:
        target=tmp_path/'target.json';target.write_text(json.dumps(valid))
        try:path.symlink_to(target)
        except OSError:pytest.skip('current user cannot create synthetic symlink')
    with pytest.raises(ValueError):parser.read_command(path,binding)
