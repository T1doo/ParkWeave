"""Independent expected update/preserve and existing consumer compatibility oracles."""
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from test_service_plan_manual_lock import (link_fixture,receipt_fixture,preparation_fixture,
    start,lock,stored,command,read,step,verified,setup,adopt,adopt_body,accepted,
    GOALS,save,snapshot,preparation_act,business)
from test_preparation import headers
from test_service_plan_recovery import recover
from test_executor_receipts import act as receipt_act
from test_case_lifecycle import read as lifecycle_read,act as lifecycle_act

def goal_read(f,p):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))

@pytest.mark.parametrize('phase',['locked','unlocked'])
def test_original_goal_output_read_remains_available_after_owner_lock_events(link_fixture,phase):
    f=link_fixture;p=start(f);initial=goal_read(f,p);assert initial.status_code==200
    assert initial.json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert lock(f,p).status_code==200
    if phase=='unlocked':assert command(f,p,'P1','UNLOCK').status_code==200
    before=snapshot(f);r=goal_read(f,p)
    assert r.status_code==200, 'existing goal-results rejected a legitimate '+phase+' plan'
    assert r.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and snapshot(f)==before

def complete(f):
    p=setup(f,GOALS[4]);assert adopt(f,p).status_code==201
    _,d=accepted(f,p);verified(f,p,'P3')
    r=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    r=receipt_act(f,r,'SUBMIT').json();r=receipt_act(f,r,'ACKNOWLEDGE').json();verified(f,p,'P4')
    local=lifecycle_read(f,p).json();assert lifecycle_act(f,p,local,'REVALIDATE').status_code==200
    verified(f,p,'P5');return p,r

def test_independent_p4_update_set_and_p1_p3_preserve_set_with_two_locks(link_fixture):
    f=link_fixture;p,r=complete(f)
    assert lock(f,p,'P4').status_code==200 and lock(f,p,'P5').status_code==200
    old=stored(f,p);expected_preserved=[s['id'] for s in old['steps'][:3]];expected_affected=[s['id'] for s in old['steps'][3:]]
    assert receipt_act(f,r,'REOPEN').status_code==200
    before=snapshot(f);x=recover(f,p,old['events'][-1]['request_key']);assert x.status_code==200 and snapshot(f)==before
    assert [s['state'] for s in x.json()['current']['steps']]==['VERIFIED','VERIFIED','VERIFIED','LOCK_CONFLICT','LOCK_CONFLICT']
    x=read(f,p).json();now=stored(f,p)
    assert x['change_impact']['preserved']==expected_preserved and x['change_impact']['affected']==expected_affected
    assert now['steps'][:3]==old['steps'][:3] and now['events']==old['events']
    for index in (3,4):
        for field in ('id','coordination_state','verified_sources','verified_sha256','manual_lock'):
            assert now['steps'][index][field]==old['steps'][index][field]
        assert now['steps'][index]['invalidated']
    assert command(f,p,'P5','UNLOCK').status_code==200
    assert step(read(f,p).json(),'P5')['state']=='BLOCKED'
    assert command(f,p,'P4','UNLOCK').status_code==200
    assert step(read(f,p).json(),'P4')['state']=='NEEDS_RECHECK' and command(f,p,'P5').status_code==409

def test_old_lock_key_after_unlock_and_new_adoption_never_relocks_current_plan(link_fixture):
    f=link_fixture;p=start(f);row=read(f,p).json();key=uuid4().hex
    r=lock(f,p,row=row,key=key);assert r.status_code==200;event=r.json()['event']
    assert command(f,p,'P1','UNLOCK').status_code==200
    assert save(f,p,goals=[GOALS[1]],text='SYNTHETIC new request').status_code==200
    current=read(f,p).json();body=adopt_body(f,{**p,'revision':current['preparation_revision']});body['expected_plan_revision']=current['revision']
    assert adopt(f,p,body).status_code==201;before=snapshot(f)
    r=lock(f,p,row=row,key=key);assert r.status_code==200 and r.json()['event']==event and snapshot(f)==before
    assert not any(s.get('manual_lock') for s in stored(f,p)['steps'])
    recovered=recover(f,p,key);assert recovered.status_code==200 and not recovered.json()['event']['current_plan'] and snapshot(f)==before

def test_three_lock_reserved_budget_rejects_fourth_and_allows_all_three_unlocks(link_fixture):
    f=link_fixture;p=setup(f,GOALS[3]);assert adopt(f,p).status_code==201;_,d=accepted(f,p);verified(f,p,'P3')
    r=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    r=receipt_act(f,r,'SUBMIT').json();r=receipt_act(f,r,'ACKNOWLEDGE').json();verified(f,p,'P4')
    for _ in range(26):assert lock(f,p).status_code==200;assert command(f,p,'P1','UNLOCK').status_code==200
    for a in ('P1','P2','P3'):assert lock(f,p,a).status_code==200
    row=read(f,p).json();assert row['revision']==60 and 'LOCK' not in step(row,'P4')['allowed_actions']
    before=snapshot(f);assert lock(f,p,'P4',row=row).status_code==409 and snapshot(f)==before
    assert command(f,p,'P4','BEGIN').status_code==200
    for a in ('P2','P1','P3'):assert command(f,p,a,'UNLOCK').status_code==200
    assert stored(f,p)['revision']==64 and not any(s.get('manual_lock') for s in stored(f,p)['steps'])

@pytest.mark.parametrize('damage',['event-id','plan-id','duplicate-key','coordination-only','revision','step-id'])
def test_damaged_event_history_is_rejected_without_observation_or_recovery_write(link_fixture,damage):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200
    plan=stored(f,p);event=plan['events'][-1]
    if damage=='event-id':event['id']=plan['events'][0]['id']
    elif damage=='plan-id':event['plan_id']=str(uuid4())
    elif damage=='duplicate-key':event['request_key']=plan['events'][0]['request_key']
    elif damage=='coordination-only':event['coordination_only']=False
    elif damage=='revision':event['revision']=2
    else:event['step_id']=str(uuid4())
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=snapshot(f);assert read(f,p).status_code==409 and recover(f,p).status_code==409 and snapshot(f)==before
