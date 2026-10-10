"""Bounded original owner decisions: real PostgreSQL, CAS and source invalidation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import service_case_steps as plans
from test_service_case_steps import (link_fixture,receipt_fixture,preparation_fixture,setup,adopt,
    adopt_body,read,step,command,verified,business,accepted,GOALS,save,resource_link)
from test_preparation import command as preparation_act
from test_service_plan_recovery import recover,snapshot
from test_case_goal_results import get as goal_results


def start(f,goal=GOALS[0]):
    p=setup(f,goal);assert adopt(f,p).status_code==201;verified(f,p,'P1');return p


def lock(f,p,adapter='P1',row=None,**extra):
    row=row or read(f,p).json()
    return command(f,p,adapter,'LOCK',row=row,expected_source_sha256=step(row,adapter)['source_sha256'],**extra)


def stored(f,p):
    with f[1].connect() as c:return c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']


def test_lock_preserves_current_verification_and_business_then_unlock_does_not_reverify(link_fixture):
    f=link_fixture;p=start(f);before=business(f);old=stored(f,p);r=lock(f,p);assert r.status_code==200,r.text
    x=r.json();assert step(x,'P1')['state']=='VERIFIED' and step(x,'P1')['manually_locked'] and step(x,'P1')['allowed_actions']==['UNLOCK']
    saved=stored(f,p);assert saved['events'][:-1]==old['events'] and saved['steps'][0]['verified_sources']==old['steps'][0]['verified_sources'] and business(f)==before
    assert x['change_impact']['affected']==[] and x['change_impact']['preserved']==[step(x,'P1')['id']]
    r=command(f,p,'P1','UNLOCK');assert r.status_code==200 and not step(r.json(),'P1')['manually_locked'];assert step(r.json(),'P1')['state']=='VERIFIED' and business(f)==before
    assert stored(f,p)['events'][-2]['action']=='LOCK' and stored(f,p)['events'][-1]['action']=='UNLOCK'


@pytest.mark.parametrize('action',['BEGIN','REPORT_FAILURE','RETRY','VERIFY','LOCK'])
def test_locked_decision_denies_new_coordination_or_overwrite(link_fixture,action):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200;row=read(f,p).json();before=snapshot(f)
    r=lock(f,p,row=row) if action=='LOCK' else command(f,p,'P1',action,row=row)
    assert r.status_code==409 and snapshot(f)==before


def test_real_material_reopen_conflict_retains_old_sources_and_unlock_requires_explicit_recheck(link_fixture):
    f=link_fixture;p=start(f,GOALS[1]);assert lock(f,p).status_code==200;old=stored(f,p)
    r=preparation_act(f,p,'REOPEN',reason='SYNTHETIC material source update');assert r.status_code==200
    x=read(f,p).json();assert step(x,'P1')['state']=='LOCK_CONFLICT' and step(x,'P2')['state']=='BLOCKED'
    assert x['change_impact']['affected']==[s['id'] for s in x['steps']] and x['change_impact']['preserved']==[]
    assert stored(f,p)['events']==old['events'] and stored(f,p)['steps'][0]['verified_sources']==old['steps'][0]['verified_sources']
    assert command(f,p,'P1').status_code==409
    r=command(f,p,'P1','UNLOCK');assert r.status_code==200 and step(r.json(),'P1')['state']=='NEEDS_RECHECK'
    assert command(f,p,'P1').status_code==409  # unlock did not repair the real material
    p={**p,'revision':r.json()['preparation_revision']};p=preparation_act(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC explicit new review').json()
    p=preparation_act(f,p,'CONFIRM',reason='SYNTHETIC explicit new confirmation').json();verified(f,p,'P1')
    assert stored(f,p)['steps'][0]['verified_sources']!=old['steps'][0]['verified_sources']


def test_receipt_source_change_affects_only_downstream_locked_decision_preserves_upstream(link_fixture):
    from test_executor_receipts import act as receipt_act
    from test_preparation import headers
    f=link_fixture;p=setup(f,GOALS[3]);assert adopt(f,p).status_code==201;_,d=accepted(f,p);verified(f,p,'P3')
    s=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    s=receipt_act(f,s,'SUBMIT').json();s=receipt_act(f,s,'ACKNOWLEDGE').json();verified(f,p,'P4');assert lock(f,p,'P4').status_code==200
    old=stored(f,p);old_view=read(f,p).json();assert receipt_act(f,s,'REOPEN').status_code==200
    x=read(f,p).json();assert step(x,'P4')['state']=='LOCK_CONFLICT'
    expected_preserved=[step(old_view,a)['id'] for a in ('P1','P2','P3')]
    assert x['change_impact']['preserved']==expected_preserved and x['change_impact']['affected']==[step(old_view,'P4')['id']]
    assert stored(f,p)['steps'][:3]==old['steps'][:3] and stored(f,p)['steps'][3]['verified_sources']==old['steps'][3]['verified_sources']
    assert stored(f,p)['events']==old['events']


@pytest.mark.parametrize('change',['request','catalog','registry'])
def test_binding_change_expands_case_recheck_and_blocks_adopt_until_explicit_unlock(link_fixture,monkeypatch,change):
    from parkweave import bounded_planning as bp
    f=link_fixture;p=start(f,GOALS[1]);assert lock(f,p).status_code==200;old=stored(f,p)
    if change=='request':assert save(f,p,goals=[GOALS[0]],text='SYNTHETIC changed request').status_code==200
    elif change=='catalog':
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','999'::jsonb)")
    else:
        registry=deepcopy(bp.REGISTRY);registry[0]['output']+=' SYNTHETIC revision';monkeypatch.setattr(bp,'REGISTRY',registry)
    x=read(f,p).json();assert step(x,'P1')['state']=='LOCK_CONFLICT' and not x['can_adopt'];assert x['change_impact']['unknown_scope']=='THIS_CASE' and x['change_impact']['affected']==[s['id'] for s in x['steps']]
    body=adopt_body(f,{**p,'revision':x['preparation_revision']});body['expected_plan_revision']=x['revision'];assert adopt(f,p,body).status_code==409
    r=command(f,p,'P1','UNLOCK');assert r.status_code==200 and r.json()['can_adopt'];unlocked=stored(f,p)
    body=adopt_body(f,{**p,'revision':r.json()['preparation_revision']});body['expected_plan_revision']=r.json()['revision'];r=adopt(f,p,body);assert r.status_code==201,r.text
    assert r.json()['plan_id']!=old['id'];history=stored(f,p)['history'];assert len(history)==1 and history[0]=={k:v for k,v in unlocked.items() if k!='history'}
    assert history[0]['events'][:len(old['events'])]==old['events'] and history[0]['steps'][0]['verified_sources']==old['steps'][0]['verified_sources']


@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_lock_cas_and_duplicate_fingerprint_have_one_event(link_fixture,same_key):
    f=link_fixture;p=start(f);row=read(f,p).json();key=uuid4().hex;before=business(f)
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:lock(f,p,row=row,key=key if same_key else uuid4().hex),range(2)))
    assert sorted(r.status_code for r in rs)==([200,200] if same_key else [200,409]);assert stored(f,p)['revision']==row['revision']+1 and business(f)==before
    if same_key:
        assert rs[0].json()['event']==rs[1].json()['event'];before=snapshot(f)
        assert lock(f,p,row=row,key=key,reason='SYNTHETIC changed fingerprint').status_code==409 and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_nonowner_and_cross_scope_lock_denied_without_private_contents_or_effect(link_fixture,user,action):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200;row=read(f,p).json();before=snapshot(f)
    r=lock(f,p,row=row,user=user) if action=='LOCK' else command(f,p,'P1','UNLOCK',row=row,user=user)
    assert r.status_code==403 and 'SYNTHETIC PRIVATE_CASE' not in r.text and snapshot(f)==before


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE'])
def test_revocation_precedes_original_lock_replay_and_get_recovery(link_fixture,cap):
    f=link_fixture;p=start(f);row=read(f,p).json();key=uuid4().hex;assert lock(f,p,row=row,key=key).status_code==200
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);table='preparation_grants' if cap=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(f);assert lock(f,p,row=row,key=key).status_code==403 and recover(f,p,key).status_code==403 and snapshot(f)==before


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_original_lock_unknown_recovery_is_read_only_and_other_case_key_rejected(link_fixture,action):
    f=link_fixture;p=start(f);row=read(f,p).json();key=uuid4().hex
    if action=='UNLOCK':assert lock(f,p).status_code==200;row=read(f,p).json()
    r=lock(f,p,row=row,key=key) if action=='LOCK' else command(f,p,'P1',action,row=row,key=key);assert r.status_code==200
    before=snapshot(f)
    for _ in range(2):
        x=recover(f,p,key);assert x.status_code==200,x.text;assert x.json()['event']['action']==action and x.json()['event']['id']==r.json()['event']['id'] and snapshot(f)==before
        assert x.json()['current']['steps'][0]['verified_sources'] is None and x.json()['current']['event'] is None
    p2=start(f);before=snapshot(f);assert recover(f,p2,key).status_code==409 and snapshot(f)==before


@pytest.mark.parametrize('damage',['missing-lock','wrong-owner','wrong-source','overwritten-decision','event-hash'])
def test_damaged_lock_cannot_downgrade_to_unlocked_or_replace_original_decision(link_fixture,damage):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200
    with f[1].connect() as c:
        row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'];s=row['steps'][0]
        if damage=='missing-lock':s.pop('manual_lock')
        elif damage=='wrong-owner':s['manual_lock']['actor_id']='prep-specialist-fixture-a'
        elif damage=='wrong-source':s['manual_lock']['source_sha256']='0'*64
        elif damage=='overwritten-decision':s['verified_sources']={'SYNTHETIC':'forged'}
        else:row['events'][-1]['fingerprint']='0'*64
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(row),p['preparation_id']))
    before=snapshot(f);assert read(f,p).status_code==409 and recover(f,p).status_code==409 and goal_results(f,p).status_code==409 and snapshot(f)==before


def test_lock_rejects_stale_hash_and_foreign_step_without_side_effect(link_fixture):
    f=link_fixture;p=start(f);row=read(f,p).json();before=snapshot(f)
    assert command(f,p,'P1','LOCK',row=row,expected_source_sha256='0'*64).status_code==409
    assert command(f,p,'P1','LOCK',row=row,step_id=str(uuid4()),expected_source_sha256=step(row,'P1')['source_sha256']).status_code==409
    assert snapshot(f)==before


def test_real_64_event_boundary_always_reserves_last_unlock_and_retains_all_history(link_fixture):
    f=link_fixture;p=start(f)
    for _ in range(30):
        assert lock(f,p).status_code==200;assert command(f,p,'P1','UNLOCK').status_code==200
    row=read(f,p).json();assert row['revision']==62 and 'LOCK' in step(row,'P1')['allowed_actions']
    assert lock(f,p).status_code==200;row=read(f,p).json();assert row['revision']==63 and step(row,'P1')['allowed_actions']==['UNLOCK']
    before=snapshot(f);assert command(f,p,'P1','BEGIN',row=row).status_code==409 and snapshot(f)==before
    assert command(f,p,'P1','UNLOCK',row=row).status_code==200;row=read(f,p).json();assert row['revision']==64 and step(row,'P1')['allowed_actions']==[] and not step(row,'P1')['manually_locked']
    events=stored(f,p)['events'];assert len(events)==64 and [e['revision'] for e in events]==list(range(1,65))
    before=snapshot(f);assert recover(f,p,events[-1]['request_key']).status_code==200 and snapshot(f)==before


def test_two_real_locks_reserve_two_unlocks_against_other_step_coordination(link_fixture):
    f=link_fixture;p=setup(f,GOALS[2]);assert adopt(f,p).status_code==201;accepted(f,p)
    for _ in range(27):assert lock(f,p).status_code==200;assert command(f,p,'P1','UNLOCK').status_code==200
    assert lock(f,p).status_code==200 and lock(f,p,'P2').status_code==200
    for action in ('BEGIN','REPORT_FAILURE','RETRY'):assert command(f,p,'P3',action,user='executor-a').status_code==200
    row=read(f,p).json();assert row['revision']==62 and step(row,'P3')['allowed_actions']==[]
    before=snapshot(f);assert command(f,p,'P3','BEGIN',row=row,user='executor-a').status_code==409 and snapshot(f)==before
    assert command(f,p,'P2','UNLOCK').status_code==200 and command(f,p,'P1','UNLOCK').status_code==200
    row=read(f,p).json();assert row['revision']==64 and not any(s['manually_locked'] for s in row['steps'])


@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_unlock_has_one_event_and_keeps_original_locked_snapshot(link_fixture,same_key):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200;old=stored(f,p);row=read(f,p).json();key=uuid4().hex
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:command(f,p,'P1','UNLOCK',row=row,key=key if same_key else uuid4().hex),range(2)))
    assert sorted(r.status_code for r in rs)==([200,200] if same_key else [200,409]);now=stored(f,p)
    assert now['revision']==old['revision']+1 and now['events'][:-1]==old['events'] and now['steps'][0]['verified_sources']==old['steps'][0]['verified_sources']


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_legal_lock_events_keep_original_goal_result_current_without_becoming_new_verification(link_fixture,action):
    f=link_fixture;p=start(f);original=goal_results(f,p).json();assert lock(f,p).status_code==200
    if action=='UNLOCK':assert command(f,p,'P1','UNLOCK').status_code==200
    before=snapshot(f);r=goal_results(f,p);assert r.status_code==200,r.text;x=r.json();assert x['state']=='LOCAL_OUTPUTS_VERIFIED' and snapshot(f)==before
    assert x['results'][0]['historical_verification']==original['results'][0]['historical_verification'] and x['results'][0]['actual_output']==original['results'][0]['actual_output']
    assert x['plan_revision']>original['plan_revision'] and not x['automatically_verified'] and not x['case_goal_completed']


def test_goal_get_after_real_source_change_is_read_only_conflict_without_downgrading_lock(link_fixture):
    f=link_fixture;p=start(f);original=goal_results(f,p).json();assert lock(f,p).status_code==200
    assert preparation_act(f,p,'REOPEN',reason='SYNTHETIC changed actual source').status_code==200
    before=snapshot(f);r=goal_results(f,p);assert r.status_code==200,r.text;x=r.json();assert snapshot(f)==before
    row=x['results'][0];assert row['state']=='NEEDS_RECHECK' and row['next_action']=='READ_ORIGINAL_STEP_AND_UNLOCK' and 'MANUAL_LOCK_CONFLICT_REQUIRES_EXPLICIT_UNLOCK' in row['issues']
    assert row['historical_verification']['id']==original['results'][0]['historical_verification']['id'] and not row['historical_verification']['current'] and row['actual_output'] is None
    assert stored(f,p)['steps'][0]['manual_lock'] and command(f,p,'P1').status_code==409
    assert command(f,p,'P1','UNLOCK').status_code==200;before=snapshot(f);r=goal_results(f,p);assert r.status_code==200 and r.json()['state']=='UNVERIFIED' and snapshot(f)==before


def test_goal_results_after_unlock_and_new_adoption_keep_original_plan_history(link_fixture):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200;old=stored(f,p)
    assert save(f,p,goals=[GOALS[0],GOALS[1]],text='SYNTHETIC explicit new request').status_code==200
    before=snapshot(f);r=goal_results(f,p);assert r.status_code==200 and r.json()['results'][0]['state']=='NEEDS_NEW_PLAN' and snapshot(f)==before
    assert command(f,p,'P1','UNLOCK').status_code==200;x=read(f,p).json();body=adopt_body(f,{**p,'revision':x['preparation_revision']});body['expected_plan_revision']=x['revision'];assert adopt(f,p,body).status_code==201
    before=snapshot(f);r=goal_results(f,p);assert r.status_code==200 and r.json()['historical_plans'][0]['id']==old['id'] and r.json()['state']=='UNVERIFIED' and snapshot(f)==before


def test_distinct_original_actors_same_literal_key_do_not_break_locked_goal_proof(link_fixture):
    f=link_fixture;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201;key=uuid4().hex
    assert command(f,p,'P1','BEGIN',user='prep-specialist-fixture-a',key=key).status_code==200;verified(f,p,'P1');assert lock(f,p,key=key).status_code==200
    before=snapshot(f);r=goal_results(f,p);assert r.status_code==200 and r.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and snapshot(f)==before
