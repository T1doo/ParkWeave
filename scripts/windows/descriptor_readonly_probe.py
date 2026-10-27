"""Two bounded reads of a caller-held existing READ_CONTROL handle.

No open/create/setter, SACL query, privilege or raw descriptor output. Ordered
ACE equality excludes unused storage for observation only; strict contract does
not. A caller must already have verified the exact object and retain the handle.
"""
import ctypes
import os
import math
import time
from dataclasses import dataclass

from .owner_descriptor_observation import CONTROL_BITS, compare_acl_control

DWORD=ctypes.c_uint32
HANDLE=ctypes.c_void_p
MAX_HANDLE=(1 << (ctypes.sizeof(HANDLE)*8))-1


@dataclass(frozen=True)
class Snapshot:
    acl: bytes | None
    control: int


class AclSizeInformation(ctypes.Structure):
    _fields_=[('count',DWORD),('used',DWORD),('free',DWORD)]


class NativeReader:
    def __init__(self):
        if os.name!='nt':raise RuntimeError('WINDOWS_REQUIRED')
        self.api=ctypes.WinDLL('advapi32',use_last_error=True)
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        pointer=ctypes.c_void_p
        declarations={
            'GetSecurityInfo':([HANDLE,ctypes.c_int,DWORD,ctypes.POINTER(pointer),pointer,ctypes.POINTER(pointer),pointer,ctypes.POINTER(pointer)],DWORD),
            'GetSecurityDescriptorControl':([pointer,ctypes.POINTER(ctypes.c_uint16),ctypes.POINTER(DWORD)],ctypes.c_int32),
            'IsValidAcl':([pointer],ctypes.c_int32),
            'GetAclInformation':([pointer,pointer,DWORD,ctypes.c_int],ctypes.c_int32),
            'GetAce':([pointer,DWORD,ctypes.POINTER(pointer)],ctypes.c_int32),
        }
        for name,(args,result) in declarations.items():
            function=getattr(self.api,name);function.argtypes=args;function.restype=result
        self.kernel.LocalFree.argtypes=[pointer];self.kernel.LocalFree.restype=pointer

    def snapshot(self,handle):
        if type(handle) is not int or not 0<handle<=MAX_HANDLE:raise ValueError('READ_REFUSED')
        owner,dacl,descriptor=(ctypes.c_void_p() for _ in range(3))
        # Same existing OWNER|DACL query flags; never ask for SACL or write access.
        if self.api.GetSecurityInfo(handle,1,1|4,ctypes.byref(owner),None,ctypes.byref(dacl),None,ctypes.byref(descriptor)):
            raise RuntimeError('READ_REFUSED')
        try:
            if not descriptor.value:raise ValueError('READ_REFUSED')
            control,revision=ctypes.c_uint16(),DWORD()
            if not self.api.GetSecurityDescriptorControl(descriptor,ctypes.byref(control),ctypes.byref(revision)):
                raise RuntimeError('READ_REFUSED')
            if not dacl.value:return Snapshot(None,control.value)
            if not self.api.IsValidAcl(dacl):raise ValueError('READ_REFUSED')
            size=ctypes.c_uint16.from_address(dacl.value+2).value
            if not 8<=size<=65535 or size%4:raise ValueError('READ_REFUSED')
            info=AclSizeInformation()
            if not self.api.GetAclInformation(dacl,ctypes.byref(info),ctypes.sizeof(info),2):raise RuntimeError('READ_REFUSED')
            if not 8<=info.used<=size or info.used+info.free!=size or info.count>(size-8)//4:raise ValueError('READ_REFUSED')
            cursor=dacl.value+8
            for index in range(info.count):
                ace=ctypes.c_void_p()
                if not self.api.GetAce(dacl,index,ctypes.byref(ace)):raise RuntimeError('READ_REFUSED')
                if ace.value!=cursor or cursor+4>dacl.value+info.used:raise ValueError('READ_REFUSED')
                length=ctypes.c_uint16.from_address(cursor+2).value
                if length<4 or length%4 or cursor+length>dacl.value+info.used:raise ValueError('READ_REFUSED')
                cursor+=length
            if cursor!=dacl.value+info.used:raise ValueError('READ_REFUSED')
            return Snapshot(ctypes.string_at(dacl,size),control.value)
        finally:
            if descriptor.value and self.kernel.LocalFree(descriptor):raise RuntimeError('READ_REFUSED')


def diagnose_existing_handle(handle,*,backend,clock=time.monotonic):
    """Never acquire handles; two reads, fixed five-second observation budget.

    Calls cannot be preempted. A read that returns after deadline is refused.
    Results contain only fixed names, booleans and bounded counts, no ACL/SID.
    """
    result={'scope':'EXISTING_DESCRIPTOR_READONLY_AB','status':'UNAVAILABLE',
            'reason':'READ_REFUSED','read_count':0,'historical_owner_transition':'NOT_MEASURED',
            'semantic_permission_change':'UNKNOWN','sacl_content':'NOT_QUERIED',
            'owner_content':'NOT_COMPARED','object_identity':'CALLER_PINNED_NOT_MEASURED'}
    if type(handle) is not int or not 0<handle<=MAX_HANDLE:
        result['reason']='INVALID_HANDLE';return result
    try:
        started=clock()
        if type(started) not in (int,float) or not math.isfinite(started):raise ValueError()
        snapshots=[]
        for _ in range(2):
            now=clock()
            if not started<=now<started+5:result['reason']='DEADLINE';return result
            value=backend.snapshot(handle);result['read_count']+=1
            now=clock()
            if not started<=now<started+5:result['reason']='DEADLINE';return result
            if not isinstance(value,Snapshot):raise ValueError()
            snapshots.append(value)
        first,second=snapshots
        comparison=compare_acl_control(first.acl,first.control,second.acl,second.control)
        if comparison['acl_observation']!='AVAILABLE' or comparison['control_observation']!='AVAILABLE':return result
        result.update(comparison,status='AVAILABLE',reason='NONE',
            control_bits_A=[name for bit,name in CONTROL_BITS if first.control&bit],
            control_bits_B=[name for bit,name in CONTROL_BITS if second.control&bit],
            unknown_control_bits_A=bool(first.control&0xc0),unknown_control_bits_B=bool(second.control&0xc0),
            raw_read_stable=first.acl==second.acl and first.control==second.control,
            normalized_dacl='ORDERED_COMPLETE_ACE_BYTES_NO_REORDER')
        # Keep original probe scope; comparison's scope names a helper only.
        result['scope']='EXISTING_DESCRIPTOR_READONLY_AB'
        return result
    except Exception:
        return result


def main(argv=None):
    """Optional inherited-handle entry, never a pathname or permission request."""
    import json,sys
    args=sys.argv[1:] if argv is None else argv
    refusal={'scope':'EXISTING_DESCRIPTOR_READONLY_AB','status':'UNAVAILABLE','reason':'EXISTING_HANDLE_REQUIRED'}
    if (len(args)!=2 or args[0]!='--held-handle' or not args[1].isascii()
            or not args[1].isdigit() or len(args[1])>20):
        print(json.dumps(refusal,separators=(',',':')));return 1
    try:reader=NativeReader()
    except Exception:
        refusal['reason']='WINDOWS_REQUIRED' if os.name!='nt' else 'READ_REFUSED'
        print(json.dumps(refusal,separators=(',',':')));return 1
    row=diagnose_existing_handle(int(args[1]),backend=reader)
    print(json.dumps(row,separators=(',',':')))
    return 0 if row['status']=='AVAILABLE' else 1


if __name__=='__main__':raise SystemExit(main())
