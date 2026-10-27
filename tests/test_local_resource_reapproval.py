"""Ordinary LOCAL same-plan source continuation; no isolated approval or authority."""
from copy import deepcopy
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave import local_resource_approval as local,case_resource_delivery as delivery
from parkweave.store import Store,Conflict
from test_local_resource_approval import local_fixture,ledger,setup,approved as approve_first
from test_case_resources import link_fixture,post as direct_bind
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_case_resource_delivery import quoted,submit,recover,effects,preview
from test_resource_bundles import bundle,states
from test_service_plan_approval import propose,decide,read as approval_read

from test_service_case_steps import verified,command as step_command
from test_service_plan_manual_lock import stored,lock


def source_adopt(f,p):
    from test_source_change_adoption import changed,preview as source_preview
    from test_service_case_steps import adopt
    response=source_preview(f,p,changed(f,p));assert response.status_code==200,response.text
    value=response.json();assert value['can_adopt'],value['blocking_reasons']
    response=adopt(f,p,value['adoption']);assert response.status_code==201,response.text
    return stored(f,p)['events'][-1]


def first(local_fixture):
    f,bridge,p,hs,data=setup(local_fixture);item,_=approve_first(f,p,data)
    response=submit(f,p,{**data,'approval_id':item['id']},uuid4().hex);assert response.status_code==201,response.text
    verified(f,p,'P2')
    return f,bridge,p,hs,response.json()


def approved(f,p,data):
    response=propose(f,p,data,revision=ledger(f,p)['revision']);assert response.status_code==201,response.text
    view=response.json();response=decide(f,p,view['items'][-1],view['revision']);assert response.status_code==200,response.text
    view=response.json();return view['items'][-1],view


def test_local_same_plan_source_adopt_reapproval_preserves_original_consumption(local_fixture):
    f,bridge,p,old_holds,old=first(local_fixture)
    assert lock(f,p,'P1').status_code==200
    original_plan=stored(f,p);prefix=deepcopy(ledger(f,p)['events']);event=source_adopt(f,p)
    hs,members=bundle(f)
    response=preview(f,p,{**members,'expected_link_revision':1})
    assert response.status_code==200,response.text
    data=quoted(f,p,{**members,'expected_link_revision':1});item,_=approved(f,p,data)
    assert item['purpose']=='CASE_RESOURCE_REAPPROVAL' and item['context']['source_reapproval']['source_adoption_event_id']==event['id']
    key=uuid4().hex;command={**data,'approval_id':item['id']};response=submit(f,p,command,key);assert response.status_code==201,response.text
    result=response.json();assert result['link']['revision']==2 and result['independent_check']['status']=='CURRENT'
    assert effects(f)==[2,6,2,2,2] and states(f,hs)==states(f,old_holds)==['CONFIRMED']*3
    assert ledger(f,p)['events'][:3]==prefix and ledger(f,p)['revision']==6
    assert stored(f,p)['id']==original_plan['id'] and stored(f,p)['steps'][0]==original_plan['steps'][0]
    assert stored(f,p)['events'][:len(original_plan['events'])]==original_plan['events']
    verified(f,p,'P2')
    assert recover(f,p,key).json()['receipt']==result['receipt']
    assert submit(f,p,command,key).json()['receipt']==result['receipt']
    assert recover(f,p,old['delivery_binding']['request_key']).json()['receipt']==old['receipt']
    assert approval_read(f,p).json()['items'][-1]['state']=='CONSUMED'
    # A later genuine ADOPT must not backfill this receipt's earlier source proof.
    source_adopt(f,p)
    later=recover(f,p,key);assert later.status_code==200,later.text
    assert later.json()['receipt']==result['receipt']
    assert later.json()['independent_check']['status']=='NEEDS_RECHECK'
    cold=Store(f[0].dsn)
    assert delivery.recover(cold,f[2]['fixture-a'],UUID(p['preparation_id']),key)['receipt']==result['receipt']
    assert delivery.recover(cold,f[2]['fixture-a'],UUID(p['preparation_id']),old['delivery_binding']['request_key'])['receipt']==old['receipt']


def continuation(local_fixture):
    f,bridge,p,old_holds,old=first(local_fixture);source_adopt(f,p)
    hs,members=bundle(f);data=quoted(f,p,{**members,'expected_link_revision':1});item,view=approved(f,p,data)
    return f,bridge,p,old_holds,old,hs,data,item,view


@pytest.mark.parametrize('change',['revoke','stale_adopt','grant','expired'])
def test_reapproval_changed_decision_source_or_authority_has_no_partial_effect(local_fixture,change):
    f,bridge,p,old_holds,old,hs,data,item,view=continuation(local_fixture)
    if change=='revoke':assert decide(f,p,item,view['revision'],'REVOKE').status_code==200
    elif change=='stale_adopt':source_adopt(f,p)
    else:
        with f[1].connect() as c:
            if change=='grant':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
            else:c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()-interval '1 second',created_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(hs[0]['id'],))
    before=deepcopy(ledger(f,p));counts=effects(f)
    result=submit(f,p,{**data,'approval_id':item['id']})
    assert result.status_code==(403 if change=='grant' else 409),result.text
    assert effects(f)==counts==[1,3,1,1,1] and ledger(f,p)==before
    assert states(f,hs)==['HELD']*3 and states(f,old_holds)==['CONFIRMED']*3


def test_commit_exception_rolls_back_new_consumption_capacity_and_association(local_fixture,monkeypatch):
    f,bridge,p,old_holds,old,hs,data,item,_=continuation(local_fixture);before=deepcopy(ledger(f,p));consume=bridge.consume
    def fail(*args,**kwargs):consume(*args,**kwargs);raise RuntimeError('controlled local reapproval after consume')
    monkeypatch.setattr(bridge,'consume',fail)
    with pytest.raises(RuntimeError,match='after consume'):submit(f,p,{**data,'approval_id':item['id']})
    assert ledger(f,p)==before and effects(f)==[1,3,1,1,1]
    assert states(f,hs)==['HELD']*3 and states(f,old_holds)==['CONFIRMED']*3


@pytest.mark.parametrize('consumer',['new-store','configured-app'])
def test_missing_mode_refuses_new_later_and_plain_bind_but_preserves_original_recovery(local_fixture,monkeypatch,consumer):
    from test_local_resource_approval import cold_without_local_approval
    f,bridge,p,old_holds,old,hs,data,item,_=continuation(local_fixture)
    body=deepcopy(ledger(f,p)['events'][2]['request']['delivery']);key=old['delivery_binding']['request_key'];before=deepcopy(ledger(f,p))
    assert direct_bind(f,p,old['combination'],revision=1).status_code==409
    app=cold_without_local_approval(f,consumer,monkeypatch)
    with TestClient(app) as api:
        cold=(*f[:3],api)
        assert preview(cold,p,dict(members=data['members'],expected_link_revision=1)).status_code==403
        assert submit(cold,p,{**data,'approval_id':item['id']}).status_code==403
        assert direct_bind(cold,p,old['combination'],revision=1).status_code==403
        recovered=recover(cold,p,key)
        assert recovered.status_code==200,recovered.text
        assert recovered.json()['receipt']==old['receipt']
        assert submit(cold,p,body,key).json()['receipt']==old['receipt']
    assert ledger(f,p)==before and effects(f)==[1,3,1,1,1] and states(f,hs)==['HELD']*3


def test_cross_case_scope_and_changed_profile_cannot_borrow_approval(local_fixture):
    f,bridge,p,old_holds,old,hs,data,item,_=continuation(local_fixture)
    from test_ordinary_case_goal_results import start
    other=start(f,goals=['LOCAL_CASE_RESOURCE_ASSOCIATION']);verified(f,other,'P1')
    other_data=quoted(f,other,{'members':data['members']});before=effects(f);history=deepcopy(ledger(f,p))
    assert submit(f,other,{**other_data,'approval_id':item['id']}).status_code==409
    assert recover(f,other,old['delivery_binding']['request_key']).status_code==409
    stripped={k:v for k,v in data.items() if k!='expected_link_revision'}
    assert submit(f,p,{**stripped,'approval_id':item['id']}).status_code==409
    assert effects(f)==before and ledger(f,p)==history
    for changes in ({'expected_previous_plan_id':stored(f,p)['id']},{'expected_previous_plan_id':stored(f,p)['id'],'replacement_frontier_profile':'KNOWN_NOT_STARTED_V1'}):
        result=preview(f,p,dict(members=data['members'],expected_link_revision=1,**changes));assert result.status_code==403,result.text


@pytest.mark.parametrize('fault',['STRIP_PROFILE','SELF_ANCHOR','STRIP_PROOFS','UNKNOWN_SCOPE'])
def test_owned_rehashed_history_cannot_remove_profile_or_use_self_anchor_or_other_scope(local_fixture,fault):
    from psycopg.types.json import Jsonb
    from parkweave import controlled_plans as cp,service_plan_approval as core,preparation as prep
    from parkweave.store import digest
    f,bridge,p,old_holds,old,hs,data,item,_=continuation(local_fixture);key=uuid4().hex
    result=submit(f,p,{**data,'approval_id':item['id']},key);assert result.status_code==201,result.text
    value=result.json();receipt=deepcopy(value['receipt']);events=deepcopy(ledger(f,p));proposal,approval,consume=events['events'][3:]
    context=proposal['binding']['context']
    for command in (proposal['request']['delivery'],consume['request']['delivery']):
        if fault=='STRIP_PROFILE':command.pop('expected_link_revision')
        elif fault=='SELF_ANCHOR':command['expected_link_revision']=2
    if fault=='STRIP_PROFILE':
        context.pop('source_reapproval');proposal['binding']['purpose']='CASE_RESOURCE_DELIVERY';receipt['delivery_binding']['context'].pop('source_reapproval')
    elif fault=='SELF_ANCHOR':
        for current in (context['source_reapproval'],receipt['delivery_binding']['context']['source_reapproval']):current.update(link_id=value['link']['id'],link_revision=2,snapshot_sha256='a'*64)
    binding_sha=cp._hash(proposal['binding']);approval['request']['expected_binding_sha256']=binding_sha;receipt['plan_approval']['binding_sha256']=binding_sha
    if fault=='STRIP_PROOFS':receipt['plan_approval']=None
    elif fault=='UNKNOWN_SCOPE':receipt['plan_approval']['scope']='UNKNOWN_SOURCE'
    fp=digest(prep.canonical(dict(preparation_id=p['preparation_id'],action='CASE_RESOURCE_DELIVERY',**consume['request']['delivery'])))
    receipt['delivery_binding']['fingerprint']=fp;consume['receipt'].update(fingerprint=fp,receipt_sha256=cp._hash(receipt));previous=None
    for event in events['events']:
        event['previous_sha256']=previous;event['fingerprint']=core._fingerprint(p['preparation_id'],event['request']);event['sha256']=cp._hash({k:v for k,v in event.items() if k!='sha256'});previous=event['sha256']
    snapshot=deepcopy(value['link']['snapshot']);snapshot['delivery_binding']=receipt['delivery_binding'];snapshot['plan_approval']=receipt['plan_approval']
    with f[1].connect() as c:
        c.execute('ALTER TABLE preparations DISABLE TRIGGER local_resource_approval_prefix')
        c.execute('UPDATE preparations SET local_resource_approvals=%s,local_resource_approval_head=%s WHERE id=%s',(Jsonb(events),Jsonb(dict(revision=events['revision'],sha256=previous)),p['preparation_id']))
        c.execute('ALTER TABLE preparations ENABLE TRIGGER local_resource_approval_prefix')
        c.execute('UPDATE synthetic_resource_combination_receipts SET payload=%s,fingerprint=%s WHERE actor_id=%s AND request_key=%s',(Jsonb(receipt),fp,'fixture-a',key))
        c.execute('UPDATE case_resource_links SET snapshot=%s,fingerprint=%s WHERE id=%s',(Jsonb(snapshot),fp,value['link']['id']))
    response=recover(f,p,key);assert response.status_code==409,response.text
    for endpoint in ('resource-plan-binding','service-case-plan','goal-results'):
        response=f[3].get('/api/preparations/'+p['preparation_id']+'/'+endpoint,headers=headers(f[2]));assert response.status_code==409,(fault,endpoint,response.text)


# Existing explicit synthetic catalog inputs; no isolated Approval/Run bridge.
from test_local_synthetic_demo import demo_inputs


@pytest.fixture
def ordinary_local(demo_inputs):
    import json
    from parkweave.api import create_app
    from parkweave import case_step_assignments as cs,local_synthetic_demo as demo
    from test_new_enterprise_local_chain import actual_http
    initial,cfg,_,_=demo_inputs;initial[1].migrate_local_resource_approval_fixture();store=Store(initial[0].dsn)
    pair=cs.from_environment(store,dict(PARKWEAVE_CASE_STEP_MODE=cs.LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=demo.PROFILE,PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=json.dumps(cfg)))
    bridge=local.LocalResourceApproval(store)
    app=create_app(store,case_step_assignments=pair,local_synthetic_demo=pair.local_synthetic_demo,local_resource_approval=bridge)
    with actual_http(app) as (api,requests):yield (store,initial[1],initial[2],api),bridge,requests


def selected_case(f,directory,goals=None):
    from test_request_intents import save
    from test_preparation import add,command as materials
    from test_local_synthetic_demo import GOALS,generate
    from ordinary_case_step_support import worker_once
    from test_service_case_steps import adopt,adopt_body
    goals=GOALS[:2] if goals is None else goals
    run=f[3].post('/api/runs',headers=headers(f[2],key=uuid4().hex),json=dict(goal='SYNTHETIC 新输入同计划来源变更后重新批准资源'))
    assert run.status_code==202,run.text;worker_once(f,directory)
    p=f[3].post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=dict(run_id=run.json()['run_id'],service_id='synthetic-material-preparation',service_version=1,reviewer_id='prep-specialist-fixture-a'))
    assert p.status_code==201,p.text;p=p.json()
    p=save(f,p,goals=goals,text='SYNTHETIC 本次独立新输入和明确选择目标').json()
    p=add(f,p,text='SYNTHETIC 本次独立诉求正文').json();p=add(f,p,'material_outline','SYNTHETIC 本次独立材料目录正文').json()
    p=materials(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC 原专员独立核对').json();p=materials(f,p,'CONFIRM',reason='SYNTHETIC 原经办人明确确认').json()
    # Original registered deterministic planner; no service-selection producer.
    response=adopt(f,p,adopt_body(f,p));assert response.status_code==201,response.text
    assert [s['adapter_id'] for s in response.json()['steps']]==(['P1','P2'] if len(goals)==2 else ['P1','P2','P3','P4','P5'])
    verified(f,p,'P1')
    hs,members=bundle(f);data=quoted(f,p,members);item,_=approve_first(f,p,data)
    response=submit(f,p,{**data,'approval_id':item['id']});assert response.status_code==201,response.text;verified(f,p,'P2')
    return p,hs,response.json()


def test_registered_new_input_same_plan_reapproval_to_original_stage_outputs_and_txt(ordinary_local,tmp_path):
    from test_ordinary_case_goal_record_pack_process import html
    from service_release_acceptance_support import authority_snapshot
    import json
    f,bridge,requests=ordinary_local;p,old_holds,old=selected_case(f,tmp_path/'worker')
    assert lock(f,p,'P1').status_code==200;before=stored(f,p);original_prefix=deepcopy(ledger(f,p)['events']);source_adopt(f,p)
    # The owned source-change fixture explicitly adds a resource and grants.
    # Approval/delivery/export must not add any further authority.
    authority=authority_snapshot(f[1])
    hs,members=bundle(f);data=quoted(f,p,{**members,'expected_link_revision':1});item,_=approved(f,p,data);key=uuid4().hex
    # Deliberately discard the successful command response, then recover by GET.
    result=submit(f,p,{**data,'approval_id':item['id']},key);assert result.status_code==201,result.text
    original=result.json()['receipt'];del result
    restored=recover(f,p,key);assert restored.status_code==200,restored.text;assert restored.json()['receipt']==original
    verified(f,p,'P2')
    results=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]));assert results.status_code==200,results.text;results=results.json()
    assert results['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert results['source_trace'].get('candidate') is None
    assert not results['case_goal_completed'] and len(results['results'])==2
    pack=html(f,tmp_path/'actual-original-txt',p,before['id'],'LOCAL_OUTPUTS_VERIFIED',goal_count=2)
    assert states(f,old_holds)==states(f,hs)==['CONFIRMED']*3
    assert stored(f,p)['id']==before['id'] and stored(f,p)['steps'][0]==before['steps'][0]
    assert ledger(f,p)['events'][:3]==original_prefix and effects(f)==[2,6,2,2,2]
    assert authority_snapshot(f[1])==authority
    assert recover(f,p,old['delivery_binding']['request_key']).json()['receipt']==old['receipt']
    (tmp_path/'actual-chain.json').write_text(json.dumps(dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],plan_id=before['id'],result_state=results['state'],result_count=2,old_receipt=old['receipt'],new_receipt=original,pack_sha256=pack['pack_sha256'],HTTP_calls=len(requests),planner='ORIGINAL_REGISTERED_DETERMINISTIC',service_selection_producer=False,real_model_calls=0,browser=False),indent=2)+'\n')


@pytest.mark.parametrize('started',['PLAN_BEGIN','OFFERED'])
def test_live_source_reapproval_refuses_started_coordination_without_touching_history(ordinary_local,tmp_path,started):
    from test_service_dispatches import offer
    from test_local_synthetic_demo import GOALS
    from test_source_change_adoption import changed,preview as source_preview
    f,bridge,_=ordinary_local;p,old_holds,old=selected_case(f,tmp_path/'worker',GOALS if started=='PLAN_BEGIN' else None)
    if started=='PLAN_BEGIN':response=step_command(f,p,'P3','BEGIN',user='prep-specialist-fixture-a')
    else:response=offer(f,p)[0]
    assert response.status_code in (200,201),response.text
    if started=='OFFERED':source_adopt(f,p)
    else:
        # This full-plan source ADOPT remains blocked by missing tail bases.
        # The live preview below must report our earlier explicit started gate.
        source=source_preview(f,p,changed(f,p));assert source.status_code==200,source.text
        assert not source.json()['can_adopt']
        assert 'CURRENT_VERIFIED_SOURCE_BASE_REQUIRED' in source.json()['blocking_reasons']
    hs,members=bundle(f);prefix=deepcopy(ledger(f,p));before=effects(f)
    result=preview(f,p,{**members,'expected_link_revision':1});assert result.status_code==409,result.text
    assert 'local source continuation refuses' in result.text
    assert ledger(f,p)==prefix and effects(f)==before and states(f,hs)==['HELD']*3
    assert recover(f,p,old['delivery_binding']['request_key']).json()['receipt']==old['receipt']
