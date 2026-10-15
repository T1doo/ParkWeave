"""Independent WIP refusal probes; own actual HTTP/ASGI/owned PG, no product edits."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from test_new_enterprise_local_chain import (
    fresh_chain, publish, new_case, material_decision, verify, holds, call,
)
from test_resource_plan_binding import complete_digest

OUT = Path(__file__).parent


@pytest.fixture
def adopted_resource(fresh_chain):
    u = fresh_chain
    values = sorted(set(u['f'][2].values()))
    path = OUT / ('resource-gate-' + uuid4().hex + '.private.json')
    path.write_text(json.dumps(values)); path.chmod(0o600)
    release = publish(u)
    row = new_case(u, release, number=327)
    material_decision(u, row, 'REVIEW')
    material_decision(u, row, 'CONFIRM')
    _, data = holds(u, offset=48)
    bundle = call(u, '/api/resource-bundles', data=data, expected=201)['combination']
    with u['f'][1].connect() as c:
        parent = c.execute('SELECT * FROM preparations WHERE id=%s', (row['preparation_id'],)).fetchone()
    assert len(parent['service_case_plan']['required_goals']) == 6
    assert not parent['service_case_plan'].get('partial_adoption')
    assert not parent['service_case_plan']['adoption_preview'].get('profile') == 'TRUSTED_SERVICE_SELECTION_V4'
    return u, row, bundle


def preview(u, row, bundle):
    return u['f'][3].get('/api/preparations/' + row['preparation_id'] + '/resource-plan-binding',
        params=dict(candidate_combination_id=bundle['id']), headers=headers(u['f'][2]))


def confirm(u, row, bundle, comparison):
    return u['f'][3].post('/api/preparations/' + row['preparation_id'] + '/resource-plan-binding/confirm',
        headers=headers(u['f'][2], key=uuid4().hex), json=dict(combination_id=bundle['id'],
            expected_preparation_revision=comparison['preparation_revision'],
            expected_link_revision=comparison['link_revision'],
            expected_comparison_sha256=comparison['sha256'],
            reason='SYNTHETIC independent exact original resource confirmation refusal'))


def result(name, **details):
    with (OUT / 'resource-gate-probe-observations.jsonl').open('a') as out:
        out.write(json.dumps(dict(scenario=name, **details), sort_keys=True) + '\n')


def test_real_unverified_p1_cannot_confirm(adopted_resource):
    u, row, bundle = adopted_resource
    before = complete_digest(u['f'])
    response = preview(u, row, bundle)
    assert response.status_code == 200, response.text
    q = response.json()['comparison']
    assert not q['can_confirm'] and 'CURRENT_PLAN_P1_REQUIRED' in q['blockers']
    assert complete_digest(u['f']) == before
    rejected = confirm(u, row, bundle, q)
    assert rejected.status_code == 409, rejected.text
    assert complete_digest(u['f']) == before
    result('real_original_p1_never_verified', get=200, post=409, complete_pg_unchanged=True)


@pytest.mark.parametrize('damage', ['history', 'partial', 'unknown_goal', 'p1_snapshot'])
def test_damaged_or_unsupported_plan_does_not_confirm(adopted_resource, damage):
    u, row, bundle = adopted_resource
    verify(u, row, 'P1')
    q = preview(u, row, bundle)
    assert q.status_code == 200 and q.json()['comparison']['can_confirm'], q.text
    comparison = q.json()['comparison']
    with u['f'][1].connect() as c:
        parent = c.execute('SELECT * FROM preparations WHERE id=%s', (row['preparation_id'],)).fetchone()
        plan = deepcopy(parent['service_case_plan'])
        intent = deepcopy(parent['request_intent'])
        if damage == 'history':
            plan['events'][0]['fingerprint'] = '0' * 64
        elif damage == 'partial':
            plan['partial_adoption'] = True
        elif damage == 'unknown_goal':
            intent['required_goals'].append('UNKNOWN_SYNTHETIC_INDEPENDENT_GOAL')
        else:
            plan['steps'][0]['verified_sha256'] = '0' * 64
        c.execute('UPDATE preparations SET service_case_plan=%s,request_intent=%s WHERE id=%s',
            (Jsonb(plan), Jsonb(intent), row['preparation_id']))
    before = complete_digest(u['f'])
    read = preview(u, row, bundle)
    assert read.status_code in (200, 409), read.text
    if read.status_code == 200:
        assert not read.json()['comparison']['can_confirm'], read.text
    assert complete_digest(u['f']) == before
    write = confirm(u, row, bundle, comparison)
    assert write.status_code == 409, write.text
    assert complete_digest(u['f']) == before
    result(damage, get=read.status_code, post=409, complete_pg_unchanged=True,
        fixture_corruption_refusal_only=True)


@pytest.mark.parametrize('capability', ['PREPARE', 'EXECUTE', 'HOLD'])
def test_current_authority_revocation_rejects_old_exact_comparison(adopted_resource, capability):
    u, row, bundle = adopted_resource
    verify(u, row, 'P1')
    q = preview(u, row, bundle)
    assert q.status_code == 200 and q.json()['comparison']['can_confirm'], q.text
    comparison = q.json()['comparison']
    with u['f'][1].connect() as c:
        u['f'][1].lock_principal(c, 'fixture-a', exclusive=True)
        table = {'PREPARE': 'preparation_grants', 'EXECUTE': 'capability_grants',
                 'HOLD': 'synthetic_resource_grants'}[capability]
        c.execute('UPDATE ' + table + ' SET active=false WHERE principal_id=%s AND capability=%s',
            ('fixture-a', capability))
    before = complete_digest(u['f'])
    write = confirm(u, row, bundle, comparison)
    assert write.status_code == 403, write.text
    assert complete_digest(u['f']) == before
    result('current_' + capability + '_revoked', post=403, complete_pg_unchanged=True)
