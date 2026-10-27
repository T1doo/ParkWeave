"""Default-closed generation/authority model; no deployed protected authority.

Only explicit fault-injection protocol tests can supply the seams below. Local
immutable names, hashes and synthetic inode checks are not an OS trust boundary.
No process actions, security setters, identity-file overwrite or rename.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from uuid import UUID

LIMIT = 32768
MAX_CHAIN = 256
ZERO_DIGEST = '0' * 64


class GenerationRefused(RuntimeError):
    pass


class Scope(Enum):
    ISOLATED_PROTOCOL_TEST = 'ISOLATED_PROTOCOL_TEST'
    FAULT_INJECTION = 'FAULT_INJECTION'


class Event(Enum):
    ROOT_CREATED = 'ROOT_CREATED'
    BIND_API = 'BIND_API'
    BIND_WORKER = 'BIND_WORKER'
    STOP_INTENT = 'STOP_INTENT'
    STOP_CONFIRMED = 'STOP_CONFIRMED'


class Status(Enum):
    COMMITTED = 'COMMITTED'
    CONFLICT = 'CONFLICT'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True)
class FileIdentity:
    volume: int
    file_id: int


@dataclass(frozen=True)
class FileSnapshot:
    identity: FileIdentity
    data: bytes


@dataclass(frozen=True)
class FileRef:
    name: str
    identity: FileIdentity
    digest: str


@dataclass(frozen=True)
class RootBinding:
    root_id: str
    identity: FileIdentity
    root_digest: str
    config_digest: str
    session_digest: str
    source_digest: str
    permissions_digest: str


@dataclass(frozen=True)
class ProcessIdentity:
    role: str
    pid: int
    created_ticks: int
    command_digest: str
    server_pid: int | None = None
    server_created_ticks: int | None = None
    server_parent_pid: int | None = None
    server_parent_created_ticks: int | None = None


@dataclass(frozen=True)
class RunIdentity:
    epoch: str
    session_id: str
    processes: tuple[ProcessIdentity, ...]


@dataclass(frozen=True)
class Checkpoint:
    revision: int
    reference: FileRef
    epoch: str
    event: Event
    run_digest: str


@dataclass(frozen=True)
class Authorization:
    scope: Scope
    root_id: str
    event: Event
    run_digest: str
    nonce: str
    proof_id: str


@dataclass(frozen=True)
class PendingCommit:
    key: str
    request_digest: str
    root: RootBinding
    expected_checkpoint: Checkpoint | None
    proposed_checkpoint: Checkpoint
    authorization: Authorization


@dataclass(frozen=True)
class AuthorityView:
    scope: Scope
    root: RootBinding
    nonce: str
    checkpoint: Checkpoint | None
    pending: PendingCommit | None = None


@dataclass(frozen=True)
class CommitResult:
    scope: Scope
    key: str
    request_digest: str
    status: Status
    checkpoint: Checkpoint | None
    nonce: str | None = None


def _refuse(reason):
    raise GenerationRefused(reason)


def _uuid(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        _refuse('INVALID_ID')


def _digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        _refuse('INVALID_DIGEST')


def _identity(value):
    if (type(value) is not FileIdentity or type(value.volume) is not int
            or not 0 <= value.volume < 1 << 64 or type(value.file_id) is not int
            or not 0 < value.file_id < 1 << 128):
        _refuse('INVALID_FILE_IDENTITY')


def canonical(value):
    try:
        data = json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        _refuse('INVALID_DOCUMENT')
    if len(data) > LIMIT:
        _refuse('DOCUMENT_LIMIT')
    return data


def digest(data):
    if type(data) is not bytes or len(data) > LIMIT:
        _refuse('INVALID_DOCUMENT')
    return hashlib.sha256(data).hexdigest()


def root_document(root_id, config_digest, session_digest, source_digest, permissions_digest):
    _uuid(root_id)
    for value in (config_digest, session_digest, source_digest, permissions_digest):
        _digest(value)
    return canonical(dict(schema=1, root_id=root_id, config_digest=config_digest,
                          session_digest=session_digest, source_digest=source_digest,
                          permissions_digest=permissions_digest))


def _run_json(run):
    if type(run) is not RunIdentity or type(run.processes) is not tuple:
        _refuse('INVALID_RUN')
    _uuid(run.epoch)
    _uuid(run.session_id)
    if (any(type(item) is not ProcessIdentity for item in run.processes)
            or tuple(item.role for item in run.processes) != ('API', 'WORKER')):
        _refuse('INVALID_RUN')
    processes = []
    for item in run.processes:
        if (type(item) is not ProcessIdentity or type(item.pid) is not int
                or not 0 < item.pid <= 0xffffffff or type(item.created_ticks) is not int
                or not 0 < item.created_ticks < 1 << 64):
            _refuse('INVALID_PROCESS_IDENTITY')
        _digest(item.command_digest)
        server = (item.server_pid, item.server_created_ticks)
        if server != (None, None):
            if (type(server[0]) is not int or not 0 < server[0] <= 0xffffffff
                    or type(server[1]) is not int or not 0 < server[1] < 1 << 64):
                _refuse('INVALID_PROCESS_IDENTITY')
            if server[0] == item.pid:
                if server[1] != item.created_ticks:
                    _refuse('INVALID_PROCESS_IDENTITY')
            elif (item.server_parent_pid != item.pid
                  or item.server_parent_created_ticks != item.created_ticks):
                _refuse('INVALID_PROCESS_IDENTITY')
        elif (item.server_parent_pid, item.server_parent_created_ticks) != (None, None):
            _refuse('INVALID_PROCESS_IDENTITY')
        processes.append(dict(role=item.role, pid=item.pid, created_ticks=item.created_ticks,
                              command_digest=item.command_digest, server_pid=item.server_pid,
                              server_created_ticks=item.server_created_ticks,
                              server_parent_pid=item.server_parent_pid,
                              server_parent_created_ticks=item.server_parent_created_ticks))
    if run.processes[0].pid == run.processes[1].pid:
        _refuse('INVALID_PROCESS_IDENTITY')
    return dict(epoch=run.epoch, session_id=run.session_id, processes=processes)


def run_digest(run):
    return digest(canonical(_run_json(run)))


def _ref_json(ref):
    if ref is None:
        return None
    if type(ref) is not FileRef:
        _refuse('INVALID_REFERENCE')
    _identity(ref.identity)
    _digest(ref.digest)
    if type(ref.name) is not str or not re.fullmatch(r'gen-[0-9a-f-]{36}-[0-9]{20}-[0-9a-f]{64}\.json', ref.name):
        _refuse('INVALID_REFERENCE')
    return dict(name=ref.name, volume=ref.identity.volume, file_id=ref.identity.file_id, digest=ref.digest)


def _checkpoint_json(point):
    if point is None:
        return None
    if (type(point) is not Checkpoint or type(point.revision) is not int
            or not 0 < point.revision <= MAX_CHAIN or type(point.event) is not Event
            or type(point.reference) is not FileRef):
        _refuse('INVALID_CHECKPOINT')
    _uuid(point.epoch)
    _digest(point.run_digest)
    return dict(revision=point.revision, reference=_ref_json(point.reference), epoch=point.epoch,
                event=point.event.value, run_digest=point.run_digest)


def _request_digest(pending):
    return digest(canonical(dict(key=pending.key, root_id=pending.root.root_id,
                                 expected=_checkpoint_json(pending.expected_checkpoint),
                                 proposed=_checkpoint_json(pending.proposed_checkpoint),
                                 authorization=dict(scope=pending.authorization.scope.value,
                                                    nonce=pending.authorization.nonce,
                                                    proof_id=pending.authorization.proof_id,
                                                    event=pending.authorization.event.value,
                                                    run_digest=pending.authorization.run_digest))))


def _transition(previous_event, previous, event, run):
    _run_json(run)
    if type(event) is not Event:
        _refuse('INVALID_EVENT')
    if event is Event.ROOT_CREATED:
        if previous_event not in (None, Event.STOP_CONFIRMED):
            _refuse('RUN_ALREADY_ACTIVE')
        if previous is not None and (run.epoch == previous.epoch or run.session_id == previous.session_id):
            _refuse('OLD_EPOCH_REPLAY')
        if any(item.server_pid is not None for item in run.processes):
            _refuse('INVALID_INITIAL_BINDING')
        return
    if previous is None or run.epoch != previous.epoch or run.session_id != previous.session_id:
        _refuse('RUN_BINDING_MISMATCH')
    if event in (Event.STOP_INTENT, Event.STOP_CONFIRMED):
        allowed = (Event.BIND_WORKER,) if event is Event.STOP_INTENT else (Event.STOP_INTENT,)
        if previous_event not in allowed or run != previous:
            _refuse('STOP_BINDING_MISMATCH')
        return
    index = 0 if event is Event.BIND_API else 1
    if (event not in (Event.BIND_API, Event.BIND_WORKER)
            or previous_event is not (Event.ROOT_CREATED if index == 0 else Event.BIND_API)):
        _refuse('INVALID_TRANSITION')
    for pos, (before, after) in enumerate(zip(previous.processes, run.processes)):
        if pos != index:
            if after != before:
                _refuse('PROCESS_BINDING_CHANGED')
        elif (before.server_pid is not None or after.server_pid is None
              or (before.role, before.pid, before.created_ticks, before.command_digest)
              != (after.role, after.pid, after.created_ticks, after.command_digest)):
            _refuse('PROCESS_BINDING_CHANGED')


class GenerationCandidate:
    """Only an explicitly labelled fault-injection model has a factory.

    Authority seam: read(root,nonce), authorize(root,event,run,nonce),
    validate_authorization(auth), commit(PendingCommit),
    resolve(root,key,request_digest,nonce). No production adapter is supplied.
    """
    def __init__(self):
        self.authority = self.storage = self.root = self.scope = None
        self._pending, self._unknown, self._floor = None, False, 0

    @classmethod
    def for_protocol_tests(cls, *, storage, authority, root, scope):
        if type(scope) is not Scope or getattr(authority, 'scope', None) is not scope:
            _refuse('EXPLICIT_TEST_SCOPE_REQUIRED')
        value = cls()
        value.storage, value.authority, value.root, value.scope = storage, authority, root, scope
        value._root_check()
        return value

    def _available(self):
        if self.authority is None or self.scope is None:
            _refuse('MISSING_PROTECTED_AUTHORITY')

    def _root_check(self):
        self._available()
        if type(self.root) is not RootBinding:
            _refuse('INVALID_ROOT_BINDING')
        _identity(self.root.identity)
        expected = root_document(self.root.root_id, self.root.config_digest, self.root.session_digest,
                                 self.root.source_digest, self.root.permissions_digest)
        snapshot = self.storage.read_root()
        if (type(snapshot) is not FileSnapshot or snapshot.identity != self.root.identity
                or snapshot.data != expected or digest(snapshot.data) != self.root.root_digest):
            _refuse('ROOT_IDENTITY_CHANGED')

    def _view(self):
        self._root_check()
        nonce = secrets.token_hex(32)
        try:
            view = self.authority.read(self.root, nonce)
        except Exception:
            _refuse('AUTHORITY_UNAVAILABLE')
        if (type(view) is not AuthorityView or view.scope is not self.scope
                or view.root != self.root or view.nonce != nonce):
            _refuse('FRESH_AUTHORITY_REQUIRED')
        revision = 0 if view.checkpoint is None else view.checkpoint.revision
        if type(revision) is not int or revision < self._floor:
            _refuse('AUTHORITY_ROLLBACK')
        return view, nonce

    def _load(self, point):
        if point is None:
            return None
        _checkpoint_json(point)
        ref, chain, seen = point.reference, [], set()
        while ref is not None:
            _ref_json(ref)
            if ref.name in seen or len(chain) >= MAX_CHAIN:
                _refuse('CHAIN_FORK_OR_LIMIT')
            seen.add(ref.name)
            try:
                snapshot = self.storage.read_generation(ref.name)
            except Exception:
                _refuse('ANCHORED_GENERATION_UNAVAILABLE')
            if (type(snapshot) is not FileSnapshot or snapshot.identity != ref.identity
                    or digest(snapshot.data) != ref.digest):
                _refuse('GENERATION_IDENTITY_CHANGED')
            try:
                body = json.loads(snapshot.data)
                if (canonical(body) != snapshot.data or set(body) != {'schema', 'root_id', 'sequence', 'event', 'run', 'previous'}
                        or body['schema'] != 1 or body['root_id'] != self.root.root_id):
                    raise ValueError()
                run = RunIdentity(body['run']['epoch'], body['run']['session_id'],
                                  tuple(ProcessIdentity(**item) for item in body['run']['processes']))
                if _run_json(run) != body['run']:
                    raise ValueError()
                event = Event(body['event'])
                seq = body['sequence']
                if type(seq) is not int or not 0 <= seq < MAX_CHAIN:
                    raise ValueError()
                name = f'gen-{run.epoch}-{seq:020d}-{ref.digest}.json'
                if name != ref.name:
                    raise ValueError()
                prev = body['previous']
                if prev is not None:
                    if set(prev) != {'name', 'volume', 'file_id', 'digest'}:
                        raise ValueError()
                    prev = FileRef(prev['name'], FileIdentity(prev['volume'], prev['file_id']), prev['digest'])
            except GenerationRefused:
                raise
            except Exception:
                _refuse('INVALID_GENERATION')
            chain.append((seq, event, run))
            ref = prev
        last_event = last_run = None
        for expected_seq, (seq, event, run) in enumerate(reversed(chain)):
            if seq != expected_seq:
                _refuse('CHAIN_GAP')
            _transition(last_event, last_run, event, run)
            last_event, last_run = event, run
        if (len(chain) != point.revision or last_event is not point.event
                or last_run.epoch != point.epoch or run_digest(last_run) != point.run_digest):
            _refuse('CHECKPOINT_BINDING_MISMATCH')
        return last_run

    def recover(self):
        self._available()
        if self._pending is not None:
            _refuse('COMMIT_OUTCOME_UNKNOWN' if self._unknown else 'PREPARED_REQUEST_OUTSTANDING')
        view, _ = self._view()
        self._load(view.checkpoint)
        if view.pending is not None:
            self._check_pending(view.pending)
            self._pending, self._unknown = view.pending, True
            _refuse('COMMIT_OUTCOME_UNKNOWN')
        self._floor = 0 if view.checkpoint is None else view.checkpoint.revision
        return view.checkpoint

    def prepare(self, event, run, key):
        self._available()
        if self._pending is not None:
            _refuse('COMMIT_OUTCOME_UNKNOWN' if self._unknown else 'PREPARED_REQUEST_OUTSTANDING')
        _uuid(key)
        view, nonce = self._view()
        previous_run = self._load(view.checkpoint)
        if view.pending is not None:
            self._check_pending(view.pending)
            self._pending, self._unknown = view.pending, True
            _refuse('COMMIT_OUTCOME_UNKNOWN')
        _transition(None if view.checkpoint is None else view.checkpoint.event, previous_run, event, run)
        claim = self.authority.authorize(self.root, event, run, nonce)
        self._authorization(claim, event, run_digest(run), nonce)
        sequence = 0 if view.checkpoint is None else view.checkpoint.revision
        data = canonical(dict(schema=1, root_id=self.root.root_id, sequence=sequence, event=event.value,
                              run=_run_json(run), previous=_ref_json(None if view.checkpoint is None else view.checkpoint.reference)))
        sha = digest(data)
        name = f'gen-{run.epoch}-{sequence:020d}-{sha}.json'
        snapshot = self.storage.create_generation(name, data)
        if type(snapshot) is not FileSnapshot or snapshot.data != data:
            _refuse('GENERATION_CREATE_UNCONFIRMED')
        _identity(snapshot.identity)
        self._root_check()
        point = Checkpoint(sequence + 1, FileRef(name, snapshot.identity, sha), run.epoch, event, run_digest(run))
        pending = PendingCommit(key, ZERO_DIGEST, self.root, view.checkpoint, point, claim)
        pending = PendingCommit(key, _request_digest(pending), self.root, view.checkpoint, point, claim)
        self._pending = pending
        return pending

    def _authorization(self, claim, event, run_sha, nonce):
        if (type(claim) is not Authorization or claim.scope is not self.scope or claim.root_id != self.root.root_id
                or claim.event is not event or claim.run_digest != run_sha or claim.nonce != nonce
                or type(claim.proof_id) is not str or not 1 <= len(claim.proof_id) <= 128):
            _refuse('EXACT_PROCESS_AUTHORIZATION_REQUIRED')
        try:
            if self.authority.validate_authorization(claim) is not None:
                _refuse('EXACT_PROCESS_AUTHORIZATION_REQUIRED')
        except Exception:
            _refuse('EXACT_PROCESS_AUTHORIZATION_REQUIRED')

    def _check_pending(self, pending):
        if type(pending) is not PendingCommit or pending.root != self.root:
            _refuse('INVALID_PENDING_REFERENCE')
        _uuid(pending.key)
        _digest(pending.request_digest)
        _checkpoint_json(pending.expected_checkpoint)
        run = self._load(pending.proposed_checkpoint)
        expected_revision = 0 if pending.expected_checkpoint is None else pending.expected_checkpoint.revision
        body = json.loads(self.storage.read_generation(pending.proposed_checkpoint.reference.name).data)
        expected_ref = None if pending.expected_checkpoint is None else pending.expected_checkpoint.reference
        if (pending.proposed_checkpoint.revision != expected_revision + 1
                or body['previous'] != _ref_json(expected_ref)):
            _refuse('PENDING_PREDECESSOR_MISMATCH')
        self._load(pending.expected_checkpoint)
        if type(pending.authorization) is not Authorization:
            _refuse('EXACT_PROCESS_AUTHORIZATION_REQUIRED')
        self._authorization(pending.authorization, pending.proposed_checkpoint.event, run_digest(run), pending.authorization.nonce)
        if _request_digest(pending) != pending.request_digest:
            _refuse('REQUEST_FINGERPRINT_MISMATCH')

    def _result(self, result, pending, nonce=None):
        if (type(result) is not CommitResult or result.scope is not self.scope
                or result.key != pending.key or result.request_digest != pending.request_digest
                or result.nonce != nonce or type(result.status) is not Status):
            _refuse('EXACT_REQUEST_RESULT_REQUIRED')
        if result.status is Status.UNKNOWN:
            self._unknown = True
            _refuse('COMMIT_OUTCOME_UNKNOWN')
        if result.status is Status.COMMITTED:
            if result.checkpoint != pending.proposed_checkpoint:
                _refuse('COMMIT_BINDING_MISMATCH')
            self._root_check()
            self._load(result.checkpoint)
            self._floor = max(self._floor, result.checkpoint.revision)
        self._pending, self._unknown = None, False
        return result.checkpoint if result.status is Status.COMMITTED else None

    def commit(self, pending):
        self._available()
        if self._unknown:
            _refuse('COMMIT_OUTCOME_UNKNOWN')
        if self._pending is not pending:
            _refuse('EXACT_PREPARED_REQUEST_REQUIRED')
        self._root_check()
        self._check_pending(pending)
        try:
            result = self.authority.commit(pending)  # Sole logical linearization point.
            return self._result(result, pending)
        except Exception as error:
            # Only an exact validated CONFLICT/COMMITTED clears the uncertainty.
            if self._pending is not None:
                self._unknown = True
            if isinstance(error, GenerationRefused):
                raise
            _refuse('COMMIT_OUTCOME_UNKNOWN')

    def reconcile(self, key, request_digest):
        self._available()
        if self._pending is None or key != self._pending.key or request_digest != self._pending.request_digest:
            _refuse('EXACT_UNCERTAIN_REQUEST_REQUIRED')
        self._root_check()
        self._check_pending(self._pending)
        nonce = secrets.token_hex(32)
        try:
            result = self.authority.resolve(self.root, key, request_digest, nonce)
            return self._result(result, self._pending, nonce)
        except GenerationRefused:
            self._unknown = True
            raise
        except Exception:
            self._unknown = True
            _refuse('COMMIT_OUTCOME_UNKNOWN')

    def process_actions(self, *args, **kwargs):
        self._available()
        _refuse('PROCESS_ACTIONS_NOT_IMPLEMENTED')


class SyntheticFileStore:
    """Ordinary Linux UUID fixture bytes/identities, not Windows private storage."""
    def __init__(self, directory):
        if os.name != 'posix':
            _refuse('LINUX_SYNTHETIC_FIXTURE_ONLY')
        self.directory = Path(directory)
        _uuid(self.directory.name)
        self.directory.mkdir(exist_ok=False)

    def _path(self, name):
        if name != 'identity-root.json' and not re.fullmatch(r'gen-[0-9a-f-]{36}-[0-9]{20}-[0-9a-f]{64}\.json', name):
            _refuse('INVALID_REFERENCE')
        return self.directory / name

    def _read(self, name):
        fd = os.open(self._path(name), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            before = os.fstat(fd)
            data = os.read(fd, LIMIT + 1)
            after = os.fstat(fd)
            if (before.st_ino != after.st_ino or before.st_dev != after.st_dev
                    or before.st_size != len(data) or after.st_size != len(data)
                    or len(data) > LIMIT or before.st_nlink != 1 or after.st_nlink != 1):
                _refuse('SYNTHETIC_READ_CHANGED')
            return FileSnapshot(FileIdentity(before.st_dev, before.st_ino), data)
        finally:
            os.close(fd)

    def _create(self, name, data):
        digest(data)
        with self._path(name).open('xb') as stream:
            stream.write(data)
        return self._read(name)

    def create_root(self, data):
        return self._create('identity-root.json', data)

    def read_root(self):
        return self._read('identity-root.json')

    def create_generation(self, name, data):
        return self._create(name, data)

    def read_generation(self, name):
        return self._read(name)
