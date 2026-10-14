"""Owned-PG preconditions for the new service release selection acceptance."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, create, headers
from service_release_acceptance_support import (
    authority_snapshot, case_history, stable_hash, wait_for_pg_blocker,
    reviewed_source_descriptor,
)
from test_template_candidate import template_candidate, publish_template


def test_second_park_uses_existing_scope_and_fresh_independent_materials(receipt_fixture):
    f = receipt_fixture
    before = authority_snapshot(f[1])
    first, _, _ = create(f, goal='SYNTHETIC first park release acceptance input')
    second, _, _ = create(f, user='fixture-c', goal='SYNTHETIC distinct second park input')
    first_history = case_history(f[1], first['preparation_id'])
    second_history = case_history(f[1], second['preparation_id'])
    assert first_history['preparations'][0]['park_id'] == 'park-a'
    assert second_history['preparations'][0]['park_id'] == 'park-b'
    assert second_history['preparations'][0]['org_id'] == 'org-c'
    assert second_history['preparations'][0]['reviewer_id'] == 'prep-specialist-fixture-c'
    assert first['case_id'] != second['case_id'] and first['run_id'] != second['run_id']
    assert not first_history['preparation_evidence'] and not second_history['preparation_evidence']
    assert f[3].get('/api/preparations/' + first['preparation_id'],
                    headers=headers(f[2], 'fixture-c')).status_code == 403
    assert f[3].get('/api/preparations/' + second['preparation_id'],
                    headers=headers(f[2])).status_code == 403
    assert authority_snapshot(f[1]) == before
    assert stable_hash(case_history(f[1], first['preparation_id'])) == stable_hash(first_history)


def test_publication_lock_probe_observes_actual_pg_blocking(receipt_fixture):
    from parkweave.catalog_publication import lock
    from parkweave.preparation import SERVICE
    f = receipt_fixture
    key = ('park-a', SERVICE, 1)
    started = Event()

    def reader():
        with f[1].connect() as connection:
            started.set()
            lock(connection, key)
            return True

    with ThreadPoolExecutor(max_workers=1) as executor:
        with f[1].connect() as connection:
            lock(connection, key, exclusive=True)
            blocker = connection.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            waiting = executor.submit(reader)
            assert started.wait(1)
            observed = wait_for_pg_blocker(f[1], blocker)
            assert observed and not waiting.done()
        assert waiting.result(timeout=2) is True


def test_source_descriptor_uses_actual_original_independent_review(template_candidate):
    engine, _, _ = template_candidate
    publish_template(engine)
    release = engine.public_catalog('template-isolated-park')['items'][0]
    descriptor = reviewed_source_descriptor(release)
    assert descriptor['template_release_id'] == release['release_id']
    assert descriptor['template_release_sha256'] == release['release_sha256']
    assert descriptor['review_revision'] == 3
    assert descriptor['source_sha256'] == stable_hash(release['snapshot']['definition']['source'])
