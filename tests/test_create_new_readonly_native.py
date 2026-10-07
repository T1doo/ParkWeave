"""Linux fake-kernel/ctypes ABI gold; no native DLL loads or security writes."""
import ctypes as C
from dataclasses import replace
import struct
from types import SimpleNamespace

import pytest

from parkweave.windows import create_new_readonly_native as n
from parkweave.windows import create_new_readonly_candidate as p
from parkweave.windows_files import Info

USER = 'S-1-5-21-7'
def acl():
    sid = bytes((1, 2)) + (5).to_bytes(6, 'big') + struct.pack('<II', 21, 7)
    ace = struct.pack('<BBHI', 0, 0, 8 + len(sid), 0x1f01ff) + sid
    return struct.pack('<BBHHH', 2, 0, 8 + len(ace), 1, 0) + ace
PARENT = p.Descriptor(USER, acl(), 0x1004)
CHILD = p.Descriptor(USER, acl(), 4)
STATE = p.Request(p.ObjectKind.PROCESS_RECORD_INITIAL, p.Operation.CREATE_NEW, 'windows-processes.json')
TEMP = p.Request(p.ObjectKind.BINDING_TEMP, p.Operation.CREATE_NEW, '.process-binding-' + 'a' * 32 + '.json')
UUID = '12345678-1234-1234-1234-123456789abc'


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.objects = {1: dict(path='\\\\?\\Volume{' + UUID + '}\\', directory=True,
                                identity=1, data=b'', descriptor=PARENT)}
        self.handles = {10: 1}
        self.next = 11
        self.nextid = 2
        self.short = False
        self.pending = False
        self.closed = []
        self.fail_close = False
        self.rename_failure = False
        self.bad_final = False

    def _newhandle(self, identity):
        h = self.next
        self.next += 1
        self.handles[h] = identity
        return h
    def has_pending(self): return self.pending
    def current_user_sid(self): return USER
    def open_drive(self, drive):
        self.calls.append(('drive', drive))
        return 10
    def final_path(self, handle):
        obj = self.objects[self.handles[handle]]
        return obj['path'] + ('wrong' if self.bad_final and not obj['directory'] else '')
    def filesystem(self, handle): return 'NTFS'
    def drive_type(self, guid): return 3
    def info(self, handle):
        obj = self.objects[self.handles[handle]]
        return Info(0x10 if obj['directory'] else 0x80, len(obj['data']), 1, 9, obj['identity'])
    def descriptor(self, handle): return self.objects[self.handles[handle]]['descriptor']
    def relative(self, parent, name, **kwargs):
        self.calls.append(('relative', parent, name, kwargs))
        path = self.final_path(parent).rstrip('\\') + '\\' + name
        found = next((i for i, obj in self.objects.items() if obj['path'] == path), None)
        creating = kwargs['disposition'] == n.FILE_CREATE
        if creating and found:
            raise FileExistsError('EXISTING_OBJECT')
        if not found:
            if not creating and not kwargs.get('directory'):
                raise p.CandidateRefused('NATIVE_OPEN_REFUSED')
            found = self.nextid
            self.nextid += 1
            self.objects[found] = dict(path=path, directory=kwargs.get('directory', False),
                                      identity=found, data=b'', descriptor=PARENT if kwargs.get('directory') else CHILD)
        return self._newhandle(found)
    def write_at(self, handle, data, offset, deadline, clock):
        self.calls.append(('write', handle, data, offset))
        count = min(2, len(data)) if self.short else len(data)
        obj = self.objects[self.handles[handle]]
        obj['data'] = obj['data'][:offset] + data[:count]
        return count
    def rename_relative(self, source, parent, name):
        self.calls.append(('rename', source, parent, name))
        if self.rename_failure: raise p.CandidateRefused('RENAME_REFUSED')
        final = self.final_path(parent).rstrip('\\') + '\\' + name
        for i, obj in list(self.objects.items()):
            if obj['path'] == final:
                obj['path'] += '.old-detached'
        self.objects[self.handles[source]]['path'] = final
    def close(self, handle):
        self.calls.append(('close', handle))
        if self.fail_close: raise p.CandidateRefused('CLEANUP_REFUSED')
        if self.pending and not self.objects[self.handles[handle]]['directory']:
            raise p.CandidateRefused('PENDING_IO_RETAINED')
        self.closed.append(handle)


def adapter(api=None, experimental=False):
    api = api or FakeAPI()
    kwargs = dict(enabled=True, expected_parent=PARENT, _api=api,
                  _runtime_for_tests='C:\\repo\\.runtime', clock=lambda: 1)
    if experimental:
        kwargs.update(namespace=n.Namespace.EXPLICIT_NONCAS_EXCLUSIVE_CANDIDATE_NAMESPACE, namespace_id=UUID)
    return n.NativeAdapter(**kwargs), api


def owned(a):
    stream = a.open_new(STATE, expected_child=CHILD, deadline=10)
    with stream: stream.write('SYNTHETIC_STATE')
    return stream.record


def test_default_off_and_nonwindows_refuse_before_dll_loading(monkeypatch):
    calls = []
    monkeypatch.setattr(n, 'CtypesAPI', lambda: calls.append('LOAD'))
    with pytest.raises(p.CandidateRefused, match='NATIVE_OPERATION_DISABLED'):
        n.NativeAdapter(expected_parent=PARENT)
    monkeypatch.setattr(n, 'os', SimpleNamespace(name='posix'))
    with pytest.raises(p.CandidateRefused, match='WINDOWS_X64_REQUIRED'):
        n.NativeAdapter(enabled=True, expected_parent=PARENT)
    assert calls == []


def test_exact_native_masks_explicit_readattributes_no_generic_security_or_file_sync():
    assert n.CREATE_ACCESS == 0x20082 and n.REPLACEMENT_TEMP_ACCESS == 0x30082
    assert n.CREATE_ACCESS & (0xf0000000 | 0x100000 | 0x80000 | 0x40000 | 0x100) == 0
    assert n.REPLACEMENT_PARENT_ACCESS == 0x1200e2
    assert n.FILE_QUERY_ACCESS == 0x20080
    assert p.CREATE_ACCESS == 0x20002  # ENG098 seam remains unchanged.


def test_strict_create_and_short_utf8_writes_stay_on_original_handle():
    a, api = adapter()
    api.short = True
    stream = a.open_new(STATE, expected_child=CHILD, deadline=10)
    handle = stream.handle
    with stream:
        assert stream.write('SYNTHETIC_汉字') == len('SYNTHETIC_汉字')
    assert all(row[1] == handle for row in api.calls if row[0] == 'write')
    assert api.objects[api.handles[handle]]['data'] == 'SYNTHETIC_汉字'.encode()
    creations = [row for row in api.calls if row[0] == 'relative' and row[3]['disposition'] == n.FILE_CREATE]
    assert len(creations) == 1 and creations[0][3] == dict(access=0x20082, disposition=2, share=0)
    assert stream.record is not None and api.closed.count(handle) == 1
    a.close()


def test_cas_default_refusal_occurs_before_temp_or_parent_write_capability():
    a, api = adapter(experimental=True)
    record = owned(a)
    api.calls.clear()
    with pytest.raises(p.CandidateRefused, match='TARGET_ID_CAS_UNAVAILABLE'):
        a.replace_record(record, TEMP, expected_child=CHILD, text='SYNTHETIC_NEW',
                         contract=n.ReplacementContract(), deadline=10)
    assert api.calls == []
    a.close()


@pytest.mark.parametrize('experimental,contract', [
    (False, n.ReplacementContract(False, True)),
    (True, n.ReplacementContract(False, False)),
    (True, n.ReplacementContract(False, True, temp_access=0x20082)),
    (True, n.ReplacementContract(False, True, parent_access=0x1200a0)),
])
def test_missing_noncas_scope_or_minimal_rights_refuse_before_operations(experimental, contract):
    a, api = adapter(experimental=experimental)
    record = owned(a)
    api.calls.clear()
    with pytest.raises(p.CandidateRefused, match='REPLACEMENT_CAPABILITY_REFUSED'):
        a.replace_record(record, TEMP, expected_child=CHILD, text='X', contract=contract, deadline=10)
    assert api.calls == []
    a.close()


def test_explicit_experimental_rename_original_temp_then_rooted_final_receipt_noncas():
    a, api = adapter(experimental=True)
    target = owned(a)
    api.calls.clear()
    receipt = a.replace_record(target, TEMP, expected_child=CHILD, text='SYNTHETIC_NEW',
                               contract=n.ReplacementContract(False, True), deadline=10)
    assert receipt.target_cas is False and receipt.same_user_namespace_race_unresolved is True
    rename = next(row for row in api.calls if row[0] == 'rename')
    writes = [row for row in api.calls if row[0] == 'write']
    assert all(row[1] == rename[1] for row in writes)
    assert api.closed.count(rename[1]) == 1
    assert receipt.final.byte_count == len('SYNTHETIC_NEW')
    assert receipt.final.identity.identity == api.handles[rename[1]]
    assert any(row[0] == 'relative' and row[2] == 'windows-processes.json' for row in api.calls[api.calls.index(rename) + 1:])
    queries = [row for row in api.calls if row[0] == 'relative' and row[2] == 'windows-processes.json'
               and row[3]['disposition'] == n.FILE_OPEN]
    assert len(queries) == 2 and all(row[3]['access'] == 0x20080 for row in queries)
    assert any(row[0] == 'relative' and row[3]['access'] == 0x30082 for row in api.calls)
    a.close()


def test_forged_old_or_failed_record_cannot_trigger_replacement():
    a, api = adapter(experimental=True)
    good = owned(a)
    forged = replace(good)
    api.calls.clear()
    with pytest.raises(p.CandidateRefused, match='OWNED_TARGET_REQUIRED'):
        a.replace_record(forged, TEMP, expected_child=CHILD, text='X', contract=n.ReplacementContract(False, True), deadline=10)
    assert api.calls == []
    a.close()


def test_postrename_final_mismatch_is_failure_with_publication_marker():
    a, api = adapter(experimental=True)
    record = owned(a)
    api.bad_final = True
    with pytest.raises(p.CandidateRefused, match='FINAL_NAME_MISMATCH') as caught:
        a.replace_record(record, TEMP, expected_child=CHILD, text='X', contract=n.ReplacementContract(False, True), deadline=10)
    assert caught.value.publication_may_have_occurred is True
    assert id(record) not in a._issued
    a.close()


def test_stream_close_validation_failure_still_closes_original_once():
    a, api = adapter()
    stream = a.open_new(STATE, expected_child=CHILD, deadline=10)
    api.objects[api.handles[stream.handle]]['descriptor'] = replace(CHILD, owner='S-1-5-32-544')
    with pytest.raises(p.CandidateRefused, match='OWNER_MISMATCH'):
        stream.close()
    assert stream.closed and stream.record is None and api.closed.count(stream.handle) == 1
    a.close()


def test_async_ctypes_uses_unique_event_null_count_and_no_wait_on_file(monkeypatch):
    api = n.CtypesAPI.__new__(n.CtypesAPI)
    api.quarantine, api.pending_handles = [], set()
    calls = []
    api.event = lambda *args: 77
    def write(handle, buf, length, count, ov):
        assert count is None
        calls.append(('write', handle, C.string_at(buf, length), ov._obj.Offset))
        return 0
    api.writefile = write
    api.wait = lambda handle, timeout: calls.append(('wait', handle, timeout)) or 0
    def result(handle, ov, count, waiting):
        assert waiting is False
        count._obj.value = 3
        return 1
    api.result = result
    api.close = lambda h: calls.append(('close', h))
    monkeypatch.setattr(n.C, 'get_last_error', lambda: 997, raising=False)
    assert api.write_at(22, b'ABC', 9, 5, lambda: 1) == 3
    assert calls == [('write', 22, b'ABC', 9), ('wait', 77, 4000), ('close', 77)]
    assert api.quarantine == []


def test_pending_cancel_does_not_close_file_event_or_free_buffers_until_terminal(monkeypatch):
    api = n.CtypesAPI.__new__(n.CtypesAPI)
    api.quarantine, api.pending_handles = [], set()
    calls = []
    api.event = lambda *args: 77
    api.writefile = lambda *args: 0
    api.wait = lambda *args: 258
    api.cancel = lambda *args: calls.append('cancel') or 1
    api._close = lambda h: calls.append(('close', h)) or 1
    monkeypatch.setattr(n.C, 'get_last_error', lambda: 997, raising=False)
    with pytest.raises(p.CandidateRefused, match='WRITE_DEADLINE') as caught:
        api.write_at(22, b'ABC', 0, 5, lambda: 1)
    assert caught.value.candidate_cleanup_failed and calls == ['cancel']
    assert len(api.quarantine) == 1 and n._PENDING_RETENTION[id(api)] is api
    with pytest.raises(p.CandidateRefused, match='PENDING_IO_RETAINED'):
        api.close(22)
    api.result = lambda *args: 0
    assert api.poll_pending() is False and calls == ['cancel']
    monkeypatch.setattr(n.C, 'get_last_error', lambda: 995, raising=False)
    assert api.poll_pending() is True
    assert calls == ['cancel', ('close', 77), ('close', 22)]
    assert id(api) not in n._PENDING_RETENTION


def test_relative_ctypes_abi_has_exact_root_create_access_and_no_sync_option():
    api = n.CtypesAPI.__new__(n.CtypesAPI)
    calls = []
    def create(out, access, oa, ios, alloc, attributes, share, disposition, options, ea, length):
        assert oa._obj.RootDirectory == 31 and oa._obj.SecurityDescriptor is None
        assert alloc is None and ea is None and length == 0
        calls.append((access, share, disposition, options))
        out._obj.value, ios._obj.Information = 55, 2
        return 0
    api.ntcreate = create
    assert api.relative(31, 'synthetic-sessions.json', access=n.CREATE_ACCESS, disposition=2, share=0) == 55
    assert calls == [(0x20082, 0, 2, 0x200040)]


def test_rename_ctypes_abi_exact_original_source_root_and_relative_name():
    api = n.CtypesAPI.__new__(n.CtypesAPI)
    calls = []
    def rename(handle, kind, buf, size):
        value = n.RenameInfo.from_buffer(buf)
        name = C.string_at(C.addressof(buf) + n.RenameInfo.FileName.offset, value.FileNameLength).decode('utf-16-le')
        calls.append((handle, kind, value.ReplaceIfExists, value.RootDirectory, name, size))
        return 1
    api.setinfo = rename
    api.rename_relative(22, 33, 'windows-processes.json')
    assert calls[0][:5] == (22, 3, 1, 33, 'windows-processes.json')
    assert n.Overlapped.hEvent.offset == 24 and C.sizeof(n.Overlapped) == 32
    assert n.RenameInfo.RootDirectory.offset == 8 and n.RenameInfo.FileName.offset == 20
