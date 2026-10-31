"""ABI/policy protocol with real owned POSIX file IO, never Windows evidence.

The NT and security-query boundaries are explicitly controlled. Real mkdirat,
exclusive open, write/fsync/readback and descriptor ownership cover sequencing;
only a separately admitted Windows run can prove native syscall semantics.
"""
import ctypes as C
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts.windows_ci import native_private_archive as archive,native_business_window as window
from scripts.windows_portable.native_secret_store_candidate import private_file_descriptor
from parkweave.windows_files import private_acl,Security,Ace

SID=bytes.fromhex('010200000000000515000000b0040000')  # Synthetic, not a real application identity.


def test_stdlib_import_has_no_native_calls_or_early_product_imports():
    script='''import ctypes,sys
sys.path.insert(0,sys.argv[1])
def forbidden(*args,**kwargs):raise AssertionError("native call during import")
ctypes.WinDLL=forbidden
import scripts.windows_ci.native_private_archive
assert not any(name=="parkweave" or name.startswith("parkweave.") for name in sys.modules)
'''
    subprocess.run([sys.executable,'-I','-B','-S','-c',script,str(Path(__file__).resolve().parents[1])],
        check=True,capture_output=True)


def test_original_private_acl_contract_and_exact_creation_descriptor_agree():
    raw=archive.descriptor(SID)
    assert raw==private_file_descriptor(SID)
    archive.verify_descriptor(raw,SID)
    user='S-1-5-21-1200'
    private_acl(Security(user,0x9004,(Ace(0,0,0x1f01ff,user),)),user)
    # Ordinary inherited extraction remains refused; no bypass was introduced.
    from parkweave.store import Denied
    with pytest.raises(Denied):private_acl(Security(user,0x8004,(Ace(0,0x10,0x1f01ff,user),)),user)
    for offset,value in ((2,0x8004),(4,0),(16,0)):
        bad=bytearray(raw);struct.pack_into('<H' if offset==2 else '<I',bad,offset,value)
        with pytest.raises(window.WindowRefused):archive.verify_descriptor(bytes(bad),SID)
    with pytest.raises(window.WindowRefused):archive.verify_descriptor(raw,SID[:-1]+b'X')
    with pytest.raises(window.WindowRefused):archive.verify_descriptor(raw[:-1],SID)


@pytest.mark.parametrize('name',['../x','CON.txt','COM¹','file:ads','alias~1','trailing.','x\\y'])
def test_unsafe_components_never_reach_creation(name):
    with pytest.raises(window.WindowRefused):archive.component(name)


def dir_batch(rows):
    chunks=[]
    for index,(name,attrs,identity) in enumerate(rows):
        text=name.encode('utf-16-le');size=(104+len(text)+7)//8*8
        raw=bytearray(size)
        struct.pack_into('<I',raw,0,size if index<len(rows)-1 else 0)
        struct.pack_into('<II',raw,56,attrs,len(text));struct.pack_into('<Q',raw,96,identity)
        raw[104:104+len(text)]=text;chunks.append(bytes(raw))
    return b''.join(chunks)


@pytest.fixture
def wired_tree(tmp_path,monkeypatch):
    tree=object.__new__(archive.NativePrivateArchive)
    tree.handles=[];tree.rows=[];tree.buffers=[];tree.ownership=[];tree.owned={}
    tree.files={};tree.created={};tree.native_unknown=tree.closed=tree.failed=False
    tree.deadline=time.monotonic()+10;tree.cleanup_end=tree.deadline+60
    tree.context=window.current_context();tree.sid=SID
    actual={};calls=[];closed=[]
    def info(h,directory):
        value=os.fstat(h);assert os.path.isdir(actual[h])==directory
        return value.st_dev,value.st_ino,value.st_size,0x10 if directory else 0x80,1 if directory else value.st_nlink
    tree._info=info
    tree._path=lambda h:'PIN:'+str(actual[h]).replace('/','\\')
    tree._security=lambda h:archive.verify_descriptor(archive.descriptor(SID),SID)
    def create(output,access,attributes,io,allocation,attrs,share,disposition,options,ea,ealen):
        oa=C.cast(attributes,C.POINTER(archive.ObjectAttributes)).contents
        text=oa.ObjectName.contents
        name=C.string_at(text.Buffer,text.Length).decode('utf-16-le')
        sd=C.string_at(oa.SecurityDescriptor,len(archive.descriptor(SID)))
        assert sd==archive.descriptor(SID) and disposition==2 and share==1
        assert oa.Attributes==0x40 and not oa.SecurityQualityOfService and options&0x200000
        directory=bool(options&1)
        assert access==(0x1200a1 if directory else 0x120083)
        calls.append((oa.RootDirectory,name,directory))
        parent=oa.RootDirectory
        try:
            if directory:
                os.mkdir(name,mode=0o700,dir_fd=parent)
                h=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            else:h=os.open(name,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600,dir_fd=parent)
        except FileExistsError:return 0xc0000035
        actual[h]=actual[parent]/name
        C.cast(output,C.POINTER(archive.PTR))[0]=h
        status=C.cast(io,C.POINTER(archive.IOStatus)).contents;status.Status=None;status.Information=2
        return 0
    def write(h,buf,size,used,overlapped):
        assert overlapped is None
        C.cast(used,C.POINTER(archive.U32))[0]=os.write(h,C.string_at(buf,size));return True
    def read(h,buf,size,used,overlapped):
        raw=os.read(h,size);C.memmove(buf,raw,len(raw))
        C.cast(used,C.POINTER(archive.U32))[0]=len(raw);return True
    def close(h):
        os.close(h);closed.append(h);return True
    def entries(h,kind,buf,size):
        if kind==10:return False
        rows=[]
        for name in os.listdir(h):
            row=os.stat(name,dir_fd=h,follow_symlinks=False)
            rows.append((name,0x10 if os.path.isdir(actual[h]/name) else 0x80,row.st_ino))
        if not rows:return False
        raw=dir_batch(rows);assert len(raw)<=size;C.memmove(buf,raw,len(raw));return True
    tree.n=SimpleNamespace(NtCreateFile=create)
    tree.k=SimpleNamespace(WriteFile=write,ReadFile=read,CloseHandle=close,
        FlushFileBuffers=lambda h:os.fsync(h) is None,
        SetFilePointerEx=lambda h,offset,unused,mode:os.lseek(h,offset,mode)==offset,
        GetFileInformationByHandleEx=entries)
    monkeypatch.setattr(C,'get_last_error',lambda:18,raising=False)
    parent=os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY);actual[parent]=tmp_path;tree._own(parent)
    tree.volume=os.fstat(parent).st_dev
    tree.dirs={'':tree._create(parent,'payload',True)}
    yield tree,tmp_path/'payload',calls,closed
    for h in tree.handles:
        try:os.close(h)
        except OSError:pass


def test_held_relative_create_flush_readback_namespace_and_numeric_handle_reuse(wired_tree):
    tree,root,calls,closed=wired_tree
    for name,raw in (('app/样例.txt','真实合成数据'.encode()),('app/second.txt',b'next'),('empty',b'')):
        tree.write(name,raw);assert (root/name).read_bytes()==raw
    tree.finish()
    file_rows=[row for row in tree.ownership if row['closed']]
    assert len(file_rows)==3 and len({row['handle'] for row in file_rows})<len(file_rows)
    assert [name for _,name,_ in calls]==['payload','app','样例.txt','second.txt','empty']
    tree.close();tree.close()
    assert all(row['attempted'] and row['closed'] for row in tree.ownership)
    assert not tree.handles and not tree.owned
    assert (root/'app/样例.txt').exists()  # No recursive delete or directory adoption.


def test_existing_leaf_unlisted_namespace_and_changed_source_are_refused(wired_tree):
    tree,root,calls,closed=wired_tree
    tree.write('app/file',b'original')
    with pytest.raises(window.WindowRefused):tree.write('app/file',b'replacement')
    assert (root/'app/file').read_bytes()==b'original'
    (root/'extra').write_bytes(b'unlisted')
    with pytest.raises(window.WindowRefused):tree.finish()
    tree.close()


@pytest.mark.parametrize('outcome',['pending','exception','failed_output','invalid_success'])
def test_unknown_native_creation_keeps_outputs_parent_and_never_closes_or_retries(wired_tree,outcome):
    tree,root,calls,closed=wired_tree
    count=0
    def unknown(output,*args):
        nonlocal count
        count+=1
        if outcome=='exception':raise RuntimeError('controlled boundary failure')
        if outcome in ('pending','failed_output'):C.cast(output,C.POINTER(archive.PTR))[0]=777777
        return dict(pending=0x103,failed_output=0xc0000022,invalid_success=0)[outcome]
    tree.n.NtCreateFile=unknown
    with pytest.raises((window.WindowRefused,RuntimeError)):tree.write('new',b'not written')
    before=list(closed)
    with pytest.raises(window.WindowRefused):tree.close()
    assert count==1 and closed==before and tree.native_unknown and tree.buffers
    assert all(os.fstat(h) for h in tree.handles) and not (root/'new').exists()


@pytest.mark.parametrize('failure',['partial_write','corrupt_readback','lost_close_ack'])
def test_io_failures_preserve_failure_and_do_not_retry(wired_tree,failure):
    tree,root,calls,closed=wired_tree
    if failure=='partial_write':
        def partial(h,buf,size,used,overlapped):
            C.cast(used,C.POINTER(archive.U32))[0]=0;return True
        tree.k.WriteFile=partial
    elif failure=='corrupt_readback':
        def corrupt(h,buf,size,used,overlapped):
            raw=os.read(h,size)
            if raw:raw=b'X'*len(raw)
            C.memmove(buf,raw,len(raw));C.cast(used,C.POINTER(archive.U32))[0]=len(raw);return True
        tree.k.ReadFile=corrupt
    else:
        original=tree.k.CloseHandle
        def lost(h):original(h);raise RuntimeError('controlled close acknowledgement unknown')
        tree.k.CloseHandle=lost
    with pytest.raises((window.WindowRefused,RuntimeError)):tree.write('file',b'original')
    if failure=='lost_close_ack':
        before=list(closed)
        with pytest.raises(window.WindowRefused):tree.close()
        assert closed==before and tree.native_unknown
    else:tree.close()


def test_null_admission_refuses_before_private_extractor_or_any_native_call(tmp_path,monkeypatch):
    monkeypatch.setattr(C,'WinDLL',lambda *args,**kw:pytest.fail('native before source admission'),raising=False)
    monkeypatch.setattr(archive,'extract_private',lambda *args:pytest.fail('extract before source admission'))
    with pytest.raises(window.WindowRefused):
        window.extract_approved_archive(object(),tmp_path/'missing',tmp_path/'missing.zip')
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('negative',[False,True])
def test_open_registers_original_handle_before_query_failure_and_retains_unknown(wired_tree,negative):
    tree,root,calls,closed=wired_tree
    # Separate query methods from the POSIX metadata seam above. The original
    # owned descriptor is real; the API boundary reports either a completed
    # negative read or an exception with an outstanding output buffer.
    h=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    tree.k.CreateFileW=lambda *args:h
    def query(handle,output):
        assert handle==h and tree.owned[h]['attempted'] is False
        if negative:return False
        raise RuntimeError('controlled query outcome unknown')
    tree.k.GetFileInformationByHandle=query
    tree._info=archive.NativePrivateArchive._info.__get__(tree)
    with pytest.raises((window.WindowRefused,RuntimeError)):tree._open(root,True)
    assert h in tree.owned and os.fstat(h)
    if negative:
        assert not tree.native_unknown
        tree.close();assert closed.count(h)==1
    else:
        assert tree.native_unknown and tree.buffers
        with pytest.raises(window.WindowRefused):tree.close()
        assert h not in closed and os.fstat(h)


@pytest.mark.parametrize('point',['flush','seek','security','path','namespace'])
def test_query_exceptions_keep_original_output_storage_and_all_borrowed_handles(wired_tree,point):
    tree,root,calls,closed=wired_tree
    def unknown(*args):raise RuntimeError('controlled native query exception')
    if point=='flush':tree.k.FlushFileBuffers=unknown
    elif point=='seek':tree.k.SetFilePointerEx=unknown
    elif point=='security':
        tree._security=archive.NativePrivateArchive._security.__get__(tree)
        tree.a=SimpleNamespace(GetKernelObjectSecurity=unknown)
    elif point=='path':
        tree._path=archive.NativePrivateArchive._path.__get__(tree)
        tree.k.GetFinalPathNameByHandleW=unknown
    else:tree.k.GetFileInformationByHandleEx=unknown
    with pytest.raises(RuntimeError):
        if point=='namespace':tree.finish()
        else:tree.write('file',b'owned synthetic bytes')
    before=list(closed)
    with pytest.raises(window.WindowRefused):tree.close()
    assert tree.native_unknown and tree.buffers and closed==before
    assert all(os.fstat(h) for h in tree.handles)


@pytest.mark.parametrize('point',['write','flush','parent_query'])
def test_each_native_call_rechecks_work_deadline_without_extending_cleanup(wired_tree,point):
    tree,root,calls,closed=wired_tree
    events=[]
    if point=='write':
        original=tree.k.WriteFile
        def expired(*args):
            result=original(*args);tree.deadline=time.monotonic()-1;return result
        tree.k.WriteFile=expired
        tree.k.FlushFileBuffers=lambda *args:events.append('forbidden flush')
    elif point=='flush':
        original=tree.k.FlushFileBuffers
        def expired(*args):
            result=original(*args);tree.deadline=time.monotonic()-1;return result
        tree.k.FlushFileBuffers=expired
        tree.k.SetFilePointerEx=lambda *args:events.append('forbidden seek')
    else:
        original=tree._security
        def expired(*args):
            result=original(*args);tree.deadline=time.monotonic()-1;return result
        tree._security=expired
        tree.n.NtCreateFile=lambda *args:events.append('forbidden create')
    end=tree.cleanup_end
    with pytest.raises(RuntimeError):tree.write('file',b'owned synthetic bytes')
    assert not events and tree.cleanup_end==end and not tree.native_unknown
    tree.close()  # Known completed work may release original handles within the original cleanup window.
    assert not tree.handles and all(row['closed'] for row in tree.ownership)


@pytest.mark.parametrize('changed_attributes',[0x20,0x22])
def test_owned_write_allows_archive_metadata_change_only(wired_tree,changed_attributes):
    tree,root,calls,closed=wired_tree
    original_info,original_write=tree._info,tree.k.WriteFile;modified=set()
    def info(h,directory):
        value=original_info(h,directory)
        if not directory and h in modified:return (*value[:3],changed_attributes,*value[4:])
        return value
    def write(h,*args):
        result=original_write(h,*args);modified.add(h);return result
    tree._info,tree.k.WriteFile=info,write
    if changed_attributes==0x20:
        tree.write('file',b'owned synthetic bytes')
        assert tree.files['file'][0]==0x20 and (root/'file').read_bytes()==b'owned synthetic bytes'
    else:
        with pytest.raises(window.WindowRefused):tree.write('file',b'owned synthetic bytes')
    tree.close()
