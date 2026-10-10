"""Persistent exact Approval and original atomic resource effects in real PG."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID, uuid4
import threading

import psycopg
import pytest

from parkweave import service_plan_approval as approval, case_resource_delivery as delivery
from parkweave import resource_holds as rh, resource_combinations as rc, case_resources as cr
from parkweave.store import Store, Conflict, Denied
from psycopg.conninfo import make_conninfo
from test_case_resources import link_fixture
from test_case_resource_delivery import prepared, quoted, submit, recover, effects, receipt_fixture, preparation_fixture
from test_resource_bundles import bundle, states
from test_preparation import headers


def enable(f,p,**kwargs):
    bridge=approval.IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,
        preparation_ids=[p['preparation_id']],enabled_for_isolated_tests=True,**kwargs)
    bridge.attach_store(f[0]); return bridge


def path(p,suffix=''):
    return '/api/preparations/'+p['preparation_id']+'/plan-approval'+suffix


def read(f,p,user='fixture-a'):
    return f[3].get(path(p),headers=headers(f[2],user))


def propose(f,p,data,revision=0,key=None,user='fixture-a'):
    return f[3].post(path(p,'/proposals'),headers=headers(f[2],user,key or uuid4().hex),
        json=dict(expected_revision=revision,delivery=data))


def decide(f,p,item,revision,action='APPROVE',key=None,user='fixture-a'):
    return f[3].post(path(p,'/commands'),headers=headers(f[2],user,key or uuid4().hex),
        json=dict(action=action,approval_id=item['id'],expected_revision=revision,
            expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC explicit '+action))


def setup(f):
    p=prepared(f); hs,d=bundle(f); data=quoted(f,p,d); bridge=enable(f,p)
    return p,hs,data,bridge


def approved(f,p,data):
    x=propose(f,p,data); assert x.status_code==201,x.text
    x=x.json(); item=x['items'][-1]
    y=decide(f,p,item,x['revision']); assert y.status_code==200,y.text
    return y.json()['items'][-1], y.json()


def ledger(f,p):
    with f[1].connect() as c:
        return c.execute('SELECT candidate_plan_approvals FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['candidate_plan_approvals']


def test_default_disabled_has_no_candidate_column_or_approval_authority(link_fixture):
    f=link_fixture; p=prepared(f); hs,d=bundle(f); data=quoted(f,p,d)
    status=f[3].get('/api/plan-approval/status',headers=headers(f[2])).json()
    assert status['enabled'] is False and status['production_execution_enabled'] is False
    assert propose(f,p,data).status_code==read(f,p).status_code==403
    with f[1].connect() as c:
        assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name='candidate_plan_approvals'").fetchone()
    assert submit(f,p,{**data,'approval_id':str(uuid4())}).status_code==403
    assert effects(f)==[0]*5 and states(f,hs)==['HELD']*3
    assert submit(f,p,data).status_code==201  # unchanged default original route


def test_owner_persistent_approval_consumption_atomic_effects_and_cold_read(link_fixture):
    f=link_fixture; p,hs,data,bridge=setup(f)
    assert submit(f,p,data).status_code==409 and effects(f)==[0]*5
    item,x=approved(f,p,data)
    assert item['state']=='APPROVED' and item['current_available'] and x['revision']==2
    assert item['purpose']=='CASE_RESOURCE_DELIVERY' and item['execution_identity']['actor_id']=='fixture-a'
    assert len(item['materials'])==2 and len(item['members'])==3
    key=uuid4().hex; actual={**data,'approval_id':item['id']}
    y=submit(f,p,actual,key); assert y.status_code==201,y.text
    y=y.json(); assert effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3
    assert y['receipt']['plan_approval']['id']==item['id'] and y['independent_check']['status']=='CURRENT'
    assert not y['case_goal_completed'] and not y['formal_release']
    now=read(f,p); assert now.status_code==200,now.text
    assert now.json()['revision']==3 and now.json()['items'][-1]['state']=='CONSUMED'
    assert not now.json()['items'][-1]['current_available']
    fresh=bridge.attach_store(Store(f[0].dsn))
    assert bridge.read(fresh,f[2]['fixture-a'],UUID(p['preparation_id']))['items'][-1]['state']=='CONSUMED'
    assert recover(f,p,key).json()['receipt']==y['receipt']
    assert submit(f,p,actual,key).json()['receipt']==y['receipt']
    assert submit(f,p,actual).status_code==409 and ledger(f,p)['revision']==3


def test_revoke_is_explicit_preserves_original_and_never_confirms_resources(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);item,x=approved(f,p,data)
    original=deepcopy(ledger(f,p)['events'])
    r=decide(f,p,item,x['revision'],'REVOKE'); assert r.status_code==200,r.text
    assert r.json()['items'][-1]['state']=='REVOKED' and not r.json()['items'][-1]['current_available']
    assert ledger(f,p)['events'][:2]==original
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
    assert effects(f)==[0]*5 and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('change',['materials','request','catalog','resource_revision','capacity','hold','plan','p1','run','authority_revision'])
def test_source_change_invalidates_original_approval_without_rebinding_or_effect(link_fixture,change):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    with f[1].connect() as c:
        if change=='materials':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
        elif change=='request':c.execute("UPDATE preparations SET request_intent=jsonb_set(request_intent,'{revision}','99') WHERE id=%s",(p['preparation_id'],))
        elif change=='catalog':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2')")
        elif change=='resource_revision':c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(hs[-1]['resource_id'],))
        elif change=='capacity':c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(hs[-1]['resource_id'],))
        elif change=='hold':c.execute('UPDATE synthetic_resource_holds SET quantity=quantity+1 WHERE id=%s',(hs[-1]['id'],))
        elif change=='plan':c.execute("UPDATE preparations SET service_case_plan=jsonb_set(service_case_plan,'{revision}',to_jsonb((service_case_plan->>'revision')::integer+1)) WHERE id=%s",(p['preparation_id'],))
        elif change=='p1':c.execute("UPDATE preparations SET service_case_plan=jsonb_set(service_case_plan,'{steps,0,invalidated}','true') WHERE id=%s",(p['preparation_id'],))
        elif change=='run':c.execute('UPDATE runs SET revision=revision+1 WHERE id=%s',(p['run_id'],))
        else:c.execute("UPDATE capability_grants SET revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    r=read(f,p); assert r.status_code==200,r.text
    assert not r.json()['items'][-1]['current_available']
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
    assert ledger(f,p)==before and effects(f)==[0]*5


@pytest.mark.parametrize('grant',['READ','EXECUTE','PREPARE','resource_READ','resource_HOLD'])
def test_revoke_and_restore_current_authority_never_revives_old_approval(link_fixture,grant):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    table='capability_grants' if grant in ('READ','EXECUTE') else 'preparation_grants' if grant=='PREPARE' else 'synthetic_resource_grants'
    cap=grant.removeprefix('resource_')
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute('UPDATE '+table+' SET active=false'+(',revision=revision+1' if table=='capability_grants' else '')+' WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==403
    r=read(f,p)
    assert r.status_code==(200 if grant in ('EXECUTE','resource_HOLD') else 403)
    if r.status_code==403: assert 'items' not in r.json() and data['reason'] not in r.text
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute('UPDATE '+table+' SET active=true'+(',revision=revision+1' if table=='capability_grants' else '')+' WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
    assert not read(f,p).json()['items'][-1]['current_available']
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
    assert ledger(f,p)==before and effects(f)==[0]*5


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_other_enterprise_case_and_roles_cannot_approve_read_recover_or_execute(link_fixture,user):
    f=link_fixture;p,hs,data,_=setup(f);item,x=approved(f,p,data)
    assert read(f,p,user).status_code==propose(f,p,data,user=user).status_code==403
    assert decide(f,p,item,x['revision'],user=user).status_code==403
    r=f[3].get(path(p,'/recovery/'+uuid4().hex),headers=headers(f[2],user));assert r.status_code==403
    assert item['id'] not in r.text and data['reason'] not in r.text
    assert submit(f,p,{**data,'approval_id':item['id']},user=user).status_code==403
    assert effects(f)==[0]*5


def test_original_key_cas_replay_changed_body_and_read_only_lost_reply_recovery(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);key=uuid4().hex
    x=propose(f,p,data,key=key);assert x.status_code==201,x.text
    before=ledger(f,p); item=x.json()['items'][-1]
    assert propose(f,p,data,key=key).json()['event']==x.json()['event']
    assert propose(f,p,{**data,'reason':'different'},key=key).status_code==409
    assert propose(f,p,data,revision=0).status_code==409
    r=f[3].get(path(p,'/recovery/'+key),headers=headers(f[2]));assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED' and not r.json()['automatically_replayed']
    assert ledger(f,p)==before and effects(f)==[0]*5
    r=f[3].get(path(p,'/recovery/'+uuid4().hex),headers=headers(f[2]));assert r.json()['status']=='NOT_OBSERVED'
    y=decide(f,p,item,1,key='same-approval');assert y.status_code==200,y.text
    assert decide(f,p,item,1,key='same-approval').json()['event']==y.json()['event']
    assert decide(f,p,item,1,'REVOKE',key='same-approval').status_code==409


@pytest.mark.parametrize('field',['reason','approval_id','valid_until','member_revision'])
def test_approval_cannot_authorize_different_exact_command(link_fixture,field):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);changed={**data,'approval_id':item['id']}
    if field=='reason':changed['reason']='different command'
    elif field=='approval_id':changed['approval_id']=str(uuid4())
    elif field=='valid_until':changed['valid_until']='2030-01-01T00:00:00Z'
    else:changed['members']=[{**m,'expected_revision':m['expected_revision']+1} for m in data['members']]
    assert submit(f,p,changed).status_code==409 and effects(f)==[0]*5 and ledger(f,p)['revision']==2


@pytest.mark.parametrize('fault_table',['synthetic_resource_combination_receipts','resource_case_claims','case_resource_links'])
def test_later_business_failure_rolls_back_approval_and_all_original_effects(link_fixture,fault_table):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    with f[1].connect() as c:
        c.execute("CREATE FUNCTION approval_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic Approval rollback';END$$")
        c.execute('CREATE TRIGGER approval_fault BEFORE INSERT ON '+fault_table+' FOR EACH ROW EXECUTE FUNCTION approval_fault()')
    with pytest.raises(psycopg.Error):delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**{**data,'approval_id':item['id']}))
    assert ledger(f,p)==before and states(f,hs)==['HELD']*3 and effects(f)==[0]*5


def test_concurrent_same_delivery_key_consumes_once_and_different_key_cannot_reuse(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);actual=delivery.Deliver(**{**data,'approval_id':item['id']});key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(lambda _:delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,actual),range(2)))
    assert rows[0]['receipt']==rows[1]['receipt'] and ledger(f,p)['revision']==3 and effects(f)==[1,3,1,1,1]
    assert submit(f,p,actual.model_dump(mode='json')).status_code==409


@pytest.mark.parametrize('damage',['truncate','clear','old_event','revision'])
def test_application_cannot_rewrite_or_clear_immutable_approval_history(link_fixture,damage):
    f=link_fixture;p,hs,data,_=setup(f);approved(f,p,data);original=ledger(f,p);value=deepcopy(original)
    if damage=='truncate':value['events']=value['events'][:1];value['revision']=1
    elif damage=='clear':value=None
    elif damage=='old_event':value['events'][0]['binding']['purpose']='OTHER'
    else:value['revision']=99
    from psycopg.types.json import Jsonb
    with pytest.raises(psycopg.Error):
        with f[0].connect() as c:c.execute('UPDATE preparations SET candidate_plan_approvals=%s WHERE id=%s',(Jsonb(value) if value else None,p['preparation_id']))
    assert ledger(f,p)==original and effects(f)==[0]*5


def test_unissued_or_wrong_database_proof_cannot_install_or_attach_candidate(link_fixture):
    f=link_fixture;p=prepared(f)
    with pytest.raises(Denied):approval.IsolatedPlanApproval(f[1],object(),preparation_ids=[p['preparation_id']],enabled_for_isolated_tests=True)
    bridge=enable(f,p)
    with pytest.raises(Denied):bridge.attach_store(Store(make_conninfo(f[0].dsn,dbname='postgres')))
    with pytest.raises(Denied):approval.IsolatedPlanApproval().attach_store(f[0])


def test_real_final_case_wait_crosses_approval_deadline_rolls_back_consumption_and_effect(link_fixture,monkeypatch):
    f=link_fixture;p=prepared(f);hs,d=bundle(f)
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '2 seconds' WHERE id=ANY(%s)",([UUID(h['id']) for h in hs],))
    data=quoted(f,p,d);enable(f,p);item,_=approved(f,p,data);before=ledger(f,p)
    entered=threading.Event();original=cr._bind_locked
    def signal(*args,**kwargs):entered.set();return original(*args,**kwargs)
    monkeypatch.setattr(cr,'_bind_locked',signal)
    def execute():
        try:return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**{**data,'approval_id':item['id']}))
        except Conflict:return 'EXPIRED'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            c.execute('SELECT id FROM cases WHERE id=%s FOR SHARE',(p['case_id'],))
            future=pool.submit(execute);assert entered.wait(2)
            c.execute('SELECT pg_sleep(GREATEST(0,extract(epoch FROM (%s::timestamptz-clock_timestamp()))+0.1))',(data['valid_until'],))
        assert future.result(timeout=8)=='EXPIRED'
    assert ledger(f,p)==before and effects(f)==[0]*5 and states(f,hs)==['HELD']*3


def test_cross_case_key_and_approval_reuse_denied_without_history_write(link_fixture):
    f=link_fixture;p=prepared(f);other=prepared(f);hs,d=bundle(f);data=quoted(f,p,d);other_data=quoted(f,other,d)
    bridge=approval.IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,
        preparation_ids=[p['preparation_id'],other['preparation_id']],enabled_for_isolated_tests=True);bridge.attach_store(f[0])
    x=propose(f,p,data,key='original-case-key');assert x.status_code==201,x.text
    item=x.json()['items'][-1];assert decide(f,p,item,1).status_code==200
    assert propose(f,other,other_data,key='original-case-key').status_code==409
    assert f[3].get(path(other,'/recovery/original-case-key'),headers=headers(f[2])).status_code==409
    assert submit(f,other,{**other_data,'approval_id':item['id']}).status_code==409
    assert ledger(f,p)['revision']==2 and ledger(f,other) is None and effects(f)==[0]*5


def test_competing_approve_and_revoke_have_one_cas_decision(link_fixture):
    f=link_fixture;p,hs,data,bridge=setup(f);x=propose(f,p,data).json();item=x['items'][-1]
    def execute(action):
        command=approval.Command(action=action,approval_id=item['id'],expected_revision=1,
            expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC competing '+action)
        try:return bridge.command(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,command)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(execute,['APPROVE','REVOKE']))
    assert rows.count('CONFLICT')==1 and ledger(f,p)['revision']==2 and effects(f)==[0]*5


def test_competing_consume_and_revoke_never_partially_commit(link_fixture):
    f=link_fixture;p,hs,data,bridge=setup(f);item,_=approved(f,p,data)
    def execute(action):
        try:
            if action=='DELIVER':return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**{**data,'approval_id':item['id']}))
            return bridge.command(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,
                approval.Command(action='REVOKE',approval_id=item['id'],expected_revision=2,expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC concurrent revoke'))
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(execute,['DELIVER','REVOKE']))
    assert rows.count('CONFLICT')==1 and ledger(f,p)['revision']==3
    state=read(f,p).json()['items'][-1]['state']
    assert (state,effects(f),states(f,hs)) in [('CONSUMED',[1,3,1,1,1],['CONFIRMED']*3),('REVOKED',[0]*5,['HELD']*3)]


def test_eight_objects_bound_history_and_all_explicit_revocations_preserved(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f)
    for i in range(8):
        x=propose(f,p,data,revision=i*2);assert x.status_code==201,x.text
        y=decide(f,p,x.json()['items'][-1],i*2+1,'REVOKE');assert y.status_code==200,y.text
    original=ledger(f,p);assert original['revision']==16
    assert propose(f,p,data,revision=16).status_code==409 and ledger(f,p)==original
    assert len(read(f,p).json()['items'])==8 and effects(f)==[0]*5


@pytest.mark.parametrize('damage',['event_hash','owner','purpose','missing_approve','malformed_last_event'])
def test_owner_faulted_ledger_is_refused_and_never_consumes(link_fixture,damage):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);value=ledger(f,p)
    if damage=='event_hash':value['events'][0]['sha256']='0'*64
    elif damage=='owner':value['events'][0]['actor_id']='fixture-b'
    elif damage=='purpose':value['events'][0]['binding']['purpose']='OTHER'
    elif damage=='missing_approve':value['events']=value['events'][:1];value['revision']=1
    else:value['events'][-1]=None
    from psycopg.types.json import Jsonb
    with f[1].connect() as c:
        c.execute('ALTER TABLE preparations DISABLE TRIGGER candidate_plan_approval_prefix')
        c.execute('UPDATE preparations SET candidate_plan_approvals=%s WHERE id=%s',(Jsonb(value),p['preparation_id']))
        c.execute('ALTER TABLE preparations ENABLE TRIGGER candidate_plan_approval_prefix')
    # The separately retained original head also rejects a valid prefix.
    assert read(f,p).status_code==409
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409 and effects(f)==[0]*5


@pytest.mark.parametrize('table',['catalog','resource','run'])
def test_restored_original_source_values_do_not_revive_old_approval(link_fixture,table):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    with f[1].connect() as c:
        if table=='catalog':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2')")
        elif table=='resource':c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(hs[-1]['resource_id'],))
        else:c.execute('UPDATE runs SET revision=revision+1 WHERE id=%s',(p['run_id'],))
    with f[1].connect() as c:
        if table=='catalog':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','1')")
        elif table=='resource':c.execute('UPDATE synthetic_resources SET revision=revision-1 WHERE id=%s',(hs[-1]['resource_id'],))
        else:c.execute('UPDATE runs SET revision=revision-1 WHERE id=%s',(p['run_id'],))
    assert not read(f,p).json()['items'][-1]['current_available']
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409 and effects(f)==[0]*5 and ledger(f,p)==before


def test_original_p2_and_goal_sources_reject_missing_consumption_proof(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data)
    r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code==201,r.text
    from test_service_case_steps import verified,read as plan_read
    verified(f,p,'P2')
    assert plan_read(f,p).status_code==200
    goals='/api/preparations/'+p['preparation_id']+'/goal-results'
    assert f[3].get(goals,headers=headers(f[2])).status_code==200
    from psycopg.types.json import Jsonb
    value=ledger(f,p);value['events']=value['events'][:2];value['revision']=2
    with f[1].connect() as c:
        c.execute('ALTER TABLE preparations DISABLE TRIGGER candidate_plan_approval_prefix')
        c.execute('UPDATE preparations SET candidate_plan_approvals=%s WHERE id=%s',(Jsonb(value),p['preparation_id']))
        c.execute('ALTER TABLE preparations ENABLE TRIGGER candidate_plan_approval_prefix')
    assert plan_read(f,p).status_code==409
    assert f[3].get(goals,headers=headers(f[2])).status_code==409
    assert effects(f)==[1,3,1,1,1]


@pytest.mark.parametrize('target',['reviewer_principal','reviewer_READ'])
def test_original_reviewer_restored_authority_cannot_revive_owner_approval(link_fixture,target):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    with f[1].connect() as c:
        reviewer=c.execute('SELECT reviewer_id FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['reviewer_id']
    for active in (False,True):
        with f[1].connect() as c:
            f[1].lock_principal(c,reviewer,exclusive=True)
            if target=='reviewer_principal':c.execute('UPDATE principals SET active=%s WHERE id=%s',(active,reviewer))
            else:c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id=%s AND capability='READ'",(active,reviewer))
    assert not read(f,p).json()['items'][-1]['current_available']
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
    assert ledger(f,p)==before and effects(f)==[0]*5


@pytest.mark.parametrize('clear_journal',[False,True])
def test_immutable_case_link_refuses_stripped_approval_receipt_even_without_journal(link_fixture,clear_journal):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);key=uuid4().hex
    r=submit(f,p,{**data,'approval_id':item['id']},key);assert r.status_code==201,r.text
    assert r.json()['link']['snapshot']['plan_approval']==r.json()['receipt']['plan_approval']
    from test_service_case_steps import verified,read as plan_read
    verified(f,p,'P2');assert plan_read(f,p).status_code==200
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_combination_receipts SET payload=payload-'plan_approval' WHERE request_key=%s",(key,))
        if clear_journal:
            c.execute('ALTER TABLE preparations DISABLE TRIGGER candidate_plan_approval_prefix')
            c.execute('UPDATE preparations SET candidate_plan_approvals=NULL,candidate_plan_approval_head=NULL WHERE id=%s',(p['preparation_id'],))
            c.execute('ALTER TABLE preparations ENABLE TRIGGER candidate_plan_approval_prefix')
    assert recover(f,p,key).status_code==409
    assert plan_read(f,p).status_code==409
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2])).status_code==409
    assert effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3
