"""Pinned, read-only transport for an EXISTING independent approval adapter.

No source backend, trust root, host installer, identity or approval is created.
The ordinary loader requires a pre-existing protected binding and distinct
non-root API/host identities. The host consumes an already-open listener; it
does not publish, chmod, replace or remove endpoints. Formal provenance and
approval consumption remain outside this transport contract.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
import sys
import threading
import time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .store import Denied
from .resource_plan_approval_read import Lookup, Scope, ReadOnlyApprovalProvider, strict_json

PROTOCOL = 'parkweave-resource-approval-host-read/1'
MAX_FRAME = 131072
MAX_RECORD = 65536
IO_SECONDS = 2.0
KEY = r'^[a-zA-Z0-9_.:-]{1,100}$'
SHA = r'^[a-f0-9]{64}$'


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _path(value):
    if (not Path(value).is_absolute() or str(Path(value)) != value
            or any(x in value for x in ('\0', '\n', '\r')) or '..' in Path(value).parts):
        raise ValueError('canonical absolute public path required')
    return value


class Config(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal['parkweave-resource-approval-host-read/1']
    binding_path: str = Field(min_length=1, max_length=4096)
    binding_sha256: str = Field(pattern=SHA)
    _absolute = field_validator('binding_path')(_path)


class Binding(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal['parkweave-resource-approval-host-binding/1']
    source_id: str = Field(pattern=KEY)
    source_kind: Literal['EXISTING_AUTHORITY_ADAPTER', 'SYNTHETIC_CONTRACT_FIXTURE']
    backend_contract_id: str = Field(pattern=KEY)
    api_uid: int = Field(ge=0)
    api_gid: int = Field(ge=0)
    host_uid: int = Field(ge=0)
    host_gid: int = Field(ge=0)
    socket_path: str = Field(min_length=1, max_length=4096)
    socket_device: int = Field(ge=1)
    socket_inode: int = Field(ge=1)
    host_pid: int = Field(ge=1)
    host_started: str = Field(pattern=r'^[0-9]+$')
    boot_id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    _absolute = field_validator('socket_path')(_path)


def _platform():
    if sys.platform != 'linux' or not hasattr(socket, 'SO_PEERCRED'):
        raise Denied('approval host requires supported Linux peer credentials; no fallback')


def _endpoint(binding):
    from .native_run_access_restricted_host import _process
    from .native_run_access_writer import _socket_stat
    value = _socket_stat(binding.socket_path)
    process = _process(binding.host_pid)
    if (not stat.S_ISSOCK(value.st_mode)
            or (value.st_dev, value.st_ino, value.st_uid, value.st_gid, stat.S_IMODE(value.st_mode)) !=
               (binding.socket_device, binding.socket_inode, binding.host_uid, binding.host_gid, 0o660)
            or process['uids'] != [binding.host_uid] * 4 or process['gids'] != [binding.host_gid] * 4
            or str(process['started']) != binding.host_started
            or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != binding.boot_id):
        raise Denied('approval host process or socket instance changed')


def _load_binding(cfg):
    from .native_run_access_restricted_host import _protected_bytes, _path_chain
    _platform()
    raw = _protected_bytes(cfg.binding_path, 0, expected=cfg.binding_sha256, limit=16384)
    binding = Binding.model_validate(strict_json(raw))
    if (binding.source_kind != 'EXISTING_AUTHORITY_ADAPTER'
            or not binding.api_uid or not binding.host_uid or binding.api_uid == binding.host_uid
            or (os.geteuid(), os.getegid()) != (binding.api_uid, binding.api_gid)
            or binding.host_gid not in [os.getegid(), *os.getgroups()]):
        raise Denied('existing distinct restricted approval host and designated API identity required')
    _path_chain(binding.socket_path, {0, binding.host_uid})
    _endpoint(binding)
    return binding


class WireLookup(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    scope: Scope
    viewer_id: str = Field(min_length=1, max_length=100)
    approval_id: UUID | None = Field(default=None, strict=False)

    def lookup(self):
        return Lookup(self.scope, self.viewer_id, self.approval_id)


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    protocol: Literal['parkweave-resource-approval-host-read/1']
    operation: Literal['READ_EXISTING']
    nonce: str = Field(pattern=r'^[a-f0-9]{32}$')
    binding_sha256: str = Field(pattern=SHA)
    source_id: str = Field(pattern=KEY)
    backend_contract_id: str = Field(pattern=KEY)
    lookup: WireLookup


class VerifyRequest(ReadRequest):
    operation: Literal['VERIFY_EXISTING']
    raw_base64: str = Field(min_length=1, max_length=87384)
    raw_sha256: str = Field(pattern=SHA)


def _record(encoded):
    raw = base64.b64decode(encoded, validate=True)
    if not 1 <= len(raw) <= MAX_RECORD:
        raise Denied('bounded existing approval record required')
    return raw


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Denied('approval source total read budget exhausted')
    return remaining


def _receive(channel, deadline):
    data = bytearray()
    while not data.endswith(b'\n'):
        channel.settimeout(_remaining(deadline))
        part = channel.recv(min(8192, MAX_FRAME + 1 - len(data)))
        if not part or len(data) + len(part) > MAX_FRAME:
            raise Denied('bounded complete approval host frame required')
        data.extend(part)
    return bytes(data[:-1])


class ApprovalHostClient:
    """No private credentials or write RPC. All read RPC share one budget."""
    def __init__(self, cfg, binding):
        self.cfg = cfg
        self._binding_json = binding.model_dump_json()
        self._deadline = ContextVar('approval-host-read-deadline', default=None)

    @property
    def binding(self):
        return Binding.model_validate_json(self._binding_json)

    @contextmanager
    def read_window(self):
        if self._deadline.get() is not None:
            raise Denied('nested approval source read window refused')
        token = self._deadline.set(time.monotonic() + IO_SECONDS)
        try:
            yield
        finally:
            self._deadline.reset(token)

    def rpc(self, operation, lookup, raw=None):
        deadline = self._deadline.get()
        if deadline is None:
            raise Denied('bounded approval read window required')
        if operation not in ('READ_EXISTING', 'VERIFY_EXISTING') or type(lookup) is not Lookup:
            raise Denied('typed read-only approval operation required')
        try:
            _remaining(deadline)
            binding = _load_binding(self.cfg)
            if binding != self.binding:
                raise Denied('approval source binding changed')
            _endpoint(binding)
            value = dict(protocol=PROTOCOL, operation=operation, nonce=secrets.token_hex(16),
                         binding_sha256=self.cfg.binding_sha256, source_id=binding.source_id,
                         backend_contract_id=binding.backend_contract_id,
                         lookup=WireLookup(scope=lookup.scope, viewer_id=lookup.viewer_id,
                                           approval_id=lookup.approval_id).model_dump(mode='json'))
            if operation == 'VERIFY_EXISTING':
                if type(raw) is not bytes or not 1 <= len(raw) <= MAX_RECORD:
                    raise Denied('bounded approval bytes required')
                value.update(raw_base64=base64.b64encode(raw).decode(), raw_sha256=_sha(raw))
            payload = _canonical(value)
            if len(payload) + 1 > MAX_FRAME:
                raise Denied('bounded approval request required')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                channel.settimeout(_remaining(deadline))
                channel.connect(binding.socket_path)
                peer = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                _endpoint(binding)
                if peer != (binding.host_pid, binding.host_uid, binding.host_gid):
                    raise Denied('approval host peer changed')
                channel.settimeout(_remaining(deadline))
                channel.sendall(payload + b'\n')
                reply = strict_json(_receive(channel, deadline))
            _remaining(deadline)
            _load_binding(self.cfg)
            _remaining(deadline)
            expected = dict(protocol=PROTOCOL, nonce=value['nonce'], request_sha256=_sha(payload),
                            binding_sha256=self.cfg.binding_sha256, source_id=binding.source_id,
                            backend_contract_id=binding.backend_contract_id)
            if (type(reply) is not dict or set(reply) != {*expected, 'result', 'error'}
                    or any(reply[k] != v for k, v in expected.items()) or reply['error'] is not None):
                raise Denied('approval host response binding unavailable')
            result = reply['result']
            if operation == 'VERIFY_EXISTING':
                if type(result) is not bool:
                    raise Denied('typed approval verification response required')
                _remaining(deadline)
                return result
            result = None if result is None else _record(result)
            _remaining(deadline)
            return result
        except (OSError, ValueError, TypeError, KeyError):
            raise Denied('existing approval host unavailable; no fallback or retry') from None

    def provider(self):
        binding = self.binding
        return ReadOnlyApprovalProvider(binding.source_id,
            lambda lookup: self.rpc('READ_EXISTING', lookup),
            lambda lookup, raw: self.rpc('VERIFY_EXISTING', lookup, raw),
            binding.source_kind, self.read_window)


def configure(raw, provider=None):
    if raw is None:
        return provider
    if provider is not None:
        raise Denied('one explicit approval provider composition required')
    try:
        if type(raw) is not str or not 1 <= len(raw.encode()) <= 16384:
            raise ValueError()
        cfg = Config.model_validate(strict_json(raw))
        binding = _load_binding(cfg)
        return ApprovalHostClient(cfg, binding).provider()
    except (OSError, ValueError, TypeError, Denied):
        raise Denied('existing protected approval host binding invalid or unavailable; values not echoed') from None


@dataclass(frozen=True)
class ReadOnlyDispatcher:
    """Trusted host composition only. Backend independently verifies its source."""
    provider: ReadOnlyApprovalProvider
    binding: Binding
    binding_sha256: str

    def __post_init__(self):
        if (type(self.provider) is not ReadOnlyApprovalProvider or type(self.binding) is not Binding
                or (self.provider.source_id, self.provider.source_kind) != (self.binding.source_id, self.binding.source_kind)
                or re.fullmatch(SHA, self.binding_sha256) is None):
            raise Denied('exact existing host adapter and public binding required')

    def dispatch(self, raw):
        if type(raw) is not bytes or not 1 <= len(raw) < MAX_FRAME:
            raise Denied('bounded approval request required')
        value = strict_json(raw)
        model = VerifyRequest if type(value) is dict and value.get('operation') == 'VERIFY_EXISTING' else ReadRequest
        request = model.model_validate(value)
        if (request.source_id, request.backend_contract_id, request.binding_sha256) != (
                self.binding.source_id, self.binding.backend_contract_id, self.binding_sha256):
            raise Denied('exact approval source host request required')
        result = None
        error = None
        try:
            lookup = request.lookup.lookup()
            if type(request) is VerifyRequest:
                record = _record(request.raw_base64)
                if _sha(record) != request.raw_sha256:
                    raise Denied('approval record hash mismatch')
                result = self.provider.verify_existing(lookup, record)
                if type(result) is not bool:
                    raise Denied('exact independent verification result required')
            else:
                record = self.provider.read_existing(lookup)
                if record is not None:
                    if type(record) is not bytes or not 1 <= len(record) <= MAX_RECORD:
                        raise Denied('bounded original record required')
                    result = base64.b64encode(record).decode()
        except Exception:
            result, error = None, 'SOURCE_UNAVAILABLE'
        return _canonical(dict(protocol=PROTOCOL, nonce=request.nonce, request_sha256=_sha(raw),
            binding_sha256=self.binding_sha256, source_id=self.binding.source_id,
            backend_contract_id=self.binding.backend_contract_id, result=result, error=error)) + b'\n'


def handle_channel(channel, dispatcher):
    """Serve one already-accepted channel; no endpoint/identity installation."""
    try:
        _platform()
        peer = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if peer[0] <= 0 or peer[1:] != (dispatcher.binding.api_uid, dispatcher.binding.api_gid):
            raise Denied('designated approval API peer required')
        deadline = time.monotonic() + IO_SECONDS
        reply = dispatcher.dispatch(_receive(channel, deadline))
        channel.settimeout(_remaining(deadline))
        channel.sendall(reply)
    except (OSError, ValueError, TypeError, Denied):
        pass  # Close without echoing data, proof, backend exception or credentials.
    finally:
        channel.close()


def serve_listener(listener, dispatcher, stop):
    """Explicit host callback over its existing listener, at most eight handlers.

    The existing backend must bound its own IO. A blocked backend cannot hold an
    API DB transaction beyond the client budget or create unlimited host threads.
    This function never binds/unlinks a path, launches a process or loads code.
    """
    if type(dispatcher) is not ReadOnlyDispatcher or type(stop) is not threading.Event:
        raise Denied('explicit existing approval host composition required')
    _platform()
    if (listener.family != socket.AF_UNIX or listener.type != socket.SOCK_STREAM
            or not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)
            or listener.getsockname() != dispatcher.binding.socket_path
            or (os.getpid(), os.geteuid(), os.getegid()) !=
               (dispatcher.binding.host_pid, dispatcher.binding.host_uid, dispatcher.binding.host_gid)):
        raise Denied('existing exact approval host listener required')
    _endpoint(dispatcher.binding)
    slots = threading.BoundedSemaphore(8)
    listener.settimeout(0.1)
    def run(channel):
        try:
            handle_channel(channel, dispatcher)
        finally:
            slots.release()
    while not stop.is_set():
        try:
            channel, _ = listener.accept()
        except socket.timeout:
            continue
        if not slots.acquire(blocking=False):
            channel.close()
            continue
        try:
            threading.Thread(target=run, args=(channel,), daemon=True).start()
        except BaseException:
            slots.release()
            channel.close()
            raise
