"""Fresh enterprise consumption through real isolated PostgreSQL product APIs."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
import pytest

from parkweave.store import Denied
from parkweave.template_candidate import TemplateEngine, TemplateRepository
from parkweave.template_consumer import ConsumerConfig, ConsumerRepository, TemplateConsumer
from parkweave.template_isolated_app import create_isolated_template_app
from template_candidate_support import (PARK, ORGS, ENTERPRISES, REVIEWERS,
    seed_new_enterprises, grant_snapshot)
from test_template_candidate import template_config, publish_template, template_command, advance_source_head


@pytest.fixture
def template_consumption(fixture, tmp_path):
    store, owner, _, _ = fixture
    tokens = seed_new_enterprises(fixture)
    now = [datetime(2026, 10, 7, tzinfo=timezone.utc)]
    engine = TemplateEngine(template_config(), TemplateRepository(tmp_path / 'bridge.template.candidate.sqlite3'), lambda: now[0])
    publish_template(engine)
    release = engine.public_catalog(PARK)['items'][0]
    config = ConsumerConfig(enabled_for_isolated_tests=True,
        allowed_database_names=[conninfo_to_dict(store.dsn)['dbname']],
        allowed_orgs=[{'park_id': PARK, 'org_id': org} for org in ORGS])
    repository = ConsumerRepository(tmp_path / 'bridge.consumer.candidate.sqlite3')
    consumer = TemplateConsumer(store, engine, config, repository)
    with TestClient(create_isolated_template_app(store, engine, consumer)) as client:
        yield dict(store=store, owner=owner, tokens=tokens, engine=engine, release=release,
                   config=config, repository=repository, consumer=consumer, client=client, now=now)


def headers(f, index=0, key=None):
    result = {'Authorization': 'Bearer ' + f['tokens'][ENTERPRISES[index]]}
    if key: result['Idempotency-Key'] = key
    return result


def body(f, index=0):
    return dict(release_id=f['release']['release_id'], expected_release_sha256=f['release']['release_sha256'],
        goal=f'New enterprise {index} explicit fresh request', reviewer_id=REVIEWERS[index],
        materials=[dict(slot='need_summary', text=f'Fresh enterprise {index} need statement',
                        source_kind='USER_STATEMENT', source_label=f'New enterprise {index} statement'),
                   dict(slot='material_outline', text=f'Fresh enterprise {index} submitted materials outline',
                        source_kind='DOCUMENT_EXCERPT', source_label=f'New enterprise {index} document')],
        reason='Explicit new enterprise reusable template adoption')


def products(owner, include_audit=False):
    with owner.connect() as c:
        return {table: c.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()
                for table in ('runs', 'cases', 'operations', 'preparations', 'preparation_evidence',
                              'preparation_events', 'controlled_plans', 'controlled_plan_events',
                              'outbox', 'run_projection', 'model_steps') +
                             (('authorization_audit',) if include_audit else ())}


def consume(f, index=0, key='new-instance', data=None):
    return f['client'].post('/api/template-consumer/instances', headers=headers(f, index, key),
                            json=data or body(f, index))


def resume(f, row, index=0, key='resume-instance'):
    return f['client'].post(f"/api/template-consumer/instances/{row['instance_id']}/resume",
                            headers=headers(f, index, key), json={})


def finish(f):
    work = f['store'].claim('isolated-template-test-worker')
    assert work is not None
    f['store'].finish(work)


def test_two_new_enterprises_get_distinct_case_materials_without_identity_or_grant_writes(template_consumption):
    f = template_consumption
    before = grant_snapshot(f['owner'])
    initial = products(f['owner'])
    assert not initial['runs'] and not initial['cases'] and not initial['preparations']
    results = []
    for index in (0, 1):
        response = consume(f, index, key=f'new-enterprise-{index}')
        assert response.status_code == 201, response.text
        row = response.json()
        assert row['state'] == 'PENDING_RUN' and not row['case_id']
        finish(f)
        result = resume(f, row, index, f'resume-{index}')
        assert result.status_code == 200, result.text
        result = result.json()
        assert result['state'] == 'PLAN_ADOPTED'
        assert not result['case_goal_completed'] and not result['automatic_execution']
        assert result['binding']['org_id'] == ORGS[index]
        assert result['preparation']['preparation']['owner_id'] == ENTERPRISES[index]
        assert result['preparation']['preparation']['state'] == 'IN_PREPARATION'
        results.append(result)
    assert len({r['run_id'] for r in results}) == len({r['case_id'] for r in results}) == 2
    assert len({r['preparation_id'] for r in results}) == len({r['plan_id'] for r in results}) == 2
    saved = products(f['owner'])
    assert len(saved['runs']) == len(saved['cases']) == len(saved['preparations']) == 2
    assert len(saved['preparation_evidence']) == 4
    for index, result in enumerate(results):
        texts = {row['text'] for row in saved['preparation_evidence']
                 if str(row['preparation_id']) == result['preparation_id']}
        assert texts == {m['text'] for m in body(f, index)['materials']}
    assert grant_snapshot(f['owner']) == before


def test_unknown_committed_run_reply_recovers_original_key_without_second_run(template_consumption, monkeypatch):
    f = template_consumption
    before = grant_snapshot(f['owner'])
    original = f['store'].submit
    lost = []
    def submit_then_lose(*args, **kwargs):
        result = original(*args, **kwargs)
        lost.append(result)
        raise RuntimeError('Injected lost committed original Run reply')
    monkeypatch.setattr(f['store'], 'submit', submit_then_lose)
    unknown_reply = consume(f, key='lost-run-reply')
    assert unknown_reply.status_code == 503
    assert unknown_reply.json()['state'] == 'UNKNOWN' and unknown_reply.json()['retry_original_request']
    saved = products(f['owner'])
    assert len(saved['runs']) == 1
    with f['repository'].connect() as c:
        stage = dict(c.execute("SELECT * FROM consumer_stages WHERE name='CREATE_RUN'").fetchone())
        assert stage['state'] == 'UNKNOWN'
    monkeypatch.setattr(f['store'], 'submit', original)
    response = consume(f, key='lost-run-reply')
    assert response.status_code == 201, response.text
    assert response.json()['run_id'] == str(lost[0])
    assert products(f['owner']) == saved
    finish(f)
    completed = resume(f, response.json(), key='resume-after-unknown')
    assert completed.status_code == 200, completed.text
    stable = products(f['owner'])
    replay = resume(f, completed.json(), key='resume-after-unknown')
    assert replay.status_code == 200 and replay.json()['plan_id'] == completed.json()['plan_id']
    assert products(f['owner']) == stable
    assert grant_snapshot(f['owner']) == before


def test_unknown_committed_material_reply_recovers_without_duplicate_case_or_evidence(template_consumption, monkeypatch):
    from parkweave import preparation
    f = template_consumption
    authority = grant_snapshot(f['owner'])
    pending = consume(f, key='lost-material-consume').json()
    finish(f)
    original = preparation.command
    def add_then_lose(*args, **kwargs):
        result = original(*args, **kwargs)
        raise RuntimeError('Injected lost committed original material reply')
    monkeypatch.setattr(preparation, 'command', add_then_lose)
    unknown_reply = resume(f, pending, key='lost-material-resume')
    assert unknown_reply.status_code == 503
    assert unknown_reply.json()['state'] == 'UNKNOWN' and unknown_reply.json()['retry_original_request']
    saved = products(f['owner'])
    assert len(saved['runs']) == len(saved['cases']) == len(saved['preparations']) == 1
    assert len(saved['preparation_evidence']) == 1
    current = f['client'].get(f"/api/template-consumer/instances/{pending['instance_id']}", headers=headers(f)).json()
    assert current['state'] == 'UNKNOWN'
    unknown = next(s for s in current['stages'] if s['state'] == 'UNKNOWN')
    assert unknown['name'].startswith('ADD_')
    monkeypatch.setattr(preparation, 'command', original)
    completed = resume(f, pending, key='lost-material-resume')
    assert completed.status_code == 200, completed.text
    assert completed.json()['state'] == 'PLAN_ADOPTED'
    after = products(f['owner'])
    assert len(after['runs']) == len(after['cases']) == len(after['preparations']) == 1
    assert len(after['preparation_evidence']) == 2
    assert saved['preparation_evidence'][0] in after['preparation_evidence']
    assert grant_snapshot(f['owner']) == authority


def test_unapproved_original_enterprise_and_revoked_reviewer_are_denied(template_consumption, fixture):
    f = template_consumption
    before = products(f['owner'])
    # Original fixture enterprise is intentionally outside the approved org set.
    response = f['client'].post('/api/template-consumer/instances',
        headers={'Authorization': 'Bearer ' + fixture[2]['fixture-a'], 'Idempotency-Key': 'outside-org'}, json=body(f))
    assert response.status_code == 403
    with f['owner'].connect() as c:
        c.execute('UPDATE principals SET active=false WHERE id=%s', (REVIEWERS[0],))
    authority = grant_snapshot(f['owner'])
    assert consume(f).status_code == 403
    assert products(f['owner']) == before and grant_snapshot(f['owner']) == authority


def test_same_key_changed_input_is_conflict_no_additional_product_write(template_consumption):
    f = template_consumption
    response = consume(f, key='immutable-input')
    assert response.status_code == 201
    before = products(f['owner'])
    changed = body(f)
    changed['materials'][0]['text'] = 'Different new material under original request key'
    response = consume(f, key='immutable-input', data=changed)
    assert response.status_code == 409
    assert products(f['owner']) == before


@pytest.mark.parametrize('action', ['read', 'resume', 'reviewer'])
def test_cross_organization_denied_without_product_write(template_consumption, action):
    f = template_consumption
    row = consume(f).json()
    before = products(f['owner'])
    if action == 'read':
        response = f['client'].get(f"/api/template-consumer/instances/{row['instance_id']}", headers=headers(f, 1))
    elif action == 'resume': response = resume(f, row, index=1)
    else:
        data = body(f, 1)
        data['reviewer_id'] = REVIEWERS[0]
        response = consume(f, 1, 'wrong-org-reviewer', data)
    assert response.status_code == 403, response.text
    assert products(f['owner']) == before


@pytest.mark.parametrize('capability', ['READ', 'EXECUTE', 'PREPARE'])
def test_current_permissions_checked_before_same_key_replay(template_consumption, capability):
    f = template_consumption
    assert consume(f, key='pre-revocation').status_code == 201
    with f['owner'].connect() as c:
        table = 'preparation_grants' if capability == 'PREPARE' else 'capability_grants'
        c.execute(f'UPDATE {table} SET active=false WHERE principal_id=%s AND capability=%s', (ENTERPRISES[0], capability))
    before = products(f['owner'])
    permissions = grant_snapshot(f['owner'])
    assert consume(f, key='pre-revocation').status_code == 403
    assert products(f['owner']) == before
    assert grant_snapshot(f['owner']) == permissions
    with f['owner'].connect() as c:
        audit = c.execute('SELECT principal_id,category,outcome FROM authorization_audit').fetchall()
    assert audit == [{'principal_id': ENTERPRISES[0], 'category': 'API_AUTHORIZATION', 'outcome': 'DENIED'}]


@pytest.mark.parametrize('change', ['withdraw', 'contract', 'expiry', 'hash', 'source_head'])
def test_unavailable_or_changed_release_blocks_new_and_resumed_product_work(template_consumption, change):
    f = template_consumption
    pending = consume(f).json()
    before = products(f['owner'])
    if change == 'withdraw': template_command(f['engine'], 'WITHDRAW')
    elif change == 'contract':
        config = template_config()
        config.revision += 1
        f['engine'].replace_contract(config)
    elif change == 'expiry': f['now'][0] = datetime(2100, 1, 1, tzinfo=timezone.utc)
    elif change == 'source_head': advance_source_head(f['engine'])
    else:
        changed = body(f)
        changed['expected_release_sha256'] = '0' * 64
        assert consume(f, key='bad-release-hash', data=changed).status_code == 409
        assert products(f['owner']) == before
        return
    assert consume(f, key='unavailable-new').status_code == 403
    assert resume(f, pending).status_code == 403
    assert products(f['owner']) == before
    current = f['client'].get(f"/api/template-consumer/instances/{pending['instance_id']}", headers=headers(f))
    assert current.status_code == 200 and not current.json()['release_available']


@pytest.mark.parametrize('field,value', [('org_id', ORGS[1]), ('run_id', 'old-run'),
    ('case_id', 'old-case'), ('grants', []), ('execution_enabled', True)])
def test_request_cannot_select_scope_or_reuse_old_record(template_consumption, field, value):
    f = template_consumption
    before = products(f['owner'])
    data = body(f)
    data[field] = value
    assert consume(f, data=data).status_code == 422
    assert products(f['owner']) == before


def test_gets_have_no_product_or_authority_effect_and_disabled_consumer_denied(template_consumption):
    f = template_consumption
    before = products(f['owner'], include_audit=True)
    authority = grant_snapshot(f['owner'])
    for _ in range(2):
        response = f['client'].get('/api/template-consumer/catalog', headers=headers(f))
        assert response.status_code == 200 and len(response.json()['templates']) == 1
    assert products(f['owner'], include_audit=True) == before and grant_snapshot(f['owner']) == authority
    disabled = TemplateConsumer(f['store'], f['engine'])
    with pytest.raises(Denied): disabled.catalog(f['tokens'][ENTERPRISES[0]])


def test_fixture_seed_cannot_target_non_fixture_database():
    class OtherStore:
        dsn = 'dbname=parkweave'
    with pytest.raises(ValueError): seed_new_enterprises(OtherStore())


@pytest.mark.parametrize('kind', ['mismatched_engine', 'disabled_consumer'])
def test_combined_factory_requires_exact_enabled_consumer(template_consumption, kind):
    f = template_consumption
    before = products(f['owner'])
    if kind == 'mismatched_engine':
        engine = TemplateEngine(template_config(), f['engine'].repository)
        with pytest.raises((Denied, ValueError)):
            create_isolated_template_app(f['store'], engine, f['consumer'])
    else:
        disabled = TemplateConsumer(f['store'], f['engine'])
        with pytest.raises((Denied, ValueError)):
            create_isolated_template_app(f['store'], f['engine'], disabled)
    assert products(f['owner']) == before


def test_instances_listing_is_exact_owner_scope_and_read_only(template_consumption):
    f = template_consumption
    mine = consume(f, key='list-owner-a').json()
    theirs = consume(f, 1, key='list-owner-b').json()
    before = products(f['owner'], include_audit=True)
    authority = grant_snapshot(f['owner'])
    response = f['client'].get('/api/template-consumer/instances', headers=headers(f))
    assert response.status_code == 200, response.text
    assert [item['instance_id'] for item in response.json()['items']] == [mine['instance_id']]
    assert theirs['instance_id'] not in response.text
    assert products(f['owner'], include_audit=True) == before and grant_snapshot(f['owner']) == authority


def test_completed_instance_keeps_immutable_release_binding_after_new_source_head(template_consumption):
    f = template_consumption
    pending = consume(f, key='completed-history').json()
    finish(f)
    completed = resume(f, pending, key='complete-before-source-change')
    assert completed.status_code == 200
    saved_binding = deepcopy(completed.json()['binding'])
    before = products(f['owner'])
    authority = grant_snapshot(f['owner'])
    advance_source_head(f['engine'])
    read = f['client'].get(f"/api/template-consumer/instances/{pending['instance_id']}", headers=headers(f))
    assert read.status_code == 200, read.text
    current = read.json()
    assert current['binding'] == saved_binding
    assert current['state'] == 'PLAN_ADOPTED' and not current['release_available']
    assert resume(f, pending, key='complete-before-source-change').status_code == 403
    assert products(f['owner']) == before and grant_snapshot(f['owner']) == authority


def test_original_product_conflict_is_definite_refusal_not_unknown(template_consumption):
    from parkweave import preparation
    f = template_consumption
    pending = consume(f, key='definite-refusal').json()
    finish(f)
    existing = f['client'].post('/api/preparations', headers=headers(f, key='original-case-preparation'),
        json={'run_id': pending['run_id'], 'service_id': preparation.SERVICE,
              'service_version': 1, 'reviewer_id': REVIEWERS[0]})
    assert existing.status_code == 201, existing.text
    before = products(f['owner'])
    refusal = resume(f, pending, key='refused-resume')
    assert refusal.status_code == 409, refusal.text
    current = f['client'].get(f"/api/template-consumer/instances/{pending['instance_id']}", headers=headers(f))
    assert current.status_code == 200
    assert current.json()['state'] == 'BLOCKED'
    refused = next(s for s in current.json()['stages'] if s['name'] == 'CREATE_PREPARATION')
    assert refused['state'] == 'REFUSED' and refused['error'] == 'PRODUCT_CONFLICT'
    assert resume(f, pending, key='refused-resume').status_code == 409
    assert products(f['owner']) == before
    with f['repository'].connect() as c:
        assert c.execute('SELECT count(*) FROM consumer_instances').fetchone()[0] == 1


def test_product_commit_then_journal_confirmation_failure_is_unknown_and_recovers(template_consumption, monkeypatch):
    from contextlib import contextmanager
    f = template_consumption
    original_connect = f['repository'].connect
    injected = []
    class ConfirmationFault:
        def __init__(self, connection): self.connection = connection
        def execute(self, sql, *args):
            if "UPDATE consumer_stages SET state='CONFIRMED'" in sql and not injected:
                injected.append(True)
                raise RuntimeError('Injected journal write failure after real PostgreSQL commit')
            return self.connection.execute(sql, *args)
    @contextmanager
    def connect_with_confirmation_fault(write=False):
        with original_connect(write=write) as connection:
            yield ConfirmationFault(connection)
    monkeypatch.setattr(f['repository'], 'connect', connect_with_confirmation_fault)
    response = consume(f, key='committed-before-journal-fault')
    assert response.status_code == 503 and response.json()['state'] == 'UNKNOWN'
    saved = products(f['owner'], include_audit=True)
    assert len(saved['runs']) == 1
    monkeypatch.setattr(f['repository'], 'connect', original_connect)
    with f['repository'].connect() as c:
        stage = dict(c.execute("SELECT * FROM consumer_stages WHERE name='CREATE_RUN'").fetchone())
        assert stage['state'] == 'UNKNOWN'
        original_body = (stage['request_key'], stage['body_sha256'], stage['body'])
    recovered = consume(f, key='committed-before-journal-fault')
    assert recovered.status_code == 201, recovered.text
    assert products(f['owner'], include_audit=True) == saved
    with f['repository'].connect() as c:
        stage = dict(c.execute("SELECT * FROM consumer_stages WHERE name='CREATE_RUN'").fetchone())
        assert stage['state'] == 'CONFIRMED'
        assert (stage['request_key'], stage['body_sha256'], stage['body']) == original_body


def test_old_live_consumer_cannot_use_release_after_separate_engine_advances_contract_head(template_consumption):
    f = template_consumption
    pending = consume(f, key='durable-head-consume').json()
    before = products(f['owner'])
    authority = grant_snapshot(f['owner'])
    newer = template_config()
    newer.revision = 2
    newer.permits[2].active = False
    advanced = TemplateEngine(newer, TemplateRepository(f['engine'].repository.path), lambda: f['now'][0])
    assert not advanced.public_catalog(PARK)['items']
    response = resume(f, pending, key='stale-live-resume')
    assert response.status_code in (403, 409), response.text
    response = consume(f, key='durable-head-consume')
    assert response.status_code in (403, 409), response.text
    assert products(f['owner']) == before and grant_snapshot(f['owner']) == authority
    with f['repository'].connect() as c:
        assert c.execute('SELECT count(*) FROM consumer_instances').fetchone()[0] == 1
