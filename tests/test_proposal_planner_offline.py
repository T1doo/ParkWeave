"""Independent owned-PG proposal-only tests. Provider transport is always fake.

The fixture deliberately shares the existing receipt-bearing owned PG setup;
no environment secrets, real provider request, browser or LIVE ledger is used.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.intern_adapter import OfflineBudget
from test_preparation import preparation_fixture, headers, add
from test_bounded_planning import setup
from test_plan_preview import digest
from test_service_plan_candidates import path, adoption

GOAL = 'LOCAL_CASE_RECORD_RECHECK'


def request_body(f, p):
    current = f[3].get('/api/preparations/' + p['preparation_id'] + '/planning-preview',
                       headers=headers(f[2])).json()['current']
    return {'expected_preparation_revision': current['preparation_revision'],
            'expected_source_sha256': current['source_sha256']}, current


def fake_envelope(document):
    return {'id': 'isolated-offline-proposal-1', 'model': 'intern-s2',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': json.dumps(document)}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}


def post_candidate(client, f, p, body, key):
    return client.post(path(p), headers=headers(f[2], key=key), json=body)


def exact_recovery(client, f, p, key):
    return client.get(path(p) + '/recovery', headers=headers(f[2], key=key))


def assert_read_only(client, f, url):
    before = digest(f)
    response = client.get(url, headers=headers(f[2]))
    assert response.status_code == 200, response.text
    assert digest(f) == before
    return response.json()


def business_snapshot(f):
    """Every public table, with only candidate metadata and auth audit excluded."""
    with f[1].connect() as connection:
        tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
        result = {}
        for item in tables:
            table = item['tablename']
            if table == 'authorization_audit':
                continue
            rows = connection.execute('SELECT * FROM "' + table + '" ORDER BY to_jsonb("' + table + '")::text').fetchall()
            if table == 'preparations':
                rows = [{key: value for key, value in row.items() if key != 'planning_previews'} for row in rows]
            result[table] = rows
        return result


def planner(handler):
    from parkweave.service_plan_planner import OfflineProposalPlanner
    return OfflineProposalPlanner(transport=httpx.MockTransport(handler), budget=OfflineBudget())


def echo_handler(requests, mutate=None, entered=None, release=None):
    def handler(request):
        wire = json.loads(request.content)
        assert 'tools' not in wire and 'tool_choice' not in wire
        from parkweave.service_plan_planner import FAKE_TOKEN
        assert request.headers.get('authorization') == 'Bearer ' + FAKE_TOKEN
        data = json.loads(wire['messages'][-1]['content'])
        assert data['scope'] == 'SYNTHETIC_PROPOSAL_ONLY'
        proposal = deepcopy(data['proposal'])
        requests.append({'method': request.method, 'proposal': deepcopy(proposal)})
        if entered is not None:
            entered.set()
            assert release.wait(10), 'isolated fake producer release timed out'
        if mutate is not None:
            proposal = mutate(proposal)
        return httpx.Response(200, json=fake_envelope(proposal))
    return handler


def test_fake_transport_original_candidate_adopt_source_trace(preparation_fixture, monkeypatch):
    f = preparation_fixture
    p = setup(f, [GOAL])
    body, _ = request_body(f, p)
    from parkweave.gateway import ExecutionGateway
    from parkweave.quota import PersistentBudget
    def prohibited(*args, **kwargs):
        raise AssertionError('proposal flow called business gateway or persistent quota')
    monkeypatch.setattr(ExecutionGateway, 'execute', prohibited)
    for method in ('reserve', 'dispatch', 'finish'):
        monkeypatch.setattr(PersistentBudget, method, prohibited)
    requests = []
    instance = planner(echo_handler(requests))
    before = business_snapshot(f)
    with TestClient(create_app(f[0], proposal_planner=instance)) as client:
        key = uuid4().hex
        response = post_candidate(client, f, p, body, key)
        assert response.status_code == 201, response.text
        value = response.json()
        assert value['state'] == 'VERIFIED_STRUCTURE_ONLY'
        assert value['can_adopt'] and value['execution_enabled'] is False
        assert business_snapshot(f) == before
        candidate = assert_read_only(client, f, path(p) + '/' + value['candidate_id'] + '/preview')
        assert candidate['verification_sha256'] == value['verification_sha256']
        assert exact_recovery(client, f, p, key).json()['status'] == 'COMMITTED'
        response = client.post('/api/preparations/' + p['preparation_id'] + '/service-case-plan',
                               headers=headers(f[2], key=uuid4().hex), json=adoption(f, p, value))
        assert response.status_code == 201, response.text
        trace = assert_read_only(client, f, '/api/preparations/' + p['preparation_id'] + '/goal-results')['source_trace']
        assert trace['candidate']['candidate_id'] == value['candidate_id']
        assert trace['candidate']['validator_version'] == 3
        assert trace['required_goals'] == [GOAL]
        assert trace['read_only'] and trace['execution_enabled'] is False
        assert len(requests) == 1 and instance.budget.calls == 1


def corrupt_document(kind):
    def mutate(proposal):
        if kind == 'extra': proposal['approved'] = True
        elif kind == 'drop_goal': proposal['required_goals'] = []; proposal['goal_coverage'] = []
        elif kind == 'unknown_version': proposal['steps'][0]['adapter_revision'] = 99
        elif kind == 'cycle': proposal['steps'][0]['depends_on'] = ['P5']
        elif kind == 'missing_dependency': proposal['steps'][-1]['depends_on'] = []
        elif kind == 'source': proposal['binding']['source_sha256'] = '0' * 64
        elif kind == 'hard_condition': proposal['constraints'] = {}
        else: raise AssertionError(kind)
        return proposal
    return mutate


@pytest.mark.parametrize('kind', ['extra', 'drop_goal', 'unknown_version', 'cycle', 'missing_dependency', 'source', 'hard_condition'])
def test_untrusted_proposal_never_downgrades_original_contract(preparation_fixture, kind):
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    requests = []; instance = planner(echo_handler(requests, corrupt_document(kind)))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client:
        key = uuid4().hex; response = post_candidate(client, f, p, body, key)
        assert response.status_code in (409, 422, 502), response.text
        recovered = exact_recovery(client, f, p, key)
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['status'] in ('FAILED_SAFE', 'OUTCOME_UNKNOWN')
        assert not recovered.json().get('items')
        repeated = post_candidate(client, f, p, body, key)
        assert repeated.status_code in (200, 201, 409, 422, 502)
        if repeated.status_code < 400:
            assert repeated.json()['status'] == recovered.json()['status']
            assert not repeated.json()['can_adopt']
        assert len(requests) == 1


def test_wait_releases_case_lock_real_material_command_and_stale_result(preparation_fixture):
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    requests = []; entered = Event(); release = Event()
    instance = planner(echo_handler(requests, entered=entered, release=release))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client, ThreadPoolExecutor(2) as pool:
        key = uuid4().hex; waiting = pool.submit(post_candidate, client, f, p, body, key)
        try:
            assert entered.wait(5)
            material = pool.submit(add, f, p)
            changed = material.result(timeout=5)
            assert changed.status_code == 200, changed.text
            pending = exact_recovery(client, f, p, key)
            assert pending.status_code == 200 and pending.json()['status'] == 'PENDING'
        finally:
            release.set()
        response = waiting.result(timeout=10)
        assert response.status_code == 409, response.text
        recovered = exact_recovery(client, f, p, key).json()
        assert recovered['status'] in ('FAILED_SAFE', 'OUTCOME_UNKNOWN', 'PENDING') and not recovered.get('items')
        assert len(requests) == 1


def test_same_key_wait_has_one_fake_dispatch_and_original_recovery(preparation_fixture):
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    requests = []; entered = Event(); release = Event()
    instance = planner(echo_handler(requests, entered=entered, release=release))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client, ThreadPoolExecutor(2) as pool:
        key = uuid4().hex; waiting = pool.submit(post_candidate, client, f, p, body, key)
        try:
            assert entered.wait(5)
            second = pool.submit(post_candidate, client, f, p, body, key).result(timeout=5)
            assert second.status_code in (200, 201, 202, 409), second.text
            if second.status_code < 400:
                assert second.json()['status'] == 'PENDING' and not second.json()['can_adopt']
            assert exact_recovery(client, f, p, key).json()['status'] == 'PENDING'
            different = {**body, 'expected_source_sha256': '0' * 64}
            assert post_candidate(client, f, p, different, key).status_code == 409
        finally:
            release.set()
        response = waiting.result(timeout=10)
        assert response.status_code == 201, response.text
        recovered = exact_recovery(client, f, p, key).json()
        assert recovered['status'] == 'COMMITTED' and recovered['items'][0]['candidate_id'] == response.json()['candidate_id']
        assert len(requests) == 1


@pytest.mark.parametrize('capability', ['READ', 'PREPARE', 'EXECUTE'])
def test_wait_rechecks_current_permissions_before_committing_proposal(preparation_fixture, capability):
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    requests = []; entered = Event(); release = Event()
    instance = planner(echo_handler(requests, entered=entered, release=release))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client, ThreadPoolExecutor(2) as pool:
        key = uuid4().hex; waiting = pool.submit(post_candidate, client, f, p, body, key)
        try:
            assert entered.wait(5)
            table = 'preparation_grants' if capability == 'PREPARE' else 'capability_grants'
            with f[1].connect() as connection:
                connection.execute('UPDATE ' + table + ' SET active=false WHERE principal_id=%s AND capability=%s',
                                   ('fixture-a', capability))
        finally:
            release.set()
        response = waiting.result(timeout=10)
        assert response.status_code == 403, response.text
        with f[1].connect() as connection:
            records = connection.execute('SELECT planning_previews FROM preparations WHERE id=%s',
                                         (p['preparation_id'],)).fetchone()['planning_previews']
        assert len(records) == 1 and 'candidate' not in records[0]
        assert len(requests) == 1


@pytest.mark.parametrize('change', ['catalog', 'registry'])
def test_wait_rechecks_original_version_fingerprints(preparation_fixture, monkeypatch, change):
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    requests = []; entered = Event(); release = Event()
    instance = planner(echo_handler(requests, entered=entered, release=release))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client, ThreadPoolExecutor(2) as pool:
        key = uuid4().hex; waiting = pool.submit(post_candidate, client, f, p, body, key)
        try:
            assert entered.wait(5)
            if change == 'catalog':
                with f[1].connect() as connection:
                    connection.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"SYNTHETIC-wait-change\"}'::jsonb")
            else:
                from parkweave import bounded_planning as bp
                registry = deepcopy(bp.REGISTRY)
                registry[0]['acceptance'] += ' SYNTHETIC changed while producer waiting'
                monkeypatch.setattr(bp, 'REGISTRY', registry)
        finally:
            release.set()
        response = waiting.result(timeout=10)
        assert response.status_code == 409, response.text
        recovered = exact_recovery(client, f, p, key).json()
        assert recovered['status'] in ('FAILED_SAFE', 'OUTCOME_UNKNOWN', 'PENDING')
        assert not recovered.get('items') and len(requests) == 1


@pytest.mark.parametrize('kind', ['duplicate', 'tool_field', 'timeout', 'socket'])
def test_malformed_or_failed_producer_preserves_original_key_without_retry(preparation_fixture, kind):
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    requests = []
    def handler(request):
        requests.append(request.method)
        if kind == 'timeout':
            raise httpx.ReadTimeout('SYNTHETIC offline timeout', request=request)
        if kind == 'socket':
            import socket
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0)); endpoint = listener.getsockname()
                # Bound, non-listening own loopback socket: OS refuses connection.
                with pytest.raises(ConnectionRefusedError):
                    socket.create_connection(endpoint, timeout=0.5)
            raise httpx.ConnectError('SYNTHETIC local socket refused', request=request)
        proposal = json.loads(json.loads(request.content)['messages'][-1]['content'])['proposal']
        envelope = fake_envelope(proposal)
        if kind == 'duplicate':
            content = envelope['choices'][0]['message']['content']
            envelope['choices'][0]['message']['content'] = '{"schema_version":1,' + content[1:]
        else:
            envelope['choices'][0]['message']['tool_calls'] = []
        return httpx.Response(200, json=envelope)
    instance = planner(handler)
    with TestClient(create_app(f[0], proposal_planner=instance)) as client:
        key = uuid4().hex; response = post_candidate(client, f, p, body, key)
        assert response.status_code in (409, 422, 502), response.text
        recovered = exact_recovery(client, f, p, key)
        assert recovered.status_code == 200 and recovered.json()['status'] in ('FAILED_SAFE', 'OUTCOME_UNKNOWN')
        assert not recovered.json().get('items')
        repeated = post_candidate(client, f, p, body, key)
        assert repeated.status_code in (200, 201, 409, 422, 502)
        if repeated.status_code < 400:
            assert repeated.json()['status'] == recovered.json()['status']
            assert not repeated.json()['can_adopt']
        assert requests == ['POST']


def test_unsupported_goal_and_unknown_catalog_remain_honest(preparation_fixture):
    f = preparation_fixture; p = setup(f, [GOAL, 'UNSUPPORTED_EXTERNAL_ACCEPTANCE']); body, _ = request_body(f, p)
    requests = []; instance = planner(echo_handler(requests))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client:
        response = post_candidate(client, f, p, body, uuid4().hex)
        assert response.status_code == 201, response.text
        value = response.json()
        assert value['required_goals'] == [GOAL, 'UNSUPPORTED_EXTERNAL_ACCEPTANCE']
        assert not value['can_adopt'] and value['can_adopt_partial']
        with f[1].connect() as connection:
            connection.execute("UPDATE preparation_catalog SET source='{}'::jsonb")
        body, _ = request_body(f, p)
        response = post_candidate(client, f, p, body, uuid4().hex)
        assert response.status_code == 201, response.text
        value = response.json()
        assert value['state'] == 'UNKNOWN' and not value['can_adopt'] and not value['can_adopt_partial']
        assert value['required_goals'] == [GOAL, 'UNSUPPORTED_EXTERNAL_ACCEPTANCE']
        assert len(requests) == 2


@pytest.mark.parametrize('mode', ['normal', 'cold_generate', 'cold_adopt', 'trace'])
def test_original_page_fake_planner_closed_loop(preparation_fixture, monkeypatch, mode):
    from test_service_plan_candidates import test_original_page_candidate_consumer_never_hand_fills_candidate_json
    import os
    from pathlib import Path
    output = os.environ.get('PROPOSAL_PLANNER_PAGE_EVIDENCE', '.runtime/proposal-planner-20261014/pages')
    monkeypatch.setenv('PLAN_CANDIDATE_EVIDENCE', str(Path(output).resolve()))
    requests = []; instance = planner(echo_handler(requests))
    f = preparation_fixture
    with TestClient(create_app(f[0], proposal_planner=instance)) as client:
        original_fixture = (f[0], f[1], f[2], client)
        test_original_page_candidate_consumer_never_hand_fills_candidate_json(original_fixture, mode, monkeypatch)
    assert len(requests) == 1 and instance.budget.calls == 1


def test_planner_offline_boundary_rejects_real_transport_or_untrusted_budget():
    from parkweave.service_plan_planner import OfflineProposalPlanner
    from parkweave.intern_adapter import ModelBoundaryError
    with pytest.raises(ModelBoundaryError):
        OfflineProposalPlanner(transport=None, budget=OfflineBudget())
    with pytest.raises(ModelBoundaryError):
        OfflineProposalPlanner(transport=httpx.MockTransport(lambda _: None), budget=object())


def test_default_app_keeps_original_synthetic_path_without_producer_dispatch(preparation_fixture, monkeypatch):
    from parkweave.http_transport import InternHTTPTransport
    from parkweave.service_plan_planner import OfflineProposalPlanner
    def forbidden(*args, **kwargs):
        raise AssertionError('default synthetic path dispatched offline or live planner')
    monkeypatch.setattr(InternHTTPTransport, 'post', forbidden)
    monkeypatch.setattr(OfflineProposalPlanner, 'propose', forbidden)
    f = preparation_fixture; p = setup(f, [GOAL]); body, _ = request_body(f, p)
    response = post_candidate(f[3], f, p, body, uuid4().hex)
    assert response.status_code == 201, response.text
    assert response.json()['state'] == 'VERIFIED_STRUCTURE_ONLY'
