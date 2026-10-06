"""Owned local Git/synthetic runners; early failure never executes real tests."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET
import pytest
from test_windows_ci_preparation import module
from scripts.windows_ci import regression_shards

POISON='SYNTHETIC_PRIVATE_PATH_DSN_ERROR'


@pytest.fixture
def cli(tmp_path,monkeypatch):
    root=tmp_path/'repo';(root/'tests').mkdir(parents=True);(root/'docs/F1').mkdir(parents=True)
    files=[]
    for name in ('a','b','c','d'):
        path=root/'tests'/('test_'+name+'.py');path.write_text('def test_one():\n assert True\n');files.append(path.relative_to(root).as_posix())
    row={'id':'AT-SYNTHETIC','stage':'F1','gate':'LIVE_BLOCKED','whole_status':'NOT_RUN','engineering_selectors':[files[0]+'::test_one']}
    (root/'docs/F1/ATBindings.json').write_text(json.dumps({'cases':[row]}));(root/'docs/验收规格.json').write_text(json.dumps({'cases':[{'id':row['id']}]}))
    document={'shards':[{'id':'S'+str(i+1),'files':[f]} for i,f in enumerate(files)],'source_file_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files}}
    manifest=root/'manifest.json';manifest.write_text(json.dumps(document))
    for command in (['git','init','-q'],['git','-c','core.autocrlf=false','add','tests'],['git','-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','fixture']):
        subprocess.run(command,cwd=root,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    spec=importlib.util.spec_from_file_location('acceptance_fault_fixture',Path(__file__).resolve().parents[1]/'scripts/run_acceptance.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner);monkeypatch.setattr(runner,'ROOT',root)
    report=root/'report.json';progress=root/'.runtime'/('server-regression-'+'a'*32+'.progress.json');progress.parent.mkdir()
    monkeypatch.setattr(sys,'argv',['acceptance','--shards',str(manifest),'--report',str(report),'--progress',str(progress),'--shard-budget','30'])
    return runner,root,manifest,report,progress,head,document


def invoke(cli,capsys):
    runner,root,manifest,report,progress,head,document=cli
    with pytest.raises(SystemExit) as error:runner.main()
    output=capsys.readouterr().out
    assert POISON not in output and str(root) not in output
    return error.value.code,json.loads(report.read_text()) if report.is_file() else None,json.loads(output)


@pytest.mark.parametrize('mode',['json','prefilled'])
def test_binding_failure_has_safe_atomic_zero_observation_and_four_not_run(cli,capsys,mode):
    _,root,_,_,_,_,_=cli;path=root/'docs/F1/ATBindings.json'
    if mode=='json':path.write_text(POISON)
    else:
        value=json.loads(path.read_text());value['cases'][0]['whole_status']='PASS';path.write_text(json.dumps(value))
    code,report,public=invoke(cli,capsys)
    assert code==1 and report['acceptance_failure']['reason']=='ACCEPTANCE_BINDINGS_INVALID'
    assert report['observed_cases']==0 and report['engineering_total_counts']=={'PASS':0,'FAIL':0,'SKIP':0}
    assert not report['full_regression'] and not report['coverage_complete']
    assert all(row['status']=='NOT_RUN' for row in report['shards'])
    assert public['report_state']=='AVAILABLE'


@pytest.mark.parametrize('mode,reason',[('hash','MANIFEST_HASH_MISMATCH'),('json','MANIFEST_SCHEMA_REFUSED'),('partition','MANIFEST_SOURCE_SET_MISMATCH'),('missing','MANIFEST_READ_FAILED')])
def test_manifest_refusal_never_becomes_report_missing(cli,capsys,mode,reason):
    _,_,manifest,_,progress,_,document=cli
    if mode=='hash':document['source_file_sha256'][document['shards'][0]['files'][0]]='0'*64;manifest.write_text(json.dumps(document))
    elif mode=='json':manifest.write_text(POISON)
    elif mode=='partition':document['shards'][0]['files']=document['shards'][1]['files'];manifest.write_text(json.dumps(document))
    else:manifest.unlink()
    code,report,_=invoke(cli,capsys)
    assert code==1 and report['acceptance_failure']['reason']==reason and report['acceptance_failure']['stage']=='MANIFEST'
    assert json.loads(progress.read_text())['phase']=='acceptance_bindings'
    assert not list(progress.parent.glob('collection-*.json'))


@pytest.mark.parametrize('claim',['0'*40,'malformed-'+POISON])
def test_wrong_source_head_cannot_pass_or_echo_claim(cli,capsys,monkeypatch,claim):
    monkeypatch.setattr(sys,'argv',sys.argv+['--source-head',claim]);code,report,_=invoke(cli,capsys)
    assert code==1 and report['source_binding']=={'state':'UNAVAILABLE'}
    assert report['acceptance_failure']['reason'] in ('SOURCE_HEAD_MISMATCH','SOURCE_BINDING_INVALID')
    assert report['acceptance_failure']['stage']=='SOURCE_BINDING'


def test_second_deadline_failure_keeps_safe_report(cli,capsys,monkeypatch):
    import job_budget
    calls=[]
    def budget(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:raise ValueError(POISON)
        return SimpleNamespace(remaining=lambda:30)
    monkeypatch.setattr(job_budget,'JobBudget',budget)
    monkeypatch.setattr(sys,'argv',sys.argv+['--job-test-deadline','100','--job-test-uptime','100000'])
    code,report,_=invoke(cli,capsys)
    assert len(calls)==2 and code==1 and report['acceptance_failure']['reason']=='JOB_BUDGET_REFUSED'


def test_unwritable_report_is_explicit_unavailable_not_claimed_saved(cli,capsys):
    _,_,_,report,_,_,_=cli;report.mkdir()
    code,saved,public=invoke(cli,capsys)
    assert code==1 and saved is None and public['report_state']=='UNAVAILABLE'
    assert public['acceptance_failure']['stage']=='REPORT_WRITE'
    assert public['acceptance_failure']['reason']=='REPORT_WRITE_FAILED'


def synthetic_run(command,**kwargs):
    collected=Path(command[command.index('--parkweave-shard-collection')+1]);files=['tests/test_'+n+'.py' for n in ('a','b','c','d')]
    selected=files if '--collect-only' in command else [f for f in files if f in command];nodes=[f+'::test_one' for f in selected]
    collected.write_text(json.dumps({'schema':2,'nodeids':nodes,'case_keys':[regression_shards.case_key(n,{}) for n in nodes]}))
    if '--junitxml' in command:
        xml=ET.Element('testsuite')
        for f in selected:ET.SubElement(xml,'testcase',classname=Path(f).stem,name='test_one')
        ET.ElementTree(xml).write(command[command.index('--junitxml')+1])
    return SimpleNamespace(returncode=0)


@pytest.mark.parametrize('claim',[False,True])
def test_normal_source_claim_requires_actual_head_and_test_blobs(cli,capsys,monkeypatch,claim):
    runner,_,_,_,_,head,_=cli
    actual=regression_shards.execute
    monkeypatch.setitem(sys.modules,'regression_shards',SimpleNamespace(execute=lambda *args,**kwargs:actual(*args,**kwargs,runner=synthetic_run)))
    if claim:monkeypatch.setattr(sys,'argv',sys.argv+['--source-head',head])
    # Normal success has the legacy private report-path stdout; parse only report.
    with pytest.raises(SystemExit) as error:runner.main()
    assert error.value.code==0;capsys.readouterr()
    report=json.loads(cli[3].read_text());assert report['engineering_total_counts']=={'PASS':4,'FAIL':0,'SKIP':0}
    assert report['source_binding']==({'state':'AVAILABLE','head_sha':head} if claim else {'state':'UNAVAILABLE'})
    assert report['full_regression'] is claim


def test_late_report_failure_preserves_original_exit_and_observed_counts(tmp_path,capsys):
    spec=importlib.util.spec_from_file_location('acceptance_late_fixture',Path(__file__).resolve().parents[1]/'scripts/run_acceptance.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    args=SimpleNamespace(report=tmp_path/'report.json',shards=True)
    context={'engineering_total_counts':{'PASS':3,'FAIL':1,'SKIP':0},'shards':[{'id':'S1','status':'FAIL','counts':{'PASS':0,'FAIL':1,'SKIP':0}}]}
    with pytest.raises(SystemExit) as error:runner.rejected_report(args,'REPORT_WRITE',OSError(POISON),{'state':'UNAVAILABLE'},17,context)
    report=json.loads(args.report.read_text());assert error.value.code==17 and report['execution_exit_code']==17
    assert report['observed_cases']==4 and report['shards'][0]['status']=='FAIL'
    assert POISON not in capsys.readouterr().out


def test_public_projection_keeps_only_typed_acceptance_and_identity_metadata():
    publisher=module('publish_summary');binding={'synthetic':'binding'};report=module('native_suite').summary([
        {'case':'full_engineering_regression','status':'FAIL','exit_code':1,'source_binding':{'state':'HEAD_ONLY','head_sha':'a'*40},
         'acceptance_failure':{'stage':'MANIFEST','reason':'MANIFEST_HASH_MISMATCH','category':'ValueError'},'raw_error':POISON},
        {'case':'Stop_native','status':'FAIL','identity_refusal':{'stage':'RECHECK','reason':'IDENTITY_CHANGED'}},
        {'case':'Start_native','status':'FAIL','cleanup_category':'BoundaryError','cleanup_identity_refusal':{'stage':'CLOSE','reason':'CLOSE_FAILED'}}])
    report.update(diagnostic_schema=1,diagnostic_binding=binding,report_state='COMPLETED',active_phase='UNKNOWN')
    safe=publisher.project(report,binding);commands,ok=publisher.annotation_commands(safe)
    assert ok and POISON not in json.dumps(safe) and 'MANIFEST_HASH_MISMATCH' in '\n'.join(commands)
    assert 'IDENTITY_CHANGED' in '\n'.join(commands) and 'CLOSE_FAILED' in '\n'.join(commands)
    report['cases'][1]['identity_refusal']['reason']=POISON
    with pytest.raises(ValueError):publisher.project(report,binding)


@pytest.mark.parametrize('state,head,expected',[('UNAVAILABLE',None,'FAIL'),('HEAD_ONLY','a'*40,'FAIL'),('AVAILABLE','b'*40,'FAIL'),('AVAILABLE','a'*40,'PASS')])
def test_native_zero_exit_cannot_pass_wrong_or_incomplete_source_binding(tmp_path,monkeypatch,state,head,expected):
    from test_job_schedule import validation_fixture
    suite,_,records=validation_fixture(tmp_path,monkeypatch)
    def regression(managed,report,progress,env,**kwargs):
        assert kwargs['source_head']=='a'*40
        binding={'state':state}
        if head is not None:binding['head_sha']=head
        report.write_text(json.dumps({'engineering_total_counts':{'PASS':4,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN',
                                     'execution_exit_code':0,'coverage_complete':True,'source_binding':binding}))
        return SimpleNamespace(returncode=0,cleanup='OWNED_TREE_STOPPED')
    monkeypatch.setattr(suite,'run_regression',regression)
    assert suite.main()==1  # Original lifecycle failure remains independent.
    row=next(row for row in records[-1]['cases'] if row['case']=='full_engineering_regression')
    assert row['status']==expected and row['exit_code']==0 and row['counts']=={'PASS':4,'FAIL':0,'SKIP':0}


def test_unsharded_late_failure_context_does_not_index_nonexistent_shards(tmp_path,capsys):
    spec=importlib.util.spec_from_file_location('acceptance_no_shards_fixture',Path(__file__).resolve().parents[1]/'scripts/run_acceptance.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    args=SimpleNamespace(report=tmp_path/'report.json',shards=None)
    with pytest.raises(SystemExit) as error:runner.rejected_report(args,'REPORT_WRITE',OSError(POISON),{'state':'UNAVAILABLE'},17,
        {'engineering_total_counts':{'PASS':1,'FAIL':0,'SKIP':0},'shards':[{'id':'S1','status':'PASS'}]})
    assert error.value.code==17 and json.loads(args.report.read_text())['shards']==[]
    assert POISON not in capsys.readouterr().out


def test_zero_exit_report_with_fixed_failure_is_never_pass(tmp_path,monkeypatch):
    from test_job_schedule import validation_fixture
    suite,_,records=validation_fixture(tmp_path,monkeypatch)
    def regression(managed,report,*args,**kwargs):
        report.write_text(json.dumps({'engineering_total_counts':{'PASS':0,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN',
            'execution_exit_code':0,'coverage_complete':True,'source_binding':{'state':'AVAILABLE','head_sha':'a'*40},
            'acceptance_failure':{'stage':'MANIFEST','reason':'MANIFEST_HASH_MISMATCH','category':'ValueError'}}))
        return SimpleNamespace(returncode=0,cleanup='OWNED_TREE_STOPPED')
    monkeypatch.setattr(suite,'run_regression',regression);assert suite.main()==1
    row=next(r for r in records[-1]['cases'] if r['case']=='full_engineering_regression')
    assert row['status']=='FAIL' and row['exit_code']==0 and row['reason']=='MANIFEST_HASH_MISMATCH'


def test_actual_stop_marker_through_native_row_remains_publishable(tmp_path,monkeypatch):
    suite=module('native_suite');suite.REPO=tmp_path;monkeypatch.setattr(suite,'require_server',lambda:None)
    monkeypatch.setattr(sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'))
    report=tmp_path/'engineering.json';monkeypatch.setattr(sys,'argv',['native','--report',str(report)])
    monkeypatch.setattr(suite.os,'environ',{k:'SYNTHETIC' for k in ('PARKWEAVE_OWNER_DSN','PARKWEAVE_DSN','PARKWEAVE_TEST_OWNER_DSN')})
    runtime=tmp_path/'.runtime';runtime.mkdir();(runtime/'windows-processes.json').write_text('{}')
    diagnostic=module('native_suite').lifecycle_failure
    import lifecycle_diagnostics
    error=ValueError(POISON);error.parkweave_lifecycle_phase='process_stop';error.parkweave_lifecycle_reason='BOUNDARY_REFUSED'
    error.parkweave_identity_refusal={'stage':'RECHECK','reason':'IDENTITY_CHANGED'}
    marker=lifecycle_diagnostics.command('stop',error);assert diagnostic(marker,'stop')['boundary_phase']=='process_stop'
    def run(command,**kwargs):
        if any(str(p).endswith('Stop.ps1') for p in command):return SimpleNamespace(returncode=1,stdout=marker,stderr='')
        if 'scripts/windows/file_candidate_probe.py' in command:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr='')
        return SimpleNamespace(returncode=1,stdout='',stderr='')
    monkeypatch.setattr(suite.subprocess,'run',run);monkeypatch.setattr(suite,'run_regression',lambda *args,**kwargs:SimpleNamespace(returncode=1))
    assert suite.main()==1
    record=json.loads(report.read_text());row=next(r for r in record['cases'] if r['case']=='final_Stop_owned_services')
    assert row['identity_refusal']=={'stage':'RECHECK','reason':'IDENTITY_CHANGED'}
    assert not {'boundary_phase','boundary_reason','cleanup_category'}&set(row)
    binding={'synthetic':'binding'};record['diagnostic_binding']=binding
    safe=module('publish_summary').project(record,binding);commands,ok=module('publish_summary').annotation_commands(safe)
    assert ok and 'IDENTITY_CHANGED' in '\n'.join(commands) and POISON not in json.dumps(safe)


@pytest.mark.parametrize('mode',['missing','empty'])
@pytest.mark.parametrize('child_code',[0,17])
def test_unsharded_verified_source_requires_nonempty_junit(cli,capsys,monkeypatch,mode,child_code):
    _,_,_,_,_,head,_=cli
    argv=list(sys.argv);index=argv.index('--shards');del argv[index:index+2]
    monkeypatch.setattr(sys,'argv',argv+['--source-head',head])
    real_run=subprocess.run
    def run(command,**kwargs):
        if '-m' in command and command[command.index('-m')+1]=='pytest':
            if mode=='empty':Path(command[command.index('--junitxml')+1]).write_text('<testsuites/>')
            return SimpleNamespace(returncode=child_code)
        return real_run(command,**kwargs)
    monkeypatch.setattr(subprocess,'run',run)
    code,report,_=invoke(cli,capsys)
    assert code==(child_code or 1) and report['execution_exit_code']==code
    assert report['source_binding']=={'state':'AVAILABLE','head_sha':head}
    assert report['acceptance_failure']['reason']=='REPORT_SUMMARY_FAILED'
    assert report['counts_scope']=='UNAVAILABLE' and report['observed_cases'] is None
    assert not report['full_regression'] and not report['coverage_complete'] and report['shards']==[]


def test_actual_shard_persist_failure_preserves_completed_observation(cli,capsys,monkeypatch):
    _,_,_,_,_,head,_=cli
    actual=regression_shards.execute;real_save=regression_shards.save;observations=[]
    def save(path,value):
        observations.append(dict(value['engineering_total_counts']))
        if value['engineering_total_counts']['PASS']==1:raise OSError(POISON)
        return real_save(path,value)
    monkeypatch.setattr(regression_shards,'save',save)
    monkeypatch.setitem(sys.modules,'regression_shards',SimpleNamespace(execute=lambda *args,**kwargs:actual(*args,**kwargs,runner=synthetic_run)))
    monkeypatch.setattr(sys,'argv',sys.argv+['--source-head',head])
    code,report,_=invoke(cli,capsys)
    assert observations[-1]=={'PASS':1,'FAIL':0,'SKIP':0}
    assert code==1 and report['acceptance_failure']['stage']=='REPORT_WRITE'
    assert report['acceptance_failure']['reason']=='REPORT_WRITE_FAILED'
    assert report['observed_cases']==1 and report['engineering_total_counts']==observations[-1]
    assert report['shards'][0]['status']=='PASS' and report['shards'][0]['counts']['PASS']==1
    assert all(row['status']=='NOT_RUN' for row in report['shards'][1:])
    assert not report['full_regression'] and not report['coverage_complete']


def test_legacy_native_zero_exit_missing_report_is_failure(tmp_path,monkeypatch):
    from test_job_schedule import validation_fixture
    suite,_,records=validation_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(sys,'argv',['native_suite','--report',str(tmp_path/'report.json')])
    monkeypatch.setattr(suite,'run_regression',lambda *args,**kwargs:SimpleNamespace(returncode=0,cleanup='OWNED_TREE_STOPPED'))
    assert suite.main()==1
    row=next(r for r in records[-1]['cases'] if r['case']=='full_engineering_regression')
    assert row['status']=='FAIL' and row['exit_code']==0
    assert row['failure_diagnostics']['state']=='REPORT_MISSING'
