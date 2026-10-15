"""Independent literal oracles: original HTML -> actual HTTP -> ASGI -> owned PG."""
from copy import deepcopy
import json
from pathlib import Path
import selectors
import subprocess
from uuid import uuid4

import pytest

from parkweave.api import create_app
from parkweave import registered_dependencies
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from test_case_opportunities import get as opportunities, post as opportunity_command, body as opportunity_body, entry
from test_service_case_steps import setup, adopt, read, GOALS
from test_service_plan_manual_lock import lock, stored
from test_case_goal_results import snapshot, complete
from test_registered_local_revision import add_resource
from test_new_enterprise_local_chain import (
    actual_http, fresh_chain, publish, new_case, enable_approval, finish_chain,
    original_rows,
)

OUT = Path('.runtime/source-adoption-independent')


@pytest.fixture
def source_adoption_http(link_fixture):
    with actual_http(create_app(link_fixture[0])) as (client, requests):
        yield (*link_fixture[:3], client), requests


def imported_source(f, p):
    response = opportunity_command(f, p, opportunity_body(opportunities(f, p).json(), item=entry()))
    assert response.status_code == 200, response.text
    return response.json()['current']['cards'][-1]


def preview(f, p, card, actor='fixture-a'):
    return f[3].get('/api/preparations/' + p['preparation_id'] + '/opportunities/' + card['id'] + '/plan-revision', headers=headers(f[2], actor))


def bounded_change(f):
    p, _, _, _ = complete(f, local=True)
    card = imported_source(f, p)
    resource = add_resource(f)
    response = preview(f, p, card)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['can_adopt'], json.dumps(value, ensure_ascii=False)
    return p, card, resource, value


def write_adoption(f, p, data, actor='fixture-a', key=None):
    return f[3].post('/api/preparations/' + p['preparation_id'] + '/service-case-plan', headers=headers(f[2], actor, key or uuid4().hex), json=data)


def run_original_page(u, row, mode, controls):
    OUT.mkdir(parents=True, exist_ok=True)
    attempt = mode + '-' + uuid4().hex[:8]
    process = subprocess.Popen(['node', 'tests/opportunity_plan_adoption_real_html.js'], cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = []
    try:
        process.stdin.write(json.dumps(dict(base=u['base'], token=u['f'][2]['fixture-a'], preparation_id=row['preparation_id'], plan_id=row['plan_id'], mode=mode)) + '\n')
        process.stdin.flush()
        result = None
        while True:
            assert selector.select(timeout=40), 'Full original HTML made no progress within 40 seconds'
            line = process.stdout.readline()
            if not line:
                break
            output.append(line)
            message = json.loads(line)
            if 'control' in message:
                assert message['control'] in controls, message
                controls[message['control']]()
                process.stdin.write('{}\n')
                process.stdin.flush()
            else:
                result = message
                break
        code = process.wait(timeout=10)
        error = process.stderr.read()
        (OUT / (attempt + '.stdout.jsonl')).write_text(''.join(output))
        (OUT / (attempt + '.stderr.log')).write_text(error)
        assert code == 0, error
        assert result and result['checks'] >= (12 if mode.startswith('late_') else 20)
        assert result['scope'] == 'FULL_ORIGINAL_HTML_REAL_HTTP_ASGI_OWNED_POSTGRESQL'
        return result
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


@pytest.mark.parametrize('mode', ['positive', 'lost'])
def test_original_html_explicit_same_case_source_adoption_and_six_goal_evidence(fresh_chain, mode):
    u = fresh_chain
    row = new_case(u, publish(u))
    enable_approval(u, [row])
    finish_chain(u, row)
    f = u['f']
    assert lock(f, row, 'P1').status_code == 200
    before = deepcopy(stored(f, row))
    business_before = original_rows(u, row)

    def after_adopt():
        current = stored(f, row)
        assert current['id'] == before['id']
        assert [step['id'] for step in current['steps']] == [step['id'] for step in before['steps']]
        assert current['events'][:-1] == before['events']
        assert current['history'] == before['history']
        assert current['steps'][0] == before['steps'][0]
        assert all(new['verified_sources'] == old['verified_sources'] for new, old in zip(current['steps'], before['steps']))
        event = current['events'][-1]
        assert event['action'] == 'ADOPT'
        assert set(event['local_revision']['affected']) == {step['id'] for step in before['steps'][1:]}
        assert set(event['local_revision']['preserved']) == {before['steps'][0]['id']}
        current_rows = original_rows(u, row)
        for table, rows in business_before.items():
            if table == 'preparations':
                ignored = {'service_case_plan', 'opportunities'}
                assert [{key: value for key, value in r.items() if key not in ignored} for r in rows] == [{key: value for key, value in r.items() if key not in ignored} for r in current_rows[table]]
            else:
                assert current_rows[table] == rows

    result = run_original_page(u, row, mode, {'change_source': lambda: add_resource(f), 'after_adopt': after_adopt})
    after = stored(f, row)
    assert after['steps'][0] == before['steps'][0]
    assert after['events'][:len(before['events'])] == before['events']
    assert after['required_goals'] == before['required_goals'] and len(after['required_goals']) == 6
    posts = [call for call in result['calls'] if call['method'] == 'POST']
    assert len(posts) == 7  # IMPORT, REFRESH, ADOPT, four affected VERIFY.
    assert all(call['status'] < 400 for call in result['calls'])


@pytest.mark.parametrize('actor', ['fixture-b', 'fixture-c', 'prep-specialist-fixture-a', 'executor-a'])
def test_independent_foreign_owner_tenant_or_role_cannot_preview_or_adopt(source_adoption_http, actor):
    f, requests = source_adoption_http
    p, card, resource, value = bounded_change(f)
    before = snapshot(f)
    assert preview(f, p, card, actor).status_code == 403
    assert write_adoption(f, p, value['adoption'], actor).status_code == 403
    assert snapshot(f) == before
    assert requests and all(request['path'].startswith('/api/') for request in requests)


@pytest.mark.parametrize('capability', ['READ', 'PREPARE', 'EXECUTE', 'active'])
def test_independent_current_revocation_precedes_opportunity_proof_replay(source_adoption_http, capability):
    f, _ = source_adoption_http
    p, card, resource, value = bounded_change(f)
    key = uuid4().hex
    response = write_adoption(f, p, value['adoption'], key=key)
    assert response.status_code == 201, response.text
    with f[1].connect() as c:
        f[1].lock_principal(c, 'fixture-a', exclusive=True)
        if capability == 'active':
            c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        else:
            table = 'preparation_grants' if capability == 'PREPARE' else 'capability_grants'
            change = 'active=false' if capability == 'PREPARE' else 'active=false,revision=revision+1'
            c.execute('UPDATE ' + table + ' SET ' + change + " WHERE principal_id='fixture-a' AND capability=%s", (capability,))
    before = snapshot(f)
    assert write_adoption(f, p, value['adoption'], key=key).status_code == 403
    recovery = f[3].get('/api/preparations/' + p['preparation_id'] + '/service-case-plan/command-recovery', headers=headers(f[2], key=key))
    assert recovery.status_code == 403
    assert snapshot(f) == before


@pytest.mark.parametrize('action', ['IGNORE', 'WITHDRAW', 'new-generation'])
def test_independent_card_invalidation_never_adopts_or_refreshes_back_to_pending(source_adoption_http, action):
    f, _ = source_adoption_http
    p, card, resource, value = bounded_change(f)
    view = opportunities(f, p).json()
    data = opportunity_body(view, item={**card['entry'], 'generation': 2}) if action == 'new-generation' else opportunity_body(view, action, card=card)
    response = opportunity_command(f, p, data)
    assert response.status_code == 200, response.text
    before = snapshot(f)
    assert write_adoption(f, p, value['adoption']).status_code == 409
    assert snapshot(f) == before
    current = response.json()['current']
    refreshed = opportunity_command(f, p, opportunity_body(current, 'REFRESH'))
    assert refreshed.status_code == 200
    old = next(c for c in refreshed.json()['current']['cards'] if c['id'] == card['id'])
    if action != 'new-generation':
        assert old['state'] == {'IGNORE': 'IGNORED', 'WITHDRAW': 'WITHDRAWN'}[action]
    else:
        assert not old['is_latest_generation']
    refused = preview(f, p, old)
    assert refused.status_code == 409 or (refused.status_code == 200 and refused.json()['can_adopt'] is False)


def test_independent_same_key_conflict_and_source_aba_reject_stale_preview(source_adoption_http):
    f, _ = source_adoption_http
    p, card, resource, value = bounded_change(f)
    with f[1].connect() as c:
        c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s', (resource,))
    with f[1].connect() as c:
        c.execute('UPDATE synthetic_resources SET capacity=capacity-1 WHERE id=%s', (resource,))
    before = snapshot(f)
    assert write_adoption(f, p, value['adoption']).status_code == 409
    assert snapshot(f) == before
    current = preview(f, p, card)
    assert current.status_code == 200, current.text
    key = uuid4().hex
    data = current.json()['adoption']
    response = write_adoption(f, p, data, key=key)
    assert response.status_code == 201, response.text
    committed = snapshot(f)
    assert write_adoption(f, p, data, key=key).status_code == 201
    assert write_adoption(f, p, {**data, 'reason': 'SYNTHETIC conflicting explicit reason'}, key=key).status_code == 409
    assert snapshot(f) == committed


def test_independent_unknown_sources_do_not_turn_hint_into_adoption(source_adoption_http, monkeypatch):
    f, _ = source_adoption_http
    p, card, resource, value = bounded_change(f)
    monkeypatch.setattr(registered_dependencies, 'COLLECTION_LIMIT', 1)
    before = snapshot(f)
    response = preview(f, p, card)
    assert response.status_code == 200, response.text
    assert response.json()['can_adopt'] is False
    assert write_adoption(f, p, value['adoption']).status_code == 409
    assert snapshot(f) == before


@pytest.mark.parametrize('source_kind', ['UNKNOWN', 'UNREVIEWED_REAL_SOURCE'])
def test_independent_unavailable_source_refresh_cannot_authorize_old_hint(source_adoption_http, source_kind):
    from psycopg.types.json import Jsonb
    f, _ = source_adoption_http
    p, card, _, value = bounded_change(f)
    with f[1].connect() as c:
        c.execute('UPDATE preparation_catalog SET source=%s WHERE park_id=%s AND service_id=%s', (Jsonb({'kind': source_kind}), 'park-a', 'synthetic-material-preparation'))
    before = snapshot(f)
    assert write_adoption(f, p, value['adoption']).status_code == 409
    assert snapshot(f) == before
    current = opportunities(f, p).json()
    refreshed = opportunity_command(f, p, opportunity_body(current, 'REFRESH'))
    assert refreshed.status_code == 200, refreshed.text
    old = next(c for c in refreshed.json()['current']['cards'] if c['id'] == card['id'])
    assert old['current_catalog_available'] is False
    assert old['source_binding_current'] is False
    assert preview(f, p, old).status_code == 409


@pytest.mark.parametrize('mode', ['late_draft', 'late_identity_aba', 'late_denied'])
def test_original_html_source_preview_late_context_does_not_replace_current_view(source_adoption_http, mode):
    f, _ = source_adoption_http
    p, _, _, _ = complete(f, local=True)
    p = {**p, 'plan_id': stored(f, p)['id']}
    before = deepcopy(stored(f, p))

    def authority(active):
        with f[1].connect() as c:
            f[1].lock_principal(c, 'fixture-a', exclusive=True)
            c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'", (active,))

    u = {'f': f, 'base': str(f[3].base_url).rstrip('/')}
    result = run_original_page(u, p, mode, {'change_source': lambda: add_resource(f), 'revoke_read': lambda: authority(False), 'restore_read': lambda: authority(True)})
    assert stored(f, p)['events'] == before['events']
    assert [call['body']['action'] for call in result['calls'] if call['method'] == 'POST'] == ['IMPORT', 'REFRESH']
