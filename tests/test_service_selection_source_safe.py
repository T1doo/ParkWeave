"""Final-save source change is a known rejection; original attempt never resends."""
from copy import deepcopy
from uuid import uuid4

import pytest

from parkweave import service_selection_candidates as selections
from parkweave.store import Conflict, Store
from test_preparation import preparation_fixture, add
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_candidates import arrangement, planner, run
from service_release_acceptance_support import authority_snapshot, case_history


def test_final_source_changed_safe_attempt_has_no_candidate_and_original_key_never_calls_model_twice(capability_catalog):
    a=capability_catalog;f,parent,capture,_=arrangement(a);calls=[];key=uuid4().hex
    before=case_history(f[1],parent['preparation_id']);authority=authority_snapshot(f[1])
    material_commit=[]
    def changed():
        reply=add(f,parent,text='SYNTHETIC explicit material change during offline model response')
        assert reply.status_code==200,reply.text
        material_commit.append(reply.json())
    model=planner(calls,changed)
    with pytest.raises(Conflict):run(a,f,parent,capture,key,model)
    assert len(calls)==1 and len(material_commit)==1
    after=case_history(f[1],parent['preparation_id'])
    assert after['cases']==before['cases'] and after['runs']==before['runs']
    assert after['service_dispatches']==before['service_dispatches']
    assert after['service_receipt_steps']==before['service_receipt_steps']
    assert after['case_resource_links']==before['case_resource_links']
    assert authority_snapshot(f[1])==authority
    saved=deepcopy(after['preparations'][0]['planning_previews'])
    assert len(saved)==1
    assert saved[0]['planner_attempt']['state']=='FAILED_SAFE'
    assert saved[0]['planner_attempt']['outcome']=='SOURCE_OR_ATTEMPT_CHANGED'
    assert 'candidate' not in saved[0]
    assert saved[0]['document']['source_sha256']==capture.expected_source_sha256
    for _ in range(2):
        recovered=selections.read(Store(f[0].dsn),f[2]['fixture-a'],parent['preparation_id'],key=key,catalog=a['catalog'])
        assert recovered['status']=='FAILED_SAFE' and recovered['items']==[]
        assert recovered['attempts'][0]['outcome']=='SOURCE_OR_ATTEMPT_CHANGED'
    repeated=run(a,f,parent,capture,key,model)
    assert repeated['status']=='FAILED_SAFE' and repeated['outcome']=='SOURCE_OR_ATTEMPT_CHANGED'
    assert len(calls)==1
    assert case_history(f[1],parent['preparation_id'])==after
    assert authority_snapshot(f[1])==authority
