"""Actual owned synthetic PG/API material outputs; no policy acceptance claim."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4
from datetime import datetime,timedelta,timezone
import pytest
from parkweave import preparation as prep
from test_preparation import preparation_fixture, create, add, command, read, headers, counts
from test_case_fact_clarifications_integration import (
    seed_facts_through_original_api, declare, confirm, confirm_body, current_parent, post_fact, authority)

@pytest.fixture
def draft_fixture(preparation_fixture):
    f=preparation_fixture; parent,_,_=create(f,goal='SYNTHETIC 准备园区咨询的企业诉求摘要')
    selected=seed_facts_through_original_api(f)
    response=declare(f,parent); assert response.status_code==200,response.text
    parent=current_parent(f,parent)
    response=confirm(f,parent,confirm_body(f,parent,selected)); assert response.status_code==200,response.text
    return f,current_parent(f,parent),selected

def preview(f,parent,user='fixture-a'):
    return f[3].get('/api/preparations/'+parent['preparation_id']+'/material-draft',headers=headers(f[2],user))

def body(x):
    return dict(expected_preparation_revision=x['preparation_revision'],expected_source_sha256=x['source_sha256'],expected_reviewer_id=x['reviewer_id'],confirm_material_share=True)

def save(f,parent,data,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+parent['preparation_id']+'/material-draft',headers=headers(f[2],user,key or uuid4().hex),json=data)

def test_actual_brief_selected_values_missing_directory_persistence_and_independent_review(draft_fixture):
    f,parent,selected=draft_fixture; before=counts(f[1]); permissions=authority(f)
    x=preview(f,parent).json(); assert x['state']=='DRAFT'
    text=x['draft']['text']; assert 'PRIVATE_REGION_SELECTED' in text and '17' in text and 'PRIVATE_SERVICE_NEED_SELECTED' in text
    assert 'PRIVATE_CONFLICTING_REGION' not in text and 'PRIVATE_FACT_EXCERPT_' not in text
    assert all(s['fingerprint'] in text for s in x['selected_sources'])
    assert [m['state'] for m in x['material_checklist']]==['MISSING','MISSING'] and counts(f[1])==before
    r=save(f,parent,body(x)); assert r.status_code==201,r.text; parent=r.json()
    pack=read(f,parent).json(); material=pack['current_materials'][0]
    assert material['text']==text and material['source_kind']=='USER_STATEMENT' and material['authenticity']=='UNVERIFIED'
    assert material['material_draft_source']['source_current'] is True
    assert pack['preparation']['state']=='IN_PREPARATION' and pack['preparation']['review_sha256'] is None
    assert authority(f)==permissions
    missing=command(f,parent,'REVIEW','prep-specialist-fixture-a',reason='check actual pack'); assert missing.status_code==409
    parent=add(f,parent,'material_outline','SYNTHETIC 企业提供的咨询问题和材料目录，证明待确认').json()
    reviewed=command(f,parent,'REVIEW','prep-specialist-fixture-a',reason='independently check exact text and both versions'); assert reviewed.status_code==200,reviewed.text
    confirmed=command(f,reviewed.json(),'CONFIRM',reason='owner checks actual reviewed versions'); assert confirmed.status_code==200,confirmed.text
    assert read(f,confirmed.json()).json()['preparation']['state']=='LOCAL_CONFIRMED'
    run=f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2])).json()
    assert run['case']['state']=='NEEDS_INPUT' and confirmed.json()['qualification']=='NOT_EVALUATED'

@pytest.mark.parametrize('user',['prep-specialist-fixture-a','fixture-b','fixture-c'])
def test_other_role_or_tenant_cannot_read_or_save_private_brief(draft_fixture,user):
    f,parent,_=draft_fixture; x=preview(f,parent).json(); before=counts(f[1])
    assert preview(f,parent,user).status_code==403
    assert save(f,parent,body(x),user=user).status_code==403 and counts(f[1])==before

@pytest.mark.parametrize('change',[{'confirm_material_share':False},{'confirm_material_share':1},{'text':'forged summary'},{'expected_reviewer_id':'prep-specialist-fixture-b'}])
def test_explicit_exact_sharing_and_server_text_required(draft_fixture,change):
    f,parent,_=draft_fixture; x=preview(f,parent).json(); b=body(x);b.update(change);before=counts(f[1])
    assert save(f,parent,b).status_code in (409,422) and counts(f[1])==before

def test_no_selection_does_not_generate_a_brief_or_guess_required_policy_materials(preparation_fixture):
    f=preparation_fixture; parent,_,_=create(f); x=preview(f,parent).json()
    assert x['state']=='BLOCKED' and x['draft'] is None and not x['can_save'] and not x['policy_requirements_generated']

def test_new_input_changes_actual_text_old_material_stays_history_and_old_key_never_reactivates(draft_fixture):
    f,parent,selected=draft_fixture; x=preview(f,parent).json(); key=uuid4().hex; b=body(x)
    first=save(f,parent,b,key); assert first.status_code==201; oldtext=x['draft']['text'];parent=current_parent(f,parent)
    selected['service_need']=post_fact(f,'service_need','SYNTHETIC 新诉求：准备资源咨询材料，不承诺获批','changed-need')
    assert preview(f,parent).json()['state']=='BLOCKED'
    assert read(f,parent).json()['current_materials'][0]['material_draft_source']['source_current'] is False
    replay=save(f,parent,b,key); assert replay.status_code==201 and replay.json()['current_result'] is False
    response=confirm(f,parent,confirm_body(f,parent,selected)); assert response.status_code==200,response.text
    parent=current_parent(f,parent); new=preview(f,parent).json()
    assert new['draft']['text']!=oldtext and 'SYNTHETIC 新诉求' in new['draft']['text']
    assert read(f,parent).json()['current_materials'][0]['material_draft_source']['source_current'] is False
    assert save(f,parent,body(new)).status_code==201
    pack=read(f,parent).json(); assert len(pack['material_history'])==2 and pack['material_history'][0]['text']==oldtext
    assert pack['current_materials'][0]['version']==2 and pack['current_materials'][0]['material_draft_source']['source_current'] is True

def test_same_key_concurrent_recovery_one_version_and_fingerprint_conflict(draft_fixture):
    f,parent,_=draft_fixture; b=body(preview(f,parent).json()); key=uuid4().hex
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:save(f,parent,b,key),range(2)))
    assert [r.status_code for r in results]==[201,201]
    assert len(read(f,parent).json()['material_history'])==1
    changed=dict(b,expected_preparation_revision=b['expected_preparation_revision']+1)
    assert save(f,parent,changed,key).status_code==409

def test_different_keys_compete_for_one_exact_source_revision(draft_fixture):
    f,parent,_=draft_fixture; b=body(preview(f,parent).json())
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:save(f,parent,b),range(2)))
    assert sorted(r.status_code for r in results)==[201,409]
    assert len(read(f,parent).json()['material_history'])==1

@pytest.mark.parametrize('mutation',['material','catalog','reviewer'])
def test_source_or_receiver_changes_refuse_old_candidate_without_write(draft_fixture,mutation):
    f,parent,_=draft_fixture; b=body(preview(f,parent).json())
    if mutation=='material': add(f,parent,'material_outline','SYNTHETIC changed directory')
    else:
        with f[1].connect() as c:
            if mutation=='catalog': c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"changed\"')")
            else: c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='prep-specialist-fixture-a' AND capability='READ'")
    before=counts(f[1]); assert save(f,parent,b).status_code==409 and counts(f[1])==before

def test_actual_fact_deadline_during_event_work_rolls_back_entire_append(draft_fixture,monkeypatch):
    f,parent,selected=draft_fixture
    with f[1].connect() as c:
        c.execute('UPDATE fact_assertions SET valid_until=%s WHERE id=%s',(datetime.now(timezone.utc)+timedelta(seconds=3),selected['region']))
    response=confirm(f,parent,confirm_body(f,parent,selected)); assert response.status_code==200,response.text
    parent=current_parent(f,parent); b=body(preview(f,parent).json());before=counts(f[1]); original=prep.event
    def expire(c,p,row,*args,**kwargs):
        result=original(c,p,row,*args,**kwargs)
        if kwargs.get('material_draft'): c.execute('SELECT pg_sleep(3.1)')
        return result
    monkeypatch.setattr(prep,'event',expire)
    r=save(f,parent,b);assert r.status_code==409 and counts(f[1])==before
    assert preview(f,parent).json()['state']=='BLOCKED'


def test_slot_correction_is_submitted_never_automatically_resolved(draft_fixture):
    f,parent,_=draft_fixture
    r=command(f,parent,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='Please provide current need summary AND directory',correction_slots=['need_summary','material_outline']);assert r.status_code==200
    parent=r.json(); assert save(f,parent,body(preview(f,parent).json())).status_code==201
    pack=read(f,parent).json(); assert pack['preparation']['state']=='CHANGES_REQUESTED'
    corrections=f[3].get('/api/preparations/'+parent['preparation_id']+'/material-corrections',headers=headers(f[2])).json()
    assert {t['status'] for t in corrections['active_targets']}=={'REQUESTED','SUBMITTED_FOR_REVIEW'}
    assert command(f,current_parent(f,parent),'REVIEW','prep-specialist-fixture-a',reason='cannot skip directory correction').status_code==409


def test_restored_field_authority_does_not_restore_old_material_source(draft_fixture):
    f,parent,_=draft_fixture; b=body(preview(f,parent).json());key=uuid4().hex
    assert save(f,parent,b,key).status_code==201
    with f[1].connect() as c:
        c.execute("UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'")
    assert save(f,parent,b,key).status_code==403
    with f[1].connect() as c:
        c.execute("UPDATE field_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'")
    assert preview(f,parent).json()['state']=='BLOCKED'
    assert read(f,parent).json()['current_materials'][0]['material_draft_source']['source_current'] is False
    assert save(f,parent,b,key).json()['current_result'] is False


def test_new_draft_reserves_exact_review_and_confirm_capacity(draft_fixture):
    f,parent,_=draft_fixture
    with f[1].connect() as c: c.execute('UPDATE preparations SET revision=62 WHERE id=%s',(parent['preparation_id'],))
    x=preview(f,parent).json();assert not x['can_save'] and 'RESERVE_REVIEW_AND_CONFIRM_HISTORY_CAPACITY' in x['issues']


@pytest.mark.parametrize('outline_exists',[False,True])
def test_capacity_accounts_for_missing_outline_before_review_and_confirmation(draft_fixture,outline_exists):
    f,parent,_=draft_fixture
    if outline_exists: parent=add(f,parent,'material_outline','SYNTHETIC existing owner directory').json()
    with f[1].connect() as c: c.execute('UPDATE preparations SET revision=61 WHERE id=%s',(parent['preparation_id'],))
    x=preview(f,parent).json();assert x['can_save'] is outline_exists
    assert x['required_followup_revisions']==(2 if outline_exists else 3)


def test_reconfirmed_new_facts_cannot_review_or_confirm_old_generated_brief(draft_fixture):
    f,parent,selected=draft_fixture
    assert save(f,parent,body(preview(f,parent).json())).status_code==201
    parent=current_parent(f,parent);parent=add(f,parent,'material_outline','SYNTHETIC own directory').json()
    selected['service_need']=post_fact(f,'service_need','SYNTHETIC corrected request requiring a changed actual brief','new-service-need')
    assert confirm(f,parent,confirm_body(f,parent,selected)).status_code==200
    parent=current_parent(f,parent);before=counts(f[1])
    assert command(f,parent,'REVIEW','prep-specialist-fixture-a',reason='old text must not become current through new fact selection').status_code==409
    assert command(f,parent,'CONFIRM',reason='old brief cannot be confirmed').status_code==409
    assert counts(f[1])==before
    readiness=f[3].get('/api/preparations/'+parent['preparation_id']+'/readiness',headers=headers(f[2])).json()
    assert readiness['current_inputs']['local_preparation_truth']=='UNKNOWN'
    new=preview(f,parent).json();assert new['can_save'] and 'corrected request' in new['draft']['text']
    assert save(f,parent,body(new)).status_code==201
    parent=current_parent(f,parent)
    checked=command(f,parent,'REVIEW','prep-specialist-fixture-a',reason='review exact changed draft and own directory');assert checked.status_code==200,checked.text
    assert command(f,checked.json(),'CONFIRM',reason='owner confirms exact changed current pack').status_code==200
