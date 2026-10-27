"""Exact historical template adoption keys survive migration; other keys do not."""
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from test_template_upgrade import upgrade_case, instance, publication, check, choose, headers
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture


def apply_legacy(u):
    row,_=instance(u,legacy=True)
    target=publication(u,source='2')
    view=check(u,row,target).json()
    assert choose(u,row,view,'REQUEST_RECHECK').status_code==200
    view=check(u,row,target).json();a=view['application']
    data=dict(expected_instance_id=row['instance_id'],target_release_id=target['release_id'],
        expected_target_sha256=target['release_sha256'],expected_check_sha256=view['check_sha256'],
        expected_choice_revision=a['choice_revision'],expected_choice_event_sha256=a['choice_event_sha256'],
        expected_plan_id=a['plan_id'],expected_plan_revision=a['plan_revision'],
        expected_preparation_revision=a['preparation_revision'],expected_source_sha256=a['source_sha256'],
        reason='SYNTHETIC explicitly adopt while retaining the exact original historical key')
    response=u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],key=uuid4().hex),json=data)
    assert response.status_code==200,response.text
    return row


def test_migrated_original_legacy_adoption_goal_history(upgrade_case):
    u=upgrade_case;row=apply_legacy(u)
    result=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert result.status_code==200,result.text
    with u['f'][1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']
    assert plan['events'][0]['request_key']=='tc:'+row['instance_id']+':ADOPT_PLAN'


@pytest.mark.parametrize('damage',['arbitrary-colon','other-instance'])
def test_migrated_legacy_key_does_not_allow_other_colon_or_instance(upgrade_case,damage):
    u=upgrade_case;row=apply_legacy(u)
    # Explicit owned-fixture corruption: a historical request key must not be
    # normalized, repaired or reassigned to another instance by a history read.
    with u['f'][1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']
        plan['events'][0]['request_key']='tc:arbitrary:ADOPT_PLAN' if damage=='arbitrary-colon' else 'tc:'+str(uuid4())+':ADOPT_PLAN'
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    result=u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',headers=headers(u['f'][2]))
    assert result.status_code==409,result.text
    with u['f'][1].connect() as c:
        assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']==plan
