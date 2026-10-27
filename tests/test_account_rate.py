"""Owner-controlled SYNTHETIC clocks and real PG locks; provider sockets forbidden."""
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import httpx
import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from parkweave.quota import AccountRateLimited, PersistentBudget
from parkweave.intern_adapter import ModelBoundaryError
from parkweave.live_safety import LiveSafety, check_names
from parkweave.http_transport import InternHTTPTransport
from parkweave.model_chain import synthetic_transport
from test_model_chain import provision, budget, submit, chain, rows, no_provider_sockets

BASE = datetime(2030, 1, 1, tzinfo=timezone.utc)
USAGE = {'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}

def clock(owner, seconds=0, *, rate=None):
    at=BASE+timedelta(seconds=seconds)
    with owner.connect() as c:
        c.execute("UPDATE shared_model_quota.accounts SET starts=%s,ends=%s",(BASE-timedelta(days=1),BASE+timedelta(days=1)))
        c.execute("INSERT INTO shared_model_quota.synthetic_clock VALUES('synthetic-shared-account',%s) ON CONFLICT(account) DO UPDATE SET at=excluded.at",(at,))
        if rate is not None:c.execute('UPDATE shared_model_quota.accounts SET rate_limit=%s',(rate,))
    return at

def setup(fixture,rate=30):
    store,owner,*_=fixture;provision(owner,calls=100,tokens=100*8192);clock(owner,rate=rate)
    return store,owner

def send(store, work):
    b=budget(store,work);r=b.reserve();b.dispatch(r);return b,r

def account(owner):
    with owner.connect() as c:return c.execute('SELECT * FROM shared_model_quota.accounts').fetchone()

def test_thirty_first_immediate_send_denied_and_unsent_refunded(fixture):
    store,owner=setup(fixture)
    for n in range(30):send(store,str(n))
    b=budget(store,'31');r=b.reserve()
    with pytest.raises(AccountRateLimited) as e:b.dispatch(r)
    assert e.value.retry_after_seconds is None
    q=account(owner);assert q['calls']==30 and q['tokens']==30*8192
    with owner.connect() as c:
        assert c.execute("SELECT count(*) n FROM shared_model_quota.reservations WHERE rate_state='IN_FLIGHT'").fetchone()['n']==30
        assert c.execute('SELECT state,rate_denials FROM shared_model_quota.reservations WHERE id=%s',(r['id'],)).fetchone()=={'state':'RELEASED','rate_denials':1}

def test_exact_sixty_second_boundary_and_same_unsent_work_retry(fixture):
    store,owner=setup(fixture,1);b,r=send(store,'first');b.finish(r,'VALIDATED',USAGE)
    clock(owner,59.999999);next_b=budget(store,'next');denied=next_b.reserve()
    with pytest.raises(AccountRateLimited) as e:next_b.dispatch(denied)
    assert float(e.value.retry_after_seconds)==pytest.approx(.000001)
    assert account(owner)['calls']==1 and account(owner)['tokens']==15
    clock(owner,60);again=budget(store,'next');new=again.reserve();assert new['id']==denied['id'];again.dispatch(new)
    with owner.connect() as c:
        events=c.execute('SELECT event FROM shared_model_quota.events WHERE reservation_id=%s ORDER BY id',(new['id'],)).fetchall()
    assert [x['event'] for x in events]==['BUDGET_RESERVED','RATE_DENIED_NOT_SENT','RELEASED','BUDGET_RESERVED','RATE_HELD_NOT_SENT','DISPATCHED']

def test_held_and_inflight_do_not_expire_delayed_send_cooldown_from_finish(fixture):
    store,owner=setup(fixture,1);b=budget(store,'held');r=b.reserve();b.hold_rate(r)
    clock(owner,120)
    with pytest.raises(AccountRateLimited):send(store,'blocked-held')
    b.dispatch(r);clock(owner,150)
    with pytest.raises(AccountRateLimited):send(store,'blocked-inflight')
    b.finish(r,'TIMEOUT_OUTCOME_UNKNOWN');clock(owner,209.999999)
    with pytest.raises(AccountRateLimited):send(store,'blocked-cooldown')
    clock(owner,210);send(store,'free')
    with pytest.raises(ModelBoundaryError,match='PREVIOUS_ATTEMPT_NO_RESEND'):budget(store,'held').reserve()
    assert account(owner)['tokens']==2*8192

def test_release_unsent_held_slot_once_no_refund_sent_or_unknown(fixture):
    store,owner=setup(fixture,1);b=budget(store,'held');r=b.reserve();b.hold_rate(r);b.release(r);b.release(r)
    assert account(owner)['calls']==0 and account(owner)['tokens']==0
    with pytest.raises(ModelBoundaryError):b.dispatch(r)
    fresh,r2=send(store,'fresh');fresh.finish(r2,'TIMEOUT_OUTCOME_UNKNOWN')
    with pytest.raises(ModelBoundaryError):fresh.release(r2)
    assert account(owner)['calls']==1 and account(owner)['tokens']==8192

def test_reopened_unsent_work_fences_old_generation(fixture):
    store,owner=setup(fixture,1);b=budget(store,'retry');old=b.reserve();b.hold_rate(old);b.release(old)
    fresh=b.reserve();assert fresh['generation']==old['generation']+1
    for action in (b.release,b.hold_rate,b.dispatch):
        with pytest.raises(ModelBoundaryError):action(old)
    assert account(owner)['calls']==1 and account(owner)['tokens']==8192
    b.dispatch(fresh);b.finish(fresh,'VALIDATED',USAGE)
    with owner.connect() as c:
        assert {r['generation'] for r in c.execute('SELECT generation FROM shared_model_quota.events').fetchall()}=={1,2}

def test_lowered_rate_rechecked_at_dispatch_and_zero_disables(fixture):
    store,owner=setup(fixture,2);b=budget(store,'held');r=b.reserve();b.hold_rate(r);other=budget(store,'other');r2=other.reserve();other.hold_rate(r2)
    clock(owner,rate=1)
    with pytest.raises(ModelBoundaryError):b.dispatch(r)
    other.release(r2);b.dispatch(r);b.finish(r,'VALIDATED',USAGE)
    clock(owner,60,rate=0)
    with pytest.raises(AccountRateLimited):send(store,'disabled')

def test_coordinator_upgrade_idempotent_and_sent_history_preserved(fixture):
    store,owner=setup(fixture,1);b,r=send(store,'history');b.finish(r,'VALIDATED',USAGE)
    from pathlib import Path
    with owner.connect() as c:
        before=c.execute('SELECT * FROM shared_model_quota.reservations WHERE id=%s',(r['id'],)).fetchone()
        c.execute(Path('src/parkweave/quota.sql').read_text())
        assert c.execute('SELECT * FROM shared_model_quota.reservations WHERE id=%s',(r['id'],)).fetchone()==before
    with pytest.raises(ModelBoundaryError,match='PREVIOUS_ATTEMPT_NO_RESEND'):budget(store,'history').reserve()

def test_clock_rewind_blocks_send_and_finish_is_conservative(fixture):
    store,owner=setup(fixture,1);b,r=send(store,'sent');clock(owner,10)
    spare=budget(store,'spare');unsent=spare.reserve();clock(owner,9)
    with pytest.raises(ModelBoundaryError):spare.dispatch(unsent)
    spare.release(unsent);b.finish(r,'VALIDATED',USAGE)
    with owner.connect() as c:assert c.execute('SELECT finished_at FROM shared_model_quota.reservations WHERE id=%s',(r['id'],)).fetchone()['finished_at']==BASE+timedelta(seconds=10)
    with pytest.raises(ModelBoundaryError):budget(store,'rewound').reserve()
    clock(owner,69.999999)
    with pytest.raises(AccountRateLimited):send(store,'early')
    clock(owner,70);send(store,'boundary')

def test_cross_worker_account_admission_atomic(fixture):
    store,owner=setup(fixture)
    def attempt(n):
        try:send(store,'concurrent:'+str(n));return True
        except AccountRateLimited:return False
    with ThreadPoolExecutor(max_workers=12) as pool:assert sum(pool.map(attempt,range(40)))==30
    assert account(owner)['calls']==30
    with owner.connect() as c:assert c.execute("SELECT count(*) n FROM shared_model_quota.reservations WHERE state='RELEASED'").fetchone()['n']==10

def test_two_synthetic_products_same_coordinator_share_thirty_slots(fixture,pg):
    store,owner=setup(fixture);role='quota_fixture_second'
    with psycopg.connect(pg.get_uri(),autocommit=True) as c:
        if not c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():c.execute('CREATE ROLE quota_fixture_second LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    with owner.connect() as c:
        c.execute("INSERT INTO shared_model_quota.products VALUES('second-synthetic-product',%s,'synthetic-shared-account',100,819200,0,0)",(role,))
        c.execute('GRANT USAGE ON SCHEMA shared_model_quota TO quota_fixture_second')
        c.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA shared_model_quota TO quota_fixture_second')
    def attempt(n):
        dsn,product=(store.dsn,'parkweave') if n%2 else (make_conninfo(owner.dsn,user=role),'second-synthetic-product')
        b=PersistentBudget(dsn,account='synthetic-shared-account',product=product,work='compete:'+str(n))
        try:r=b.reserve();b.dispatch(r);return True
        except AccountRateLimited:return False
    with ThreadPoolExecutor(max_workers=12) as pool:assert sum(pool.map(attempt,range(40)))==30
    assert account(owner)['calls']==30
    with owner.connect() as c:assert sum(r['calls'] for r in c.execute('SELECT calls FROM shared_model_quota.products').fetchall())==30

def test_clock_and_rate_policy_owner_only_live_ignores_synthetic_clock(fixture):
    store,owner=setup(fixture)
    with store.connect() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute('UPDATE shared_model_quota.synthetic_clock SET at=clock_timestamp()')
    with owner.connect() as c:
        with pytest.raises(psycopg.errors.CheckViolation):c.execute('UPDATE shared_model_quota.accounts SET rate_limit=31')
    with owner.connect() as c:
        c.execute("UPDATE shared_model_quota.accounts SET kind='LIVE',authorization_evidence='SYNTHETIC authorization, not actual approval',approved_by='SYNTHETIC owner'")
        actual=c.execute("SELECT shared_model_quota.time_for('synthetic-shared-account') t,clock_timestamp() now").fetchone()
        assert abs((actual['t']-actual['now']).total_seconds())<1
    with pytest.raises(ModelBoundaryError):budget(store,'unverified-live',kind='LIVE').reserve()

class NamesOnly(Mapping):
    def __init__(self,names):self.names=names;self.iterations=0
    def __getitem__(self,key):raise AssertionError('secret value accessed')
    def __iter__(self):self.iterations+=1;return iter(self.names)
    def __len__(self):return len(self.names)

@pytest.mark.parametrize('token_name',['PARKWEAVE_INTERN_API_TOKEN','INTERN_API_TOKEN'])
def test_live_config_presence_checks_names_only(token_name):
    env=NamesOnly([token_name,'PARKWEAVE_QUOTA_DSN','PARKWEAVE_PROVIDER_ACCOUNT'])
    check_names(env,enabled=True,budget_authorized=True,injection_authorized=True,rate_verified=True,shared_binding_verified=True).require()
    assert env.iterations==1

@pytest.mark.parametrize('missing',['PARKWEAVE_INTERN_API_TOKEN','PARKWEAVE_QUOTA_DSN','PARKWEAVE_PROVIDER_ACCOUNT'])
def test_live_missing_names_fail_closed(missing):
    env=NamesOnly([x for x in ['PARKWEAVE_INTERN_API_TOKEN','PARKWEAVE_QUOTA_DSN','PARKWEAVE_PROVIDER_ACCOUNT'] if x!=missing])
    with pytest.raises(ModelBoundaryError,match='LIVE_SAFETY_BLOCKED'):check_names(env,enabled=True,budget_authorized=True,injection_authorized=True,rate_verified=True,shared_binding_verified=True).require()

@pytest.mark.parametrize('field',list(LiveSafety.__dataclass_fields__))
def test_live_each_explicit_precondition_required(field):
    fields={name:True for name in LiveSafety.__dataclass_fields__};fields[field]=False
    with pytest.raises(ModelBoundaryError):LiveSafety(**fields).require()
    fields[field]='true'
    with pytest.raises(ModelBoundaryError):LiveSafety(**fields).require()

def test_default_live_off_does_not_even_iterate_names():
    env=NamesOnly(['INTERN_API_TOKEN'])
    with pytest.raises(ModelBoundaryError):check_names(env).require()
    assert env.iterations==0

def counted_chain(store):
    base=synthetic_transport();requests=[]
    def handler(request):requests.append(request);return base.transport.handle_request(request)
    return chain(store,InternHTTPTransport(httpx.MockTransport(handler))),requests

def due(owner,run):
    with owner.connect() as c:c.execute('UPDATE runs SET next_attempt_at=clock_timestamp() WHERE id=%s',(run,))

def test_rate_deferred_feedback_resumes_no_duplicate_case_or_plan(fixture):
    store,owner=setup(fixture,1);run=submit(fixture);ch,requests=counted_chain(store)
    ch.execute(store.claim('first'));r,op,case=rows(owner,run)
    assert r['state']=='RUNNING' and r['lease_until'] is None and op['state']=='VERIFIED' and len(requests)==1
    assert store.claim('not-due') is None
    case_id=case['id'];clock(owner,60);due(owner,run);ch.execute(store.claim('resume'))
    r,op,case=rows(owner,run);assert r['state']=='SUCCEEDED' and case['id']==case_id and len(requests)==2
    assert account(owner)['calls']==2 and account(owner)['tokens']==30
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM model_plans WHERE run_id=%s',(run,)).fetchone()['n']==2
        assert c.execute('SELECT count(*) n FROM cases WHERE run_id=%s',(run,)).fetchone()['n']==1

def test_rate_denial_retry_is_bounded_three_attempts_known_effect_preserved(fixture):
    store,owner=setup(fixture,1);run=submit(fixture);ch,requests=counted_chain(store)
    for n in range(3):
        due(owner,run);ch.execute(store.claim('retry:'+str(n)))
    r,op,case=rows(owner,run)
    assert r['state']=='FAILED' and op['state']=='VERIFIED' and case['state']=='NEEDS_INPUT' and len(requests)==1
    assert account(owner)['calls']==1 and account(owner)['tokens']==15
    with owner.connect() as c:
        feedback=c.execute("SELECT * FROM shared_model_quota.reservations WHERE work=%s",(run+':FEEDBACK',)).fetchone()
        assert feedback['rate_denials']==3 and feedback['state']=='RELEASED'
        assert c.execute("SELECT outcome FROM model_steps WHERE run_id=%s AND phase='FEEDBACK'",(run,)).fetchone()['outcome']=='ACCOUNT_RATE_LIMITED_NOT_SENT'
