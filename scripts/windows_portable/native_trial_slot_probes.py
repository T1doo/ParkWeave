"""Actual auxiliary fixed-slot negative probes inside the original trial tmp.

Never corrupts the business journal. Fixed files are FILE_CREATE only, retained
until runner disposal, and cannot be retried/adopted. No protocol dictionary is
accepted as an exclusive-open or torn-slot observation.
"""
import ctypes as C
from hashlib import sha256
import weakref

from parkweave.windows_handles import (PTR,UnicodeString,ObjectAttributes,IOStatus,FileInfo,
    nt_status,completed_nt_handle,require_nt_create_ready,retain_pending_nt_create)
from . import fixed_journal as j,native_trial_authority as a
from .native_protected_objects import create,require_original_creation,submit_create
from .native_layout_candidate import _leaf_held

_completed=weakref.WeakKeyDictionary()
_retained=[]


class NativeSlotProbes:
    def __init__(self,lease,security):
        a.need(a.bound_state(lease) is not None and security.lease is lease)
        self.lease,self.api,self.security=lease,lease.fs.api,security
        self.parent=_leaf_held(lease,security.layout,'tmp')[1]
        self.handles=[];self.failed=False

    def _new(self,name):
        a.budget(self.lease)
        handle=create(self.api,self.parent,name,directory=False,write=True,exclusive=True)
        self.handles.append(handle)
        return handle

    def _verify(self):
        a.budget(self.lease);self.lease._verify()
        for h in self.handles:
            require_original_creation(self.api,h)
            a.need(self.api.info(h).size<=j.SIZE)

    def _seek(self,h,offset):
        self._verify();fn=self.api.readonly.k.SetFilePointerEx
        fn.argtypes,fn.restype=[PTR,C.c_int64,PTR,C.c_uint32],C.c_int32
        self.api.need(fn(h,offset,None,0))

    def _read(self,h,offset,count):
        a.need(0<=offset<=j.SIZE and 0<count<=j.SIZE)
        self._seek(h,offset);raw=self.api.read(h,count);self._verify();return raw

    def _write(self,h,offset,raw):
        a.need(type(raw) is bytes and 0<=offset and 0<len(raw)<=j.SIZE and offset+len(raw)<=j.SIZE)
        self._seek(h,offset);buffer=C.create_string_buffer(raw);count=C.c_uint32()
        self.api.need(self.api.writefile(h,buffer,len(raw),C.byref(count),None))
        a.need(count.value==len(raw));self._verify();return count.value

    def _flush(self,h):self._verify();self.api.flush(h);self._verify()

    def _exclusive(self,h,name):
        self._verify();before=require_original_creation(self.api,h)
        require_nt_create_ready(self.api.readonly)
        raw=name.encode('utf-16-le');text=C.create_string_buffer(raw+b'\0\0')
        unicode=UnicodeString(len(raw),len(raw)+2,C.cast(text,PTR))
        attrs=ObjectAttributes(C.sizeof(ObjectAttributes),self.parent,C.pointer(unicode),0x40,None,None)
        result,io=PTR(),IOStatus()
        status=submit_create(self.api,result,io,attrs,(unicode,text),access=0x40120081,
            attributes=0x80,share=0,disposition=1,options=0x20|0x200000|0x40|2)
        owned=completed_nt_handle(status,result.value)
        if owned:
            # Unexpected success still transfers ownership. Close it once and
            # fail; it can never count as a sharing violation.
            try:self.api.close(result.value)
            finally:a.need(False)
        a.need(status==nt_status(0xc0000043) and not result.value)
        a.need(require_original_creation(self.api,h)==before)
        return status,before

    def run(self):
        primary=None;cleanup=[];observed=None
        try:
            lock=self._new('.pw-native-probe.lock')
            slots=self._new('.pw-native-probe.slots')
            torn=self._new('.pw-native-probe.torn')
            io=_SlotIO(self,slots,lock)
            record=dict(schema=j.schema(j.FixedFormat.INSTANCE_V2),root=io.root_id,lock=io.lock_id,
                journal=io.identity(),generation=1,sequence=2,phase='NEW',initialized=False,
                runtime='STOPPED',handoff='OWNED',instance_id=self.lease._verified_instance_uuid())
            snapshot=j.FixedJournal(io,format=j.FixedFormat.INSTANCE_V2).write(j.encode(record),None)
            refusal=self._exclusive(slots,'.pw-native-probe.slots')
            damaged=bytearray(snapshot[1]);damaged[-1]^=1
            self._write(torn,0,bytes(damaged));self._flush(torn)
            before=self._read(torn,0,j.SIZE)
            try:j.FixedJournal(_SlotIO(self,torn,lock),format=j.FixedFormat.INSTANCE_V2).read()
            except j.LeaseRefused as error:a.need(str(error)=='FIXED_SLOT_TORN')
            else:a.need(False)
            a.need(before==bytes(damaged)==self._read(torn,0,j.SIZE))
            from .native_trial_interruptions import NativeInterruptionJob,STAGES
            interruptions=[]
            for stage in STAGES:
                h=self._new('.pw-native-interrupt-'+stage.lower()+'.slots')
                stage_io=_SlotIO(self,h,lock)
                stage_record={**record,'journal':stage_io.identity()}
                first=j.slot_bytes({**stage_record,'sequence':1},0,j.ZERO_HASH,format=j.FixedFormat.INSTANCE_V2)
                expected=first+j.slot_bytes(stage_record,1,sha256(first).digest(),format=j.FixedFormat.INSTANCE_V2)
                child=NativeInterruptionJob(self,self.security,h,stage,expected)
                try:identity=child.run()
                finally:
                    if not child.cleanup_partial():
                        _retained.append(child);a.need(False)
                if stage in ('BEFORE_WRITE','PARTIAL_WRITE'):
                    length=0 if stage=='BEFORE_WRITE' else 317
                    a.need(self.api.info(h).size==length)
                    try:j.FixedJournal(stage_io,format=j.FixedFormat.INSTANCE_V2).read()
                    except j.LeaseRefused as error:a.need(str(error)=='FIXED_FILE_LENGTH')
                    else:a.need(False)
                    observed_raw=b'' if length==0 else self._read(h,0,length)
                    a.need(observed_raw==expected[:length])
                    outcome='SAFE_REFUSAL_FIXED_FILE_LENGTH'
                else:
                    a.need(j.FixedJournal(stage_io,format=j.FixedFormat.INSTANCE_V2).read()==(j.encode(stage_record),expected))
                    observed_raw=self._read(h,0,j.SIZE);outcome='EXACT_READBACK'
                interruptions.append((stage,identity,require_original_creation(self.api,h),outcome,sha256(observed_raw).hexdigest()))
            self._verify()
            observed=(tuple(require_original_creation(self.api,h) for h in self.handles),
                refusal,sha256(before).hexdigest(),tuple(interruptions))
        except BaseException as error:primary=error;self.failed=True
        finally:
            if getattr(self.api.readonly,'_nt_create_pending',False):
                _retained.append(self);cleanup.append(RuntimeError('NATIVE_PROBE_PENDING_UNKNOWN'))
            else:
                while self.handles:
                    try:a.budget(self.lease,cleanup=True)
                    except BaseException as error:
                        cleanup.append(error);break
                    h=self.handles.pop()
                    try:self.api.close(h)
                    except BaseException as error:cleanup.append(error)
        if primary is not None or cleanup:
            self.failed=True;_retained.append(self)
            raise BaseExceptionGroup('NATIVE_SLOT_PROBE_UNKNOWN',([primary] if primary else [])+cleanup)
        _completed[self]=(self.lease,observed)
        from .native_trial_facts import completed_slot_probes
        return completed_slot_probes(self.lease,self)


class _SlotIO:
    journal_format=j.FixedFormat.INSTANCE_V2
    def __init__(self,probe,node,lock):
        self.probe,self.node,self.lock=probe,node,lock
        self.root_id=list(probe.lease.fs.root_id)
        self.lock_id=list(require_original_creation(probe.api,lock).identity)
    def verify(self):self.probe._verify()
    def identity(self):return list(require_original_creation(self.probe.api,self.node).identity)
    def length(self):self.verify();return self.probe.api.info(self.node).size
    def signature(self):
        self.verify();info=FileInfo();self.probe.api.need(self.probe.api.getinfo(self.node,C.byref(info)))
        return (info.Attributes,info.Creation.Low,info.Creation.High,info.Write.Low,info.Write.High,
            info.Volume,info.SizeHigh,info.SizeLow,info.Links,info.IndexHigh,info.IndexLow)
    def read_at(self,offset,count):return self.probe._read(self.node,offset,count)
    def write_at(self,offset,raw):return self.probe._write(self.node,offset,raw)
    def flush_file(self):self.probe._flush(self.node)
