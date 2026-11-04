"""Normal LIVE worker plumbing with private pipes and two actual PG databases.

All credentials/approvals below are self-authored synthetic fixtures. The only
HTTP request implementation is replaced with the existing offline provider
fixture; no model endpoint, Windows credential API or operator account is used.
"""
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg.conninfo import make_conninfo
import pytest

from parkweave.intern_adapter import ModelBoundaryError
from parkweave.live_credentials import parse_credentials,InheritedPipeCredentials,MAX_BYTES
from parkweave.live_worker import LiveWorkerRuntime
from parkweave.model_chain import FAKE_TOKEN,synthetic_transport
from parkweave.quota import PersistentBudget,AccountRateLimited
from parkweave.store import Store
from parkweave import worker
from conftest import drop_owned_fixture_database

pytestmark=pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux private pipe/PG integration, not Windows evidence')


@pytest.fixture
def coordinator(pg,fixture):
    name='fixture_'+uuid4().hex;identity=uuid4()
    with psycopg.connect(pg.get_uri(),autocommit=True) as c:
        c.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(name)))
    owner=Store(make_conninfo(pg.get_uri(),dbname=name))
    try:
        with owner.connect() as c:
            c.execute(Path('src/parkweave/quota.sql').read_text())
            c.execute("INSERT INTO shared_model_quota.accounts(account,kind,approved,starts,ends,call_limit,token_limit,authorization_evidence,approved_by,rate_verified,rate_evidence) VALUES('offline-live-fixture','LIVE',true,clock_timestamp()-interval '1 minute',clock_timestamp()+interval '1 hour',2,16384,'SYNTHETIC NOT REAL APPROVAL','synthetic owner',true,'SYNTHETIC RATE ONLY')")
            c.execute("INSERT INTO shared_model_quota.products VALUES('parkweave','parkweave_app','offline-live-fixture',2,16384,0,0)")
            c.execute("INSERT INTO shared_model_quota.live_worker_approvals VALUES('parkweave','offline-live-fixture',%s,true,clock_timestamp()-interval '1 minute',clock_timestamp()+interval '1 hour','synthetic owner','SYNTHETIC PIPE TEST, NOT REAL INJECTION APPROVAL')",(identity,))
            c.execute('GRANT USAGE ON SCHEMA shared_model_quota TO parkweave_app')
            c.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA shared_model_quota TO parkweave_app')
        dsn=make_conninfo(owner.dsn,user='parkweave_app')
        raw=json.dumps(dict(schema='parkweave-live-worker/1',token=FAKE_TOKEN,
            quota_dsn=dsn,account='offline-live-fixture',coordinator_id=str(identity))).encode()
        yield owner,dsn,identity,raw
    finally:drop_owned_fixture_database(pg,name)


def pipe_source(raw):
    r,w=os.pipe()
    os.write(w,raw);os.close(w)
    return r


def start(monkeypatch,fixture,raw):
    store=fixture[0]
    monkeypatch.setenv('PARKWEAVE_DSN',store.dsn)
    fd=pipe_source(raw)
    try:worker.main(['--once','--model-live','--model-config-fd',str(fd)])
    finally:os.close(fd)


def submit(fixture):
    _,_,tokens,client=fixture
    response=client.post('/api/runs',headers={'Authorization':'Bearer '+tokens['fixture-a'],
        'Idempotency-Key':'live-worker-offline'},json={'goal':'SYNTHETIC local goal','action':'case.create'})
    assert response.status_code==202
    return response.json()['run_id']


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('external HTTP prohibited')
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',forbidden)


def test_normal_worker_protected_pipe_separate_coordinator_plan_feedback(monkeypatch,fixture,coordinator,capsys):
    owner,dsn,identity,raw=coordinator;run=submit(fixture);requests=[];base=synthetic_transport()
    def offline(transport,request):
        requests.append(request)
        return base.transport.handle_request(request)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',offline)
    start(monkeypatch,fixture,raw)
    assert len(requests)==2 and all(r.url.scheme=='https' and r.headers['authorization']=='Bearer '+FAKE_TOKEN for r in requests)
    with fixture[1].connect() as c:
        assert c.execute('SELECT state FROM runs WHERE id=%s',(run,)).fetchone()['state']=='SUCCEEDED'
        assert c.execute('SELECT state FROM cases WHERE run_id=%s',(run,)).fetchone()['state']=='NEEDS_INPUT'
        assert c.execute("SELECT to_regnamespace('shared_model_quota') n").fetchone()['n'] is None
    with owner.connect() as c:
        rows=c.execute('SELECT state,usage FROM shared_model_quota.reservations').fetchall()
        assert len(rows)==2 and all(r['state']=='SETTLED' and r['usage']['total_tokens']==15 for r in rows)
    captured=capsys.readouterr();assert FAKE_TOKEN not in captured.out+captured.err and dsn not in captured.out+captured.err


def test_live_worker_preserves_non_model_fact_actions(monkeypatch,fixture,coordinator):
    _,_,tokens,client=fixture
    response=client.post('/api/runs',headers={'Authorization':'Bearer '+tokens['fixture-a'],
        'Idempotency-Key':'live-worker-local-facts'},json={'goal':'SYNTHETIC fact assessment','action':'facts.assess','fact_fields':['region']})
    assert response.status_code==202
    start(monkeypatch,fixture,coordinator[3])
    with fixture[1].connect() as c:
        assert c.execute('SELECT state FROM runs WHERE id=%s',(response.json()['run_id'],)).fetchone()['state']=='SUCCEEDED'
        assert c.execute('SELECT count(*) n FROM model_steps').fetchone()['n']==0
    with coordinator[0].connect() as c:
        assert c.execute('SELECT calls FROM shared_model_quota.accounts').fetchone()['calls']==0


@pytest.mark.parametrize('change',[
    "UPDATE shared_model_quota.accounts SET approved=false",
    "UPDATE shared_model_quota.accounts SET rate_verified=false",
    "UPDATE shared_model_quota.live_worker_approvals SET approved=false",
    "UPDATE shared_model_quota.live_worker_approvals SET ends=clock_timestamp()-interval '1 second',starts=clock_timestamp()-interval '1 hour'",
    "UPDATE shared_model_quota.live_worker_approvals SET coordinator_id=gen_random_uuid()",
    "UPDATE shared_model_quota.products SET db_role='wrong-role'",
])
def test_unapproved_or_misbound_live_worker_never_claims(monkeypatch,fixture,coordinator,change,capsys):
    owner,_,_,raw=coordinator;run=submit(fixture)
    with owner.connect() as c:c.execute(change)
    with pytest.raises(SystemExit) as error:start(monkeypatch,fixture,raw)
    assert error.value.code==2
    with fixture[1].connect() as c:
        assert c.execute('SELECT state FROM runs WHERE id=%s',(run,)).fetchone()['state']=='QUEUED'
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0
    with owner.connect() as c:assert c.execute('SELECT calls FROM shared_model_quota.accounts').fetchone()['calls']==0
    captured=capsys.readouterr()
    assert 'model startup refused: LIVE_SAFETY_BLOCKED' in captured.err
    assert FAKE_TOKEN not in captured.out+captured.err


def test_revocation_before_atomic_dispatch_keeps_unsent_and_allows_release(fixture,coordinator):
    owner,dsn,identity,_=coordinator
    b=PersistentBudget(dsn,account='offline-live-fixture',product='parkweave',work='revoke',kind='LIVE',coordinator_id=identity)
    record=b.reserve()
    with owner.connect() as c:c.execute('UPDATE shared_model_quota.live_worker_approvals SET approved=false')
    with pytest.raises(ModelBoundaryError,match='QUOTA_DENIED'):b.dispatch(record)
    with owner.connect() as c:
        r=c.execute('SELECT state,rate_state FROM shared_model_quota.reservations').fetchone()
        assert r==dict(state='RESERVED',rate_state=None)
    b.release(record)
    with owner.connect() as c:assert c.execute('SELECT calls FROM shared_model_quota.accounts').fetchone()['calls']==0


def test_legacy_live_and_private_functions_cannot_bypass_worker_binding(fixture,coordinator):
    owner,dsn,identity,_=coordinator
    b=PersistentBudget(dsn,account='offline-live-fixture',product='parkweave',work='guard',kind='LIVE',coordinator_id=identity)
    record=b.reserve()
    with owner.connect() as c:c.execute('UPDATE shared_model_quota.live_worker_approvals SET approved=false')
    calls=[
        ('SELECT shared_model_quota.reserve(%s,%s,%s,8192,\'LIVE\')',('parkweave','offline-live-fixture','bypass')),
        ('SELECT shared_model_quota.reserve(%s,%s,%s,8192,NULL)',('parkweave','offline-live-fixture','null-bypass')),
        ('SELECT shared_model_quota.hold_rate(%s,%s)',(record['id'],record['generation'])),
        ("SELECT shared_model_quota.transition(%s,%s,'DISPATCHED',NULL,NULL)",(record['id'],record['generation'])),
        ("SELECT shared_model_quota._reserve(%s,%s,%s,8192,'LIVE')",('parkweave','offline-live-fixture','private-bypass')),
        ('SELECT shared_model_quota._hold_rate(%s,%s)',(record['id'],record['generation'])),
        ("SELECT shared_model_quota._transition(%s,%s,'DISPATCHED',NULL,NULL)",(record['id'],record['generation'])),
    ]
    for query,args in calls:
        with psycopg.connect(dsn) as c:
            with pytest.raises(psycopg.Error):c.execute(query,args)
    with psycopg.connect(dsn) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute('UPDATE shared_model_quota.live_worker_approvals SET approved=true')
    with owner.connect() as c:
        assert c.execute('SELECT state,rate_state FROM shared_model_quota.reservations').fetchone()==dict(state='RESERVED',rate_state=None)
        assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==1
        assert c.execute('SELECT calls,tokens FROM shared_model_quota.accounts').fetchone()==dict(calls=1,tokens=8192)
    b.release(record)


def test_atomic_rate_denial_releases_unsent_and_unknown_can_settle_after_revocation(fixture,coordinator):
    owner,dsn,identity,_=coordinator
    with owner.connect() as c:c.execute('UPDATE shared_model_quota.accounts SET rate_limit=1')
    one=PersistentBudget(dsn,account='offline-live-fixture',product='parkweave',work='first',kind='LIVE',coordinator_id=identity)
    two=PersistentBudget(dsn,account='offline-live-fixture',product='parkweave',work='second',kind='LIVE',coordinator_id=identity)
    first=one.reserve();one.dispatch(first);second=two.reserve()
    with pytest.raises(AccountRateLimited):two.dispatch(second)
    with owner.connect() as c:
        assert c.execute('SELECT state,rate_state FROM shared_model_quota.reservations WHERE id=%s',(second['id'],)).fetchone()==dict(state='RELEASED',rate_state='RELEASED')
        c.execute('UPDATE shared_model_quota.live_worker_approvals SET approved=false')
    one.finish(first,'TIMEOUT_OUTCOME_UNKNOWN')
    with pytest.raises(ModelBoundaryError):one.reserve()
    with owner.connect() as c:
        assert c.execute('SELECT state,usage FROM shared_model_quota.reservations WHERE id=%s',(first['id'],)).fetchone()==dict(state='OUTCOME_UNKNOWN',usage=None)
        assert c.execute('SELECT calls,tokens FROM shared_model_quota.accounts').fetchone()==dict(calls=1,tokens=8192)


def test_private_source_is_real_anonymous_pipe_and_no_plaintext_file_fallback(tmp_path,coordinator):
    raw=coordinator[3];fd=pipe_source(raw)
    try:
        credential=InheritedPipeCredentials(fd).read()
        assert credential.token.get_secret_value()==FAKE_TOKEN
        assert FAKE_TOKEN not in repr(credential) and coordinator[1] not in repr(credential)
        assert not os.get_inheritable(fd)
    finally:os.close(fd)
    file=tmp_path/'not-a-source';file.write_bytes(raw);file.chmod(0o600)
    fd=os.open(file,os.O_RDONLY)
    try:
        with pytest.raises(ModelBoundaryError):InheritedPipeCredentials(fd).read()
    finally:os.close(fd)
    # An unlinked named FIFO satisfies nlink=0, but is not a kernel pipe:[id].
    fifo=tmp_path/'fifo';os.mkfifo(fifo,0o600);fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK);fifo.unlink()
    try:
        with pytest.raises(ModelBoundaryError):InheritedPipeCredentials(fd).read()
    finally:os.close(fd)


@pytest.mark.parametrize('raw',[b'{}',b'{"token":"secret","token":"other"}',b'x'*(MAX_BYTES+1),b'{"x":NaN}'])
def test_invalid_private_payload_no_secret_error(raw):
    with pytest.raises(ModelBoundaryError) as error:parse_credentials(raw)
    assert str(error.value)=='LIVE_CREDENTIAL_FORMAT_REFUSED'


def test_pipe_requires_eof_with_one_absolute_deadline(coordinator):
    r,w=os.pipe();os.write(w,coordinator[3]);started=time.monotonic()
    try:
        with pytest.raises(ModelBoundaryError,match='LIVE_CREDENTIAL_SOURCE_REFUSED'):InheritedPipeCredentials(r).read()
        assert 1.8<=time.monotonic()-started<3.5
    finally:os.close(r);os.close(w)


def test_missing_source_and_ambient_pg_configuration_refuse_without_fallback(monkeypatch,fixture,coordinator,capsys):
    monkeypatch.setenv('PARKWEAVE_DSN',fixture[0].dsn)
    monkeypatch.setenv('PARKWEAVE_INTERN_API_TOKEN',FAKE_TOKEN)
    with pytest.raises(SystemExit) as error:worker.main(['--once','--model-live'])
    assert error.value.code==2
    assert '移除 --model-live 使用本地办理' in capsys.readouterr().err
    monkeypatch.setenv('PGUNKNOWN','not inspected')
    with pytest.raises(SystemExit) as error:start(monkeypatch,fixture,coordinator[3])
    assert error.value.code==2


def test_worker_startup_refuses_credential_api_failure_without_secret_trace(monkeypatch,fixture):
    from parkweave import live_credentials
    def unavailable():raise OSError('SYNTHETIC private error must not escape')
    monkeypatch.setattr(live_credentials,'_windows_blob',unavailable)
    # Pure source failure protocol only, no Windows API call.
    with pytest.raises(ModelBoundaryError,match='LIVE_CREDENTIAL_UNAVAILABLE'):
        live_credentials.WindowsCredentialCredentials().read()
