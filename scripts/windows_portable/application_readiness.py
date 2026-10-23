"""Production startup consumer; shared acceptance clock, not DB preemption.

Synchronous libpq calls have connection/statement timeouts and late rejection;
no hard transport-blackhole deadline has been established. No launch or mint.
"""
from dataclasses import dataclass,field
import socket
import time
import weakref

from .controller import CandidateRefused
from .processes import PrivateProcessAdapter
from parkweave import runtime_readiness as runtime


@dataclass(frozen=True,repr=False)
class ExistingActorProbe:
    bearer: str = field(repr=False)
    actor: tuple[str,str,str,str]

    def expected(self):
        if (type(self.bearer) is not str or not 1<=len(self.bearer)<=512 or
                any(ord(c)<33 or ord(c)>126 for c in self.bearer) or type(self.actor) is not tuple or len(self.actor)!=4):
            raise CandidateRefused('existing bounded actor probe required')
        result=dict(zip(('id','park_id','org_id','role'),self.actor))
        runtime.actor(result)
        return result


@dataclass(frozen=True,repr=False)
class RegisteredApplication:
    adapter: PrivateProcessAdapter
    api: object
    worker: object
    port: int
    challenge: str


class ReadyApplication:
    __slots__=('__weakref__',)
    def __reduce__(self): raise TypeError('startup observation cannot be serialized')


_issued=weakref.WeakKeyDictionary()


def _get(application, bearer, nonce, deadline):
    """One direct IPv4 loopback GET. Whole response shares the absolute clock."""
    port=application.port
    application.adapter.require_endpoint_support(application.api)
    if type(port) is not int or not 1<=port<=65535: raise CandidateRefused('explicit local API port required')
    data=(f'GET /api/runtime/readiness HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {bearer}\r\n'
          f'X-ParkWeave-Readiness-Challenge: {nonce}\r\nConnection: close\r\n\r\n').encode('ascii')
    def remaining():
        left=deadline-time.monotonic()
        if left<=0: raise CandidateRefused('application readiness deadline')
        return min(.3,left)
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
        connection.settimeout(remaining());connection.connect(('127.0.0.1',port))
        application.adapter.verify_api_connection(application.api,connection)
        connection.settimeout(remaining());connection.sendall(data)
        raw=bytearray();header=None;length=None
        while True:
            connection.settimeout(remaining())
            chunk=connection.recv(512)
            if not chunk: raise CandidateRefused('API readiness response incomplete')
            raw.extend(chunk)
            if header is None:
                split=raw.find(b'\r\n\r\n')
                if split<0:
                    if len(raw)>2048: raise CandidateRefused('API readiness header limit')
                    continue
                if split>2048: raise CandidateRefused('API readiness header limit')
                lines=bytes(raw[:split]).split(b'\r\n')
                if len(lines)>20 or lines[0] not in (b'HTTP/1.1 200 OK',b'HTTP/1.0 200 OK'):
                    raise CandidateRefused('API readiness not successful')
                header={}
                for line in lines[1:]:
                    key,separator,value=line.partition(b':')
                    key=key.lower()
                    if not separator or key in header: raise CandidateRefused('API readiness headers invalid')
                    header[key]=value.strip()
                if (b'transfer-encoding' in header or b'content-encoding' in header or
                        header.get(b'content-type',b'').split(b';')[0]!=b'application/json' or
                        header.get(b'cache-control')!=b'no-store' or not header.get(b'content-length',b'').isdigit()):
                    raise CandidateRefused('API readiness framing required')
                length=int(header[b'content-length'])
                if not 0<length<=runtime.LIMIT: raise CandidateRefused('API readiness body limit')
                raw=raw[split+4:]
            if len(raw)>length: raise CandidateRefused('API readiness extra bytes')
            if len(raw)==length:
                remaining()
                return runtime.parse(bytes(raw))


def _database(inputs, deadline):
    from parkweave.installed_fixture_receipt import _dsn, _connect
    parsed=_dsn(inputs.application_dsn,'parkweave')
    if parsed['host']!='127.0.0.1': raise CandidateRefused('explicit local database required')
    if deadline-time.monotonic()<2: raise CandidateRefused('database readiness budget unavailable')
    with _connect({**parsed,'connect_timeout':'2'},autocommit=False) as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL statement_timeout='1500ms'")
        result=runtime.database(c,'LOCAL')
    if time.monotonic()>=deadline: raise CandidateRefused('database readiness deadline')
    if result['port']!=int(parsed['port']): raise CandidateRefused('database readiness port mismatch')
    return result


def require_application_ready(lease, inputs, application, probe, registered):
    if (type(application) is not RegisteredApplication or type(application.adapter) is not PrivateProcessAdapter
            or application.adapter.lease is not lease or application.api is application.worker
            or len(registered)!=2 or not all(any(token is x for x in registered) for token in (application.api,application.worker))
            or type(probe) is not ExistingActorProbe):
        raise CandidateRefused('exact registered API and worker required')
    nonce=runtime.challenge(application.challenge);expected_actor=probe.expected()
    deadline=time.monotonic()+5
    lease._verify()
    identities=tuple(application.adapter.live_identity(token) for token in (application.api,application.worker))
    application.adapter.require_endpoint_support(application.api)  # Missing witness: no DB probe or HTTP call.
    expected_db=_database(inputs,deadline)  # Real app-role read; physical binding was independently verified by Security.
    frame=runtime.validate_frame(application.adapter.worker_ready_frame(application.worker,deadline),'worker')
    expected_worker=dict(schema='parkweave-worker-ready/1',challenge=nonce,pid=identities[1][0],
                         database=expected_db,mode='LOCAL',state='WAITING_GO',business_started=False)
    if frame!=expected_worker: raise CandidateRefused('current bound worker readiness required')
    observed=runtime.validate_frame(_get(application,probe.bearer,nonce,deadline),'api')
    expected_api=dict(schema='parkweave-api-ready/1',challenge=nonce,pid=identities[0][0],database=expected_db,
                      actor=expected_actor,mode='LOCAL',business_authority=False)
    if observed!=expected_api: raise CandidateRefused('current authenticated API identity required')
    if tuple(application.adapter.live_identity(t) for t in (application.api,application.worker))!=identities:
        raise CandidateRefused('application creation identity changed')
    lease._verify()
    if time.monotonic()>=deadline: raise CandidateRefused('application readiness deadline')
    receipt=ReadyApplication();_issued[receipt]=(application,lease,identities,deadline)
    return receipt  # Worker is still blocked before its first claim.


def check_before_running(receipt):
    if type(receipt) is not ReadyApplication or receipt not in _issued:
        raise CandidateRefused('current readiness required before RUNNING')
    application,lease,identities,deadline=_issued[receipt]
    if time.monotonic()>=deadline or lease.status()!='APPLICATION':
        raise CandidateRefused('application readiness deadline or phase changed')
    if tuple(application.adapter.live_identity(t) for t in (application.api,application.worker))!=identities:
        raise CandidateRefused('application creation identity changed')


def activate_application(receipt):
    if type(receipt) is not ReadyApplication or receipt not in _issued:
        raise CandidateRefused('current unconsumed readiness required')
    application,lease,identities,deadline=_issued.pop(receipt)  # Never replay unknown GO.
    if time.monotonic()>=deadline or lease.status()!='RUNNING':
        raise CandidateRefused('durable RUNNING within readiness clock required')
    if tuple(application.adapter.live_identity(t) for t in (application.api,application.worker))!=identities:
        raise CandidateRefused('application creation identity changed')
    application.adapter.worker_go(application.worker,application.challenge)
    if time.monotonic()>=deadline: raise CandidateRefused('application activation deadline')
