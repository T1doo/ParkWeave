import json
from pathlib import Path
from test_partial_service_plan import setup_partial
from test_case_resources import link_fixture,group,post as link
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_service_case_steps import adopt,adopt_body,command,read
from test_service_dispatches import offer

def test_reject_unselected_offer_preserves_verified_selected_p2(link_fixture):
    f=link_fixture;p=setup_partial(f,'LOCAL_CASE_RECORD_RECHECK',{'excluded_roles':['service_executor']})
    assert adopt(f,p,adopt_body(f,p,partial_adoption=True)).status_code==201
    assert command(f,p,'P1').status_code==200
    g=group(f);assert link(f,p,g).status_code==201
    assert command(f,p,'P2').status_code==200
    with f[1].connect() as c:before=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
    r=offer(f,p)[0]
    with f[1].connect() as c:after=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
    proof=dict(source_sha='666d1c70cd3f620ce8fad18d0c0c4f6521b35390',response_status=r.status_code,response=r.json(),before_steps=[dict(adapter=x['adapter_id'],invalidated=x['invalidated'],coordination_state=x['coordination_state']) for x in before['steps']],after_steps=[dict(adapter=x['adapter_id'],invalidated=x['invalidated'],coordination_state=x['coordination_state']) for x in after['steps']],events_unchanged=before['events']==after['events'],plan_unchanged=before==after)
    Path('.runtime/partial-plan-20261013/independent/gate-rejection/actual.json').write_text(json.dumps(proof,indent=2)+'\n')
    assert r.status_code==409,r.text
    assert after==before,'Unselected OFFER rejection must preserve selected P1/P2 verification'
