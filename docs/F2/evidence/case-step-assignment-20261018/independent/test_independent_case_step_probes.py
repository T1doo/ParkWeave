"""Literal independent cases; written before freeze, not executed in WIP.

Only the original owned fixture creates identities/grants before provider boot.
Normal business mutations use original actual HTTP/worker. Owner SQL below is
explicit artifact-corruption or an owned lock negative, never authority setup.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import time
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from parkweave.api import create_app
from parkweave import case_step_assignments as cs
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from test_new_enterprise_local_chain import actual_http
from service_release_acceptance_support import authority_snapshot

REVIEWER = 'prep-specialist-fixture-a'
BUSINESS_TABLES = (
    'runs', 'cases', 'preparations', 'preparation_evidence', 'preparation_events',
    'service_dispatches', 'service_dispatch_offers', 'service_dispatch_events',
    'service_receipt_steps', 'service_step_receipts', 'service_receipt_events',
    'dispatch_notice_outbox', 'dispatch_notices', 'controlled_plans',
    'controlled_plan_events',
)


def ok(response, expected=200):
    assert response.status_code == expected, f'HTTP {response.status_code}: {response.text}'
    return response.json()


def snapshot(owner, tables=BUSINESS_TABLES):
    with owner.connect() as c:
        return {table: c.execute(
            'SELECT to_jsonb(x) value FROM ' + table + ' x ORDER BY to_jsonb(x)::text'
        ).fetchall() for table in tables}


@contextmanager
def app_scope(f, **limits):
    provider = cs.IsolatedCaseStepAssignments(
        f[0], f[1], f[1]._case_fact_fixture_receipt,
        owner_id='fixture-a', reviewer_id=REVIEWER,
        executor_ids=('executor-a',), enabled_for_isolated_tests=True, **limits)
    before = authority_snapshot(f[1])
    with actual_http(create_app(f[0], case_step_assignments=provider)) as (api, traffic):
        yield (*f[:3], api), provider, before, traffic


def post(f, path, body, actor='fixture-a', key=None, status=200):
    key = key or uuid4().hex
    return ok(f[3].post(path, json=body, headers=headers(f[2], actor, key)), status)


def prepared(f, tag):
    created = post(f, '/api/runs', {'goal': 'PRIVATE_INDEPENDENT_GOAL_' + tag}, status=202)
    f[0].finish(f[0].claim('independent-case-step-' + tag))
    p = post(f, '/api/preparations', dict(
        run_id=created['run_id'], service_id='synthetic-material-preparation',
        service_version=1, reviewer_id=REVIEWER), status=201)
    for slot in ('need_summary', 'material_outline'):
        p = post(f, '/api/preparations/' + p['preparation_id'] + '/commands', dict(
            action='ADD_EVIDENCE', expected_revision=p['revision'], slot=slot,
            text='PRIVATE_INDEPENDENT_MATERIAL_' + tag + '_' + slot,
            source_kind='DOCUMENT_EXCERPT', source_label='SYNTHETIC independent original'))
    for actor, action in ((REVIEWER, 'REVIEW'), ('fixture-a', 'CONFIRM')):
        p = post(f, '/api/preparations/' + p['preparation_id'] + '/commands', dict(
            action=action, expected_revision=p['revision'], reason='SYNTHETIC explicit ' + action), actor)
    return p


def offered(f, p):
    return post(f, '/api/preparations/' + p['preparation_id'] + '/dispatch', dict(
        expected_preparation_revision=p['revision'], expected_dispatch_revision=0,
        executor_id='executor-a', reason='SYNTHETIC explicit fixed task'), REVIEWER, status=201)


def decide(f, d, action, actor='executor-a', key=None):
    return post(f, '/api/service-dispatches/' + d['dispatch_id'] + '/commands', dict(
        action=action, expected_revision=d['revision'], reason='SYNTHETIC explicit ' + action), actor, key)


def read_receipt(f, step, actor='executor-a'):
    return ok(f[3].get('/api/executor-receipts/' + step, headers=headers(f[2], actor)))


def receipt_action(f, row, action, text=None, key=None):
    body = dict(action=action, expected_revision=row['step']['revision'])
    if action == 'SUBMIT':
        body.update(text=text, source_kind='SYNTHETIC', source_label='SYNTHETIC independent task output')
    else:
        body.update(reason='SYNTHETIC explicit owner ' + action,
                    receipt_sha256=row['current_receipt']['source_sha256'])
    return post(f, '/api/executor-receipts/' + row['step']['id'] + '/commands', body,
                'executor-a' if action == 'SUBMIT' else 'fixture-a', key)


def test_literal_correction_reopen_append_only_and_minimal_cold_views(receipt_fixture):
    from fastapi.testclient import TestClient
    from parkweave.store import Store, Denied
    with app_scope(receipt_fixture) as (f, provider, authority, traffic):
        p = prepared(f, 'corrections')
        d = decide(f, offered(f, p), 'ACCEPT')
        r = read_receipt(f, d['receipt_step_id'])
        r = receipt_action(f, r, 'SUBMIT', 'SYNTHETIC literal first output')
        first = deepcopy(r['receipt_history'][0])
        r = receipt_action(f, r, 'REQUEST_CHANGES')
        r = receipt_action(f, r, 'SUBMIT', 'SYNTHETIC literal corrected output')
        r = receipt_action(f, r, 'ACKNOWLEDGE')
        r = receipt_action(f, r, 'REOPEN')
        r = receipt_action(f, r, 'SUBMIT', 'SYNTHETIC literal reopened output')
        assert [x['version'] for x in r['receipt_history']] == [1, 2, 3]
        assert [x['action'] for x in r['history']] == [
            'CREATE', 'SUBMIT', 'REQUEST_CHANGES', 'SUBMIT', 'ACKNOWLEDGE', 'REOPEN', 'SUBMIT']
        assert r['receipt_history'][0] == first
        assert r['current_receipt']['source_sha256'] == sha256(b'SYNTHETIC literal reopened output').hexdigest()
        assert r['case_goal_completed'] is False and r['run_access_granted'] is False
        assert r['assignment_valid_until'] == d['assignment_valid_until']
        assert 'PRIVATE_INDEPENDENT' not in json.dumps(r)
        assert 'owner_id' not in r['step']
        with TestClient(create_app(f[0], case_step_assignments=provider)) as rebound:
            assert ok(rebound.get('/api/executor-receipts/' + d['receipt_step_id'],
                                 headers=headers(f[2], 'executor-a'))) == r | {'event': None, 'replay_mode': None}
        for store in (f[0], Store(f[0].dsn)):
            with TestClient(create_app(store)) as ordinary:
                for path in ('/api/runs/' + p['run_id'],
                             '/api/executor-receipts/' + d['receipt_step_id'],
                             '/api/preparations/' + p['preparation_id'] + '/dispatch'):
                    ok(ordinary.get(path, headers=headers(f[2], 'executor-a')), 403)
        with pytest.raises(Denied):
            create_app(Store(f[0].dsn), case_step_assignments=provider)
        assert authority_snapshot(f[1]) == authority
        assert sum(x['method'] == 'POST' for x in traffic) == 14


def test_literal_damaged_offer_prefix_and_marker_types_are_quarantined(receipt_fixture):
    with app_scope(receipt_fixture) as (f, _, authority, _):
        p = prepared(f, 'marker'); d = offered(f, p)
        with f[1].connect() as c:
            event = c.execute("SELECT * FROM service_dispatch_events WHERE action='OFFER'").fetchone()
        variants = []
        for key, value in [('dispatch_id', str(uuid4())), ('offer_id', str(uuid4())),
                           ('revision', 1.0), ('action', 'ACCEPT'), ('state', 'ACCEPTED'),
                           ('actor_id', 'fixture-a'), ('executor_id', 'unassigned'),
                           ('reason', 'SYNTHETIC different original reason'),
                           ('receipt_step_id', str(uuid4()))]:
            payload = deepcopy(event['payload']); payload[key] = value
            variants.append((key, payload))
        for key, value in [('service_version', 1.0), ('catalog_sha256', 'bad-sha'),
                           ('generations', [])]:
            payload = deepcopy(event['payload']); payload[cs.MARKER]['binding'][key] = value
            variants.append(('binding.' + key, payload))
        try:
            for label, payload in variants:
                with f[1].connect() as c:
                    c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(payload), event['id']))
                before = snapshot(f[1])
                for actor in ('executor-a', 'fixture-a', REVIEWER):
                    response = f[3].get('/api/service-dispatches/' + d['dispatch_id'], headers=headers(f[2], actor))
                    assert response.status_code in (403, 409), (label, actor, response.status_code, response.text)
                assert snapshot(f[1]) == before
        finally:
            with f[1].connect() as c:
                c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(event['payload']), event['id']))
        assert authority_snapshot(f[1]) == authority


def test_literal_recovery_original_revision_and_body_proof_no_writes(receipt_fixture):
    with app_scope(receipt_fixture) as (f, _, authority, _):
        p = prepared(f, 'recovery'); d = offered(f, p)
        query = dict(preparation_id=p['preparation_id'], case_id=p['case_id'], run_id=p['run_id'],
                     offer_id=d['current_offer']['id'], expected_revision=d['revision'],
                     preparation_revision=p['revision'])
        path = '/api/service-dispatches/' + d['dispatch_id'] + '/accept-recovery'
        absent = uuid4().hex; before = snapshot(f[1])
        answer = ok(f[3].get(path, params=query, headers=headers(f[2], 'executor-a', absent)))
        assert answer['status'] == 'NOT_OBSERVED' and answer['event'] is None
        for revision in (2, 63):
            response = f[3].get(path, params={**query, 'expected_revision': revision},
                               headers=headers(f[2], 'executor-a', absent))
            assert response.status_code in (403, 409), response.text
        assert snapshot(f[1]) == before
        key = uuid4().hex; accepted = decide(f, d, 'ACCEPT', key=key)
        before = snapshot(f[1])
        answer = ok(f[3].get(path, params=query, headers=headers(f[2], 'executor-a', key)))
        assert answer['status'] == 'COMMITTED'
        assert answer['event']['receipt_step_id'] == accepted['receipt_step_id']
        assert snapshot(f[1]) == before
        row = read_receipt(f, accepted['receipt_step_id']); key = uuid4().hex
        submitted = receipt_action(f, row, 'SUBMIT', 'SYNTHETIC original immutable receipt', key)
        submit_path = '/api/executor-receipts/' + row['step']['id'] + '/submit-recovery'
        query.pop('offer_id'); query['expected_revision'] = row['step']['revision']
        before = snapshot(f[1])
        answer = ok(f[3].get(submit_path, params=query, headers=headers(f[2], 'executor-a', key)))
        assert answer['status'] == 'COMMITTED'
        assert answer['event']['receipt_sha256'] == submitted['current_receipt']['source_sha256']
        assert snapshot(f[1]) == before
        with f[1].connect() as c:
            event = c.execute("SELECT * FROM service_receipt_events WHERE action='SUBMIT'").fetchone()
        payload = deepcopy(event['payload']); payload['receipt_id'] = 'invalid-uuid'
        try:
            with f[1].connect() as c:
                c.execute('UPDATE service_receipt_events SET payload=%s WHERE id=%s', (Jsonb(payload), event['id']))
            before = snapshot(f[1])
            response = f[3].get(submit_path, params=query, headers=headers(f[2], 'executor-a', key))
            assert response.status_code in (403, 409), response.text
            assert snapshot(f[1]) == before
        finally:
            with f[1].connect() as c:
                c.execute('UPDATE service_receipt_events SET payload=%s WHERE id=%s', (Jsonb(event['payload']), event['id']))
        assert authority_snapshot(f[1]) == authority


def test_literal_material_new_generation_does_not_revive_and_owner_history_stays_discoverable(receipt_fixture):
    with app_scope(receipt_fixture) as (f, _, authority, _):
        p = prepared(f, 'material'); d = decide(f, offered(f, p), 'ACCEPT')
        row = read_receipt(f, d['receipt_step_id'])
        submitted = receipt_action(f, row, 'SUBMIT', 'SYNTHETIC preserved output before source change')
        retained = deepcopy(submitted['receipt_history'])
        p = post(f, '/api/preparations/' + p['preparation_id'] + '/commands', dict(
            action='REOPEN', expected_revision=p['revision'], reason='SYNTHETIC material recheck'))
        for actor, action in ((REVIEWER, 'REVIEW'), ('fixture-a', 'CONFIRM')):
            p = post(f, '/api/preparations/' + p['preparation_id'] + '/commands', dict(
                action=action, expected_revision=p['revision'], reason='SYNTHETIC same source recheck'), actor)
        before = snapshot(f[1])
        response = f[3].get('/api/executor-receipts/' + row['step']['id'], headers=headers(f[2], 'executor-a'))
        ok(response, 403); assert snapshot(f[1]) == before
        catalog = ok(f[3].get('/api/service-dispatches/catalog', params={'preparation_id': p['preparation_id']},
                              headers=headers(f[2], REVIEWER)))
        assert catalog['ready'] is False and catalog['executors'] == []
        current = ok(f[3].get('/api/service-dispatches/' + d['dispatch_id'], headers=headers(f[2], REVIEWER)))
        withdrawn = decide(f, current, 'WITHDRAW', REVIEWER)
        assert withdrawn['current_offer']['state'] == 'WITHDRAWN'
        assert withdrawn['current_offer']['receipt_step_id'] is None
        listing = ok(f[3].get('/api/executor-receipts', headers=headers(f[2])))
        assert [x['id'] for x in listing['items']] == [row['step']['id']]
        history = read_receipt(f, row['step']['id'], 'fixture-a')
        assert history['receipt_history'] == retained and history['is_current_step'] is False
        assert history['can_submit'] is False and history['dependency'] == 'DEPENDENCY_CHANGED'
        assert authority_snapshot(f[1]) == authority


def test_literal_actual_parent_wait_deadline_is_not_extended(receipt_fixture):
    with app_scope(receipt_fixture, offer_seconds=2) as (f, _, authority, _):
        p = prepared(f, 'deadline'); d = offered(f, p)
        with f[1].connect() as blocker:
            blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE', (p['preparation_id'],))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(f[3].post,
                    '/api/service-dispatches/' + d['dispatch_id'] + '/commands',
                    headers=headers(f[2], 'executor-a', uuid4().hex),
                    json=dict(action='ACCEPT', expected_revision=1, reason='SYNTHETIC original wait'))
                observed = False
                for _ in range(40):
                    with f[1].connect() as c:
                        observed = bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM preparations%' LIMIT 1").fetchone())
                    if observed:
                        break
                    time.sleep(.02)
                assert observed, 'owned HTTP request never entered expected PG parent lock wait'
                time.sleep(2.05); blocker.commit()
                response = future.result(timeout=10)
        ok(response, 403)
        with f[1].connect() as c:
            assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n'] == 0
            assert [x['action'] for x in c.execute('SELECT action FROM service_dispatch_events ORDER BY revision').fetchall()] == ['OFFER']
            assert c.execute('SELECT state FROM service_dispatch_offers').fetchone()['state'] == 'OFFERED'
        assert authority_snapshot(f[1]) == authority
