"""Default-closed scoped writer contract and independent-process reference.

No installer, SQL GRANT, credential discovery or production startup is provided.
The reference bootstrap is issued only by the existing owned-fixture controller.
The API holds the old application DSN and pinned channels, never writer secrets.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import socketserver
import stat
import struct
import threading
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import preparation as prep
from . import native_run_access as native
from .store import Store, Conflict, Denied

SCHEME = 'ORDINARY_PG_SCOPED_WRITER_V1'
MAX_FRAME = 524288
MAX_SECONDS = 3600
SHA = '^[a-f0-9]{64}$'


class Source(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    run_id: str
    run_revision: int = Field(ge=1)
    input_fingerprint: str = Field(pattern=SHA)
    owner_id: str
    park_id: str
    org_id: str
    preparation_id: str
    preparation_revision: int = Field(ge=1)
    preparation_state: str
    review_sha256: str = Field(pattern=SHA)
    material_sha256: str = Field(pattern=SHA)
    case_id: str


class WriterPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    scheme: str = SCHEME
    environment: str
    policy_id: str
    revision: int = Field(ge=1)
    owner_id: str = Field(min_length=1, max_length=128)
    approver_id: str = Field(min_length=1, max_length=128)
    beneficiary_id: str = Field(min_length=1, max_length=128)
    approver_actions: list[str]
    capability: str = 'READ'
    max_access_seconds: int = MAX_SECONDS
    valid_from: str
    valid_until: str
    source: Source
    generations: dict
    database_name: str
    database_oid: int = Field(gt=0)
    system_identifier: str
    database_host: str
    database_port: int = Field(gt=0, le=65535)
    application_role: str
    writer_role: str

    @model_validator(mode='after')
    def exact_contract(self):
        if (self.scheme != SCHEME or self.environment not in ('PRODUCTION', 'OWNED_SYNTHETIC_REFERENCE') or
                self.capability != 'READ' or self.max_access_seconds != MAX_SECONDS or
                set(self.approver_actions) != {'APPROVE', 'REJECT', 'REVOKE'} or len(self.approver_actions) != 3 or
                len({self.owner_id, self.approver_id, self.beneficiary_id}) != 3 or
                self.owner_id != self.source.owner_id or self.writer_role == self.application_role):
            raise ValueError('explicit independent single-Run writer contract required')
        for value in (self.policy_id, self.source.run_id, self.source.case_id, self.source.preparation_id):
            if str(UUID(value)) != value:
                raise ValueError('canonical exact object UUID required')
        for value in (self.owner_id, self.approver_id, self.beneficiary_id, self.source.park_id, self.source.org_id):
            if '*' in value:
                raise ValueError('wildcard authority is unsupported')
        start, end = datetime.fromisoformat(self.valid_from), datetime.fromisoformat(self.valid_until)
        if (start.utcoffset() != timedelta(0) or end.utcoffset() != timedelta(0) or
                not 0 < (end-start).total_seconds() <= MAX_SECONDS):
            raise ValueError('explicit UTC policy interval of at most one hour required')
        if self.environment == 'OWNED_SYNTHETIC_REFERENCE' and not re.fullmatch(r'fixture_[a-f0-9]{32}', self.database_name):
            raise ValueError('owned reference fixture UUID required')
        return self


class EndpointPin(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    command_path: str
    verify_path: str
    command_device: int
    command_inode: int
    verify_device: int
    verify_inode: int
    pid: int = Field(gt=0)
    uid: int = Field(ge=0)
    process_started: str
    boot_id: str
    policy_sha256: str = Field(pattern=SHA)


def _canonical(value):
    return prep.canonical(value)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _source(value):
    return {k: v for k, v in value.items() if k != 'case_state'}


def _public_database(c):
    row = c.execute("""SELECT d.oid database_oid,d.datname database_name,
        pg_get_userbyid(d.datdba) database_owner,current_user database_role,
        pg_postmaster_start_time() started FROM pg_database d
        WHERE d.datname=current_database()""").fetchone()
    return dict(row, database_host=c.info.host, database_port=c.info.port)


def _pid_started(pid):
    # The reference is Linux only; no weaker Windows/TCP fallback.
    return Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()[19]


def _socket_stat(path):
    p = Path(path)
    if not p.is_absolute() or len(os.fsencode(p)) > 103:
        raise Denied('explicit bounded Unix socket path required')
    for part in (p, *p.parents):
        value = part.lstat()
        if stat.S_ISLNK(value.st_mode):
            raise Denied('writer endpoint symlink refused')
    value = p.lstat()
    if not stat.S_ISSOCK(value.st_mode):
        raise Denied('writer endpoint must be a socket')
    return value


def pin_reference_endpoint(policy, command_path, verify_path, pid, uid, boot_id):
    """Controller observes its own Popen/OS objects; never adopts a HELLO."""
    policy = WriterPolicy.model_validate(policy)
    a, b = _socket_stat(command_path), _socket_stat(verify_path)
    if a.st_uid != uid or b.st_uid != uid or command_path == verify_path:
        raise Denied('distinct controller-owned writer channels required')
    return EndpointPin(command_path=command_path, verify_path=verify_path,
        command_device=a.st_dev, command_inode=a.st_ino, verify_device=b.st_dev, verify_inode=b.st_ino,
        pid=pid, uid=uid, process_started=_pid_started(pid), boot_id=boot_id,
        policy_sha256=_sha(policy.model_dump()))


@dataclass(frozen=True)
class WriterPermit:
    approver_ids: frozenset
    valid_until: datetime
    max_access_seconds: int
    revision: int
    policy_sha256: str


class WriterClient:
    """Only public scope and app Store; no DSN override or signing operation."""
    def __init__(self, store, policy, pin):
        self.store = store
        # Preserve immutable canonical bytes; model dict/list objects are not trust anchors.
        self._policy_json = _canonical(WriterPolicy.model_validate(policy).model_dump())
        self._pin_json = _canonical(EndpointPin.model_validate(pin).model_dump())
        if self.pin.policy_sha256 != _sha(self.policy.model_dump()):
            raise Denied('controller policy pin mismatch')

    @property
    def policy(self):
        return WriterPolicy.model_validate_json(self._policy_json)

    @property
    def pin(self):
        return EndpointPin.model_validate_json(self._pin_json)

    def rpc(self, operation, **data):
        pin = self.pin
        verify = operation in ('VALIDATE', 'VERIFY')
        path = pin.verify_path if verify else pin.command_path
        expected = (pin.verify_device, pin.verify_inode) if verify else (pin.command_device, pin.command_inode)
        try:
            before = _socket_stat(path)
            if (before.st_dev, before.st_ino, before.st_uid) != (*expected, pin.uid) or _pid_started(pin.pid) != pin.process_started:
                raise Denied('writer process/socket instance changed')
            nonce = secrets.token_hex(16)
            value = dict(operation=operation, nonce=nonce, run_id=self.policy.source.run_id, **data)
            payload = (_canonical(value) + '\n').encode()
            if len(payload) > MAX_FRAME:
                raise Denied('bounded writer request required')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                channel.settimeout(7 if not verify else 2)
                channel.connect(path)
                pid, uid, _ = struct.unpack('3i', channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                after = _socket_stat(path)
                if ((pid, uid) != (pin.pid, pin.uid) or (after.st_dev, after.st_ino) != expected or
                        _pid_started(pid) != pin.process_started):
                    raise Denied('writer peer identity changed')
                channel.sendall(payload)
                with channel.makefile('rb') as stream:
                    raw = stream.readline(MAX_FRAME + 1)
            if len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
                raise Denied('writer response unknown; GET original key')
            reply = json.loads(raw)
            if (not isinstance(reply, dict) or reply.get('nonce') != nonce or reply.get('boot_id') != pin.boot_id or
                    reply.get('policy_sha256') != pin.policy_sha256):
                raise Denied('writer response binding unavailable')
            if reply.get('error') == 'CONFLICT':
                raise Conflict(reply['message'])
            if reply.get('error'):
                raise Denied(reply.get('message', 'writer request denied'))
            return reply['result']
        except (OSError, ValueError, KeyError) as exc:
            raise Denied('writer channel unavailable; GET original key without resubmitting') from exc

    def _database(self, c):
        value = _public_database(c)
        p = self.policy
        if ((value['database_name'], value['database_oid'], value['database_host'], value['database_port'], value['database_role']) !=
                (p.database_name, p.database_oid, p.database_host, p.database_port, p.application_role)):
            raise Denied('application database/role differs from writer contract')
        role=c.execute('SELECT rolsuper,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user').fetchone()
        if any(role.values()) or value['database_role']==value['database_owner']:
            raise Denied('API requires its existing non-owner restricted role')
        return value

    def validate(self, c):
        value = WriterClient._database(self, c)
        reply = WriterClient.rpc(self, 'VALIDATE')
        if (reply['database_name'], reply['database_oid'], reply['system_identifier'], reply['started']) != (
                value['database_name'], value['database_oid'], self.policy.system_identifier, value['started'].isoformat()):
            raise Denied('writer and application live database differ')
        return _permit_value(self.policy)

    def verify(self, receipts):
        return WriterClient.rpc(self, 'VERIFY', receipts=receipts) is True

    def invoke(self, operation, token, run_id, key, data):
        if str(run_id) != self.policy.source.run_id:
            raise Denied('exact writer Run required')
        with self.store._guarded_connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            WriterClient.validate(self, c)
        return WriterClient.rpc(self, operation, token=token, request_key=key,
                                command=data.model_dump(mode='json'))


def _permit_value(policy):
    return WriterPermit(frozenset({policy.approver_id}), datetime.fromisoformat(policy.valid_until),
                        MAX_SECONDS, policy.revision, _sha(policy.model_dump()))


class WriterContext:
    """Private writer process state; never attached to an API application."""
    def __init__(self, store, policy, key):
        self.store = store
        self._policy_json = _canonical(WriterPolicy.model_validate(policy).model_dump())
        if not isinstance(key, bytes) or len(key) != 32:
            raise Denied('independently supplied writer key required')
        self._key = key

    @property
    def policy(self):
        return WriterPolicy.model_validate_json(self._policy_json)

    def validate(self, c):
        p = self.policy
        runtime = getattr(self.store, '_restricted_runtime', None)
        if runtime is not None:
            from .native_run_access_restricted_runtime import RuntimeGuard
            if type(runtime) is not RuntimeGuard or runtime.policy_json != self._policy_json:
                raise Denied('exact restricted runtime contract required')
            RuntimeGuard.check(runtime, c)
        value = _public_database(c)
        if ((value['database_name'], value['database_oid'], value['database_host'], value['database_port'], value['database_role']) !=
                (p.database_name, p.database_oid, p.database_host, p.database_port, p.writer_role)):
            raise Denied('writer database/role differs from explicit installation contract')
        system = c.execute('SELECT system_identifier::text value FROM pg_control_system()').fetchone()['value']
        if system != p.system_identifier:
            raise Denied('writer physical cluster changed')
        role = c.execute('SELECT rolsuper,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user').fetchone()
        if p.environment == 'PRODUCTION' and (any(role.values()) or value['database_role'] == value['database_owner']):
            raise Denied('production writer requires a restricted non-owner identity and approved installation')
        now = native._now(c)
        if not datetime.fromisoformat(p.valid_from) <= now < datetime.fromisoformat(p.valid_until):
            raise Denied('writer policy outside its explicit UTC interval')
        return _permit_value(p)

    def sign(self, receipt):
        value = deepcopy(receipt)
        if 'writer_proof' in value:
            raise Denied('writer proof cannot be supplied by a caller')
        value['writer_proof'] = dict(scheme=SCHEME, policy_sha256=_sha(self.policy.model_dump()),
                                    key_id=hashlib.sha256(self._key).hexdigest(),
                                    hmac_sha256=hmac.new(self._key, _canonical(receipt).encode(), hashlib.sha256).hexdigest())
        return value

    def verify(self, receipts):
        if not isinstance(receipts, list) or len(receipts) > 128:
            return False
        for receipt in receipts:
            if not isinstance(receipt, dict):
                return False
            raw = {k: v for k, v in receipt.items() if k != 'writer_proof'}
            expected=WriterContext.sign(self, raw)['writer_proof']
            actual=receipt.get('writer_proof')
            if (not isinstance(actual,dict) or set(actual)!=set(expected) or
                    any(actual[k]!=expected[k] for k in expected if k!='hmac_sha256') or
                    not isinstance(actual['hmac_sha256'],str) or
                    not hmac.compare_digest(actual['hmac_sha256'],expected['hmac_sha256'])):
                return False
        return True

    def action(self, bridge, c, actor, action):
        p = self.policy
        expected = p.owner_id if action in ('REQUEST', 'CANCEL', 'ACTIVATE') else p.approver_id
        if action == 'REVOKE':
            expected = actor['id'] if actor['id'] in (p.owner_id, p.approver_id) else None
        if actor['id'] != expected or not actor['active'] or (actor['park_id'], actor['org_id']) != (p.source.park_id, p.source.org_id):
            raise Denied('current explicitly designated writer actor required')
        bridge.store.check_capability(c, actor, 'READ')
        run = c.execute('SELECT * FROM runs WHERE id=%s', (p.source.run_id,)).fetchone()
        if not run or (run['principal_id'], run['park_id'], run['org_id']) != (p.owner_id, p.source.park_id, p.source.org_id):
            raise Denied('exact writer owner and tenant required')
        if action in ('REQUEST', 'APPROVE', 'ACTIVATE'):
            from .native_run_access_activation import _generations
            if (_source(bridge._source(c, run, bridge._parent(c, run))) != p.source.model_dump() or
                    _generations(c, p.owner_id, p.beneficiary_id, p.approver_id) != p.generations):
                raise Denied('explicit writer source/authority changed; new policy required')
        if action == 'REQUEST' and (run.get('native_run_access_protocol') or {}).get('events'):
            raise Conflict('single-request policy consumed; no renewal or implicit new policy')
        if action in ('REQUEST', 'ACTIVATE'):
            prep.grant(bridge.store, c, actor, 'PREPARE')
            bridge.store.check_capability(c, actor, 'EXECUTE')


def _writer(bridge):
    value = getattr(bridge, 'writer', None)
    if (type(bridge) is not native.NativeRunAccess or type(value) not in (WriterClient, WriterContext) or
            value.store is not bridge.store or bridge.test_permit is not None or bridge.activation_permit is not None or
            (type(value) is WriterContext and getattr(bridge.store, '_native_api_boundary', False)) or
            bridge.store.mode != 'LOCAL' or getattr(bridge.store, '_isolated_run_access', None) is not None):
        raise Denied('exact separate writer binding required')
    return value


def _records(c, run_id):
    row = c.execute('SELECT native_run_access_protocol,native_run_access_activation FROM runs WHERE id=%s', (run_id,)).fetchone()
    if not row:
        raise Denied('record unavailable')
    protocol, activation = row['native_run_access_protocol'], row['native_run_access_activation']
    events = []
    for ledger in (protocol, activation):
        if ledger is None:
            continue
        items = ledger.get('events')
        if not isinstance(items, list) or not items or ledger.get('revision') != len(items):
            raise Denied('writer ledger/head unavailable')
        last = items[-1]
        if last.get('revision') != ledger['revision']:
            raise Denied('writer receipt revision differs from head')
        if ledger is protocol:
            if any(ledger.get(k) != last.get(k) for k in ('state', 'request', 'lease_id')):
                raise Denied('writer protocol head differs from signed receipt')
            leases = [dict(id=e['lease_id'], state='NON_EFFECTIVE', request_id=e['request']['request_id'],
                           source=e['request']['source'], validity=e['request']['approved_validity'])
                      for e in items if e.get('action') == 'APPROVE']
            if leases != ledger.get('leases'):
                raise Denied('writer proposed leases differ from signed approvals')
        elif ledger.get('activation_id') != last.get('activation_id'):
            raise Denied('writer activation head differs from receipt')
        events.extend(items)
    return events


def permit(bridge, c):
    value = _writer(bridge)
    run_id = value.policy.source.run_id
    schemas = c.execute('SELECT current_schemas(true) value').fetchone()['value']
    if 'public' not in schemas or not set(schemas) <= {'public', 'pg_catalog'}:
        raise Denied('writer provider refuses temporary/shadow scope')
    result = type(value).validate(value, c)
    if not type(value).verify(value, _records(c, run_id)):
        raise Denied('writer origin proof invalid; stored approval is not authority')
    return result


def history(bridge,c,run_id):
    value=_writer(bridge)
    if str(run_id)!=value.policy.source.run_id:
        raise Denied('exact writer metadata scope required')
    if type(value) is WriterClient:
        WriterClient._database(value,c)
    if not type(value).verify(value,_records(c,run_id)):
        raise Denied('historical writer origin proof unavailable')


def binding(bridge, c, run_id):
    value = _writer(bridge)
    p = value.policy
    if str(run_id) != p.source.run_id:
        raise Denied('single explicitly selected writer Run required')
    permit(bridge, c)
    run = c.execute('SELECT * FROM runs WHERE id=%s', (run_id,)).fetchone()
    ledger = run.get('native_run_access_protocol') or {}
    request = ledger.get('request') or {}
    if (ledger.get('state') != 'APPROVED' or request.get('requester_id') != p.owner_id or
            request.get('target_id') != p.beneficiary_id or request.get('approver_id') != p.approver_id):
        raise Denied('writer-approved exact lease required')
    from .native_run_access_activation import NAMESPACE, _generations
    result = dict(namespace=NAMESPACE, run_id=p.source.run_id, lease_id=ledger['lease_id'],
        request_id=request['request_id'], protocol_revision=ledger['revision'], owner_id=p.owner_id,
        executor_id=p.beneficiary_id, approver_id=p.approver_id, capability='READ',
        source=deepcopy(request['source']), authority=deepcopy(request['authority']),
        approver_authority=deepcopy(request['approver_authority']), validity=deepcopy(request['approved_validity']),
        authority_generations=deepcopy(p.generations))
    if _generations(c, p.owner_id, p.beneficiary_id, p.approver_id) != p.generations:
        raise Denied('writer permission generation changed')
    return _permit_value(p), result


def invoke(bridge, operation, token, run_id, key, data):
    if getattr(bridge,'read_only',False):raise Denied('ordinary provider is read-only; writer commands disabled')
    value = _writer(bridge)
    if type(value) is not WriterClient:
        raise Denied('API requires client channel, not private writer context')
    if getattr(bridge,'runtime_write_binding',None) is not None:
        from .ordinary_runtime_write import before_invoke
        before_invoke(bridge, operation, run_id)
    return WriterClient.invoke(value, operation, token, run_id, key, data)


def before_action(bridge, c, actor, action, run_id, data):
    value = _writer(bridge)
    if type(value) is not WriterContext or str(run_id) != value.policy.source.run_id:
        raise Denied('separate private writer transaction required')
    WriterContext.action(value, bridge, c, actor, action)
    if action == 'REQUEST' and data.confirm_request is not True:
        raise Denied('owner must explicitly confirm the exact single-Run request')
    if action == 'REQUEST' and data.target_id != value.policy.beneficiary_id:
        raise Denied('single declared beneficiary required')
    c._writer_checks = [*(getattr(c, '_writer_checks', [])), (bridge, actor['id'], action)]


def sign(bridge, receipt, data):
    value = _writer(bridge)
    if type(value) is not WriterContext:
        raise Denied('receipt signing belongs to writer process')
    bound=deepcopy(receipt)
    bound['writer_command']=data.model_dump(mode='json')
    return WriterContext.sign(value, bound)


def recheck(bridge, c, actor_id, action):
    value = _writer(bridge)
    permit(bridge, c)
    actor = c.execute('SELECT * FROM principals WHERE id=%s', (actor_id,)).fetchone()
    if not actor:
        raise Denied('current writer actor required')
    # REQUEST has already appended its one event; do not classify its commit as renewal.
    WriterContext.action(value, bridge, c, actor, 'ACTIVATE' if action == 'REQUEST' else action)


def reference_bootstrap(owner, proof, *, run_id, approver_id, beneficiary_id, valid_until):
    """Existing authorized controller setup; no new grants or production bootstrap."""
    from .native_run_access_activation import _generations
    native._proof(owner, proof)
    bridge = native.NativeRunAccess(owner)
    with owner.connect() as c:
        native._owner_connection(c, proof)
        run = c.execute('SELECT * FROM runs WHERE id=%s', (run_id,)).fetchone()
        if not run or run.get('native_run_access_protocol') is not None or run.get('native_run_access_activation') is not None:
            raise Denied('explicit fresh ordinary Run without prior access protocol required')
        source = bridge._source(c, run, bridge._parent(c, run))
        for actor, role in ((source['owner_id'], 'enterprise_operator'), (approver_id, 'park_specialist'), (beneficiary_id, 'service_executor')):
            bridge._principal(c, actor, run, role)
        prep.grant(owner, c, bridge._principal(c, source['owner_id'], run), 'PREPARE')
        owner.check_capability(c, bridge._principal(c, source['owner_id'], run), 'EXECUTE')
        value = _public_database(c)
        system = c.execute('SELECT system_identifier::text value FROM pg_control_system()').fetchone()['value']
        policy = WriterPolicy(environment='OWNED_SYNTHETIC_REFERENCE', policy_id=str(uuid4()), revision=1,
            owner_id=source['owner_id'], approver_id=approver_id, beneficiary_id=beneficiary_id,
            approver_actions=['APPROVE', 'REJECT', 'REVOKE'], valid_from=native._now(c).isoformat(),
            valid_until=valid_until, source=Source.model_validate(_source(source)),
            generations=_generations(c, source['owner_id'], beneficiary_id, approver_id),
            database_name=value['database_name'], database_oid=value['database_oid'], system_identifier=system,
            database_host=value['database_host'], database_port=value['database_port'],
            application_role='parkweave_app', writer_role=value['database_role'])
        if source['preparation_state'] != 'LOCAL_CONFIRMED' or source['review_sha256'] != source['material_sha256']:
            raise Denied('owner-confirmed current material required')
    return dict(policy=policy.model_dump(), writer_dsn=owner.dsn, key=secrets.token_hex(32), boot_id=str(uuid4()))


class _ReferenceEngine:
    """Reference process only; production provisioning is deliberately absent."""
    def __init__(self,bootstrap):
        if not isinstance(bootstrap,dict) or set(bootstrap)!={'policy','writer_dsn','key','boot_id'}:
            raise Denied('explicit controller bootstrap required')
        self.policy=WriterPolicy.model_validate(bootstrap['policy'])
        if self.policy.environment!='OWNED_SYNTHETIC_REFERENCE':
            raise Denied('production installation/credentials are not authorized by reference startup')
        self._dsn=bootstrap['writer_dsn']
        self._key=bytes.fromhex(bootstrap['key'])
        self.boot_id=str(UUID(bootstrap['boot_id']))

    def execute(self,request,verify_channel):
        if not isinstance(request,dict):raise Denied('typed writer message required')
        operation=request.get('operation')
        expected={'operation','nonce','run_id'}
        if operation=='VERIFY':expected.add('receipts')
        elif operation in ('COMMAND','ACTIVATE'):expected.update(('token','request_key','command'))
        elif operation!='VALIDATE':raise Denied('unknown writer operation')
        if (set(request)!=expected or request['run_id']!=self.policy.source.run_id or
                not isinstance(request['nonce'],str) or not re.fullmatch('[a-f0-9]{32}',request['nonce']) or
                verify_channel!=(operation in ('VALIDATE','VERIFY'))):
            raise Denied('strict writer message/channel/scope required')
        store=Store(self._dsn)
        context=WriterContext(store,self.policy,self._key)
        if operation=='VERIFY':
            # Pure MAC check, no PostgreSQL connection or locks. Current access
            # is independently checked on the API's already-guarded transaction.
            return WriterContext.verify(context,request['receipts'])
        if operation=='VALIDATE':
            with store._guarded_connect() as c:
                c.execute('SET TRANSACTION READ ONLY')
                WriterContext.validate(context,c)
                value=_public_database(c)
                return dict(database_name=value['database_name'],database_oid=value['database_oid'],
                            system_identifier=self.policy.system_identifier,started=value['started'].isoformat())
        if not isinstance(request['token'],str) or not 1<=len(request['token'])<=256:
            raise Denied('current actual session required')
        bridge=native.NativeRunAccess(store,writer=context)
        store._native_run_access=bridge
        if operation=='COMMAND':
            data=native.RunCommand.model_validate(request['command'])
            return bridge.command(request['token'],UUID(request['run_id']),request['request_key'],data)
        from .native_run_access_activation import Activate
        data=Activate.model_validate(request['command'])
        return bridge.activate(request['token'],UUID(request['run_id']),request['request_key'],data)


class _Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
    daemon_threads=True
    block_on_close=False
    def __init__(self,path,engine,verify_channel):
        self.engine,self.verify_channel=engine,verify_channel
        self._slots=threading.BoundedSemaphore(8)
        super().__init__(path,_Handler)

    def process_request(self,request,client_address):
        # Bound handlers before spawning, including peers that never send a frame.
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:super().process_request(request,client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self._slots.release()


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(2)
        value={}
        engine=self.server.engine
        try:
            raw=self.rfile.readline(MAX_FRAME+1)
            if len(raw)>MAX_FRAME or not raw.endswith(b'\n'):raise Denied('bounded complete writer frame required')
            value=json.loads(raw)
            if not isinstance(value,dict):raise Denied('typed writer frame required')
            result=engine.execute(value,self.server.verify_channel)
            reply=dict(result=result)
        except Conflict as exc:reply=dict(error='CONFLICT',message=str(exc))
        except Denied as exc:reply=dict(error='DENIED',message=str(exc))
        except (ValueError,TypeError,KeyError):reply=dict(error='DENIED',message='typed writer command refused')
        except Exception:reply=dict(error='CONFLICT',message='writer transaction failed; GET original key without resubmitting')
        reply.update(nonce=value.get('nonce') if isinstance(value,dict) else None,
                     boot_id=engine.boot_id,policy_sha256=_sha(engine.policy.model_dump()))
        payload=(_canonical(reply)+'\n').encode()
        if len(payload)>MAX_FRAME:return
        try:self.wfile.write(payload)
        except (OSError,ValueError):pass  # Committed effects remain; no replay.


def serve_reference(bootstrap,command_path,verify_path):
    """Real independent process; two listeners keep verification off command queues."""
    if os.name!='posix' or not hasattr(socket,'SO_PEERCRED'):
        raise Denied('reference requires Linux peer credentials; no fallback')
    engine=_ReferenceEngine(bootstrap)
    if command_path==verify_path:raise Denied('independent command/verification endpoints required')
    servers=[]
    try:
        for path,verify in ((command_path,False),(verify_path,True)):
            p=Path(path)
            if p.exists() or p.is_symlink():raise Denied('reference endpoint must be newly created')
            for parent in p.parents:
                if parent.is_symlink():raise Denied('reference endpoint parent symlink refused')
            servers.append(_Server(path,engine,verify))
        worker=threading.Thread(target=servers[1].serve_forever,daemon=True)
        worker.start()
        servers[0].serve_forever()
    finally:
        for server in servers:server.server_close()
        # The controller owns process shutdown and its exact temporary directory;
        # never unlink a socket that might have been replaced by another process.


def _read_private_bootstrap(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        value=os.fstat(fd)
        if (not stat.S_ISREG(value.st_mode) or value.st_uid!=os.getuid() or value.st_mode&0o077 or value.st_size>131072):
            raise Denied('controller-private reference bootstrap required')
        with os.fdopen(fd,'r') as stream:
            fd=None
            return json.load(stream)
    finally:
        if fd is not None:os.close(fd)


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Owned synthetic reference only; no production startup')
    parser.add_argument('--reference-bootstrap',required=True)
    parser.add_argument('--command-socket',required=True)
    parser.add_argument('--verify-socket',required=True)
    args=parser.parse_args()
    serve_reference(_read_private_bootstrap(args.reference_bootstrap),args.command_socket,args.verify_socket)


if __name__=='__main__':
    # The native bridge uses exact canonical types. Executing this file as -m
    # must not construct a second set of __main__ policy/context classes.
    from .native_run_access_writer import main as canonical_main
    canonical_main()
