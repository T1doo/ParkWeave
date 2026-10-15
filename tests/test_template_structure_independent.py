"""Independent literal structural migration oracles; original owned PG/ASGI only."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
from uuid import uuid4
import pytest
from test_template_upgrade import (upgrade_case, publication, instance, confirmed, check,
                                  choose, plan_read, plan_command, headers, GOALS)
from test_template_migration_independent import stored, facts, all_pg_rows, admit as old_admit, apply as old_apply, recovery
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture



def admit(u,row,target,choice='REQUEST_RECHECK'):
    view,data=old_admit(u,row,target,choice)
    application=view['application']
    data['expected_structure_sha256']=application.get('structure_sha256')
    data['confirm_structure_change']=True
    return view,data


def apply(u,row,data,key=None,user='fixture-a'):
    return u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply-structure',headers=headers(u['f'][2],user,key or uuid4().hex),json=data)



def denied_effects_preserved(before,after,actor,count):
    # Original API records denied authorization independently. Preserve that
    # audit contract while proving no business/permission/coordination write.
    assert {k:v for k,v in after.items() if k!='authorization_audit'}=={k:v for k,v in before.items() if k!='authorization_audit'}
    old={str(r['id']):r for r in before['authorization_audit']}
    current={str(r['id']):r for r in after['authorization_audit']}
    assert all(current[k]==v for k,v in old.items())
    added=[v for k,v in current.items() if k not in old]
    assert len(added)==count
    assert all(r['principal_id']==actor and r['category']=='API_AUTHORIZATION' and r['outcome']=='DENIED' for r in added)

OLD_GOALS=GOALS[:4]
NEW_GOALS=GOALS

@pytest.fixture(autouse=True)
def private_fixture_sessions(upgrade_case):
    p=Path('.runtime/template-structure-tests-20261015/redaction-values.private.json')
    p.parent.mkdir(parents=True,exist_ok=True)
    values=json.loads(p.read_text()) if p.exists() else []
    p.write_text(json.dumps(sorted(set(values)|set(upgrade_case['f'][2].values()))))
    p.chmod(0o600)


def test_new_case_goal_not_predeclared_is_explicitly_rejected(upgrade_case):
    u=upgrade_case
    row,old=instance(u,OLD_GOALS)
    p=confirmed(u,row)
    target=publication(u,NEW_GOALS,source='1',name='Synthetic explicitly proposed P5 extension')
    assert [s['id'] for s in old['snapshot']['definition']['steps']]==['P1','P2','P3','P4']
    assert [s['id'] for s in target['snapshot']['definition']['steps']]==['P1','P2','P3','P4','P5']
    before=all_pg_rows(u)
    view=check(u,row,target)
    assert view.status_code==200,view.text
    assert all_pg_rows(u)==before, 'structural inspection wrote existing facts'
    body=view.json()
    assert body['check']['classification']=='NEEDS_RECHECK'
    assert 'UPGRADE_SCOPE_UNSUPPORTED' in body['application']['blockers'],body['application']

SIX_GOALS = [
    'LOCAL_MATERIAL_PREPARATION',
    'LOCAL_CASE_RESOURCE_ASSOCIATION',
    'LOCAL_INTERNAL_ACCEPTANCE',
    'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
    'LOCAL_SYNTHETIC_COORDINATION_RECORDS',
    'LOCAL_CASE_RECORD_RECHECK',
]


def declared_instance(u, template_goals=OLD_GOALS, case_goals=SIX_GOALS):
    """Real original Consume explicitly declares a superset before any upgrade."""
    old=publication(u,template_goals)
    data=dict(release_id=old['release_id'],expected_release_sha256=old['release_sha256'],
        goal='SYNTHETIC PRIVATE_STRUCTURE_CASE',reviewer_id='prep-specialist-fixture-a',
        required_goals=list(case_goals),
        materials=[dict(slot=s,text='SYNTHETIC PRIVATE_STRUCTURE_MATERIAL '+s,source_kind='USER_STATEMENT',source_label='Synthetic structure fixture input') for s in ('need_summary','material_outline')],
        reason='Explicit six goals from original Case creation')
    response=u['client'].post('/api/template-consumer/instances',headers=headers(u['f'][2],key=uuid4().hex),json=data)
    assert response.status_code==201,response.text
    row=response.json();u['f'][0].finish(u['f'][0].claim('template-structure-case'))
    response=u['client'].post('/api/template-consumer/instances/'+row['instance_id']+'/resume',headers=headers(u['f'][2],key=uuid4().hex),json={})
    assert response.status_code==200,response.text
    row=response.json();assert row['state']=='PLAN_CONFIRMATION_REQUIRED'
    preview=u['client'].get('/api/template-consumer/instances/'+row['instance_id']+'/planning',headers=headers(u['f'][2])).json()
    adoption=dict(expected_preparation_revision=preview['current']['preparation_revision'],expected_request_revision=preview['request_intent']['revision'],
        expected_source_sha256=preview['current']['source_sha256'],expected_plan_revision=0,required_goals=preview['request_intent']['required_goals'],
        reason='SYNTHETIC explicit original six-goal plan adoption')
    response=u['client'].post('/api/template-consumer/instances/'+row['instance_id']+'/adopt',headers=headers(u['f'][2],key=uuid4().hex),json=adoption)
    assert response.status_code==200,response.text
    row=response.json();assert row['state']=='PLAN_ADOPTED'
    p=confirmed(u,row)
    assert [s['adapter_id'] for s in stored(u,row)['steps']]==['P1','P2','P3','P4','P5']
    assert stored(u,row)['required_goals']==SIX_GOALS
    return row,old,p


def test_literal_template_structure_addition_with_unchanged_original_six_goals(upgrade_case):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,SIX_GOALS,source='1',name='Synthetic template adds already declared P5 requirement')
    assert [s['id'] for s in old['snapshot']['definition']['steps']]==['P1','P2','P3','P4']
    assert [s['id'] for s in target['snapshot']['definition']['steps']]==['P1','P2','P3','P4','P5']
    old_plan=deepcopy(stored(u,row));before=all_pg_rows(u)
    view=check(u,row,target)
    assert view.status_code==200,view.text
    assert all_pg_rows(u)==before
    body=view.json();assert body['check']['classification']=='NEEDS_RECHECK'
    assert 'UPGRADE_SCOPE_UNSUPPORTED' not in body['application']['blockers'],body['application']
    ids={s['adapter_id']:s['id'] for s in old_plan['steps']}
    assert set(body['application']['affected'])=={ids['P4'],ids['P5']}
    assert set(body['application']['preserved'])=={ids['P1'],ids['P2'],ids['P3']}


def complete_declared(u, template_goals=OLD_GOALS, finalize=True, begin_p5=False):
    from test_template_migration_independent import accepted, verified, adopt, adopt_body
    from test_executor_receipts import act as receipt_act
    from test_case_lifecycle import read as life_read, act as life_act
    row,old,p=declared_instance(u,template_goals)
    with u['f'][1].connect() as c:
        for actor in ('prep-specialist-fixture-a','executor-a'):
            c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING', (row['run_id'],actor,'park-a','org-a'))
    current=plan_read(u['f'],p).json()
    result=adopt(u['f'],p,{**adopt_body(u['f'],p),'expected_plan_revision':current['revision'],'local_revision':True})
    assert result.status_code==201,result.text
    _,dispatch=accepted(u['f'],p);verified(u['f'],p,'P3')
    receipt=u['f'][3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(u['f'][2],'executor-a')).json()
    receipt=receipt_act(u['f'],receipt,'SUBMIT').json()
    result=receipt_act(u['f'],receipt,'ACKNOWLEDGE');assert result.status_code==200,result.text
    verified(u['f'],p,'P4')
    result=life_act(u['f'],p,life_read(u['f'],p).json(),'REVALIDATE');assert result.status_code==200,result.text
    if begin_p5:
        response=plan_command(u['f'],p,'P5','BEGIN')
        assert response.status_code==200,response.text
    if finalize:verified(u['f'],p,'P5')
    return row,old,p


def goal_results(u,row):
    response=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('target_goals,affected_adapters',[(GOALS,('P5',)),(SIX_GOALS,('P4','P5'))])
def test_actual_structural_adoption_preserves_six_goals_and_every_actual_effect(upgrade_case,target_goals,affected_adapters):
    from test_template_migration_independent import verified
    u=upgrade_case;row,old,p=complete_declared(u)
    initial_results=goal_results(u,row)
    assert initial_results['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert [r['goal'] for r in initial_results['results']]==SIX_GOALS
    outputs={r['goal']:r['actual_output'] for r in initial_results['results']}
    target=publication(u,target_goals,source='1',name='Synthetic structural expansion with original Case goals')
    before=deepcopy(stored(u,row));business=facts(u)
    view,data=admit(u,row,target)
    ids={s['adapter_id']:s['id'] for s in before['steps']}
    assert view['application']['eligible'],view['application']
    assert set(view['application']['affected'])=={ids[a] for a in affected_adapters}
    assert set(view['application']['preserved'])=={ids[a] for a in ('P1','P2','P3','P4','P5') if a not in affected_adapters}
    result=apply(u,row,data,'structure-actual-adoption')
    assert result.status_code==200,result.text
    after=stored(u,row)
    assert after['id']==before['id'] and after['required_goals']==before['required_goals']==SIX_GOALS
    assert after['binding']==before['binding'] and after['adoption_preview']==before['adoption_preview']
    assert after['history']==before['history']
    assert after['events'][:-1]==before['events']
    for oldstep,newstep in zip(before['steps'],after['steps']):
        assert oldstep['id']==newstep['id'] and oldstep['contract']==newstep['contract']
        assert oldstep['verified_sources']==newstep['verified_sources'] and oldstep['verified_sha256']==newstep['verified_sha256']
        if oldstep['adapter_id'] not in affected_adapters:assert newstep==oldstep
    assert facts(u)==business
    current=plan_read(u['f'],p).json();states={s['adapter_id']:s['state'] for s in current['steps']}
    assert {a for a,state in states.items() if state!='VERIFIED'}==set(affected_adapters)
    assert goal_results(u,row)['state']!='LOCAL_OUTPUTS_VERIFIED'
    for adapter in affected_adapters:verified(u['f'],p,adapter)
    final=goal_results(u,row)
    assert final['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert {r['goal']:r['actual_output'] for r in final['results']}==outputs
    assert facts(u)==business
    saved=all_pg_rows(u)
    recovered=recovery(u,row,'structure-actual-adoption')
    assert recovered.status_code==200 and recovered.json()['status']=='COMMITTED',recovered.text
    assert all_pg_rows(u)==saved


@pytest.mark.parametrize('locked,allowed',[('P1',True),('P5',False)])
def test_structural_change_respects_precise_existing_manual_lock(upgrade_case,locked,allowed):
    from test_template_migration_independent import verified
    u=upgrade_case;row,old,p=complete_declared(u)
    current=plan_read(u['f'],p).json();step=next(s for s in current['steps'] if s['adapter_id']==locked)
    response=plan_command(u['f'],p,locked,'LOCK',row=current,expected_source_sha256=step['source_sha256'])
    assert response.status_code==200,response.text
    target=publication(u,GOALS,source='1',name='Synthetic P5 requirement versus current manual lock')
    before=deepcopy(stored(u,row));business=facts(u)
    read=check(u,row,target);assert read.status_code==200,read.text
    body=read.json()
    if allowed:
        assert body['check']['classification']=='NEEDS_RECHECK',body
        view,data=admit(u,row,target)
        assert view['application']['eligible'],view['application']
        response=apply(u,row,data,'structural-preserved-lock');assert response.status_code==200,response.text
        saved=stored(u,row)
        original=next(s for s in before['steps'] if s['adapter_id']==locked)
        assert next(s for s in saved['steps'] if s['adapter_id']==locked)==original
        verified(u['f'],p,'P5')
        assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED'
    else:
        assert body['check']['classification']=='LOCK_CONFLICT',body
        assert body['check']['allowed_choices']==['KEEP_CURRENT']
        response=choose(u,row,body,'REQUEST_RECHECK');assert response.status_code==409,response.text
        assert stored(u,row)==before
        current=plan_read(u['f'],p).json()
        response=plan_command(u['f'],p,locked,'UNLOCK',row=current);assert response.status_code==200,response.text
        view,data=admit(u,row,target)
        assert view['application']['eligible'],view['application']
        response=apply(u,row,data,'structural-after-original-unlock');assert response.status_code==200,response.text
        verified(u['f'],p,'P5')
    assert facts(u)==business


def advance(u,p,revision):
    current=plan_read(u['f'],p).json()
    assert (revision-current['revision'])%2==0
    while current['revision']<revision:
        step=current['steps'][0]
        response=plan_command(u['f'],p,'P1','LOCK',row=current,expected_source_sha256=step['source_sha256'])
        assert response.status_code==200,response.text
        response=plan_command(u['f'],p,'P1','UNLOCK',row=response.json())
        assert response.status_code==200,response.text
        current=response.json()
    return current


@pytest.mark.parametrize('revision',[62,63])
def test_structural_new_p5_budget_reserves_exact_owner_verify_capacity(upgrade_case,revision):
    from test_template_migration_independent import verified
    u=upgrade_case;row,old,p=complete_declared(u,begin_p5=revision==62)
    assert stored(u,row)['revision']==(8 if revision==62 else 7)
    advance(u,p,revision)
    target=publication(u,GOALS,source='1',name='Synthetic structural requirement at event boundary')
    view,data=admit(u,row,target);before=all_pg_rows(u)
    ids={s['adapter_id']:s['id'] for s in stored(u,row)['steps']}
    assert view['application']['affected']==[ids['P5']]
    key=uuid4().hex;response=apply(u,row,data,key)
    if revision==62:
        assert view['application']['eligible'],view['application']
        assert response.status_code==200,response.text
        verified(u['f'],p,'P5')
        assert stored(u,row)['revision']==64
        assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED'
    else:
        assert not view['application']['eligible'] and 'PLAN_EVENT_LIMIT' in view['application']['blockers']
        assert response.status_code==409,response.text
        assert all_pg_rows(u)==before
        assert recovery(u,row,key).json()['status']=='NOT_OBSERVED'


@pytest.mark.parametrize('old_goals,target_goals,affected',[(GOALS[:1],GOALS[:2],('P2','P3','P4','P5')),(GOALS[:2],GOALS[:3],('P3','P4','P5'))])
def test_structural_registered_requirement_propagates_to_literal_downstream(upgrade_case,old_goals,target_goals,affected):
    from test_template_migration_independent import verified
    u=upgrade_case;row,old,p=complete_declared(u,old_goals)
    target=publication(u,target_goals,source='1',name='Synthetic registered upstream requirement expansion')
    before=deepcopy(stored(u,row));business=facts(u);view,data=admit(u,row,target)
    ids={s['adapter_id']:s['id'] for s in before['steps']}
    assert view['application']['eligible'],view['application']
    assert set(view['application']['affected'])=={ids[a] for a in affected}
    assert set(view['application']['preserved'])=={ids[a] for a in ('P1','P2','P3','P4','P5') if a not in affected}
    response=apply(u,row,data,'structural-upstream');assert response.status_code==200,response.text
    for adapter in affected:verified(u['f'],p,adapter)
    assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert facts(u)==business


def test_mixed_source_and_structural_change_conservatively_reverifies_all(upgrade_case):
    from test_template_migration_independent import verified
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='2',name='Synthetic simultaneous source and structure update')
    before=deepcopy(stored(u,row));business=facts(u);view,data=admit(u,row,target)
    assert view['application']['eligible'],view['application']
    assert set(view['application']['affected'])=={s['id'] for s in before['steps']}
    assert view['application']['preserved']==[]
    response=apply(u,row,data,'structural-source-expanded');assert response.status_code==200,response.text
    for adapter in ('P1','P2','P3','P4','P5'):verified(u['f'],p,adapter)
    assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED' and facts(u)==business


def test_structural_multihop_compares_effective_template_and_keeps_old_key(upgrade_case):
    from test_template_migration_independent import verified
    u=upgrade_case;row,v1,p=complete_declared(u,GOALS[:1]);business=facts(u)
    v2=publication(u,GOALS[:2],source='1',name='Synthetic first structural expansion')
    _,data=admit(u,row,v2);response=apply(u,row,data,'structural-v2');assert response.status_code==200,response.text
    for adapter in ('P2','P3','P4','P5'):verified(u['f'],p,adapter)
    before=deepcopy(stored(u,row))
    v3=publication(u,GOALS[:3],source='1',name='Synthetic second structural expansion')
    view,data=admit(u,row,v3)
    ids={s['adapter_id']:s['id'] for s in before['steps']}
    assert view['application']['eligible'],view['application']
    assert set(view['application']['affected'])=={ids[a] for a in ('P3','P4','P5')}
    assert set(view['application']['preserved'])=={ids['P1'],ids['P2']}
    response=apply(u,row,data,'structural-v3');assert response.status_code==200,response.text
    for adapter in ('P3','P4','P5'):verified(u['f'],p,adapter)
    assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED' and facts(u)==business
    saved=all_pg_rows(u);response=recovery(u,row,'structural-v2')
    assert response.status_code==200,response.text
    assert response.json()['effective_release_id']==v2['release_id']
    assert all_pg_rows(u)==saved


@pytest.mark.parametrize('mode',['same_key_same_body','same_key_different_body','different_key_same_body'])
def test_structural_apply_concurrency_has_exactly_one_immutable_event(upgrade_case,mode):
    from concurrent.futures import ThreadPoolExecutor
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic concurrent structural operation')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    other=deepcopy(data)
    if mode=='same_key_different_body':other['reason']='SYNTHETIC distinct explicit structural reason'
    keys=['structural-concurrent-a','structural-concurrent-b' if mode=='different_key_same_body' else 'structural-concurrent-a']
    business=facts(u);old=deepcopy(stored(u,row))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda n:apply(u,row,(data,other)[n],keys[n]),range(2)))
    codes=sorted(r.status_code for r in results)
    assert codes==([200,200] if mode=='same_key_same_body' else [200,409]),[(r.status_code,r.text) for r in results]
    new=stored(u,row)
    assert new['revision']==old['revision']+1 and len(new['events'])==len(old['events'])+1
    assert new['events'][-1]['action']=='TEMPLATE_UPGRADE' and facts(u)==business
    if mode=='same_key_same_body':assert results[0].json()['event']==results[1].json()['event']


def test_structural_event_save_failure_rolls_back_actual_pg_update(upgrade_case,monkeypatch):
    from fastapi.testclient import TestClient
    from parkweave import service_case_steps as plans
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic structural event fault')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    before=all_pg_rows(u);save=plans._save
    def failed(*args,**kwargs):
        save(*args,**kwargs)
        raise RuntimeError('SYNTHETIC actual structural PG UPDATE succeeded before injected failure')
    monkeypatch.setattr(plans,'_save',failed)
    with TestClient(u['client'].app,raise_server_exceptions=False) as client:
        response=client.post('/api/template-upgrade/'+row['instance_id']+'/apply-structure',headers=headers(u['f'][2],key='structural-event-fault'),json=data)
    assert response.status_code in (500,503),response.text
    assert all_pg_rows(u)==before
    assert recovery(u,row,'structural-event-fault').json()['status']=='NOT_OBSERVED'


def test_structural_lost_committed_response_gets_original_key_without_repost(upgrade_case,monkeypatch):
    from fastapi.testclient import TestClient
    from parkweave.template_upgrade import TemplateUpgradeChecker
    from uuid import UUID
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic lost structural response')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    original=u['checker'].apply;calls=[]
    def lost(*args,**kwargs):
        result=original(*args,**kwargs);calls.append(result)
        raise RuntimeError('SYNTHETIC committed structural response lost')
    monkeypatch.setattr(u['checker'],'apply',lost)
    with TestClient(u['client'].app,raise_server_exceptions=False) as client:
        response=client.post('/api/template-upgrade/'+row['instance_id']+'/apply-structure',headers=headers(u['f'][2],key='structural-lost-response'),json=data)
    assert response.status_code in (500,503),response.text
    assert len(calls)==1
    before=all_pg_rows(u)
    def forbidden(*args,**kwargs):raise AssertionError('GET recovery must not re-send POST')
    monkeypatch.setattr(u['checker'],'apply',forbidden)
    response=recovery(u,row,'structural-lost-response')
    assert response.status_code==200 and response.json()['status']=='COMMITTED',response.text
    cold=TemplateUpgradeChecker(u['consumer'],u['repository'],enabled_for_isolated_tests=True)
    result=cold.recover_application(u['f'][2]['fixture-a'],UUID(row['instance_id']),'structural-lost-response')
    assert result['status']=='COMMITTED' and all_pg_rows(u)==before and len(calls)==1


def test_structural_adoption_never_changes_other_case_plan_or_current_request(upgrade_case):
    u=upgrade_case;row,old,p=complete_declared(u)
    other,other_old,other_p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic one-Case structural choice')
    original_other=deepcopy(stored(u,other));business=facts(u)
    with u['consumer'].repository.connect() as c:
        consumer_before=[tuple(x) for x in c.execute('SELECT * FROM consumer_instances ORDER BY id')]
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    response=apply(u,row,data,'structural-one-case');assert response.status_code==200,response.text
    assert stored(u,other)==original_other and facts(u)==business
    with u['consumer'].repository.connect() as c:
        assert [tuple(x) for x in c.execute('SELECT * FROM consumer_instances ORDER BY id')]==consumer_before
    before=all_pg_rows(u)
    response=recovery(u,other,'structural-one-case')
    assert response.status_code==409,response.text
    assert all_pg_rows(u)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_structural_apply_and_recovery_reject_other_identity(upgrade_case,user):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic owner-only structural choice')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    before=all_pg_rows(u)
    result=apply(u,row,data,'structural-owner-key',user=user)
    assert result.status_code==403,result.text
    result=recovery(u,row,'structural-owner-key',user=user)
    assert result.status_code==403,result.text
    denied_effects_preserved(before,all_pg_rows(u),user,2)


@pytest.mark.parametrize('permission',['EXECUTE','PREPARE','READ'])
def test_structural_current_revocation_blocks_apply_and_original_recovery(upgrade_case,permission):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic current revoked structural choice')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    with u['f'][1].connect() as c:
        u['f'][1].lock_principal(c,'fixture-a',exclusive=True)
        if permission=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(permission,))
    before=all_pg_rows(u)
    response=apply(u,row,data,'structural-revoked')
    assert response.status_code==403,response.text
    if permission in ('READ','PREPARE'):
        response=recovery(u,row,'structural-revoked')
        assert response.status_code==403,response.text
    denied_effects_preserved(before,all_pg_rows(u),'fixture-a',1 if permission=='EXECUTE' else 2)


def test_original_six_goal_fixture_has_a_legal_even_verified_revision(upgrade_case):
    u=upgrade_case;row,old,p=complete_declared(u,begin_p5=True)
    assert stored(u,row)['revision']==8
    assert goal_results(u,row)['state']=='LOCAL_OUTPUTS_VERIFIED'


def test_old_apply_never_accepts_structural_revision_without_new_confirmation(upgrade_case):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic old endpoint structure refusal')
    view,data=old_admit(u,row,target)
    before=all_pg_rows(u)
    response=old_apply(u,row,data,'structural-old-apply')
    assert response.status_code==409,response.text
    assert all_pg_rows(u)==before
    assert recovery(u,row,'structural-old-apply').json()['status']=='NOT_OBSERVED'


@pytest.mark.parametrize('confirmation',[False,1,0,'true',None])
def test_structure_confirmation_is_literal_boolean_true(upgrade_case,confirmation):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic strict structural confirmation')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    data['confirm_structure_change']=confirmation
    before=all_pg_rows(u)
    response=apply(u,row,data,'structural-invalid-confirmation')
    assert response.status_code==422,response.text
    assert all_pg_rows(u)==before


def test_structure_digest_cas_refuses_changed_proof(upgrade_case):
    u=upgrade_case;row,old,p=complete_declared(u)
    target=publication(u,GOALS,source='1',name='Synthetic structural proof CAS')
    view,data=admit(u,row,target);assert view['application']['eligible'],view['application']
    digest=data['expected_structure_sha256'];data['expected_structure_sha256']='0'*64 if digest!='0'*64 else '1'*64
    before=all_pg_rows(u)
    response=apply(u,row,data,'structural-wrong-proof')
    assert response.status_code==409,response.text
    assert all_pg_rows(u)==before
    assert recovery(u,row,'structural-wrong-proof').json()['status']=='NOT_OBSERVED'


@pytest.mark.parametrize('no_current_output',[True,False])
def test_structural_adoption_requires_every_original_step_current_verified(upgrade_case,no_current_output):
    u=upgrade_case
    if no_current_output:row,old,p=declared_instance(u)
    else:row,old,p=complete_declared(u,finalize=False)
    target=publication(u,GOALS,source='1',name='Synthetic structure waits for original full verification')
    view,data=admit(u,row,target)
    assert not view['application']['eligible']
    assert 'CURRENT_VERIFIED_CASE_PLAN_REQUIRED' in view['application']['blockers'],view['application']
    before=all_pg_rows(u)
    response=apply(u,row,data,'structural-unverified-original')
    assert response.status_code==409,response.text
    assert all_pg_rows(u)==before
