"""Owner-only synthetic session creation; native cases separate from fake contracts."""
import io
import os
from pathlib import Path
import pytest
from parkweave.synthetic_session_file import create_synthetic_session_file,SessionOwnerError

class Backend:
    def __init__(self,fail=None,changed=False):self.events=[];self.fail=fail;self.changed=changed;self.n=0
    def event(self,name):
        self.events.append(name)
        if self.fail==name:raise SessionOwnerError('SYNTHETIC_REFUSAL')
    def current_user(self):self.event('current_user');return object(),'current_sid'
    def create(self,path):self.event('create_new');return 'exact_handle'
    def inspect(self,handle):
        assert handle=='exact_handle';self.n+=1;self.event('inspect'+str(self.n))
        return 'descriptor'+str(self.n),'current_sid',b'DACL_CHANGED' if self.changed and self.n==2 else b'DACL',0x8004|(1 if self.n==1 else 0)
    def set_owner(self,handle,sid):assert (handle,sid)==('exact_handle','current_sid');self.event('owner_only')
    def verify_owner(self,owner,sid):assert owner==sid;self.event('verify_owner')
    def transfer_fd(self,handle):self.event('transfer');return 77
    def text_file(self,fd):assert fd==77;return io.StringIO()
    def release_descriptor(self,descriptor):self.events.append('free_'+descriptor)
    def close(self,handle):assert handle=='exact_handle';self.events.append('close_exact')

def test_session_owner_verified_with_unchanged_dacl_before_stream_transfer():
    backend=Backend();stream=create_synthetic_session_file('.runtime/synthetic-sessions.json',_backend=backend)
    assert stream.getvalue()==''
    assert backend.events==['current_user','create_new','inspect1','owner_only','inspect2','verify_owner','transfer','free_descriptor2','free_descriptor1']

@pytest.mark.parametrize('fail',['current_user','create_new','inspect1','owner_only','inspect2','verify_owner','transfer'])
def test_session_owner_failure_never_exposes_token_stream_or_reopens(fail):
    backend=Backend(fail=fail)
    with pytest.raises(SessionOwnerError):create_synthetic_session_file('.runtime/synthetic-sessions.json',_backend=backend)
    assert backend.events.count('create_new')<=1
    if fail not in ('current_user','create_new'):assert backend.events[-1]=='close_exact'
    if fail!='transfer':assert 'transfer' not in backend.events

def test_session_dacl_difference_refused_before_any_token_write():
    backend=Backend(changed=True)
    with pytest.raises(SessionOwnerError,match='SESSION_PERMISSIONS_CHANGED'):create_synthetic_session_file('.runtime/synthetic-sessions.json',_backend=backend)
    assert 'transfer' not in backend.events and backend.events[-1]=='close_exact'

def test_session_other_path_refused_before_backend_access():
    backend=Backend()
    with pytest.raises(ValueError):create_synthetic_session_file('.runtime/windows-config.json',_backend=backend)
    assert not backend.events

@pytest.mark.skipif(os.name!='nt',reason='native Windows owner-only verification required')
def test_native_session_owner_matches_current_user_and_existing_bytes_protected(tmp_path,monkeypatch):
    from parkweave.synthetic_session_file import WindowsSessionFile
    monkeypatch.chdir(tmp_path);Path('.runtime').mkdir()
    with create_synthetic_session_file('.runtime/synthetic-sessions.json') as stream:stream.write('SYNTHETIC_ONLY')
    path=Path('.runtime/synthetic-sessions.json');before=path.read_bytes()
    with pytest.raises(FileExistsError):create_synthetic_session_file(path)
    assert path.read_bytes()==before

@pytest.mark.parametrize('close_refused',[False,True])
def test_session_crt_transfer_then_text_wrap_failure_closes_fd_once_without_handle_close(monkeypatch,close_refused):
    import sys
    from types import SimpleNamespace
    import parkweave.synthetic_session_file as module
    closed=[]
    monkeypatch.setitem(sys.modules,'msvcrt',SimpleNamespace(open_osfhandle=lambda handle,flags:77))
    def refuse(*args,**kwargs):raise OSError('SYNTHETIC_WRAP_REFUSED')
    def close(fd):
        closed.append(fd)
        if close_refused:raise OSError('SYNTHETIC_CLOSE_REFUSED')
    monkeypatch.setattr(module,'os',SimpleNamespace(O_WRONLY=1,O_TEXT=0,fdopen=refuse,close=close))
    class Transferred(Backend):
        def transfer_fd(self,handle):return module.WindowsSessionFile.transfer_fd(self,handle)
        def text_file(self,fd):return module.WindowsSessionFile.text_file(self,fd)
    backend=Transferred()
    with pytest.raises(OSError):module.create_synthetic_session_file('.runtime/synthetic-sessions.json',_backend=backend)
    assert closed==[77] and 'close_exact' not in backend.events
    assert backend.events[-2:]==['free_descriptor2','free_descriptor1']


@pytest.mark.parametrize('kind',['file','directory','link'])
def test_windows_existing_path_refused_before_owner_handle_without_mutation(tmp_path,kind):
    from types import SimpleNamespace
    from parkweave.synthetic_session_file import WindowsSessionFile
    path=tmp_path/'existing';target=tmp_path/'target';target.write_bytes(b'SYNTHETIC_PROTECTED')
    if kind=='file':path.write_bytes(b'SYNTHETIC_PROTECTED')
    elif kind=='directory':path.mkdir()
    else:
        try:path.symlink_to(target)
        except OSError:pytest.skip('symlink creation unavailable')
    before=path.lstat();calls=[];backend=WindowsSessionFile.__new__(WindowsSessionFile)
    backend.k=SimpleNamespace(CreateFileW=lambda *args:calls.append(args))
    with pytest.raises(FileExistsError):backend.create(path)
    after=path.lstat()
    assert not calls and (after.st_mode,after.st_ino)==(before.st_mode,before.st_ino)
    assert target.read_bytes()==b'SYNTHETIC_PROTECTED'
    if kind=='file':assert path.read_bytes()==b'SYNTHETIC_PROTECTED'


@pytest.mark.parametrize('code,expected',[(80,FileExistsError),(183,FileExistsError),(5,SessionOwnerError),(32,SessionOwnerError)])
def test_windows_create_new_race_and_denial_keep_distinct_gold(tmp_path,monkeypatch,code,expected):
    from types import SimpleNamespace
    import parkweave.synthetic_session_file as module
    backend=module.WindowsSessionFile.__new__(module.WindowsSessionFile);calls=[]
    def create(*args):calls.append(args);return module.ctypes.c_void_p(-1).value
    backend.k=SimpleNamespace(CreateFileW=create)
    monkeypatch.setattr(module.ctypes,'get_last_error',lambda:code,raising=False)
    with pytest.raises(expected):backend.create(tmp_path/'absent')
    assert len(calls)==1 and calls[0][4]==1 and calls[0][2]==0


@pytest.mark.parametrize('bit',[0x400,0x1000,0x10])
def test_owner_control_change_refused_with_verified_owner_and_same_dacl(bit):
    class ChangedControl(Backend):
        def inspect(self,handle):
            descriptor,owner,acl,control=super().inspect(handle)
            return descriptor,owner,acl,control^(bit if self.n==2 else 0)
    backend=ChangedControl()
    with pytest.raises(SessionOwnerError,match='SESSION_PERMISSIONS_CHANGED'):
        create_synthetic_session_file('.runtime/synthetic-sessions.json',_backend=backend)
    assert 'verify_owner' in backend.events and 'transfer' not in backend.events
    assert backend.events[-1]=='close_exact'


def test_native_owner_pause_refuses_before_backend_or_create(monkeypatch):
    from types import SimpleNamespace
    import parkweave.synthetic_session_file as module
    calls=[]
    monkeypatch.setattr(module,'os',SimpleNamespace(name='nt'))
    monkeypatch.setattr(module,'WindowsSessionFile',lambda:calls.append('construct'))
    with pytest.raises(module.SessionOwnerError,match='OWNER_MUTATION_PAUSED'):
        module.create_synthetic_session_file('.runtime/synthetic-sessions.json')
    fixed=Path(module.__file__).resolve().parents[2]/'.runtime/windows-config.json'
    with pytest.raises(module.SessionOwnerError,match='OWNER_MUTATION_PAUSED'):
        module.create_synthetic_config_file(fixed)
    assert calls==[]


def test_native_owner_direct_setter_pause_never_calls_security_api():
    from types import SimpleNamespace
    import parkweave.synthetic_session_file as module
    calls=[];backend=module.WindowsSessionFile.__new__(module.WindowsSessionFile)
    backend.a=SimpleNamespace(SetSecurityInfo=lambda *args:calls.append(args))
    with pytest.raises(module.SessionOwnerError,match='OWNER_MUTATION_PAUSED'):backend.set_owner(1,2)
    assert not calls
    with pytest.raises(module.SessionOwnerError,match='OWNER_MUTATION_PAUSED'):
        module.create_synthetic_session_file('.runtime/synthetic-sessions.json',_backend=backend)
    assert not calls


@pytest.mark.parametrize('change',['SLACK','CAPACITY','RESERVED','ACE_MASK','ACE_TYPE','ACE_FLAGS','ACE_ORDER','NULL_EMPTY','CONTROL'])
def test_owner_readonly_acl_difference_never_relaxes_original_contract(change):
    import struct
    from scripts.windows.owner_descriptor_observation import compare_acl_control
    def acl(aces,slack=b'',reserved=0):return struct.pack('<BBHHH',2,reserved,8+sum(map(len,aces))+len(slack),len(aces),0)+b''.join(aces)+slack
    first=bytes((0,0,8,0,1,0,0,0));second=bytes((1,0,8,0,2,0,0,0))
    before=acl([first,second]);after=before;control=0x8004
    if change=='SLACK':before=acl([first,second],b'AAAA');after=acl([first,second],b'BBBB')
    elif change=='CAPACITY':after=acl([first,second],b'AAAA')
    elif change=='RESERVED':after=acl([first,second],reserved=1)
    elif change.startswith('ACE_'):
        updated=bytearray(first);updated[{'ACE_MASK':4,'ACE_TYPE':0,'ACE_FLAGS':1}.get(change,4)]^=1
        after=acl([second,first] if change=='ACE_ORDER' else [bytes(updated),second])
    elif change=='NULL_EMPTY':before=None;after=acl([])
    elif change=='CONTROL':control^=0x400
    result=compare_acl_control(before,0x8004,after,control)
    assert result['strict_contract']=='REFUSED' and result['semantic_permission_change']=='UNKNOWN'
    if change in ('SLACK','CAPACITY','RESERVED'):assert result['ordered_ace_bytes']=='EQUAL'
    if change.startswith('ACE_'):assert result['ordered_ace_bytes']=='DIFFERENT'
    if change=='CONTROL':assert result['control_changed_bits']==['DACL_AUTO_INHERITED']
    assert result['sacl_content']=='NOT_QUERIED'


@pytest.mark.parametrize('invalid',[b'',b'12345678',b'\x02\x00\x08\x00\x01\x00\x00\x00',b'\x02\x00\x0c\x00\x01\x00\x00\x00\x00\x00\x00\x00'])
def test_owner_readonly_invalid_acl_is_unavailable(invalid):
    from scripts.windows.owner_descriptor_observation import compare_acl_control
    row=compare_acl_control(invalid,0x8004,invalid,0x8004)
    assert row['acl_observation']=='UNAVAILABLE' and row['strict_contract']=='REFUSED'
