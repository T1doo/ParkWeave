"""CREATE_NEW protocol candidate, with no native adapter or production caller.

The backend seam must create relative to the held, verified directory handle.
There is deliberately no pathname fallback: native race/CRT semantics remain
unproven. No owner/ACL setter, security descriptor installation or privileges.
"""
from dataclasses import dataclass
from enum import Enum
import re
import struct
import sys
from typing import Protocol, TextIO

from ..windows_files import Info, Security, Ace, component, private_acl
from ..store import Denied

FILE_WRITE_DATA = 0x00000002
READ_CONTROL = 0x00020000
CREATE_ACCESS = FILE_WRITE_DATA | READ_CONTROL
CREATE_NEW = 1  # Win32 semantic vocabulary; not NtCreateFile's disposition value.
SHARE_NONE = 0
DIRECTORY = 0x10
REPARSE = 0x400
UNSAFE_ATTRIBUTES = 0x40 | 0x1000 | 0x40000 | 0x400000
DACL_PRESENT = 0x4
PROTECTED = 0x1000
TRUSTED_SYSTEM = frozenset({'S-1-5-18', 'S-1-5-32-544'})


class CandidateRefused(RuntimeError):
    """Fixed reasons only: no private paths, SIDs, ACLs or native error text."""


class ObjectKind(Enum):
    SESSION = 'SESSION'
    CONFIG = 'CONFIG'
    SERVICE_LOG = 'SERVICE_LOG'
    PROCESS_RECORD_INITIAL = 'PROCESS_RECORD_INITIAL'
    BINDING_TEMP = 'BINDING_TEMP'
    PROCESS_RECORD_REPLACEMENT = 'PROCESS_RECORD_REPLACEMENT'


class Operation(Enum):
    CREATE_NEW = 'CREATE_NEW'
    ATOMIC_REPLACEMENT = 'ATOMIC_REPLACEMENT'


@dataclass(frozen=True)
class Request:
    kind: ObjectKind
    operation: Operation
    basename: str


@dataclass(frozen=True)
class Descriptor:
    owner: str
    raw_dacl: bytes
    control: int


@dataclass(frozen=True)
class DirectoryContract:
    # Caller retains this parent handle until the returned stream closes.
    handle: int
    identity: Info
    descriptor: Descriptor
    user_sid: str
    expected_child: Descriptor


class Backend(Protocol):
    def current_user_sid(self) -> str: ...
    def info(self, handle: int) -> Info: ...
    def descriptor(self, handle: int) -> Descriptor:
        """Validate OWNER|DACL descriptor, copy bytes, release native allocation."""
        ...
    def create_new(self, parent: int, name: str, *, access: int,
                   disposition: int, share: int, security_attributes: None) -> int:
        """Atomic exclusive regular-file creation relative to exact held parent.

        Never follow a reparse point; existing object/race raises FileExistsError.
        Failure after acquisition must close its own handle, retaining the object.
        Return only a fresh child handle, never the caller-owned parent handle.
        Exact FILE_WRITE_DATA|READ_CONTROL only: no generic mapping, explicit
        SYNCHRONIZE, WRITE_OWNER/WRITE_DAC, setter or injected descriptor.
        """
        ...
    def transfer_fd(self, handle: int) -> int:
        """Only success transfers handle ownership; failure leaves it to caller."""
        ...
    def text_file(self, fd: int) -> TextIO:
        """Only success transfers fd ownership; failure leaves it to caller."""
        ...
    def close(self, handle: int) -> None: ...
    def close_fd(self, fd: int) -> None: ...


def _handle(value):
    if type(value) is not int or not 0 < value < (1 << 64) - 1:
        raise CandidateRefused('INVALID_HANDLE')


def _sid(value):
    # No SID normalization or display-name parsing.
    if (type(value) is not str or len(value) > 184
            or not re.fullmatch(r'S-1-[0-9]+(?:-[0-9]+){1,15}', value)):
        raise CandidateRefused('DESCRIPTOR_REFUSED')
    return value


def _aces(raw):
    # Restricted basic allow/deny ACEs only. Raw bytes remain the contract,
    # including unused capacity and reserved fields; never normalize equality.
    if type(raw) is not bytes or not 8 <= len(raw) <= 65535:
        raise CandidateRefused('DESCRIPTOR_REFUSED')
    revision, reserved, size, count, reserved2 = struct.unpack_from('<BBHHH', raw)
    if (revision not in (2, 4) or size != len(raw) or size % 4
            or reserved or reserved2 or not 1 <= count <= 128):
        raise CandidateRefused('DESCRIPTOR_REFUSED')
    cursor = 8
    result = []
    for _ in range(count):
        if cursor + 16 > size:
            raise CandidateRefused('DESCRIPTOR_REFUSED')
        kind, flags, length, mask = struct.unpack_from('<BBHI', raw, cursor)
        if (kind not in (0, 1) or flags & ~0x1f or length < 16
                or length % 4 or cursor + length > size):
            raise CandidateRefused('DESCRIPTOR_REFUSED')
        sid = raw[cursor + 8:cursor + length]
        if sid[0] != 1 or not 1 <= sid[1] <= 15 or len(sid) != 8 + 4 * sid[1]:
            raise CandidateRefused('DESCRIPTOR_REFUSED')
        authority = int.from_bytes(sid[2:8], 'big')
        subs = struct.unpack_from('<' + 'I' * sid[1], sid, 8)
        result.append(Ace(kind, flags, mask, 'S-1-' + str(authority)
                          + ''.join('-' + str(sub) for sub in subs)))
        cursor += length
    return tuple(result)


def _private_descriptor(value, user, *, directory):
    if (type(value) is not Descriptor or type(value.control) is not int
            or not 0 <= value.control <= 0xffff):
        raise CandidateRefused('DESCRIPTOR_REFUSED')
    if _sid(value.owner) != user:
        raise CandidateRefused('OWNER_MISMATCH')
    if not value.control & DACL_PRESENT or value.control & 0xc0:
        raise CandidateRefused('DESCRIPTOR_REFUSED')
    aces = _aces(value.raw_dacl)
    if directory:
        # Existing strict read-only directory policy: current User owner,
        # protected DACL, supported ACEs and only trusted allow SIDs.
        try:
            private_acl(Security(value.owner, value.control, aces), user)
        except Denied:
            raise CandidateRefused('UNSAFE_PARENT') from None
    else:
        # A child may inherit supported ACEs; expected raw bytes/control must
        # be explicitly supplied, not guessed from the directory descriptor.
        if any(ace.kind == 0 and ace.sid not in ({user} | TRUSTED_SYSTEM)
               for ace in aces):
            raise CandidateRefused('UNSAFE_CHILD')


def _metadata(value, *, directory, volume=None):
    if (type(value) is not Info or any(type(v) is not int for v in
            (value.attributes, value.size, value.links, value.volume, value.identity))
            or value.attributes < 0 or value.size < 0 or value.links < 1
            or value.volume < 0 or value.identity <= 0
            or value.attributes & (REPARSE | UNSAFE_ATTRIBUTES)
            or bool(value.attributes & DIRECTORY) != directory
            or (volume is not None and value.volume != volume)
            or (not directory and (value.links != 1 or value.size != 0))):
        raise CandidateRefused('OBJECT_METADATA_REFUSED')


def _backend(backend):
    if backend is None:
        raise CandidateRefused('NATIVE_ADAPTER_NOT_IMPLEMENTED')
    return backend


def verify_private_directory(handle, *, expected_parent, expected_child, backend=None):
    """Readonly verification of an explicitly caller-held directory.

    Caller must prove directory handle provenance/local filesystem, lifetime
    and scope separately. This function does not open, create or protect it.
    """
    api = _backend(backend)
    _handle(handle)
    try:
        user = _sid(api.current_user_sid())
        _private_descriptor(expected_parent, user, directory=True)
        _private_descriptor(expected_child, user, directory=False)
        info = api.info(handle)
        _metadata(info, directory=True)
        observed = api.descriptor(handle)
        _private_descriptor(observed, user, directory=True)
        if observed != expected_parent:
            raise CandidateRefused('PARENT_CONTRACT_MISMATCH')
        contract = DirectoryContract(handle, info, observed, user, expected_child)
        _check_parent(api, contract)
        return contract
    except CandidateRefused:
        raise
    except Exception:
        raise CandidateRefused('PARENT_READ_REFUSED') from None


def _check_parent(api, contract):
    if api.current_user_sid() != contract.user_sid:
        raise CandidateRefused('USER_CHANGED')
    info = api.info(contract.handle)
    _metadata(info, directory=True)
    observed = api.descriptor(contract.handle)
    _private_descriptor(observed, contract.user_sid, directory=True)
    if info != contract.identity or observed != contract.descriptor:
        raise CandidateRefused('PARENT_CHANGED')


def _request(request):
    if (type(request) is not Request or type(request.kind) is not ObjectKind
            or type(request.operation) is not Operation):
        raise CandidateRefused('OBJECT_CONTRACT_REQUIRED')
    if request.operation is not Operation.CREATE_NEW:
        raise CandidateRefused('ATOMIC_REPLACEMENT_NOT_IMPLEMENTED')
    fixed = {ObjectKind.SESSION: 'synthetic-sessions.json',
             ObjectKind.CONFIG: 'windows-config.json',
             ObjectKind.SERVICE_LOG: 'windows-services.log',
             ObjectKind.PROCESS_RECORD_INITIAL: 'windows-processes.json'}
    try:
        component(request.basename)
    except (Denied, UnicodeError):
        raise CandidateRefused('INVALID_COMPONENT') from None
    if request.kind is ObjectKind.BINDING_TEMP:
        if not re.fullmatch(r'\.process-binding-[0-9a-f]{32}\.json', request.basename):
            raise CandidateRefused('OBJECT_BASENAME_MISMATCH')
    elif request.kind not in fixed or request.basename != fixed[request.kind]:
        raise CandidateRefused('OBJECT_BASENAME_MISMATCH')
    return request.basename


def create_new_readonly_candidate(contract, request, *, backend=None):
    """Content stream only after same-handle checks; never delete on failure.

    Independent test seam; no native default, production integration or path
    fallback. Caller owns the parent handle; returned stream owns only child.
    """
    api = _backend(backend)
    if type(contract) is not DirectoryContract:
        raise CandidateRefused('DIRECTORY_CONTRACT_REQUIRED')
    _handle(contract.handle)
    name = _request(request)
    # Validate even a manually assembled contract before the backend creates.
    _sid(contract.user_sid)
    _metadata(contract.identity, directory=True)
    _private_descriptor(contract.descriptor, contract.user_sid, directory=True)
    _private_descriptor(contract.expected_child, contract.user_sid, directory=False)
    handle = fd = None
    try:
        _check_parent(api, contract)
        created = api.create_new(contract.handle, name, access=CREATE_ACCESS,
                                 disposition=CREATE_NEW, share=SHARE_NONE,
                                 security_attributes=None)
        _handle(created)
        if created == contract.handle:
            raise CandidateRefused('BORROWED_PARENT_HANDLE')
        handle = created  # Adopt only a validated, non-parent fresh child.
        first_info = api.info(handle)
        _metadata(first_info, directory=False, volume=contract.identity.volume)
        first = api.descriptor(handle)
        _private_descriptor(first, contract.user_sid, directory=False)
        if first != contract.expected_child:
            raise CandidateRefused('CHILD_CONTRACT_MISMATCH')
        _check_parent(api, contract)
        second_info = api.info(handle)
        _metadata(second_info, directory=False, volume=contract.identity.volume)
        second = api.descriptor(handle)
        _private_descriptor(second, contract.user_sid, directory=False)
        if second_info != first_info or second != first:
            raise CandidateRefused('CHILD_CHANGED')
        _check_parent(api, contract)
        fd = api.transfer_fd(handle)
        handle = None  # Only successful transfer changes the resource owner.
        if type(fd) is not int or fd < 0:
            raise CandidateRefused('FD_TRANSFER_REFUSED')
        stream = api.text_file(fd)
        fd = None
        return stream
    except (CandidateRefused, FileExistsError):
        raise
    except Exception:
        raise CandidateRefused('CANDIDATE_OPERATION_REFUSED') from None
    finally:
        # A backend close failure remains a refusal. No path reopen/unlink,
        # second close, owner/ACL repair or content write before verification.
        primary = sys.exc_info()[1]
        cleanup_failed = False
        if handle is not None:
            try:
                api.close(handle)
            except Exception:
                cleanup_failed = True
        if fd is not None:
            try:
                api.close_fd(fd)
            except Exception:
                cleanup_failed = True
        if cleanup_failed:
            if primary is not None:
                primary.candidate_cleanup_failed = True
            else:
                raise CandidateRefused('CLEANUP_REFUSED') from None


def replace_process_record_candidate(*args, **kwargs):
    """No safe final-inode replacement adapter has been implemented.

    A verified BINDING_TEMP stream does not verify target identity, publication
    races, inherited metadata or final STATE. Never call os.replace as fallback.
    """
    raise CandidateRefused('ATOMIC_REPLACEMENT_NOT_IMPLEMENTED')
