"""Explicit memory baseline, isolated fixture PG and in-process ASGI only."""
from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4
import json

import pytest
from fastapi.testclient import TestClient

from parkweave import history_summary as hs, resource_combinations
from parkweave.api import create_app
from parkweave.store import Store, Denied
from test_preparation import preparation_fixture, filled, headers
from test_fact_history_read_source_store import selected, memory_reader, snapshot, mixed_document
from test_case_fact_bundle import command as bundle_command, body as bundle_body, get as bundle_get


def url(p, stage='P4', case=None):
    return f"/api/cases/{case or p['case_id']}/preparations/{p['preparation_id']}/history-summary/{stage}"


def assert_read_effects(f, before, audit_delta=0):
    after = snapshot(f)
    assert len(after.pop('authorization_audit')) == len(before['authorization_audit']) + audit_delta
    assert after == {k:v for k,v in before.items() if k != 'authorization_audit'}


@pytest.mark.parametrize('stage', ['P4', 'P5'])
def test_explicit_summary_after_execution_revoked_and_old_routes_stay_closed(preparation_fixture, stage):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, stage)
    f[1].revoke_capability('fixture-a', 'EXECUTE')
    with f[1].connect() as c:
        c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    cold = Store(f[0].dsn);before = snapshot(f);records = deepcopy(reader.records)
    with TestClient(create_app(cold, summary_reader=reader)) as client:
        response = client.get(url(p, stage), headers=headers(f[2]))
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'no-store'
        result = response.json()
        assert result['case_id'] == p['case_id'] and result['stage'] == stage
        assert result['summary_only'] and result['read_only'] and not result['execution_available']
        assert not result['new_grants'] and not result['automatically_replayed']
        assert result['execution_qualification'] == 'NOT_EVALUATED' and result['formal_writes'] == 0
        assert result['history'][0]['source_state'] == 'SNAPSHOT_MATCH'
        summary = result['history'][0]['summary']
        assert summary['state'] == 'FAILED' and summary['p4_state'] == 'NOT_EXECUTED'
        assert summary['receipt_events'] == [] and not summary['case_goal_completed']
        if stage == 'P5':assert summary['past_case_state'] is None and summary['verification_at_execution'] is None
        for private in ('PRIVATE ERROR', 'proof', 'artifact', 'source_snapshot', 'source_excerpt', 'choices', '地区甲'):
            assert private not in json.dumps(result, ensure_ascii=False)
        assert_read_effects(f, before)
        route = 'receipt' if stage == 'P4' else 'lifecycle'
        setattr(cold, '_isolated_'+route+'_execution_preview', reader)
        assert client.get('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview', headers=headers(f[2])).status_code == 403
        body = dict(expected_preparation_revision=1, expected_request_revision=1,
                    expected_source_sha256='0'*64, review_decision='ACKNOWLEDGE')
        if stage == 'P5':body['lifecycle_sequence'] = 'REVALIDATE_CLOSE_REOPEN'
        assert client.post('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview', headers=headers(f[2], key='synthetic-old-gate'), json=body).status_code == 403
    assert_read_effects(f, before, 2)
    assert reader.records == records


@pytest.mark.parametrize('registration', ['default', 'attribute', 'environment', 'duck', 'subclass', 'wrong_stage'])
def test_only_explicit_exact_matching_reader_is_accepted(preparation_fixture, monkeypatch, registration):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4');kwargs = {}
    if registration == 'attribute':f[0].summary_reader = reader;f[0]._history_summary_reader = reader
    elif registration == 'environment':monkeypatch.setenv('PARKWEAVE_SUMMARY_READER', 'P4')
    elif registration == 'duck':
        class Duck:
            stage = 'P4'
            def read_case(self, *args):raise AssertionError('duck reader called')
        kwargs['summary_reader'] = Duck()
    elif registration == 'subclass':
        class Child(hs.MemoryHistorySummaryReader):
            def read_case(self, *args):raise AssertionError('subclass called')
        kwargs['summary_reader'] = Child('P4', reader.baselines, reader.records)
    elif registration == 'wrong_stage':kwargs['summary_reader'] = reader
    before = snapshot(f)
    with TestClient(create_app(f[0], **kwargs)) as client:
        assert client.get(url(p, 'P5' if registration == 'wrong_stage' else 'P4'), headers=headers(f[2]), params={'summary_reader':'P4'}).status_code == 403
    assert_read_effects(f, before, 1)


@pytest.mark.parametrize('change', ['read', 'field_read', 'field_expired', 'inactive', 'other_enterprise',
    'other_park', 'wrong_case', 'source_body', 'source_version', 'source_expired', 'baseline_expired',
    'baseline_revoked', 'baseline_missing', 'database', 'catalog_unknown', 'resource_read'])
def test_http_current_scope_and_source_denials_preserve_business_and_permissions(preparation_fixture, change):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4')
    user = 'fixture-b' if change == 'other_enterprise' else 'fixture-c' if change == 'other_park' else 'fixture-a'
    case = uuid4() if change == 'wrong_case' else None
    baseline = reader.baselines[p['preparation_id']]
    if change == 'baseline_missing':reader.baselines.clear()
    elif change.startswith('baseline_') or change == 'database':
        updates = {'baseline_expired':{'valid_until':baseline.valid_from}, 'baseline_revoked':{'revoked':True}, 'database':{'database':('different', '0', '0')}}
        reader.baselines[p['preparation_id']] = replace(baseline, **updates[change])
    else:
        statements = {
            'read':"UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'",
            'field_read':"UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'",
            'field_expired':"UPDATE field_grants SET valid_until=clock_timestamp() WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'",
            'inactive':"UPDATE principals SET active=false WHERE id='fixture-a'",
            'source_body':"UPDATE fact_assertions SET source_excerpt='SYNTHETIC changed' WHERE field_name='region'",
            'source_version':"UPDATE fact_assertions SET revision=revision+1 WHERE field_name='region'",
            'source_expired':"UPDATE fact_assertions SET valid_until=clock_timestamp() WHERE field_name='region'",
            'catalog_unknown':"UPDATE preparation_catalog SET source='{}'::jsonb",
            'resource_read':"UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'"}
        if change in statements:
            with f[1].connect() as c:c.execute(statements[change])
    before = snapshot(f);records = deepcopy(reader.records)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        response = client.get(url(p, case=case), headers=headers(f[2], user))
        assert response.status_code == 403, response.text
        assert response.json() == {'detail':'record unavailable or authorization denied'}
    assert_read_effects(f, before, 1)
    assert reader.records == records


@pytest.mark.parametrize('change', ['wrong_case', 'read', 'field_read'])
def test_case_and_current_permissions_precede_history_access(preparation_fixture, monkeypatch, change):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4')
    if change == 'read':f[1].revoke_capability('fixture-a', 'READ')
    elif change == 'field_read':f[1].revoke_field('fixture-a', 'region', 'READ')
    def forbidden(*args, **kwargs):raise AssertionError('history accessed before Case/current READ')
    monkeypatch.setattr(reader, '_rows', forbidden)
    monkeypatch.setattr(hs, 'summaries', forbidden)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        assert client.get(url(p, case=uuid4() if change == 'wrong_case' else None), headers=headers(f[2])).status_code == 403
    with pytest.raises(Denied):reader.read_case(f[0], f[2]['fixture-a'], None, UUID(p['preparation_id']))


@pytest.mark.parametrize('change', ['source', 'selection', 'read', 'baseline', 'records', 'stage', 'case'])
def test_http_final_guard_rechecks_after_projection(preparation_fixture, monkeypatch, change):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P5');original = hs.summaries
    other_case = None
    if change == 'case':
        run_id = f[3].post('/api/runs', headers=headers(f[2], key=uuid4().hex),
                          json={'goal':'SYNTHETIC unpaired Case'}).json()['run_id']
        f[0].finish(f[0].claim('synthetic-history-case'))
        with f[1].connect() as c:
            other_case = c.execute('SELECT id FROM cases WHERE run_id=%s', (UUID(run_id),)).fetchone()['id']
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == 'baseline':reader.baselines[p['preparation_id']] = replace(reader.baselines[p['preparation_id']], revoked=True)
        elif change == 'records':reader.records[p['preparation_id']] = ()
        elif change == 'stage':reader.stage = 'P4'
        else:
            with f[1].connect() as c:
                if change == 'source':c.execute("UPDATE fact_assertions SET revision=revision+1 WHERE field_name='region'")
                elif change == 'selection':c.execute('UPDATE preparations SET fact_clarifications=NULL WHERE id=%s', (UUID(p['preparation_id']),))
                elif change == 'case':c.execute('UPDATE preparations SET case_id=%s WHERE id=%s', (other_case, UUID(p['preparation_id'])))
                else:c.execute("UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        return result
    monkeypatch.setattr(hs, 'summaries', changed)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        assert client.get(url(p, 'P5'), headers=headers(f[2])).status_code == 403


def test_request_stage_is_pinned_across_reader_entry(preparation_fixture, monkeypatch):
    f = preparation_fixture;p = selected(f);reader = memory_reader(f, p, 'P4')
    replacement = memory_reader(f, p, 'P5');original = reader.read_case
    def switched(*args, **kwargs):
        reader.stage = replacement.stage
        reader.baselines = replacement.baselines
        reader.records = replacement.records
        return original(*args, **kwargs)
    monkeypatch.setattr(reader, 'read_case', switched)
    before = snapshot(f)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        assert client.get(url(p, 'P4'), headers=headers(f[2])).status_code == 403
    assert_read_effects(f, before, 1)


def test_withdrawn_selected_document_refused_over_http(preparation_fixture):
    f = preparation_fixture;p, entry = mixed_document(f);reader = memory_reader(f, p, 'P5')
    response = bundle_command(f, p, bundle_body(bundle_get(f, p).json(), 'WITHDRAW', source_id=entry['id']))
    assert response.status_code == 200, response.text
    before = snapshot(f)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        assert client.get(url(p, 'P5'), headers=headers(f[2])).status_code == 403
    assert_read_effects(f, before, 1)


def test_ordinary_undeclared_case_and_protocol_validation_regression(preparation_fixture):
    f = preparation_fixture;resource_combinations.seed_synthetic(f[1]);p = filled(f);reader = memory_reader(f, p, 'P4')
    normal_url = '/api/runs/'+p['run_id'];ordinary = f[3].get(normal_url, headers=headers(f[2])).json()
    before = snapshot(f)
    with TestClient(create_app(f[0], summary_reader=reader)) as client:
        assert client.get(url(p), headers=headers(f[2])).status_code == 200
        assert client.get(normal_url, headers=headers(f[2])).json() == ordinary
        assert client.get(url(p, 'P3'), headers=headers(f[2])).status_code == 422
        assert client.get(url(p)).status_code == 401
        assert client.post(url(p), headers=headers(f[2]), json={}).status_code == 405
    assert_read_effects(f, before)
