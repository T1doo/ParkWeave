"""Real owned POSIX directories/files + completion algorithm protocol.

The inspection seam observes actual POSIX identities/modes/metadata. It does
not assert Windows ACL/SID facts or issue a native runtime/acceptance capability.
"""
from dataclasses import replace
from hashlib import sha256
import json,os,stat
from pathlib import Path

import pytest
from types import SimpleNamespace

from parkweave.windows_files import Info
from scripts.windows_portable import native_runtime_staging as runtime,endpoint_plan
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
from scripts.windows_portable.fixed_journal import FixedFormat
from scripts.windows_portable.fixed_secret_store import _under_lease
from scripts.windows_portable.controller import CandidateRefused,ControlFailure
from scripts.windows_ci import native_business_entry as entry,native_failure_diagnostics as diagnostics


@pytest.fixture
def tree(tmp_path):
    lease=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2).claim_fresh(str(tmp_path/'owned'))
    value=object.__new__(runtime.NativeRuntimeInstallation)
    value.lease=lease;value.key=_under_lease(lease,lambda:endpoint_plan._key_held(lease))
    value.rows={};value.dest={'':lease.fs.root};value.identities=set();value.directories=('app','app/child')
    value._created_directory_rows={};value._completion_pending=True;value._copy_complete=False
    value.failed=value.closed=False;value._gate=lease._verify
    handles=[];overrides={};security_overrides={}
    def path(h):return os.readlink('/proc/self/fd/'+str(h)).replace('/','\\')
    value.root_path=path(lease.fs.root)
    def observe(h,directory,**kw):
        info=os.fstat(h)
        assert info.st_uid==os.geteuid() and not stat.S_IMODE(info.st_mode)&0o077
        actual_directory=stat.S_ISDIR(info.st_mode)
        assert actual_directory==directory and (directory or stat.S_ISREG(info.st_mode))
        native_shape=Info(0x10 if directory else 0x80,info.st_size,info.st_nlink,info.st_dev,info.st_ino)
        native_shape=overrides.get(h,native_shape)
        if native_shape.attributes&(0x400|0x40|0x1000|0x40000|0x400000) or bool(native_shape.attributes&0x10)!=directory:
            raise CandidateRefused('CONTROLLED_UNSAFE_METADATA')
        descriptor=security_overrides.get(h,(info.st_uid,stat.S_IMODE(info.st_mode)))
        return native_shape,descriptor,path(h)
    value._inspect=observe
    def entries(h):
        result=[]
        for name in os.listdir(h):
            actual=os.stat(name,dir_fd=h,follow_symlinks=False)
            attrs=0x10 if stat.S_ISDIR(actual.st_mode) else 0x80
            pinned=next((owned for owned in handles if os.fstat(owned).st_ino==actual.st_ino),None)
            if pinned in overrides:attrs=overrides[pinned].attributes
            result.append((name,attrs,actual.st_ino))
        return tuple(result)
    value._entries=entries
    root=tmp_path/'owned'
    os.mkdir('app',0o700,dir_fd=lease.fs.root)
    app=os.open('app',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=lease.fs.root);handles.append(app)
    value.dest['app']=app;value._record('app',app,True)
    empty=value.rows['app'][2]
    os.mkdir('child',0o700,dir_fd=app)
    child=os.open('child',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=app);handles.append(child)
    value.dest['app/child']=child;value._record('app/child',child,True)
    writer=os.open('data.txt',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=child)
    try:
        assert os.write(writer,b'abc')==3;os.fsync(writer)
        assert os.pread(writer,3,0)==b'abc'
    finally:os.close(writer)
    pin=os.open('data.txt',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=child);handles.append(pin)
    value.files=(('app/child/data.txt',3,sha256(b'abc').hexdigest()),)
    value._record('app/child/data.txt',pin,False);value._copy_complete=True
    yield value,root,empty,overrides,security_overrides
    runtime._issued.pop(value,None)
    for h in reversed(handles):os.close(h)
    if lease.active:lease.release()


def test_real_empty_directory_changes_when_its_own_children_are_created_then_seals_once(tree):
    value,root,empty,_,_=tree
    actual=value._inspect(value.dest['app'],True)
    assert empty!=actual and {'SIZE','LINKS'}&set(runtime.metadata_changes(empty,actual))
    file_before=value.rows['app/child/data.txt']
    _under_lease(value.lease,value._seal_new_directories)
    assert value.rows['app'][2]==actual and value.rows['app/child/data.txt']==file_before
    assert not value._completion_pending and value not in runtime._issued
    _under_lease(value.lease,value.verify)
    with pytest.raises(CandidateRefused):_under_lease(value.lease,value._seal_new_directories)
    assert (root/'app/child/data.txt').read_bytes()==b'abc'


def test_archive_only_directory_attribute_change_is_supported_during_completion(tree):
    value,_,_,overrides,_=tree
    h=value.dest['app'];overrides[h]=replace(value._inspect(h,True)[0],attributes=0x30)
    _under_lease(value.lease,value._seal_new_directories)
    assert value.rows['app'][2][0].attributes==0x30
    _under_lease(value.lease,value.verify)


@pytest.mark.parametrize('change',['identity','volume','security','path','attributes','unsafe','type','extra_name','wrong_namespace_id'])
def test_completion_never_adopts_identity_protection_other_bits_or_unlisted_members(tree,change):
    value,root,_,overrides,security=tree;h=value.dest['app']
    before=dict(value.rows);info=value._inspect(h,True)[0]
    if change=='identity':overrides[h]=replace(info,identity=info.identity+1)
    elif change=='volume':overrides[h]=replace(info,volume=info.volume+1)
    elif change=='security':security[h]=('CONTROLLED_FOREIGN_PROTECTION',)
    elif change=='path':os.rename(root/'app',root/'renamed')
    elif change=='attributes':overrides[h]=replace(info,attributes=0x12)
    elif change=='unsafe':overrides[h]=replace(info,attributes=0x410)
    elif change=='type':overrides[h]=replace(info,attributes=0x80)
    elif change=='extra_name':(root/'app/extra').write_bytes(b'not-listed')
    else:
        original=value._entries
        value._entries=lambda handle:tuple((name,attrs,identity+1) for name,attrs,identity in original(handle))
    with pytest.raises(CandidateRefused):_under_lease(value.lease,value._seal_new_directories)
    assert value.rows==before and value.failed and not value._completion_pending
    with pytest.raises(CandidateRefused):_under_lease(value.lease,value._seal_new_directories)


def test_files_are_never_rebased_and_completed_directories_stay_immutable(tree):
    value,root,_,_,_=tree
    (root/'app/child/data.txt').write_bytes(b'larger')  # This test owns the POSIX file, no Windows mutation.
    with pytest.raises(runtime.RuntimeMetadataChanged) as caught:
        _under_lease(value.lease,value._seal_new_directories)
    assert caught.value.object_kind=='FILE' and 'SIZE' in caught.value.changed_fields


def test_after_completion_new_growth_is_refused_instead_of_resealed(tree):
    value,root,_,_,_=tree
    _under_lease(value.lease,value._seal_new_directories)
    os.mkdir(root/'app/later',0o700)
    with pytest.raises(CandidateRefused):_under_lease(value.lease,value.verify)
    with pytest.raises(CandidateRefused):_under_lease(value.lease,value._seal_new_directories)


@pytest.mark.parametrize('state',['reopen','incomplete','already_issued'])
def test_completion_is_unavailable_outside_the_single_new_constructor_finish(tree,state):
    value,_,_,_,_=tree;calls=[]
    value._gate=lambda:calls.append('unexpected IO')
    if state=='reopen':value._completion_pending=False
    elif state=='incomplete':value._copy_complete=False
    else:runtime._issued[value]=('controlled sentinel, NOT an accepted capability',)
    with pytest.raises(CandidateRefused):value._seal_new_directories()
    assert calls==[]


def test_metadata_diagnostics_only_emit_fixed_kind_and_fields_not_private_values():
    secret='PRIVATE_PATH_SID_DESCRIPTOR_DO_NOT_OUTPUT'
    error=runtime.RuntimeMetadataChanged(True,('SIZE','LINKS'))
    report=entry._failure_diagnostic(ControlFailure('ACQUIRE',error,[]))
    row=report['exception_details'][0]
    assert row['runtime_metadata']==dict(object_kind='DIRECTORY',changed_fields=['SIZE','LINKS'])
    assert report['control']['outcome']=='UNKNOWN' and row['type']=='RuntimeMetadataChanged'
    error.args=(secret,);error.changed_fields=({'private':secret},)
    malformed=entry._failure_diagnostic(ControlFailure('ACQUIRE',error,[]))
    assert malformed['exception_details'][0]['runtime_metadata']==dict(details='UNAVAILABLE')
    fake=type('RuntimeMetadataChanged',(CandidateRefused,),{})(secret)
    assert entry._error_type(fake)=='UNLISTED_EXCEPTION'
    assert secret not in json.dumps([report,malformed,diagnostics.detail(fake,entry._error_type(fake))])


def test_metadata_pass_checks_original_deadline_between_native_queries(monkeypatch):
    clock=[1000.];calls=[]
    monkeypatch.setattr(runtime,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    value=object.__new__(runtime.NativeRuntimeInstallation)
    value.failed=value.closed=False;value.deadline=1001.;value.lease=object()
    def info(h):calls.append('info');clock[0]=1002.;return Info(0x10,0,1,1,1)
    value.api=SimpleNamespace(info=info,security=lambda h:calls.append('forbidden security'),
        descriptor=lambda h:calls.append('forbidden descriptor'),final_path=lambda h:calls.append('forbidden path'))
    with pytest.raises(CandidateRefused):value._inspect(1,True)
    assert calls==['info']


def test_gate_checks_expiry_after_identity_probe_before_further_root_queries(monkeypatch):
    clock=[1000.];calls=[]
    monkeypatch.setattr(runtime,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    value=object.__new__(runtime.NativeRuntimeInstallation)
    value.failed=value.closed=False;value.deadline=1001.;value.key=('controlled protocol key',)
    value.api=SimpleNamespace(descriptor=lambda h:calls.append('forbidden descriptor'),
        final_path=lambda h:calls.append('forbidden path'))
    class Lease:pass
    value.lease=Lease();value.lease.fs=SimpleNamespace(api=value.api,root=1)
    def probe():clock[0]=1002.;return value.key
    value.probe=SimpleNamespace(lease=value.lease,api=value.api,_gate=probe)
    with pytest.raises(CandidateRefused):value._gate()
    assert calls==[]


def test_runtime_locator_only_uses_original_verified_public_manifest_catalogue():
    root=Path(__file__).resolve().parents[1]
    sites=diagnostics.SourceSites(root,'b'*40,runtime_files={'app/public/sub/file.py':{}})
    error=runtime.RuntimeMetadataChanged(False,('SIZE',),relative_path='app/public/sub/file.py')
    report=diagnostics.detail(error,'RuntimeMetadataChanged',sites)
    assert report['runtime_relative_path']=='app/public/sub/file.py'
    stage=runtime.RuntimeStagingFailure('COPY_FILE','app/public')
    assert diagnostics.detail(stage,'RuntimeStagingFailure',sites)['runtime_stage']=='COPY_FILE'
    assert diagnostics.detail(stage,'RuntimeStagingFailure',sites)['runtime_relative_path']=='app/public'
    for path in (r'C:\PRIVATE\secret', '../secret', 'app/private', {'secret':True}, None):
        error.relative_path=path
        assert 'runtime_relative_path' not in diagnostics.detail(error,'RuntimeMetadataChanged',sites)
    error.relative_path='app/public/sub/file.py'
    assert 'runtime_relative_path' not in diagnostics.detail(error,'RuntimeMetadataChanged')


@pytest.mark.parametrize('operation',['open','create'])
def test_root_path_query_expiry_prevents_following_open_or_create(monkeypatch,operation):
    clock=[1000.];calls=[]
    monkeypatch.setattr(runtime,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    value=object.__new__(runtime.NativeRuntimeInstallation)
    value.failed=value.closed=False;value.deadline=1001.;value.key=('controlled key',)
    def final_path(h):clock[0]=1002.;return 'ROOT'
    value.api=SimpleNamespace(descriptor=lambda h:'SD',final_path=final_path,
        open_relative=lambda *args:calls.append('forbidden open'),ntcreate=lambda *args:calls.append('forbidden create'))
    class Lease:pass
    value.lease=Lease();value.lease.fs=SimpleNamespace(api=value.api,root=1)
    value.probe=SimpleNamespace(lease=value.lease,api=value.api,_gate=lambda:value.key)
    value.root_sd='SD';value.root_path='ROOT'
    with pytest.raises(CandidateRefused):
        value._open(1,'child') if operation=='open' else value._create(1,'child',False)
    assert calls==[]
