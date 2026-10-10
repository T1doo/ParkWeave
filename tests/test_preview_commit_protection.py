"""Real HTTP/PG/SQLite barriers at the former final-sample/commit gap."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from queue import Queue
from threading import Event
from uuid import UUID, uuid4
import sqlite3
import time

import pytest
from psycopg.types.json import Jsonb
from parkweave import catalog_publication as catalogs, isolated_execution_preview as ep
from parkweave.api import create_app
from test_new_enterprise_local_chain import actual_http
from test_isolated_execution_preview import preparation_fixture, setup, body, execute, read, snapshot
from test_isolated_run_access import access_fixture, receipt_fixture, approved
from test_service_plan_approval import enable
from test_catalog_approval_coordination import publish
from test_preparation import add
from test_request_intents import save


@contextmanager
def http(f):
    with actual_http(create_app(f[0])) as (client, requests):
        yield (*f[:3], client), requests


def pause_final(monkeypatch):
    entered, release = Event(), Event()
    original = ep.planning._proposal
    calls = [0]
    def sampled(*args):
        value = original(*args)
        calls[0] += 1
        if calls[0] == 2:
            entered.set()
            assert release.wait(10), 'final-sample barrier timed out'
        return value
    monkeypatch.setattr(ep.planning, '_proposal', sampled)
    return entered, release


def wait_lock(f, pid):
    end = time.monotonic() + 5
    while time.monotonic() < end:
        with f[1].connect() as c:
            row = c.execute("SELECT 1 FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock'", (pid,)).fetchone()
        if row:
            return
        time.sleep(.02)
    raise AssertionError('real PG lock wait not observed')


def assert_snapshot_semantics(x):
    assert x['source_atomicity'] is False
    assert x['source_consistency'] == 'COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON'
    assert {h['source_state'] for h in x['history']} <= {'SNAPSHOT_MATCH', 'STALE'}


@pytest.mark.parametrize('action', ['PUBLISH', 'WITHDRAW'])
def test_original_catalog_publisher_waits_after_final_sample_until_preview_commit(preparation_fixture, tmp_path, monkeypatch, action):
    original = preparation_fixture
    p, engine = setup(original, tmp_path)
    bridge = enable(original, p)
    protocol = catalogs.IsolatedCatalogPublication(bridge, enabled_for_isolated_tests=True)
    with http(original) as (f, _):
        data, key = body(f, p), uuid4().hex
        before = snapshot(f)
        entered, release = pause_final(monkeypatch)
        pids = Queue()
        original_lock = catalogs.lock
        def observed(c, source_key, exclusive=False):
            if exclusive:
                pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
            return original_lock(c, source_key, exclusive)
        monkeypatch.setattr(catalogs, 'lock', observed)
        with ThreadPoolExecutor(max_workers=2) as pool:
            preview = pool.submit(execute, f, p, data, key)
            try:
                assert entered.wait(5)
                writer = pool.submit(publish, protocol, p, action=action)
                wait_lock(f, pids.get(timeout=5))
                assert not writer.done() and snapshot(f) == before
                with sqlite3.connect(engine.path) as db:
                    assert db.execute('SELECT count(*) FROM previews').fetchone()[0] == 0
            finally:
                release.set()
            result, event = preview.result(timeout=15), writer.result(timeout=15)
        assert result.status_code == 201, result.text
        assert event['revision'] == 2
        assert_snapshot_semantics(result.json())
        current = read(f, p, key).json()
        assert current['result'] == result.json()['result']
        assert current['history'][0]['source_state'] == 'STALE'
        after = snapshot(f)
        assert {k:v for k,v in after.items() if k != 'preparation_catalog'} == {k:v for k,v in before.items() if k != 'preparation_catalog'}


@pytest.mark.parametrize('writer_kind', ['material', 'revocation'])
def test_original_material_and_revocation_writer_wait_through_preview_commit(preparation_fixture, tmp_path, monkeypatch, writer_kind):
    with http(preparation_fixture) as (f, _):
        p, engine = setup(f, tmp_path)
        data, key = body(f, p), uuid4().hex
        entered, release = pause_final(monkeypatch)
        pids = Queue()
        original_connect = f[1].connect
        def observed_connection():
            c = original_connect()
            pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
            return c
        # Owner connection observes the real revoke worker; the material writer
        # uses the original API and is observed via the app's principal lock.
        old_lock = f[0].lock_principal
        def observe_lock(c, principal, exclusive=False):
            if not entered.is_set() or writer_kind != 'material':
                return old_lock(c, principal, exclusive)
            pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
            return old_lock(c, principal, exclusive)
        monkeypatch.setattr(f[0], 'lock_principal', observe_lock)
        def write():
            if writer_kind == 'material':
                return add(f, p, 'need_summary', 'SYNTHETIC newer source')
            monkeypatch.setattr(f[1], 'connect', observed_connection)
            return f[1].revoke_capability('fixture-a', 'EXECUTE')
        with ThreadPoolExecutor(max_workers=2) as pool:
            preview = pool.submit(execute, f, p, data, key)
            try:
                assert entered.wait(5)
                writer = pool.submit(write)
                wait_lock(f, pids.get(timeout=5))
                assert not writer.done()
                with sqlite3.connect(engine.path) as db:
                    assert db.execute('SELECT count(*) FROM previews').fetchone()[0] == 0
            finally:
                release.set()
            result, changed = preview.result(timeout=15), writer.result(timeout=15)
        assert result.status_code == 201, result.text
        assert_snapshot_semantics(result.json())
        if writer_kind == 'material':
            assert changed.status_code == 200, changed.text
            recovered = read(f, p, key).json()
            assert recovered['result'] == result.json()['result'] and recovered['history'][0]['source_state'] == 'STALE'
            assert execute(f, p, data).status_code == 409
        else:
            assert read(f, p, key).status_code == 403
            with sqlite3.connect(engine.path) as db:
                assert db.execute('SELECT count(*) FROM previews').fetchone()[0] == 1


def test_uncooperative_catalog_change_after_final_sample_is_snapshot_stale_not_current(preparation_fixture, tmp_path, monkeypatch):
    with http(preparation_fixture) as (f, _):
        p, engine = setup(f, tmp_path)
        data, key = body(f, p), uuid4().hex
        before = snapshot(f)
        entered, release = pause_final(monkeypatch)
        with ThreadPoolExecutor(max_workers=1) as pool:
            preview = pool.submit(execute, f, p, data, key)
            try:
                assert entered.wait(5)
                with f[1].connect() as c:
                    # Explicitly noncooperative historical owner writer.
                    c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a' AND service_id=%s AND version=1", (Jsonb({'kind':'SYNTHETIC','id':'after-final-sample','revision':'2'}), ep.prep.SERVICE))
                changed = snapshot(f)
            finally:
                release.set()
            response = preview.result(timeout=15)
        assert response.status_code == 201, response.text
        value = response.json()
        assert_snapshot_semantics(value)
        assert value['history'][0]['source_state'] == 'STALE'
        assert value['current_source_sha256'] != value['result']['binding']['source_sha256']
        assert {k:v for k,v in changed.items() if k != 'preparation_catalog'} == {k:v for k,v in before.items() if k != 'preparation_catalog'}
        assert snapshot(f) == changed
        assert read(f, p, key).json()['result'] == value['result']
        assert execute(f, p, data, key).json()['result'] == value['result']
        assert execute(f, p, data).status_code == 409


def test_sqlite_wait_expired_managed_dependency_rejected_before_insert_and_cold_get_only(access_fixture, tmp_path, monkeypatch):
    a = access_fixture
    approved(a)
    original, p, _, now, _ = a
    p = {**p, 'revision':save(original, p, goals=['LOCAL_MATERIAL_PREPARATION']).json()['revision']}
    engine = ep.IsolatedExecutionPreview(original[0], (tmp_path/'managed-preview').resolve(), enabled_for_synthetic_preview=True)
    engine.attach_store(original[0])
    with http(original) as (f, requests):
        data, key = body(f, p), uuid4().hex
        before = snapshot(f)
        entered, attempted = Event(), Event()
        original_source = engine._source
        def observed(*args):
            value = original_source(*args)
            assert ('executor-a', p['run_id']) in args[1]._managed_checks
            entered.set()
            return value
        monkeypatch.setattr(engine, '_source', observed)
        original_database = engine._database
        @contextmanager
        def observed_database():
            with original_database() as db:
                db.set_trace_callback(lambda statement: attempted.set() if statement == 'BEGIN IMMEDIATE' else None)
                yield db
        monkeypatch.setattr(engine, '_database', observed_database)
        blocker = sqlite3.connect(engine.path)
        blocker.execute('BEGIN IMMEDIATE')
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                request = pool.submit(execute, f, p, data, key)
                assert entered.wait(5) and attempted.wait(5) and not request.done()
                # Advance the original bridge's explicit synthetic lease clock
                # while a different real SQLite connection owns the write lock.
                now[0] += timedelta(minutes=11)
                blocker.rollback()
                response = request.result(timeout=15)
        finally:
            blocker.close()
        assert response.status_code == 403, response.text
        with sqlite3.connect(engine.path) as db:
            assert db.execute('SELECT count(*) FROM previews').fetchone()[0] == 0
        monkeypatch.setattr(engine, '_source', original_source)
        ep.IsolatedExecutionPreview(f[0], engine.root, enabled_for_synthetic_preview=True).attach_store(f[0])
        requests.clear()
        recovered = read(f, p, key)
        assert recovered.status_code == 200 and recovered.json()['status'] == 'NOT_OBSERVED'
        assert {r['method'] for r in requests} == {'GET'} and snapshot(f) == before


def test_principal_lock_wait_revocation_precedes_sampling_and_no_artifact(preparation_fixture, tmp_path, monkeypatch):
    with http(preparation_fixture) as (f, _):
        p, engine = setup(f, tmp_path)
        data, key = body(f, p), uuid4().hex
        entered = Event()
        old = f[0].lock_principal
        def observed(c, principal, exclusive=False):
            entered.set()
            return old(c, principal, exclusive)
        monkeypatch.setattr(f[0], 'lock_principal', observed)
        with f[1].connect() as blocker:
            f[1].lock_principal(blocker, 'fixture-a', exclusive=True)
            with ThreadPoolExecutor(max_workers=1) as pool:
                request = pool.submit(execute, f, p, data, key)
                assert entered.wait(5)
                blocker.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
                blocker.commit()
                response = request.result(timeout=15)
        assert response.status_code == 403
        with sqlite3.connect(engine.path) as db:
            assert db.execute('SELECT count(*) FROM previews').fetchone()[0] == 0


def test_inserted_uncommitted_failure_rolls_back_and_explicit_same_key_recovers(preparation_fixture, tmp_path, monkeypatch):
    with http(preparation_fixture) as (f, _):
        p, engine = setup(f, tmp_path)
        data, key = body(f, p), uuid4().hex
        before, calls = snapshot(f), []
        original = engine._guard
        def fail_after_insert(*args):
            original(*args)
            calls.append(1)
            if len(calls) == 3:
                raise ep.Unavailable('SYNTHETIC after inserted proof, before SQLite commit')
        monkeypatch.setattr(engine, '_guard', fail_after_insert)
        assert execute(f, p, data, key).status_code == 503
        monkeypatch.setattr(engine, '_guard', original)
        assert read(f, p, key).json()['status'] == 'NOT_OBSERVED'
        assert snapshot(f) == before


def test_post_commit_response_comparison_failure_preserves_exact_result_for_get_only_recovery(preparation_fixture, tmp_path, monkeypatch):
    with http(preparation_fixture) as (f, requests):
        p, engine = setup(f, tmp_path)
        data, key = body(f, p), uuid4().hex
        before, calls = snapshot(f), []
        original = ep.planning._proposal
        def unavailable_response(*args):
            calls.append(1)
            if len(calls) == 3:
                raise ep.Unavailable('SYNTHETIC response comparison failed after committed preview')
            return original(*args)
        monkeypatch.setattr(ep.planning, '_proposal', unavailable_response)
        assert execute(f, p, data, key).status_code == 503
        with sqlite3.connect(engine.path) as db:
            row = db.execute('SELECT document FROM previews').fetchone()
        assert row is not None
        monkeypatch.setattr(ep.planning, '_proposal', original)
        ep.IsolatedExecutionPreview(f[0], engine.root, enabled_for_synthetic_preview=True).attach_store(f[0])
        requests.clear()
        recovered = read(f, p, key)
        assert recovered.status_code == 200 and recovered.json()['status'] == 'COMMITTED'
        assert ep.prep.canonical(recovered.json()['result']) == row[0]
        assert_snapshot_semantics(recovered.json())
        assert {r['method'] for r in requests} == {'GET'} and snapshot(f) == before
        result = execute(f, p, data, key)
        assert result.status_code == 201, result.text
        ep.IsolatedExecutionPreview(f[0], engine.root, enabled_for_synthetic_preview=True).attach_store(f[0])
        assert read(f, p, key).json()['result'] == result.json()['result']
        assert_snapshot_semantics(read(f, p).json())
        assert snapshot(f) == before
