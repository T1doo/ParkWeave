"""Correct final scope contract: hashed free strings, typed public source."""
import hashlib
import json
from copy import deepcopy
from parkweave import native_run_access_trial_plan as trial
from test_native_run_access_trial_plan import inputs


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def test_safe_scope_hashes_free_fields_and_binds_typed_scope_without_authority():
    spec, snapshot, host = inputs()
    values = {name:'Bearer SYNTHETIC_PRIVATE_'+name+'_NOT_REAL_CREDENTIAL' for name in ['owner_id','approver_id','beneficiary_id','park_id','org_id','preparation_state']}
    for name in ['owner_id','approver_id','beneficiary_id']:spec['policy'][name] = values[name]
    for name in ['owner_id','park_id','org_id','preparation_state']:spec['policy']['source'][name] = values[name]
    before = deepcopy((spec,snapshot,host))
    result = trial.prepare(spec,snapshot,host)
    assert result['status'] == 'APPROVAL_REQUIRED'
    assert (spec,snapshot,host) == before
    assert all(value not in json.dumps(result) for value in values.values())
    scope = result['declared_case_scope']
    assert scope['source_sha256'] == digest(spec['policy']['source'])
    assert scope['actors_sha256'] == digest({name:spec['policy'][name] for name in ['owner_id','approver_id','beneficiary_id']})
    assert set(scope['public_source']) == {'run_id','run_revision','input_fingerprint','preparation_id','preparation_revision','review_sha256','material_sha256','case_id'}
    assert all(scope['public_source'][name] == spec['policy']['source'][name] for name in scope['public_source'])
    assert result['writer_argv'] is None and result['writer_runtime'] == 'NOT_IMPLEMENTED'
    assert result['actual_run'] == 'NOT_RUN'
    assert all(result[name] is False for name in ['launch_authorized','installation_authorized','activation_enabled','production_connected'])
    spec['policy']['source']['run_revision'] += 1
    modified = trial.prepare(spec,snapshot,host)
    assert modified['plan_digest'] != result['plan_digest']
    assert modified['declared_case_scope']['source_sha256'] != scope['source_sha256']
    assert modified['declared_case_scope']['public_source']['run_revision'] == spec['policy']['source']['run_revision']
