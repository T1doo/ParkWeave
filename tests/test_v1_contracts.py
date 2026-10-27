import copy
import pytest
from test_worker_gateway import runtime,auth


def action():
    return {'input_schema_ref':'Intake/0.1','output_schema_ref':'LocalCaseReceipt/1','dependencies':[],
            'limits':{'max_steps':1,'max_payload_bytes':16384},'prechecks':['CURRENT_AUTHORIZATION'],
            'postchecks':['LOCAL_RECORD_EXISTS'],'reconciliation':'LOCAL_TRANSACTION_ATOMIC'}


def service():
    return {'schema_version':'parkweave-domain/1.0-draft','service_id':'svc-intake','revision':'1','owner_org_id':'org-a',
            'title':'合成服务规格','service_kind':'LOCAL_INTAKE','validity':{'valid_from':'2026-01-01T00:00:00+00:00',
            'valid_until':'2099-01-01T00:00:00+00:00','timezone':'UTC'},'eligibility':'NOT_REQUIRED',
            'material_requirements':[],'resource_requirements':[],'action_bindings':[action()],
            'completion_checks':['LOCAL_RECORD_EXISTS'],'visibility':'OWN_ORGANIZATION',
            'handling_policy':{'accepting_org_id':'org-a','calendar_ref':None,'target_seconds':None,'target_source_ref':None,'pause_reasons':[]},
            'source_refs':[{'id':'synthetic-service-doc','kind':'SYNTHETIC','revision':'1'}],
            'reviewer_id':'fixture-a','publication':'REVIEWED_SYNTHETIC'}


def plan():
    return {'schema_version':'parkweave-domain/1.0-draft','request_ref':'req-1','plan_id':'plan-1','revision':'1',
            'required_goals':['g1'],'goal_coverage':{'g1':['s1']},'steps':[{'step_id':'s1','service_ref':'svc-intake',
             'revision':'1','action':action(),'depends_on':[],'responsible_role':'enterprise_operator','delivery':'LOCAL_CASE_RECORD',
             'input_mapping':{},'preconditions':[],'completion_checks':['LOCAL_RECORD_EXISTS']}],
            'dependency_lock':{'svc-intake':'1'},'unknowns':[],'resource_proposals':[],
            'approval_requirements':['CURRENT_AUTHORITY'],'validation_suite_ref':'at-foundation-1'}


def test_actual_v1_minimum_contracts_validate_but_cannot_publish_or_execute(runtime):
    api,owner,tokens,env=runtime
    r=api.post('/api/contracts/service',headers=auth(tokens),json=service());assert r.status_code==200,r.text
    assert r.json()['published'] is False and r.json()['validation_scope']=='STRUCTURE_ONLY'
    r=api.post('/api/contracts/plan',headers=auth(tokens),json=plan());assert r.status_code==200,r.text
    assert r.json()['executed'] is False
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0


@pytest.mark.parametrize('remove',['validity','handling_policy','material_requirements','resource_requirements','visibility','source_refs','reviewer_id'])
def test_v1_required_field_absence_rejected_without_effect(runtime,remove):
    data=service();data.pop(remove)
    r=runtime[0].post('/api/contracts/service',headers=auth(runtime[2]),json=data)
    assert r.status_code==422
    with runtime[1].connect() as c:assert c.execute('SELECT count(*) n FROM operations').fetchone()['n']==0


def test_v1_source_deadline_tool_and_rule_boundaries(runtime):
    api,owner,tokens,env=runtime
    for change in [{'reviewer_id':None}, {'handling_policy':service()['handling_policy']|{'target_seconds':60}},
                   {'eligibility':{'kind':'EQ','field':'region','expected':'x','script':'evil'}},
                   {'validity':{'valid_from':'2026-01-01T00:00:00','valid_until':'2099-01-01T00:00:00'}}]:
        assert api.post('/api/contracts/service',headers=auth(tokens),json=service()|change).status_code==422
    bad=service();bad['action_bindings'][0]['action_id']='python.exec'
    assert api.post('/api/contracts/service',headers=auth(tokens),json=bad).status_code==422
    nested={'kind':'EXISTS','field':'region'}
    for _ in range(9):nested={'kind':'AND','children':[nested]}
    assert api.post('/api/contracts/service',headers=auth(tokens),json=service()|{'eligibility':nested}).status_code==422
    bad_plan=plan();bad_plan['dependency_lock']={'svc-intake':'stale'}
    assert api.post('/api/contracts/plan',headers=auth(tokens),json=bad_plan).status_code==422
