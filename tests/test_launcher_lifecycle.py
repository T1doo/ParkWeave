"""Lifecycle integration of private proven child records; no native PASS claim."""
import json
from types import SimpleNamespace
import pytest
from test_bounded_observation import prepare_start
from test_lifecycle_diagnostics import lifecycle,diagnostic


def test_start_persists_verified_api_child_without_changing_root_records(tmp_path,monkeypatch,capsys):
    import psutil
    prepare_start(tmp_path,monkeypatch,'PID_MISMATCH')
    monkeypatch.setattr(lifecycle,'native_binding_enabled',lambda:True)
    monkeypatch.setattr(psutil.Popen,'children',lambda self,recursive=False:[],raising=False)
    def binding(root,record,pid,repo):
        if root.pid==901:
            return {'relation':'DIRECT_CHILD','server':{'pid':9999,'created':1.01,'command':record['command'],'parent_pid':901,'parent_created':record['created']}}
        return {'relation':'ROOT','server':None}
    monkeypatch.setattr(lifecycle,'bind_execution',binding)
    lifecycle.start()
    rows=json.loads(lifecycle.STATE.read_text())['processes']
    assert [r['pid'] for r in rows]==[901,902]
    assert rows[0]['server']['pid']==9999 and rows[0]['server']['parent_pid']==901
    assert 'server' not in rows[1]
    obs=diagnostic.parse(capsys.readouterr().out,'start')['start_observation']
    assert obs['server_relation']=='DIRECT_CHILD' and obs['server_pid_valid'] and obs['process_matches']


def test_metadata_binding_refuses_changed_state_without_overwriting(tmp_path,monkeypatch):
    path=tmp_path/'state.json';path.write_bytes(b'changed user record')
    monkeypatch.setattr(lifecycle,'STATE',path)
    with pytest.raises(lifecycle.BoundaryError):lifecycle.save_execution_bindings([],b'original owned record')
    assert path.read_bytes()==b'changed user record' and list(tmp_path.iterdir())==[path]


def test_binding_write_failure_is_not_swallowed_as_transport_retry(tmp_path,monkeypatch):
    prepare_start(tmp_path,monkeypatch,'MODE_MISMATCH')
    monkeypatch.setattr(lifecycle,'native_binding_enabled',lambda:True)
    monkeypatch.setattr(lifecycle,'bind_execution',lambda root,record,pid,repo:{'relation':'DIRECT_CHILD','server':{'pid':9999,'created':1.01,'command':record['command'],'parent_pid':root.pid,'parent_created':record['created']}})
    calls=[]
    def refuse(*args):calls.append('write');raise OSError('synthetic private detail')
    monkeypatch.setattr(lifecycle,'save_execution_bindings',refuse)
    monkeypatch.setattr(lifecycle,'stop_record',lambda *args:'FOREIGN_REFUSED')
    with pytest.raises(lifecycle.BoundaryError) as error:lifecycle.start()
    row=diagnostic.parse(diagnostic.command('start',error.value),'start')
    assert calls==['write'] and row['category']=='OSError' and row['boundary_phase']=='process_record'
    assert row['start_observation']['attempts']==1 and row['start_observation']['other_errors']==0
    assert 'server' not in json.loads(lifecycle.STATE.read_text())['processes'][0]
    assert 'synthetic private detail' not in json.dumps(row)


@pytest.mark.parametrize('still_present',[True,False])
def test_absent_launcher_never_authorizes_orphan_termination(tmp_path,still_present):
    record={'pid':1,'server':{'pid':2}}
    orphan=SimpleNamespace(terminate=lambda:pytest.fail('orphan termination'))
    def factory(pid):
        if pid==1 or not still_present:raise ProcessLookupError()
        return orphan
    assert lifecycle.stop_record(record,tmp_path,factory)==('FOREIGN_REFUSED' if still_present else 'ABSENT')


@pytest.mark.parametrize('matched',[True,False])
def test_stop_holds_pins_and_verifies_chain_before_child_signal(tmp_path,monkeypatch,matched):
    import server_identity
    events=[];held=set()
    class Pin:
        def __init__(self,pid,*args):self.pid=pid
        def __enter__(self):held.add(self.pid);return self
        def __exit__(self,*args):held.remove(self.pid)
        alive=True
        def verify(self,**kwargs):assert self.pid in held
    monkeypatch.setattr(server_identity,'PinnedProcess',Pin)
    monkeypatch.setattr(lifecycle,'identify_process',lambda *args:True)
    monkeypatch.setattr(lifecycle,'saved_child_matches',lambda *args:matched)
    def stop_root():
        assert held=={1,2};events.append('root-stop')
    root=SimpleNamespace(terminate=stop_root,wait=lambda **kw:events.append('root-wait'))
    def stop_child():
        assert held=={1,2};events.append('child-stop')
    child=SimpleNamespace(terminate=stop_child,wait=lambda **kw:events.append('child-wait'))
    record={'pid':1,'created':1,'server':{'pid':2,'created':1.01}}
    result=lifecycle.stop_record(record,tmp_path,lambda pid:root if pid==1 else child)
    assert result==('STOPPED' if matched else 'FOREIGN_REFUSED') and not held
    assert events==(['child-stop','child-wait','root-stop','root-wait'] if matched else [])


def test_relation_projection_is_typed_and_does_not_expose_pid(tmp_path,monkeypatch,capsys):
    prepare_start(tmp_path,monkeypatch,'SUCCESS');lifecycle.start()
    obs=diagnostic.parse(capsys.readouterr().out,'start')['start_observation']
    good={**obs,'server_relation':'ROOT','server_pid_valid':True}
    assert diagnostic.start_observation(good)==good
    for bad in [dict(good,server_relation='any descendant'),dict(good,server_pid_valid=901),dict(good,server_pid=901),dict(good,process_matches=False)]:
        with pytest.raises(ValueError):diagnostic.start_observation(bad)


@pytest.mark.parametrize('relation',['NONE','UNIQUE','AMBIGUOUS','REFUSED'])
def test_native_root_paths_pin_until_signal_and_bound_failure_children(tmp_path,monkeypatch,relation):
    import psutil,server_identity
    held=set();signals=[]
    class Pin:
        alive=True
        def __init__(self,pid,*args):self.pid=pid
        def __enter__(self):held.add(self.pid);return self
        def __exit__(self,*args):held.remove(self.pid)
        def verify(self,**kwargs):assert self.pid in held
    class Process:
        def __init__(self,pid):self.pid=pid
        def children(self,recursive=False):
            assert recursive is False
            return [] if relation=='NONE' else [Process(2),Process(3)] if relation=='AMBIGUOUS' else [Process(2)]
        def terminate(self):
            assert 1 in held and (self.pid==1 or self.pid in held);signals.append(self.pid)
        def wait(self,**kwargs):assert 1 in held
    monkeypatch.setattr(psutil,'Process',Process)
    monkeypatch.setattr(server_identity,'PinnedProcess',Pin)
    monkeypatch.setattr(lifecycle,'native_binding_enabled',lambda:True)
    monkeypatch.setattr(lifecycle,'identify_process',lambda *args:True)
    monkeypatch.setattr(lifecycle,'saved_child_matches',lambda *args:True)
    monkeypatch.setattr(lifecycle,'bind_execution',lambda *args:{'relation':'REFUSED' if relation=='REFUSED' else 'DIRECT_CHILD','server':{'pid':2,'created':1.01}})
    result=lifecycle.stop_record({'pid':1,'created':1},tmp_path,Process)
    assert result==('STOPPED' if relation in ('NONE','UNIQUE') else 'FOREIGN_REFUSED')
    assert signals==([] if relation in ('AMBIGUOUS','REFUSED') else [1] if relation=='NONE' else [2,1])
    assert not held
