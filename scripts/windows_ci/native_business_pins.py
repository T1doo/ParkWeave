"""Read-only bootstrap pins held through the complete native business trial.

Standard library only: do NOT import vendor or product/native modules before
all their approved bytes and ancestor paths are pinned. The coordinator stays
in the existing GitHub runner Python; candidate executable startup is delegated
only later to the original held-installation/owned-process implementations.
"""
import ctypes as C
from hashlib import sha256
import os
from pathlib import Path
import time

_live=[]


class FileTime(C.Structure):_fields_=[('low',C.c_uint32),('high',C.c_uint32)]
class FileInfo(C.Structure):
    _fields_=[('attributes',C.c_uint32),('creation',FileTime),('access',FileTime),('write',FileTime),
        ('volume',C.c_uint32),('size_high',C.c_uint32),('size_low',C.c_uint32),('links',C.c_uint32),
        ('index_high',C.c_uint32),('index_low',C.c_uint32)]


def need(value):
    if not value:raise RuntimeError('ORIGINAL_BOOTSTRAP_PINS_REQUIRED')


class NativeBootstrapPins:
    def __init__(self,payload,raw,manifest,deadline,context):
        self.handles=[];self.rows=[];self.files={};self.closed=self.failed=False
        self.deadline,self.context=deadline,context
        _live.append(self)  # Before any native construction/call or partial failure.
        need(os.name=='nt' and C.sizeof(C.c_void_p)==8)
        self.k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        declarations={
            'CreateFileW':(C.c_void_p,[C.c_wchar_p,C.c_uint32,C.c_uint32,C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p]),
            'GetFileInformationByHandle':(C.c_int32,[C.c_void_p,C.POINTER(FileInfo)]),
            'GetFinalPathNameByHandleW':(C.c_uint32,[C.c_void_p,C.c_wchar_p,C.c_uint32,C.c_uint32]),
            'SetFilePointerEx':(C.c_int32,[C.c_void_p,C.c_int64,C.c_void_p,C.c_uint32]),
            'ReadFile':(C.c_int32,[C.c_void_p,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32),C.c_void_p]),
            'CloseHandle':(C.c_int32,[C.c_void_p]),
            'GetCurrentProcess':(C.c_void_p,[]),
            'QueryFullProcessImageNameW':(C.c_int32,[C.c_void_p,C.c_uint32,C.c_wchar_p,C.POINTER(C.c_uint32)]),
            'GetDriveTypeW':(C.c_uint32,[C.c_wchar_p]),
        }
        for name,(result,args) in declarations.items():
            fn=getattr(self.k,name);fn.restype,fn.argtypes=result,args
        self.payload=Path(payload);self.raw=raw
        self.manifest=manifest
        # Hold the actual coordinator image and its full ancestor chain too.
        import sys
        coordinator=self._chain(Path(sys.executable),directory=False)
        text=C.create_unicode_buffer(4096);length=C.c_uint32(len(text))
        need(self.k.QueryFullProcessImageNameW(self.k.GetCurrentProcess(),1,text,C.byref(length)))
        need(text.value.casefold()==self._path(coordinator,2).casefold())
        self.root=self._chain(self.payload,directory=True)
        dirs={'':self.root};expected=dict(manifest['files'])
        expected['payload-manifest.json']=dict(bytes=len(raw),sha256=sha256(raw).hexdigest())
        for name,row in sorted(expected.items()):
            self._time();parts=name.split('/')
            for n in range(1,len(parts)):
                prefix='/'.join(parts[:n])
                if prefix not in dirs:dirs[prefix]=self._open(self.payload/Path(*parts[:n]),True)
            h=self._open(self.payload/Path(*parts),False)
            before=self._info(h,False)
            need(before[2]==row['bytes'] and self._hash(h,row['bytes'])==row['sha256']
                 and self._info(h,False)==before)
            self.files[name]=(h,before,row['sha256'])
        self.verify()

    def _time(self):
        from .native_business_window import current_context
        need(not self.closed and not self.failed and time.monotonic()<self.deadline
             and current_context()==self.context)

    def _path(self,h,mode=1):
        text=C.create_unicode_buffer(4096);count=self.k.GetFinalPathNameByHandleW(h,text,len(text),mode)
        need(0<count<len(text));return text.value

    def _info(self,h,directory):
        info=FileInfo();need(self.k.GetFileInformationByHandle(h,C.byref(info)))
        need(bool(info.attributes&0x10)==directory and not info.attributes&(0x400|0x40|0x1000|0x40000|0x400000)
             and (directory or info.links==1))
        return (info.volume,(info.index_high<<32)|info.index_low,(info.size_high<<32)|info.size_low,
            info.attributes,info.links,info.creation.high,info.creation.low,info.write.high,info.write.low)

    def _open(self,path,directory):
        self._time()
        # SHARE_READ only prevents write/delete replacement; no inherited handle.
        try:h=self.k.CreateFileW(str(path),0x120081,1,None,3,0x02000000|0x00200000,None)
        except BaseException:
            self.failed=True;raise RuntimeError('BOOTSTRAP_OPEN_UNKNOWN') from None
        need(h not in (None,0,C.c_void_p(-1).value));self.handles.append(h)
        observed=self._info(h,directory);final=self._path(h)
        self.rows.append((h,directory,observed,final))
        return h

    def _chain(self,path,*,directory):
        need(path.is_absolute() and len(path.anchor)==3 and path.anchor[1:]==':\\'
             and not any(x in ('.','..') for x in path.parts))
        need(self.k.GetDriveTypeW(path.anchor)==3)
        current=Path(path.anchor);h=self._open(current,True)
        for index,part in enumerate(path.parts[1:]):
            need(part and part[-1:] not in (' ','.') and not any(c in part for c in '<>:"/\\|?*'))
            current=current/part
            h=self._open(current,True if index<len(path.parts)-2 else directory)
        return h

    def _hash(self,h,size):
        need(type(size) is int and 0<=size<=128*1024*1024 and self.k.SetFilePointerEx(h,0,None,0))
        result=sha256();left=size
        while left:
            self._time();buffer=C.create_string_buffer(min(1024*1024,left));used=C.c_uint32()
            need(self.k.ReadFile(h,buffer,len(buffer),C.byref(used),None) and 0<used.value<=len(buffer))
            result.update(buffer.raw[:used.value]);left-=used.value
        return result.hexdigest()

    def read(self,name):
        self._time();need(type(name) is str and name in self.files)
        h,before,digest=self.files[name]
        need(self._info(h,False)==before and self.k.SetFilePointerEx(h,0,None,0))
        chunks=[];left=before[2]
        while left:
            self._time();buffer=C.create_string_buffer(min(1024*1024,left));used=C.c_uint32()
            need(self.k.ReadFile(h,buffer,len(buffer),C.byref(used),None) and 0<used.value<=len(buffer))
            chunks.append(buffer.raw[:used.value]);left-=used.value
        raw=b''.join(chunks)
        need(sha256(raw).hexdigest()==digest and self._info(h,False)==before)
        return raw

    def verify(self):
        self._time()
        for h,directory,info,path in self.rows:
            self._time();need(self._info(h,directory)==info and self._path(h)==path)

    def close(self,cleanup_end):
        need(not self.closed)
        while self.handles:
            from .native_business_window import current_context
            need(time.monotonic()<cleanup_end and current_context()==self.context)
            h=self.handles.pop()
            try:need(self.k.CloseHandle(h))
            except BaseException:self.failed=True;raise
        self.closed=True
        if self in _live:_live.remove(self)
