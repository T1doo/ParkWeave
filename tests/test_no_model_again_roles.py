"""Distinct original inputs/adoptions and fresh backend role reads; no browser."""
from copy import deepcopy
import json
from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.store import Store
from parkweave import case_step_assignments as cs,local_synthetic_demo as demo,local_resource_approval as local
from test_no_model_difference_observation import ordinary_local,staged,adopt,headers
from test_local_synthetic_demo import demo_inputs
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_service_case_steps import GOALS,verified
from test_resource_bundles import bundle
from test_case_resource_delivery import quoted,submit
from test_local_resource_approval import approved
from test_service_dispatches import offer,command as dispatch_command
from service_release_acceptance_support import case_history


def test_distinct_no_model_inputs_keep_exact_adoption_and_fresh_role_reads(ordinary_local,demo_inputs,tmp_path):
    f,_,_=ordinary_local;records=[]
    for label,goals in [('A设备维护',GOALS),('B员工培训',GOALS[:1])]:
        inputs=dict(goal='SYNTHETIC '+label,request='SYNTHETIC '+label+' 本次独立诉求',need_summary='SYNTHETIC '+label+' 新摘要',material_outline='SYNTHETIC '+label+' 新目录')
        p,body,candidate=staged(f,tmp_path/label,goals,inputs)
        if records:
            bad={**body,'candidate_id':records[0]['candidate']['candidate_id'],'expected_candidate_sha256':records[0]['candidate']['candidate_sha256'],'expected_verification_sha256':records[0]['candidate']['verification_sha256']}
            denied=adopt(f,p,bad);assert denied.status_code==409,denied.text
        response=adopt(f,p,body);assert response.status_code==201,response.text
        plan=response.json();assert plan['required_goals']==goals
        assert [s['state'] for s in plan['steps']]==(['PENDING','BLOCKED','BLOCKED','BLOCKED','BLOCKED'] if len(goals)==5 else ['PENDING'])
        records.append(dict(preparation=p,plan=plan,candidate=candidate,inputs=inputs))
        if len(records)==1:
            verified(f,p,'P1');hs,members=bundle(f);delivery=quoted(f,p,members);item,_=approved(f,p,delivery)
            response=submit(f,p,{**delivery,'approval_id':item['id']});assert response.status_code==201,response.text;verified(f,p,'P2')
            response=offer(f,p)[0];assert response.status_code==201,response.text
            response=dispatch_command(f,response.json(),'ACCEPT');assert response.status_code==200,response.text
            records[0]['accepted']=response.json();records[0]['history_before_B']=case_history(f[1],p['preparation_id'])
    a,b=records
    for key in ('preparation_id','case_id','run_id'):assert a['preparation'][key]!=b['preparation'][key]
    assert a['plan']['plan_id']!=b['plan']['plan_id'] and a['candidate']['candidate_id']!=b['candidate']['candidate_id']
    assert case_history(f[1],a['preparation']['preparation_id'])==a['history_before_B']
    _,cfg,_,_=demo_inputs;store=Store(f[0].dsn)
    pair=cs.from_environment(store,dict(PARKWEAVE_CASE_STEP_MODE=cs.LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=demo.PROFILE,PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=json.dumps(cfg)))
    app=create_app(store,case_step_assignments=pair,local_synthetic_demo=pair.local_synthetic_demo,local_resource_approval=local.LocalResourceApproval(store))
    reads=[]
    with TestClient(app) as cold:
        for actor in ('fixture-a','prep-specialist-fixture-a'):
            for record in records:
                path='/api/preparations/'+record['preparation']['preparation_id'];response=cold.get(path,headers=headers(f[2],actor));assert response.status_code==200,response.text
                value=response.json();assert value['preparation']['id']==record['preparation']['preparation_id']
                text=json.dumps(value,ensure_ascii=False);assert record['inputs']['need_summary'] in text and record['inputs']['material_outline'] in text
                other=b if record is a else a;assert other['inputs']['need_summary'] not in text
                reads.append(dict(actor=actor,path=path,response=value))
        for record in records:
            path='/api/preparations/'+record['preparation']['preparation_id'];response=cold.get(path+'/service-case-plan',headers=headers(f[2]));assert response.status_code==200,response.text
            assert response.json()['plan_id']==record['plan']['plan_id'] and response.json()['candidate_consumption']['candidate_id']==record['candidate']['candidate_id']
            if record is a:
                actual=cold.get(path+'/dispatch',headers=headers(f[2],'executor-a'));assert actual.status_code==200,actual.text
                assert actual.json()['dispatch_id']==a['accepted']['dispatch_id'] and actual.json()['assignment_valid_until']==a['accepted']['assignment_valid_until']
                receipt=cold.get('/api/executor-receipts/'+a['accepted']['receipt_step_id'],headers=headers(f[2],'executor-a'));assert receipt.status_code==200,receipt.text
                assert receipt.json()['step']['case_id']==a['preparation']['case_id'] and receipt.json()['current_receipt'] is None
                assert b['inputs']['need_summary'] not in actual.text+receipt.text
            else:
                denied=cold.get(path+'/dispatch',headers=headers(f[2],'executor-a'));assert denied.status_code==403 and '新摘要' not in denied.text
    (tmp_path/'distinct-inputs-fresh-roles.json').write_text(json.dumps(dict(records=records,fresh_backend_reads=reads,P1_P2_only_A_prerequisites=True,no_business_SQL_write=True,not_browser=True),ensure_ascii=False,indent=2,default=str)+'\n')
