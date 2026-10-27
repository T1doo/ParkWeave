"""Linux fake API tests of candidate policy/flow. NOT Windows DLL evidence."""
import ctypes as C
from dataclasses import replace
import hashlib
import os
import uuid
import pytest
from parkweave.store import Denied
from parkweave.windows_files import (_read_candidate,read_windows_candidate,root_parts,
    logical_resource,private_acl,Ace,Security,Info,PROTECTED,DACL_PRESENT)
from parkweave.windows_handles import UnicodeString,ObjectAttributes,IOStatus,FileInfo,WinAPI

ROOT=r'C:\Users\tester\private'
SID='S-1-5-21-1-2-3-1001'
FID=str(uuid.uuid4());DATA='SYNTHETIC 合成文本'.encode()
RESOURCE={'id':FID,'size':len(DATA),'sha256':hashlib.sha256(DATA).hexdigest()}
SAFE=Security(SID,PROTECTED|DACL_PRESENT,(Ace(0,0,0x1f01ff,SID),))

class FakeAPI:
    def __init__(self):
        self.nodes=['drive','Users','tester','private','files',FID+'.txt'];self.closed=[];self.opened=[];self.security_reads=[]
        self.metadata={i:Info(0x10 if i<5 else 0,len(DATA) if i==5 else 0,1,123,i) for i in range(6)}
        self.acls={i:SAFE for i in range(6)};self.content=DATA
    def open_drive(self,drive):assert drive=='C:\\';self.opened.append((None,drive,False));return 0
    def open_relative(self,parent,name,read_data):
        child=self.nodes.index(name);assert child==parent+1
        assert parent not in self.closed
        self.opened.append((parent,name,read_data));return child
    def close(self,h):assert h not in self.closed;self.closed.append(h)
    def info(self,h):return self.metadata[h]
    def security(self,h):self.security_reads.append(h);return self.acls[h]
    def user_sid(self):return SID
    def final_path(self,h):return '\\\\?\\Volume{12345678-1234-1234-1234-123456789abc}\\'
    def filesystem(self,h):return 'NTFS'
    def drive_type(self,guid):return 3
    def read(self,h,limit):assert h==5 and limit==16385;assert not self.closed;return self.content

def test_candidate_flow_opens_relative_once_keeps_handles_and_checks_acl_twice():
    api=FakeAPI();assert _read_candidate(ROOT,RESOURCE,api)==DATA
    assert api.closed==[5,4,3,2,1,0] and [r[2] for r in api.opened]==[False]*5+[True]
    assert api.security_reads==[3,4,5,3,4,5]

@pytest.mark.parametrize('root',[None,'',r'C:private',r'\private',r'\\server\share',r'\\?\C:\private','C:\\',r'C:\private'+'\\',r'C:\a\..\b',r'C:\a\.\b',r'C:\a:b',r'C:\a/b',r'C:\a. ',r'C:\CON',r'C:\NUL.txt',r'C:\LPT¹',r'C:\a~1',r'C:\a\x\..',r'C:\a\x\file:stream','C:\\bad\x00name'])
def test_root_path_refuses_ambiguous_namespace_alias_ads_and_traversal(root):
    with pytest.raises(Denied):root_parts(root)

@pytest.mark.parametrize('key,value',[('id','../file'),('id',FID+':stream'),('id','{'+FID+'}'),('id',FID.upper()),('size',True),('size',-1),('size',16385),('sha256','bad')])
def test_logical_resource_only_canonical_uuid_and_frozen_integrity(key,value):
    with pytest.raises(Denied):logical_resource(RESOURCE|{key:value})

@pytest.mark.parametrize('security',[
 replace(SAFE,owner='other'),replace(SAFE,control=DACL_PRESENT),replace(SAFE,control=PROTECTED),replace(SAFE,aces=None),replace(SAFE,aces=()),
 replace(SAFE,aces=(Ace(0,0,1,'S-1-1-0'),)),replace(SAFE,aces=(Ace(0,8,1,'S-1-1-0'),)),
 replace(SAFE,aces=(Ace(0,0x10,1,SID),)),replace(SAFE,aces=(Ace(5,0,1,SID),)),replace(SAFE,aces=(Ace(9,0,1,SID),)),replace(SAFE,aces=(Ace(0,0x40,1,SID),))])
def test_unsafe_or_unsupported_acl_refused_without_mutators(security):
    with pytest.raises(Denied):private_acl(security,SID)

def test_known_trusted_sid_allow_and_simple_foreign_deny_supported():
    private_acl(replace(SAFE,aces=SAFE.aces+(Ace(0,0,1,'S-1-5-18'),Ace(0,0,1,'S-1-5-32-544'),Ace(1,0,1,'S-1-1-0'))),SID)

@pytest.mark.parametrize('node,change',[(i,{'attributes':0x410}) for i in range(5)]+[(5,{'attributes':0x400}),(5,{'attributes':0x10}),(5,{'links':2}),(5,{'size':16385}),(5,{'volume':456}),(5,{'attributes':0x1000}),(5,{'attributes':0x40})])
def test_reparse_every_component_and_bad_object_refused_handles_close(node,change):
    api=FakeAPI();api.metadata[node]=replace(api.metadata[node],**change)
    with pytest.raises(Denied):_read_candidate(ROOT,RESOURCE,api)
    assert api.closed==list(reversed(range(node+1)))

@pytest.mark.parametrize('node',[3,4,5])
def test_private_root_files_and_file_each_enforce_acl(node):
    api=FakeAPI();api.acls[node]=replace(SAFE,aces=(Ace(0,0,1,'S-1-1-0'),))
    with pytest.raises(Denied):_read_candidate(ROOT,RESOURCE,api)
    assert api.closed and api.closed[-1]==0

@pytest.mark.parametrize('kind',['hash','utf8','size','identity','acl-change','volume-guid','non-NTFS','remote'])
def test_read_integrity_and_post_read_security_fail_closed(kind):
    api=FakeAPI();resource=dict(RESOURCE)
    if kind=='hash':resource['sha256']='0'*64
    if kind=='utf8':api.content=b'\xff';resource.update(size=1,sha256=hashlib.sha256(b'\xff').hexdigest());api.metadata[5]=replace(api.metadata[5],size=1)
    if kind=='size':api.content=DATA+b'x'
    if kind in ('identity','acl-change'):
        old=api.read
        def changed(h,limit):
            data=old(h,limit)
            if kind=='identity':api.metadata[h]=replace(api.metadata[h],identity=999)
            else:api.acls[h]=replace(SAFE,owner='foreign')
            return data
        api.read=changed
    if kind=='volume-guid':api.final_path=lambda h:r'\\?\Volume{12345678-1234-1234-1234-123456789abc}\subst'
    if kind=='non-NTFS':api.filesystem=lambda h:'ReFS'
    if kind=='remote':api.drive_type=lambda guid:4
    with pytest.raises(Denied):_read_candidate(ROOT,resource,api)
    assert api.closed[-1]==0

def test_x64_abi_layout_explicit_fixed_width_not_linux_c_ulong():
    if C.sizeof(C.c_void_p)!=8:pytest.skip('x64 ABI layout test')
    assert C.sizeof(UnicodeString)==16 and UnicodeString.Buffer.offset==8
    assert C.sizeof(ObjectAttributes)==48 and ObjectAttributes.RootDirectory.offset==8 and ObjectAttributes.Attributes.offset==24
    assert C.sizeof(IOStatus)==16 and C.sizeof(FileInfo)==52

def test_linux_does_not_load_dll_or_expose_unsafe_fallback(monkeypatch):
    if os.name=='nt':pytest.skip('Linux rejection evidence only')
    with pytest.raises(Denied):WinAPI()
    with pytest.raises(Denied):read_windows_candidate(ROOT,RESOURCE)
    import parkweave.windows_files as candidate
    monkeypatch.setattr(candidate,'read_windows_candidate',lambda *args:pytest.fail('production must not activate candidate'))
    from parkweave.files import read_text_resource
    with pytest.raises(Denied):read_text_resource(ROOT,RESOURCE)

def test_native_relative_open_arguments_never_reopen_full_path_or_request_write():
    from parkweave.windows_handles import (READ_CONTROL,READ_ATTRIBUTES,SYNCHRONIZE,FILE_READ_DATA,
        SHARE_READ,FILE_OPEN,SYNC_NONALERT,OPEN_REPARSE)
    api=WinAPI.__new__(WinAPI);calls=[]
    def ntcreate(handle,access,attributes,io,allocation,attrs,share,disposition,options,ea,ealen):
        oa=C.cast(attributes,C.POINTER(ObjectAttributes)).contents
        u=oa.ObjectName.contents;name=C.string_at(u.Buffer,u.Length).decode('utf-16-le')
        assert oa.RootDirectory==321 and oa.Attributes==0x40 and name=='files'
        assert share==SHARE_READ and disposition==FILE_OPEN and options==SYNC_NONALERT|OPEN_REPARSE
        assert not allocation and not ea and ealen==0 and attrs==0
        calls.append(access);C.cast(handle,C.POINTER(C.c_void_p))[0]=123;return 0
    api.ntcreate=ntcreate
    assert api.open_relative(321,'files',False)==123
    assert calls==[READ_CONTROL|READ_ATTRIBUTES|SYNCHRONIZE]
    with pytest.raises(Denied):api.open_relative(321,'../outside',False)
    assert len(calls)==1


def test_native_relative_unknown_status_closes_returned_handle_without_fallback():
    api=WinAPI.__new__(WinAPI);closed=[];api.close=closed.append
    def ntcreate(handle,*args):C.cast(handle,C.POINTER(C.c_void_p))[0]=123;return 0x40000000
    api.ntcreate=ntcreate
    with pytest.raises(Denied,match='status=0x40000000'):api.open_relative(321,'files',False)
    assert closed==[123]


def test_native_probe_linux_guard_never_writes_supplied_path(tmp_path):
    import subprocess,sys
    from parkweave.process_env import minimal_environment
    if os.name=='nt':pytest.skip('Linux guard evidence')
    target=tmp_path/'must-stay-absent'
    result=subprocess.run([sys.executable,'scripts/windows/file_candidate_probe.py','--fixture-dir',str(target)],
        env=minimal_environment(os.environ),capture_output=True,text=True,timeout=5)
    assert result.returncode==1 and 'NOT_RUN' in result.stdout and not target.exists()
