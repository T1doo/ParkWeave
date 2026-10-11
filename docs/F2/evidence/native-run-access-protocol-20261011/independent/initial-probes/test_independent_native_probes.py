"""Additional owned PostgreSQL probes; never installs effective assignments."""
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from conftest import fixture, pg
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_native_run_access import native_fixture, act, body, ledger, snapshot
from parkweave import native_run_access as native
from parkweave.store import Store
from psycopg.types.json import Jsonb
import psycopg
import pytest


def observe(name, value):
    target = Path(__file__).with_name('initial-probes')
    target.mkdir(exist_ok=True)
    (target / (name + '.json')).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def test_json_null_native_marker_is_not_legacy(native_fixture):
    a = native_fixture
    f, parent, _, before = a
    # SELECT only: simulates psycopg's actual decoding without any assignment write.
    with f[0].connect() as c:
        p = f[0].auth(c, f[2]['executor-a'], lock=True)
        row = c.execute("""SELECT %s::text principal_id, %s::uuid run_id,
            %s::text park_id, %s::text org_id, true active,
            'null'::jsonb native_access, ('null'::jsonb IS NOT NULL) native_sql_present""",
            (p['id'], parent['run_id'], p['park_id'], p['org_id'])).fetchone()
        allowed = Store(f[0].dsn).assignment_allowed(c, p, parent['run_id'], assignment=row)
    observe('json-null-marker', {'native_sql_present': row['native_sql_present'],
                                'python_marker_is_none': row['native_access'] is None,
                                'assignment_allowed': allowed,
                                'authority_snapshot_unchanged': snapshot(f[1]) == before})
    assert not allowed, 'SQL non-NULL native JSON null must not become a legacy assignment'


def test_pg_append_cannot_rewrite_existing_request_on_cancel(native_fixture):
    a = native_fixture
    f, parent, bridge, before = a
    act(a, 'REQUEST')
    original = deepcopy(ledger(a))
    altered = deepcopy(original)
    altered['revision'] = 2
    altered['state'] = 'CANCELLED'
    altered['request']['target_id'] = 'unassigned'
    event = deepcopy(original['events'][-1])
    event.update(action='CANCEL', revision=2, state='CANCELLED',
                 request_key='synthetic-head-tamper', fingerprint='a' * 64,
                 request=deepcopy(altered['request']))
    altered['events'].append(event)
    rejected = False
    try:
        with f[0].connect() as c:
            c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',
                      (Jsonb(altered), parent['run_id']))
    except psycopg.errors.RaiseException:
        rejected = True
    current = ledger(a)
    observe('cancel-request-rewrite', {'rejected': rejected,
        'original_prefix_preserved': current['events'][:1] == original['events'],
        'current_target': current['request']['target_id'],
        'authority_snapshot_unchanged': snapshot(f[1]) == before})
    assert rejected, 'terminal append must preserve the original request head'


def test_pg_append_rejects_self_approval_lease_without_valid_request(native_fixture):
    a = native_fixture
    f, parent, _, before = a
    act(a, 'REQUEST')
    original = deepcopy(ledger(a))
    altered = deepcopy(original)
    altered['revision'] = 2
    altered['state'] = 'APPROVED'
    altered['request']['approver_id'] = 'fixture-a'
    altered['request']['approved_validity'] = altered['request']['requested_validity']
    altered['lease_id'] = str(uuid4())
    altered['leases'].append({'state': 'NON_EFFECTIVE'})
    event = deepcopy(original['events'][-1])
    event.update(action='APPROVE', revision=2, state='APPROVED',
                 request_key='synthetic-self-approve', fingerprint='b' * 64,
                 request=deepcopy(altered['request']), lease_id=altered['lease_id'])
    altered['events'].append(event)
    rejected = False
    try:
        with f[0].connect() as c:
            c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',
                      (Jsonb(altered), parent['run_id']))
    except psycopg.errors.RaiseException:
        rejected = True
    current = ledger(a)
    observe('self-approval-lease', {'rejected': rejected, 'state': current['state'],
        'current_approver': current['request'].get('approver_id'),
        'lease_has_exact_id': bool(current['leases'] and current['leases'][-1].get('id') == current.get('lease_id')),
        'authority_snapshot_unchanged': snapshot(f[1]) == before})
    assert rejected, 'approval append must reject self approval and an unbound lease'


def test_two_request_cycles_keep_original_key_receipt(native_fixture):
    a = native_fixture
    f, parent, bridge, before = a
    first_data = body(a, 'REQUEST')
    first = act(a, 'REQUEST', key='first-cycle-key', data=first_data)
    act(a, 'CANCEL')
    second = act(a, 'REQUEST', key='second-cycle-key')
    act(a, 'REJECT')
    assert first['request']['request_id'] != second['request']['request_id']
    assert bridge.recover(f[2]['fixture-a'], UUID(parent['run_id']), 'first-cycle-key')['receipt'] == first
    assert act(a, 'REQUEST', key='first-cycle-key', data=first_data) == first
    assert ledger(a)['revision'] == 4 and snapshot(f[1]) == before


@pytest.mark.parametrize('marker', [{}, [], False, 'UNKNOWN'])
def test_non_null_unknown_markers_deny_even_cold(native_fixture, marker):
    a = native_fixture
    f, parent, _, before = a
    with f[0].connect() as c:
        p = f[0].auth(c, f[2]['executor-a'], lock=True)
        row = dict(principal_id=p['id'], run_id=UUID(parent['run_id']),
                   park_id=p['park_id'], org_id=p['org_id'], active=True, native_access=marker)
        assert not Store(f[0].dsn).assignment_allowed(c, p, parent['run_id'], assignment=row)
    assert snapshot(f[1]) == before
