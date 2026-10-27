"""Protocol/fake evidence only: no Windows syscalls or production activation."""
import ast
from dataclasses import replace
import io
import os
from pathlib import Path
import struct

import pytest

from parkweave.windows import create_new_readonly_candidate as m
from parkweave.windows_files import Info

USER = 'S-1-5-21-7'
GROUP = 'S-1-5-32-544'


def acl(sid=USER, *, flags=0, kind=0, mask=0x1f01ff, slack=b''):
    parts = sid.split('-')
    subs = list(map(int, parts[3:]))
    raw_sid = bytes((1, len(subs))) + int(parts[2]).to_bytes(6, 'big')
    raw_sid += struct.pack('<' + 'I' * len(subs), *subs)
    ace = struct.pack('<BBHI', kind, flags, 8 + len(raw_sid), mask) + raw_sid
    return struct.pack('<BBHHH', 2, 0, 8 + len(ace) + len(slack), 1, 0) + ace + slack


PARENT = m.Descriptor(USER, acl(flags=3), 0x1004)
CHILD = m.Descriptor(USER, acl(flags=0x10), 0x404)
PARENT_INFO = Info(0x10, 0, 1, 8, 100)
CHILD_INFO = Info(0x80, 0, 1, 8, 200)
NAME = 'windows-services.log'
REQUEST = m.Request(m.ObjectKind.SERVICE_LOG, m.Operation.CREATE_NEW, NAME)


class Fake:
    def __init__(self):
        self.events = []
        self.user = USER
        self.parent = PARENT
        self.child = CHILD
        self.parent_info = PARENT_INFO
        self.child_info = CHILD_INFO
        self.fail = None
        self.created = False
        self.stream = io.StringIO()
        self.child_reads = 0
        self.after_create = None
        self.after_first = None
        self.close_failure = False
        self.expected_name = NAME

    def event(self, value):
        self.events.append(value)
        if self.fail == value:
            raise OSError('PRIVATE_POISON_PATH_SID')

    def current_user_sid(self):
        self.event('user')
        return self.user

    def info(self, handle):
        assert handle in (10, 20)
        self.event('parent_info' if handle == 10 else 'child_info')
        return self.parent_info if handle == 10 else self.child_info

    def descriptor(self, handle):
        assert handle in (10, 20)
        self.event('parent_descriptor' if handle == 10 else 'child_descriptor')
        if handle == 10:
            return self.parent
        self.child_reads += 1
        value = self.child
        if self.child_reads == 1 and self.after_first:
            self.after_first(self)
        return value

    def create_new(self, parent, name, **kwargs):
        self.event('create')
        assert parent == 10 and name == self.expected_name
        assert kwargs == dict(access=0x00020002, disposition=1, share=0,
                              security_attributes=None)
        if self.created:
            raise FileExistsError('EXISTING_OBJECT')
        self.created = True
        if self.after_create:
            self.after_create(self)
        return 20

    def transfer_fd(self, handle):
        assert handle == 20
        self.event('transfer')
        return 77

    def text_file(self, fd):
        assert fd == 77
        self.event('wrap')
        return self.stream

    def close(self, handle):
        assert handle == 20
        self.events.append('close_handle')
        if self.close_failure:
            raise OSError('PRIVATE_CLEANUP_POISON')

    def close_fd(self, fd):
        assert fd == 77
        self.events.append('close_fd')
        if self.close_failure:
            raise OSError('PRIVATE_CLEANUP_POISON')


def contract(api):
    result = m.verify_private_directory(10, expected_parent=PARENT,
                                        expected_child=CHILD, backend=api)
    api.events.clear()
    return result


def test_stream_after_exact_user_private_parent_and_same_child_handle_checks():
    api = Fake()
    c = contract(api)
    stream = m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert stream is api.stream and stream.getvalue() == ''
    assert api.events == [
        'user', 'parent_info', 'parent_descriptor', 'create',
        'child_info', 'child_descriptor',
        'user', 'parent_info', 'parent_descriptor',
        'child_info', 'child_descriptor',
        'user', 'parent_info', 'parent_descriptor', 'transfer', 'wrap',
    ]
    stream.write('SYNTHETIC_ONLY')
    assert stream.getvalue() == 'SYNTHETIC_ONLY'
    assert not {'close_handle', 'close_fd'} & set(api.events)


def test_default_refuses_without_native_adapter_or_parent_creation():
    with pytest.raises(m.CandidateRefused, match='NATIVE_ADAPTER_NOT_IMPLEMENTED'):
        m.verify_private_directory(10, expected_parent=PARENT, expected_child=CHILD)
    with pytest.raises(m.CandidateRefused, match='NATIVE_ADAPTER_NOT_IMPLEMENTED'):
        m.create_new_readonly_candidate(None, REQUEST)


@pytest.mark.parametrize('name', ['../x', 'x/y', 'x\\y', 'x:stream', 'NUL', '.', 'x.', '\ud800'])
def test_invalid_component_never_calls_backend(name):
    api = Fake()
    c = contract(api)
    with pytest.raises(m.CandidateRefused, match='INVALID_COMPONENT'):
        m.create_new_readonly_candidate(c, m.Request(m.ObjectKind.SERVICE_LOG, m.Operation.CREATE_NEW, name), backend=api)
    assert api.events == []


@pytest.mark.parametrize('change', ['owner', 'unprotected', 'public_allow', 'reparse', 'nondirectory', 'bad_descriptor'])
def test_unsafe_parent_refused_before_creation(change):
    api = Fake()
    if change == 'owner':
        api.parent = replace(PARENT, owner=GROUP)
    elif change == 'unprotected':
        api.parent = replace(PARENT, control=4)
    elif change == 'public_allow':
        api.parent = replace(PARENT, raw_dacl=acl('S-1-1-0'))
    elif change == 'reparse':
        api.parent_info = replace(PARENT_INFO, attributes=0x410)
    elif change == 'nondirectory':
        api.parent_info = replace(PARENT_INFO, attributes=0x80)
    else:
        api.parent = replace(PARENT, raw_dacl=b'INVALID')
    with pytest.raises(m.CandidateRefused):
        m.verify_private_directory(10, expected_parent=api.parent, expected_child=CHILD, backend=api)
    assert 'create' not in api.events


@pytest.mark.parametrize('change', ['user', 'identity', 'descriptor'])
def test_parent_changes_between_verified_contract_and_create_refuse(change):
    api = Fake()
    c = contract(api)
    if change == 'user':
        api.user = GROUP
    elif change == 'identity':
        api.parent_info = replace(PARENT_INFO, identity=101)
    else:
        api.parent = replace(PARENT, raw_dacl=acl(flags=3, slack=b'ABCD'))
    with pytest.raises(m.CandidateRefused):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert not api.created and 'create' not in api.events


@pytest.mark.parametrize('change', ['user', 'identity', 'descriptor', 'reparse'])
def test_parent_drift_after_new_object_retains_empty_object_and_closes(change):
    api = Fake()
    c = contract(api)
    def drift(backend):
        if change == 'user':
            backend.user = GROUP
        elif change == 'identity':
            backend.parent_info = replace(PARENT_INFO, identity=101)
        elif change == 'reparse':
            backend.parent_info = replace(PARENT_INFO, attributes=0x410)
        else:
            backend.parent = replace(PARENT, control=PARENT.control ^ 0x400)
    api.after_create = drift
    with pytest.raises(m.CandidateRefused):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.created and api.stream.getvalue() == ''
    assert 'transfer' not in api.events and api.events[-1] == 'close_handle'


@pytest.mark.parametrize('change', ['owner_group', 'raw_slack', 'raw_mask', 'control', 'owner_defaulted', 'null_acl', 'public_allow'])
def test_child_owner_acl_control_contract_failure_never_transfers_or_repairs(change):
    api = Fake()
    c = contract(api)
    if change == 'owner_group':
        api.child = replace(CHILD, owner=GROUP)
    elif change == 'raw_slack':
        api.child = replace(CHILD, raw_dacl=acl(flags=0x10, slack=b'ABCD'))
    elif change == 'raw_mask':
        api.child = replace(CHILD, raw_dacl=acl(flags=0x10, mask=1))
    elif change in ('control', 'owner_defaulted'):
        api.child = replace(CHILD, control=CHILD.control ^ (0x1000 if change == 'control' else 1))
    elif change == 'null_acl':
        api.child = replace(CHILD, raw_dacl=None)
    else:
        api.child = replace(CHILD, raw_dacl=acl('S-1-1-0'))
    with pytest.raises(m.CandidateRefused):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.created and api.stream.getvalue() == ''
    assert 'transfer' not in api.events and api.events.count('close_handle') == 1


@pytest.mark.parametrize('change', ['reparse', 'directory', 'hardlink', 'size', 'volume'])
def test_created_child_metadata_refused(change):
    api = Fake()
    c = contract(api)
    update = {'reparse': {'attributes': 0x480}, 'directory': {'attributes': 0x10},
              'hardlink': {'links': 2}, 'size': {'size': 1}, 'volume': {'volume': 9}}[change]
    api.child_info = replace(CHILD_INFO, **update)
    with pytest.raises(m.CandidateRefused, match='OBJECT_METADATA_REFUSED'):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.events[-1] == 'close_handle' and 'transfer' not in api.events


@pytest.mark.parametrize('change', ['descriptor', 'identity'])
def test_same_child_handle_second_read_detects_change(change):
    api = Fake()
    c = contract(api)
    def drift(backend):
        if change == 'descriptor':
            backend.child = replace(CHILD, control=CHILD.control ^ 1)
        else:
            backend.child_info = replace(CHILD_INFO, identity=201)
    api.after_first = drift
    with pytest.raises(m.CandidateRefused, match='CHILD_CHANGED'):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.child_reads == 2 and api.events[-1] == 'close_handle'


def test_atomic_create_collision_preserves_existing_object_without_close_or_transfer():
    api = Fake()
    c = contract(api)
    api.created = True
    api.stream.write('SYNTHETIC_EXISTING')
    with pytest.raises(FileExistsError):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.events.count('create') == 1
    assert api.stream.getvalue() == 'SYNTHETIC_EXISTING'
    assert not {'transfer', 'close_handle', 'close_fd'} & set(api.events)


def test_backend_parent_handle_alias_refuses_without_closing_borrowed_parent():
    class Aliased(Fake):
        def create_new(self, parent, name, **kwargs):
            self.event('create')
            return parent
    api = Aliased()
    c = contract(api)
    with pytest.raises(m.CandidateRefused, match='BORROWED_PARENT_HANDLE'):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.events[-1] == 'create'
    assert not {'child_info', 'child_descriptor', 'transfer', 'close_handle', 'close_fd'} & set(api.events)
    assert api.info(c.handle) == PARENT_INFO


@pytest.mark.parametrize('phase', ['child_info', 'child_descriptor', 'transfer', 'wrap'])
def test_failure_resources_closed_once_and_private_error_redacted(phase):
    api = Fake()
    c = contract(api)
    api.fail = phase
    with pytest.raises(m.CandidateRefused, match='CANDIDATE_OPERATION_REFUSED') as caught:
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert 'POISON' not in str(caught.value)
    expected = 'close_fd' if phase == 'wrap' else 'close_handle'
    assert api.events[-1] == expected and api.events.count(expected) == 1
    assert ('close_handle' not in api.events) if phase == 'wrap' else ('close_fd' not in api.events)
    assert api.created and api.stream.getvalue() == ''


def test_cleanup_refusal_preserves_primary_owner_mismatch_and_fixed_annotation():
    api = Fake()
    c = contract(api)
    api.child = replace(CHILD, owner=GROUP)
    api.close_failure = True
    with pytest.raises(m.CandidateRefused, match='OWNER_MISMATCH') as caught:
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert caught.value.candidate_cleanup_failed is True
    assert api.events.count('close_handle') == 1 and 'POISON' not in str(caught.value)


@pytest.mark.parametrize('raw', [b'', b'12345678', acl()[:-1], acl(flags=0x20), acl(kind=5)])
def test_malformed_acl_contract_rejected_before_creation(raw):
    api = Fake()
    with pytest.raises(m.CandidateRefused, match='DESCRIPTOR_REFUSED'):
        m.verify_private_directory(10, expected_parent=PARENT,
                                   expected_child=replace(CHILD, raw_dacl=raw), backend=api)
    assert 'create' not in api.events


def test_candidate_is_unwired_with_no_native_setters_or_access_expansion():
    source = Path(m.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    call_names = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not call_names & {'SetSecurityInfo', 'SetOwner', 'SetAcl', 'SetAccessControl',
                            'unlink', 'WinDLL', 'exists', 'lstat'}
    assert m.CREATE_ACCESS == 0x00020002
    # No generic bits: this mask has no FILE_GENERIC_WRITE mapping to conceal
    # SYNCHRONIZE, write-EA or write-attributes. Native/CRT acceptance NOT_RUN.
    assert m.CREATE_ACCESS & (0xf0000000 | 0x80000 | 0x40000 | 0x100000 | 0x10 | 0x100) == 0
    assert m.CREATE_NEW == 1 and m.SHARE_NONE == 0
    production = Path(m.__file__).parents[1] / 'synthetic_session_file.py'
    assert 'create_new_readonly_candidate' not in production.read_text(encoding='utf-8')


@pytest.mark.parametrize('kind,name', [
    (m.ObjectKind.SESSION, 'synthetic-sessions.json'),
    (m.ObjectKind.CONFIG, 'windows-config.json'),
    (m.ObjectKind.SERVICE_LOG, 'windows-services.log'),
    (m.ObjectKind.PROCESS_RECORD_INITIAL, 'windows-processes.json'),
    (m.ObjectKind.BINDING_TEMP, '.process-binding-' + 'a' * 32 + '.json'),
])
def test_explicit_creation_roles_match_only_their_new_object_basenames(kind, name):
    api = Fake()
    c = contract(api)
    api.expected_name = name
    stream = m.create_new_readonly_candidate(c, m.Request(kind, m.Operation.CREATE_NEW, name), backend=api)
    assert stream.getvalue() == '' and api.created


@pytest.mark.parametrize('kind,name', [
    (m.ObjectKind.CONFIG, 'synthetic-sessions.json'),
    (m.ObjectKind.SERVICE_LOG, 'windows-processes.json'),
    (m.ObjectKind.PROCESS_RECORD_INITIAL, 'windows-services.log'),
    (m.ObjectKind.BINDING_TEMP, '.process-binding-abc.json'),
    (m.ObjectKind.BINDING_TEMP, '.process-binding-' + 'A' * 32 + '.json'),
    (m.ObjectKind.PROCESS_RECORD_REPLACEMENT, 'windows-processes.json'),
])
def test_wrong_role_basename_cannot_create(kind, name):
    api = Fake()
    c = contract(api)
    with pytest.raises(m.CandidateRefused, match='OBJECT_BASENAME_MISMATCH'):
        m.create_new_readonly_candidate(c, m.Request(kind, m.Operation.CREATE_NEW, name), backend=api)
    assert api.events == []


def test_atomic_replacement_final_object_refuses_without_backend_calls():
    api = Fake()
    c = contract(api)
    request = m.Request(m.ObjectKind.PROCESS_RECORD_REPLACEMENT,
                        m.Operation.ATOMIC_REPLACEMENT, 'windows-processes.json')
    with pytest.raises(m.CandidateRefused, match='ATOMIC_REPLACEMENT_NOT_IMPLEMENTED'):
        m.create_new_readonly_candidate(c, request, backend=api)
    with pytest.raises(m.CandidateRefused, match='ATOMIC_REPLACEMENT_NOT_IMPLEMENTED'):
        m.replace_process_record_candidate(c, request, backend=api)
    assert api.events == []


@pytest.mark.parametrize('item', [None, NAME, m.Request('SERVICE_LOG', m.Operation.CREATE_NEW, NAME),
                                     m.Request(m.ObjectKind.SERVICE_LOG, 'CREATE_NEW', NAME)])
def test_untyped_object_contract_refuses_before_create(item):
    api = Fake()
    c = contract(api)
    with pytest.raises(m.CandidateRefused, match='OBJECT_CONTRACT_REQUIRED'):
        m.create_new_readonly_candidate(c, item, backend=api)
    assert api.events == []


@pytest.mark.parametrize('control', [0x40, 0x80, 0x4c4, 0x400, True, -1, 0x10000])
def test_unknown_or_absent_dacl_control_refuses_before_create(control):
    api = Fake()
    with pytest.raises(m.CandidateRefused, match='DESCRIPTOR_REFUSED'):
        m.verify_private_directory(10, expected_parent=PARENT,
                                   expected_child=replace(CHILD, control=control), backend=api)
    assert 'create' not in api.events


class OrdinaryFixture(Fake):
    """Actual Linux exclusive bytes/FD cleanup, with synthetic descriptor data.

    These operations neither set nor measure Windows owner, ACL or reparse
    semantics. This fixture cannot be selected as the candidate default.
    """
    def __init__(self, root):
        super().__init__()
        self.path = root / NAME
        self.fd = None

    def create_new(self, parent, name, **kwargs):
        super().create_new(parent, name, **kwargs)
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        return 20

    def transfer_fd(self, handle):
        self.event('transfer')
        assert handle == 20
        return self.fd

    def text_file(self, fd):
        self.event('wrap')
        return os.fdopen(fd, 'w', encoding='utf-8')

    def close(self, handle):
        assert handle == 20
        self.events.append('close_handle')
        os.close(self.fd)

    def close_fd(self, fd):
        self.events.append('close_fd')
        os.close(fd)


def test_ordinary_synthetic_fixture_failure_retains_actual_empty_file_and_closed_fd(tmp_path):
    api = OrdinaryFixture(tmp_path)
    c = contract(api)
    api.child = replace(CHILD, owner=GROUP)
    with pytest.raises(m.CandidateRefused, match='OWNER_MISMATCH'):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.path.exists() and api.path.read_bytes() == b''
    with pytest.raises(OSError):
        os.fstat(api.fd)
    assert api.events.count('close_handle') == 1


def test_ordinary_synthetic_fixture_existing_bytes_never_overwritten(tmp_path):
    api = OrdinaryFixture(tmp_path)
    c = contract(api)
    api.path.write_bytes(b'SYNTHETIC_PROTECTED')
    with pytest.raises(FileExistsError):
        m.create_new_readonly_candidate(c, REQUEST, backend=api)
    assert api.path.read_bytes() == b'SYNTHETIC_PROTECTED'
    assert api.fd is None and 'close_handle' not in api.events


def test_ordinary_synthetic_fixture_stream_transfer_closes_fd_without_second_handle_close(tmp_path):
    api = OrdinaryFixture(tmp_path)
    c = contract(api)
    with m.create_new_readonly_candidate(c, REQUEST, backend=api) as stream:
        stream.write('SYNTHETIC_ONLY')
    assert api.path.read_text() == 'SYNTHETIC_ONLY'
    with pytest.raises(OSError):
        os.fstat(api.fd)
    assert not {'close_handle', 'close_fd'} & set(api.events)
