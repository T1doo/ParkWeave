"""Owned fixture historical corruption: rehashing never normalizes JSON types."""
from copy import deepcopy
import pytest
from psycopg.types.json import Jsonb
from parkweave import template_migration as migration
from parkweave.template_candidate import sha
from test_note_template_carry import ready,request,apply,upgrade_case,link_fixture,receipt_fixture,preparation_fixture
from test_template_migration_independent import stored,facts,recovery
from test_template_upgrade import headers
from test_service_case_steps import read as plan_read

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
