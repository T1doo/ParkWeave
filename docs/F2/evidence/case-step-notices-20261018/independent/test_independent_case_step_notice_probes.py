"""Independent notice oracles; source preparation only until parent freezes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import json
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from parkweave import case_step_assignments as cs, dispatch_notices as dn, service_dispatches as sd
from parkweave.api import create_app
from parkweave.store import Denied
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from test_new_enterprise_local_chain import actual_http
from service_release_acceptance_support import authority_snapshot

REVIEWER = 'prep-specialist-fixture-a'


def ok(r, expected=200):
    assert r.status_code == expected, f'HTTP {r.status_code}: {r.text}'
    return r.json()


@contextmanager
def scoped(f, **limits):
    scope = cs.IsolatedCaseStepAssignments(f[0], f[1], f[1]._case_fact_fixture_receipt,
        owner_id='fixture-a', reviewer_id=REVIEWER, executor_ids=('executor-a',),
        enabled_for_isolated_tests=True, **limits)
    before = authority_snapshot(f[1])
    with actual_http(create_app(f[0], case_step_assignments=scope)) as (api, traffic):
        yield (*f[:3], api), scope, before, traffic


def post(f, path, body, actor='fixture-a', status=200):
    return ok(f[3].post(path, headers=headers(f[2], actor, uuid4().hex), json=body), status)


def prepare(f, tag):
    run = post(f, '/api/runs', {'goal': 'PRIVATE_NOTICE_GOAL_' + tag}, status=202)
    f[0].finish(f[0].claim('independent-case-step-notice-' + tag))
    p = post(f, '/api/preparations', dict(run_id=run['run_id'],
        service_id='synthetic-material-preparation', service_version=1, reviewer_id=REVIEWER), status=201)
    for slot in ('need_summary', 'material_outline'):
        p = post(f, '/api/preparations/' + p['preparation_id'] + '/commands', dict(
            action='ADD_EVIDENCE', expected_revision=p['revision'], slot=slot,
            text='PRIVATE_NOTICE_MATERIAL_' + tag + '_' + slot,
            source_kind='DOCUMENT_EXCERPT', source_label='SYNTHETIC independent original'))
    for actor, action in ((REVIEWER, 'REVIEW'), ('fixture-a', 'CONFIRM')):
        p = post(f, '/api/preparations/' + p['preparation_id'] + '/commands', dict(
            action=action, expected_revision=p['revision'], reason='SYNTHETIC explicit ' + action), actor)
    return p


def offer(f, p):
    return post(f, '/api/preparations/' + p['preparation_id'] + '/dispatch', dict(
        expected_preparation_revision=p['revision'], expected_dispatch_revision=0,
        executor_id='executor-a', reason='PRIVATE_NOTICE_DISPATCH_REASON'), REVIEWER, 201)


def decide(f, d, action):
    return post(f, '/api/service-dispatches/' + d['dispatch_id'] + '/commands', dict(
        action=action, expected_revision=d['revision'], reason='SYNTHETIC explicit ' + action),
        REVIEWER if action == 'WITHDRAW' else 'executor-a')


def drain(f, scope=None, bound=128):
    for _ in range(bound):
        if not dn.consume(f[0], case_step_assignments=scope):
            return
    raise AssertionError('bounded independent drain did not settle')


def inbox(f, actor='executor-a'):
    return ok(f[3].get('/api/dispatch-notices', headers=headers(f[2], actor)))


def command(f, n, action, actor='executor-a', expected=200):
    return post(f, '/api/dispatch-notices/' + n['event_id'] + '/commands',
                dict(action=action, expected_revision=n['revision']), actor, expected)


def notice_snapshot(owner):
    with owner.connect() as c:
        return {name:c.execute('SELECT to_jsonb(x) value FROM '+name+' x ORDER BY to_jsonb(x)::text').fetchall()
                for name in ('dispatch_notice_outbox', 'dispatch_notices')}


def test_literal_default_skips_entire_lineage_and_timestamps_stay_distinct(receipt_fixture):
    with scoped(receipt_fixture) as (f, scope, authority, _):
        p = prepare(f, 'lineage'); d = offer(f, p)
        before = notice_snapshot(f[1]); drain(f)
        assert notice_snapshot(f[1]) == before
        drain(f, scope)
        n = inbox(f)['items'][0]
        assert n['action'] == 'OFFER' and n['actionable'] is True
        assert n['open_requested_at'] is None and n['read_at'] is None
        assert 'PRIVATE_NOTICE_' not in json.dumps(inbox(f))
        before = notice_snapshot(f[1]); command(f, n, 'MARK_READ', expected=409)
        assert notice_snapshot(f[1]) == before
        opened = command(f, n, 'OPEN')['notice']
        assert opened['open_requested_at'] and opened['read_at'] is None
        d = decide(f, d, 'ACCEPT')
        before = notice_snapshot(f[1]); drain(f)
        assert notice_snapshot(f[1]) == before, 'markerless ACCEPT intent was stolen by default consumer'
        drain(f, scope)
        marked = command(f, n, 'MARK_READ')['notice']
        assert marked['open_requested_at'] == opened['open_requested_at']
        assert marked['delivered_at'] == opened['delivered_at']
        assert marked['read_at'] and marked['historical'] is True and marked['actionable'] is False
        assert command(f, n, 'MARK_READ')['notice'] == marked == command(f, n, 'OPEN')['notice']
        assert sorted(x['action'] for x in inbox(f, 'fixture-a')['items']) == ['ACCEPT', 'OFFER']
        assert [x['action'] for x in inbox(f, REVIEWER)['items']] == ['ACCEPT']
        d = decide(f, d, 'WITHDRAW')
        before = notice_snapshot(f[1]); drain(f)
        assert notice_snapshot(f[1]) == before, 'markerless WITHDRAW intent was stolen by default consumer'
        drain(f, scope)
        ok(f[3].get('/api/dispatch-notices/' + n['event_id'], headers=headers(f[2], 'executor-a')), 403)
        with f[1].connect() as c:
            terminal = c.execute("SELECT recipient_id,state FROM dispatch_notice_outbox o JOIN service_dispatch_events e ON e.id=o.event_id WHERE e.action='WITHDRAW' ORDER BY recipient_id").fetchall()
            assert terminal == [{'recipient_id':'executor-a','state':'SUPPRESSED'}, {'recipient_id':'fixture-a','state':'DELIVERED'}]
        with TestClient(create_app(f[0])) as ordinary:
            ok(ordinary.get('/api/dispatch-notices/' + n['event_id'], headers=headers(f[2])), 403)
            assert ok(ordinary.get('/api/dispatch-notices', headers=headers(f[2])))['items'] == []
        assert authority_snapshot(f[1]) == authority


def test_literal_skiplocked_case_callbacks_do_not_poison_later_case(receipt_fixture, monkeypatch):
    with scoped(receipt_fixture) as (f, scope, authority, _):
        ids = iter((UUID(int=101), UUID(int=102)))
        monkeypatch.setattr(sd, 'uuid4', lambda: next(ids))
        first = offer(f, prepare(f, 'skip-first'))
        second = offer(f, prepare(f, 'skip-second'))
        first_end = datetime.fromisoformat(first['assignment_valid_until'])
        second_end = datetime.fromisoformat(second['assignment_valid_until'])
        assert first_end < second_end
        middle = first_end + (second_end - first_end) / 2
        actual_now = cs._now
        authority_check = dn._authority
        crossed = False

        def current_time(c):
            return middle if crossed else actual_now(c)

        def check(store, c, p, source, *args, **kwargs):
            nonlocal crossed
            result = authority_check(store, c, p, source, *args, **kwargs)
            if source['event_id'] == UUID(int=102):
                crossed = True
            return result

        monkeypatch.setattr(cs, '_now', current_time)
        monkeypatch.setattr(dn, '_authority', check)
        with f[1].connect() as blocker:
            blocker.execute('SELECT * FROM dispatch_notice_outbox WHERE event_id=%s FOR UPDATE', (UUID(int=101),))
            assert dn.consume(f[0], case_step_assignments=scope) is True
        assert crossed
        with f[1].connect() as c:
            assert {x['state'] for x in c.execute('SELECT state FROM dispatch_notice_outbox WHERE event_id=%s', (UUID(int=101),))} == {'PENDING'}
            assert c.execute('SELECT count(*) n FROM dispatch_notices WHERE event_id=%s', (UUID(int=102),)).fetchone()['n'] == 1
        assert authority_snapshot(f[1]) == authority


def test_literal_false_offer_revision_two_is_not_proved_by_first_marker(receipt_fixture):
    with scoped(receipt_fixture) as (f, scope, authority, _):
        d = offer(f, prepare(f, 'false-offer')); drain(f, scope)
        decide(f, d, 'ACCEPT')
        with f[1].connect() as c:
            accepted = c.execute("SELECT * FROM service_dispatch_events WHERE action='ACCEPT'").fetchone()
            c.execute("UPDATE service_dispatch_events SET action='OFFER' WHERE id=%s", (accepted['id'],))
        try:
            before = notice_snapshot(f[1]); drain(f); drain(f, scope)
            assert notice_snapshot(f[1]) == before
            with f[1].connect() as c:
                assert {x['state'] for x in c.execute('SELECT state FROM dispatch_notice_outbox WHERE event_id=%s', (accepted['id'],))} == {'PENDING'}
                assert not c.execute('SELECT 1 FROM dispatch_notices WHERE event_id=%s', (accepted['id'],)).fetchone()
        finally:
            with f[1].connect() as c:
                c.execute("UPDATE service_dispatch_events SET action='ACCEPT' WHERE id=%s", (accepted['id'],))
        drain(f, scope)
        assert [x['action'] for x in inbox(f, REVIEWER)['items']] == ['ACCEPT']
        assert authority_snapshot(f[1]) == authority


def test_literal_foreign_prefix_cannot_starve_own_lane_at_scan_limit_one(receipt_fixture, monkeypatch):
    from psycopg.types.json import Jsonb
    with scoped(receipt_fixture) as (f, scope, authority, _):
        ids = iter((UUID(int=201), UUID(int=202)))
        monkeypatch.setattr(sd, 'uuid4', lambda: next(ids))
        offer(f, prepare(f, 'foreign-prefix'))
        offer(f, prepare(f, 'own-after-prefix'))
        with f[1].connect() as c:
            row = c.execute('SELECT payload FROM service_dispatch_events WHERE id=%s', (UUID(int=201),)).fetchone()
            original = deepcopy(row['payload']); foreign = deepcopy(original)
            foreign[cs.MARKER]['binding']['contract_id'] = str(uuid4())
            c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(foreign), UUID(int=201)))
        monkeypatch.setattr(dn, 'SCAN_LIMIT', 1)
        try:
            before = notice_snapshot(f[1])
            assert dn.consume(f[0]) is False
            assert notice_snapshot(f[1]) == before
            assert dn.consume(f[0], case_step_assignments=scope) is True
            with f[1].connect() as c:
                assert {x['state'] for x in c.execute('SELECT state FROM dispatch_notice_outbox WHERE event_id=%s', (UUID(int=201),))} == {'PENDING'}
                assert c.execute('SELECT count(*) n FROM dispatch_notices WHERE event_id=%s', (UUID(int=202),)).fetchone()['n'] == 1
            assert dn.consume(f[0], case_step_assignments=scope) is True
            assert dn.consume(f[0], case_step_assignments=scope) is False
        finally:
            with f[1].connect() as c:
                c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(original), UUID(int=201)))
        assert authority_snapshot(f[1]) == authority


def test_literal_actual_notice_wait_crosses_deadline_without_marking_read(receipt_fixture):
    with scoped(receipt_fixture, offer_seconds=2) as (f, scope, authority, _):
        offer(f, prepare(f, 'notice-wait')); drain(f, scope)
        n = inbox(f)['items'][0]; command(f, n, 'OPEN')
        with f[1].connect() as blocker:
            blocker.execute("SELECT * FROM dispatch_notices WHERE recipient_id='executor-a' FOR UPDATE")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(f[3].post, '/api/dispatch-notices/' + n['event_id'] + '/commands',
                    headers=headers(f[2], 'executor-a'), json=dict(action='MARK_READ', expected_revision=1))
                observed = False
                for _ in range(40):
                    with f[1].connect() as c:
                        observed = bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM dispatch_notices%' LIMIT 1").fetchone())
                    if observed:break
                    time.sleep(.02)
                assert observed
                time.sleep(2.05); blocker.commit()
                ok(future.result(timeout=10), 403)
        with f[1].connect() as c:
            assert c.execute("SELECT read_at FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()['read_at'] is None
        owner = next(x for x in inbox(f, 'fixture-a')['items'] if x['event_id'] == n['event_id'])
        assert owner['historical'] is True and owner['actionable'] is False
        command(f, owner, 'OPEN', 'fixture-a'); command(f, owner, 'MARK_READ', 'fixture-a')
        assert authority_snapshot(f[1]) == authority


def test_literal_real_paging_cursor_cannot_cross_default_mode(receipt_fixture):
    with scoped(receipt_fixture) as (f, scope, authority, _):
        for number in range(11):
            d = offer(f, prepare(f, 'page-' + str(number)))
            decide(f, d, 'ACCEPT')
        drain(f, scope)
        navigation = dn.Navigation()
        first = dn.list_items(f[0], f[2]['fixture-a'], navigation=navigation, case_step_assignments=scope)
        assert len(first['items']) == 20 and first['check_limit'] == 100 and first['page_limit'] == 20
        cursor = first['next_cursor']; assert isinstance(cursor, str) and len(cursor) == 43
        before = notice_snapshot(f[1])
        with pytest.raises(Denied):
            dn.list_items(f[0], f[2]['fixture-a'], cursor=cursor, navigation=navigation)
        second = dn.list_items(f[0], f[2]['fixture-a'], cursor=cursor,
                               navigation=navigation, case_step_assignments=scope)
        assert len(second['items']) == 2 and second['next_cursor'] is None
        first_ids = {str(x['event_id']) for x in first['items']}
        second_ids = {str(x['event_id']) for x in second['items']}
        assert not first_ids & second_ids and len(first_ids | second_ids) == 22
        assert notice_snapshot(f[1]) == before
        assert authority_snapshot(f[1]) == authority
