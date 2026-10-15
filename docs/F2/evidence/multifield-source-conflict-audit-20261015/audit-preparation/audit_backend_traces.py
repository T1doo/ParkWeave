"""Independent recount of the 41 earlier source-suite HTML traces, no product calls."""
from collections import Counter
from pathlib import Path
import argparse
import json
import re

from audit_archive import ROOT, HERE, read_json, identity, public_json

GROUPS = {
    'test_typed_source_impact_independent': {'late_read_403', 'late_read_aba', 'lost', 'open_current_403', 'open_late_403', 'positive'},
    'test_shared_source_cases_independent': {'current_403', 'kind_switch', 'late_403', 'late_aba', 'lost', 'overflow', 'pagination', 'pagination_stale', 'positive'},
    'test_service_release_preflight_independent': {'breaking', 'current_403', 'late_403', 'late_aba', 'lock', 'lost', 'lost_withdrawn', 'pending', 'record', 'repeat', 'source', 'tampered', 'target_aba', 'unknown_dto'},
    'test_at24_27_change_batch_independent': {'accept', 'at27', 'capacity', 'capacity_lost_adopt', 'current_403', 'late_403', 'late_aba', 'late_json_reject', 'late_transport_reject', 'lost_note', 'lost_note_bad_unknown', 'lost_note_unknown'},
}
CONTROLLED = {('test_service_release_preflight_independent', m) for m in ['pending', 'unknown_dto']} | {('test_at24_27_change_batch_independent', m) for m in ['late_json_reject', 'late_transport_reject', 'lost_note_bad_unknown']}
LOST = {('test_typed_source_impact_independent', 'lost'), ('test_shared_source_cases_independent', 'lost')} | {('test_service_release_preflight_independent', m) for m in ['lost', 'lost_withdrawn']} | {('test_at24_27_change_batch_independent', m) for m in ['capacity_lost_adopt', 'lost_note', 'lost_note_unknown']}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--attempt', required=True); parser.add_argument('--archive-ready', action='store_true')
    args = parser.parse_args(); config = read_json(HERE / 'audit-config.json')
    assert args.archive_ready and config['archive_ready'] is True
    assert re.fullmatch(r'[a-z0-9_-]+', args.attempt)
    out = HERE / args.attempt; assert out.is_dir()
    assert not (out / 'independent-backend-HTML41.json').exists()
    reported = read_json(ROOT / '.runtime/multifield-source-backend-formal/html-summary.json')
    reported_rows = {r['path']: r for r in reported['traces']}
    records, per_group, categories, fetches = [], {}, Counter(), Counter()
    for group, expected_modes in GROUPS.items():
        observed = set()
        base = ROOT / '.runtime/multifield-source-final/artifacts/backend-v2' / group
        for path in sorted(base.glob('*.stdout.jsonl')):
            items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            finals = [r for r in items if str(r.get('scope', '')).startswith('FULL_ORIGINAL_HTML_')]
            assert len(finals) == 1
            row = finals[0]; mode = row['mode']; key = (group, mode); calls = row['calls']
            assert mode in expected_modes and mode not in observed; observed.add(mode)
            assert row.get('real_browser', 'NOT_RUN') == 'NOT_RUN'
            negative = row.get('negative_transport_fixture') is True
            assert negative == (key in CONTROLLED)
            category = 'CONTROLLED_CLIENT_NEGATIVE' if negative else 'REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS' if key in LOST else 'REAL_BACKEND_RESPONSE_SCENARIO'
            if key in LOST:
                assert any(c.get('method') == 'POST' and c.get('status') in {200, 201} for c in calls)
            relative = str(path.relative_to(ROOT)); counterpart = reported_rows[relative]
            assert identity(path)['sha256'] == counterpart['sha256'] and len(calls) == counterpart['http_call_records']
            assert counterpart['response_evidence'] == category
            assert counterpart['http_methods'] == dict(Counter(c.get('method', 'UNKNOWN') for c in calls))
            assert counterpart['http_statuses'] == dict(Counter(str(c.get('status', 'UNKNOWN')) for c in calls))
            categories[category] += 1; fetches[category] += len(calls)
            records.append(dict(group=group, mode=mode, path=relative, **identity(path),
                                category=category, page_driver_fetch_records=len(calls), real_browser='NOT_RUN'))
        assert observed == expected_modes
        per_group[group] = len(observed)
    assert len(records) == 41 and len(reported_rows) == 41
    assert dict(categories) == {'REAL_BACKEND_RESPONSE_SCENARIO': 29, 'REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS': 7, 'CONTROLLED_CLIENT_NEGATIVE': 5}
    assert sum(fetches.values()) == 957
    public_json(out / 'independent-backend-HTML41.json', dict(status='PASS_SEPARATE_TRACE_CLASSIFICATION',
        source_sha=config['source_sha'], complete_HTML_modes=41, per_group=per_group,
        response_evidence_categories=dict(categories), page_driver_fetch_records_by_category=dict(fetches),
        fetch_record_unit_not_all_actual_untouched_backend_HTTP=True, controlled_client_negative_modes_not_real_backend_refusal_claim=True,
        counts_not_pytest_or_new_package_sample_denominator=True, full_shipped_HTML_Node_VM_not_real_browser=True,
        controlled_loss_not_actual_network_packet_loss=True, records=records))


if __name__ == '__main__':
    main()
