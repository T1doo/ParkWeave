from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from psycopg.types.json import Jsonb
from parkweave.domain import Intake
from parkweave.fault_ledger import FaultAdapter,FaultLedger
from parkweave.store import Conflict,Denied


@pytest.fixture
def faults(fixture):
    store,owner,tokens,client=fixture
    with owner.connect() as c:
        c.execute(Path('src/parkweave/fault-schema.sql').read_text())
        c.execute('GRANT SELECT,INSERT,UPDATE ON fault_operations TO parkweave_app')
    ledger=FaultLedger(store,FaultAdapter(owner))
    return ledger,owner,tokens


def prepare(faults):
    ledger,owner,tokens=faults
    op=ledger.prepare(tokens['fixture-a'],'fault-1',Intake(goal='合成：远端响应丢失'))
    return op


def test_lost_response_reconciles_without_redispatch(faults):
    ledger,owner,tokens=faults;op=prepare(faults)
    old=ledger.claim();env=ledger.dispatch(old)
    response=ledger.adapter.send(env,lose_response=True);ledger.record(old,response)
    assert ledger.read(tokens['fixture-a'],op)['state']=='OUTCOME_UNKNOWN'
    new=ledger.claim()
    with pytest.raises(Conflict):ledger.dispatch(new)
    ledger.reconcile(new)
    assert ledger.read(tokens['fixture-a'],op)['state']=='VERIFIED'
    assert ledger.claim() is None
    with owner.connect() as c:
        assert c.execute('SELECT dispatch_count FROM fault_effects').fetchone()['dispatch_count']==1
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0


@pytest.mark.parametrize('intent',['PAUSE','CANCEL'])
def test_unknown_control_keeps_effect_visible_and_fences_old_callback(faults,intent):
    ledger,owner,tokens=faults;op=prepare(faults)
    old=ledger.claim();env=ledger.dispatch(old)
    ledger.control(tokens['fixture-a'],op,intent)
    new=ledger.claim();ledger.reconcile(new)  # no visible remote result yet; do not assume failure
    row=ledger.read(tokens['fixture-a'],op)
    assert row['state']=='OUTCOME_UNKNOWN' and row['intent']==intent
    receipt=ledger.adapter.send(env)  # already sent intent can take effect after cancellation
    with pytest.raises(Conflict):ledger.record(old,receipt)
    recovery=ledger.claim();ledger.reconcile(recovery)
    row=ledger.read(tokens['fixture-a'],op)
    assert row['state']=='VERIFIED' and row['intent']==intent
    with pytest.raises(Conflict):ledger.control(tokens['fixture-a'],op,'CANCEL')
    with owner.connect() as c:assert c.execute('SELECT dispatch_count FROM fault_effects').fetchone()['dispatch_count']==1


def test_crash_after_dispatch_and_withdrawal_does_not_resend(faults):
    ledger,owner,tokens=faults;op=prepare(faults)
    old=ledger.claim();env=ledger.dispatch(old)
    ledger.adapter.send(env)  # crash before recording the known response
    owner.revoke('fixture-a')
    with owner.connect() as c:
        c.execute("UPDATE fault_operations SET lease_until=clock_timestamp()-interval '1 second'")
    new=ledger.claim();ledger.reconcile(new)
    with pytest.raises(Conflict):ledger.record(old,ledger.adapter.query(env))
    with pytest.raises(Denied):ledger.read(tokens['fixture-a'],op)
    with owner.connect() as c:
        assert c.execute('SELECT state FROM fault_operations').fetchone()['state']=='VERIFIED'
        assert c.execute('SELECT dispatch_count FROM fault_effects').fetchone()['dispatch_count']==1


def test_withdrawal_before_dispatch_is_safe_failure(faults):
    ledger,owner,tokens=faults;op=prepare(faults)
    claim=ledger.claim();owner.revoke('fixture-a')
    assert ledger.dispatch(claim) is None
    with owner.connect() as c:
        assert c.execute('SELECT state FROM fault_operations').fetchone()['state']=='FAILED_SAFE'
        assert c.execute('SELECT count(*) n FROM fault_effects').fetchone()['n']==0


@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_fault_isolation_read_control_and_same_key(faults,user):
    ledger,owner,tokens=faults;op=prepare(faults)
    with pytest.raises(Denied):ledger.read(tokens[user],op)
    with pytest.raises(Denied):ledger.control(tokens[user],op,'CANCEL')
    other=ledger.prepare(tokens[user],'fault-1',Intake(goal='合成：另外一件事'))
    assert other!=op
    with pytest.raises(Conflict):ledger.prepare(tokens['fixture-a'],'fault-1',Intake(goal='改变输入'))


def test_receipt_cannot_cross_scope_or_fingerprint(faults):
    ledger,owner,tokens=faults;op=prepare(faults)
    claim=ledger.claim();env=ledger.dispatch(claim)
    receipt=ledger.adapter.send(env);receipt['org_id']='org-b'
    ledger.record(claim,receipt)
    assert ledger.read(tokens['fixture-a'],op)['state']=='EFFECT_KNOWN_INVALID'
    assert ledger.claim() is None


def test_only_one_fault_claim_and_unknown_query_stays_unknown(faults):
    ledger,owner,tokens=faults;op=prepare(faults)
    with ThreadPoolExecutor(max_workers=8) as pool:claims=list(pool.map(lambda _:ledger.claim(),range(8)))
    assert sum(x is not None for x in claims)==1
    claim=next(x for x in claims if x);ledger.dispatch(claim);ledger.record(claim,None)
    for _ in range(3):ledger.reconcile(ledger.claim())
    assert ledger.read(tokens['fixture-a'],op)['state']=='OUTCOME_UNKNOWN'
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM fault_effects').fetchone()['n']==0


def test_fault_tables_absent_in_regular_database(fixture):
    store,owner,tokens,client=fixture
    with owner.connect() as c:
        assert c.execute("SELECT to_regclass('fault_operations') t").fetchone()['t'] is None
    assert client.post('/api/runs',json={'goal':'x','action':'fault.record'},
                       headers={'Authorization':'Bearer '+tokens['fixture-a'],'Idempotency-Key':'unsafe'}).status_code==422


@pytest.mark.parametrize('intent',['PAUSE','CANCEL'])
def test_control_before_dispatch_creates_no_effect(faults,intent):
    ledger,owner,tokens=faults;op=prepare(faults)
    old=ledger.claim();ledger.control(tokens['fixture-a'],op,intent)
    with pytest.raises(Conflict):ledger.dispatch(old)
    assert ledger.claim() is None
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM fault_effects').fetchone()['n']==0
    if intent=='PAUSE':
        ledger.control(tokens['fixture-a'],op,'CONTINUE')
        new=ledger.claim();env=ledger.dispatch(new);ledger.record(new,ledger.adapter.send(env))
        assert ledger.read(tokens['fixture-a'],op)['state']=='VERIFIED'
    else:
        assert ledger.read(tokens['fixture-a'],op)['state']=='FAILED_SAFE'


def test_expired_fault_worker_cannot_dispatch(faults):
    ledger,owner,tokens=faults;prepare(faults)
    old=ledger.claim()
    with owner.connect() as c:c.execute("UPDATE fault_operations SET lease_until=clock_timestamp()-interval '1 second'")
    with pytest.raises(Conflict):ledger.dispatch(old)
    new=ledger.claim();env=ledger.dispatch(new);ledger.record(new,ledger.adapter.send(env))
    with owner.connect() as c:assert c.execute('SELECT dispatch_count FROM fault_effects').fetchone()['dispatch_count']==1
