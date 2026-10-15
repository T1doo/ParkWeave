"""Recount frozen literal observations and HTML traces without product closures."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import re
import traceback

from audit_archive import ROOT, HERE, read_json, relpath, identity, public_json
from audit_execution_scope import junit_nodes

PHASE = re.compile(r' \((?:setup|call|teardown)\)$')
ALIASES = {
    'MF04_SUMMARY_ONLY': 'MF04', 'MF06_BOTH_SLOTS': 'MF06',
    'MF17_RECEIPT_ONLY': 'MF17', 'MF17_UNION_RECEIPT_CONTROL': 'MF17',
    'MF16_RESOURCE_RECEIPT_UNION': 'MF16', 'HTML_summary_keep': 'MF04',
    'COMMITTED_V3_IS_NOT_ADOPT_summary_keep': 'MF04', 'HTML_dual_merge_lost_ack': 'MF06',
    'COMMITTED_V3_IS_NOT_ADOPT_dual_merge_lost_ack': 'MF06',
    'MF25_UNKNOWN_RESOURCE_WITH_RECEIPT': 'MF25',
}


def rows(base):
    values = {}
    for path in sorted(base.glob('*.jsonl')):
        if path.name.endswith('.stdout.jsonl') or '.private.' in path.name:
            continue
        kind = path.name.rsplit('-', 1)[0]
        for line, text in enumerate(path.read_text().splitlines(), 1):
            item = json.loads(text)
            if not item.get('run_id'):
                continue
            item = dict(item, source_file=str(path.relative_to(ROOT)), source_line=line)
            values.setdefault(kind, []).append(item)
    return values


def html(rows_by_kind, expected_scope, expected_modes):
    result = {}
    for row in rows_by_kind.get('html-results', []):
        path = relpath(row['source_file']).parent / row['trace']
        assert path.resolve().is_relative_to(relpath(row['source_file']).parent.resolve())
        outputs = [json.loads(line) for line in path.read_text().splitlines()]
        outputs = [item for item in outputs if item.get('scope') == expected_scope]
        assert len(outputs) == 1
        item = outputs[0]; mode = item['mode']; calls = item['calls']
        assert mode in expected_modes and mode not in result
        assert item['real_browser'] == 'NOT_RUN' and item.get('fake_dto', False) is False
        assert item.get('negative_transport_fixture', False) is False
        assert calls and all(c['method'] in {'GET', 'POST'} and type(c['status']) is int for c in calls)
        adopts = [c for c in calls if c['method'] == 'POST' and c['path'].endswith('/service-case-plan')
                  and (c.get('body') or {}).get('local_revision') is True
                  and (c.get('body') or {}).get('opportunity_proof')]
        verifies = [c for c in calls if c['method'] == 'POST' and '/service-case-plan/' in c['path']
                    and (c.get('body') or {}).get('action') == 'VERIFY']
        if mode in {'summary_keep', 'dual_merge_lost_ack'}:
            assert len(adopts) == 1 and len(verifies) == 5
        if mode in {'current_403', 'late_403'}:
            assert not adopts and not verifies and all(c['method'] == 'GET' for c in calls)
            assert any(c['status'] == 403 for c in calls)
        recovery = None
        if mode == 'dual_merge_lost_ack':
            posts = [c for c in calls if c['method'] == 'POST' and c['path'].endswith('/plan-material-package/commands')]
            assert len(posts) == 1 and posts[0]['status'] == 200 and posts[0]['request_key']
            exact = [c for c in calls if c['method'] == 'GET' and c['path'].endswith('/plan-material-package/recovery/' + posts[0]['request_key'])]
            assert len(exact) == 1 and exact[0]['status'] == 200
            assert item['controlled_committed_response_loss'] is True
            recovery = 'COMMITTED_POST_THEN_CONTROLLED_CLIENT_DISCARD_AND_EXACT_KEY_PATH_GET_NO_REPOST'
        if mode == 'lost_adopt':
            # Old API carries key in Idempotency-Key header, absent from captured GET fields.
            old_gets = [c for c in calls if c['method'] == 'GET' and c['path'].endswith('/service-case-plan/command-recovery')]
            assert len(adopts) == 1 and adopts[0]['status'] == 201
            assert old_gets and all(c['status'] == 200 for c in old_gets)
            recovery = 'RAW_RECOVERY_GET_PLUS_FROZEN_HANDLER_AND_EXECUTED_DRIVER_ASSERTIONS; GET_HEADER_KEY_NOT_CAPTURED'
        result[mode] = dict(calls=len(calls), methods=dict(Counter(c['method'] for c in calls)),
                            statuses=dict(Counter(str(c['status']) for c in calls)),
                            original_opportunity_bound_ADOPT_POSTs=len(adopts), original_VERIFY_POSTs=len(verifies),
                            trace=str(path.relative_to(ROOT)), trace_sha256=identity(path)['sha256'],
                            real_browser='NOT_RUN', fake_DTO=False, recovery_evidence_boundary=recovery)
    assert set(result) == set(expected_modes)
    return result


def perform(config, attempt):
    base = relpath(config['execution_base'])
    raw = base / 'artifacts/independent-new-v2/test_multifield_source_package_independent'
    actual = rows(raw)
    for items in actual.values():
        assert all(row['source_sha'] == config['source_sha'] for row in items)
    oracle_path = ROOT / 'docs/F2/MultifieldSourceConflictOracle-20261015.json'
    oracle_raw = oracle_path.read_bytes()
    assert oracle_raw == (ROOT / '.runtime/multifield-source-review/literal-oracle-v2.json').read_bytes()
    assert hashlib.sha256(oracle_raw).hexdigest() == 'a7c23d489091f62ac49e8c2a2df872231c1aa926ba1356fba05be5e3646df0ea'
    literal = {row['id']: row for row in json.loads(oracle_raw)['scenarios']}
    assert set(literal) == {'MF' + str(i).zfill(2) for i in range(1, 41)}
    baselines = {PHASE.sub('', r['test']): r for r in actual['baseline'] if 'cases' in r}
    assert len(baselines) == 24
    observations, precision = [], {}
    for row in actual['oracle']:
        design = literal[ALIASES[row['scenario']]]
        case = row['case']; initial = baselines[PHASE.sub('', row['test'])]['cases'][case]
        ids = initial['step_ids']; assert set(ids) == {'P1', 'P2', 'P3', 'P4', 'P5'}
        expected_a = {ids[p] for p in design['affected'][case]}
        expected_p = {ids[p] for p in design['preserved'][case]}
        assert expected_a.isdisjoint(expected_p) and expected_a | expected_p == set(ids.values())
        assert set(row['expected_affected']) == set(row['actual_affected']) == expected_a
        assert set(row['expected_preserved']) == set(row['actual_preserved']) == expected_p
        assert all(row[k] == 0 for k in ['missed_count', 'wrong_count', 'wrong_preserved_count'])
        unknown = design['id'] == 'MF25'
        assert row['intentional_unknown'] is unknown
        observations.append(dict(scenario=row['scenario'], literal_design=design['id'], case=case,
                                 unknown=unknown, affected=len(expected_a), preserved=len(expected_p),
                                 literal_source_sha256=hashlib.sha256(oracle_raw).hexdigest(),
                                 artifact=row['source_file'], line=row['source_line']))
    for label, unknown in [('known', False), ('UNKNOWN_conservative', True)]:
        selected = [r for r in observations if r['unknown'] is unknown]
        precision[label] = dict(rows=len(selected), affected=sum(r['affected'] for r in selected),
                                preserved=sum(r['preserved'] for r in selected), missed=0, wrong=0, wrong_preserved=0)
    assert precision['known'] == dict(rows=18, affected=42, preserved=48, missed=0, wrong=0, wrong_preserved=0)
    assert precision['UNKNOWN_conservative'] == dict(rows=2, affected=10, preserved=0, missed=0, wrong=0, wrong_preserved=0)
    union = actual['union-results']; assert len(union) == 1
    assert all(union[0][k] is True for k in ['old_reservations_and_reports_preserved', 'p1_locks_exact', 'receipt_source_changed_only_A'])
    assert union[0]['literal_affected_A'] == union[0]['literal_affected_B'] == ['P2', 'P3', 'P4', 'P5']
    closures = actual['closures']; assert len(closures) == 7
    assert all(r['six_goals_current'] and r['stable_ids_contract_history'] and r['worklist_complete']
               and r['worklist_is_recorded_state_not_fact_verification'] for r in closures)
    assert sum(r['unaffected_B_exact'] is True for r in closures) == 6
    assert all(item['evidence_verified'] is False and item['case_goal_completed'] is False
               for row in closures for item in row['worklist_items'])
    new_html = html(actual, 'FULL_ORIGINAL_HTML_MULTIFIELD_PACKAGE_ACTUAL_HTTP_ASGI_OWNED_PG',
                    {'summary_keep', 'dual_merge_lost_ack', 'current_403', 'late_403'})
    carry = rows(base / 'artifacts/independent-new-v2/test_note_template_carry_independent')
    carry_html = html(carry, 'FULL_ORIGINAL_HTML_NOTE_TEMPLATE_CARRY_ACTUAL_HTTP_ASGI_OWNED_PG',
                      {'title_locked', 'source_changed'})
    manual = rows(base / 'artifacts/independent-prior-v2/test_manual_content_continuation_independent')
    manual_html = html(manual, 'FULL_ORIGINAL_HTML_MANUAL_CONTINUATION_REAL_HTTP_ASGI_OWNED_PG',
                       {'keep_edit', 'accept', 'merge', 'defer_unknown', 'lost_choice', 'lost_adopt', 'current_403', 'late_403'})
    mapping_dir = base / 'independent-new-v2-analysis'
    mapping_input = read_json(mapping_dir / 'mapping-input.json')
    reported_mapping = read_json(mapping_dir / 'design40-actual-mapping.json')
    executed = dict(junit_nodes(base / 'independent-new-v2.xml')[0])
    coverage = []
    for rule in mapping_input['mapping']:
        chosen = {n: status for n, status in executed.items() if n.startswith('tests/test_multifield_source_package_independent.py::')
                  and any(n.split('::', 1)[1] == suffix or n.split('::', 1)[1].startswith(suffix + '[') for suffix in rule['nodes'])}
        scope = rule['planned_scope']
        if chosen and set(chosen.values()) != {'PASS'}:
            scope = 'FAIL'
        elif rule['nodes'] and not chosen:
            scope = 'NOT_RUN'
        coverage.append(dict(id=rule['id'], scope=scope, named_nodes=chosen,
                             asserted=rule.get('asserted'), reason=rule.get('reason'), not_claimed=rule.get('not_claimed')))
    assert {r['id'] for r in coverage} == set(literal)
    counts = dict(Counter(r['scope'] for r in coverage))
    assert counts == config['expected_independent_new24_design40_scope']
    assert reported_mapping['scope_status_counts'] == counts
    for independent, reported in zip(coverage, reported_mapping['rows']):
        assert independent['id'] == reported['id'] and independent['scope'] == reported['status']
        assert independent['named_nodes'] == reported['actual_named_tests']
    public_json(attempt / 'independent-claims-audit.json', dict(status='PASS_BOUNDED_CLAIMS_OTHER_GATES_STILL_REQUIRED',
        source_sha=config['source_sha'], precision_from_original_literal_not_product_closure=precision,
        observations=observations, source_union_control_unmasked=True, closure_observations=7,
        unaffected_B_whole_plan_exact_observations=6, local_goal_state_not_real_completion=True,
        new_HTML=new_html, prior_carry_HTML=carry_html, prior_manual_HTML=manual_html,
        HTML_modes_this_audit_subset=14, entire97_HTML_total_claimed=False,
        design40_scopes=counts, design_mapping=coverage, forty_designs_not_pytest_count=True,
        controlled_response_discard_not_real_network_loss=True,
        prior_cold_GET_headers_not_captured=True, product_model_calls=0,
        NOT_RUN=['real browser', 'Windows', 'formal AT', 'real models', 'formal governance/fulfillment', 'production']))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--attempt', required=True); parser.add_argument('--archive-ready', action='store_true')
    args = parser.parse_args(); config = read_json(HERE / 'audit-config.json')
    assert args.archive_ready and config['archive_ready'] is True, 'NOT_RUN: explicit archive-ready required'
    assert re.fullmatch(r'[a-z0-9_-]+', args.attempt)
    attempt = HERE / args.attempt
    assert attempt.is_dir() and not (attempt / 'independent-claims-audit.json').exists()
    try:
        perform(config, attempt)
    except BaseException as exc:
        public_json(attempt / 'claims-audit-failure.json', dict(status='FAIL_OR_STOP_NO_FINAL_PASS',
                    error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc()))
        raise


if __name__ == '__main__':
    main()
