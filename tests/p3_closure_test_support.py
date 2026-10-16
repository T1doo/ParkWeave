"""Original business command helpers and inspectable evidence for the new profile."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json
import os

from p3_closure_fixture_support import PROFILE, offer_current, dispatch_read
from test_preparation import headers
from test_service_case_steps import verified
from test_case_resource_delivery import quoted, submit, recover
from test_plan_source_reapproval import approved
from test_resource_bundles import bundle


def record(name, value):
    root = Path(os.environ.get('P3_CLOSURE_ARTIFACT_ROOT', '.runtime/p3-closure-root/dev-artifacts'))
    root.mkdir(parents=True, exist_ok=True)
    p = root / (name + '-' + uuid4().hex + '.json')
    p.write_text(json.dumps(value, indent=2, default=str) + '\n')
    return p


def quote(t):
    hs, body = bundle(t['f'])
    data = quoted(t['f'], t['p'], {**body, 'expected_link_revision': 1,
                  'expected_previous_plan_id': t['old']['id'], 'replacement_frontier_profile': PROFILE})
    return hs, data


def marker(t):
    with t['f'][1].connect() as c:
        return deepcopy(c.execute('SELECT candidate_business_frontier FROM preparations WHERE id=%s', (t['p']['preparation_id'],)).fetchone()['candidate_business_frontier'])


def tail(t):
    from test_service_dispatches import command as dispatch_command
    from test_executor_receipts import act as receipt_action
    from test_case_lifecycle import read as local_read, act as local_action
    f, p = t['f'], t['p']
    verified(f, p, 'P2')
    offered, _ = offer_current(t)
    r = dispatch_command(f, offered, 'ACCEPT', expected_business_frontier=offered['business_frontier'])
    assert r.status_code == 200, r.text
    accepted = r.json()
    verified(f, p, 'P3')
    r = f[3].get('/api/executor-receipts/' + accepted['receipt_step_id'], headers=headers(f[2], 'executor-a'))
    assert r.status_code == 200, r.text
    r = receipt_action(f, r.json(), 'SUBMIT', expected_business_frontier=r.json()['business_frontier'])
    assert r.status_code == 200, r.text
    r = receipt_action(f, r.json(), 'ACKNOWLEDGE', expected_business_frontier=r.json()['business_frontier'])
    assert r.status_code == 200, r.text
    verified(f, p, 'P4')
    r = local_read(f, p)
    assert r.status_code == 200, r.text
    r = local_action(f, p, r.json(), 'REVALIDATE', expected_business_frontier=r.json()['business_frontier'])
    assert r.status_code == 200, r.text
    verified(f, p, 'P5')
    g = f[3].get('/api/preparations/' + p['preparation_id'] + '/goal-results', headers=headers(f[2]))
    assert g.status_code == 200, g.text
    result = g.json()
    assert result['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(result['results']) == 6
    assert all(row['state'] == 'LOCAL_OUTPUT_VERIFIED' for row in result['results'])
    assert result['case_goal_completed'] is False
    w = f[3].get('/api/cases/worklist', params={'limit': 1}, headers=headers(f[2]))
    assert w.status_code == 200, w.text
    worklist = w.json()
    assert worklist['read_only'] and worklist['recorded_states_only']
    row = next(row for row in worklist['items'] if row['case_id'] == p['case_id'])
    assert row['evidence_verified'] is False and row['case_goal_completed'] is False
    record('original-five-verify-six-local-goals', dict(goals=result, worklist=worklist))
    return accepted
