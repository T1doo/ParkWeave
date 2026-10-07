"""Tool self-tests only; simulated responses are not ParkWeave integration PASS."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.case_fact_integration_contract import (
    ContractFailure, FactAPI, Request, assert_redacted, assert_historical_replay,
    assert_reconfirmation, assert_observed_invalidation, assert_recovery_generation,
    assert_eligible_before_invalidation, capture_eligibility, verify_refusals, checklist,
)


class Response:
    def __init__(self, status, body): self.status_code, self._body = status, body
    def json(self): return deepcopy(self._body)


def current_view():
    return dict(state='CURRENT', satisfied=True, revision=2, preparation_revision=5,
        source_sha256='a'*64, history=[{'revision':1},{'revision':2}])


def test_real_fastapi_unmounted_route_is_blocked_not_pass():
    with TestClient(FastAPI()) as client:
        report = FactAPI(client,'synthetic-id','PRIVATE_TEST_TOKEN').mount_probe()
    assert report == {'status':'BLOCKED','reason':'FACT_ROUTES_NOT_MOUNTED','http_status':404}


def test_recursive_redaction_accepts_opaque_descriptor_but_rejects_private_ledger_and_values():
    assert_redacted({'preparation':{'revision':3}, 'history':[{'public_status':{'state':'STALE','source_sha256':'a'*64}}]}, ['PRIVATE_SYNTHETIC_FACT_101'])
    for leaked in ({'nested':[{'fact_clarifications':{}}]}, {'history':[{'assertion_id':'private'}]},
                   {'safe_key':'PRIVATE_SYNTHETIC_FACT_101'}, {'sources':[{'value':42}]},
                   {'nested':{'choices':[]}}, {'safe':{'source_excerpt':'unselected text'}}):
        with pytest.raises(ContractFailure) as result: assert_redacted(leaked,['PRIVATE_SYNTHETIC_FACT_101'])
        assert 'PRIVATE_SYNTHETIC_FACT_101' not in str(result.value)


def test_historical_current_snapshot_cannot_override_actual_stale_view():
    response=Response(201,{'recovery':'HISTORICAL_COMMITTED_EVENT','current_decision_restored':False,
        'revision':3,'public_status':{'state':'CURRENT'}})
    stale=dict(current_view(),state='STALE',satisfied=False)
    assert_historical_replay(response,stale,3)
    with pytest.raises(ContractFailure):assert_historical_replay(response,current_view(),3)
    for wrong in ({'current_decision_restored':True},{'revision':4},{'recovery':'CURRENT'}):
        with pytest.raises(ContractFailure):assert_historical_replay(Response(201,response.json()|wrong),stale,3)


def test_invalidation_distinguishes_clock_rights_source_and_request_versions():
    before=current_view();stale=dict(before,state='STALE',satisfied=False)
    with pytest.raises(ContractFailure):assert_observed_invalidation(dict(before,satisfied=False),stale,'EXPIRED')
    assert_observed_invalidation(before,stale,'EXPIRED')
    assert_observed_invalidation(before,stale,'WRITE_REVOKED')
    assert_observed_invalidation(before,dict(stale,source_sha256='b'*64),'SOURCE')
    assert_observed_invalidation(before,dict(stale,source_sha256='b'*64,preparation_revision=6),'REQUEST')
    with pytest.raises(ContractFailure):assert_observed_invalidation(before,dict(stale,source_sha256='b'*64),'EXPIRED')
    with pytest.raises(ContractFailure):assert_observed_invalidation(before,dict(stale,revision=3),'WRITE_REVOKED')


def test_reconfirmation_requires_both_revisions_actual_review_reset_and_immutable_history():
    previous=dict(current_view(),state='STALE',satisfied=False)
    now=dict(previous,state='CURRENT',satisfied=True,revision=3,preparation_revision=6,
        authenticity='USER_ASSERTED_UNVERIFIED',qualification='NOT_EVALUATED',history=previous['history']+[{'revision':3}])
    event={'action':'CONFIRM_FACT_PURPOSE','revision':6,'state':'IN_PREPARATION'}
    generic={'preparation':{'revision':6,'state':'IN_PREPARATION','review_sha256':None}}
    assert_reconfirmation(event,previous,now,generic)
    for mutation in ({'preparation_revision':5},{'history':[{'rewritten':True}]},{'qualification':'APPROVED'}):
        with pytest.raises(ContractFailure):assert_reconfirmation(event,previous,now|mutation,generic)
    with pytest.raises(ContractFailure):assert_reconfirmation(event,previous,now,{'preparation':generic['preparation']|{'review_sha256':'old-review'}})


def requests():
    sha='a'*64
    prep='SYNTHETIC-prep';root='/api/preparations/'+prep
    plan={'plan_id':'SYNTHETIC-plan','preparation_id':prep,'case_id':'SYNTHETIC-case','run_id':'SYNTHETIC-run','steps':[{'adapter_id':'P'+str(n),'state':'VERIFIED'} for n in range(1,5)]}
    return [
        Request('P1_VERIFY',root+'/service-case-plan/commands','PRIVATE_TOKEN',{'action':'VERIFY','step_id':'p1','expected_revision':2,'expected_source_sha256':sha},
            precondition_path=root+'/service-case-plan',precondition={'preparation_id':prep,'revision':2,'steps':[{'id':'p1','adapter_id':'P1','allowed_actions':['VERIFY'],'source_sha256':sha}]}),
        Request('NEW_OFFER',root+'/dispatch','PRIVATE_TOKEN',{'expected_preparation_revision':5,'expected_dispatch_revision':0,'executor_id':'SYNTHETIC-executor'},
            precondition_path='/api/service-dispatches/catalog?preparation_id='+prep,precondition={'ready':True,'preparation_revision':5,'dispatch_revision':0,'executors':[{'id':'SYNTHETIC-executor'}]},predecessors=deepcopy(plan),predecessor_path=root+'/service-case-plan'),
        Request('OLD_SUBMIT','/api/executor-receipts/SYNTHETIC-step/commands','PRIVATE_TOKEN',{'action':'SUBMIT','expected_revision':1},
            precondition_path='/api/executor-receipts/SYNTHETIC-step',precondition={'is_current_step':True,'dependency':'CURRENT','step':{'id':'SYNTHETIC-step','preparation_id':prep,'case_id':'SYNTHETIC-case','run_id':'SYNTHETIC-run','state':'AWAITING_RECEIPT','revision':1}},predecessors=deepcopy(plan),predecessor_path=root+'/service-case-plan'),
        Request('P5_CLOSE',root+'/local-case/commands','PRIVATE_TOKEN',{'action':'CLOSE_LOCAL_RECORD','expected_revision':2,'expected_cycle':1,'expected_snapshot_sha256':sha},
            precondition_path=root+'/local-case',precondition={'preparation_id':prep,'case_id':'SYNTHETIC-case','can_close_local_record':True,'revision':2,'cycle':1,'current_snapshot_sha256':sha},predecessors=deepcopy(plan),predecessor_path=root+'/service-case-plan'),
    ]


def test_refusal_checks_all_original_commands_and_business_effects_not_only_http_status():
    class Client:
        status=409; effect=False
        def post(self,*args,**kwargs):
            if self.effect: state.append('unexpected effect')
            return Response(self.status,{'detail':'refused'})
    state=[];client=Client()
    assert len(verify_refusals(client,requests(),lambda:deepcopy(state)))==4
    client.effect=True
    with pytest.raises(ContractFailure):verify_refusals(client,requests(),lambda:deepcopy(state))
    client.effect=False
    for status in (200,404,500):
        client.status=status
        with pytest.raises(ContractFailure):verify_refusals(client,requests(),lambda:deepcopy(state))
    client.status=409
    with pytest.raises(ContractFailure):verify_refusals(client,requests()[:1],lambda:deepcopy(state))


def test_request_objects_never_repr_tokens_or_private_body():
    assert 'PRIVATE_TOKEN' not in repr(requests()[0])
    assert 'PRIVATE_TOKEN' not in repr(FactAPI(None,'id','PRIVATE_TOKEN'))


def test_cli_is_pending_checklist_not_network_or_integration_pass():
    import json
    script=Path(__file__).resolve().parents[1]/'scripts/case_fact_integration_contract.py'
    result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0
    report=json.loads(result.stdout)
    assert report==checklist() and report['integration_pass'] is False
    assert report['scope']=='PENDING_MAIN_LINE_BLACK_BOX_CONTRACT'


def test_unrelated_state_machine_refusals_without_ready_evidence_do_not_count_as_fact_gates():
    from scripts.case_fact_integration_contract import assert_eligible_before_invalidation
    items=requests()
    items[0].precondition=None
    with pytest.raises(ContractFailure):assert_eligible_before_invalidation(items[0])
    items=requests();items[1].precondition['ready']=False
    with pytest.raises(ContractFailure):assert_eligible_before_invalidation(items[1])
    items=requests();items[2].precondition['step']['state']='LOCAL_ACKNOWLEDGED'
    with pytest.raises(ContractFailure):assert_eligible_before_invalidation(items[2])
    items=requests();items[3].precondition['can_close_local_record']=False
    with pytest.raises(ContractFailure):assert_eligible_before_invalidation(items[3])
    items=requests();items[1].predecessors['steps'][1]['state']='PENDING'
    with pytest.raises(ContractFailure):assert_eligible_before_invalidation(items[1])


def test_unrelated_endpoint_case_or_read_origin_cannot_prove_original_gate_refusal():
    unknown=requests()[0];unknown.check='PRIVATE_TOKEN'
    with pytest.raises(ContractFailure) as result:assert_eligible_before_invalidation(unknown)
    assert 'PRIVATE_TOKEN' not in str(result.value)
    for index in range(4):
        item=requests()[index];item.path='/api/unrelated/commands'
        with pytest.raises(ContractFailure):assert_eligible_before_invalidation(item)
        item=requests()[index];item.precondition_path='/api/another-case'
        with pytest.raises(ContractFailure):assert_eligible_before_invalidation(item)
    for index in (1,2,3):
        item=requests()[index];item.predecessors['preparation_id']='OTHER-prep'
        with pytest.raises(ContractFailure):assert_eligible_before_invalidation(item)
        item=requests()[index];item.predecessor_path='/api/preparations/OTHER-prep/service-case-plan'
        with pytest.raises(ContractFailure):assert_eligible_before_invalidation(item)
    item=requests()[2];item.predecessors['case_id']='OTHER-case'
    with pytest.raises(ContractFailure):assert_eligible_before_invalidation(item)


def test_capture_reads_original_paths_before_validating_and_keeps_snapshots_private():
    item=requests()[2];original=deepcopy(item.precondition);plan=deepcopy(item.predecessors)
    class Client:
        def get(self,path,**kwargs):
            assert kwargs['headers']['Authorization']=='Bearer PRIVATE_TOKEN'
            return Response(200,original if path==item.precondition_path else plan)
    assert capture_eligibility(Client(),item,item.precondition_path,item.predecessor_path) is item
    original['step']['state']='CHANGED_AFTER_CAPTURE'
    assert item.precondition['step']['state']=='AWAITING_RECEIPT'


def test_recovery_requires_real_receipt_belonging_to_same_final_case_and_run():
    old={'step':{'id':'OLD-step','preparation_id':'prep','case_id':'case','run_id':'run',
                 'executor_id':'executor','preparation_revision':5},'current_receipt':{'id':'OLD-receipt'}}
    new={'step':old['step']|{'id':'NEW-step','preparation_revision':6,'state':'LOCAL_ACKNOWLEDGED'},
         'current_receipt':{'id':'NEW-receipt','step_id':'NEW-step','version':1}}
    final={'case':{'id':'case','state':'WAITING_CONFIRMATION'},'run_id':'run'}
    assert_recovery_generation(old,new,final)
    for wrong in ({'case':{'id':'OTHER-case','state':'WAITING_CONFIRMATION'}},{'run_id':'OTHER-run'}):
        with pytest.raises(ContractFailure):assert_recovery_generation(old,new,final|wrong)
    unrelated=deepcopy(new);unrelated['current_receipt']['step_id']='OLD-step'
    with pytest.raises(ContractFailure):assert_recovery_generation(old,unrelated,final)
