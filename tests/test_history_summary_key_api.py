"""Bounded original-key projection and in-process ASGI, synthetic fixtures only."""
from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4
import json

import pytest
from fastapi.testclient import TestClient

from parkweave import history_summary as hs
from parkweave.api import create_app
from parkweave.store import Denied
from test_preparation import preparation_fixture, headers
from test_fact_history_read_source_store import selected, memory_reader, snapshot
from test_history_summary import sample, seal
from test_history_summary_api import url, assert_read_effects


def add_original(reader, preparation_id, key, *, replace_all=False):
    """Explicit server-fixture enrollment of another independent synthetic row."""
    baseline = reader.baselines[preparation_id]
    row = deepcopy(reader.records[preparation_id][0]);doc = json.loads(row['document'])
    doc['id'] = str(uuid4());doc['request_key'] = key
    row = seal(doc, hs._checks(reader.stage, baseline.namespace))
    anchor = hs.RecordAnchor(doc['id'], key, hs.row_sha256(row), baseline.records[0].source_sha256)
    reader.records[preparation_id] = (row,) if replace_all else (*reader.records[preparation_id], row)
    reader.baselines[preparation_id] = replace(baseline, records=(anchor,) if replace_all else (*baseline.records, anchor))


@pytest.mark.parametrize('stage', ['P4', 'P5'])
@pytest.mark.parametrize('key', ['synthetic-key', 'absent-original-key'])
def test_original_key_has_exact_existing_projection_and_no_inferred_failure(stage, key):
    context, baseline, row, _ = sample(stage)
    full = hs.summaries(stage, baseline, context, (row,))
    result = hs.summaries(stage, baseline, context, (row,), key)
    assert result['history'] == full['history'] and result['request_key'] == key
    assert result['status'] == ('COMMITTED' if key == row['request_key'] else 'NOT_OBSERVED')
    assert result['result'] == (full['history'][0]['summary'] if key == row['request_key'] else None)
    if result['result'] is not None:assert result['result']['state'] == 'FAILED'
    assert not result['execution_available'] and not result['automatically_replayed'] and not result['new_grants']
    assert result['formal_writes'] == 0 and result['execution_qualification'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('key', ['A', 'a'*128, 'A0._:-z'])
def test_pure_original_key_boundary_exact_ascii(key):
    context, baseline, row, checks = sample()
    doc = json.loads(row['document']);doc['request_key'] = key;row = seal(doc, checks)
    baseline = replace(baseline, records=(replace(baseline.records[0], key=key, row_sha256=hs.row_sha256(row)),))
    assert hs.summaries('P4', baseline, context, (row,), key)['status'] == 'COMMITTED'
    assert hs.summaries('P4', baseline, context, (row,), key.swapcase())['status'] == 'NOT_OBSERVED'


@pytest.mark.parametrize('key', ['', 'x'*129, ' private', 'private ', 'private/key', 'private\\key', 'private+key', '%41', '私密', 42, False, [], {}])
def test_pure_invalid_original_keys_are_refused(key):
    context, baseline, row, _ = sample()
    with pytest.raises(Denied):hs.summaries('P4', baseline, context, (row,), key)


@pytest.mark.parametrize('stage', ['P4', 'P5'])
def test_http_original_key_and_full_history_envelopes_preserve_exact_states(preparation_fixture, stage):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, stage)
    add_original(reader, p['preparation_id'], 'Exact.Original_Key:2-')
    before = snapshot(f);baselines = deepcopy(reader.baselines);rows = deepcopy(reader.records)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        full = client.get(url(p, stage), headers=headers(f[2])).json()
        assert 'request_key' not in full and 'status' not in full and 'result' not in full
        for key, expected_index in [('synthetic-key', 0), ('Exact.Original_Key:2-', 1), ('exact.original_key:2-', None)]:
            response = client.get(url(p, stage), headers=headers(f[2]), params={'request_key':key})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['history'] == full['history'] and result['case_id'] == p['case_id'] and result['stage'] == stage
            assert result['request_key'] == key and response.headers['cache-control'] == 'no-store'
            assert result['status'] == ('COMMITTED' if expected_index is not None else 'NOT_OBSERVED')
            assert result['result'] == (full['history'][expected_index]['summary'] if expected_index is not None else None)
            if expected_index is not None:assert result['result']['state'] == 'FAILED'
            assert not result['automatically_replayed'] and not result['execution_available'] and not result['new_grants']
            assert result['formal_writes'] == 0 and result['execution_qualification'] == 'NOT_EVALUATED'
            for secret in ('PRIVATE ERROR', 'proof', 'artifact', 'source_snapshot', 'source_excerpt', 'choices'):
                assert secret not in json.dumps(result)
        assert client.get(url(p, stage), headers=headers(f[2])).json() == full
    assert_read_effects(f, before)
    assert reader.baselines == baselines and reader.records == rows


@pytest.mark.parametrize('key', ['Z', 'K'*128, 'A0._:-z'])
def test_http_valid_length_and_punctuation_match_exact_original(preparation_fixture, key):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4')
    add_original(reader, p['preparation_id'], key)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        response = client.get(url(p), headers=headers(f[2]), params={'request_key':key})
    assert response.status_code == 200 and response.json()['status'] == 'COMMITTED'
    assert response.json()['result']['request_key'] == key


@pytest.mark.parametrize('key', ['', 'private-'+'x'*121, ' private-key', 'private-key ', 'private/key', 'private\\key', 'private+key', '%41', '私密键', 'private\nkey'])
def test_http_invalid_key_is_generic_and_precedes_history_decode(preparation_fixture, monkeypatch, key):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4')
    def forbidden(*args, **kwargs):raise AssertionError('invalid key decoded history')
    monkeypatch.setattr(reader, '_rows', forbidden);before = snapshot(f)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        response = client.get(url(p), headers=headers(f[2]), params={'request_key':key})
    assert response.status_code == 403, response.text
    assert response.json() == {'detail':'record unavailable or authorization denied'}
    assert 'synthetic-key' not in response.text
    if key:assert key not in response.text
    assert_read_effects(f, before, 1)


@pytest.mark.parametrize('keys', [('synthetic-key', 'not-observed'), ('synthetic-key', 'synthetic-key')])
def test_duplicate_query_keys_are_refused_without_implicit_last_value(preparation_fixture, keys):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4');before = snapshot(f)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        response = client.get(url(p), headers=headers(f[2]), params=[('request_key', key) for key in keys])
    assert response.status_code == 403 and response.json() == {'detail':'record unavailable or authorization denied'}
    assert all(key not in response.text for key in keys)
    assert_read_effects(f, before, 1)


@pytest.mark.parametrize('key', ['synthetic-key', 'not-observed'])
@pytest.mark.parametrize('change', ['case', 'stage', 'read', 'field_read', 'baseline_expired', 'baseline_revoked', 'source_version', 'source_expired', 'default'])
def test_original_key_queries_cannot_skip_current_scope_and_source_guards(preparation_fixture, key, change):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4');case = uuid4() if change == 'case' else None
    if change in ('baseline_expired', 'baseline_revoked'):
        baseline = reader.baselines[p['preparation_id']]
        reader.baselines[p['preparation_id']] = replace(baseline, **({'valid_until':baseline.valid_from} if change == 'baseline_expired' else {'revoked':True}))
    elif change in ('read', 'field_read', 'source_version', 'source_expired'):
        sql = {'read':"UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'",
               'field_read':"UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'",
               'source_version':"UPDATE fact_assertions SET revision=revision+1 WHERE field_name='region'",
               'source_expired':"UPDATE fact_assertions SET valid_until=clock_timestamp() WHERE field_name='region'"}
        with f[1].connect() as c:c.execute(sql[change])
    before = snapshot(f)
    with TestClient(create_app(f[0], summary_reader=None if change == 'default' else reader)) as client:
        response = client.get(url(p, 'P5' if change == 'stage' else 'P4', case), headers=headers(f[2]), params={'request_key':key})
    assert response.status_code == 403 and response.json() == {'detail':'record unavailable or authorization denied'}
    assert key not in response.text and 'synthetic-key' not in response.text
    assert_read_effects(f, before, 1)


@pytest.mark.parametrize('key', ['synthetic-key', 'not-observed'])
@pytest.mark.parametrize('change', ['read', 'field_read', 'source_expiry', 'baseline_expiry', 'history', 'stage'])
def test_key_projection_final_guard_rechecks_current_permissions_and_history(preparation_fixture, monkeypatch, key, change):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4');original = hs.summaries
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == 'history':add_original(reader, p['preparation_id'], 'not-observed')
        elif change == 'stage':reader.stage = 'P5'
        elif change == 'baseline_expiry':
            baseline = reader.baselines[p['preparation_id']]
            reader.baselines[p['preparation_id']] = replace(baseline, valid_until=baseline.valid_from)
        else:
            sql = {'read':"UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'",
                   'field_read':"UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'",
                   'source_expiry':"UPDATE fact_assertions SET valid_until=clock_timestamp() WHERE field_name='region'"}
            with f[1].connect() as c:c.execute(sql[change])
        return result
    monkeypatch.setattr(hs, 'summaries', changed)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        response = client.get(url(p), headers=headers(f[2]), params={'request_key':key})
    assert response.status_code == 403 and response.json() == {'detail':'record unavailable or authorization denied'}
    assert key not in response.text


@pytest.mark.parametrize('stage', ['P4', 'P5'])
def test_late_history_changes_are_new_observations_never_retries(preparation_fixture, stage):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, stage)
    before = snapshot(f);key = 'late-original-key'
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        response = client.get(url(p, stage), headers=headers(f[2]), params={'request_key':key})
        assert response.status_code == 200 and response.json()['status'] == 'NOT_OBSERVED' and response.json()['result'] is None
        assert len(reader.records[p['preparation_id']]) == 1
        # Only explicit server-owned fixture enrollment adds history. The GET did not.
        add_original(reader, p['preparation_id'], key)
        response = client.get(url(p, stage), headers=headers(f[2]), params={'request_key':key})
        assert response.status_code == 200 and response.json()['status'] == 'COMMITTED'
        result = response.json();assert result['result']['state'] == 'FAILED'
        assert not result['automatically_replayed'] and not result['execution_available']
        assert result['formal_writes'] == 0 and not result['new_grants']
        assert client.get(url(p, stage), headers=headers(f[2])).json()['history'] == result['history']
        # An unanchored late row cannot become observed, even for a missing key.
        reader.records[p['preparation_id']] += (deepcopy(reader.records[p['preparation_id']][-1]),)
        response = client.get(url(p, stage), headers=headers(f[2]), params={'request_key':'still-not-observed'})
        assert response.status_code == 403
    assert_read_effects(f, before, 1)
