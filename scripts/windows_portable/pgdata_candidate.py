"""Unwired NEW-only PGDATA capability, native execution NOT_ACCEPTED.

Dedicated policy, not windows_files.private_acl relaxation: a protected root
with one concrete current-user OI/CI ACE; descendants inherit that exact ACE.
No generic rights/CREATOR_OWNER/extra principals, conversion or ACL repair.
Checks are cooperative observations, not an atomic snapshot or protection
against malicious same-user/admin mutation. No resume, password or PG calls.
Reopen remains refused: authenticated persistent profile publication is not
implemented by this invocation-local capability. No directory durability claim.
"""
import ctypes as C
from dataclasses import dataclass
import hashlib
import math
import os
import re
import struct
import time
import weakref

from parkweave.windows_files import (Ace, Security, DIRECTORY, REPARSE,
    UNSAFE_ATTRIBUTES, PROTECTED, DACL_PRESENT, component, private_acl)
from parkweave.windows_handles import (UnicodeString, ObjectAttributes, IOStatus, PTR,
    completed_nt_handle,require_nt_create_ready,retain_pending_nt_create,
    query_call,require_query_ready,retain_query_unknown)
from .default_dacl_candidate import _sid_buffer
from .endpoint_plan import _key_held
from .fixed_directories import FixedDirectoryLease, _exclusive_entry, _exclusive_operation
from .fixed_windows_journal import FixedWindowsFilesystem, NativeFixedLeaseAPI

PROFILE = 'parkweave-pgdata-current-user-inheritance/1'
FILE_ALL = 0x1f01ff


class DataRefused(RuntimeError):
    pass


def _need(ok):
    if not ok: raise DataRefused('PRIVATE_PGDATA_REFUSED')


def _sid_text(raw):
    _sid_buffer(raw)
    return 'S-1-' + str(int.from_bytes(raw[2:8], 'big')) + ''.join(
        '-'+str(x[0]) for x in struct.iter_unpack('<I', raw[8:]))


def root_descriptor(sid):
    """Self-relative descriptor bytes only; not a current-user credential."""
    _sid_buffer(sid)
    ace = struct.pack('<BBHI', 0, 3, 8+len(sid), FILE_ALL) + sid
    acl = struct.pack('<BBHHH', 2, 0, 8+len(ace), 1, 0) + ace
    return struct.pack('<BBHIIII', 1, 0, 0x9004, 20, 0, 0, 20+len(sid)) + sid + acl


def check_descriptor(value, sid, *, root, directory):
    _need(type(value) is tuple and len(value) == 3)
    owner, control, raw = value
    flags = 3 if root else (0x13 if directory else 0x10)
    ace = struct.pack('<BBHI', 0, flags, 8+len(sid), FILE_ALL) + sid
    expected = struct.pack('<BBHHH', 2, 0, 8+len(ace), 1, 0) + ace
    check_security(Security(owner, control, (Ace(0, flags, FILE_ALL, _sid_text(sid)),)),
                   _sid_text(sid), root=root, directory=directory)
    _need(type(raw) is bytes and raw == expected)  # No ignored payload/free ACE area.


def pg_command_path(value):
    """A conservative DOS argv representation, never filesystem authority."""
    _need(type(value) is str and re.match(r'^\\\\\?\\[A-Za-z]:\\', value) is not None)
    path = value[4:]
    _need(len(path.encode('utf-16-le', errors='strict'))//2 <= 240)
    parts = path[3:].split('\\')
    _need(parts and len(parts) <= 64)
    for part in parts: component(part)
    return path.replace('\\', '/'), path[:3], tuple(parts)


def descriptor_digest(value):
    from .credential_envelope import canonical
    owner, control, raw = value
    return hashlib.sha256(canonical([owner, control, raw.hex()])).hexdigest()


def check_security(value, user, *, root, directory):
    _need(type(value) is Security and type(user) is str and
          re.fullmatch(r'S-1-[0-9]+(?:-[0-9]+){1,15}', user) is not None)
    # Concrete FILE_ALL and concrete user SID have no generic mapping or
    # effective/inherit-only splitting. Reject all broader ACL shapes.
    flags = 3 if root else (0x13 if directory else 0x10)
    _need(value.owner == user and type(value.control) is int and
          value.control & DACL_PRESENT and
          bool(value.control & PROTECTED) == root and
          value.control & ~(0x8000|0x1000|0x400|0x4) == 0 and
          type(value.aces) is tuple and value.aces == (Ace(0, flags, FILE_ALL, user),))


def _metadata(info, volume, *, directory):
    _need(type(info.volume) is int and info.volume == volume and
          type(info.identity) is int and 0 < info.identity < 2**64 and
          type(info.attributes) is int and not info.attributes & (REPARSE|UNSAFE_ATTRIBUTES) and
          bool(info.attributes & DIRECTORY) == directory and
          (directory or info.links == 1))
    return (info.volume, info.identity)


def directory_batch(raw):
    """Bounded FILE_ID_BOTH_DIR_INFO parsing, Windows WCHAR always 16 bits."""
    _need(type(raw) is bytes and 104 <= len(raw) <= 65536)
    result, offset, seen = [], 0, set()
    while True:
        _need(offset+104 <= len(raw))
        advance = struct.unpack_from('<I', raw, offset)[0]
        attrs, length = struct.unpack_from('<II', raw, offset+56)
        identity = struct.unpack_from('<Q', raw, offset+96)[0]
        short = raw[offset+68]
        _need(0 < length <= 510 and length % 2 == 0 and short <= 24 and short % 2 == 0)
        end = offset+104+length
        _need(end <= len(raw) and (not advance or advance % 8 == 0 and advance >= 104+length and offset+advance+104 <= len(raw)))
        name = raw[offset+104:end].decode('utf-16-le', errors='strict')
        if name not in ('.', '..'):
            component(name)
            _need(name.casefold() not in seen and identity > 0)
            seen.add(name.casefold()); result.append((name, attrs, identity))
        if not advance: return tuple(result)
        offset += advance


@dataclass(frozen=True, repr=False)
class _Binding:
    key: tuple
    user: str
    sid: bytes
    data_id: tuple
    root_id: tuple
    data_sd: tuple
    root_sd: tuple
    path: str
    command_path: str
    command_chain: tuple
    profile: str = PROFILE


_issued = weakref.WeakKeyDictionary()
_by_lease = weakref.WeakKeyDictionary()
_unknown_targets = []  # Retain original pins/buffers after unacknowledged native IO.


def native_pgdata():
    raise DataRefused('NATIVE_PGDATA_NOT_ACCEPTED')


@_exclusive_entry
def _create_entry(lease, target, *, layout):
    return _create_target_held(lease,target,layout=layout)


@_exclusive_operation
def _create_target_held(lease,target,*,layout):
    _need(type(lease) is FixedDirectoryLease and type(lease.fs) is FixedWindowsFilesystem
          and type(lease.fs.api) is NativeFixedLeaseAPI and type(target) is _NewDataTarget and target.lease is lease)
    _need(lease not in _by_lease)
    _by_lease[lease] = target  # One attempt, including an unknown create outcome.
    try:
        target.layout=layout  # Freeze only after entry and single-attempt ownership.
        key = _key_held(lease)
        _need(key[-1] == 1 and lease.record['phase'] == 'CLUSTER' and not lease.record['initialized'])
        target._create_native(key)
    except BaseException:
        target._fail()
        raise


@_exclusive_operation
def _path_held(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease and _by_lease.get(lease) is target)
    try:
        binding = target._verify()
        return binding.command_path
    except BaseException:
        target._fail()
        raise


@_exclusive_entry
def _scan_entry(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease and _by_lease.get(lease) is target)
    try:
        before = target._walk()
        _need(target._walk() == before)  # Stable selected metadata, not DB contents.
        target._verify()
        return len(before)
    except BaseException:
        target._fail()
        raise


@_exclusive_entry
def _close_entry(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease)
    target._close_native()


@_exclusive_operation
def _profile_held(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease and _by_lease.get(lease) is target)
    try:
        binding = target._verify()
        _need(binding.key[-1] == 1)  # Invocation-local NEW capability only.
        return dict(profile=PROFILE, instance_id=binding.key[0], sid=binding.user,
                    parent_identity=list(binding.data_id), root_identity=list(binding.root_id),
                    root_control=binding.root_sd[1], root_security_sha256=descriptor_digest(binding.root_sd))
    except BaseException:
        target._fail()
        raise


@_exclusive_operation
def _recover_held(lease, ticket, deadline):
    from .native_secret_store_candidate import _consume_ticket
    store,state,_ = _consume_ticket(lease,ticket,'PGDATA')
    _need(type(lease) is FixedDirectoryLease and type(lease.fs) is FixedWindowsFilesystem
          and type(lease.fs.api) is NativeFixedLeaseAPI and lease not in _by_lease)
    key=_key_held(lease)
    _need(key[-1]>=2 and lease.record['phase']=='READY_STOPPED' and lease.record['initialized'] is True
          and lease.record['runtime']=='STOPPED')
    target=_NewDataTarget(lease,deadline)
    _by_lease[lease]=target  # One recovery attempt, not a missing-directory creation route.
    try:
        profile=state.config['pgdata']
        # Revalidate the exact authenticated schema, never an imported profile dict.
        from .credential_envelope import validate_payload, Purpose, ConfigFormat
        validate_payload(store.binding,Purpose.CONFIG,state.config,config_format=ConfigFormat.PGDATA_SCHEMA4)
        _need(profile['instance_id']==key[0] and profile['sid']==store.binding.sid)
        target.user=store.binding.sid
        sid=store.api.sid_bytes
        target.data=target._open(lease.fs.root,'data',anchor=True)
        data_id=target._identity(target.data,directory=True)
        private_acl(target.api.security(target.data),target.user)
        data_sd=target.api.descriptor(target.data)
        _need(data_id==tuple(profile['parent_identity']))
        target.root=target._open(target.data,'postgresql',anchor=True)  # FILE_OPEN only.
        root_id=target._identity(target.root,directory=True)
        _need(root_id==tuple(profile['root_identity'])==tuple(state.config['database']['data_identity']))
        root_sd=target.api.descriptor(target.root)
        check_descriptor(root_sd,sid,root=True,directory=True)
        _need(root_sd[1]==profile['root_control'] and descriptor_digest(root_sd)==profile['root_security_sha256'])
        path=target.api.final_path(lease.fs.root).rstrip('\\')+'\\data\\postgresql'
        _need(target.api.final_path(target.data)==target.api.final_path(lease.fs.root).rstrip('\\')+'\\data'
              and target.api.final_path(target.root)==path)
        command_path,chain=target._pin_command_path(root_id,path)
        _issued[target]=_Binding(key,target.user,sid,data_id,root_id,data_sd,root_sd,path,command_path,chain)
        target._verify()
        # Journal STOPPED is the lifecycle precondition, not independent proof
        # of zero OS processes. These are cooperative selected observations.
        before=target._walk();_need(target._walk()==before)
        target._verify();store._native_check()
        target.outcome='REOPEN_OBSERVED_NOT_NATIVE_ACCEPTANCE'
        return target
    except BaseException:
        target._fail();raise


class _NewDataTarget:
    native_acceptance = False
    launch_ready = False

    def __init__(self, lease, deadline):
        _need(os.name == 'nt' and C.sizeof(PTR) == 8 and type(lease) is FixedDirectoryLease)
        _need(type(deadline) in (int, float) and math.isfinite(deadline))
        self.lease, self.deadline = lease, deadline
        self.handles, self.data, self.root = [], None, None
        self.failed, self.closed, self.outcome, self.cleanup_errors = False, False, 'NOT_CREATED', []
        self.api = lease.fs.api
        _need(type(self.api) is NativeFixedLeaseAPI)
        self.query = self.api.k.GetFileInformationByHandleEx
        self.query.argtypes, self.query.restype = [PTR, C.c_int32, PTR, C.c_uint32], C.c_int32

    def __reduce__(self): raise TypeError('PGDATA_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('PGDATA_NOT_TRANSFERABLE')
    def __deepcopy__(self, memo): raise TypeError('PGDATA_NOT_TRANSFERABLE')

    def create(self,*,layout):
        _create_entry(self.lease, self,layout=layout)

    def scan_stopped(self):
        # Caller must independently establish owned PG stopped. This method
        # neither establishes that fact nor authorizes resume or credentials.
        return _scan_entry(self.lease, self)

    def _time(self):
        require_nt_create_ready(self.api.readonly)
        require_query_ready(self.api.readonly)
        _need(time.monotonic() < self.deadline)

    def _query(self,function,*args):
        self._time()
        value=function(*args)
        self._time()
        return value

    def _open(self, parent, name, *, create=False, descriptor=None, anchor=False):
        self._time(); component(name)
        require_nt_create_ready(self.api.readonly)
        raw = name.encode('utf-16-le'); text = C.create_string_buffer(raw+b'\0\0')
        unicode = UnicodeString(len(raw), len(raw)+2, C.cast(text, PTR))
        sd = C.create_string_buffer(descriptor) if descriptor is not None else None
        attrs = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(unicode),
                                 0x40, C.cast(sd, PTR) if sd is not None else None, None)
        handle, io = PTR(), IOStatus()
        from .native_protected_objects import submit_create,transfer_completed_create
        self._time()
        status=submit_create(self.api,handle,io,attrs,(unicode,text,sd),access=0x120081,
            attributes=0x10 if create else 0,share=3 if anchor else 7,
            disposition=2 if create else 1,options=0x20|0x200000|(1 if create else 0))
        if status==0 and io.Status not in (None,0):
            retain_pending_nt_create(self.api.readonly,handle,io,attrs,unicode,text,sd)
            _need(False)
        owned=completed_nt_handle(status,handle.value)
        if not owned and (status>=0 or handle.value not in (None,0)):
            retain_pending_nt_create(self.api.readonly,handle,io,attrs,unicode,text,sd)
        if owned:self.handles.append(handle.value)
        transfer_completed_create(self.api,handle,io,attrs,self.handles)
        self._time()
        _need(status==0 and owned)  # Information-success is owned, but not admitted.
        if create: _need(io.Information == 2)  # FILE_CREATED, never OPEN_IF.
        return handle.value

    def _identity(self, handle, *, directory):
        info = self._query(self.api.info,handle)
        return _metadata(info, self.lease.fs.root_id[0], directory=directory)

    def _dos_path(self):
        self._time()
        buffer = C.create_unicode_buffer(4096)
        count=query_call(self.api.readonly,'PGDATA_DOS_PATH',self.api.getpath,
            (self.root,buffer,len(buffer),0),(self,buffer))  # VOLUME_NAME_DOS.
        self._time()
        _need(0 < count < len(buffer))
        return pg_command_path(buffer.value)

    def _pin_command_path(self, root_id, guid_path):
        before, drive, parts = self._dos_path()
        self._time()
        handle = self.api.open_drive(drive)
        self.handles.append(handle)
        self._time()
        chain = []
        for name in (None, *parts):
            if name is not None: handle = self._open(handle, name, anchor=True)
            identity = self._identity(handle, directory=True)
            chain.append((handle, identity, self._query(self.api.descriptor,handle)))
        _need(chain[-1][1] == root_id and self._query(self.api.final_path,handle) == guid_path and
              self._dos_path()[0] == before)
        return before, tuple(chain)  # Held until this target closes, not just path resolution.

    def _current_user_sid(self):
        self._time()
        # Read the actual current TOKEN_USER through existing API; never accept
        # an imported SID or substitute token owner for the user principal.
        token, used, primary, cleanup = PTR(), C.c_uint32(), None, None
        self._user_token=token  # Preserve original output even before ownership classification.
        opened=query_call(self.api.readonly,'PGDATA_USER_TOKEN',self.api.opentoken,
            (self.api.process(),8,C.byref(token)),(self,token))
        valid=type(token.value) is int and 0<token.value<PTR(-1).value-15
        if (not opened and token.value not in (None,0)) or (opened and not valid):
            retain_query_unknown(self.api.readonly,'PGDATA_USER_TOKEN_OUTPUT',self,token)
            _need(False)
        self.api.need(opened);_need(valid)
        self.handles.append(token.value)
        try:
            self._time()
            buffer = C.create_string_buffer(4096)
            self.api.need(query_call(self.api.readonly,'PGDATA_USER_SID',self.api.tokeninfo,
                (token,1,buffer,len(buffer),C.byref(used)),(self,token,buffer,used)))
            from .restricted_token_candidate import _parse
            sid = _parse(buffer, used.value, 1)
            _need(_sid_text(sid) == self.user)
        except BaseException as error:
            primary = error
        finally:
            try:
                self._close_one(token.value)
            except BaseException as error:
                cleanup = error
                self.cleanup_errors.append(('TOKEN_CLOSE_UNKNOWN', token.value))
        if primary is not None or cleanup is not None:
            raise BaseExceptionGroup('PGDATA_USER_QUERY_UNKNOWN',
                                     [x for x in (primary, cleanup) if x is not None])
        return sid

    def _create_native(self, key):
        self.lease._verify()
        from .native_layout_candidate import _leaf_held
        _,_,expected_data,expected_sd=_leaf_held(self.lease,self.layout,'data')
        self.user = self._query(self.api.user_sid)
        sid=self._current_user_sid()
        self.data = self._open(self.lease.fs.root, 'data', anchor=True)
        data_id = self._identity(self.data, directory=True)
        private_acl(self._query(self.api.security,self.data), self.user)
        data_sd = self._query(self.api.descriptor,self.data)
        _need(data_id==expected_data and data_sd==expected_sd)
        _need(self._query(self.api.final_path,self.data) == self._query(self.api.final_path,self.lease.fs.root).rstrip('\\')+'\\data')
        self.root = self._open(self.data, 'postgresql', create=True,
                              descriptor=root_descriptor(sid), anchor=True)
        root_id = self._identity(self.root, directory=True)
        _need(len({tuple(self.lease.fs.root_id), data_id, root_id}) == 3)
        check_security(self._query(self.api.security,self.root), self.user, root=True, directory=True)
        root_sd = self._query(self.api.descriptor,self.root)
        path = self._query(self.api.final_path,self.data).rstrip('\\')+'\\postgresql'
        _need(self._query(self.api.final_path,self.root) == path)
        check_descriptor(root_sd, sid, root=True, directory=True)
        command_path, chain = self._pin_command_path(root_id, path)
        binding = _Binding(key, self.user, sid, data_id, root_id, data_sd, root_sd, path, command_path, chain)
        _issued[self] = binding
        self._verify()
        _need(self._entries(self.root) == ())  # Only this invocation's new empty root.
        self._verify()
        self.outcome = 'NEW_ROOT_OBSERVED_NOT_NATIVE_ACCEPTANCE'

    def _verify(self):
        self._time()
        _need(not self.closed and not self.failed and _by_lease.get(self.lease) is self)
        binding = _issued.get(self)
        _need(binding is not None and binding.profile == PROFILE and _key_held(self.lease) == binding.key)
        self.lease._verify()
        _need(self.api is self.lease.fs.api and self._query(self.api.user_sid) == binding.user and
              self._identity(self.data, directory=True) == binding.data_id and
              self._identity(self.root, directory=True) == binding.root_id and
              self._query(self.api.descriptor,self.data) == binding.data_sd and
              self._query(self.api.descriptor,self.root) == binding.root_sd and
              self._query(self.api.final_path,self.data) == self._query(self.api.final_path,self.lease.fs.root).rstrip('\\')+'\\data' and
              self._query(self.api.final_path,self.root) == binding.path)
        check_security(self._query(self.api.security,self.root), binding.user, root=True, directory=True)
        if binding.key[-1]==1:
            from .native_layout_candidate import _leaf_held
            _,_,identity,sd=_leaf_held(self.lease,self.layout,'data')
            _need(identity==binding.data_id and sd==binding.data_sd)
        for handle, identity, descriptor in binding.command_chain:
            _need(self._identity(handle, directory=True) == identity and self._query(self.api.descriptor,handle) == descriptor)
        _need(self._dos_path()[0] == binding.command_path)
        self.lease._verify()
        return binding

    def _entries(self, handle):
        rows, seen, restart = [], set(), True
        for _ in range(4096):
            self._time()
            buffer = C.create_string_buffer(65536)
            ok=query_call(self.api.readonly,'PGDATA_DIRECTORY_ENTRIES',self.query,
                (handle,11 if restart else 10,buffer,len(buffer)),(self,handle,buffer))
            self._time()
            if not ok:
                _need(C.get_last_error() == 18)  # ERROR_NO_MORE_FILES only.
                return tuple(sorted(rows))
            restart = False
            for row in directory_batch(buffer.raw):
                _need(row[0].casefold() not in seen and len(rows) < 100000)
                seen.add(row[0].casefold()); rows.append(row)
        _need(False)

    def _walk(self):
        binding = self._verify(); result, seen = [], {binding.root_id}
        def visit(parent, parts):
            self._time(); _need(len(parts) <= 64)
            parent_info, parent_sd = self._query(self.api.info,parent), self._query(self.api.descriptor,parent)
            entries = self._entries(parent)
            for name, attrs, identity in entries:
                _need(len(result) < 100000)
                directory = bool(attrs & DIRECTORY)
                handle = self._open(parent, name)
                primary, cleanup = None, None
                try:
                    ident = self._identity(handle, directory=directory)
                    _need(ident[1] == identity and ident not in seen)
                    seen.add(ident)
                    security = self._query(self.api.security,handle)
                    check_security(security, binding.user, root=False, directory=directory)
                    descriptor = self._query(self.api.descriptor,handle)
                    check_descriptor(descriptor, binding.sid, root=False, directory=directory)
                    _need(self._query(self.api.final_path,handle) == binding.path+'\\'+'\\'.join((*parts, name)))
                    result.append(((*parts, name), ident, descriptor, directory))
                    if directory: visit(handle, (*parts, name))
                    _need(self._identity(handle, directory=directory) == ident and
                          self._query(self.api.descriptor,handle) == descriptor)
                except BaseException as error:
                    primary = error
                finally:
                    try: self._close_one(handle)
                    except BaseException as error: cleanup = error
                if primary is not None and cleanup is not None:
                    raise BaseExceptionGroup('PGDATA_OBJECT_AND_CLOSE_UNKNOWN', [primary, cleanup])
                if primary is not None: raise primary
                if cleanup is not None: raise cleanup
            # Any selected structural/ACL drift refuses, never repairs. Sizes
            # and content hashes are deliberately not a whole-database claim.
            _need(self._query(self.api.info,parent) == parent_info and self._query(self.api.descriptor,parent) == parent_sd and
                  self._entries(parent) == entries)
        visit(self.root, ())
        return tuple(result)

    def _close_one(self, handle):
        require_nt_create_ready(self.api.readonly);require_query_ready(self.api.readonly)
        from .native_trial_authority import budget
        budget(self.lease,cleanup=True)
        # Remove before close: an unknown close is never retried by integer.
        self.handles.remove(handle)
        try: self.api.close(handle)
        except BaseException:
            self.cleanup_errors.append(('HANDLE_CLOSE_UNKNOWN', handle))
            raise

    def close(self):
        _close_entry(self.lease, self)

    def _close_native(self):
        if self.closed:return
        _need(not getattr(self,'_close_started',False))
        self._close_started=True
        errors = []
        try:
            require_nt_create_ready(self.api.readonly);require_query_ready(self.api.readonly)
            from .native_trial_authority import budget
            for handle in tuple(reversed(self.handles)):
                budget(self.lease,cleanup=True)
                try: self._close_one(handle)
                except BaseException as error: errors.append(error)
        except BaseException as error:
            self.cleanup_errors.append(('CLOSE_NOT_ACKNOWLEDGED',None));errors.append(error)
        self.closed = not self.handles and not errors and not self.cleanup_errors
        if errors or self.cleanup_errors:
            self.failed, self.outcome, self.lease.poisoned = True, 'UNKNOWN', True
            _unknown_targets.append(self)
            raise BaseExceptionGroup('PGDATA_CLOSE_UNKNOWN', errors or [DataRefused('PGDATA_CLOSE_UNKNOWN')])

    def _fail(self):
        self.failed, self.outcome, self.lease.poisoned = True, 'UNKNOWN', True
        _unknown_targets.append(self)
        try: self._close_native()
        except BaseException: pass  # Retain primary and cleanup_errors; no delete/repair.
