from test_template_upgrade import upgrade_case,instance,publication,check,choose,headers
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from uuid import uuid4

def body(u,row,target):
    v=check(u,row,target).json()
    assert choose(u,row,v,'REQUEST_RECHECK').status_code==200
    v=check(u,row,target).json();a=v['application']
    return dict(expected_instance_id=row['instance_id'],target_release_id=target['release_id'],expected_target_sha256=target['release_sha256'],expected_check_sha256=v['check_sha256'],expected_choice_revision=a['choice_revision'],expected_choice_event_sha256=a['choice_event_sha256'],expected_plan_id=a['plan_id'],expected_plan_revision=a['plan_revision'],expected_preparation_revision=a['preparation_revision'],expected_source_sha256=a['source_sha256'],reason='SYNTHETIC prove original global actor request key')

def test_two_instances_reuse_original_global_plan_key_guard(upgrade_case):
    u=upgrade_case;first,_=instance(u);second,_=instance(u);target=publication(u,source='2')
    one=body(u,first,target);two=body(u,second,target);key=uuid4().hex
    a=u['client'].post('/api/template-upgrade/'+first['instance_id']+'/apply',headers=headers(u['f'][2],key=key),json=one)
    b=u['client'].post('/api/template-upgrade/'+second['instance_id']+'/apply',headers=headers(u['f'][2],key=key),json=two)
    assert a.status_code==200,a.text
    assert b.status_code==409,b.text
    assert 'Case scope changed' in b.text
