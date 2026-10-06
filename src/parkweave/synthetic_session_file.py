"""Exclusive synthetic Windows session file; owner-only update before token writes."""
import ctypes
import os
from pathlib import Path


class SessionOwnerError(RuntimeError):
    pass


class WindowsSessionFile:
    def __init__(self):
        from ctypes import wintypes as w
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.a=ctypes.WinDLL('advapi32',use_last_error=True)
        self.ptr=ctypes.c_void_p;self.dword=w.DWORD
        signatures={
            'CreateFileW':([w.LPCWSTR,w.DWORD,w.DWORD,self.ptr,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE),
            'GetCurrentProcess':([],w.HANDLE),'CloseHandle':([w.HANDLE],w.BOOL),
            'LocalFree':([self.ptr],self.ptr),
            'OpenProcessToken':([w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)],w.BOOL),
            'GetTokenInformation':([w.HANDLE,ctypes.c_int,self.ptr,w.DWORD,ctypes.POINTER(w.DWORD)],w.BOOL),
            'SetSecurityInfo':([w.HANDLE,ctypes.c_int,w.DWORD,self.ptr,self.ptr,self.ptr,self.ptr],w.DWORD),
            'GetSecurityInfo':([w.HANDLE,ctypes.c_int,w.DWORD,ctypes.POINTER(self.ptr),self.ptr,ctypes.POINTER(self.ptr),self.ptr,ctypes.POINTER(self.ptr)],w.DWORD),
            'EqualSid':([self.ptr,self.ptr],w.BOOL),
            'GetSecurityDescriptorControl':([self.ptr,ctypes.POINTER(w.WORD),ctypes.POINTER(w.DWORD)],w.BOOL),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.k if name in ('CreateFileW','GetCurrentProcess','CloseHandle','LocalFree') else self.a,name)
            fn.argtypes=args;fn.restype=result

    def current_user(self):
        token=self.ptr()
        if not self.a.OpenProcessToken(self.k.GetCurrentProcess(),8,ctypes.byref(token)):
            raise SessionOwnerError('TOKEN_QUERY_REFUSED')
        try:
            length=self.dword()
            self.a.GetTokenInformation(token,1,None,0,ctypes.byref(length))
            if not 0<length.value<=65536:raise SessionOwnerError('TOKEN_QUERY_REFUSED')
            buffer=ctypes.create_string_buffer(length.value)
            if not self.a.GetTokenInformation(token,1,buffer,length,ctypes.byref(length)):
                raise SessionOwnerError('TOKEN_QUERY_REFUSED')
            sid=ctypes.cast(buffer,ctypes.POINTER(self.ptr))[0]
            return buffer,sid  # Keep TOKEN_USER backing memory alive until verification.
        finally:self.k.CloseHandle(token)

    def create(self,path):
        # WRITE_OWNER is requested on this new object only; never enable privileges.
        handle=self.k.CreateFileW(str(path),0x40000000|0x20000|0x80000,0,None,1,0x80,None)
        if handle==ctypes.c_void_p(-1).value:
            if ctypes.get_last_error() in (80,183):raise FileExistsError('session file exists')
            raise SessionOwnerError('SESSION_CREATE_REFUSED')
        return handle

    def inspect(self,handle):
        owner=self.ptr();dacl=self.ptr();descriptor=self.ptr()
        if self.a.GetSecurityInfo(handle,1,1|4,ctypes.byref(owner),None,ctypes.byref(dacl),None,ctypes.byref(descriptor)):
            raise SessionOwnerError('SESSION_INSPECTION_REFUSED')
        try:
            control=ctypes.c_uint16();revision=self.dword()
            if not self.a.GetSecurityDescriptorControl(descriptor,ctypes.byref(control),ctypes.byref(revision)):
                raise SessionOwnerError('SESSION_INSPECTION_REFUSED')
            # ACL header: BYTE revision, BYTE reserved, WORD AclSize.
            size=ctypes.c_uint16.from_address(dacl.value+2).value if dacl.value else 0
            if dacl.value and not 8<=size<=65535:raise SessionOwnerError('SESSION_INSPECTION_REFUSED')
            acl=ctypes.string_at(dacl,size) if dacl.value else None
            return descriptor,owner,acl,control.value
        except BaseException:
            self.k.LocalFree(descriptor);raise

    def set_owner(self,handle,sid):
        if self.a.SetSecurityInfo(handle,1,1,sid,None,None,None):
            raise SessionOwnerError('SESSION_OWNER_REFUSED')

    def verify_owner(self,owner,sid):
        if not self.a.EqualSid(owner,sid):raise SessionOwnerError('SESSION_OWNER_MISMATCH')

    def release_descriptor(self,descriptor):self.k.LocalFree(descriptor)
    def close(self,handle):self.k.CloseHandle(handle)
    def transfer_fd(self,handle):
        import msvcrt
        return msvcrt.open_osfhandle(handle,os.O_WRONLY|os.O_TEXT)

    def text_file(self,fd):
        try:return os.fdopen(fd,'w',encoding='utf-8')
        except BaseException as error:
            try:os.close(fd)
            except OSError:error.session_fd_cleanup_failed=True
            raise



def create_synthetic_session_file(path,*,_backend=None):
    """Only synthetic CLI's fixed filename; failure leaves new empty file protected."""
    path=Path(path)
    if path!=Path('.runtime/synthetic-sessions.json'):
        raise ValueError('fixed synthetic session path required')
    if _backend is None and os.name!='nt':raise SessionOwnerError('WINDOWS_REQUIRED')
    backend=_backend if _backend is not None else WindowsSessionFile()
    backing,sid=backend.current_user()
    handle=backend.create(path)
    before=after=None
    try:
        before=backend.inspect(handle)
        backend.set_owner(handle,sid)
        after=backend.inspect(handle)
        backend.verify_owner(after[1],sid)
        # Owner-defaulted may change; all DACL/SACL inheritance/control bits stay.
        if before[2]!=after[2] or (before[3]&~1)!=(after[3]&~1):
            raise SessionOwnerError('SESSION_PERMISSIONS_CHANGED')
        fd=backend.transfer_fd(handle)
        handle=None  # CRT takes ownership before text wrapping can fail.
        stream=backend.text_file(fd)
        return stream
    finally:
        for state in (after,before):
            if state is not None:backend.release_descriptor(state[0])
        if handle is not None:backend.close(handle)
