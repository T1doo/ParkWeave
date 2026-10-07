"""Immutable catalog decision evidence and current-use guards on actual UUID PG.

Administrator source edits happen only in each test's isolated owner database.
No catalog application grant, release authority or original demo DB is used.
"""
import hashlib
import json
from uuid import UUID, uuid4

import pytest
import psycopg

from test_case_resources import link_fixture, group, post as legacy_bind
from test_controlled_plans import through, check, read as read_plan
from test_executor_receipts import receipt_fixture, act as receipt_action, ready, create as create_receipt
from test_preparation import preparation_fixture, headers
from test_resource_substitution_confirm import compared, confirm, body, authority_records
from test_resource_plan_binding import complete_digest
from test_case_lifecycle import read as read_local, act as local_action
from test_service_dispatches import offer


def document_sha(document):
    return hashlib.sha256(json.dumps(document,ensure_ascii=False,sort_keys=True,
                                    separators=(',',':')).encode()).hexdigest()


def decide(f,finished=False):
    p,old,dispatch,_=through(f,2)
    candidate=group(f);comparison=compared(f,p,candidate)
    request=body(candidate,comparison);key=uuid4().hex
    response=confirm(f,p,request,key=key)
    assert response.status_code==201,response.text
    event=response.json()['event']
    assert check(f,p,'P2').status_code==200
    assert check(f,p,'P3').status_code==200
    receipt=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],
                     headers=headers(f[2],'executor-a')).json()
    assert receipt['step']['state']=='AWAITING_RECEIPT'
    if finished:
        receipt=receipt_action(f,receipt,'SUBMIT').json()
        receipt=receipt_action(f,receipt,'ACKNOWLEDGE').json()
        assert check(f,p,'P4').status_code==200
    return p,old,candidate,event,request,key,dispatch,receipt


def alter_catalog(f,p):
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2'::jsonb) WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",
                  (UUID(p['preparation_id']),))


def read_binding(f,p,candidate):
    return compared(f,p,candidate)


def saved_record(f,event):
    with f[1].connect() as c:
        return c.execute('SELECT * FROM case_resource_links WHERE id=%s',(UUID(event['id']),)).fetchone()


def stale_after_material_recheck(f,p,candidate):
    alter_catalog(f,p)
    assert check(f,p,'P1').status_code==200
    plan=read_plan(f,p).json()
    assert plan['steps'][0]['state']=='CURRENT'
    assert plan['steps'][1]['state']!='CURRENT'
    assert plan['steps'][1]['can_check'] is False
    assert 'RESOURCE_CATALOG_DECISION_STALE' in plan['steps'][1]['issues']
    view=read_binding(f,p,candidate)
    assert view['history'][-1]['catalog_decision']['status']=='STALE'
    return plan,view


def test_saved_catalog_document_and_hash_remain_immutable_while_current_is_stale(link_fixture):
    f=link_fixture;p,_,candidate,event,_,_,_,_=decide(f,finished=True)
    authority=authority_records(f)
    immutable=event['snapshot']['binding_impact']['immutable_catalog']
    assert immutable['sha256']==document_sha(immutable['document'])
    assert immutable['source_revision']==immutable['document']['source']['revision']
    original=saved_record(f,event)
    current=read_binding(f,p,candidate)
    decision=current['history'][-1]['catalog_decision']
    assert decision['status']=='CURRENT'
    assert decision['saved_catalog_sha256']==decision['current_catalog_sha256']==immutable['sha256']
    assert decision['decision_ref']==event['snapshot']['binding_impact']['decision_ref']
    assert decision['decision_ref']['link_id']==event['id']
    alter_catalog(f,p)
    current=read_binding(f,p,candidate)
    decision=current['history'][-1]['catalog_decision']
    assert decision['status']=='STALE'
    assert decision['saved_catalog_sha256']==immutable['sha256']
    assert decision['current_catalog_sha256']!=immutable['sha256']
    assert decision['catalog_snapshot']==immutable
    assert 'RESOURCE_CATALOG_DECISION_STALE' in decision['issues']
    assert current['history'][-1]['record']==event
    assert saved_record(f,event)==original
    assert authority_records(f)==authority
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='preparation_catalog'):
        with f[0].connect() as c:
            c.execute('UPDATE preparation_catalog SET source=source')


@pytest.mark.parametrize('step',['P2','P3','P4'])
def test_new_material_check_cannot_turn_old_catalog_decision_into_current_step(link_fixture,step):
    f=link_fixture;p,_,candidate,event,_,_,_,_=decide(f,finished=True)
    authority=authority_records(f);original=saved_record(f,event)
    plan,_=stale_after_material_recheck(f,p,candidate)
    before=complete_digest(f)
    response=check(f,p,step,row=plan)
    assert response.status_code==409,response.text
    assert complete_digest(f)==before
    assert saved_record(f,event)==original
    assert authority_records(f)==authority


@pytest.mark.parametrize('entry',['dispatch','receipt','local_record'])
def test_stale_catalog_decision_blocks_existing_execution_entry_after_p1_recheck(link_fixture,entry):
    f=link_fixture;p,_,candidate,event,_,_,dispatch,receipt=decide(f,finished=entry=='local_record')
    authority=authority_records(f);original=saved_record(f,event)
    stale_after_material_recheck(f,p,candidate)
    local=read_local(f,p).json() if entry=='local_record' else None
    if local:
        assert 'RESOURCE_CATALOG_DECISION_STALE' in local['checks']['RESOURCE_RECHECK']
        assert local['can_revalidate'] is False
    before=complete_digest(f)
    if entry=='dispatch':
        response=offer(f,p,revision=dispatch['revision'])[0]
        assert 'controlled plan' in response.text
    elif entry=='receipt':
        response=receipt_action(f,receipt,'SUBMIT')
        assert 'controlled plan' in response.text
    else:
        response=local_action(f,p,local,'REVALIDATE')
    assert response.status_code==409,response.text
    assert complete_digest(f)==before
    assert saved_record(f,event)==original
    assert authority_records(f)==authority


def test_old_key_recovers_history_but_never_revalidates_old_catalog_decision(link_fixture):
    f=link_fixture;p,_,candidate,event,request,key,_,_=decide(f)
    original=saved_record(f,event);authority=authority_records(f)
    stale_after_material_recheck(f,p,candidate)
    before=complete_digest(f)
    response=confirm(f,p,request,key=key)
    assert response.status_code==201,response.text
    recovered=response.json()
    assert recovered['event']==event
    assert recovered['current']['status']==recovered['current']['source_status']=='NEEDS_RECHECK'
    assert recovered['current']['catalog_decision']['status']=='STALE'
    assert recovered['current']['catalog_decision']['saved_catalog_sha256']==event['snapshot']['binding_impact']['immutable_catalog']['sha256']
    assert 'RESOURCE_CATALOG_DECISION_STALE' in recovered['current']['reasons']
    assert complete_digest(f)==before
    assert saved_record(f,event)==original
    assert authority_records(f)==authority


def test_new_explicit_same_combo_decision_rebind_preserves_old_hash_and_occupancy(link_fixture):
    f=link_fixture;p,old,candidate,event,_,_,_,receipt=decide(f)
    original=saved_record(f,event);authority=authority_records(f)
    _,current=stale_after_material_recheck(f,p,candidate)
    assert current['comparison']['can_confirm'] is True
    response=confirm(f,p,body(candidate,current,reason='SYNTHETIC explicit new catalog decision'))
    assert response.status_code==201,response.text
    refreshed=response.json();new_event=refreshed['event']
    assert new_event['id']!=event['id'] and new_event['revision']==3
    assert new_event['combination_id']==event['combination_id']==candidate['id']
    document=new_event['snapshot']['binding_impact']['immutable_catalog']
    assert document['sha256']==document_sha(document['document'])
    assert document['sha256']!=event['snapshot']['binding_impact']['immutable_catalog']['sha256']
    assert refreshed['current']['catalog_decision']['status']=='CURRENT'
    assert saved_record(f,event)==original
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM case_resource_links').fetchone()['n']==3
        assert c.execute('SELECT count(*) n FROM resource_case_claims').fetchone()['n']==2
        assert [r['state'] for r in c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=ANY(%s) ORDER BY id',([UUID(old['id']),UUID(candidate['id'])],))]==['CONFIRMED','CONFIRMED']
    assert check(f,p,'P2').status_code==200
    assert check(f,p,'P3').status_code==200
    assert receipt_action(f,receipt,'SUBMIT').status_code==200
    assert authority_records(f)==authority


def test_directory_change_never_manufactures_authority_for_existing_unassigned_executor(link_fixture):
    f=link_fixture;p,_,candidate,event,_,_,_,_=decide(f)
    authority=authority_records(f)
    stale_after_material_recheck(f,p,candidate)
    response=f[3].get('/api/preparations/'+p['preparation_id']+'/resource-plan-binding',
      headers=headers(f[2],'unassigned'),params={'candidate_combination_id':candidate['id']})
    assert response.status_code==403
    assert authority_records(f)==authority
    assert saved_record(f,event)['snapshot']['binding_impact']==event['snapshot']['binding_impact']


def test_strict_catalog_decision_is_guarded_at_existing_entry_without_controlled_plan(link_fixture):
    f=link_fixture;p=ready(f);old=group(f)
    assert legacy_bind(f,p,old).status_code==201
    candidate=group(f);comparison=compared(f,p,candidate)
    response=confirm(f,p,body(candidate,comparison))
    assert response.status_code==201,response.text
    event=response.json()['event'];authority=authority_records(f)
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM controlled_plans').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==0
    alter_catalog(f,p)
    assert read_binding(f,p,candidate)['history'][-1]['catalog_decision']['status']=='STALE'
    before=complete_digest(f)
    response=create_receipt(f,p)[0]
    assert response.status_code==409,response.text
    assert complete_digest(f)==before
    assert authority_records(f)==authority
    assert saved_record(f,event)['snapshot']['binding_impact']==event['snapshot']['binding_impact']
