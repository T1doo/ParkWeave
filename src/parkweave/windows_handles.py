"""Explicit Win11 x64 ctypes ABI; loaded only by unactivated candidate probe.
Read-only methods. Documented Microsoft handle APIs; no impersonation/privilege APIs.
"""
import ctypes as C
import os
from .store import Denied
from .windows_files import Ace,Security,Info,component
U16=C.c_uint16;U32=C.c_uint32;I32=C.c_int32;PTR=C.c_void_p

class UnicodeString(C.Structure):
    _fields_=[('Length',U16),('MaximumLength',U16),('Buffer',PTR)]
class ObjectAttributes(C.Structure):
    _fields_=[('Length',U32),('RootDirectory',PTR),('ObjectName',C.POINTER(UnicodeString)),('Attributes',U32),('SecurityDescriptor',PTR),('SecurityQualityOfService',PTR)]
class IOStatus(C.Structure):
    # NTSTATUS/PVOID union occupies pointer width on x64.
    _fields_=[('Status',PTR),('Information',C.c_size_t)]
class FileTime(C.Structure):
    _fields_=[('Low',U32),('High',U32)]
class FileInfo(C.Structure):
    _fields_=[('Attributes',U32),('Creation',FileTime),('Access',FileTime),('Write',FileTime),('Volume',U32),('SizeHigh',U32),('SizeLow',U32),('Links',U32),('IndexHigh',U32),('IndexLow',U32)]
class ACL(C.Structure):
    _fields_=[('Revision',C.c_uint8),('Sbz1',C.c_uint8),('Size',U16),('AceCount',U16),('Sbz2',U16)]

READ_CONTROL=0x20000
READ_ATTRIBUTES=0x80
SYNCHRONIZE=0x100000
FILE_READ_DATA=1
SHARE_READ=1
FILE_OPEN=1
SYNC_NONALERT=0x20
OPEN_REPARSE=0x200000

class WinAPI:
    def __init__(self):
        if os.name!='nt' or C.sizeof(PTR)!=8:raise Denied('native Windows x64 only')
        # System DLL search only; never resolve DLLs from cwd/PATH.
        self.k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        self.a=C.WinDLL('advapi32.dll',use_last_error=True,winmode=0x800)
        self.n=C.WinDLL('ntdll.dll',use_last_error=True,winmode=0x800)
        def bind(lib,name,result,args):
            f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
        self.create=bind(self.k,'CreateFileW',PTR,[C.c_wchar_p,U32,U32,PTR,U32,U32,PTR])
        self.ntcreate=bind(self.n,'NtCreateFile',I32,[C.POINTER(PTR),U32,C.POINTER(ObjectAttributes),C.POINTER(IOStatus),PTR,U32,U32,U32,U32,PTR,U32])
        self._close=bind(self.k,'CloseHandle',I32,[PTR])
        self.getinfo=bind(self.k,'GetFileInformationByHandle',I32,[PTR,C.POINTER(FileInfo)])
        self.gettype=bind(self.k,'GetFileType',U32,[PTR])
        self.getpath=bind(self.k,'GetFinalPathNameByHandleW',U32,[PTR,C.c_wchar_p,U32,U32])
        self.getvolume=bind(self.k,'GetVolumeInformationByHandleW',I32,[PTR,C.c_wchar_p,U32,C.POINTER(U32),C.POINTER(U32),C.POINTER(U32),C.c_wchar_p,U32])
        self.getdrive=bind(self.k,'GetDriveTypeW',U32,[C.c_wchar_p])
        self.readfile=bind(self.k,'ReadFile',I32,[PTR,PTR,U32,C.POINTER(U32),PTR])
        self.getsecurity=bind(self.a,'GetSecurityInfo',U32,[PTR,U32,U32,C.POINTER(PTR),C.POINTER(PTR),C.POINTER(PTR),C.POINTER(PTR),C.POINTER(PTR)])
        self.control=bind(self.a,'GetSecurityDescriptorControl',I32,[PTR,C.POINTER(U16),C.POINTER(U32)])
        self.valid_sd=bind(self.a,'IsValidSecurityDescriptor',I32,[PTR])
        self.valid_acl=bind(self.a,'IsValidAcl',I32,[PTR])
        self.getace=bind(self.a,'GetAce',I32,[PTR,U32,C.POINTER(PTR)])
        self.valid_sid=bind(self.a,'IsValidSid',I32,[PTR])
        self.sidlen=bind(self.a,'GetLengthSid',U32,[PTR])
        self.sidstring=bind(self.a,'ConvertSidToStringSidW',I32,[PTR,C.POINTER(PTR)])
        self.localfree=bind(self.k,'LocalFree',PTR,[PTR])
        self.process=bind(self.k,'GetCurrentProcess',PTR,[])
        self.opentoken=bind(self.a,'OpenProcessToken',I32,[PTR,U32,C.POINTER(PTR)])
        self.tokeninfo=bind(self.a,'GetTokenInformation',I32,[PTR,U32,PTR,U32,C.POINTER(U32)])
        self._sid=self._user_sid()
    def need(self,result):
        if not result:raise Denied('Windows handle operation refused; error='+str(C.get_last_error()))
    def close(self,handle):self.need(self._close(handle))
    def open_drive(self,drive):
        # Drive-root path only; no arbitrary complete business path passed to Win32.
        handle=self.create('\\\\?\\'+drive,READ_CONTROL|READ_ATTRIBUTES,SHARE_READ,None,3,0x02000000|0x00200000,None)
        if handle in (None,C.c_void_p(-1).value):raise Denied('Windows drive open refused')
        return handle
    def open_relative(self,parent,name,read_data):
        component(name)
        raw=name.encode('utf-16-le');buf=C.create_string_buffer(raw+b'\0\0')
        u=UnicodeString(len(raw),len(raw)+2,C.cast(buf,PTR))
        oa=ObjectAttributes(C.sizeof(ObjectAttributes),parent,C.pointer(u),0x40,None,None)
        handle=PTR();io=IOStatus()
        access=READ_CONTROL|READ_ATTRIBUTES|SYNCHRONIZE|(FILE_READ_DATA if read_data else 0)
        status=self.ntcreate(C.byref(handle),access,C.byref(oa),C.byref(io),None,0,SHARE_READ,FILE_OPEN,SYNC_NONALERT|OPEN_REPARSE,None,0)
        if status!=0 or not handle.value:
            if handle.value:self.close(handle.value)
            raise Denied('Windows relative open refused; status='+hex(status&0xffffffff))
        return handle.value
    def info(self,handle):
        if self.gettype(handle)!=1:raise Denied('Windows non-disk handle refused')
        f=FileInfo();self.need(self.getinfo(handle,C.byref(f)))
        return Info(f.Attributes,(f.SizeHigh<<32)|f.SizeLow,f.Links,f.Volume,(f.IndexHigh<<32)|f.IndexLow)
    def final_path(self,handle):
        buf=C.create_unicode_buffer(4096);length=self.getpath(handle,buf,len(buf),1)
        if not 0<length<len(buf):raise Denied('Windows volume identity unavailable')
        return buf.value
    def filesystem(self,handle):
        buf=C.create_unicode_buffer(32);serial=U32();maxlen=U32();flags=U32()
        self.need(self.getvolume(handle,None,0,C.byref(serial),C.byref(maxlen),C.byref(flags),buf,len(buf)))
        return buf.value
    def drive_type(self,guid):return self.getdrive(guid)
    def sid(self,pointer):
        self.need(self.valid_sid(pointer));out=PTR()
        self.need(self.sidstring(pointer,C.byref(out)))
        try:return C.wstring_at(out)
        finally:self.localfree(out)
    def _user_sid(self):
        token=PTR();self.need(self.opentoken(self.process(),8,C.byref(token)))
        try:
            needed=U32();self.tokeninfo(token,1,None,0,C.byref(needed))
            if not 0<needed.value<=4096:raise Denied('Windows user token unavailable')
            buf=C.create_string_buffer(needed.value);self.need(self.tokeninfo(token,1,buf,len(buf),C.byref(needed)))
            return self.sid(C.cast(buf,C.POINTER(PTR))[0])
        finally:self.close(token)
    def user_sid(self):return self._sid
    def security(self,handle):
        owner=PTR();dacl=PTR();sd=PTR()
        status=self.getsecurity(handle,1,1|4,C.byref(owner),None,C.byref(dacl),None,C.byref(sd))
        if status!=0:raise Denied('Windows security read refused')
        try:
            self.need(self.valid_sd(sd));control=U16();revision=U32()
            self.need(self.control(sd,C.byref(control),C.byref(revision)))
            user=self.sid(owner)
            if not dacl.value:return Security(user,control.value,None)
            self.need(self.valid_acl(dacl));header=C.cast(dacl,C.POINTER(ACL)).contents
            if header.AceCount>128:raise Denied('Windows ACL exceeds candidate limit')
            aces=[];start=dacl.value;end=start+header.Size
            for i in range(header.AceCount):
                pointer=PTR();self.need(self.getace(dacl,i,C.byref(pointer)))
                address=pointer.value
                if address is None or address<start+C.sizeof(ACL) or address+8>end:raise Denied('invalid ACE bounds')
                head=C.string_at(address,8);kind,flags=head[0],head[1];size=int.from_bytes(head[2:4],'little')
                if kind not in (0,1) or size<16 or address+size>end:raise Denied('unsupported Windows ACE')
                sidptr=address+8;sidhead=C.string_at(sidptr,8)
                if sidhead[0]!=1 or sidhead[1]>15 or 8+4*sidhead[1]>size-8:raise Denied('invalid ACE SID bounds')
                self.need(self.valid_sid(sidptr));sidlength=self.sidlen(sidptr)
                if sidlength>size-8 or sidlength<8:raise Denied('invalid ACE SID bounds')
                aces.append(Ace(kind,flags,int.from_bytes(head[4:8],'little'),self.sid(sidptr)))
            return Security(user,control.value,tuple(aces))
        finally:
            if sd.value:self.localfree(sd)
    def read(self,handle,limit):
        buf=C.create_string_buffer(limit);length=U32()
        self.need(self.readfile(handle,buf,limit,C.byref(length),None))
        if length.value>limit:raise Denied('invalid Windows read length')
        return buf.raw[:length.value]
