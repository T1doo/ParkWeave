"""Append-only synthetic delivery feedback through current API and real PG."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4, UUID
import pytest
import psycopg
from parkweave.store import Store
from parkweave.api import create_app
from fastapi.testclient import TestClient
from test_preparation import preparation_fixture, filled, command, add, read, headers, create
from test_readiness import rows

SPECIALIST='prep-specialist-fixture-a'

def checked(r,status=200):
    assert r.status_code==status,r.text
    return r.json()

def ready(f):
    return checked(command(f,filled(f),'REVIEW',SPECIALIST,reason='SYNTHETIC independent review'))

def url(p):return '/api/preparations/'+p['preparation_id']+'/material-objections'

def get(f,p,user='fixture-a'):return f[3].get(url(p),headers=headers(f[2],user))

def body(v,action='RAISE',ticket=None,reason='SYNTHETIC explicit feedback'):
    d=dict(action=action,expected_preparation_revision=v['preparation_revision'],expected_version=ticket['version'] if ticket else 0,
           binding_sha256=v['binding']['sha256'],reason=reason)
    if ticket:d['objection_id']=ticket['id']
    if action in ('KEEP_OPEN','ACCEPT_RESPONSE'):d['response_id']=ticket['response_id']
    return d

def post(f,p,d,user='fixture-a',key=None):return f[3].post(url(p),headers=headers(f[2],user,key or uuid4().hex),json=d)

def act(f,p,action='RAISE',user='fixture-a',reason='SYNTHETIC explicit feedback'):
    v=checked(get(f,p,user));t=v['items'][-1] if action!='RAISE' else None
    return checked(post(f,p,body(v,action,t,reason),user))

def test_owner_review_is_only_resolution_and_immutable_history(preparation_fixture):
    f=preparation_fixture;p=ready(f);before=rows(f)
    opened=act(f,p);v=checked(get(f,p));assert v['unresolved'] and v['items'][0]['state']=='OPEN'
    assert command(f,opened,'CONFIRM',reason='cannot bypass unresolved').status_code==409
    responded=act(f,p,'RESPOND',SPECIALIST);v=checked(get(f,p));assert v['unresolved'] and v['items'][0]['state']=='AWAITING_OWNER_REVIEW'
    assert command(f,responded,'CONFIRM',reason='response not resolution').status_code==409
    act(f,p,'KEEP_OPEN');assert checked(get(f,p))['items'][0]['state']=='OPEN'
    act(f,p,'RESPOND',SPECIALIST);resolved=act(f,p,'ACCEPT_RESPONSE')
    v=checked(get(f,p));assert not v['unresolved'] and len(v['items'][0]['history'])==5
    confirmed=checked(command(f,resolved,'CONFIRM',reason='explicit current confirmation'))
    assert confirmed['state']=='LOCAL_CONFIRMED' and not checked(get(f,p))['case_goal_completed']
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s',(p['case_id'],)).fetchone()['state']=='NEEDS_INPUT'
        es=c.execute("SELECT id,payload FROM preparation_events WHERE action='MATERIAL_OBJECTION' ORDER BY revision").fetchall()
        assert [str(e['id']) for e in es]==[h['event_id'] for h in v['items'][0]['history']]
    after=rows(f)
    for t in before:
        if t not in ('preparations','preparation_events','controlled_plans'):assert before[t]==after[t],t
    for sql in ('UPDATE preparation_events SET payload=payload','DELETE FROM preparation_events'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)

@pytest.mark.parametrize('action,user',[('RAISE',SPECIALIST),('RESPOND','fixture-a'),('KEEP_OPEN',SPECIALIST),('ACCEPT_RESPONSE',SPECIALIST),('REBIND',SPECIALIST)])
def test_no_role_escalation(preparation_fixture,action,user):
    f=preparation_fixture;p=ready(f);act(f,p);v=checked(get(f,p));before=rows(f)
    d=body(v,action,v['items'][0] if action!='RAISE' else None)
    if action in ('KEEP_OPEN','ACCEPT_RESPONSE'):d['response_id']=str(uuid4())
    assert post(f,p,d,user).status_code==403
    assert rows(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-b','prep-specialist-fixture-c'])
def test_cross_tenant_read_write_recovery_private(preparation_fixture,user):
    f=preparation_fixture;p=ready(f);v=checked(get(f,p));key=uuid4().hex;checked(post(f,p,body(v,reason='PRIVATE feedback'),key=key));before=rows(f)
    for r in (get(f,p,user),post(f,p,body(v),user),f[3].get(url(p)+'/recovery/'+key,headers=headers(f[2],user))):
        assert r.status_code==403 and 'PRIVATE' not in r.text and p['case_id'] not in r.text
    assert rows(f)==before

@pytest.mark.parametrize('role,cap',[('fixture-a','READ'),('fixture-a','PREPARE'),('fixture-a','EXECUTE'),(SPECIALIST,'READ'),(SPECIALIST,'REVIEW_ASSIGNED'),(SPECIALIST,'inactive')])
def test_current_revocation_precedes_replay_and_recovery(preparation_fixture,role,cap):
    f=preparation_fixture;p=ready(f);act(f,p)
    v=checked(get(f,p,role));d=body(v,'RESPOND',v['items'][0]) if role==SPECIALIST else body(v)
    key=uuid4().hex;checked(post(f,p,d,role,key))
    with f[1].connect() as c:
        f[1].lock_principal(c,role,exclusive=True)
        if cap=='inactive':c.execute('UPDATE principals SET active=false WHERE id=%s',(role,))
        elif cap in ('PREPARE','REVIEW_ASSIGNED'):c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(role,))
        else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(role,cap))
    before=rows(f);assert post(f,p,d,role,key).status_code==403
    recovery=f[3].get(url(p)+'/recovery/'+key,headers=headers(f[2],role))
    # EXECUTE is a write gate; authorized read-only recovery remains possible.
    assert recovery.status_code==(200 if cap=='EXECUTE' else 403)
    assert rows(f)==before

def test_lost_response_cold_store_and_original_key_replay(preparation_fixture):
    f=preparation_fixture;p=ready(f);d=body(checked(get(f,p)));key=uuid4().hex;original=checked(post(f,p,d,key=key));before=rows(f)
    with TestClient(create_app(Store(f[0].dsn))) as api:
        r=checked(api.get(url(p)+'/recovery/'+key,headers=headers(f[2])))
        assert r['event']==original and r['status']=='COMMITTED' and not r['automatically_replayed']
        assert checked(api.post(url(p),headers=headers(f[2],key=key),json=d))==original
        assert api.post(url(p),headers=headers(f[2],key=key),json={**d,'reason':'different'}).status_code==409
        absence=checked(api.get(url(p)+'/recovery/'+uuid4().hex,headers=headers(f[2])))
        assert absence['status']=='NOT_OBSERVED' and absence['event'] is None
    assert rows(f)==before

@pytest.mark.parametrize('change',['material','request','catalog','reopen'])
def test_source_changes_require_explicit_rebind_new_response(preparation_fixture,change):
    f=preparation_fixture;p=ready(f);act(f,p);responded=act(f,p,'RESPOND',SPECIALIST);old=checked(get(f,p));history=old['items'][0]['history']
    if change=='material':new=checked(add(f,responded,text='SYNTHETIC changed actual source'))
    elif change=='request':
        new=checked(f[3].post('/api/preparations/'+p['preparation_id']+'/request-intent',headers=headers(f[2],key=uuid4().hex),json=dict(expected_preparation_revision=responded['revision'],request_text='SYNTHETIC new intent',required_goals=[])))
    elif change=='reopen':new=checked(command(f,responded,'REOPEN',reason='explicit reopen'))
    else:
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"v2\"}'::jsonb WHERE park_id='park-a'")
        new=responded
    stale=checked(get(f,p));assert stale['items'][0]['state']=='STALE'
    assert post(f,p,body(stale,'ACCEPT_RESPONSE',stale['items'][0])).status_code==409
    if change=='catalog':new=checked(command(f,new,'REOPEN',reason='SYNTHETIC changed catalog requires new review'))
    new=checked(command(f,new,'REVIEW',SPECIALIST,reason='SYNTHETIC new independent source review'))
    v=checked(get(f,p));rebound=checked(post(f,p,body(v,'REBIND',v['items'][0])))
    assert checked(get(f,p))['items'][0]['history'][:2]==history
    v=checked(get(f,p));d=body(v,'ACCEPT_RESPONSE',v['items'][0]);d['response_id']=history[-1]['event_id']
    assert post(f,p,d).status_code==409
    act(f,p,'RESPOND',SPECIALIST);act(f,p,'ACCEPT_RESPONSE');assert not checked(get(f,p))['unresolved']

@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_writers_single_effect(preparation_fixture,same_key):
    f=preparation_fixture;p=ready(f);d=body(checked(get(f,p)));key=uuid4().hex
    with ThreadPoolExecutor(2) as ex:
        results=list(ex.map(lambda k:post(f,p,d,key=k),[key,key if same_key else uuid4().hex]))
    assert sorted(r.status_code for r in results)==([200,200] if same_key else [200,409])
    assert len(checked(get(f,p))['items'])==1

def test_response_identity_cas_and_transaction_rollback(preparation_fixture,monkeypatch):
    from parkweave import preparation as prep
    f=preparation_fixture;p=ready(f);act(f,p);act(f,p,'RESPOND',SPECIALIST);v=checked(get(f,p));before=rows(f)
    d=body(v,'ACCEPT_RESPONSE',v['items'][0]);d['response_id']=str(uuid4())
    assert post(f,p,d).status_code==409 and rows(f)==before
    def fail(*args,**kwargs):raise RuntimeError('SYNTHETIC transaction fault')
    monkeypatch.setattr(prep,'event',fail)
    with pytest.raises(RuntimeError):post(f,p,body(v,'ACCEPT_RESPONSE',v['items'][0]))
    assert rows(f)==before

def test_feedback_private_endpoint_not_generic_history_and_no_sql_text(preparation_fixture):
    f=preparation_fixture;p=ready(f);act(f,p,reason="PRIVATE <script>throw Error('x')</script>; DROP TABLE cases")
    generic=checked(read(f,p));assert all('objection' not in h['payload'] for h in generic['history'])
    dedicated=checked(get(f,p));assert 'PRIVATE' in dedicated['items'][0]['history'][0]['reason']
    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==1

@pytest.mark.parametrize('alter',[{'reason':''},{'reason':'x'*1001},{'action':'CLOSE_CASE'},{'binding_sha256':'fake'},{'expected_version':1},{'park_id':'park-b'},{'response_id':str(uuid4())}])
def test_bounded_shape_rejects_without_mutation(preparation_fixture,alter):
    f=preparation_fixture;p=ready(f);d=body(checked(get(f,p)));before=rows(f)
    assert post(f,p,{**d,**alter}).status_code==422 and rows(f)==before

def test_existing_database_migration_requires_receipt(preparation_fixture):
    f=preparation_fixture
    with f[1].connect() as c:assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==28
    # Current Linux version 28 is restart-compatible without rerunning migration or fresh receipt.
    Store(f[1].dsn).migrate()

from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_case_lifecycle import built, read as lifecycle_read, act as lifecycle_act

def test_unresolved_feedback_blocks_real_local_close(preparation_fixture,link_fixture):
    f=link_fixture;p,_,_,_=built(f)
    lc=checked(lifecycle_read(f,p));validated=checked(lifecycle_act(f,p,lc,'REVALIDATE'))
    act(f,p)
    before=rows(f);r=lifecycle_act(f,p,validated,'CLOSE_LOCAL_RECORD')
    assert r.status_code==409 and rows(f)==before
    with f[1].connect() as c:assert c.execute('SELECT state FROM cases WHERE id=%s',(p['case_id'],)).fetchone()['state']!='FULFILLED'


def test_same_enterprise_other_case_cannot_use_objection_or_recovery_key(preparation_fixture):
    f=preparation_fixture;p=ready(f);d=body(checked(get(f,p)));key=uuid4().hex;opened=checked(post(f,p,d,key=key))
    other=ready(f);before=rows(f)
    assert f[3].get(url(other)+'/recovery/'+key,headers=headers(f[2])).status_code==409
    assert post(f,other,body(checked(get(f,other)),reason='different'),key=key).status_code==409
    assert rows(f)==before


def test_raw_source_tampering_and_reviewer_revocation_cannot_accept_response(preparation_fixture):
    f=preparation_fixture;p=ready(f);act(f,p);act(f,p,'RESPOND',SPECIALIST)
    with f[1].connect() as c:c.execute("UPDATE preparation_evidence SET text='SYNTHETIC tampered body' WHERE preparation_id=%s AND slot='need_summary'",(p['preparation_id'],))
    v=checked(get(f,p));before=rows(f)
    assert v['items'][0]['state']=='STALE' and not v['current_review_valid']
    assert post(f,p,body(v,'ACCEPT_RESPONSE',v['items'][0])).status_code==409 and rows(f)==before


def test_bound_history_limits_leave_pending_visible(preparation_fixture):
    f=preparation_fixture;p=ready(f)
    for _ in range(8):act(f,p)
    v=checked(get(f,p));assert len(v['items'])==8 and not v['can_raise'] and v['unresolved']
    before=rows(f);assert post(f,p,body(v)).status_code==409 and rows(f)==before

@pytest.mark.parametrize('user,cap',[('fixture-a','READ'),('fixture-a','EXECUTE'),(SPECIALIST,'READ')])
def test_restored_capability_generation_requires_explicit_rebind(preparation_fixture,user,cap):
    f=preparation_fixture;p=ready(f);act(f,p);act(f,p,'RESPOND',SPECIALIST)
    f[1].revoke_capability(user,cap)
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True)
        c.execute('UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id=%s AND capability=%s',(user,cap))
    v=checked(get(f,p));assert v['items'][0]['state']=='STALE'
    assert post(f,p,body(v,'ACCEPT_RESPONSE',v['items'][0])).status_code==409
    parent=checked(read(f,p))['preparation'];current={'preparation_id':p['preparation_id'],'revision':parent['revision']}
    current=checked(command(f,current,'REOPEN',reason='SYNTHETIC new authority generation'))
    checked(command(f,current,'REVIEW',SPECIALIST,reason='SYNTHETIC current authority independent review'))
    act(f,p,'REBIND');act(f,p,'RESPOND',SPECIALIST);act(f,p,'ACCEPT_RESPONSE')
    assert not checked(get(f,p))['unresolved']

def test_schema26_cannot_be_installed_without_real_ticket_and_ddl_rolls_back(preparation_fixture):
    from pathlib import Path
    from parkweave.store import Denied
    f=preparation_fixture;sql=Path('src/parkweave/migration-026.sql').read_text()
    before=rows(f)
    with pytest.raises(psycopg.errors.RaiseException,match='creation ticket required'):
        with f[1].connect() as c:c.execute(sql)
    with f[1].connect() as c:
        f[1]._case_fact_fixture_receipt.authorize_migration(c)
        c.execute('DELETE FROM schema_version WHERE version>=27')  # isolated prior-26 replay, fully rolled back
        c.execute(sql);c.rollback()
    assert rows(f)==before
    with f[1].connect() as c:
        f[1]._case_fact_fixture_receipt.authorize_migration(c)
        c.execute('UPDATE pg_temp.parkweave_fixture_migration_receipt SET database_oid=0')
        with pytest.raises(psycopg.errors.RaiseException,match='does not match'):c.execute(sql)
        c.rollback()
    assert rows(f)==before
