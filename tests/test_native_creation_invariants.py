"""Independent gold invariants. Linux fake handles/DLLs only; native NOT_RUN."""
import ctypes as C
from dataclasses import replace
import struct
from types import SimpleNamespace
from uuid import uuid4

import pytest

from parkweave import windows_handles as wh
from parkweave.windows import create_new_readonly_candidate as old
from parkweave.windows import create_new_readonly_native as n
from parkweave.windows_files import Info

USER = 'S-1-5-21-101'
OTHER = 'S-1-5-21-102'
GUID = '\\\\?\\Volume{00000000-0000-0000-0000-000000000001}\\'


def raw_acl(sid=USER, *, flags=0, slack=b''):
    parts = sid.split('-')
    subs = list(map(int, parts[3:]))
    raw = bytes((1, len(subs))) + int(parts[2]).to_bytes(6, 'big') + struct.pack('<' + 'I' * len(subs), *subs)
    ace = struct.pack('<BBHI', 0, flags, 8 + len(raw), 0x1f01ff) + raw
    return struct.pack('<BBHHH', 2, 0, 8 + len(ace) + len(slack), 1, 0) + ace + slack


PARENT = old.Descriptor(USER, raw_acl(flags=3), 0x1004)
CHILD = old.Descriptor(USER, raw_acl(flags=0x10), 0x404)
REQUEST = old.Request(old.ObjectKind.SERVICE_LOG, old.Operation.CREATE_NEW, 'windows-services.log')
PROCESS = old.Request(old.ObjectKind.PROCESS_RECORD_INITIAL, old.Operation.CREATE_NEW, 'windows-processes.json')


class ObjectModel:
    """Objects and raw handles are distinct; every read checks handle lifetime."""
    def __init__(self):
        self.events, self.handles, self.closed, self.nodes = [], {}, set(), {}
        self.next_handle, self.next_object = 10, 100
        self.user, self.after_create, self.after_write = USER, None, None
        self.short_write, self.fail_write, self.fail_close = None, False, None
        self.fail_final_binding = False
        root = self.node(True, GUID)
        repo = self.node(True, GUID + 'repo')
        runtime = self.node(True, GUID + 'repo\\.runtime')
        root['children']['repo'], repo['children']['.runtime'] = repo, runtime
        self.root, self.runtime = root, runtime

    def node(self, directory, path):
        self.next_object += 1
        value = dict(info=Info(0x10 if directory else 0x80, 0, 1, 8, self.next_object),
                     descriptor=PARENT if directory else CHILD, path=path, children={}, data=b'')
        self.nodes[self.next_object] = value
        return value

    def held(self, node):
        self.next_handle += 1
        self.handles[self.next_handle] = node
        return self.next_handle

    def object(self, handle):
        assert handle in self.handles and handle not in self.closed, 'raw handle reused after close'
        return self.handles[handle]

    def has_pending(self):
        return False

    def open_drive(self, drive):
        assert drive == 'C:\\'
        self.events.append(('drive', drive))
        return self.held(self.root)

    def final_path(self, handle):
        self.events.append(('path', handle))
        return self.object(handle)['path']

    def filesystem(self, handle):
        self.object(handle)
        return 'NTFS'

    def drive_type(self, path):
        assert path == GUID
        return 3

    def current_user_sid(self):
        self.events.append(('user', self.user))
        return self.user

    def info(self, handle):
        self.events.append(('info', handle))
        return self.object(handle)['info']

    def descriptor(self, handle):
        self.events.append(('descriptor', handle))
        return self.object(handle)['descriptor']

    def relative(self, parent, name, *, access, disposition, share, directory=False):
        node = self.object(parent)
        self.events.append(('relative', parent, name, access, disposition, share, directory))
        if disposition == 2:
            assert not directory
            if name in node['children']:
                raise FileExistsError('EXISTING_OBJECT')
            child = self.node(False, node['path'].rstrip('\\') + '\\' + name)
            node['children'][name] = child
            handle = self.held(child)
            if self.after_create:
                self.after_create(self, handle)
            return handle
        assert disposition == 1
        if name not in node['children'] and name.startswith('eng099-noncas-'):
            node['children'][name] = self.node(True, node['path'] + '\\' + name)
        child = node['children'][name]
        if self.fail_final_binding and name == PROCESS.basename and any(e[0] == 'rename' for e in self.events):
            child = self.node(False, child['path'])
        return self.held(child)

    def write_at(self, handle, data, offset, deadline, clock):
        node = self.object(handle)
        self.events.append(('write', handle, bytes(data), offset, deadline))
        if self.fail_write:
            raise old.CandidateRefused('WRITE_REFUSED')
        count = min(len(data), self.short_write or len(data))
        assert len(node['data']) == offset
        node['data'] += data[:count]
        node['info'] = replace(node['info'], size=len(node['data']))
        if self.after_write:
            self.after_write(self, handle)
        return count

    def rename_relative(self, source, parent, name):
        child, parent_node = self.object(source), self.object(parent)
        self.events.append(('rename', source, parent, name))
        parent_node['children'][name] = child
        child['path'] = parent_node['path'].rstrip('\\') + '\\' + name

    def close(self, handle):
        self.object(handle)
        self.events.append(('close', handle))
        if self.fail_close == handle:
            raise OSError('PRIVATE_CLEANUP_POISON')
        self.closed.add(handle)


def adapter(api=None, *, experimental=False):
    api = api or ObjectModel()
    namespace = n.Namespace.EXPLICIT_NONCAS_EXCLUSIVE_CANDIDATE_NAMESPACE if experimental else n.Namespace.FIXED_RUNTIME
    value = n.NativeAdapter(enabled=True, expected_parent=PARENT, namespace=namespace,
                            namespace_id=str(uuid4()) if experimental else None,
                            _api=api, _runtime_for_tests='C:\\repo\\.runtime', clock=lambda: 1.0)
    return value, api


def created_handle(api):
    return next(e[1] for e in api.events if e[0] == 'write')


def test_native_contract_rights_are_exact_and_legacy_fake_contract_is_unchanged():
    assert old.CREATE_ACCESS == 0x20002
    assert n.CREATE_ACCESS == 0x20082
    assert n.REPLACEMENT_TEMP_ACCESS == 0x30082
    assert n.READ_PARENT_ACCESS == 0x1200a0
    assert n.REPLACEMENT_PARENT_ACCESS == 0x1200e2
    assert n.NativeCreationContract().access == 0x20082


def test_pinned_root_relative_share_zero_same_raw_handle_writes_and_final_verification():
    value, api = adapter()
    stream = value.open_new(REQUEST, expected_child=CHILD, deadline=5.0)
    handle = stream.handle
    assert stream.write('Aé𐐀') == 3
    stream.close()
    creates = [e for e in api.events if e[0] == 'relative' and e[4] == 2]
    assert creates == [('relative', value.parent, REQUEST.basename, 0x20082, 2, 0, False)]
    assert api.handles[handle]['data'] == 'Aé𐐀'.encode()
    assert {e[1] for e in api.events if e[0] == 'write'} == {handle}
    child_reads = [e for e in api.events if e[0] in ('info', 'descriptor') and e[1] == handle]
    assert len(child_reads) >= 8
    assert stream.record.identity.identity == api.handles[handle]['info'].identity
    assert stream.record.byte_count == len('Aé𐐀'.encode())
    assert ('close', handle) in api.events
    assert all(h not in api.closed for h in value.handles)
    value.close()
    assert all(h in api.closed for h in api.handles)


@pytest.mark.parametrize('mask', [0x20002, 0x20083, 0x30082, 0x120082, 0x40000, 0x80000])
def test_wrong_creation_access_refuses_before_any_file_creation(mask):
    value, api = adapter()
    before = list(api.events)
    with pytest.raises(old.CandidateRefused):
        value.open_new(REQUEST, expected_child=CHILD, deadline=5, contract=n.NativeCreationContract(access=mask))
    assert api.events == before
    value.close()


@pytest.mark.parametrize('change', ['reparse', 'owner', 'group', 'control', 'raw_slack', 'parent_identity', 'user'])
def test_untrusted_creation_or_parent_change_refuses_before_content_and_closes_child(change):
    api = ObjectModel()
    def changed(model, handle):
        node = model.handles[handle]
        if change == 'reparse': node['info'] = replace(node['info'], attributes=0x480)
        elif change == 'owner': node['descriptor'] = replace(CHILD, owner=OTHER)
        elif change == 'group': node['descriptor'] = replace(CHILD, raw_dacl=raw_acl(OTHER, flags=0x10))
        elif change == 'control': node['descriptor'] = replace(CHILD, control=0x1004)
        elif change == 'raw_slack': node['descriptor'] = replace(CHILD, raw_dacl=raw_acl(flags=0x10, slack=b'\x01\0\0\0'))
        elif change == 'parent_identity': model.runtime['info'] = replace(model.runtime['info'], identity=999)
        else: model.user = OTHER
    value, api = adapter(api)
    api.after_create = changed
    with pytest.raises(old.CandidateRefused):
        value.open_new(REQUEST, expected_child=CHILD, deadline=5)
    assert not any(e[0] == 'write' for e in api.events)
    child = max(api.handles)
    assert child in api.closed
    value.close()


def test_short_writes_keep_utf8_byte_offsets_and_one_total_deadline():
    value, api = adapter()
    api.short_write = 2
    stream = value.open_new(REQUEST, expected_child=CHILD, deadline=5)
    assert stream.write('é😀') == 2
    assert [(e[3], e[4]) for e in api.events if e[0] == 'write'] == [(0, 5), (2, 5), (4, 5)]
    stream.close()
    assert stream.record.byte_count == 6
    value.close()


def test_write_failure_does_not_issue_record_and_closes_exact_child_once():
    value, api = adapter()
    stream = value.open_new(REQUEST, expected_child=CHILD, deadline=5)
    api.fail_write = True
    with pytest.raises(old.CandidateRefused): stream.write('uncommitted')
    stream.close()
    assert stream.record is None
    assert api.events.count(('close', stream.handle)) == 1
    value.close()


def test_close_validation_failure_still_releases_child_and_never_issues_success():
    value, api = adapter()
    stream = value.open_new(REQUEST, expected_child=CHILD, deadline=5)
    stream.write('actual bytes')
    api.handles[stream.handle]['descriptor'] = replace(CHILD, control=0x1004)
    with pytest.raises(old.CandidateRefused): stream.close()
    assert stream.record is None and stream.handle in api.closed
    assert api.events.count(('close', stream.handle)) == 1
    value.close()


def initial_record(value):
    stream = value.open_new(PROCESS, expected_child=CHILD, deadline=5)
    stream.write('old process binding')
    stream.close()
    return stream.record


def temp_request():
    return old.Request(old.ObjectKind.BINDING_TEMP, old.Operation.CREATE_NEW,
                       '.process-binding-' + uuid4().hex + '.json')


def test_default_target_cas_required_refuses_before_temp_or_rename():
    value, api = adapter()
    target = initial_record(value)
    before = list(api.events)
    with pytest.raises(old.CandidateRefused, match='TARGET_ID_CAS_UNAVAILABLE'):
        value.replace_record(target, temp_request(), expected_child=CHILD, text='new',
                             contract=n.ReplacementContract(), deadline=5)
    assert api.events == before
    assert not any(e[0] == 'rename' for e in api.events)
    value.close()


def test_explicit_uuid_noncas_replacement_verifies_same_handle_then_rooted_final_target_binding():
    value, api = adapter(experimental=True)
    target = initial_record(value)
    contract = n.ReplacementContract(require_target_cas=False, explicit_noncas_exclusive_candidate_namespace=True)
    receipt = value.replace_record(target, temp_request(), expected_child=CHILD,
                                   text='new process binding', contract=contract, deadline=5)
    assert receipt.target_cas is False and receipt.same_user_namespace_race_unresolved is True
    assert receipt.content_readback_verified is False and receipt.durability_verified is False
    renamed = next(e for e in api.events if e[0] == 'rename')
    assert api.handles[renamed[1]]['info'].identity == receipt.final.identity.identity
    creates = [e for e in api.events if e[0] == 'relative' and e[4] == 2]
    assert creates[-1][3:6] == (0x30082, 2, 0)
    parent_opens = [e for e in api.events if e[0] == 'relative' and e[3] == 0x1200e2]
    assert len(parent_opens) == 1
    rename_index = api.events.index(renamed)
    final_opens = [e for e in api.events[rename_index + 1:] if e[0] == 'relative' and e[2] == PROCESS.basename]
    assert len(final_opens) == 1
    target_queries = [e for e in api.events if e[0] == 'relative'
                      and e[2] == PROCESS.basename and e[4] == 1 and not e[6]]
    assert len(target_queries) == 2
    assert all(e[3] == 0x20080 for e in target_queries)
    assert n.FILE_QUERY_ACCESS == 0x20080
    assert ('close', renamed[1]) in api.events[rename_index + 1:]
    value.close()


def test_noncas_final_target_rebinding_fails_closed_after_possible_publication():
    value, api = adapter(experimental=True)
    target = initial_record(value)
    api.fail_final_binding = True
    contract = n.ReplacementContract(require_target_cas=False, explicit_noncas_exclusive_candidate_namespace=True)
    with pytest.raises(old.CandidateRefused) as failure:
        value.replace_record(target, temp_request(), expected_child=CHILD, text='new', contract=contract, deadline=5)
    assert failure.value.publication_may_have_occurred
    assert not value._issued
    value.close()


def bare_api():
    api = n.CtypesAPI.__new__(n.CtypesAPI)
    api.quarantine, api.pending_handles = [], set()
    return api


def address(value):
    return value.value if isinstance(value, C.c_void_p) else int(value)


class BoundFunction:
    def __init__(self, name):
        self.name, self.argtypes, self.restype = name, None, None
    def __call__(self, *args):
        raise AssertionError('No native DLL function may execute: ' + self.name)


class FakeDLL:
    def __init__(self, name):
        self.name, self.functions = name, {}
    def __getattr__(self, name):
        return self.functions.setdefault(name, BoundFunction(name))


def test_actual_ctypes_x64_bindings_and_structure_layouts_use_system_dll_fakes(monkeypatch):
    loads = []
    def dll(name, **kwargs):
        assert kwargs == dict(use_last_error=True, winmode=0x800)
        loads.append(name)
        return FakeDLL(name)
    monkeypatch.setattr(wh, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(C, 'WinDLL', dll, raising=False)
    monkeypatch.setattr(wh.WinAPI, '_user_sid', lambda self: USER)
    api = n.CtypesAPI()
    assert loads == ['kernel32.dll', 'advapi32.dll', 'ntdll.dll']
    assert C.sizeof(n.Overlapped) == 32 and n.Overlapped.hEvent.offset == 24
    assert C.sizeof(wh.ObjectAttributes) == 48 and wh.ObjectAttributes.RootDirectory.offset == 8
    assert C.sizeof(wh.UnicodeString) == 16 and C.sizeof(wh.IOStatus) == 16
    assert n.RenameInfo.RootDirectory.offset == 8 and n.RenameInfo.FileName.offset == 20
    assert api.ntcreate.argtypes == [C.POINTER(wh.PTR), wh.U32, C.POINTER(wh.ObjectAttributes), C.POINTER(wh.IOStatus), wh.PTR, wh.U32, wh.U32, wh.U32, wh.U32, wh.PTR, wh.U32]
    assert api.getsecurity.restype is wh.U32
    assert api.getsecurity.argtypes == [wh.PTR, wh.U32, wh.U32] + [C.POINTER(wh.PTR)] * 5
    assert api.writefile.argtypes == [wh.PTR, wh.PTR, wh.U32, wh.PTR, C.POINTER(n.Overlapped)]
    assert api.result.argtypes == [wh.PTR, C.POINTER(n.Overlapped), C.POINTER(wh.U32), wh.I32]
    assert api.setinfo.argtypes == [wh.PTR, wh.I32, wh.PTR, wh.U32]
    assert not any('SetSecurity' in f or 'SetToken' in f or 'AdjustToken' in f for lib in (api.k, api.a, api.n) for f in lib.functions)


def test_ntcreate_uses_held_root_exact_rights_no_security_descriptor_and_async_file_options():
    api = bare_api()
    calls = []
    def create(out, access, oa_ptr, ios_ptr, allocation, attributes, share, disposition, options, ea, ea_length):
        oa = C.cast(oa_ptr, C.POINTER(wh.ObjectAttributes)).contents
        name = oa.ObjectName.contents
        calls.append((access, oa.RootDirectory, C.string_at(name.Buffer, name.Length).decode('utf-16-le'), oa.Attributes,
                      oa.SecurityDescriptor, oa.SecurityQualityOfService, allocation, attributes, share, disposition, options, ea, ea_length))
        C.cast(out, C.POINTER(wh.PTR))[0] = 901
        C.cast(ios_ptr, C.POINTER(wh.IOStatus)).contents.Information = 2
        return 0
    api.ntcreate = create
    assert api.relative(701, 'windows-services.log', access=0x20082, disposition=2, share=0) == 901
    assert calls == [(0x20082, 701, 'windows-services.log', 0x40, None, None, None, 0x80, 0, 2, 0x200040, None, 0)]


@pytest.mark.parametrize('status,information', [(0, 1), (0xc0000035, 0), (0xc0000022, 0)])
def test_ntcreate_failed_or_noncreated_result_closes_acquired_handle_once(status, information):
    api = bare_api()
    closed = []
    api._close = lambda handle: closed.append(handle) or 1
    def create(out, access, oa, ios, *args):
        C.cast(out, C.POINTER(wh.PTR))[0] = 901
        C.cast(ios, C.POINTER(wh.IOStatus)).contents.Information = information
        return status
    api.ntcreate = create
    with pytest.raises((old.CandidateRefused, FileExistsError)):
        api.relative(701, REQUEST.basename, access=0x20082, disposition=2, share=0)
    assert closed == [901]


def test_security_read_on_exact_handle_preserves_raw_bytes_and_frees_allocations_on_failure():
    api = bare_api()
    dacl = C.create_string_buffer(raw_acl(flags=0x10, slack=b'\x99\0\0\0'))
    sd, sid = C.create_string_buffer(64), C.create_string_buffer(32)
    sid_text = C.create_unicode_buffer(USER)
    freed, queried = [], []
    def security(handle, kind, flags, owner, group, acl, sacl, descriptor):
        queried.append((handle, kind, flags, group, sacl))
        C.cast(owner, C.POINTER(wh.PTR))[0] = C.addressof(sid)
        C.cast(acl, C.POINTER(wh.PTR))[0] = C.addressof(dacl)
        C.cast(descriptor, C.POINTER(wh.PTR))[0] = C.addressof(sd)
        return 0
    def control(pointer, value, revision):
        C.cast(value, C.POINTER(wh.U16))[0] = 0x404
        C.cast(revision, C.POINTER(wh.U32))[0] = 1
        return 1
    def sizes(pointer, out, length, kind):
        assert length == 12 and kind == 2
        info = C.cast(out, C.POINTER(n.AclSize)).contents
        info.count, info.used, info.free = 1, len(dacl.raw) - 1 - 4, 4
        return 1
    def ace(pointer, index, out):
        assert index == 0
        C.cast(out, C.POINTER(wh.PTR))[0] = C.addressof(dacl) + 8
        return 1
    def sid_string(pointer, out):
        C.cast(out, C.POINTER(wh.PTR))[0] = C.addressof(sid_text)
        return 1
    api.getsecurity, api.control, api.aclinfo, api.getace = security, control, sizes, ace
    api.valid_sd = api.valid_acl = api.valid_sid = lambda pointer: 1
    api.sidstring = sid_string
    api.localfree = lambda pointer: freed.append(address(pointer)) or None
    descriptor = api.descriptor(123456789)
    assert queried == [(123456789, 1, 5, None, None)]
    assert descriptor == old.Descriptor(USER, dacl.raw[:-1], 0x404)
    assert freed == [C.addressof(sid_text), C.addressof(sd)]
    freed.clear()
    api.valid_acl = lambda pointer: 0
    with pytest.raises(old.CandidateRefused): api.descriptor(123456789)
    assert freed == [C.addressof(sd)]


def test_token_user_query_uses_tokenuser_one_and_closes_token_without_mutation():
    api = bare_api()
    calls, closed = [], []
    api.process = lambda: 700
    def token(process, rights, out):
        calls.append(('open', process, rights))
        C.cast(out, C.POINTER(wh.PTR))[0] = 701
        return 1
    def information(handle, kind, buffer, size, needed):
        calls.append(('info', handle.value, kind, size))
        C.cast(needed, C.POINTER(wh.U32))[0] = 16
        if buffer is not None:
            C.cast(buffer, C.POINTER(wh.PTR))[0] = 0x123456
        return 1
    api.opentoken, api.tokeninfo = token, information
    api.sid = lambda pointer: USER if pointer == 0x123456 else None
    api._close = lambda handle: closed.append(address(handle)) or 1
    assert api.current_user_sid() == USER
    assert calls == [('open', 700, 8), ('info', 701, 1, 0), ('info', 701, 1, 16)]
    assert closed == [701]


def asynchronous_api(monkeypatch, *, result_error=None, timeout=False, count=3):
    api = bare_api()
    events, state = [], {'error': 997}
    monkeypatch.setattr(C, 'get_last_error', lambda: state['error'], raising=False)
    api.event = lambda *args: events.append(('event', args)) or 501
    api._close = lambda handle: events.append(('close', handle)) or 1
    def write(handle, buffer, length, synchronous_count, ov_ptr):
        ov = C.cast(ov_ptr, C.POINTER(n.Overlapped)).contents
        events.append(('write', handle, C.string_at(buffer, length), synchronous_count,
                       C.addressof(ov), ov.Offset, ov.OffsetHigh, ov.hEvent))
        return 0
    def result(handle, ov_ptr, count_ptr, wait):
        ov = C.cast(ov_ptr, C.POINTER(n.Overlapped)).contents
        events.append(('result', handle, C.addressof(ov), wait))
        if result_error is not None:
            state['error'] = result_error
            return 0
        C.cast(count_ptr, C.POINTER(wh.U32))[0] = count
        return 1
    api.writefile, api.result = write, result
    api.wait = lambda handle, milliseconds: events.append(('wait', handle, milliseconds)) or (258 if timeout else 0)
    api.cancel = lambda handle, ov: events.append(('cancel', handle, C.addressof(C.cast(ov, C.POINTER(n.Overlapped)).contents))) or 1
    return api, events, state


def test_pending_write_waits_event_and_reuses_exact_overlapped_without_file_synchronize(monkeypatch):
    api, events, _ = asynchronous_api(monkeypatch)
    assert api.write_at(1001, b'abc', (1 << 32) + 7, 4.0, lambda: 1.0) == 3
    write = next(e for e in events if e[0] == 'write')
    result = next(e for e in events if e[0] == 'result')
    assert write[1:4] == (1001, b'abc', None)
    assert write[5:] == (7, 1, 501)
    assert result == ('result', 1001, write[4], False)
    assert ('wait', 501, 3000) in events and ('close', 501) in events
    assert not api.quarantine and not api.has_pending()


@pytest.mark.parametrize('mode', ['deadline', 'incomplete', 'unknown_error'])
def test_unresolved_overlapped_retains_buffer_event_handle_and_cancels_exact_operation(monkeypatch, mode):
    api, events, _ = asynchronous_api(monkeypatch, timeout=mode == 'deadline',
                                    result_error=996 if mode == 'incomplete' else 5 if mode == 'unknown_error' else None)
    with pytest.raises(old.CandidateRefused) as failure:
        api.write_at(1001, b'abc', 0, 4.0, lambda: 1.0)
    assert failure.value.candidate_cleanup_failed
    assert api.pending_handles == {1001} and api.has_pending()
    handle, buf, ov, event = api.quarantine[0]
    assert (handle, buf.raw[:3], ov.hEvent, event) == (1001, b'abc', 501, 501)
    write = next(e for e in events if e[0] == 'write')
    assert ('cancel', 1001, write[4]) in events
    assert not any(e[0] == 'close' for e in events)
    with pytest.raises(old.CandidateRefused): api.close(1001)
    assert n._PENDING_RETENTION[id(api)] is api
    # Explicit terminal cancellation poll is the only place these objects retire.
    def aborted(handle, ov, count, wait):
        monkeypatch.setattr(C, 'get_last_error', lambda: 995, raising=False)
        return 0
    api.result = aborted
    assert api.poll_pending()
    assert ('close', 501) in events and ('close', 1001) in events
    assert not api.quarantine and id(api) not in n._PENDING_RETENTION


def test_rooted_rename_abi_is_replace_only_with_no_posix_or_ignore_readonly_flags():
    api = bare_api()
    calls = []
    def rename(handle, information_class, buffer, size):
        info = n.RenameInfo.from_buffer(buffer)
        name = C.string_at(C.addressof(buffer) + n.RenameInfo.FileName.offset, info.FileNameLength).decode('utf-16-le')
        calls.append((handle, information_class, info.ReplaceIfExists, info.RootDirectory, name,
                      bytes(buffer)[1:n.RenameInfo.RootDirectory.offset]))
        return 1
    api.setinfo = rename
    api.rename_relative(777, 888, 'windows-processes.json')
    assert calls == [(777, 3, 1, 888, 'windows-processes.json', b'\0' * 7)]


@pytest.mark.parametrize('ancestor', ['root', 'repo', 'runtime'])
def test_every_held_ancestor_reparse_is_rejected_without_file_creation_or_unclosed_handles(ancestor):
    api = ObjectModel()
    node = api.root if ancestor == 'root' else api.root['children']['repo'] if ancestor == 'repo' else api.runtime
    node['info'] = replace(node['info'], attributes=0x410)
    with pytest.raises(old.CandidateRefused): adapter(api)
    assert not any(e[0] == 'relative' and e[4] == 2 for e in api.events)
    assert set(api.handles) == api.closed


@pytest.mark.parametrize('deadline', [True, float('nan'), float('inf'), 1.0, 0])
def test_invalid_or_expired_deadline_never_acquires_a_child(deadline):
    value, api = adapter()
    before = list(api.events)
    with pytest.raises(old.CandidateRefused, match='INVALID_DEADLINE'):
        value.open_new(REQUEST, expected_child=CHILD, deadline=deadline)
    assert api.events == before
    value.close()


def test_native_activation_default_and_unsupported_platform_refuse_without_dll_loading(monkeypatch):
    attempted = []
    monkeypatch.setattr(C, 'WinDLL', lambda *args, **kwargs: attempted.append(args) or None, raising=False)
    with pytest.raises(old.CandidateRefused, match='NATIVE_OPERATION_DISABLED'):
        n.NativeAdapter(expected_parent=PARENT)
    if n.os.name != 'nt':
        with pytest.raises(old.CandidateRefused, match='WINDOWS_X64_REQUIRED'):
            n.NativeAdapter(enabled=True, expected_parent=PARENT)
    assert attempted == []


def test_cleanup_failure_after_validation_refusal_preserves_primary_and_never_issues_receipt():
    value, api = adapter()
    stream = value.open_new(REQUEST, expected_child=CHILD, deadline=5)
    stream.write('actual bytes')
    api.handles[stream.handle]['descriptor'] = replace(CHILD, control=0x1004)
    api.fail_close = stream.handle
    with pytest.raises(old.CandidateRefused, match='FILE_CHANGED') as failure:
        stream.close()
    assert failure.value.candidate_cleanup_failed
    assert stream.closed and stream.record is None and not value._issued
    assert api.events.count(('close', stream.handle)) == 1
    api.fail_close = None
    value.close()


@pytest.mark.parametrize('override', [dict(temp_access=0x20082), dict(temp_access=0x130082),
    dict(parent_access=0x120082), dict(parent_access=0x1200c2), dict(parent_access=0x1f01ff), dict(explicit_noncas_exclusive_candidate_namespace=False)])
def test_noncas_capability_mask_expansion_or_missing_capability_refuses_before_rename(override):
    value, api = adapter(experimental=True)
    target = initial_record(value)
    before = list(api.events)
    contract = n.ReplacementContract(require_target_cas=False, explicit_noncas_exclusive_candidate_namespace=True)
    contract = replace(contract, **override)
    with pytest.raises(old.CandidateRefused, match='REPLACEMENT_CAPABILITY_REFUSED'):
        value.replace_record(target, temp_request(), expected_child=CHILD, text='new', contract=contract, deadline=5)
    assert api.events == before
    value.close()


def test_security_status_failure_frees_returned_descriptor_and_never_queries_or_repairs_it():
    api = bare_api()
    sd = C.create_string_buffer(64)
    freed = []
    def security(handle, kind, flags, owner, group, acl, sacl, descriptor):
        C.cast(descriptor, C.POINTER(wh.PTR))[0] = C.addressof(sd)
        return 5
    api.getsecurity = security
    api.localfree = lambda pointer: freed.append(address(pointer)) or None
    api.valid_sd = lambda pointer: pytest.fail('failed read may not validate or repair descriptor')
    with pytest.raises(old.CandidateRefused, match='DESCRIPTOR_REFUSED'):
        api.descriptor(123)
    assert freed == [C.addressof(sd)]


def test_terminal_async_cancellation_releases_event_and_does_not_claim_write_success(monkeypatch):
    api, events, _ = asynchronous_api(monkeypatch, result_error=995)
    with pytest.raises(old.CandidateRefused, match='WRITE_COMPLETION_REFUSED'):
        api.write_at(1001, b'abc', 0, 4.0, lambda: 1.0)
    assert not api.quarantine and not api.pending_handles
    assert ('close', 501) in events
    assert not any(e[0] == 'cancel' for e in events)


@pytest.mark.parametrize('handle', [0, 901])
def test_pending_ntcreate_retains_name_oa_ios_and_blocks_next_operation_even_without_output_handle(handle):
    api = bare_api()
    closed = []
    api._close = lambda value: closed.append(address(value)) or 1
    def create(out, access, oa, ios, *args):
        C.cast(out, C.POINTER(wh.PTR))[0] = handle or None
        C.cast(ios, C.POINTER(wh.IOStatus)).contents.Information = 0
        return 0x103
    api.ntcreate = create
    with pytest.raises(old.CandidateRefused, match='NATIVE_OPEN_REFUSED'):
        api.relative(701, REQUEST.basename, access=0x20082, disposition=2, share=0)
    assert api.has_pending() and not closed
    buf, name, oa, out, ios = api.quarantine[0]
    assert C.string_at(name.Buffer, name.Length).decode('utf-16-le') == REQUEST.basename
    assert oa.RootDirectory == 701 and out.value == (handle or None)
    assert n._PENDING_RETENTION[id(api)] is api
    assert not api.poll_pending() and api.has_pending()
    assert not closed


@pytest.mark.parametrize('count', [0, True, 4])
def test_invalid_write_completion_count_never_issues_record(count):
    value, api = adapter()
    stream = value.open_new(REQUEST, expected_child=CHILD, deadline=5)
    api.write_at = lambda *args: count
    with pytest.raises(old.CandidateRefused, match='WRITE_COMPLETION_REFUSED'):
        stream.write('abc')
    stream.close()
    assert stream.record is None and stream.handle in api.closed
    value.close()


def test_terminal_poll_cleanup_failure_retains_resources_and_never_retries_close(monkeypatch):
    api, events, _ = asynchronous_api(monkeypatch, timeout=True)
    with pytest.raises(old.CandidateRefused):
        api.write_at(1001, b'abc', 0, 4.0, lambda: 1.0)
    def aborted(handle, ov, count, wait):
        monkeypatch.setattr(C, 'get_last_error', lambda: 995, raising=False)
        return 0
    api.result = aborted
    def close(handle):
        events.append(('close', handle))
        return 0 if handle == 501 else 1
    api._close = close
    with pytest.raises(old.CandidateRefused, match='CLEANUP_REFUSED'):
        api.poll_pending()
    assert api.has_pending() and api.quarantine and n._PENDING_RETENTION[id(api)] is api
    before = list(events)
    assert not api.poll_pending()
    assert events == before
    assert events.count(('close', 501)) == events.count(('close', 1001)) == 1


def test_descriptor_allocation_free_failure_preserves_read_refusal_and_is_not_success():
    api = bare_api()
    sd = C.create_string_buffer(64)
    freed = []
    def security(handle, kind, flags, owner, group, acl, sacl, descriptor):
        C.cast(descriptor, C.POINTER(wh.PTR))[0] = C.addressof(sd)
        return 5
    api.getsecurity = security
    api.localfree = lambda pointer: freed.append(address(pointer)) or address(pointer)
    with pytest.raises(old.CandidateRefused, match='DESCRIPTOR_REFUSED') as failure:
        api.descriptor(123)
    assert failure.value.candidate_cleanup_failed
    assert freed == [C.addressof(sd)]
