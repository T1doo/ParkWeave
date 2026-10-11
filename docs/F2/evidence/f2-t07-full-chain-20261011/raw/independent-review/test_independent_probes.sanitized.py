"""Additional real-HTTP, owned-PG T07 boundary oracles; never mutate product."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests'))
from conftest import fixture, pg
from test_f2_t07_full_chain import chain, link_fixture, receipt_fixture, preparation_fixture
from parkweave import resource_holds


def persistent_business(u):
    rows = u.business()
    rows.update(u.rows(['outbox', 'run_projection', 'dispatch_notice_outbox',
                        'dispatch_notices', 'controlled_plans', 'controlled_plan_events']))
    return rows


def test_owned_cold_api_rechecks_revoked_owner_before_history_key_and_late_ack(chain):
    u = chain
    p, _, _, d, receipt = u.completed('independent-cold-revocation')
    original = next(r for r in u.trace if r['request_body']
                    and r['request_body'].get('slot') == 'material_outline')
    # Same existing explicit synthetic management failure as the production tests.
    # This revocation is not regranted or treated as a business confirmation.
    u.f[1].revoke_capability('fixture-a', 'READ')
    before = persistent_business(u)
    with u.cold_api():
        for path in [u.path(p), u.path(p, '/goal-results'),
                     u.path(p, '/local-case'),
                     '/api/executor-receipts/' + d['receipt_step_id']]:
            denied = u.get(path, status=403)
            assert 'independent-cold-revocation new outline' not in str(denied)
        u.get(u.path(p, '/command-recovery'), key=original['request_key'], status=403)
        u.post('/api/executor-receipts/' + receipt['step']['id'] + '/commands',
               dict(action='ACKNOWLEDGE', expected_revision=receipt['step']['revision'],
                    receipt_sha256=receipt['current_receipt']['source_sha256'],
                    reason='SYNTHETIC revoked owner cannot confirm via cold API'), status=403)
        assert persistent_business(u) == before
    assert persistent_business(u) == before


def test_independent_resource_release_invalidates_current_goal_without_erasing_case_or_ack(chain):
    u = chain
    p, combo, data, _, receipt = u.completed('independent-resource-release')
    original = persistent_business(u)
    u.post('/api/resource-combinations/' + combo['id'] + '/cancel', {})
    after_release = persistent_business(u)
    outputs = u.get(u.path(p, '/goal-results'))
    assert outputs['state'] == 'UNVERIFIED' and not outputs['case_goal_completed']
    by_adapter = {r['adapter_id']: r for r in outputs['results']}
    assert by_adapter['P1']['state'] == 'LOCAL_OUTPUT_VERIFIED'
    assert by_adapter['P2']['state'] == 'NEEDS_RECHECK'
    assert by_adapter['P2']['actual_output'] is None
    assert all(r['state'] != 'LOCAL_OUTPUT_VERIFIED' for r in outputs['results']
               if r['adapter_id'] in ('P3', 'P4', 'P5'))
    assert persistent_business(u) == after_release
    for table in ['cases', 'runs', 'service_dispatches', 'service_dispatch_offers',
                  'service_dispatch_events', 'service_receipt_steps',
                  'service_step_receipts', 'service_receipt_events', 'case_local_events']:
        assert after_release[table] == original[table], table
    saved = u.get('/api/executor-receipts/' + receipt['step']['id'])
    assert saved['step']['state'] == 'LOCAL_ACKNOWLEDGED'
    assert saved['current_receipt']['id'] == receipt['current_receipt']['id']
    assert u.get('/api/runs/' + p['run_id'])['state'] == 'SUCCEEDED'
    preview = u.post('/api/synthetic-resources/' + str(resource_holds.RESOURCE_ID) + '/preview',
                     {k: data[k] for k in ('starts_at', 'ends_at', 'quantity')})
    assert preview['occupied_peak'] == 0 and preview['available']


def test_old_verify_key_remains_historical_read_only_after_receipt_feedback_without_auto_verify(chain):
    u = chain
    p, _, _, _, receipt = u.completed('independent-historical-verify')
    original_verify = next(r for r in u.trace if r['request_body']
                           and r['request_body'].get('action') == 'VERIFY'
                           and r['request_body'].get('reason', '').endswith(' P4'))
    original_event = original_verify['response']['event']
    u.receipt_action(receipt, 'REOPEN')
    before = persistent_business(u)
    recovered = u.get(u.path(p, '/service-case-plan/command-recovery'),
                      key=original_verify['request_key'])
    assert recovered['status'] == 'COMMITTED' and recovered['historical_only']
    assert recovered['read_only'] and not recovered['automatically_replayed']
    assert (recovered['event']['id'], recovered['event']['revision']) == (
        original_event['id'], original_event['revision'])
    assert recovered['event']['current_plan'] and recovered['event']['historical_only']
    step = next(s for s in recovered['current']['steps'] if s['adapter_id'] == 'P4')
    assert step['state'] != 'VERIFIED' and step['allowed_actions'] == []
    assert step['source_sha256'] is None and step['verified_sha256'] is None
    assert step['verified_sources'] is None
    result = u.get(u.path(p, '/goal-results'))
    p4 = next(r for r in result['results'] if r['adapter_id'] == 'P4')
    assert result['state'] == 'UNVERIFIED' and p4['state'] == 'NEEDS_RECHECK'
    assert p4['historical_verification']['id'] == original_event['id']
    assert not p4['historical_verification']['current'] and not result['automatically_verified']
    assert persistent_business(u) == before
