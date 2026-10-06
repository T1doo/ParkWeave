"""Fixed object enums and a single last-recorded snapshot; synthetic probes only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from types import SimpleNamespace
import pytest
from test_summary_publication import publication
from test_lifecycle import lifecycle
from test_acl_readonly import powershell_fixture
from test_windows_ci_preparation import module,ROOT
import lifecycle_diagnostics as diagnostic

KNOWN='tests/test_lifecycle.py::test_config_write_is_exclusive_and_no_secret_fields'
POISON='SYNTHETIC /private/path SID credential %0A\n::error::injection'


@pytest.mark.parametrize('fault,expected,code',[('inheritance','ROOT',4),('owner_mismatch','SESSIONS',2),('config_owner','CONFIG',2)])
def test_powershell_readonly_object_is_fixed_and_reason_keeps_exit_contract(tmp_path,fault,expected,code):
    if fault=='config_owner':
        private=tmp_path/'private';private.mkdir();(private/'windows-config.json').write_text('SYNTHETIC')
    result=powershell_fixture(tmp_path,fault,lifecycle.acl_check_command())
    assert result.returncode==code and result.stdout==expected+'\n' and result.stderr==''


@pytest.mark.parametrize('raw,expected',[(b'ROOT\r\n','ROOT'),('SESSIONS\n','SESSIONS'),('CONFIG','CONFIG'),(POISON,None),(b'ROOT\nCONFIG\n',None),(b'ROOT\xff',None),(b'x'*65537,None)],ids=['root-crlf','sessions-lf','config','poison','multiple','non-ascii','oversize'])
def test_acl_object_roundtrip_discards_private_or_multiple_output(tmp_path,monkeypatch,raw,expected):
    monkeypatch.setattr(lifecycle,'require_windows',lambda:None)
    monkeypatch.setattr(lifecycle.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=2,stdout=raw,stderr=POISON))
    with pytest.raises(lifecycle.BoundaryError) as failure:lifecycle.native_acl_check(tmp_path)
    marker=diagnostic.command('doctor',failure.value);row=diagnostic.parse(marker,'doctor')
    assert row['boundary_reason']=='ACL_OWNER_MISMATCH' and row.get('acl_object')==expected
    assert POISON not in marker and len((marker+'\n').encode('ascii'))<=1024


@pytest.mark.parametrize('obj',[POISON,'FILES','UNKNOWN',True,{},['ROOT']])
def test_lifecycle_rejects_unknown_acl_objects_without_exposing_input(obj):
    row={'schema':1,'action':'doctor','boundary_phase':'private_acl','category':'BoundaryError','boundary_reason':'ACL_OWNER_MISMATCH','acl_object':obj}
    assert diagnostic.parse(diagnostic.PREFIX+json.dumps(row),'doctor')['boundary_reason']=='DIAGNOSTIC_UNAVAILABLE'


def test_atomic_phase_and_allowlisted_deparametrized_test_share_one_snapshot(tmp_path):
    progress=module('regression_progress');path=tmp_path/('server-regression-'+uuid.uuid4().hex+'.progress.json')
    progress.write(path,'pytest_call',KNOWN+'['+POISON+']')
    assert progress.read_snapshot(path)=={'regression_phase':'pytest_call','active_test_id':KNOWN}
    assert POISON not in path.read_text() and len(path.read_bytes())<=512
    progress.write(path,'pytest_teardown',POISON)
    assert progress.read_snapshot(path)=={'regression_phase':'pytest_teardown'}
    assert json.loads(path.read_text())['active_test_id'] is None
    assert not list(tmp_path.glob('.progress-*.tmp'))


@pytest.mark.parametrize('corruption',['wrong_id','duplicate','wrong_uuid','non_string','over_bound'])
def test_atomic_snapshot_corruption_never_projects_partial_phase_or_id(tmp_path,corruption):
    progress=module('regression_progress');path=tmp_path/('server-regression-'+uuid.uuid4().hex+'.progress.json')
    progress.write(path,'pytest_call',KNOWN);row=json.loads(path.read_text())
    if corruption=='wrong_id':row['active_test_id']=POISON
    if corruption=='wrong_uuid':row['execution_id']=uuid.uuid4().hex
    if corruption=='non_string':row['active_test_id']=[KNOWN]
    text=json.dumps(row)
    if corruption=='duplicate':text=text[:-1]+',"phase":"pytest_setup"}'
    if corruption=='over_bound':text+='x'*513
    path.write_text(text)
    assert progress.read_snapshot(path)=={'regression_phase':'UNKNOWN'}


@pytest.mark.parametrize('phase',['pytest_setup','pytest_call','pytest_teardown'])
def test_real_pytest_last_recorded_id_survives_stall_without_raw_parameter(tmp_path,phase):
    progress=module('regression_progress');path=tmp_path/('server-regression-'+uuid.uuid4().hex+'.progress.json')
    folder=tmp_path/'tests';folder.mkdir();test=folder/'test_lifecycle.py'
    code='import pytest,time\n'
    if phase=='pytest_setup':code+='@pytest.fixture\ndef slow():\n time.sleep(20)\n'
    elif phase=='pytest_teardown':code+='@pytest.fixture\ndef slow():\n yield\n time.sleep(20)\n'
    code+='@pytest.mark.parametrize("value",['+repr(POISON)+'])\ndef '+KNOWN.split('::')[1]+'(value'+(',slow' if phase!='pytest_call' else '')+'):\n '+('time.sleep(20)' if phase=='pytest_call' else 'pass')+'\n'
    test.write_text(code)
    from parkweave.process_env import minimal_environment
    process=subprocess.Popen([sys.executable,'-m','pytest','-q','-p','scripts.windows_ci.regression_plugin','--rootdir',str(tmp_path),'--parkweave-progress',str(path),str(test)],cwd=ROOT,env=minimal_environment(os.environ),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            snapshot=progress.read_snapshot(path)
            if {key:snapshot.get(key) for key in ('regression_phase','active_test_id')}=={'regression_phase':phase,'active_test_id':KNOWN}:break
            assert process.poll() is None;time.sleep(.03)
        assert {key:snapshot.get(key) for key in ('regression_phase','active_test_id')}=={'regression_phase':phase,'active_test_id':KNOWN}
        assert snapshot['regression_observation']['collected']==1
        assert snapshot['regression_observation']['completed']==0
        assert POISON not in json.dumps(snapshot)
        assert process.poll() is None and POISON not in path.read_text()
    finally:
        if process.poll() is None:process.terminate()
        process.wait(timeout=5)


def test_timeout_reads_one_phase_id_snapshot_and_preserves_failure(tmp_path,monkeypatch):
    suite=module('native_suite');progress=module('regression_progress');suite.REPO=tmp_path;suite.require_server=lambda:None
    monkeypatch.setattr(suite.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(suite.sys,'argv',['native_suite','--report',str(tmp_path/'summary.json')])
    config={k:'SYNTHETIC' for k in ('PARKWEAVE_OWNER_DSN','PARKWEAVE_DSN','PARKWEAVE_TEST_OWNER_DSN')};monkeypatch.setattr(suite.os,'environ',config)
    reads=[]
    def snapshot(path):reads.append(path);return progress.read_snapshot(path)
    monkeypatch.setattr(suite,'regression_snapshot',snapshot)
    def run(command,**kw):
        if 'scripts/run_acceptance.py' in command:
            assert kw['timeout']==600
            path=Path(command[command.index('--progress')+1]);progress.write(path,'pytest_call',KNOWN)
            raise subprocess.TimeoutExpired(command,600,output=POISON,stderr=POISON)
        return SimpleNamespace(returncode=1,stdout='',stderr='')
    monkeypatch.setattr(suite,'run_owned_job',lambda command,**kwargs:run(command,**kwargs))
    monkeypatch.setattr(suite.subprocess,'run',run)
    assert suite.main()==1 and len(reads)==1
    rows=json.loads((tmp_path/'summary.json').read_text())['cases'];row=next(x for x in rows if x['case']=='full_engineering_regression')
    assert row['status']=='FAIL' and row['category']=='TimeoutExpired' and row['regression_phase']=='pytest_call' and row['active_test_id']==KNOWN
    assert POISON not in repr(rows)


def test_safe_projection_and_annotations_expose_fixed_object_and_last_id_with_global_bounds():
    publisher=module('publish_summary');binding={'synthetic':'binding'}
    record=module('native_suite').summary([
        {'case':'Setup_native','status':'FAIL','boundary_phase':'private_acl','category':'BoundaryError','boundary_reason':'ACL_OWNER_MISMATCH','acl_object':'CONFIG','raw':POISON},
        {'case':'full_engineering_regression','status':'FAIL','phase':'regression_run','category':'TimeoutExpired','regression_phase':'pytest_call','active_test_id':KNOWN,'failure_diagnostics':{'state':'AVAILABLE','failed_test_ids':sorted(publisher._allowed_tests(),key=len)[:25]}},
    ])
    record.update(diagnostic_schema=1,diagnostic_binding=binding,report_state='COMPLETED',active_phase='UNKNOWN')
    public=publisher.project(record,binding);commands,ok=publisher.annotation_commands(public)
    assert ok and len(commands)==3 and POISON not in repr(commands) and 'tests/' not in repr(commands)
    rows=[json.loads(c.split('::',2)[-1]) for c in commands]
    assert rows[1]['acl_object']=='CONFIG' and rows[2]['active_test_id']==KNOWN.removeprefix('tests/').replace('.py::','::')
    assert len(rows[2]['failed_test_ids'])==24 and rows[2]['annotation_ids_omitted']==1
    assert sum(len(r.get('failed_test_ids',[]))+int('active_test_id' in r) for r in rows)==25
    assert max(publisher.annotation_size(c) for c in commands)<=2048 and sum(publisher.annotation_size(c) for c in commands)<=16384


@pytest.mark.parametrize('field',['acl_object','active_test_id'])
def test_hostile_new_annotation_fields_fail_closed(publication,field):
    source,_,_=publication;publisher=module('publish_summary');public=publisher.read_summary(source)
    public['cases'][0][field]=POISON
    commands,ok=publisher.annotation_commands(public)
    assert not ok and len(commands)==1 and POISON not in repr(commands)


def test_identity_read_failure_does_not_misattribute_an_acl_object(tmp_path):
    command=lifecycle.acl_check_command().replace('if ($null -eq $sid', "throw 'SYNTHETIC identity unavailable'; if ($null -eq $sid",1)
    result=powershell_fixture(tmp_path,'valid',command)
    assert result.returncode==5 and result.stdout==result.stderr==''


def test_valid_acl_primary_survives_cleanup_without_mixing_metadata():
    error=PermissionError(POISON);error.parkweave_lifecycle_phase='process_stop'
    error.parkweave_lifecycle_primary={'boundary_phase':'private_acl','category':'BoundaryError','boundary_reason':'ACL_OWNER_MISMATCH','acl_object':'CONFIG'}
    row=diagnostic.parse(diagnostic.command('start',error),'start')
    assert row=={**error.parkweave_lifecycle_primary,'cleanup_category':'PermissionError'}
    assert POISON not in repr(row)
