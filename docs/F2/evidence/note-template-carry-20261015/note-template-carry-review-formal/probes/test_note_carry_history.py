"""Independent WIP API/owned-PG fixtures and pure historical refusal checks.

Frozen shared source loaded by the formal runner; no tracked source/test edits.
Mature legacy fixture has five required goals and P1-P5; six-goal acceptance is separate.
"""
from copy import deepcopy
import json,os
from pathlib import Path
from uuid import uuid4

from parkweave import template_migration as migration, note_template_carry as carry
from parkweave import service_case_steps as plans
from parkweave.store import Conflict
from test_note_template_carry import ready,request,apply
from test_template_upgrade import upgrade_case,headers,publication,GOALS,check
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture,act as receipt_act
from test_preparation import preparation_fixture,command as prepare,add,read as prep_read
from test_template_migration_independent import stored,facts,recovery
from test_plan_source_conflicts import edit,read as note_read,changed
from test_manual_content_continuation import send as note_send
from test_source_change_adoption import preview,adopt
from test_service_case_steps import verified

HERE=Path(__file__).resolve().parent


def record(name,value):
    (HERE/(os.environ['NOTE_CARRY_REVIEW_WINDOW']+'-'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def test_actual_success_receipt_strict_epoch_types_and_frozen_history(upgrade_case):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target)
    response=apply(u,row,body);assert response.status_code==200,response.text
    with u['f'][1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
    assert plans._recovery_proofs(parent)
    results=[]
    cases=['current_epoch_bool','current_epoch_float','captured_epoch_bool','captured_epoch_float',
           'current_summary_text','current_outline_label','current_outline_kind','note_body',
           'proof_version_bool','proof_version_unknown','source_changed_integer','action_grant_integer',
           'plan_steps_hash','ledger_prefix_hash','prior_release_source_hash','partition',
           'check_hash','extra_field','proof_sha_only','missing_proof']
    for label in cases:
        candidate=deepcopy(parent);plan=candidate['service_case_plan'];event=plan['events'][-1];patch=event['template_upgrade'];proof=patch['note_carry']
        if label in ('current_epoch_bool','current_epoch_float','captured_epoch_bool','captured_epoch_float'):
            key='current_epochs' if label.startswith('current') else 'captured_epochs'
            assert proof['materials'][key][0]['version']==1
            proof['materials'][key][0]['version']=True if label.endswith('bool') else 1.0
        elif label=='current_summary_text':
            item=next(m for m in proof['materials']['current'] if m['slot']=='need_summary')
            item['text']='SYNTHETIC arbitrary material not in actual original P1 verification'
            from parkweave.store import digest
            item['source_sha256']=digest(item['text'])
            epoch=next(m for m in proof['materials']['current_epochs'] if m['slot']=='need_summary');epoch['source_sha256']=item['source_sha256']
        elif label in ('current_outline_label','current_outline_kind'):
            item=next(m for m in proof['materials']['current'] if m['slot']=='material_outline')
            if label.endswith('label'):item['source_label']='SYNTHETIC false original source label'
            else:item['source_kind']='DOCUMENT_EXCERPT' if item['source_kind']=='USER_STATEMENT' else 'USER_STATEMENT'
        elif label=='note_body':
            note=next(iter(proof['notes'].values()));note['text']+='SYNTHETIC changed manual'
            from parkweave.store import digest
            note['text_sha256']=digest(note['text'])
        elif label=='proof_version_bool':proof['version']=True
        elif label=='proof_version_unknown':proof['version']=2
        elif label=='source_changed_integer':proof['source_changed']=0
        elif label=='action_grant_integer':proof['case_versions']['action_grant_epochs'][0]['active']=1
        elif label=='plan_steps_hash':proof['plan_ref']['steps_sha256']='a'*64
        elif label=='ledger_prefix_hash':proof['ledger']['sha256']='a'*64
        elif label=='prior_release_source_hash':proof['previous_release']['source_sha256']='a'*64
        elif label=='partition':proof['affected']=proof['preserved'];proof['preserved']=[]
        elif label=='check_hash':proof['check_sha256']='a'*64
        elif label=='extra_field':proof['permission']=True
        proof['sha256']=migration.sha({k:v for k,v in proof.items() if k!='sha256'})
        if label not in ('proof_sha_only','missing_proof'):
            patch['request']['expected_note_carry_sha256']=proof['sha256']
            event['fingerprint']=migration.fingerprint(row['instance_id'],migration.NoteCarryApply.model_validate(patch['request']))
        if label=='proof_sha_only':proof['case_versions']['case_epoch']='999999'
        if label=='missing_proof':del patch['note_carry']
        try:plans._recovery_proofs(candidate)
        except Conflict:rejected=True
        else:rejected=False
        results.append(dict(case=label,expected_rejected=True,actual_rejected=rejected))
    record('historical-20-mutation-matrix',dict(actual_successful_PG_API_setup=True,pure_mutation_checks=results,no_PG_tampering=True,fixture_required_goal_count=len(parent['service_case_plan']['required_goals'])))
    assert all(r['actual_rejected'] for r in results),results


def test_real_v2_material_continue_first_carry_then_edit_reconfirm_next_hop(upgrade_case):
    from test_case_resources import get as resource_read,post as resource_link
    from test_service_dispatches import offer,command as dispatch_command
    from test_case_lifecycle import read as local_read,act as local_command
    u=upgrade_case;row,p,target=ready(u);f=u['f'];manual=next(iter(stored(u,row)['owner_amendments'].values()))['text']
    # The fixture's new publication does not affect actual material commands.
    current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    reopened=prepare(f,current,'REOPEN',reason='SYNTHETIC real source change before v2 carry');assert reopened.status_code==200,reopened.text
    incoming='SYNTHETIC review literal exact condition\n  preserve actual source spaces  '
    current,card=changed(f,reopened.json(),text=incoming)
    v=note_read(f,p,card);assert v.status_code==200,v.text;v=v.json()
    merged=manual+'\n'+v['source']['text']
    result=note_send(f,p,v,'MERGE_NOTE',merged);assert result.status_code==200,result.text
    assert result.json()['receipt']['plan_note']['version']==2
    source=preview(f,p,card);assert source.status_code==200 and source.json()['can_adopt'],source.text
    adopted=adopt(f,p,source.json()['adoption']);assert adopted.status_code==201,adopted.text
    current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    reviewed=prepare(f,current,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC actual replacement review');assert reviewed.status_code==200,reviewed.text
    confirmed=prepare(f,reviewed.json(),'CONFIRM',reason='SYNTHETIC owner replacement confirmed');assert confirmed.status_code==200,confirmed.text
    verified(f,p,'P1')
    link=resource_read(f,p).json();old=link['current']['record']
    current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    linked=resource_link(f,current,dict(id=old['combination_id']),revision=link['link_revision']);assert linked.status_code==201,linked.text
    verified(f,p,'P2')
    with f[1].connect() as c:dispatch_id=str(c.execute('SELECT id FROM service_dispatches WHERE preparation_id=%s',(row['preparation_id'],)).fetchone()['id'])
    dispatch=f[3].get('/api/service-dispatches/'+dispatch_id,headers=headers(f[2],'prep-specialist-fixture-a'));assert dispatch.status_code==200,dispatch.text
    current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id']);value=dispatch.json()
    offered=offer(f,current,revision=value['revision'],recovery_receipt_step_id=value['recovery_receipt_step_id'])[0];assert offered.status_code==201,offered.text
    accepted=dispatch_command(f,offered.json(),'ACCEPT');assert accepted.status_code==200,accepted.text
    verified(f,p,'P3')
    receipt=f[3].get('/api/executor-receipts/'+accepted.json()['receipt_step_id'],headers=headers(f[2],'executor-a'));assert receipt.status_code==200,receipt.text
    submitted=receipt_act(f,receipt.json(),'SUBMIT');assert submitted.status_code==200,submitted.text
    acknowledged=receipt_act(f,submitted.json(),'ACKNOWLEDGE');assert acknowledged.status_code==200,acknowledged.text
    verified(f,p,'P4')
    local=local_read(f,p);assert local.status_code==200,local.text
    rechecked=local_command(f,p,local.json(),'REVALIDATE');assert rechecked.status_code==200,rechecked.text
    verified(f,p,'P5')
    before=deepcopy(stored(u,row));business=facts(u);v,body=request(u,row,target);assert v['application']['note_carry']['eligible'],v['application']['note_carry']
    key=uuid4().hex;first=apply(u,row,body,key);assert first.status_code==200,first.text
    assert stored(u,row)['owner_amendments']==before['owner_amendments'] and facts(u)==business
    edit(f,p,merged+'\nSYNTHETIC later owner note')
    # Original material continuation must be possible through the real current
    # card. The upgrade must never waive this existing note re-confirmation.
    from test_case_opportunities import get as opportunities,post as opportunity_post,body as opportunity_body
    refreshed=opportunity_post(f,p,opportunity_body(opportunities(f,p).json(),'REFRESH'));assert refreshed.status_code==200,refreshed.text
    card=next(c for c in refreshed.json()['current']['cards'] if c['is_latest_generation'])
    value=note_read(f,p,card);assert value.status_code==200,value.text;value=value.json()
    record('v2-post-carry-edit-view',value)
    assert 'KEEP_AND_CONTINUE' in value['action_requests'],value
    continued=note_send(f,p,value,'KEEP_AND_CONTINUE');assert continued.status_code==200,continued.text
    target2=publication(u,GOALS,'1','SYNTHETIC second actual v2 carry')
    v,body2=request(u,row,target2);assert v['application']['note_carry']['eligible'],v['application']['note_carry']
    second_business=facts(u)
    second=apply(u,row,body2);assert second.status_code==200,second.text
    assert facts(u)==second_business
    old=recovery(u,row,key);assert old.status_code==200 and old.json()['event']==first.json()['event'],old.text
    assert stored(u,row)['events'][:len(before['events'])]==before['events']
    record('v2-material-carry-chain',dict(material_version2=True,proof_version2=True,original_local_ADOPT=True,original_P1_P5_VERIFY=True,first_carry=True,post_carry_edit=True,original_reconfirmation=True,next_hop=True,first_key_cold_GET=True,each_carry_immediate_business_snapshot_equal=True,fixture_required_goal_count=len(before['required_goals'])))

