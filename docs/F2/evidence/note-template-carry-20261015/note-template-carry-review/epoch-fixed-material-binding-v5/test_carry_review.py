"""Independent WIP API/owned-PG fixtures and pure historical refusal checks.

Product loaded only from ../source-wip-v1; no tracked test/source edits.
"""
from copy import deepcopy
import json
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
    (HERE/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')


def test_actual_success_receipt_strict_epoch_types_and_frozen_history(upgrade_case):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target)
    response=apply(u,row,body);assert response.status_code==200,response.text
    with u['f'][1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
    assert plans._recovery_proofs(parent)
    results=[]
    for label in ['current_need_summary_forged','current_outline_kind_forged','captured_need_summary_forged']:
        candidate=deepcopy(parent);plan=candidate['service_case_plan'];event=plan['events'][-1];patch=event['template_upgrade'];proof=patch['note_carry']
        if label=='current_need_summary_forged':
            target=next(m for m in proof['materials']['current'] if m['slot']=='need_summary')
            target['text']='SYNTHETIC arbitrary current summary that was never used by actual P1 VERIFY'
            from parkweave.store import digest
            target['source_sha256']=digest(target['text'])
            epoch=next(m for m in proof['materials']['current_epochs'] if m['slot']=='need_summary');epoch['source_sha256']=target['source_sha256']
        elif label=='current_outline_kind_forged':
            target=next(m for m in proof['materials']['current'] if m['slot']=='material_outline')
            target['source_label']='SYNTHETIC different outline label never present in actual source'
        else:
            target=proof['materials']['captured_epochs'][0];target['source_sha256']='a'*64
        proof['sha256']=migration.sha({k:v for k,v in proof.items() if k!='sha256'})
        patch['request']['expected_note_carry_sha256']=proof['sha256']
        event['fingerprint']=migration.fingerprint(row['instance_id'],migration.NoteCarryApply.model_validate(patch['request']))
        try:plans._recovery_proofs(candidate)
        except Conflict:rejected=True
        else:rejected=False
        results.append(dict(case=label,expected_rejected=True,actual_rejected=rejected))
    record('historical-material-binding-matrix',dict(actual_successful_PG_API_setup=True,pure_mutation_checks=results,no_PG_tampering=True))
    assert all(r['actual_rejected'] for r in results),results


