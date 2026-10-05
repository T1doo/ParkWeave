"""Self-authored HTTP fixtures + actual PG/CLI; zero provider calls."""
import json
import os
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
import psycopg
import pytest
from pydantic import SecretStr
from parkweave.quota import PersistentBudget
from parkweave.intern_adapter import InternChatAdapter,ModelBoundaryError
from parkweave.http_transport import InternHTTPTransport
from parkweave.model_chain import ModelChain,synthetic_transport,FAKE_TOKEN
from parkweave.process_env import minimal_environment
from parkweave.store import Conflict

@pytest.fixture(autouse=True)
def no_provider_sockets(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('real HTTP transport forbidden in ENG007')
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',forbidden)

def provision(owner,*,calls=4,tokens=32768,approved=True,kind='SYNTHETIC'):
    with owner.connect() as c:
        c.execute(Path('src/parkweave/quota.sql').read_text())
        c.execute("INSERT INTO shared_model_quota.accounts(account,kind,approved,starts,ends,call_limit,token_limit,calls,tokens,authorization_evidence,approved_by) VALUES('synthetic-shared-account',%s,%s,clock_timestamp()-interval '1 minute',clock_timestamp()+interval '1 hour',%s,%s,0,0,NULL,NULL)",(kind,approved,calls,tokens))
        c.execute("INSERT INTO shared_model_quota.products VALUES('parkweave','parkweave_app','synthetic-shared-account',%s,%s,0,0)",(calls,tokens))
        c.execute('GRANT USAGE ON SCHEMA shared_model_quota TO parkweave_app')
        c.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA shared_model_quota TO parkweave_app')

def budget(store,work='fixture:PLAN',**kwargs):
    return PersistentBudget(store.dsn,account='synthetic-shared-account',product='parkweave',work=work,**kwargs)

def submit(fixture):
    store,owner,tokens,client=fixture
    r=client.post('/api/runs',headers={'Authorization':'Bearer '+tokens['fixture-a'],'Idempotency-Key':'model-test'},json={'goal':'SYNTHETIC local goal','action':'case.create'})
    assert r.status_code==202
    return r.json()['run_id']

def chain(store,transport=None):
    return ModelChain(store,quota_dsn=store.dsn,account='synthetic-shared-account',transport=transport or synthetic_transport(),token=SecretStr(FAKE_TOKEN))

def rows(owner,run):
    with owner.connect() as c:
        return c.execute('SELECT * FROM runs WHERE id=%s',(run,)).fetchone(),c.execute('SELECT * FROM operations WHERE run_id=%s',(run,)).fetchone(),c.execute('SELECT * FROM cases WHERE run_id=%s',(run,)).fetchone()

@pytest.mark.parametrize('scenario,cases',[('good',1),('wrong-model',0),('bad-args',0),('truncated',0),('secret-echo',0),('timeout',0),('feedback-error',1)])
def test_actual_worker_plan_tool_feedback_and_failures(fixture,scenario,cases):
    store,owner,*_=fixture;provision(owner);run=submit(fixture)
    proc=subprocess.run([sys.executable,'-m','parkweave.worker','--once','--model-fixture',scenario],
        env=minimal_environment(os.environ,PARKWEAVE_DSN=store.dsn),capture_output=True,text=True,timeout=10)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    assert FAKE_TOKEN not in proc.stdout+proc.stderr
    r,op,case=rows(owner,run)
    assert bool(case)==bool(cases)
    assert r['state']==('SUCCEEDED' if scenario=='good' else 'FAILED')
    if cases:
        assert op['state']=='VERIFIED' and op['receipt']['verified'] is True
        assert case['state']=='NEEDS_INPUT' and case['external_acceptance']=='NOT_SUBMITTED' and case['offline_fulfillment']=='NO_EVIDENCE'
        assert r['success_scope']=='LOCAL_CASE_CREATED'
    with owner.connect() as c:
        usage=c.execute('SELECT * FROM shared_model_quota.reservations ORDER BY work').fetchall()
        assert len(usage)==(2 if cases else 1)
        assert FAKE_TOKEN not in repr(usage)
        if scenario in ('timeout','secret-echo'):assert usage[0]['state']=='OUTCOME_UNKNOWN' and usage[0]['usage'] is None
        if scenario=='good':
            steps=c.execute('SELECT * FROM model_steps WHERE run_id=%s ORDER BY phase',(run,)).fetchall()
            assert len(steps)==2 and all(s['state']=='VALIDATED' for s in steps)
            assert all(s['result']['mode']=='OFFLINE_HTTP_FIXTURE' for s in steps)

def test_worker_without_budget_blocks_before_http_or_effect(fixture):
    store,owner,*_=fixture;run=submit(fixture)
    chain(store).execute(store.claim('worker'))
    r,op,case=rows(owner,run)
    assert r['state']=='FAILED' and op['receipt']['reason']=='QUOTA_DENIED' and case is None

@pytest.mark.parametrize('approved,kind',[(False,'LIVE'),(True,'SYNTHETIC')])
def test_real_transport_gate_zero_network_without_live_budget(fixture,approved,kind):
    store,owner,*_=fixture;provision(owner,approved=approved,kind=kind)
    from parkweave.live_safety import LiveSafety
    safety=LiveSafety(*([True]*7))  # Explicit fictional conditions, never real environment.
    adapter=InternChatAdapter(transport=InternHTTPTransport(),token=SecretStr(FAKE_TOKEN),budget=budget(store,kind='LIVE'),live_safety=safety)
    with pytest.raises(ModelBoundaryError,match='QUOTA_DENIED'):adapter.complete([{'role':'user','content':'synthetic'}])
    with owner.connect() as c:assert c.execute('SELECT calls FROM shared_model_quota.accounts').fetchone()['calls']==0

def test_unknown_sent_work_survives_restart_no_refund_or_resend(fixture):
    store,owner,*_=fixture;provision(owner,calls=1,tokens=8192)
    b=budget(store);r=b.reserve();b.dispatch(r);b.finish(r,'TIMEOUT_OUTCOME_UNKNOWN')
    with pytest.raises(ModelBoundaryError,match='PREVIOUS_ATTEMPT_NO_RESEND'):budget(store).reserve()
    with pytest.raises(ModelBoundaryError,match='QUOTA_DENIED'):budget(store,'different').reserve()
    with pytest.raises(ModelBoundaryError):b.release(r)
    with owner.connect() as c:
        q=c.execute('SELECT * FROM shared_model_quota.accounts').fetchone();assert q['calls']==1 and q['tokens']==8192

def test_dispatch_race_one_winner_and_usage_replay_immutable(fixture):
    store,owner,*_=fixture;provision(owner);b=budget(store);r=b.reserve()
    def dispatch(_):
        try:b.dispatch(r);return True
        except ModelBoundaryError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(dispatch,range(2)))==1
    usage={'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}
    b.finish(r,'VALIDATED',usage);b.finish(r,'VALIDATED',usage)
    with pytest.raises(ModelBoundaryError):b.finish(r,'VALIDATED',usage|{'total_tokens':16})
    with owner.connect() as c:assert c.execute('SELECT tokens FROM shared_model_quota.accounts').fetchone()['tokens']==15

def test_owner_only_limits_and_role_account_binding(fixture):
    store,owner,*_=fixture;provision(owner)
    with store.connect() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute('UPDATE shared_model_quota.accounts SET call_limit=999')
    with pytest.raises(ModelBoundaryError):PersistentBudget(store.dsn,account='other-account',product='parkweave',work='x').reserve()
    with pytest.raises(ModelBoundaryError):PersistentBudget(store.dsn,account='synthetic-shared-account',product='other-product',work='x').reserve()

def test_two_products_coordinate_same_account_atomically(fixture,pg):
    store,owner,*_=fixture;provision(owner,calls=1,tokens=8192)
    role='quota_fixture_second'
    with psycopg.connect(pg.get_uri(),autocommit=True) as c:
        if not c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():c.execute('CREATE ROLE quota_fixture_second LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    with owner.connect() as c:
        c.execute("INSERT INTO shared_model_quota.products VALUES('second-synthetic-product',%s,'synthetic-shared-account',1,8192,0,0)",(role,))
        c.execute('GRANT USAGE ON SCHEMA shared_model_quota TO quota_fixture_second')
        c.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA shared_model_quota TO quota_fixture_second')
    from psycopg.conninfo import make_conninfo
    second=PersistentBudget(make_conninfo(owner.dsn,user=role),account='synthetic-shared-account',product='second-synthetic-product',work='y')
    def reserve(b):
        try:b.reserve();return True
        except ModelBoundaryError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(reserve,[budget(store),second]))==1
    with owner.connect() as c:assert c.execute('SELECT calls FROM shared_model_quota.accounts').fetchone()['calls']==1

def test_revoked_after_model_response_before_tool_blocks_effect_but_settles_usage(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);base=synthetic_transport()
    def handler(request):
        response=base.transport.handle_request(request)
        owner.revoke('fixture-a')
        return response
    chain(store,InternHTTPTransport(httpx.MockTransport(handler))).execute(store.claim('worker'))
    r,op,case=rows(owner,run);assert r['state']=='FAILED' and case is None
    with owner.connect() as c:
        q=c.execute('SELECT * FROM shared_model_quota.reservations').fetchone();assert q['state']=='SETTLED' and q['usage']['total_tokens']==15

def test_feedback_resume_keeps_known_effect_and_does_not_repeat_plan(fixture,monkeypatch):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);claim=store.claim('worker');ch=chain(store)
    original=ch.step
    def interrupted(claim,phase,messages):
        if phase=='FEEDBACK':raise Conflict('synthetic process lost after known local effect')
        return original(claim,phase,messages)
    monkeypatch.setattr(ch,'step',interrupted)
    with pytest.raises(Conflict):ch.execute(claim)
    r,op,case=rows(owner,run);case_id=case['id'];assert op['state']=='VERIFIED' and r['state']=='RUNNING'
    with owner.connect() as c:c.execute("UPDATE runs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",(run,))
    chain(store).execute(store.claim('replacement'))
    r,op,case=rows(owner,run);assert r['state']=='SUCCEEDED' and case['id']==case_id
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==2

def test_secret_escape_and_stream_limit_reject_before_business(fixture):
    store,owner,*_=fixture;provision(owner)
    raw=json.dumps({'id':'synthetic','model':'Intern-S2','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':FAKE_TOKEN}}]}).replace('synthetic-worker',r'\u0073ynthetic-worker')
    a=InternChatAdapter(transport=InternHTTPTransport(httpx.MockTransport(lambda _:httpx.Response(200,text=raw))),token=SecretStr(FAKE_TOKEN),budget=budget(store))
    with pytest.raises(ModelBoundaryError,match='SECRET_OUTPUT_REJECTED'):a.complete([{'role':'user','content':'fixture'}])
    b=InternChatAdapter(transport=InternHTTPTransport(httpx.MockTransport(lambda _:httpx.Response(200,content=b'x'*65537))),token=SecretStr(FAKE_TOKEN),budget=budget(store,'large'))
    with pytest.raises(ModelBoundaryError,match='RESPONSE_LIMIT'):b.complete([{'role':'user','content':'fixture'}])

def test_product_ceiling_unsent_release_and_expired_dispatch(fixture):
    store,owner,*_=fixture;provision(owner,calls=3,tokens=24576)
    with owner.connect() as c:c.execute("UPDATE shared_model_quota.products SET call_limit=1 WHERE product='parkweave'")
    b=budget(store);r=b.reserve()
    with pytest.raises(ModelBoundaryError):budget(store,'second').reserve()
    b.release(r)
    fresh=budget(store,'third');r2=fresh.reserve()
    with owner.connect() as c:c.execute("UPDATE shared_model_quota.accounts SET ends=clock_timestamp()-interval '1 second'")
    with pytest.raises(ModelBoundaryError):fresh.dispatch(r2)
    fresh.release(r2)
    with owner.connect() as c:
        q=c.execute('SELECT * FROM shared_model_quota.accounts').fetchone();assert q['calls']==0 and q['tokens']==0

def test_dispatched_crash_resumes_as_failure_without_model_resend(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);claim=store.claim('lost')
    with owner.connect() as c:
        c.execute("INSERT INTO model_steps VALUES(%s,'PLAN','STARTED',NULL,NULL)",(run,))
        c.execute("UPDATE runs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",(run,))
    b=budget(store,run+':PLAN');record=b.reserve();b.dispatch(record)
    chain(store).execute(store.claim('replacement'))
    r,op,case=rows(owner,run);assert r['state']=='FAILED' and case is None and op['receipt']['reason']=='PREVIOUS_ATTEMPT_NO_RESEND'
    with owner.connect() as c:
        q=c.execute('SELECT * FROM shared_model_quota.reservations').fetchone();assert q['state']=='DISPATCHED' and q['reserved']==8192

def test_default_worker_cannot_bypass_started_model_intent(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture)
    with owner.connect() as c:c.execute("INSERT INTO model_steps VALUES(%s,'PLAN','STARTED',NULL,NULL)",(run,))
    proc=subprocess.run([sys.executable,'-m','parkweave.worker','--once'],env=minimal_environment(os.environ,PARKWEAVE_DSN=store.dsn),capture_output=True,text=True,timeout=10)
    assert proc.returncode==0
    r,op,case=rows(owner,run);assert r['state']=='FAILED' and case is None and op['receipt']['reason']=='MODEL_CHAIN_RUNTIME_REQUIRED'

def test_proposal_cannot_change_intent(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);base=synthetic_transport()
    def handler(request):
        response=base.transport.handle_request(request);body=response.json()
        body['choices'][0]['message']['tool_calls'][0]['function']['arguments']=json.dumps({'goal':'different goal'})
        return httpx.Response(200,json=body)
    chain(store,InternHTTPTransport(httpx.MockTransport(handler))).execute(store.claim('worker'))
    r,op,case=rows(owner,run);assert r['state']=='FAILED' and case is None and op['receipt']['reason']=='INTENT_PROPOSAL_MISMATCH'

def test_revoked_before_dispatch_releases_only_confirmed_unsent_reservation(fixture):
    store,owner,*_=fixture;provision(owner)
    def revoke():raise Conflict('synthetic revoke before dispatch')
    a=InternChatAdapter(transport=synthetic_transport(),token=SecretStr(FAKE_TOKEN),budget=budget(store),before_dispatch=revoke)
    with pytest.raises(ModelBoundaryError,match='DISPATCH_AUTHORIZATION_CHANGED'):a.complete([{'role':'user','content':'fixture'}])
    with owner.connect() as c:
        assert c.execute('SELECT calls FROM shared_model_quota.accounts').fetchone()['calls']==0
        assert c.execute('SELECT state FROM shared_model_quota.reservations').fetchone()['state']=='RELEASED'

def test_usage_overrun_is_charged_and_prevents_next_request(fixture):
    store,owner,*_=fixture;provision(owner,calls=3,tokens=8192)
    base=synthetic_transport()
    def handler(request):
        body=base.transport.handle_request(request).json();body['usage']={'prompt_tokens':9000,'completion_tokens':1,'total_tokens':9001}
        return httpx.Response(200,json=body)
    a=InternChatAdapter(transport=InternHTTPTransport(httpx.MockTransport(handler)),token=SecretStr(FAKE_TOKEN),budget=budget(store))
    with pytest.raises(ModelBoundaryError,match='USAGE_RESERVATION_EXCEEDED'):a.complete([{'role':'user','content':'fixture'}])
    with owner.connect() as c:assert c.execute('SELECT tokens FROM shared_model_quota.accounts').fetchone()['tokens']==9001
    with pytest.raises(ModelBoundaryError):budget(store,'new').reserve()

def test_feedback_second_tool_is_not_executed_and_known_case_survives(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);base=synthetic_transport()
    def handler(request):
        if json.loads(request.content)['messages'][-1]['role']=='tool':
            original=httpx.Request('POST',str(request.url),json={'messages':[{'role':'user','content':'SYNTHETIC local goal'}]})
            return base.transport.handle_request(original)
        return base.transport.handle_request(request)
    chain(store,InternHTTPTransport(httpx.MockTransport(handler))).execute(store.claim('worker'))
    r,op,case=rows(owner,run)
    assert r['state']=='FAILED' and case is not None and op['state']=='VERIFIED'
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM cases WHERE run_id=%s',(run,)).fetchone()['n']==1
        assert c.execute("SELECT outcome FROM model_steps WHERE run_id=%s AND phase='FEEDBACK'",(run,)).fetchone()['outcome']=='FEEDBACK_TOOL_REJECTED'

def test_fenced_response_records_usage_but_cannot_save_plan_or_create_case(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);base=synthetic_transport();claim=store.claim('old')
    def handler(request):
        response=base.transport.handle_request(request)
        with owner.connect() as c:c.execute('UPDATE runs SET fence=fence+1 WHERE id=%s',(run,))
        return response
    with pytest.raises(Conflict):chain(store,InternHTTPTransport(httpx.MockTransport(handler))).execute(claim)
    r,op,case=rows(owner,run);assert case is None and op['state']=='PREPARED'
    with owner.connect() as c:
        assert c.execute('SELECT state FROM shared_model_quota.reservations').fetchone()['state']=='SETTLED'
        assert c.execute('SELECT state FROM model_steps WHERE run_id=%s',(run,)).fetchone()['state']=='STARTED'

def test_independent_heartbeat_renews_while_http_fixture_waits(fixture):
    import time
    from parkweave.lease import LeaseKeeper
    store,owner,*_=fixture;provision(owner);run=submit(fixture);base=synthetic_transport();claim=store.claim('worker',1)
    def handler(request):
        if json.loads(request.content)['messages'][-1]['role']=='user':
            time.sleep(1.4)
            with owner.connect() as c:
                r=c.execute('SELECT heartbeat_count,lease_until>clock_timestamp() live FROM runs WHERE id=%s',(run,)).fetchone()
                assert r['live'] and r['heartbeat_count']>=2
            assert store.claim('competitor',1) is None
        return base.transport.handle_request(request)
    with LeaseKeeper(store,claim,1):chain(store,InternHTTPTransport(httpx.MockTransport(handler))).execute(claim)
    assert rows(owner,run)[0]['state']=='SUCCEEDED'

def test_invalid_usage_does_not_become_false_settled_charge(fixture):
    store,owner,*_=fixture;provision(owner);base=synthetic_transport()
    def handler(request):
        body=base.transport.handle_request(request).json();body['usage']={'prompt_tokens':10,'completion_tokens':5,'total_tokens':16}
        return httpx.Response(200,json=body)
    a=InternChatAdapter(transport=InternHTTPTransport(httpx.MockTransport(handler)),token=SecretStr(FAKE_TOKEN),budget=budget(store))
    with pytest.raises(ModelBoundaryError,match='INVALID_USAGE'):a.complete([{'role':'user','content':'fixture'}])
    with owner.connect() as c:
        row=c.execute('SELECT * FROM shared_model_quota.reservations').fetchone()
        assert row['state']=='OUTCOME_UNKNOWN' and row['usage'] is None and row['outcome']=='INVALID_USAGE'
        assert c.execute('SELECT tokens FROM shared_model_quota.accounts').fetchone()['tokens']==8192

def test_live_approval_requires_owner_evidence_not_just_boolean(fixture):
    store,owner,*_=fixture;provision(owner,kind='LIVE',approved=False)
    with owner.connect() as c:
        with pytest.raises(psycopg.errors.CheckViolation):c.execute('UPDATE shared_model_quota.accounts SET approved=true')
    with pytest.raises(ModelBoundaryError):budget(store,kind='LIVE').reserve()
