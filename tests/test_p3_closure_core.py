"""Actual owned PG/ASGI closed-history replacement through all original commands."""
from copy import deepcopy
from uuid import uuid4
import pytest

from p3_closure_fixture_support import (closure_case, capability_resource_catalog, capability_catalog,
    preparation_fixture, receipt_fixture, PROFILE)
from p3_closure_test_support import quote, marker, tail, record, submit, recover, approved
from test_case_resource_delivery import effects
from test_resource_bundles import states
from test_service_plan_manual_lock import stored
from test_service_plan_approval import ledger


@pytest.mark.parametrize('closure_case', [{'action': 'WITHDRAW'}, {'action': 'DECLINE', 'cycles': 2}], indirect=True)
def test_explicit_closed_history_approval_original_five_verify_and_read_only_cold_get(closure_case):
    t = closure_case
    f, p = t['f'], t['p']
    initial = marker(t)
    assert initial['epoch'] > 0 and initial['ever_started'] is True
    assert [s['coordination_state'] for s in t['old']['steps']] == ['VERIFIED', 'VERIFIED', 'PENDING', 'PENDING', 'PENDING']
    plan = deepcopy(stored(f, p))
    oldledger = deepcopy(ledger(f, p))
    hs, data = quote(t)
    # The ordinary delivery request does not grant consent or contain a server proof.
    assert data['replacement_frontier_profile'] == PROFILE
    before = effects(f)
    assert submit(f, p, data).status_code == 409 and effects(f) == before
    item, _ = approved(f, p, data)
    report = item['context']['plan_replacement']['compatibility']
    assert report['schema'] == 3 and report['qualification']['profile'] == PROFILE
    assert report['qualification']['epoch'] == initial['epoch'] and report['qualification']['ever_started'] is True
    key = uuid4().hex
    body = {**data, 'approval_id': item['id']}
    r = submit(f, p, body, key)
    assert r.status_code == 201, r.text
    result = deepcopy(r.json())
    assert effects(f) == [2, 6, 2, 2, 2] and states(f, hs) == ['CONFIRMED'] * 3
    assert marker(t) == initial and stored(f, p) == plan
    assert ledger(f, p)['events'][:3] == oldledger['events']
    accepted = tail(t)
    finalmark = marker(t)
    assert finalmark['epoch'] > initial['epoch'] and finalmark['events'][:initial['epoch']] == initial['events']
    current = deepcopy(stored(f, p))
    with f[1].connect() as c:
        links = c.execute('SELECT id,revision,snapshot FROM case_resource_links WHERE preparation_id=%s ORDER BY revision', (p['preparation_id'],)).fetchall()
    assert len(links) == 2 and str(links[0]['id']) == t['oldreceipt']['link']['id']
    assert links[0]['snapshot'] == t['oldreceipt']['link']['snapshot']
    old_history = {k: v for k, v in t['old'].items() if k != 'history'}
    assert current['history'][0] == old_history
    for _ in range(2):
        r = recover(f, p, key)
        assert r.status_code == 200, r.text
        assert r.json()['receipt'] == result['receipt'] and r.json()['independent_check']['status'] == 'CURRENT'
        assert marker(t) == finalmark and stored(f, p) == current
    assert submit(f, p, body, key).json()['receipt'] == result['receipt']
    assert submit(f, p, {**body, 'reason': body['reason'] + ' changed'}, key).status_code == 409
    assert effects(f) == [2, 6, 2, 2, 2]
    record('positive-closed-history-original-tail-cold-get', dict(action=t['closure_action'], before=initial, after=finalmark,
           qualification=report['qualification'], new_receipt=result['receipt'], accepted_dispatch=accepted))
