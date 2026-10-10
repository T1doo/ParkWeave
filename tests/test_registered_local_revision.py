"""Independent expected sets exercised through real HTTP and isolated PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import controlled_plans as cp, registered_dependencies as deps
from parkweave import resource_holds as rh
from parkweave.api import create_app
from test_service_case_steps import (link_fixture,receipt_fixture,preparation_fixture,read,step,
    verified,adopt,adopt_body,command,business,GOALS,resource_link)
from test_service_plan_manual_lock import lock,stored
from test_case_goal_results import complete,get,snapshot
from test_executor_receipts import act as receipt_act
from test_preparation import headers
from test_service_plan_recovery import recover
from test_new_enterprise_local_chain import actual_http


@pytest.fixture
def http_f(link_fixture):
    f=link_fixture
    with actual_http(create_app(f[0])) as (client,requests):
        yield (*f[:3],client)
        assert requests and all(r['path'].startswith('/api/') for r in requests)


def add_resource(f,user='fixture-a'):
    id=uuid4()
    with f[1].connect() as c:
        c.execute('INSERT INTO synthetic_resources(id,park_id,name,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source) SELECT %s,park_id,%s,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source FROM synthetic_resources WHERE id=%s',
                  (id,'SYNTHETIC PRIVATE_OPTIONAL_RESOURCE',rh.RESOURCE_ID))
        c.execute('INSERT INTO synthetic_resource_grants(principal_id,resource_id,park_id,org_id,capability,active) SELECT principal_id,%s,park_id,org_id,capability,active FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=%s',(id,user,rh.RESOURCE_ID))
    return id


def patch_body(f,p):
    x=read(f,p).json();body=adopt_body(f,{**p,'revision':x['preparation_revision']})
    return {**body,'expected_plan_revision':x['revision'],'local_revision':True,'reason':'SYNTHETIC PRIVATE_EXPLICIT_LOCAL_PATCH'}


def patch(f,p,body=None,key=None,user='fixture-a'):
    return adopt(f,p,body or patch_body(f,p),key,user)


def expected_impact(x,changed,preserved):
    # Literal oracle sets come from the frozen contract, not from the planner.
    expected={step(x,a)['id'] for a in changed};actual=set(x['change_impact']['affected'])
    assert expected-actual==set(),('missed_invalidation',expected-actual)
    assert actual-expected==set(),('wrong_invalidation',actual-expected)
    assert set(x['change_impact']['preserved'])=={step(x,a)['id'] for a in preserved}


@pytest.mark.parametrize('change',['insert','remove','rule','capacity'])
def test_resource_collection_local_revision_preserves_upstream_and_all_history(http_f,change):
    f=http_f;p,g,d,s=complete(f,local=True)
    optional=add_resource(f) if change!='insert' else None
    if optional:
        assert patch(f,p).status_code==201
        for a in ('P2','P3','P4'):verified(f,p,a)
        verified(f,p,'P5')
    old=stored(f,p);history=deepcopy(old['events']);before=business(f)
    if change=='insert':add_resource(f)
    else:
        with f[1].connect() as c:
            if change=='remove':c.execute('DELETE FROM synthetic_resource_grants WHERE resource_id=%s AND principal_id=%s',(optional,'fixture-a'))
            elif change=='rule':c.execute('UPDATE synthetic_resources SET revision=revision+1,buffer_seconds=buffer_seconds+1 WHERE id=%s',(optional,))
            else:c.execute('UPDATE synthetic_resources SET revision=revision+1,capacity=capacity+1 WHERE id=%s',(optional,))
    x=read(f,p).json();expected_impact(x,('P2','P3','P4','P5'),('P1',));assert x['local_revision_required'] and x['can_adopt']
    assert command(f,p,'P2').status_code==409
    r=patch(f,p);assert r.status_code==201,r.text;now=stored(f,p);assert now['id']==old['id'] and [z['id'] for z in now['steps']]==[z['id'] for z in old['steps']]
    assert now['events'][:-1]==history and now['steps'][0]==old['steps'][0] and now['history']==old['history'] and business(f)==before
    assert all(now['steps'][i]['verified_sources']==old['steps'][i]['verified_sources'] for i in range(5))
    assert r.json()['state']!='VERIFIED' and get(f,p).json()['state']=='UNVERIFIED'
    for a in ('P2','P3','P4'):verified(f,p,a)
    verified(f,p,'P5')
    x=get(f,p).json();assert x['state']=='LOCAL_OUTPUTS_VERIFIED' and not x['case_goal_completed']
    assert stored(f,p)['events'][:len(history)]==history and stored(f,p)['steps'][0]==old['steps'][0]


@pytest.mark.parametrize('change',['new','remove'])
def test_existing_run_access_collection_affects_p3_and_keeps_explicit_assignment(http_f,change):
    f=http_f;p,g,d,s=complete(f,local=True)
    if change=='remove':
        with f[1].connect() as c:c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(p['run_id'],'unassigned','park-a','org-a'))
        assert patch(f,p).status_code==201
        for a in ('P3','P4'):verified(f,p,a)
        verified(f,p,'P5')
    old=stored(f,p)
    with f[1].connect() as c:
        if change=='new':
            c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(p['run_id'],'unassigned','park-a','org-a'))
        else:c.execute('UPDATE run_assignments SET active=false WHERE run_id=%s AND principal_id=%s',(p['run_id'],'unassigned'))
    x=read(f,p).json()
    expected_impact(x,('P3','P4','P5'),('P1','P2'));before=business(f);r=patch(f,p);assert r.status_code==201,r.text
    assert business(f)==before and stored(f,p)['steps'][:2]==old['steps'][:2] and stored(f,p)['events'][:-1]==old['events']
    assert step(r.json(),'P3')['actual_business_state']=='ACCEPTED'
    for a in ('P3','P4'):verified(f,p,a)
    verified(f,p,'P5')
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'


def test_actual_new_receipt_output_rechecks_only_p4_downstream_and_retains_old_outputs(http_f):
    f=http_f;p,g,d,s=complete(f,local=True);old=stored(f,p);old_output=get(f,p).json()['results'][3]['actual_output']
    s=receipt_act(f,s,'REOPEN').json();x=read(f,p).json();expected_impact(x,('P4','P5'),('P1','P2','P3'))
    assert not x['local_revision_required'] and command(f,p,'P4').status_code==409
    s=receipt_act(f,s,'SUBMIT',text='SYNTHETIC PRIVATE_NEW_ACTUAL_OUTPUT').json();assert command(f,p,'P4').status_code==409
    s=receipt_act(f,s,'ACKNOWLEDGE').json();verified(f,p,'P4')
    from test_case_lifecycle import read as lr,act as la
    assert la(f,p,lr(f,p).json(),'REVALIDATE').status_code==200;verified(f,p,'P5')
    new=get(f,p).json();output=new['results'][3]['actual_output'];assert output['receipt_id']!=old_output['receipt_id'] and output['receipt_version']==old_output['receipt_version']+1
    assert new['state']=='LOCAL_OUTPUTS_VERIFIED' and stored(f,p)['steps'][:3]==old['steps'][:3] and stored(f,p)['events'][:len(old['events'])]==old['events']
    assert old['steps'][3]['verified_sources']['receipt_id']==old_output['receipt_id'] and 'PRIVATE_NEW_ACTUAL_OUTPUT' not in str(new)


def test_selected_resource_capacity_needs_actual_new_association_then_explicit_verification(http_f):
    f=http_f;p,g,d,s=complete(f);old=stored(f,p)
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1,revision=revision+1 WHERE id=%s',(rh.RESOURCE_ID,))
    x=read(f,p).json();expected_impact(x,('P2','P3','P4'),('P1',));assert patch(f,p).status_code==201
    assert command(f,p,'P2').status_code==409
    from test_resource_holds import body
    from test_resource_combinations import hold,write
    from parkweave.resource_combinations import SECOND_RESOURCE_ID
    holds=[]
    for id in (rh.RESOURCE_ID,SECOND_RESOURCE_ID):
        with f[1].connect() as c:revision=c.execute('SELECT revision FROM synthetic_resources WHERE id=%s',(id,)).fetchone()['revision']
        r=hold(f,id,{**body(f),'expected_revision':revision});assert r.status_code==201,r.text;holds.append(r.json()['hold'])
    r=write(f,{'members':[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds]});assert r.status_code==201,r.text;new_group=r.json()['combination']
    r=resource_link(f,p,new_group,revision=1);assert r.status_code==201,r.text;verified(f,p,'P2')
    x=get(f,p).json();assert x['results'][1]['actual_output']['combination_id']==new_group['id']!=g['id']
    assert stored(f,p)['steps'][0]==old['steps'][0] and stored(f,p)['events'][:len(old['events'])]==old['events']
    with f[1].connect() as c:assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(g['id'],)).fetchone()['state']=='CONFIRMED'


def test_unaffected_lock_survives_patch_affected_lock_waits_for_explicit_unlock(http_f):
    f=http_f;p,g,d,s=complete(f);assert lock(f,p,'P1').status_code==200;assert lock(f,p,'P3').status_code==200;old=stored(f,p);add_resource(f)
    x=read(f,p).json();assert step(x,'P1')['state']=='VERIFIED' and step(x,'P3')['state']=='LOCK_CONFLICT' and not x['can_adopt']
    assert patch(f,p).status_code==409 and stored(f,p)['events']==old['events']
    assert command(f,p,'P3','UNLOCK').status_code==200;r=patch(f,p);assert r.status_code==201,r.text
    assert stored(f,p)['steps'][0]==old['steps'][0] and stored(f,p)['steps'][2]['verified_sources']==old['steps'][2]['verified_sources']
    assert stored(f,p)['steps'][0]['manual_lock']==old['steps'][0]['manual_lock'] and step(r.json(),'P1')['state']=='VERIFIED'


@pytest.mark.parametrize('unknown',['legacy','declaration','saved-overflow','overflow'])
def test_unknown_expands_case_recheck_without_rewriting_body_or_history(http_f,monkeypatch,unknown):
    f=http_f;p,g,d,s=complete(f)
    if unknown=='overflow':monkeypatch.setattr(deps,'COLLECTION_LIMIT',1)
    else:
        with f[1].connect() as c:
            plan=stored(f,p)
            if unknown=='legacy':
                plan.pop('dependency_manifest');plan['events'][0].pop('dependencies')
                for st in plan['steps']:
                    for key in ('resource_collection','run_access_collection'):st['verified_sources'].pop(key,None)
                    st['verified_sha256']=cp._hash(st['verified_sources'])
                for e in plan['events']:
                    if e['action']=='VERIFY':
                        st=next(z for z in plan['steps'] if z['id']==e['step_id']);e['sources']=deepcopy(st['verified_sources']);e['source_sha256']=st['verified_sha256']
                        e['fingerprint']=cp._hash(dict(preparation_id=p['preparation_id'],action='VERIFY',step_id=e['step_id'],expected_revision=e['revision']-1,expected_source_sha256=e['source_sha256'],reason=e['reason']))
            else:
                if unknown=='saved-overflow':plan['dependency_manifest']['collections']['resources'].update(known=False,count=257)
                else:plan['dependency_manifest']['declarations']['P2'].append('UNKNOWN_DYNAMIC_SOURCE')
                value=plan['dependency_manifest'];value['sha256']=cp._hash({k:v for k,v in value.items() if k!='sha256'});plan['events'][0]['dependencies']=deepcopy(value)
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=stored(f,p);x=read(f,p).json();expected_impact(x,('P1','P2','P3','P4'),());assert x['change_impact']['unknown_scope']=='THIS_CASE'
    assert stored(f,p)['events']==before['events'] and [z['contract'] for z in stored(f,p)['steps']]==[z['contract'] for z in before['steps']]
    if unknown=='overflow':assert not x['can_adopt'] and patch(f,p).status_code==409;return
    assert recover(f,p,before['events'][0]['request_key']).status_code==200
    r=patch(f,p);assert r.status_code==201,r.text;assert stored(f,p)['events'][:-1]==before['events']
    assert [z['id'] for z in stored(f,p)['steps']]==[z['id'] for z in before['steps']] and command(f,p,'P4').status_code==409
    for a in ('P1','P2','P3','P4'):verified(f,p,a)
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_adopt_cas_duplicate_and_lost_response_recover_read_only(http_f,same_key):
    f=http_f;p,g,d,s=complete(f);add_resource(f);body=patch_body(f,p);key=uuid4().hex;old=stored(f,p);before=business(f)
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:patch(f,p,body,key if same_key else uuid4().hex),range(2)))
    assert sorted(r.status_code for r in rs)==([201,201] if same_key else [201,409]);now=stored(f,p);assert now['revision']==old['revision']+1 and now['events'][:-1]==old['events'] and business(f)==before
    event=now['events'][-1];before=snapshot(f);r=recover(f,p,event['request_key']);assert r.status_code==200,r.text
    assert r.json()['event']['expected_revision']==old['revision'] and r.json()['event']['previous_plan_id']==old['id'] and r.json()['event']['plan_id']==old['id']
    assert snapshot(f)==before and patch(f,p,body,event['request_key']).json()['event']==event
    assert patch(f,p,{**body,'reason':'SYNTHETIC changed fingerprint'},event['request_key']).status_code==409


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_local_adoption_has_no_new_actor_or_cross_enterprise_access(http_f,user):
    f=http_f;p,g,d,s=complete(f);add_resource(f);body=patch_body(f,p);before=snapshot(f);r=patch(f,p,body,user=user)
    assert r.status_code==403 and 'PRIVATE_EXPLICIT_LOCAL_PATCH' not in r.text and snapshot(f)==before


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE'])
def test_revocation_precedes_original_patch_replay_and_recovery(http_f,cap):
    f=http_f;p,g,d,s=complete(f);add_resource(f);body=patch_body(f,p);key=uuid4().hex;assert patch(f,p,body,key).status_code==201
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);table='preparation_grants' if cap=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(f);assert patch(f,p,body,key).status_code==403 and recover(f,p,key).status_code==403 and snapshot(f)==before


def test_unrelated_owner_resource_and_other_run_do_not_invalidate_plan(http_f):
    f=http_f;p,g,d,s=complete(f);old=stored(f,p);add_resource(f,'fixture-b');before=snapshot(f);x=read(f,p).json()
    assert x['state']=='VERIFIED' and not x['local_revision_required'] and stored(f,p)==old and snapshot(f)==before


@pytest.mark.parametrize('damage',['manifest','previous','request','partition','event-basis','valid-partition','event-revision','plan-revision','event-id','plan-id','event-key','adopt-actor'])
def test_damaged_dependency_journal_is_rejected_without_observation_writes(http_f,damage):
    f=http_f;p,g,d,s=complete(f);add_resource(f);assert patch(f,p).status_code==201;plan=stored(f,p)
    if damage=='manifest':plan['dependency_manifest']['sha256']='0'*64
    elif damage=='previous':plan['events'][-1]['local_revision']['previous_sha256']='0'*64
    elif damage=='request':plan['events'][-1]['local_revision']['request']['reason']='SYNTHETIC forged'
    elif damage=='partition':plan['events'][-1]['local_revision']['affected']=[str(uuid4())]
    elif damage=='valid-partition':
        part=plan['events'][-1]['local_revision'];p1=plan['steps'][0]['id'];p2=plan['steps'][1]['id']
        part['affected']=[p1 if x==p2 else x for x in part['affected']];part['preserved']=[p2 if x==p1 else x for x in part['preserved']]
    elif damage=='event-revision':plan['events'][-1]['revision']+=7
    elif damage=='plan-revision':plan['revision']=True
    elif damage=='event-id':plan['events'][-1]['id']=plan['events'][0]['id']
    elif damage=='plan-id':plan['events'][-1]['plan_id']=str(uuid4())
    elif damage=='event-key':plan['events'][-1]['request_key']=plan['events'][0]['request_key']
    elif damage=='adopt-actor':plan['events'][0]['actor_id']='prep-specialist-fixture-a'
    else:plan['events'][-1]['dependencies']['collections']['resources']['sha256']='0'*64
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=snapshot(f);assert read(f,p).status_code==409 and recover(f,p).status_code==409 and get(f,p).status_code==409 and snapshot(f)==before


def test_declared_branch_closure_does_not_invalidate_unrelated_numeric_step():
    steps=[dict(adapter_id='P1',depends_on=[]),dict(adapter_id='P2',depends_on=['P1']),dict(adapter_id='P3',depends_on=['P1']),dict(adapter_id='P4',depends_on=['P2'])]
    assert deps.closure(steps,{'P2'})=={'P2','P4'}


def test_saved_local_adoption_stays_readable_when_current_declaration_version_changes(http_f,monkeypatch):
    f=http_f;p,g,d,s=complete(f);add_resource(f);key=uuid4().hex
    assert patch(f,p,key=key).status_code==201
    for adapter in ('P2','P3','P4'):verified(f,p,adapter)
    assert read(f,p).json()['state']=='VERIFIED' and recover(f,p,key).json()['status']=='COMMITTED'
    before=stored(f,p);old_business=business(f)
    # Technical future-version compatibility only: no source/registry/business migration.
    monkeypatch.setattr(deps,'VERSION',2)
    r=read(f,p);assert r.status_code==200,r.text;x=r.json()
    expected_impact(x,('P1','P2','P3','P4'),());assert x['change_impact']['unknown_scope']=='THIS_CASE'
    rc=recover(f,p,key);assert rc.status_code==200 and rc.json()['status']=='COMMITTED'
    observed=stored(f,p);assert observed['events']==before['events'] and observed['history']==before['history']
    for old,new in zip(before['steps'],observed['steps']):
        assert {k:v for k,v in old.items() if k!='invalidated'}=={k:v for k,v in new.items() if k!='invalidated'}
    assert business(f)==old_business
    adopted=patch(f,p);assert adopted.status_code==201,adopted.text
    now=stored(f,p);assert now['dependency_manifest']['version']==2 and now['events'][:-1]==before['events']
    assert set(now['events'][-1]['local_revision']['affected'])=={z['id'] for z in before['steps']} and not now['events'][-1]['local_revision']['preserved']
    assert command(f,p,'P4').status_code==409
    for adapter in ('P1','P2','P3','P4'):verified(f,p,adapter)
    assert read(f,p).json()['state']=='VERIFIED' and business(f)==old_business
