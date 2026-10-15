from test_global_key import *

def test_migrated_original_legacy_adoption_goal_history(upgrade_case):
    u=upgrade_case;row,_=instance(u,legacy=True);target=publication(u,source='2')
    data=body(u,row,target)
    response=u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],key=uuid4().hex),json=data)
    assert response.status_code==200,response.text
    result=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert result.status_code==200,result.text

import pytest
from copy import deepcopy
from psycopg.types.json import Jsonb

@pytest.mark.parametrize('damage',['arbitrary-colon','other-instance'])
def test_migrated_legacy_key_does_not_allow_other_colon_or_instance(upgrade_case,damage):
    u=upgrade_case;row,_=instance(u,legacy=True);target=publication(u,source='2');data=body(u,row,target)
    response=u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],key=uuid4().hex),json=data)
    assert response.status_code==200,response.text
    with u['f'][1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']
        plan['events'][0]['request_key']='tc:arbitrary:ADOPT_PLAN' if damage=='arbitrary-colon' else 'tc:'+str(uuid4())+':ADOPT_PLAN'
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    result=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert result.status_code==409,result.text
    with u['f'][1].connect() as c:assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']==plan
