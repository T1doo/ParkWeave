"""Source-bound opportunity adoption through real HTTP and owned PostgreSQL."""
from copy import deepcopy
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_service_case_steps import adopt,read,step,verified,command,setup,GOALS,adopt_body
from test_case_goal_results import complete,get,snapshot
from test_service_plan_manual_lock import stored,lock
from test_case_opportunities import imported,post,body,get as opportunities
from test_preparation import headers,command as prepare,add
from test_service_plan_recovery import recover


def preview(f,p,card,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/opportunities/'+card['id']+'/plan-revision',headers=headers(f[2],user))


def changed(f,p):
    _,x,_=imported(f,p);card=x['cards'][0];add_resource(f)
    r=post(f,p,body(opportunities(f,p).json(),'REFRESH'));assert r.status_code==200,r.text
    return r.json()['current']['cards'][0]


def test_actual_opportunity_source_collection_adoption_preserves_locked_p1_and_history(http_f):
    f=http_f;p,g,d,s=complete(f,local=True);assert lock(f,p,'P1').status_code==200
    card=changed(f,p);old=stored(f,p);before=snapshot(f)
    r=preview(f,p,card);assert r.status_code==200,r.text;x=r.json();assert x['can_adopt'],x
    assert snapshot(f)==before and x['scope']=='SOURCE_CHANGE_LOCAL_REVISION_PREVIEW'
    assert set(x['affected'])=={step(read(f,p).json(),a)['id'] for a in ('P2','P3','P4','P5')}
    assert x['preserved']==[old['steps'][0]['id']]
    key=uuid4().hex;r=adopt(f,p,x['adoption'],key);assert r.status_code==201,r.text
    now=stored(f,p);assert now['id']==old['id'] and now['steps'][0]==old['steps'][0] and now['history']==old['history']
    assert now['events'][:-1]==old['events'] and [z['id'] for z in now['steps']]==[z['id'] for z in old['steps']]
    assert [z['verified_sources'] for z in now['steps']]==[z['verified_sources'] for z in old['steps']]
    before=snapshot(f);assert recover(f,p,key).json()['status']=='COMMITTED' and snapshot(f)==before
    assert adopt(f,p,x['adoption'],key).status_code==201 and stored(f,p)['revision']==now['revision']
    assert adopt(f,p,{**x['adoption'],'reason':'different parameters'},key).status_code==409
    for a in ('P2','P3','P4','P5'):verified(f,p,a)
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert stored(f,p)['steps'][0]==old['steps'][0]
    fresh=preview(f,p,card);assert fresh.status_code==200 and not fresh.json()['can_adopt']


def test_material_revision_uses_actual_before_sources_and_original_verify(http_f):
    f=http_f;p=setup(f,GOALS[0]);r=adopt(f,p);assert r.status_code==201;verified(f,p,'P1')
    _,x,_=imported(f,p);card=x['cards'][0];old=stored(f,p)
    p=prepare(f,p,'REOPEN',reason='SYNTHETIC actual material change').json()
    p=add(f,p,text='SYNTHETIC actual source replacement').json()
    assert preview(f,p,card).status_code==409
    x=post(f,p,body(opportunities(f,p).json(),'REFRESH')).json()['current'];card=x['cards'][0]
    r=preview(f,p,card);assert r.status_code==200,r.text;x=r.json();assert x['can_adopt'],x
    assert x['directly_changed']==[old['steps'][0]['id']] and x['affected']==x['directly_changed'] and not x['preserved']
    r=adopt(f,p,x['adoption']);assert r.status_code==201,r.text
    assert stored(f,p)['steps'][0]['verified_sources']==old['steps'][0]['verified_sources'] and command(f,p,'P1').status_code==409
    p=prepare(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC review replacement').json()
    p=prepare(f,p,'CONFIRM',reason='SYNTHETIC confirm replacement').json();verified(f,p,'P1')
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED' and stored(f,p)['id']==old['id']


@pytest.mark.parametrize('bad',['ledger','card','basis','preview','plan','unknown-proof'])
def test_forged_stale_proof_denies_without_plan_or_business_writes(http_f,bad):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p);x=preview(f,p,card).json();data=deepcopy(x['adoption'])
    if bad=='ledger':data['opportunity_proof']['expected_ledger_revision']+=1
    elif bad=='card':data['opportunity_proof']['expected_card_version']+=1
    elif bad=='basis':data['opportunity_proof']['expected_basis_sha256']='0'*64
    elif bad=='preview':data['opportunity_proof']['expected_preview_sha256']='0'*64
    elif bad=='plan':data['expected_plan_revision']-=1
    else:data['opportunity_proof']['authority']='imported hint'
    before=snapshot(f);assert adopt(f,p,data).status_code==(422 if bad=='unknown-proof' else 409) and snapshot(f)==before


@pytest.mark.parametrize('action',['IGNORE','WITHDRAW','NEW_GENERATION'])
def test_suppressed_old_generation_cannot_be_revived_by_refresh_or_old_preview(http_f,action):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p);x=preview(f,p,card).json();v=opportunities(f,p).json()
    if action=='NEW_GENERATION':r=post(f,p,body(v,item={**card['entry'],'generation':2}))
    else:r=post(f,p,body(v,action,card=card))
    assert r.status_code==200;r=post(f,p,body(r.json()['current'],'REFRESH'));assert r.status_code==200
    before=snapshot(f);assert preview(f,p,card).status_code==409 and adopt(f,p,x['adoption']).status_code==409 and snapshot(f)==before


def test_xmin_rejects_external_actual_resource_a_b_a_old_preview(http_f):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p);x=preview(f,p,card).json();assert x['can_adopt']
    with f[1].connect() as c:r=c.execute('SELECT id,capacity FROM synthetic_resources ORDER BY id LIMIT 1').fetchone()
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(r['id'],))
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(r['capacity'],r['id']))
    before=snapshot(f);assert adopt(f,p,x['adoption']).status_code==409 and snapshot(f)==before
    fresh=preview(f,p,card).json();assert fresh['can_adopt'] and fresh['preview_sha256']!=x['preview_sha256']
    assert adopt(f,p,fresh['adoption']).status_code==201


def test_affected_lock_requires_original_unlock_and_changes_preview_revision(http_f):
    f=http_f;p,g,d,s=complete(f);assert lock(f,p,'P1').status_code==200;assert lock(f,p,'P3').status_code==200
    card=changed(f,p);old=stored(f,p);x=preview(f,p,card).json();assert not x['can_adopt'] and 'AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK' in x['blocking_reasons']
    assert adopt(f,p,x['adoption']).status_code==409 and stored(f,p)['events']==old['events']
    assert command(f,p,'P3','UNLOCK').status_code==200
    fresh=preview(f,p,card).json();assert fresh['can_adopt'] and adopt(f,p,x['adoption']).status_code==409
    assert adopt(f,p,fresh['adoption']).status_code==201 and stored(f,p)['steps'][0]==old['steps'][0]


def test_hint_without_actual_change_or_missing_verify_base_never_authorizes(http_f):
    f=http_f;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201
    _,x,_=imported(f,p);card=x['cards'][0];before=snapshot(f);x=preview(f,p,card).json()
    assert not x['can_adopt'] and 'CURRENT_VERIFIED_SOURCE_BASE_REQUIRED' in x['blocking_reasons'] and snapshot(f)==before
    assert adopt(f,p,x['adoption']).status_code==409;verified(f,p,'P1');x=preview(f,p,card).json()
    assert not x['can_adopt'] and 'NO_ACTUAL_SOURCE_CHANGE' in x['blocking_reasons']


@pytest.mark.parametrize('damage',['partition','before','current','ledger','hash'])
def test_tampered_saved_source_change_proof_denies_all_original_reads(http_f,damage):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p);x=preview(f,p,card).json();key=uuid4().hex
    assert adopt(f,p,x['adoption'],key).status_code==201;plan=stored(f,p);proof=plan['events'][-1]['local_revision']['source_change']
    if damage=='partition':proof['affected']=proof['preserved']
    elif damage=='before':proof['before_sources']['P1']['preparation_revision']+=1
    elif damage=='current':proof['current_sources']['P2']['resource_collection']['sha256']='0'*64
    elif damage=='ledger':proof['ledger_sha256']='0'*64
    else:proof['sha256']='0'*64
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=snapshot(f);assert read(f,p).status_code==409 and recover(f,p,key).status_code==409 and get(f,p).status_code==409 and snapshot(f)==before


def test_real_event_budget_keeps_room_for_affected_verify_and_original_unlock(http_f):
    f=http_f;p,g,d,s=complete(f,local=True)
    # 52 real, original commands retain their full journal; no forged revision.
    for _ in range(26):
        assert lock(f,p,'P1').status_code==200
        assert command(f,p,'P1','UNLOCK').status_code==200
    assert lock(f,p,'P1').status_code==200
    card=changed(f,p);old=stored(f,p);assert old['revision']==59
    before=snapshot(f);r=preview(f,p,card);assert r.status_code==200,r.text;x=r.json()
    assert not x['can_adopt'] and x['remaining_verify_events']==4
    assert 'EVENT_CAPACITY_RESERVED_FOR_UNLOCK_AND_VERIFY' in x['blocking_reasons']
    assert adopt(f,p,x['adoption']).status_code==409 and snapshot(f)==before


def test_actual_row_version_bound_overflow_never_becomes_known_truncated_source(http_f):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p)
    for _ in range(130):add_resource(f)
    before=snapshot(f);r=preview(f,p,card)
    assert r.status_code==409 and 'bounded current source row-version proof' in r.text and snapshot(f)==before


def test_expired_actual_source_refuses_preview_adoption_even_with_pending_current_card(http_f):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p)
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],))
    before=snapshot(f);r=preview(f,p,card);assert r.status_code==200,r.text;x=r.json()
    assert not x['can_adopt'] and 'CURRENT_KNOWN_SOURCE_REQUIRED' in x['blocking_reasons']
    assert adopt(f,p,x['adoption']).status_code==409 and snapshot(f)==before


def test_original_opportunity_recovery_key_plan_revision_keeps_its_route(http_f):
    f=http_f;p,x,_=imported(f)
    result=post(f,p,body(x,'REFRESH'),key='plan-revision')
    assert result.status_code==200,result.text
    before=snapshot(f)
    recovered=f[3].get('/api/preparations/'+p['preparation_id']+'/opportunities/recovery/plan-revision',headers=headers(f[2]))
    assert recovered.status_code==200,recovered.text
    assert recovered.json()['receipt']==result.json()['receipt']
    assert snapshot(f)==before
