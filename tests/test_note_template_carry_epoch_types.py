"""Owned history proof refusals: strict epoch JSON types and complete original P1 material anchors."""
from copy import deepcopy
import pytest
from psycopg.types.json import Jsonb
from parkweave import template_migration as migration
from parkweave.template_candidate import sha
from test_note_template_carry import ready,request,apply,upgrade_case,link_fixture,receipt_fixture,preparation_fixture
from test_template_migration_independent import stored,facts,recovery
from test_template_upgrade import headers,confirmed
from test_service_case_steps import read as plan_read,adopt_body,adopt,verified
from test_preparation import add
from parkweave.store import digest
from test_case_opportunities import imported,get as opportunities,post as opportunity_post,body as opportunity_body
from test_source_change_adoption import preview as source_preview

@pytest.mark.parametrize('slot',['current_epochs','captured_epochs'])
@pytest.mark.parametrize('value',[True,1.0],ids=['bool','float'])
def test_rehashed_nested_epoch_version_types_are_rejected_by_history(upgrade_case,slot,value):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target);key='SYNTHETIC_epoch_type_history'
    result=apply(u,row,body,key);assert result.status_code==200,result.text
    plan=deepcopy(stored(u,row));event=plan['events'][-1];proof=event['template_upgrade']['note_carry']
    assert proof['materials'][slot][0]['version']==1
    proof['materials'][slot][0]['version']=value
    proof['sha256']=sha({k:v for k,v in proof.items() if k!='sha256'})
    event['template_upgrade']['request']['expected_note_carry_sha256']=proof['sha256']
    data=migration.NoteCarryApply.model_validate(event['template_upgrade']['request']);event['fingerprint']=migration.fingerprint(row['instance_id'],data)
    with u['f'][1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    before=facts(u)
    response=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert response.status_code==409, 'rehashed bool/float epoch version was accepted as integer in historical proof'
    assert plan_read(u['f'],p).status_code==409 and recovery(u,row,key).status_code==409
    assert stored(u,row)==plan and facts(u)==before


@pytest.mark.parametrize('damage',['need_summary_text','outline_label'])
def test_rehashed_forged_material_package_refused_against_original_p1(upgrade_case,damage):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target);key='SYNTHETIC_material_anchor'
    response=apply(u,row,body,key);assert response.status_code==200,response.text
    plan=deepcopy(stored(u,row));event=plan['events'][-1];proof=event['template_upgrade']['note_carry']
    if damage=='need_summary_text':
        material=next(m for m in proof['materials']['current'] if m['slot']=='need_summary')
        material['text']='SYNTHETIC forged summary never present at the original P1 verification'
        material['source_sha256']=digest(material['text'])
        next(m for m in proof['materials']['current_epochs'] if m['slot']=='need_summary')['source_sha256']=material['source_sha256']
    else:
        next(m for m in proof['materials']['current'] if m['slot']=='material_outline')['source_label']='SYNTHETIC forged outline label never observed'
    proof['sha256']=sha({k:v for k,v in proof.items() if k!='sha256'})
    event['template_upgrade']['request']['expected_note_carry_sha256']=proof['sha256']
    event['fingerprint']=migration.fingerprint(row['instance_id'],migration.NoteCarryApply.model_validate(event['template_upgrade']['request']))
    with u['f'][1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    business=facts(u)
    r=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert r.status_code==409,'rehashing carry/request/event must not manufacture the previously verified full material package'
    assert plan_read(u['f'],p).status_code==409 and recovery(u,row,key).status_code==409
    assert stored(u,row)==plan and facts(u)==business


def test_old_carry_uses_original_p1_prefix_after_real_later_material_verification(upgrade_case):
    u=upgrade_case;row,p,target=ready(u);_,body=request(u,row,target);key='SYNTHETIC_original_material_prefix'
    response=apply(u,row,body,key);assert response.status_code==200,response.text
    original=response.json()['event'];before=deepcopy(stored(u,row))
    imported(u['f'],p)
    changed=add(u['f'],p,slot='need_summary',text='SYNTHETIC a real later summary version after the recorded carry');assert changed.status_code==200,changed.text
    p=confirmed(u,row)
    current=plan_read(u['f'],p);assert current.status_code==200,current.text
    refreshed=opportunity_post(u['f'],p,opportunity_body(opportunities(u['f'],p).json(),'REFRESH'))
    assert refreshed.status_code==200,refreshed.text
    card=refreshed.json()['current']['cards'][0]
    preview=source_preview(u['f'],p,card);assert preview.status_code==200,preview.text
    assert preview.json()['can_adopt'],preview.json()
    adopted=adopt(u['f'],p,preview.json()['adoption']);assert adopted.status_code==201,adopted.text
    verified(u['f'],p,'P1')
    now=stored(u,row);assert now['steps'][0]['verified_sources']['preparation_sha256']!=before['steps'][0]['verified_sources']['preparation_sha256']
    assert now['events'][:len(before['events'])]==before['events']
    cold=recovery(u,row,key);assert cold.status_code==200,cold.text
    assert cold.json()['event']==original and plan_read(u['f'],p).status_code==200
