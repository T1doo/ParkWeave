"""Owned PostgreSQL authorization-lock ordering probe, no permission updates."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from conftest import fixture, pg
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_native_run_access import native_fixture, act, body, ledger, snapshot
from parkweave.store import Conflict, Denied


def test_current_permission_writer_queue_does_not_deadlock_protocol(native_fixture, monkeypatch):
    a = native_fixture
    f, parent, bridge, before = a
    act(a, 'REQUEST')
    approve_data, cancel_data = body(a, 'APPROVE'), body(a, 'CANCEL')
    approval_holds_parent = Event()
    proceed_approval = Event()
    writer_ready = Event()
    writer_pid = []
    original = bridge._participants_current

    def gated(c, run, request):
        if not approval_holds_parent.is_set():
            approval_holds_parent.set()
            assert proceed_approval.wait(5), 'owned approval gate timed out'
        return original(c, run, request)

    monkeypatch.setattr(bridge, '_participants_current', gated)

    def submit(action, data):
        try:
            return {'outcome': 'COMMITTED', 'receipt': act(a, action, data=data)}
        except (Conflict, Denied) as e:
            return {'outcome': type(e).__name__, 'message': str(e)}
        except Exception as e:
            return {'outcome': 'UNHANDLED', 'type': type(e).__name__,
                    'sqlstate': getattr(e, 'sqlstate', None), 'message': str(e)}

    def permission_writer():
        # Uses the exact existing exclusive authorization lock, without mutation.
        with f[1].connect() as c:
            c.execute("SET LOCAL lock_timeout='8s'")
            writer_pid.append(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
            writer_ready.set()
            f[1].lock_principal(c, 'fixture-a', exclusive=True)
        return {'outcome': 'LOCKED_AND_RELEASED', 'permission_updates': 0}

    def wait_for(query, params=()):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            with f[1].connect() as c:
                if c.execute(query, params).fetchone():
                    return True
            Event().wait(.01)
        return False

    with ThreadPoolExecutor(max_workers=3) as pool:
        approve = pool.submit(submit, 'APPROVE', approve_data)
        assert approval_holds_parent.wait(3)
        cancel = pool.submit(submit, 'CANCEL', cancel_data)
        parent_wait_observed = wait_for("""SELECT 1 FROM pg_stat_activity
            WHERE datname=current_database() AND wait_event_type='Lock'
            AND query LIKE 'SELECT * FROM preparations%FOR UPDATE%'""")
        assert parent_wait_observed
        writer = pool.submit(permission_writer)
        assert writer_ready.wait(3)
        permission_wait_observed = wait_for("""SELECT 1 FROM pg_stat_activity a
            JOIN pg_locks l ON l.pid=a.pid WHERE a.pid=%s AND a.wait_event_type='Lock'
            AND l.locktype='advisory' AND l.mode='ExclusiveLock' AND NOT l.granted""",
            (writer_pid[0],))
        assert permission_wait_observed
        proceed_approval.set()
        results = {'approve': approve.result(timeout=8), 'cancel': cancel.result(timeout=8),
                   'permission_writer': writer.result(timeout=8),
                   'parent_wait_observed': parent_wait_observed,
                   'permission_wait_observed': permission_wait_observed,
                   'authority_snapshot_unchanged': snapshot(f[1]) == before,
                   'ledger_revision': ledger(a)['revision']}
    target = Path(os.environ['PARKWEAVE_INDEPENDENT_NATIVE_OBSERVATIONS']) / 'lock-queue-observation.json'
    target.write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    assert all(results[key]['outcome'] != 'UNHANDLED' for key in ('approve', 'cancel')), results
    assert results['authority_snapshot_unchanged']
