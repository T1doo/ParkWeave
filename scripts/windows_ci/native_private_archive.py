"""Creation-time private extraction after the fixed source/archive admission.

Standard library only, before product/vendor imports and bootstrap read pins.
Every new object gets an explicit owner and protected user-only DACL; no
security setter, existing-object adoption, path writer or browser execution.
Partial/unknown objects remain in the disposable VM, never repaired or retried.
"""
import ctypes as C
from hashlib import sha256
import os
from pathlib import Path
import struct
import time

from .native_business_pins import NativeBootstrapPins,FileInfo

PTR=C.c_void_p
U32=C.c_uint32
_live=[]


def need(value):
    if not value:
        from .native_business_window import WindowRefused
        raise WindowRefused('PRIVATE_ARCHIVE_CREATION_REFUSED')


class UnicodeString(C.Structure):
    _fields_=[('Length',C.c_uint16),('MaximumLength',C.c_uint16),('Buffer',PTR)]


class ObjectAttributes(C.Structure):
    _fields_=[('Length',U32),('RootDirectory',PTR),('ObjectName',C.POINTER(UnicodeString)),
        ('Attributes',U32),('SecurityDescriptor',PTR),('SecurityQualityOfService',PTR)]


class IOStatus(C.Structure):
    _fields_=[('Status',PTR),('Information',C.c_size_t)]


def sid_at(raw,offset):
    need(type(raw) is bytes and type(offset) is int and 0<=offset<=len(raw)-8)
    count=raw[offset+1];need(raw[offset]==1 and 0<count<=15)
    end=offset+8+4*count;need(end<=len(raw))
    return raw[offset:end]


def descriptor(sid):
    need(sid_at(sid,0)==sid)
    ace=struct.pack('<BBHI',0,0,8+len(sid),0x1f01ff)+sid
    acl=struct.pack('<BBHHH',2,0,8+len(ace),1,0)+ace
    return struct.pack('<BBHIIII',1,0,0x9004,20,0,0,20+len(sid))+sid+acl


def verify_descriptor(raw,sid):
    need(type(raw) is bytes and 20<=len(raw)<=65536)
    revision,_,control,owner,group,sacl,dacl=struct.unpack_from('<BBHIIII',raw)
    # Query returns a self-relative SD. Only the exact explicit creation ACL
    # is supported; inherited/default ACLs or additional ACEs are not accepted.
    need(revision==1 and control&~1==0x9004 and owner>=20 and sid_at(raw,owner)==sid
        and dacl>=20 and dacl+8<=len(raw) and sacl==0)
    expected=descriptor(sid)[20+len(sid):]
    size=struct.unpack_from('<H',raw,dacl+2)[0]
    need(size==len(expected) and raw[dacl:dacl+size]==expected)
    return sid,control,expected


def component(name):
    need(type(name) is str and name and len(name.encode('utf-16-le'))<=510
        and name not in ('.','..') and name[-1:] not in (' ','.') and '~' not in name
        and not any(ord(c)<32 or c in '<>:"/\\|?*' for c in name))
    stem=name.split('.',1)[0].upper()
    need(stem not in {'CON','PRN','AUX','NUL','CONIN$','CONOUT$',
        *(f'COM{i}' for i in '123456789¹²³'),*(f'LPT{i}' for i in '123456789¹²³')})


def directory_rows(raw):
    need(type(raw) is bytes and 104<=len(raw)<=65536)
    result=[];offset=0;seen=set()
    while True:
        need(offset+104<=len(raw))
        advance=struct.unpack_from('<I',raw,offset)[0]
        attrs,length=struct.unpack_from('<II',raw,offset+56)
        identity=struct.unpack_from('<Q',raw,offset+96)[0];short=raw[offset+68]
        need(0<length<=510 and length%2==0 and short<=24 and short%2==0)
        end=offset+104+length
        need(end<=len(raw) and (not advance or advance%8==0 and advance>=104+length
            and offset+advance+104<=len(raw)))
        name=raw[offset+104:end].decode('utf-16-le',errors='strict')
        if name not in ('.','..'):
            component(name);need(name.casefold() not in seen and identity>0)
            seen.add(name.casefold());result.append((name,attrs,identity))
        if not advance:return tuple(result)
        offset+=advance


class NativePrivateArchive(NativeBootstrapPins):
    """Original held-relative FILE_CREATE; no native acceptance capability."""
    def __init__(self,payload,deadline,context):
        self.handles=[];self.rows=[];self.buffers=[];self.ownership=[];self.owned={}
        self.files={};self.created={}
        self.closed=self.failed=self.native_unknown=False
        self.deadline,self.context=deadline,context;self.cleanup_end=deadline+60
        _live.append(self)  # Also retains syscall output storage on interruption.
        need(os.name=='nt' and C.sizeof(PTR)==8)
        self._time()
        self._bind_kernel()
        self._time()
        self.a=C.WinDLL('advapi32.dll',use_last_error=True,winmode=0x800)
        self._time()
        self.n=C.WinDLL('ntdll.dll',use_last_error=True,winmode=0x800)
        declarations=(
            (self.a,'OpenProcessToken',C.c_int32,[PTR,U32,C.POINTER(PTR)]),
            (self.a,'OpenThreadToken',C.c_int32,[PTR,U32,C.c_int32,C.POINTER(PTR)]),
            (self.a,'GetTokenInformation',C.c_int32,[PTR,U32,PTR,U32,C.POINTER(U32)]),
            (self.a,'GetKernelObjectSecurity',C.c_int32,[PTR,U32,PTR,U32,C.POINTER(U32)]),
            (self.k,'GetCurrentThread',PTR,[]),
            (self.k,'WriteFile',C.c_int32,[PTR,PTR,U32,C.POINTER(U32),PTR]),
            (self.k,'FlushFileBuffers',C.c_int32,[PTR]),
            (self.k,'GetFileInformationByHandleEx',C.c_int32,[PTR,C.c_int32,PTR,U32]),
            (self.k,'GetVolumeInformationByHandleW',C.c_int32,[PTR,C.c_wchar_p,U32,
                C.POINTER(U32),C.POINTER(U32),C.POINTER(U32),C.c_wchar_p,U32]),
            (self.n,'NtCreateFile',C.c_int32,[C.POINTER(PTR),U32,C.POINTER(ObjectAttributes),
                C.POINTER(IOStatus),PTR,U32,U32,U32,U32,PTR,U32]),
        )
        for dll,name,result,args in declarations:
            fn=getattr(dll,name);fn.restype,fn.argtypes=result,args
        self.sid=self._user()
        parent=Path(payload).parent
        anchor=self._chain(parent,directory=True)
        self.volume=self._info(anchor,True)[0]
        fs=C.create_unicode_buffer(32);serial,maximum,flags=U32(),U32(),U32()
        need(self._call(self.k.GetVolumeInformationByHandleW,
            (anchor,None,0,C.byref(serial),C.byref(maximum),C.byref(flags),fs,len(fs)),
            (serial,maximum,flags,fs)) and fs.value=='NTFS')
        self.dirs={'':self._create(anchor,Path(payload).name,True)}

    def _remember(self,h):
        need(h not in self.owned)
        row=dict(handle=h,attempted=False,closed=False)
        self.ownership.append(row);self.owned[h]=row

    def _time(self):
        need(not self.native_unknown)
        super()._time()

    def _own(self,h):
        self.handles.append(h);self._remember(h)

    def _open(self,path,directory):
        self._time();text=C.create_unicode_buffer(str(path))
        h=self._call(self.k.CreateFileW,(text,0x120081,1,None,3,0x02000000|0x00200000,None),(text,))
        need(h not in (None,0,PTR(-1).value));self._own(h)
        # Register ownership BEFORE a later info/path query can fail.
        self.rows.append((h,directory,self._info(h,directory),self._path(h)))
        return h

    def _chain(self,path,*,directory):
        need(path.is_absolute() and len(path.anchor)==3 and path.anchor[1:]==':\\'
            and len(str(path))<=2048 and len(path.parts)<=64)
        anchor=C.create_unicode_buffer(path.anchor)
        need(self._call(self.k.GetDriveTypeW,(anchor,),(anchor,))==3)
        current=Path(path.anchor);h=self._open(current,True)
        for index,part in enumerate(path.parts[1:]):
            component(part);current=current/part
            h=self._open(current,True if index<len(path.parts)-2 else directory)
        return h

    def _info(self,h,directory):
        info=FileInfo()
        need(self._call(self.k.GetFileInformationByHandle,(h,C.byref(info)),(info,)))
        need(((info.index_high<<32)|info.index_low)>0
            and bool(info.attributes&0x10)==directory and not info.attributes&(0x400|0x40|0x1000|0x40000|0x400000)
            and (directory or info.links==1))
        return (info.volume,(info.index_high<<32)|info.index_low,(info.size_high<<32)|info.size_low,
            info.attributes,info.links,info.creation.high,info.creation.low,info.write.high,info.write.low)

    def _path(self,h,mode=1):
        text=C.create_unicode_buffer(4096)
        count=self._call(self.k.GetFinalPathNameByHandleW,(h,text,len(text),mode),(text,))
        need(0<count<len(text));return text.value

    def _call(self,fn,args,storage):
        # Synchronous output buffers may be released only after the original
        # call returns. An interrupted/unknown call keeps its pointed storage
        # and every borrowed parent pin alive for VM teardown.
        self._time()
        self.buffers.append(storage)
        try:result=fn(*args)
        except BaseException:self.native_unknown=True;raise
        self.buffers.pop()
        return result

    def _user(self):
        self._time()
        token=PTR();self.buffers.append(token)
        thread=self._call(self.k.GetCurrentThread,(),())
        ok=self._call(self.a.OpenThreadToken,(thread,8,True,C.byref(token)),(token,))
        if ok or token.value:
            if ok and token.value not in (None,0,PTR(-1).value):self._own(token.value)
            else:self.native_unknown=True
            need(False)  # Never impersonate, revert, or use OpenAsSelf fallback.
        need(C.get_last_error()==1008)
        token=PTR();self.buffers.append(token)
        process=self._call(self.k.GetCurrentProcess,(),())
        ok=self._call(self.a.OpenProcessToken,(process,8,C.byref(token)),(token,))
        if not ok or token.value in (None,0,PTR(-1).value):
            if token.value or ok:self.native_unknown=True
            need(False)
        self._own(token.value)
        raw=C.create_string_buffer(4096);used=U32();self.buffers.extend((raw,used))
        ok=self._call(self.a.GetTokenInformation,(token,1,raw,len(raw),C.byref(used)),(token,raw,used))
        need(ok)
        need(C.sizeof(PTR)<=used.value<=len(raw))
        address=C.cast(raw,C.POINTER(PTR))[0];start=C.addressof(raw)
        need(address is not None and start+16<=address<start+used.value)
        sid=sid_at(raw.raw[:used.value],address-start)
        self._close(token.value)
        return sid

    def _security(self,h):
        raw=C.create_string_buffer(65536);used=U32()
        ok=self._call(self.a.GetKernelObjectSecurity,(h,5,raw,len(raw),C.byref(used)),(raw,used))
        need(ok and 20<=used.value<=len(raw))
        return verify_descriptor(raw.raw[:used.value],self.sid)

    def _verify_directory(self,h):
        self._time();info=self._info(h,True)
        saved=self.created[h]
        need((info[0],info[1],info[3],info[4],self._path(h),self._security(h))==saved)

    def _create(self,parent,name,directory):
        self._time();component(name)
        if parent in getattr(self,'created',{}):self._verify_directory(parent)
        before=self._info(parent,True);path=self._path(parent)
        text=C.create_string_buffer(name.encode('utf-16-le')+b'\0\0')
        u=UnicodeString(len(name.encode('utf-16-le')),len(name.encode('utf-16-le'))+2,C.cast(text,PTR))
        sd=C.create_string_buffer(descriptor(self.sid))
        attrs=ObjectAttributes(C.sizeof(ObjectAttributes),parent,C.pointer(u),0x40,C.cast(sd,PTR),None)
        h,io=PTR(),IOStatus()
        self.buffers.append((h,io,attrs,u,text,sd))  # BEFORE entering ctypes.
        self._time()
        try:
            status=self.n.NtCreateFile(C.byref(h),0x1200a1 if directory else 0x120083,
                C.byref(attrs),C.byref(io),None,0x10 if directory else 0x80,1,2,
                0x20|0x200000|(1 if directory else 0x40|2),None,0)&0xffffffff
        except BaseException:self.native_unknown=True;raise
        if status==0x103 or status!=0 and h.value or status==0 and h.value in (None,0,PTR(-1).value):
            self.native_unknown=True;need(False)
        need(status==0)
        self._own(h.value)
        need(io.Information==2 and not io.Status)
        info=self._info(h.value,directory)
        need(info[0]==self.volume and info[1]!=before[1]
            and self._path(h.value)==path.rstrip('\\')+'\\'+name
            and self._info(parent,True)[:2]==before[:2] and self._path(parent)==path)
        security=self._security(h.value)
        if directory:
            self.created[h.value]=(info[0],info[1],info[3],info[4],self._path(h.value),security)
        if parent in self.created:self._verify_directory(parent)
        return h.value

    def write(self,name,data):
        self._time();need(type(name) is str and type(data) is bytes and len(data)<=128*1024*1024)
        parts=name.split('/');need(1<=len(parts)<=64)
        for part in parts:component(part)
        for index in range(1,len(parts)):
            prefix='/'.join(parts[:index])
            if prefix not in self.dirs:
                self.dirs[prefix]=self._create(self.dirs['/'.join(parts[:index-1])],parts[index-1],True)
        h=self._create(self.dirs['/'.join(parts[:-1])],parts[-1],False)
        before=self._info(h,False);security=self._security(h)
        for offset in range(0,len(data),1024*1024):
            self._time();raw=data[offset:offset+1024*1024]
            buf=C.create_string_buffer(raw);used=U32()
            ok=self._call(self.k.WriteFile,(h,buf,len(raw),C.byref(used),None),(buf,used))
            need(ok and used.value==len(raw))
        need(self._call(self.k.FlushFileBuffers,(h,),()))
        after=self._info(h,False)
        need(after[:2]==before[:2] and after[2]==len(data) and after[3:5]==before[3:5]
            and self._security(h)==security and self._hash(h,len(data))==sha256(data).hexdigest()
            and self._info(h,False)==after)
        self.files[name]=(after[3],after[1])
        self._close(h)

    def _hash(self,h,size):
        need(0<=size<=128*1024*1024 and self._call(self.k.SetFilePointerEx,(h,0,None,0),()))
        result=sha256();left=size
        while True:
            self._time();count=min(1024*1024,left) if left else 1
            raw=C.create_string_buffer(count);used=U32()
            ok=self._call(self.k.ReadFile,(h,raw,count,C.byref(used),None),(raw,used))
            need(ok)
            if not left:need(used.value==0);return result.hexdigest()
            need(0<used.value<=count);result.update(raw.raw[:used.value]);left-=used.value

    def _close(self,h):
        need(not self.native_unknown)
        from .native_business_window import current_context
        need(time.monotonic()<self.cleanup_end and current_context()==self.context)
        row=self.owned.get(h)
        need(h in self.handles and row is not None and not row['attempted']);row['attempted']=True
        try:need(self.k.CloseHandle(h))
        except BaseException:self.native_unknown=True;raise
        row['closed']=True;del self.owned[h];self.handles.remove(h)

    def close(self):
        if self.closed:return
        # Pending/unknown native call storage and HANDLE ownership stay alive;
        # do not guess completion, close again, repair permissions or delete.
        need(not self.native_unknown)
        while self.handles:
            from .native_business_window import current_context
            need(time.monotonic()<self.cleanup_end and current_context()==self.context)
            self._close(self.handles[-1])
        self.closed=True
        if self in _live:_live.remove(self)

    def finish(self):
        expected=dict(self.files)
        for path,h in self.dirs.items():
            if path:
                info=self._info(h,True);expected[path]=(info[3],info[1])
        seen=set()
        for prefix,h in self.dirs.items():
            self._verify_directory(h);local=set()
            for index in range(4096):
                self._time();raw=C.create_string_buffer(65536)
                if not self._call(self.k.GetFileInformationByHandleEx,
                        (h,11 if index==0 else 10,raw,len(raw)),(raw,)):
                    need(C.get_last_error()==18);break
                for name,attrs,identity in directory_rows(raw.raw):
                    path=(prefix+'/' if prefix else '')+name
                    need(name.casefold() not in local and path not in seen
                        and expected.get(path)==(attrs,identity))
                    local.add(name.casefold());seen.add(path)
            else:need(False)
            self._verify_directory(h)
        need(seen==set(expected))


def extract_private(payload,entries,deadline,context):
    """Only called by extract_approved_archive after original byte admission."""
    tree=None;primary=cleanup=None
    try:
        # Preserve partial-constructor ownership even if __init__ raises.
        tree=object.__new__(NativePrivateArchive)
        NativePrivateArchive.__init__(tree,payload,deadline,context)
        for name,data in entries:tree.write(name,data)
        tree.finish()
    except BaseException as error:primary=error
    finally:
        if tree is not None and hasattr(tree,'handles'):
            try:tree.close()
            except BaseException as error:cleanup=error
    if primary is not None or cleanup is not None:
        raise BaseExceptionGroup('PRIVATE_ARCHIVE_CREATE_OR_CLOSE_FAILED',
            [error for error in (primary,cleanup) if error is not None]) from None
