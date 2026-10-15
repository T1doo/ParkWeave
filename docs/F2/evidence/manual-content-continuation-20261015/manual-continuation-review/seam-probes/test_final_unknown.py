"""Actual API final-read UNKNOWN fault seam; no product/source edits."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json
import os
import pytest
from parkweave import plan_source_conflicts as notes
from test_plan_source_conflicts import (
    http_f, link_fixture, receipt_fixture, preparation_fixture,
    read, edit, changed, cold, path, stored, snapshot, complete,
)
from test_preparation import headers

HERE = Path(__file__).resolve().parent
SIX_GOALS = [
    'LOCAL_MATERIAL_PREPARATION', 'LOCAL_CASE_RESOURCE_ASSOCIATION',
    'LOCAL_INTERNAL_ACCEPTANCE', 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
    'LOCAL_CASE_RECORD_RECHECK', 'LOCAL_SYNTHETIC_COORDINATION_RECORDS',
]


@pytest.mark.parametrize('action', ['KEEP_AND_CONTINUE', 'MERGE_NOTE'])
def test_final_source_read_unknown_rolls_back_and_retains_original_key(http_f, monkeypatch, action):
    f = http_f
    parent, _, _, _ = complete(f, goals=SIX_GOALS, local=True)
    incoming = 'SYNTHETIC exact source condition\nSYNTHETIC use original verification'
    manual = 'SYNTHETIC retained human note\n' + incoming
    edit(f, parent, manual)
    parent, card = changed(f, parent, mixed=True, text=incoming)
    value = read(f, parent, card)
    assert value.status_code == 200, value.text
    value = value.json()
    assert value['continuation']['can_keep_and_continue'] and value['continuation']['can_merge']
    (HERE / (os.environ['REVIEW_SEAM_WINDOW'] + '-' + action.lower() + '-dto.json')).write_text(json.dumps(value, indent=2) + '\n')
    before_plan = stored(f, parent)
    assert before_plan['required_goals'] == SIX_GOALS
    assert [s['adapter_id'] for s in before_plan['steps']] == ['P1', 'P2', 'P3', 'P4', 'P5']
    body = deepcopy(value['action_requests'][action])
    body['reason'] = 'SYNTHETIC final-read unavailable original request'
    if action == 'MERGE_NOTE':
        body['text'] = manual + '\nSYNTHETIC explicit appended reminder'
    key = uuid4().hex
    before = snapshot(f)
    original_basis = notes._basis
    calls = []

    def last_read_unavailable(*args, **kwargs):
        calls.append(len(calls) + 1)
        if len(calls) == 2:
            # A bounded source reader can legitimately report unavailability.
            # Let actual _view catch Conflict and return its normal UNKNOWN,
            # None-basis result. No fake successful permission/plan/source DTO.
            raise notes.Conflict('SYNTHETIC final source reader unavailable')
        return original_basis(*args, **kwargs)

    monkeypatch.setattr(notes, '_basis', last_read_unavailable)
    response = f[3].post(path(parent) + '/commands', headers=headers(f[2], key=key), json=body)
    monkeypatch.setattr(notes, '_basis', original_basis)
    unchanged = snapshot(f) == before and stored(f, parent) == before_plan
    recovered = cold(f, parent, key)
    row = dict(action=action, actual_HTTP_status=response.status_code, required_HTTP_status=409,
               final_read_seam_called=len(calls), all_business_and_plan_and_ledger_rows_unchanged=unchanged,
               cold_GET_status=recovered.status_code,
               cold_result=recovered.json().get('status') if recovered.status_code == 200 else None,
               actual_original_six_goal_P1_P5_API_PG_setup=True,
               source_unavailability='CONTROLLED_FINAL_READER_CONFLICT_SEAM_NOT_A_REAL_SOURCE_EXPIRY_EVENT',
               synthetic_fault_injection=True, real_browser=False)
    with (HERE / (os.environ['REVIEW_SEAM_WINDOW'] + '-observed.jsonl')).open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    assert response.status_code == 409, (response.status_code, response.text)
    assert len(calls) == 2 and unchanged
    assert recovered.status_code == 200 and recovered.json()['status'] == 'NOT_OBSERVED'
    assert snapshot(f) == before
    # No structured definitive rejection: the original opaque client handle
    # must remain pending and cold GET is the only allowed retry operation.
    assert response.json().get('status') != 'DEFINITIVELY_REJECTED'


@pytest.mark.parametrize('action', ['KEEP_AND_CONTINUE', 'MERGE_NOTE'])
def test_actual_owned_catalog_change_before_final_read_is_409_not_500(http_f, monkeypatch, action):
    f = http_f
    parent, _, _, _ = complete(f, goals=SIX_GOALS, local=True)
    source_text = 'SYNTHETIC current line one\nSYNTHETIC current line two'
    manual = 'SYNTHETIC human reminder\n' + source_text
    edit(f, parent, manual)
    parent, card = changed(f, parent, mixed=True, text=source_text)
    value = read(f, parent, card).json()
    assert value['continuation']['can_keep_and_continue']
    body = deepcopy(value['action_requests'][action])
    body['reason'] = 'SYNTHETIC actual current catalogue final-read refusal'
    if action == 'MERGE_NOTE':
        body['text'] = manual + '\nSYNTHETIC explicit additional reminder'
    original_view = notes._view
    calls = []

    def change_actual_source_before_final_view(*args, **kwargs):
        calls.append(len(calls) + 1)
        if len(calls) == 2:
            # The only intervention is the owned fixture administrator changing
            # actual source data in a separately committed PG transaction. The
            # complete original view, sources and permission checks still run.
            with f[1].connect() as connection:
                connection.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"'::jsonb) WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)", (parent['preparation_id'],))
        return original_view(*args, **kwargs)

    key = uuid4().hex
    before = snapshot(f)
    plan_before = stored(f, parent)
    monkeypatch.setattr(notes, '_view', change_actual_source_before_final_view)
    response = f[3].post(path(parent) + '/commands', headers=headers(f[2], key=key), json=body)
    monkeypatch.setattr(notes, '_view', original_view)
    with f[1].connect() as connection:
        kind = connection.execute("SELECT source->>'kind' AS kind FROM preparation_catalog WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)", (parent['preparation_id'],)).fetchone()['kind']
    unchanged = snapshot(f) == before and stored(f, parent) == plan_before
    recovered = cold(f, parent, key)
    row = dict(action=action, actual_HTTP_status=response.status_code, required_HTTP_status=409,
               original_final_view_calls=len(calls), actual_owned_catalog_kind=kind,
               all_business_and_plan_and_ledger_rows_unchanged=unchanged,
               external_fixture_source_change_separate=True,
               catalog_table_excluded_from_unchanged_business_snapshot=True,
               cold_GET_status=recovered.status_code,
               cold_result=recovered.json().get('status') if recovered.status_code == 200 else None,
               actual_original_six_goal_P1_P5_API_PG_setup=True, fake_source_or_permission_result=False)
    with (HERE / (os.environ['REVIEW_SEAM_WINDOW'] + '-actual-catalog-observed.jsonl')).open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    assert response.status_code == 409 and kind == 'UNKNOWN', response.text
    assert len(calls) == 2 and unchanged
    assert response.json().get('status') != 'DEFINITIVELY_REJECTED'
    assert recovered.status_code == 200 and recovered.json()['status'] == 'NOT_OBSERVED'
    assert snapshot(f) == before
