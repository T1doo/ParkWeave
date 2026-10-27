"""Owned PostgreSQL + actual ASGI, ordinary synthetic resource time suggestions."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
import time
from psycopg.errors import CheckViolation
from uuid import UUID, uuid4

import pytest

from parkweave import resource_holds as rh
from parkweave.store import Conflict
from test_preparation import headers
from test_resource_holds import resource_fixture, body, hold, preview, configure, counts


def search_body(data, **changes):
    start = rh.Preview(**{k: data[k] for k in ('starts_at', 'ends_at', 'quantity')}).starts_at
    return {**{k: data[k] for k in ('starts_at', 'ends_at', 'quantity')},
            'search_from': start.isoformat(), 'search_until': (start + timedelta(hours=4)).isoformat(),
            **changes}


def search(f, data, user='fixture-a', resource_id=rh.RESOURCE_ID):
    return f[3].post(f'/api/synthetic-resources/{resource_id}/alternative-times',
                     headers=headers(f[2], user), json=data)


def test_conflict_search_then_original_preview_hold_confirm(resource_fixture):
    f = resource_fixture
    configure(f, capacity=1, buffer_seconds=300)
    data = body(f)
    blocking = hold(f, dict(data, purpose='PRIVATE_OTHER_PURPOSE'), user='fixture-b').json()['hold']
    assert not preview(f, data).json()['available']
    before = counts(f)
    response = search(f, search_body(data))
    assert response.status_code == 200, response.text
    result = response.json()
    assert counts(f) == before
    first = result['items'][0]
    assert rh.Preview(**first).starts_at == rh.Hold(**data).ends_at + timedelta(minutes=15)
    assert 'PRIVATE_OTHER_PURPOSE' not in response.text and blocking['id'] not in response.text
    assert 'fixture-b' not in response.text and 'org-b' not in response.text
    assert result['preview_only'] and result['reservation'] == 'NOT_CONFIRMED'
    selected = dict(data, **first)
    current = preview(f, selected)
    assert current.status_code == 200 and current.json()['available']
    created = hold(f, selected)
    assert created.status_code == 201, created.text
    h = created.json()['hold']
    confirmed = f[3].post(f"/api/resource-holds/{h['id']}/confirm",
                         headers=headers(f[2], 'fixture-a', uuid4().hex),
                         json={'expected_revision': h['resource_revision']})
    assert confirmed.status_code == 200 and confirmed.json()['hold']['state'] == 'CONFIRMED'


@pytest.mark.parametrize('buffer, expected_minutes', [(0, 60), (300, 75), (450, 75), (451, 90)])
def test_half_open_and_both_resource_and_hold_buffers(resource_fixture, buffer, expected_minutes):
    f = resource_fixture
    configure(f, capacity=1, buffer_seconds=buffer)
    data = body(f)
    assert hold(f, data, user='fixture-b').status_code == 201
    result = search(f, search_body(data)).json()
    assert rh.Preview(**result['items'][0]).starts_at == rh.Hold(**data).starts_at + timedelta(minutes=expected_minutes)
    # Existing occupied hold keeps its own historical buffer after a rule revision.
    configure(f, buffer_seconds=0)
    result = search(f, search_body(data)).json()
    expected = 60 + ((buffer + 899) // 900) * 15
    assert rh.Preview(**result['items'][0]).starts_at == rh.Hold(**data).starts_at + timedelta(minutes=expected)


def test_quantity_uses_peak_not_sum_of_adjacent_holds(resource_fixture):
    f = resource_fixture
    configure(f, capacity=3, buffer_seconds=0)
    data = body(f, quantity=2)
    parsed = rh.Hold(**data)
    half = (parsed.starts_at + timedelta(minutes=30)).isoformat()
    assert hold(f, dict(data, quantity=1, ends_at=half), user='fixture-b').status_code == 201
    assert hold(f, dict(data, quantity=1, starts_at=half), user='fixture-b').status_code == 201
    result = search(f, search_body(data)).json()
    assert result['items'][0]['starts_at'] == data['starts_at']
    assert all(i['quantity'] == 2 for i in result['items'])
    assert not search(f, search_body(dict(data, quantity=4))).json()['items']


def test_opening_buffer_and_past_candidates_are_skipped(resource_fixture):
    f = resource_fixture
    configure(f, buffer_seconds=300)
    data = body(f); parsed = rh.Hold(**data)
    with f[1].connect() as c:
        c.execute('UPDATE synthetic_resources SET open_from=%s,open_until=%s WHERE id=%s',
                  (parsed.starts_at, parsed.ends_at + timedelta(minutes=35), rh.RESOURCE_ID))
    result = search(f, search_body(data)).json()
    assert [rh.Preview(**i).starts_at for i in result['items']] == [parsed.starts_at + timedelta(minutes=15), parsed.starts_at + timedelta(minutes=30)]
    past = search_body(data, search_from=(parsed.starts_at - timedelta(hours=2)).isoformat())
    assert all(rh.Preview(**i).starts_at >= rh.Preview(**result['items'][0]).starts_at for i in search(f, past).json()['items'])


def test_expired_held_does_not_write_cleanup_and_confirmed_still_counts(resource_fixture):
    f = resource_fixture
    configure(f, capacity=1, buffer_seconds=0)
    data = body(f); h = hold(f, data, user='fixture-b').json()['hold']
    with f[1].connect() as c:
        c.execute("UPDATE synthetic_resource_holds SET created_at=clock_timestamp()-interval '1 day',expires_at=clock_timestamp()-interval '1 hour' WHERE id=%s", (UUID(h['id']),))
    before = counts(f)
    assert search(f, search_body(data)).json()['items'][0]['starts_at'] == data['starts_at']
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM synthetic_resource_holds WHERE id=%s', (UUID(h['id']),)).fetchone()['state'] == 'HELD'
        c.execute("UPDATE synthetic_resource_holds SET state='CONFIRMED' WHERE id=%s", (UUID(h['id']),))
    assert search(f, search_body(data)).json()['items'][0]['starts_at'] == data['ends_at']
    assert counts(f) == before


def test_read_only_even_without_hold_execute_and_sql_has_no_business_mutations(resource_fixture, monkeypatch):
    f = resource_fixture
    with f[1].connect() as c:
        c.execute("DELETE FROM capability_grants WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    original = f[0].connect; queries = []
    class Connection:
        def __init__(self, c): self.c = c
        def execute(self, sql, *args, **kwargs):
            queries.append(sql)
            return self.c.execute(sql, *args, **kwargs)
    @contextmanager
    def tracked():
        with original() as c: yield Connection(c)
    data = search_body(body(f)); before = counts(f)
    monkeypatch.setattr(f[0], 'connect', tracked)
    response = search(f, data)
    assert response.status_code == 200 and response.json()['items']
    assert all(sql.lstrip().split()[0] in ('SELECT', 'SET') for sql in queries)
    assert any('pg_advisory_xact_lock_shared' in sql for sql in queries)
    assert counts(f) == before
    assert hold(f).status_code == 403


@pytest.mark.parametrize('target', ['active', 'role', 'org', 'park', 'READ', 'resource_READ'])
def test_current_authority_and_tenant_rechecked(resource_fixture, target):
    f = resource_fixture; data = search_body(body(f))
    assert search(f, data).status_code == 200
    with f[1].connect() as c:
        if target == 'active': c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif target == 'role': c.execute("UPDATE principals SET role='park_specialist' WHERE id='fixture-a'")
        elif target == 'org': c.execute("UPDATE principals SET org_id='org-other' WHERE id='fixture-a'")
        elif target == 'park': c.execute("UPDATE principals SET park_id='park-other' WHERE id='fixture-a'")
        elif target == 'READ': c.execute("DELETE FROM capability_grants WHERE principal_id='fixture-a' AND capability='READ'")
        else: c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    assert search(f, data).status_code == 403
    assert search(f, data, user='fixture-c').status_code == 403


def test_disabled_resource_rejected(resource_fixture):
    f = resource_fixture
    data = search_body(body(f))
    configure(f, enabled=False)
    assert search(f, data).status_code == 409
    assert counts(f) == (0, 0)


def test_existing_schema_rejects_unsupported_authority_no_new_scope(resource_fixture):
    f = resource_fixture
    with pytest.raises(CheckViolation):
        with f[1].connect() as c:
            c.execute("UPDATE synthetic_resources SET authority='IMPORTED_SNAPSHOT' WHERE id=%s", (rh.RESOURCE_ID,))
    assert search(f, dict(search_body(body(f)), authority='IMPORTED_SNAPSHOT')).status_code == 422
    assert search(f, search_body(body(f)), resource_id=uuid4()).status_code == 403
    assert counts(f) == (0, 0)


def test_explicit_bounds_sorting_normalization_and_grid_empty_scope(resource_fixture):
    f = resource_fixture; data = search_body(body(f))
    start = rh.AlternativeTimes(**data).search_from
    data['search_until'] = (start + timedelta(hours=24)).isoformat()
    result = search(f, data).json()
    assert len(result['items']) == 10 and result['results_truncated'] and result['grid_exhausted']
    assert result['scanned_candidates'] == result['available_candidates'] == 93
    assert result['scan_limit'] == 100 and result['result_limit'] == 10
    assert result['coverage'] == 'SEARCH_WINDOW_GRID_ONLY' and result['ordering'] == 'START_ASC'
    times = [rh.Preview(**i).starts_at for i in result['items']]
    assert times == sorted(times) and all(b - a == timedelta(minutes=15) for a, b in zip(times, times[1:]))
    invalid = [dict(data, search_until=(start + timedelta(hours=24, seconds=1)).isoformat()),
               dict(data, search_until=data['search_from']), dict(data, quantity=True),
               dict(data, quantity=0), dict(data, quantity=21), dict(data, grid_minutes=1),
               dict(data, result_limit=1000), dict(data, search_from='2026-10-11T10:00:00'),
               dict(data, ends_at=(start + timedelta(hours=4, seconds=1)).isoformat()),
               dict(data, search_until=(start + timedelta(minutes=59)).isoformat())]
    for value in invalid: assert search(f, value).status_code == 422
    empty = search(f, dict(data, quantity=20)).json()
    assert empty['items'] == [] and empty['coverage'] == 'SEARCH_WINDOW_GRID_ONLY'
    offset = dict(data, search_from=start.isoformat().replace('+00:00', 'Z'))
    assert search(f, offset).json()['items'] == result['items']


def test_suggestion_is_not_reserved_rival_claim_rejects_original_hold(resource_fixture):
    f = resource_fixture
    configure(f, capacity=1)
    data = body(f); item = search(f, search_body(data)).json()['items'][0]
    selected = dict(data, **item)
    assert preview(f, selected).json()['available']
    assert hold(f, selected, user='fixture-b').status_code == 201
    assert hold(f, selected).status_code == 409
    assert counts(f) == (1, 1)


def test_search_clock_and_rules_rechecked_after_resource_lock(resource_fixture, monkeypatch):
    f = resource_fixture
    configure(f, capacity=1, buffer_seconds=0)
    data = body(f); h = hold(f, data, user='fixture-b').json()['hold']
    entered = threading.Event(); original = rh._lock; backend = []
    def signal(c, id, shared=False):
        if shared:
            backend.append(c.info.backend_pid)
            entered.set()
        return original(c, id, shared)
    monkeypatch.setattr(rh, '_lock', signal)
    def observed_wait():
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with f[1].connect() as observer:
                row = observer.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s', (backend[-1],)).fetchone()
            if row and row['wait_event_type'] == 'Lock': return
            threading.Event().wait(0.01)
        pytest.fail('actual resource advisory Lock wait not observed')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('synthetic-resource:' + str(rh.RESOURCE_ID),))
            c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()+interval '0.15 seconds' WHERE id=%s", (UUID(h['id']),))
            future = pool.submit(rh.alternative_times, f[0], f[2]['fixture-a'], rh.RESOURCE_ID, rh.AlternativeTimes(**search_body(data)))
            assert entered.wait(2)
            observed_wait()
            # Controlled owned database wait, not a browser or external network.
            c.execute('SELECT pg_sleep(0.2)')
        result = future.result(timeout=5)
    assert result['items'][0]['starts_at'] == rh.Hold(**data).starts_at
    entered.clear()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('synthetic-resource:' + str(rh.RESOURCE_ID),))
            c.execute('UPDATE synthetic_resources SET enabled=false,revision=revision+1 WHERE id=%s', (rh.RESOURCE_ID,))
            future = pool.submit(rh.alternative_times, f[0], f[2]['fixture-a'], rh.RESOURCE_ID, rh.AlternativeTimes(**search_body(data)))
            assert entered.wait(2)
            observed_wait()
        with pytest.raises(Conflict, match='disabled'): future.result(timeout=5)


@pytest.mark.parametrize('starts,ends', [
    ('9999-12-31T23:59:58Z', '9999-12-31T23:59:59Z'),
    ('0001-01-01T00:00:00Z', '0001-01-01T00:00:01Z')])
def test_extreme_utc_window_is_bounded_without_datetime_overflow(resource_fixture, starts, ends):
    f = resource_fixture; data = search_body(body(f))
    data.update(starts_at=starts, ends_at=ends, search_from=starts, search_until=ends)
    response = search(f, data)
    assert response.status_code == 200
    assert response.json()['items'] == [] and response.json()['scanned_candidates'] == 1


@pytest.mark.parametrize('field', ['starts_at', 'ends_at', 'search_from', 'search_until'])
@pytest.mark.parametrize('extreme', ['9999-12-31T23:59:59-01:00', '0001-01-01T00:00:00+01:00'])
def test_all_new_route_dates_reject_utc_conversion_overflow(resource_fixture, field, extreme):
    f = resource_fixture; data = search_body(body(f))
    assert search(f, dict(data, **{field: extreme})).status_code == 422
    assert counts(f) == (0, 0)

