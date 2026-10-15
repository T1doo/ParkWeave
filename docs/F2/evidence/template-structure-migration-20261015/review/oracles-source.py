"""Independent contract probes; real original P1–P5 effects, six immutable goals."""
from copy import deepcopy
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from pathlib import Path
from uuid import uuid4
import json
import os
import sqlite3
import subprocess
import sys
import pytest
import psycopg
from parkweave.store import Conflict

from test_template_upgrade import (upgrade_case, publication, instance, check, choose,
                                  link_fixture, receipt_fixture, preparation_fixture,
                                  plan_read, plan_command, verified, headers)
import test_template_migration_independent as original

SIX = ['LOCAL_MATERIAL_PREPARATION', 'LOCAL_CASE_RESOURCE_ASSOCIATION',
       'LOCAL_INTERNAL_ACCEPTANCE', 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
       'LOCAL_SYNTHETIC_COORDINATION_RECORDS', 'LOCAL_CASE_RECORD_RECHECK']


@pytest.fixture(autouse=True)
def record_private_fixture_sessions(upgrade_case):
    pool = Path('.runtime/template-structure-review-20261015/redaction-values.private.json')
    values = json.loads(pool.read_text()) if pool.exists() else []
    pool.write_text(json.dumps(sorted(set(values) | set(upgrade_case['f'][2].values()))))
    pool.chmod(0o600)


def full_six(u, *, verify_last=True):
    original_post = u['client'].post

    def post(path, **kwargs):
        if path == '/api/template-consumer/instances':
            kwargs['json'] = {**kwargs['json'], 'required_goals': SIX}
        return original_post(path, **kwargs)

    def build_instance(u, ignored):
        with patch.object(u['client'], 'post', post):
            return instance(u, SIX[:4])

    verify = original.verified
    def verify_selected(f, p, adapter):
        if adapter == 'P5' and not verify_last:
            return None
        return verify(f, p, adapter)

    with patch.object(original, 'instance', build_instance), patch.object(original, 'verified', verify_selected):
        return original.full(u)


def test_fixture_has_actual_all_six_without_rewriting_original_request(upgrade_case):
    u = upgrade_case
    row, release, p = full_six(u)
    plan = original.stored(u, row)
    assert plan['required_goals'] == SIX
    assert plan['binding']['request_intent']['required_goals'] == SIX
    assert [s['adapter_id'] for s in plan['steps']] == ['P1', 'P2', 'P3', 'P4', 'P5']
    assert row['binding']['release_snapshot']['definition']['required_goals'] == SIX[:4]
    view = plan_read(u['f'], p).json()
    assert view['state'] == 'VERIFIED'
    result = u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',
        headers=headers(u['f'][2]))
    assert result.status_code == 200, result.text
    assert len(result.json()['results']) == 6
    assert result.json()['state'] == 'LOCAL_OUTPUTS_VERIFIED'


def structure_admit(u, row, target):
    v, data = original.admit(u, row, target)
    data.update(confirm_structure_change=True,
                expected_structure_sha256=v['application']['structure_sha256'])
    return v, data


def structure_apply(u, row, data, key=None):
    return u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply-structure',
        headers=headers(u['f'][2], key=key or uuid4().hex), json=data)


def test_independent_three_hop_structure_sources_and_preserved_lock(upgrade_case):
    u = upgrade_case
    row, release, p = full_six(u)
    before = deepcopy(original.stored(u, row))
    facts = original.facts(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    view, data = structure_admit(u, row, target)
    assert view['application']['eligible'], view['application']
    assert view['application']['affected'] == [before['steps'][-1]['id']]
    first_key = uuid4().hex
    result = structure_apply(u, row, data, first_key)
    assert result.status_code in (200, 201), result.text
    first_event = deepcopy(result.json()['event'])
    current = plan_read(u['f'], p).json()
    for a, b in zip(before['steps'][:-1], current['steps'][:-1]):
        assert b['state'] == 'VERIFIED'
        assert b['source_sha256'] == a['verified_sha256']
    assert current['steps'][-1]['source_sha256'] != before['steps'][-1]['verified_sha256']
    verified(u['f'], p, 'P5')
    first = deepcopy(original.stored(u, row))
    current = plan_read(u['f'], p).json()
    locked = plan_command(u['f'], p, 'P1', 'LOCK', row=current,
        expected_source_sha256=current['steps'][0]['source_sha256'])
    assert locked.status_code == 200, locked.text
    p1_lock = deepcopy(original.stored(u, row)['steps'][0]['manual_lock'])
    target2 = publication(u, SIX[:4]+[SIX[-1], SIX[4]])
    v2, d2 = structure_admit(u, row, target2)
    assert v2['check']['classification'] == 'NEEDS_RECHECK', v2
    assert v2['application']['eligible'], v2['application']
    assert v2['application']['affected'] == [s['id'] for s in first['steps'][3:]]
    result2 = structure_apply(u, row, d2)
    assert result2.status_code in (200, 201), result2.text
    current = plan_read(u['f'], p).json()
    assert current['steps'][0]['manually_locked']
    assert original.stored(u, row)['steps'][0]['manual_lock'] == p1_lock
    for adapter in ('P4', 'P5'):
        verified(u['f'], p, adapter)
    before_description = deepcopy(original.stored(u, row))
    target3 = publication(u, SIX[:4]+[SIX[-1], SIX[4]], name='SYNTHETIC description only')
    v3, d3 = original.admit(u, row, target3, 'ACK_COMPATIBLE')
    assert v3['application']['eligible'], v3
    assert not v3['application']['affected']
    result3 = original.apply(u, row, d3)
    assert result3.status_code in (200, 201), result3.text
    final = original.stored(u, row)
    assert [s['id'] for s in final['steps']] == [s['id'] for s in before['steps']]
    assert final['required_goals'] == before['required_goals'] == SIX
    assert final['goal_coverage'] == before['goal_coverage']
    assert final['steps'] == before_description['steps']
    assert final['events'][:len(before['events'])] == before['events']
    assert original.facts(u) == facts
    recovered = original.recovery(u, row, first_key)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['event'] == first_event
    assert recovered.json()['effective_release_id'] == target['release_id']
    goals = u['client'].get('/api/preparations/'+row['preparation_id']+'/goal-results',
        headers=headers(u['f'][2]))
    assert goals.status_code == 200, goals.text
    assert goals.json()['state'] == 'LOCAL_OUTPUTS_VERIFIED'
    assert len(goals.json()['results']) == 6


@pytest.mark.parametrize('damage', ['extra_patch', 'extra_structure', 'missing_confirmation',
                                  'integer_confirmation', 'wrong_structure_hash', 'initial_intent'])
def test_independent_closed_structure_and_initial_intent_proofs(upgrade_case, damage):
    u = upgrade_case
    row, _, _ = full_six(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    _, data = structure_admit(u, row, target)
    result = structure_apply(u, row, data)
    assert result.status_code in (200, 201), result.text
    with u['f'][1].connect() as c:
        parent = deepcopy(c.execute('SELECT * FROM preparations WHERE id=%s',
            (row['preparation_id'],)).fetchone())
    patch_data = parent['service_case_plan']['events'][-1]['template_upgrade']
    if damage == 'extra_patch':
        patch_data['unproved'] = True
    elif damage == 'extra_structure':
        patch_data['structure_change']['unproved'] = True
    elif damage == 'missing_confirmation':
        patch_data['request'].pop('confirm_structure_change')
    elif damage == 'integer_confirmation':
        patch_data['request']['confirm_structure_change'] = 1
    elif damage == 'wrong_structure_hash':
        patch_data['request']['expected_structure_sha256'] = '0'*64
    elif damage == 'initial_intent':
        parent['service_case_plan']['binding']['request_intent']['required_goals'] = SIX[:4]
    from parkweave import service_case_steps
    with pytest.raises(Conflict):
        service_case_steps._recovery_proofs(parent)


def test_independent_structure_source_choice_leases_at_actual_pg_commit(upgrade_case, monkeypatch):
    u = upgrade_case
    row, _, _ = full_six(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    _, data = structure_admit(u, row, target)
    native_commit = psycopg.Connection.commit
    observed = []

    def commit(c):
        if c.info.user == 'parkweave_app' and not observed:
            current = c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',
                (row['preparation_id'],)).fetchone()
            if current and current['service_case_plan']['events'][-1]['request_key'] == 'structure-review-real-commit':
                locks = []
                for path in (u['engine'].repository.path, u['repository'].path):
                    concurrent = sqlite3.connect(path, timeout=0)
                    try:
                        concurrent.execute('BEGIN IMMEDIATE')
                        concurrent.execute('PRAGMA user_version=0')
                        concurrent.commit()
                        locks.append(False)
                    except sqlite3.OperationalError:
                        locks.append(True)
                    finally:
                        concurrent.rollback()
                        concurrent.close()
                observed.append(locks)
        return native_commit(c)

    monkeypatch.setattr(psycopg.Connection, 'commit', commit)
    result = structure_apply(u, row, data, 'structure-review-real-commit')
    assert result.status_code in (200, 201), result.text
    assert observed == [[True, True]], observed


def test_independent_complete_old_package_reader_refuses_structure_without_undo(upgrade_case):
    from parkweave import controlled_plans
    u = upgrade_case
    row, _, _ = full_six(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    _, data = structure_admit(u, row, target)
    result = structure_apply(u, row, data)
    assert result.status_code in (200, 201), result.text
    before = deepcopy(original.stored(u, row))
    facts = original.facts(u)
    with u['f'][1].connect() as c:
        parent = c.execute('SELECT * FROM preparations WHERE id=%s', (row['preparation_id'],)).fetchone()
    old = Path('.runtime/template-structure-review-20261015/old-package/src').resolve()
    env = {**os.environ, 'PYTHONPATH': str(old)}
    program = '''import json,sys
from pathlib import Path
from parkweave import service_case_steps
from parkweave.store import Conflict
assert Path(service_case_steps.__file__).resolve().is_relative_to(Path(sys.argv[1]))
try: service_case_steps._recovery_proofs(json.load(sys.stdin))
except Conflict: print("OLD_FULL_PACKAGE_REFUSED_STRUCTURE_EVENT")
else: raise SystemExit("old reader silently accepted unknown structure semantics")
'''
    run = subprocess.run([sys.executable, '-c', program, str(old)],
        input=json.dumps(controlled_plans._normal(parent)), text=True, capture_output=True, env=env)
    assert run.returncode == 0, run.stdout+run.stderr
    assert run.stdout.strip() == 'OLD_FULL_PACKAGE_REFUSED_STRUCTURE_EVENT'
    assert original.stored(u, row) == before
    assert original.facts(u) == facts


@pytest.mark.parametrize('change', ['expiry', 'withdraw', 'revoke'])
def test_independent_structure_current_authority_after_real_pg_wait(upgrade_case, change):
    from parkweave.template_candidate import Command
    u = upgrade_case
    row, _, _ = full_six(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    _, data = structure_admit(u, row, target)
    before = deepcopy(original.stored(u, row))
    clock = u['engine'].clock
    with u['f'][1].connect() as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        if change == 'revoke':
            u['f'][1].lock_principal(blocker, 'fixture-a', exclusive=True)
        else:
            blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE', (row['preparation_id'],))
        future = pool.submit(structure_apply, u, row, data, 'structure-wait-'+change)
        waiting = False
        for _ in range(150):
            with u['f'][1].connect() as c:
                waiting = bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename='parkweave_app' AND wait_event_type='Lock' AND pid<>pg_backend_pid()").fetchone())
            if waiting:
                break
            Event().wait(.02)
        assert waiting, 'actual owned PostgreSQL lock wait was not observed'
        if change == 'expiry':
            u['engine'].clock = lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
        elif change == 'withdraw':
            head = u['engine'].read('template-publisher', u['scope'])
            u['engine'].command('template-publisher', u['scope'], uuid4().hex,
                Command(action='WITHDRAW', expected_revision=head['revision'],
                    expected_definition_sha256=head['definition_sha256'], reason='SYNTHETIC current authority withdrawal during PG wait'))
        else:
            blocker.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        blocker.commit()
        response = future.result(timeout=8)
    u['engine'].clock = clock
    assert response.status_code in (403, 409), response.text
    assert original.stored(u, row) == before


def test_independent_structure_pending_original_p5_explicitly_refused(upgrade_case):
    u = upgrade_case
    row, _, _ = full_six(u, verify_last=False)
    before = deepcopy(original.stored(u, row))
    assert before['steps'][-1]['verified_sha256'] is None
    target = publication(u, SIX[:4]+[SIX[-1]])
    view = check(u, row, target)
    assert view.status_code == 200, view.text
    application = view.json()['application']
    assert not application['eligible']
    assert any('VERIFIED' in blocker for blocker in application['blockers']), application
    assert original.stored(u, row) == before


@pytest.mark.parametrize('wrong_version', [True, 1.0], ids=['boolean', 'floating'])
def test_independent_semantic_version_alias_real_storage_refused(upgrade_case, wrong_version):
    from psycopg.types.json import Jsonb
    u = upgrade_case
    row, _, _ = full_six(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    _, data = structure_admit(u, row, target)
    key = uuid4().hex
    result = structure_apply(u, row, data, key)
    assert result.status_code in (200, 201), result.text
    damaged = deepcopy(original.stored(u, row))
    damaged['events'][-1]['template_upgrade']['structure_change']['version'] = wrong_version
    with u['f'][1].connect() as c:
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',
            (Jsonb(damaged), row['preparation_id']))
    response = original.recovery(u, row, key)
    assert response.status_code == 409, response.text
