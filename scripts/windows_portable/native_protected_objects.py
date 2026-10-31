"""FILE_CREATE with explicit current-user protection; never an ACL setter.

Used only after the original NEW admission. An inherited/default descriptor is
not sufficient: Windows can otherwise choose an Administrators owner and an
unprotected inherited DACL. Original parent/child HANDLEs are verified before
the creation observation is issued. Existing objects are never adopted.
"""
import ctypes as C
from dataclasses import dataclass
import struct
import weakref

from parkweave.windows_files import component, private_acl, DIRECTORY, REPARSE, UNSAFE_ATTRIBUTES
from parkweave.windows_handles import (PTR, UnicodeString, ObjectAttributes, IOStatus,
    nt_status, completed_nt_handle, require_nt_create_ready, retain_pending_nt_create)
from .directories import LeaseRefused


@dataclass(frozen=True)
class _Created:
    parent: int
    parent_identity: tuple
    parent_descriptor: tuple
    identity: tuple
    descriptor: tuple
    path: str
    directory: bool


_created = weakref.WeakKeyDictionary()
_unknown = []
_inflight = {}  # Bounded original call storage, including completed transfers.


def need(value):
    if not value: raise LeaseRefused('NATIVE_PROTECTED_CREATE_REFUSED')


def submit_create(api,handle,io,attrs,buffers,*,access,attributes,share,disposition,options):
    # Register PHANDLE/IOSB/OBJECT_ATTRIBUTES and all pointed storage BEFORE
    # entering ctypes. An interrupted/exceptional syscall outcome is UNKNOWN,
    # even if the currently readable output looks empty. Never guess/close it.
    need(len(_inflight)<4096)
    storage=(api,handle,io,attrs,*buffers);key=id(storage);_inflight[key]=storage
    try:
        status=nt_status(api.ntcreate(C.byref(handle),access,C.byref(attrs),C.byref(io),None,
            attributes,share,disposition,options,None,0))
    except BaseException:
        retain_pending_nt_create(api.readonly,handle,io,attrs,*buffers)
        _unknown.append(storage)
        raise LeaseRefused('NATIVE_CREATE_CALL_OUTCOME_UNKNOWN') from None
    if status==0x103:
        retain_pending_nt_create(api.readonly,handle,io,attrs,*buffers)
        _unknown.append(storage)
        raise LeaseRefused('NATIVE_CREATE_PENDING_UNKNOWN')
    # Keep the original outputs alive even across an asynchronous interruption
    # between returning status and the caller registering the returned HANDLE.
    # This table never closes/retries a handle; actual ownership is elsewhere.
    return status


def sid_bytes(text):
    """Canonical binary form of the original API's already queried user SID."""
    need(type(text) is str)
    parts = text.split('-')
    need(4 <= len(parts) <= 18 and parts[:2] == ['S', '1']
         and all(p.isascii() and p.isdigit() and str(int(p)) == p for p in parts[2:]))
    values = [int(p) for p in parts[2:]]
    need(values[0] < 2**48 and all(v < 2**32 for v in values[1:]))
    return bytes((1, len(values)-1)) + values[0].to_bytes(6, 'big') + b''.join(struct.pack('<I', v) for v in values[1:])


def _identity(api, handle, directory):
    info = api.info(handle)
    need(bool(info.attributes & DIRECTORY) == directory and not info.attributes & (REPARSE | UNSAFE_ATTRIBUTES)
         and info.identity > 0 and (directory or info.links == 1))
    private_acl(api.security(handle), api.user_sid())
    return info.volume, info.identity


def create(api, parent, name, *, directory, write=False, exclusive=False, rename=False):
    from .fixed_windows_journal import NativeFixedLeaseAPI
    from .native_secret_store_candidate import private_file_descriptor
    need(type(api) is NativeFixedLeaseAPI and type(directory) is bool)
    from .native_trial_authority import require_creation_target
    require_creation_target(api,parent,name,directory=directory)
    component(name); require_nt_create_ready(api.readonly)
    parent_id = _identity(api, parent, True)
    parent_sd, parent_path, user = api.descriptor(parent), api.final_path(parent), api.user_sid()
    raw_sid = sid_bytes(user)
    text = C.create_string_buffer(name.encode('utf-16-le') + b'\0\0')
    unicode = UnicodeString(len(name.encode('utf-16-le')), len(name.encode('utf-16-le'))+2, C.cast(text, PTR))
    sd = C.create_string_buffer(private_file_descriptor(raw_sid))
    attrs = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(unicode), 0x40, C.cast(sd, PTR), None)
    handle, io = PTR(), IOStatus()
    access = 0x120081 | (0x40000000 if write else 0) | (0x10000 if rename else 0)
    options = 0x20 | 0x200000 | (1 if directory else 0x40) | (2 if write else 0)
    status=submit_create(api,handle,io,attrs,(unicode,text,sd),access=access,
        attributes=0x10 if directory else 0x80,share=0 if exclusive else 1,disposition=2,options=options)
    owned = completed_nt_handle(status, handle.value)
    try:
        need(status == 0 and owned and io.Information == 2)
        child_id = _identity(api, handle.value, directory)
        child_sd, path = api.descriptor(handle.value), api.final_path(handle.value)
        need(child_id[0] == parent_id[0] and child_id != parent_id and api.user_sid() == user
             and child_sd[0] == user and child_sd[1] & ~1 in (0x1004, 0x9004)
             and child_sd[2] == private_file_descriptor(raw_sid)[20+len(raw_sid):]
             and path == parent_path.rstrip('\\')+'\\'+name
             and _identity(api, parent, True) == parent_id and api.descriptor(parent) == parent_sd
             and api.final_path(parent) == parent_path)
        _created.setdefault(api, {})[handle.value] = _Created(parent, parent_id, parent_sd,
            child_id, child_sd, path, directory)
        return handle.value
    except BaseException as primary:
        if owned:
            try: api.close(handle.value)
            except BaseException as cleanup:
                _unknown.append((api, handle.value))
                raise BaseExceptionGroup('PROTECTED_CREATE_CLOSE_UNKNOWN', [primary, cleanup]) from None
        raise


def require_original_creation(api, handle):
    row = _created.get(api, {}).get(handle)
    need(row is not None and _identity(api, handle, row.directory) == row.identity
         and api.descriptor(handle) == row.descriptor and api.final_path(handle) == row.path
         and _identity(api, row.parent, True) == row.parent_identity
         and api.descriptor(row.parent) == row.parent_descriptor)
    return row
