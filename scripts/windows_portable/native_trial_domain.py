"""Persistent TRIAL_ONLY domain, checked through the original root HANDLE.

Production acquisition refuses a marked root even after a future acceptance
gate opens. A trial cannot adopt an existing unmarked root or manufacture a
marker on REOPEN. No marker deletion/repair or path-following fallback exists.
"""
import ctypes as C
from hashlib import sha256
import json

from parkweave.windows_handles import (PTR, UnicodeString, ObjectAttributes, IOStatus,
    nt_status, completed_nt_handle, require_nt_create_ready, retain_pending_nt_create)
from . import native_trial_authority as authority
from .directories import LeaseRefused
from .native_protected_objects import create, require_original_creation, _identity,submit_create

MARKER = '.parkweave-trial-only'


def need(value):
    if not value: raise LeaseRefused('TRIAL_ONLY_DOMAIN_REFUSED')


def _open_optional(api, parent):
    require_nt_create_ready(api.readonly)
    raw = MARKER.encode('utf-16-le'); text = C.create_string_buffer(raw+b'\0\0')
    name = UnicodeString(len(raw),len(raw)+2,C.cast(text,PTR))
    attrs = ObjectAttributes(C.sizeof(ObjectAttributes),parent,C.pointer(name),0x40,None,None)
    handle, io = PTR(), IOStatus()
    status=submit_create(api,handle,io,attrs,(name,text),access=0x120081,attributes=0x80,
        share=1,disposition=1,options=0x20|0x200000|0x40)
    if status == nt_status(0xc0000034) and not handle.value: return None  # Exact final-name absence only.
    owned = completed_nt_handle(status,handle.value)
    if status != 0 or not owned or io.Information != 1:
        primary = LeaseRefused('TRIAL_MARKER_OPEN_REFUSED')
        if owned:
            try: api.close(handle.value)
            except BaseException as cleanup:
                raise BaseExceptionGroup('TRIAL_MARKER_OPEN_CLOSE_UNKNOWN',[primary,cleanup]) from None
        raise primary
    return handle.value


def require_domain(filesystem, *, fresh):
    value = authority.bound_state(filesystem)
    api, root = filesystem.api, filesystem.root
    handle = _open_optional(api, root)
    if handle is not None:
        filesystem.hold(handle)  # Retain before any fallible identity/content query.
    if value is None:
        need(handle is None)  # Formal startup can NEVER adopt TRIAL_ONLY data.
        return
    need(value.root is not None and filesystem.base == str(value.parent)
         and api.final_path(root).endswith('\\'+value.root.rsplit('\\',1)[1]))
    expected = json.dumps(dict(domain='TRIAL_ONLY',schema=1,trial_key=value.key,
        source_commit=value.manifest['source_commit'],manifest_sha256=value.window.manifest_sha256,
        root_identity=list(_identity(api,root,True))),sort_keys=True,separators=(',',':')).encode('ascii')
    if fresh:
        need(handle is None and value.marker is None and not value.generations)
        require_original_creation(api,root)
        handle = filesystem.hold(create(api,root,MARKER,directory=False,write=True))
        count = C.c_uint32(); buffer = C.create_string_buffer(expected)
        api.need(api.writefile(handle,buffer,len(expected),C.byref(count),None));need(count.value==len(expected))
        api.flush(handle)
    else:
        need(handle is not None and value.marker is not None and value.restart_ready)
        need(len(value.generations)==1 and not value.generations[0].active)
    identity, descriptor = _identity(api,handle,False), api.descriptor(handle)
    need(api.info(handle).size == len(expected) and api.final_path(handle)==api.final_path(root).rstrip('\\')+'\\'+MARKER)
    seek = api.readonly.k.SetFilePointerEx
    seek.argtypes,seek.restype=[PTR,C.c_int64,PTR,C.c_uint32],C.c_int32
    api.need(seek(handle,0,None,0));raw=api.read(handle,len(expected)+1)
    need(raw==expected and _identity(api,handle,False)==identity and api.descriptor(handle)==descriptor)
    observed=(identity,descriptor,sha256(raw).hexdigest())
    if fresh:value.marker=observed
    else:need(value.marker==observed)
