"""Injected contracts; Linux results are not native Windows evidence."""
import importlib.util
import os
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('server_identity_contract', Path(__file__).resolve().parents[1] / 'scripts/windows/server_identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class Process:
    def __init__(self, pid, created, repo, command, parent=1):
        self.pid, self.created, self.repo, self.command, self.parent = pid, created, str(repo), list(command), parent
        self.reads = 0
        self.mutate = None
    def create_time(self):
        self.reads += 1
        if self.mutate and self.reads == 3:
            self.mutate(self)
        return self.created
    def cwd(self): return self.repo
    def cmdline(self): return self.command
    def ppid(self): return self.parent
    def exe(self): return getattr(self, "image", self.command[0])


class Backend:
    def __init__(self, processes):
        self.processes = processes
        self.opened, self.closed = [], []
        self.borrowed = None
        self.overrides = {}
        self.fail_open = None
        self.fail_close = False
        self.fail_identity = None
    def creation_handle(self, root): return self.borrowed
    def open(self, pid):
        if pid == self.fail_open: raise RuntimeError('PRIVATE')
        handle = ('owned', pid)
        self.opened.append(handle)
        return handle
    def identity(self, handle):
        if handle == self.fail_identity: raise RuntimeError('PRIVATE')
        pid = handle[1]
        p = self.processes[pid]
        return self.overrides.get(handle, (pid, p.created, True))
    def close(self, handle):
        self.closed.append(handle)
        if self.fail_close: raise RuntimeError('PRIVATE')


def setup(tmp_path):
    command = [str(tmp_path / '.venv-windows/Scripts/python.exe'), '-m', 'uvicorn', 'parkweave.api:configured_app', '--factory', '--host', '127.0.0.1', '--port', '8765']
    root = Process(101, 100., tmp_path, command)
    child = Process(102, 101., tmp_path, command, parent=101)
    processes = {101: root, 102: child}
    backend = Backend(processes)
    record = {'pid': 101, 'created': 100., 'command': command}
    # Mirrors lifecycle's unchanged command/cwd/time policy; the binding adds
    # direct-parent, time interval, kernel identity and repeated snapshots.
    def identify(proc, rec, repo):
        return rec['command'] == command and abs(proc.create_time()-rec['created']) < .01 and proc.cwd() == str(repo.resolve()) and proc.cmdline() == rec['command']
    def bind(pid=102):
        return identity.bind_server(root, record, pid, tmp_path, identify=identify, process_factory=processes.__getitem__, backend=backend, clock=lambda: 110.)
    return root, child, record, backend, bind


def test_direct_child_has_private_record_and_closes_both_owned_handles(tmp_path):
    root, child, record, backend, bind = setup(tmp_path)
    result = bind()
    assert result == {'relation': 'DIRECT_CHILD', 'server': {'pid': 102, 'created': 101., 'command': record['command'], 'parent_pid': 101, 'parent_created': 100.}}
    assert backend.closed == [('owned', 102), ('owned', 101)]


def test_root_pid_retains_exact_root_relation(tmp_path):
    root, child, record, backend, bind = setup(tmp_path)
    assert bind(101) == {'relation': 'ROOT', 'server': None}
    assert backend.opened == backend.closed == [('owned', 101)]


def test_root_reuse_inside_legacy_ten_millisecond_window_is_refused(tmp_path):
    root, child, record, backend, bind = setup(tmp_path)
    root.created += .001
    assert bind()['relation'] == 'REFUSED'
    assert not backend.opened


@pytest.mark.parametrize('pid', [True, False, 0, -1, '102', 102., None, 0x100000000])
def test_invalid_health_pid_never_opens_process(tmp_path, pid):
    *_, backend, bind = setup(tmp_path)
    assert bind(pid) == {'relation': 'REFUSED', 'server': None,'identity_refusal':{'stage':'ROOT_POLICY','reason':'POLICY_REFUSED'}}
    assert not backend.opened


@pytest.mark.parametrize('field,value', [('command',['foreign']), ('repo','foreign'), ('parent',999), ('created',99.), ('created',111.)])
def test_foreign_child_or_creation_interval_is_refused(tmp_path, field, value):
    root, child, record, backend, bind = setup(tmp_path)
    setattr(child, field, value)
    assert bind()['relation'] == 'REFUSED'
    assert backend.closed == backend.opened


def test_child_created_after_sixty_second_launch_window_is_refused(tmp_path):
    root, child, record, backend, bind = setup(tmp_path)
    child.created = 161.
    result = identity.bind_server(root, record, 102, tmp_path, identify=lambda *args: True,
                                 process_factory=lambda _: child, backend=backend, clock=lambda: 200.)
    assert result['relation'] == 'REFUSED'
    assert backend.closed == backend.opened


@pytest.mark.parametrize('target,field,value', [('root','created',101.), ('root','command',['foreign']), ('child','created',102.), ('child','parent',999), ('child','repo','foreign'), ('child','command',['foreign'])])
def test_identity_changes_between_snapshots_are_refused(tmp_path, target, field, value):
    root, child, record, backend, bind = setup(tmp_path)
    p = root if target == 'root' else child
    p.mutate = lambda process: setattr(process, field, value)
    assert bind()['relation'] == 'REFUSED'
    assert backend.closed == backend.opened[::-1]


@pytest.mark.parametrize('handle,observation', [(('owned',101),(999,100.,True)), (('owned',101),(101,100.01,True)), (('owned',101),(101,100.,False)), (('owned',102),(102,101.01,True)), (('owned',102),(102,101.,False))])
def test_kernel_pid_creation_and_liveness_must_match(tmp_path, handle, observation):
    *_, backend, bind = setup(tmp_path)
    backend.overrides[handle] = observation
    assert bind()['relation'] == 'REFUSED'
    assert sorted(backend.closed) == sorted(backend.opened)


def test_borrowed_creation_handle_is_verified_but_never_closed(tmp_path):
    *_, backend, bind = setup(tmp_path)
    backend.borrowed = ('borrowed',101)
    assert bind()['relation'] == 'DIRECT_CHILD'
    assert backend.borrowed not in backend.closed
    backend.overrides[backend.borrowed] = (101,99.,True)
    backend.opened.clear();backend.closed.clear()
    assert bind()['relation'] == 'REFUSED'
    assert not backend.opened and not backend.closed


@pytest.mark.parametrize('failure', ['open', 'identity', 'close', 'missing_creation_handle'])
def test_backend_failures_are_constant_and_release_owned_handles(tmp_path, failure):
    *_, backend, bind = setup(tmp_path)
    if failure == 'open': backend.fail_open = 102
    if failure == 'identity': backend.fail_identity = ('owned',102)
    if failure == 'close': backend.fail_close = True
    if failure == 'missing_creation_handle':
        def refused(root): raise AttributeError('PRIVATE')
        backend.creation_handle = refused
    result=bind()
    expected={'open':('CHILD_PIN','OPEN_FAILED'),'identity':('CHILD_PIN','READ_FAILED'),'close':('CLOSE','CLOSE_FAILED'),'missing_creation_handle':('BORROWED','UNAVAILABLE')}[failure]
    assert result == {'relation':'REFUSED','server':None,'identity_refusal':dict(zip(('stage','reason'),expected))}
    assert sorted(backend.closed) == sorted(backend.opened)


def test_pinned_context_holds_handle_for_caller_operation(tmp_path):
    *_, backend, bind = setup(tmp_path)
    with identity.PinnedProcess(101,100.,backend) as pinned:
        pinned.verify()
        assert backend.closed == []
    assert backend.closed == [('owned',101)]


def test_default_pin_reverification_refuses_dead_but_explicit_mode_confirms_exit(tmp_path):
    *_, backend, bind = setup(tmp_path)
    with identity.PinnedProcess(101,100.,backend) as pinned:
        backend.overrides[('owned',101)] = (101,100.,False)
        with pytest.raises(identity.IdentityRefused): pinned.verify()
        assert pinned.alive is None
        assert pinned.verify(require_live=False) is pinned and pinned.alive is False
        assert backend.closed == []
    assert backend.closed == [('owned',101)]


@pytest.mark.parametrize('observation', [(999,100.,False),(101,100.001,False),(101,100.,None),(101,100.,0)])
def test_nonlive_pin_verification_still_refuses_reuse_and_unknown_status(tmp_path,observation):
    *_, backend, bind = setup(tmp_path)
    with identity.PinnedProcess(101,100.,backend) as pinned:
        backend.overrides[('owned',101)] = observation
        with pytest.raises(identity.IdentityRefused): pinned.verify(require_live=False)
        assert pinned.alive is None


@pytest.mark.parametrize('difference,accepted', [(0.000009,True),(0.000011,False)])
def test_kernel_time_ten_microsecond_tolerance_boundary(tmp_path,difference,accepted):
    *_, backend, bind = setup(tmp_path)
    assert identity.KERNEL_TIME_TOLERANCE == .000010
    backend.overrides[('owned',101)] = (101,100.+difference,True)
    assert (bind()['relation'] == 'DIRECT_CHILD') is accepted
    assert sorted(backend.closed) == sorted(backend.opened)


def test_interruption_during_enter_releases_exact_handle(tmp_path):
    *_, backend, bind = setup(tmp_path)
    def interrupted(handle): raise KeyboardInterrupt()
    backend.identity = interrupted
    with pytest.raises(KeyboardInterrupt):
        with identity.PinnedProcess(101,100.,backend): pass
    assert backend.closed == [('owned',101)]


@pytest.mark.skipif(os.name != 'nt', reason='NOT_RUN: Windows read-only kernel handle validation')
def test_native_windows_query_current_process_handle_only():
    import psutil
    current = psutil.Process()
    with identity.PinnedProcess(current.pid,current.create_time()) as pinned:
        pinned.verify()


@pytest.mark.skipif(os.name != 'nt', reason='NOT_RUN: Windows actual Popen borrowed handle validation')
def test_native_windows_popen_binding_preserves_borrowed_creation_handle(tmp_path):
    import psutil,subprocess,sys
    root = psutil.Popen([sys.executable,'-c','import sys; sys.stdin.read(1)'],
                        cwd=tmp_path,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        backend = identity.WindowsBackend()
        borrowed = backend.creation_handle(root)
        record = {'pid':root.pid,'created':root.create_time(),'command':root.cmdline()}
        def identify(process,stored,repo):
            return process.pid==stored['pid'] and abs(process.create_time()-stored['created'])<.01 and process.cwd()==str(repo.resolve()) and process.cmdline()==stored['command']
        result = identity.bind_server(root,record,root.pid,tmp_path,identify=identify,backend=backend)
        assert result == {'relation':'ROOT','server':None}
        pid,created,alive = backend.identity(borrowed)
        assert pid==root.pid and alive is True
        assert abs(created-record['created']) <= identity.KERNEL_TIME_TOLERANCE
    finally:
        # EOF releases the synthetic program, including a possible redirector's
        # child, without expanding termination to any discovered process.
        root.stdin.close()
        root.wait(timeout=10)


@pytest.mark.parametrize('field,value,stage,reason', [('command',['foreign'],'CHILD_POLICY','ARGV0_MISMATCH'),('parent',999,'CHILD_SNAPSHOT','PARENT_MISMATCH'),('created',111.,'CHILD_SNAPSHOT','CREATION_WINDOW_REFUSED')])
def test_refusal_branch_is_fixed_without_process_or_private_error_content(tmp_path,field,value,stage,reason):
    root, child, record, backend, bind = setup(tmp_path)
    setattr(child,field,value)
    result=bind()
    assert result['identity_refusal']=={'stage':stage,'reason':reason}
    assert set(result)=={'relation','server','identity_refusal'} and result['server'] is None
    assert str(tmp_path) not in repr(result) and 'PRIVATE' not in repr(result)


@pytest.mark.parametrize('observation,reason', [( (999,100.,True),'PID_MISMATCH'),((101,100.01,True),'CTIME_MISMATCH'),((101,100.,False),'NOT_LIVE'),((101,100.,None),'READ_FAILED')])
def test_pin_fixed_reason_and_close_failure_preserve_original_refusal(tmp_path,observation,reason):
    *_, backend, bind = setup(tmp_path)
    backend.overrides[('owned',101)]=observation;backend.fail_close=True
    result=bind()
    assert result['identity_refusal']=={'stage':'ROOT_PIN','reason':reason}
    assert backend.closed==[('owned',101)]


def test_close_failure_after_body_refusal_preserves_primary_branch(tmp_path):
    root, child, record, backend, bind = setup(tmp_path)
    child.parent=999;backend.fail_close=True
    assert bind()['identity_refusal']=={'stage':'CHILD_SNAPSHOT','reason':'PARENT_MISMATCH'}
    assert backend.closed==[('owned',101)]


def test_borrowed_unknown_liveness_is_read_failure_not_confirmed_exit(tmp_path):
    *_, backend, bind = setup(tmp_path)
    backend.borrowed=('borrowed',101)
    backend.overrides[backend.borrowed]=(101,100.,None)
    assert bind()['identity_refusal']=={'stage':'BORROWED','reason':'READ_FAILED'}
    assert not backend.opened and not backend.closed


@pytest.mark.parametrize('field,value,reason',[('repo','PRIVATE','CWD_MISMATCH'),('command',['PRIVATE'],'ARGV0_MISMATCH'),('command',[],'COMMAND_MISMATCH')])
def test_child_policy_observes_fixed_difference_without_relaxing_identity(tmp_path,field,value,reason):
    root,child,record,backend,bind=setup(tmp_path)
    setattr(child,field,value)
    assert bind()=={'relation':'REFUSED','server':None,'identity_refusal':{'stage':'CHILD_POLICY','reason':reason}}
    assert backend.closed==[('owned',root.pid)] and not any(handle[1]==child.pid for handle in backend.opened)


def test_child_command_tail_difference_remains_refused(tmp_path):
    root,child,record,backend,bind=setup(tmp_path)
    child.command[-1]='8999'
    assert bind()['identity_refusal']=={'stage':'CHILD_POLICY','reason':'COMMAND_TAIL_MISMATCH'}


@pytest.fixture
def redirector(tmp_path):
    from types import SimpleNamespace
    root, child, record, backend, _ = setup(tmp_path)
    managed=tmp_path/'.venv-windows/Scripts/python.exe'
    managed.parent.mkdir(parents=True);managed.write_bytes(b'SYNTHETIC')
    base=tmp_path/'base/python.exe';base.parent.mkdir();base.write_bytes(b'SYNTHETIC')
    cfg=tmp_path/'.venv-windows/pyvenv.cfg'
    cfg.write_text('home = '+str(base.parent)+'\nexecutable = '+str(base)+'\n')
    runtime=SimpleNamespace(executable=str(managed),prefix=str(managed.parent.parent),base_prefix=str(base.parent),_base_executable=str(base))
    authority=lambda command,repo:identity.redirector_authority(command,repo,runtime)
    child.command=[str(base),*record['command'][1:]]
    def identify(p,rec,repo):
        return rec['command']==record['command'] and not abs(p.create_time()-rec['created'])>=.01 and p.cwd()==str(repo) and p.cmdline()==rec['command']
    def bind():
        return identity.bind_server(root,record,child.pid,tmp_path,identify=identify,process_factory={101:root,102:child}.__getitem__,backend=backend,clock=lambda:110.,command_authority=authority)
    return root,child,record,backend,runtime,cfg,bind


def test_redirector_accepts_only_managed_runtime_exact_base_image_and_tail(redirector):
    root,child,record,backend,runtime,cfg,bind=redirector
    before=identity.bind_server(root,record,child.pid,Path(root.repo),identify=lambda p,rec,repo:p.cmdline()==rec['command'],process_factory={101:root,102:child}.__getitem__,backend=backend,clock=lambda:110.)
    assert before['identity_refusal']=={'stage':'CHILD_POLICY','reason':'ARGV0_MISMATCH'}
    backend.opened.clear();backend.closed.clear()
    result=bind()
    assert result['relation']=='DIRECT_CHILD'
    assert result['server']['command']==child.command
    assert result['server']['launcher_command']==record['command']
    assert result['server']['base_executable']==runtime._base_executable
    assert backend.closed==[('owned',102),('owned',101)]
    # The saved identity is re-derived, never trusted after authority drift.
    cfg.write_text('home = '+str(cfg.parent)+'\n')
    assert bind()['relation']=='REFUSED'


@pytest.mark.parametrize('field,value',[
 ('executable','python.exe'),('prefix','/foreign'),('base_prefix','/foreign'),
 ('_base_executable','python.exe'),('_base_executable','/missing/python.exe')])
def test_redirector_authority_refuses_runtime_drift(redirector,field,value):
    *_,runtime,cfg,bind=redirector
    setattr(runtime,field,value)
    result=bind();assert result['relation']=='REFUSED'
    assert result['identity_refusal']['reason']=='TRUSTED_COMMAND_REFUSED'


@pytest.mark.parametrize('fault',['other_python','tail_port','tail_added','tail_missing','image','relative_image','cwd','parent','late','nan','inf','nonfile','duplicate_home','cfg_executable','authority_recheck'])
def test_redirector_rejects_spoofed_identity_and_changed_authority(redirector,fault):
    root,child,record,backend,runtime,cfg,bind=redirector
    if fault=='other_python':child.command[0]=str(cfg.parent/'other/python.exe')
    elif fault=='tail_port':child.command[-1]='8766'
    elif fault=='tail_added':child.command.append('--foreign')
    elif fault=='tail_missing':child.command.pop()
    elif fault=='image':child.image=record['command'][0]
    elif fault=='relative_image':child.image='python.exe'
    elif fault=='cwd':child.repo='foreign'
    elif fault=='parent':child.parent=999
    elif fault=='late':child.created=161.
    elif fault in ('nan','inf'):child.created=float(fault)
    elif fault=='nonfile':Path(runtime._base_executable).unlink();Path(runtime._base_executable).mkdir()
    elif fault=='duplicate_home':cfg.write_text(cfg.read_text()+'home = '+runtime.base_prefix+'\n')
    elif fault=='cfg_executable':cfg.write_text('home = '+runtime.base_prefix+'\nexecutable = '+record['command'][0]+'\n')
    elif fault=='authority_recheck':child.mutate=lambda p:cfg.write_text('home = foreign\n')
    result=bind();assert result['relation']=='REFUSED' and result['server'] is None
    assert backend.closed==list(reversed(backend.opened))


@pytest.mark.parametrize('drift',[False,True])
def test_stop_rederives_redirector_record_before_any_signal(redirector,monkeypatch,drift):
    from test_lifecycle import lifecycle
    import server_identity
    root,child,record,backend,runtime,cfg,bind=redirector
    bound=bind();assert bound['relation']=='DIRECT_CHILD'
    record={**record,'server':bound['server']};signals=[]
    root.terminate=lambda:signals.append('root');root.wait=lambda **kwargs:None
    child.terminate=lambda:signals.append('child');child.wait=lambda **kwargs:None
    monkeypatch.setattr(server_identity,'PinnedProcess',lambda pid,created:identity.PinnedProcess(pid,created,backend))
    monkeypatch.setattr(lifecycle,'bind_execution',lambda *args:bind())
    if drift:cfg.write_text('home = foreign\n')
    result=lifecycle.stop_record(record,Path(root.repo),{101:root,102:child}.__getitem__)
    assert result==('FOREIGN_REFUSED' if drift else 'STOPPED')
    assert signals==([] if drift else ['child','root'])


@pytest.mark.parametrize('created',[float('nan'),float('inf'),'invalid'])
def test_redirector_dynamic_creation_read_never_bypasses_child_policy(redirector,created):
    root,child,record,backend,runtime,cfg,bind=redirector
    original=child.create_time
    def read():
        value=original()
        return created if child.reads==2 else value
    child.create_time=read
    result=bind()
    assert result['identity_refusal']=={'stage':'CHILD_POLICY','reason':'READ_FAILED' if isinstance(created,str) else 'CTIME_MISMATCH'}
    assert result['relation']=='REFUSED' and backend.closed==[('owned',101)]
