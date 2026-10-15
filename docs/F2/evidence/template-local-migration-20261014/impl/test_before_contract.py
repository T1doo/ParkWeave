from test_template_upgrade import upgrade_case, instance, publication, check, snapshot
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from uuid import uuid4

def test_original_recheck_intent_does_not_apply_current_template(upgrade_case):
    u=upgrade_case
    row,old=instance(u)
    target=publication(u,source='2')
    from test_template_upgrade import choose
    before=snapshot(u)
    inspection=check(u,row,target).json()
    decision=choose(u,row,inspection,'REQUEST_RECHECK')
    assert decision.status_code==200,decision.text
    assert snapshot(u)==before
    current=u['consumer'].read(u['f'][2]['fixture-a'],row['instance_id'])
    assert current['binding']['release_id']==target['release_id'], 'PRODUCT GAP: original recheck intent leaves old immutable binding and unavailable original release'
