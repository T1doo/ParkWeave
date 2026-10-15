"""Exact historical employees references, independent of current source rows."""
from copy import deepcopy
import pytest
from test_fact_history_read_source import sample
from parkweave import employees_fact_provenance as provenance, case_fact_clarifications as facts
from parkweave.service_case_steps import Adopt,_adopt_request


def fixture():
    parent,principal,receipts,rows,applicable,now=sample()
    descriptor=facts.public_status(facts._result(parent['fact_clarifications'],'CURRENT',(),parent['fact_clarifications']['events'][-1]['source_sha256']))
    descriptor['descriptor_sha256']=facts._hash(descriptor)
    return parent,descriptor


def sources(descriptor):return {'P1':{'fact_clarification':deepcopy(descriptor),'preparation_revision':3}}


def test_same_descriptor_preserves_selected_assertion_and_no_private_values():
    parent,descriptor=fixture();original=deepcopy(parent)
    proof,_=provenance.project(parent,sources(descriptor),sources(descriptor))
    assert parent==original and proof['selected_changed'] is False and proof['aggregate_changed'] is False
    node=proof['before']
    assert node==proof['current'] and node['assertion_revision']==1
    assert not {'value','source_excerpt','source_snapshot','source_ref','unit'}&set(node)
    assert node['authenticity']=='USER_ASSERTED_UNVERIFIED'


@pytest.mark.parametrize('mutation',['missing_decision','wrong_sha','descriptor_sha','source_sha','duplicate_choice','bad_revision','bad_value','bad_row_keys','bad_row_uuid','bad_utc','unsupported_source','missing_row','duplicate_row','wrong_field','wrong_owner','wrong_receipt_decision','scalar_snapshot','bool_ledger_version'])
def test_historical_detail_is_never_filled_from_current(mutation):
    parent,descriptor=fixture();event=parent['fact_clarifications']['events'][-1]
    if mutation=='missing_decision':descriptor['decision_ref']='00000000-0000-0000-0000-000000000001'
    elif mutation=='wrong_sha':descriptor['decision_sha256']='a'*64
    elif mutation=='descriptor_sha':descriptor['descriptor_sha256']='b'*64
    elif mutation=='source_sha':descriptor['source_sha256']='c'*64
    elif mutation=='duplicate_choice':event['choices'][1]=deepcopy(event['choices'][0])
    elif mutation=='bad_revision':event['source_snapshot']['sources'][1]['revision']=True
    elif mutation=='bad_value':event['source_snapshot']['sources'][1]['value']=True
    elif mutation=='bad_row_keys':event['source_snapshot']['sources'][1]['new']='unregistered'
    elif mutation=='bad_row_uuid':event['source_snapshot']['sources'][1]['id']='not-a-uuid'
    elif mutation=='bad_utc':event['source_snapshot']['sources'][1]['valid_from']='2026-10-11T00:00:00'
    elif mutation=='unsupported_source':event['source_snapshot']['sources'][1]['source_kind']='DOCUMENT_EXTRACT_SYNTHETIC'
    elif mutation=='missing_row':event['source_snapshot']['sources'].pop(1)
    elif mutation=='duplicate_row':event['source_snapshot']['sources'].append(deepcopy(event['source_snapshot']['sources'][1]))
    elif mutation=='wrong_field':event['source_snapshot']['sources'][1]['field_name']='region'
    elif mutation=='wrong_owner':parent['owner_id']='other-owner'
    elif mutation=='wrong_receipt_decision':event['actor_id']='other-owner'
    elif mutation=='scalar_snapshot':event['source_snapshot']=False
    elif mutation=='bool_ledger_version':parent['fact_clarifications']['version']=True
    # Rehash whole historical envelope: semantic/type checks still reject.
    if mutation not in ('missing_decision','wrong_sha','descriptor_sha','source_sha','bool_ledger_version'):
        event['source_sha256']=facts._hash(event['source_snapshot'])
        event['decision_sha256']=facts._hash({k:v for k,v in event.items() if k!='decision_sha256'})
        descriptor['decision_sha256']=event['decision_sha256'];descriptor['source_sha256']=event['source_sha256']
    if mutation!='descriptor_sha':descriptor['descriptor_sha256']=facts._hash({k:v for k,v in descriptor.items() if k!='descriptor_sha256'})
    with pytest.raises(provenance.ERRORS):provenance.project(parent,sources(descriptor),sources(descriptor))


def test_optional_request_extension_preserves_legacy_serialization():
    request=dict(expected_preparation_revision=1,expected_request_revision=1,expected_source_sha256='a'*64,required_goals=['goal'],reason='explicit owner')
    data=Adopt(**request)
    assert 'fact_provenance_scope' not in _adopt_request(data)
    with pytest.raises(ValueError):Adopt(**request,fact_provenance_scope=provenance.SCOPE)
