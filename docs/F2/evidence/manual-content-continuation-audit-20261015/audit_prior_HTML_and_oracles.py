"""Recount original seven-module artifacts; do not import its summarizer."""
from collections import Counter, defaultdict
from pathlib import Path
import json

from audit_archive import ROOT, HERE, read_json, public_json, identity

SHA = '14bc83f241149bd03907bd088a35eb6df53ba0a2'
BASE = ROOT / '.runtime/manual-continuation-backend-formal-v2'
ART = BASE / 'artifacts/formal7'
RULES = {
    'test_typed_source_impact_independent': (6, set(), {'lost'}),
    'test_shared_source_cases_independent': (9, set(), {'lost'}),
    'test_service_release_preflight_independent': (14, {'pending','unknown_dto'}, {'lost','lost_withdrawn'}),
    'test_at24_27_change_batch_independent': (12, {'late_json_reject','late_transport_reject','lost_note_bad_unknown'},
                                             {'lost_note','lost_note_unknown','capacity_lost_adopt'}),
}
EXPECTED_ROWS = {
    'test_typed_source_impact_independent': {'known':(8,23), 'declared_UNKNOWN':(2,10), 'additional_UNKNOWN':(1,5)},
    'test_shared_source_cases_independent': {'known':(8,14), 'declared_UNKNOWN':(4,10), 'additional_UNKNOWN':(0,0)},
    'test_service_release_preflight_independent': {'known':(15,62), 'declared_UNKNOWN':(4,20), 'additional_UNKNOWN':(0,0)},
    'test_at24_27_change_batch_independent': {'known':(27,100), 'declared_UNKNOWN':(8,40), 'additional_UNKNOWN':(0,0)},
}


def main():
    config = read_json(HERE / 'audit-config.json')
    assert config['archive_ready'] is True
    attempt = HERE / 'archive-v1'
    html = []; oracle = []; lock_cases = []
    for group, (count, negatives, losses) in RULES.items():
        traces = list((ART / group).glob('*.stdout.jsonl'))
        assert len(traces) == count
        modes = set()
        for path in traces:
            packets = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            results = [row for row in packets if isinstance(row,dict) and str(row.get('scope','')).startswith('FULL_ORIGINAL_HTML_')]
            assert len(results) == 1
            row = results[0]; mode = row['mode']
            assert mode not in modes; modes.add(mode)
            assert (row.get('negative_transport_fixture') is True) == (mode in negatives)
            category = 'CONTROLLED_CLIENT_NEGATIVE' if mode in negatives else 'REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS' if mode in losses else 'REAL_BACKEND_RESPONSE_SCENARIO'
            calls = row['calls']
            html.append(dict(group=group,mode=mode,category=category,raw=str(path.relative_to(ROOT)),
                raw_identity=identity(path),page_fetch_records=len(calls),
                methods=dict(Counter(call.get('method','UNKNOWN') for call in calls)),
                statuses=dict(Counter(str(call.get('status','UNKNOWN')) for call in calls)),
                real_browser='NOT_RUN',fixture_setup_and_control_HTTP_not_counted=True))
        assert negatives.issubset(modes) and losses.issubset(modes)
        for path in (ART / group).glob('oracle-*.jsonl'):
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                assert row.get('head',row.get('source_sha')) == SHA
                expected, actual = set(row['expected_affected']),set(row['actual_affected'])
                preserved, kept = set(row['expected_preserved']),set(row['actual_preserved'])
                assert expected == actual and preserved == kept
                declared = bool(row.get('intentional_unknown') or row.get('intentional_unknown_expansion'))
                additional = bool(row.get('unknown_scope') or row.get('expected_classification') == 'UNKNOWN'
                                  or row.get('expected_state') in {'UNKNOWN','NO_PLAN','NO_PREPARATION'})
                category = 'declared_UNKNOWN' if declared else 'additional_UNKNOWN' if additional else 'known'
                result = dict(group=group,category=category,raw=str(path.relative_to(ROOT)),line=line_number,
                    source_sha=SHA,affected_pairs=len(expected),preserved_pairs=len(preserved),
                    missed=0,wrong_affected=0,wrong_preserved=0,missing_preserved=0,
                    lock_fields_recorded='expected_locked' in row)
                if 'expected_locked' in row:
                    assert set(row['expected_locked']) == set(row['actual_locked'])
                    result.update(locked_pairs=len(set(row['expected_locked'])),wrong_locked=0)
                oracle.append(result)
        for path in (ART / group).glob('at-results-*.jsonl'):
            for line_number,line in enumerate(path.read_text().splitlines(),1):
                row = json.loads(line)
                if row.get('p1_lock_exact') is True:
                    assert row['all_six_local_outputs_verified'] is True
                    lock_cases.append(dict(raw=str(path.relative_to(ROOT)),line=line_number,
                        case=row.get('case'),P1_lock_exact=True,six_goals_verified=True))
    assert len(html) == 41 and len(oracle) == 77
    categories = dict(Counter(row['category'] for row in html))
    assert categories == {'REAL_BACKEND_RESPONSE_SCENARIO':29,
                          'REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS':7,
                          'CONTROLLED_CLIENT_NEGATIVE':5}
    assert sum(row['page_fetch_records'] for row in html) == 957
    stated_html = read_json(BASE / 'html-summary.json')
    assert stated_html['source_sha'] == SHA and stated_html['total'] == len(html)
    assert stated_html['total_node_call_records'] == sum(row['page_fetch_records'] for row in html)
    assert stated_html['response_evidence_categories'] == categories
    for stated in stated_html['traces']:
        observed = next(row for row in html if row['raw'] == str((BASE / stated['path']).relative_to(ROOT)))
        assert stated['sha256'] == observed['raw_identity']['sha256']
        assert stated['size'] == observed['raw_identity']['bytes']
        assert stated['http_call_records'] == observed['page_fetch_records']
        assert stated['response_evidence'] == observed['category']
    groups = {}
    for group in RULES:
        groups[group] = {}
        for category in ['known','declared_UNKNOWN','additional_UNKNOWN']:
            rows = [row for row in oracle if row['group']==group and row['category']==category]
            actual = (len(rows),sum(row['affected_pairs'] for row in rows))
            assert actual == EXPECTED_ROWS[group][category]
            groups[group][category] = dict(records=actual[0],affected_step_pairs=actual[1],
                preserved_step_pairs=sum(row['preserved_pairs'] for row in rows),
                missed=0,wrong_affected=0,wrong_preserved=0,missing_preserved=0,
                rows_with_lock_fields=sum(row['lock_fields_recorded'] for row in rows))
    locked = [row for row in oracle if row['lock_fields_recorded']]
    assert len(locked) == 19 and sum(row['locked_pairs'] for row in locked) == 3
    assert len(lock_cases) == 2 and {row['case'] for row in lock_cases} == {'A','B'}
    new = read_json(ROOT / '.runtime/manual-continuation-independent-formal-v2/manual-independent-v2-html-summary.json')['flows']
    assert len(new) == 8
    combined = Counter(categories)
    for row in new:
        assert not row['negative_transport_fixture']
        combined['REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS' if row['mode'] in {'lost_choice','lost_adopt'} else 'REAL_BACKEND_RESPONSE_SCENARIO'] += 1
    assert sum(combined.values()) == 49
    public_json(attempt / 'prior41-plus-new8-HTML-denominators.json',dict(status='PASS_RECOUNTED_RAW_TRACES',
        source_sha=SHA,prior_HTML_traces=41,new_HTML_traces=8,total_HTML_traces=49,
        prior_page_fetch_records=957,new_page_fetch_records=sum(row['requests'] for row in new),
        prior_categories=categories,total49_categories=dict(combined),raw_traces=html,
        all_real_browser_Windows_formal_AT_real_model_production='NOT_RUN',
        controlled_client_negative_not_real_backend_refusal_evidence=True,
        fixture_setup_and_control_HTTP_denominators_not_added=True))
    public_json(attempt / 'prior77-propagation-and-lock-denominators.json',dict(status='PASS_RAW_LITERAL_ROWS',
        source_sha=SHA,records=77,groups=groups,rows=oracle,
        UNKNOWN_categories_separate_from_known=True,lock_rows=19,expected_locked_pairs=3,
        wrong_locked_pairs=0,selected_capacity_P1_exact_cases=lock_cases,
        missing_lock_fields_not_claimed_as_lock_precision=True))
    print(json.dumps(dict(status='PASS_RAW_TRACE_RECOUNT',HTML=49,prior_oracle_rows=77,
        prior_page_fetch_records=957,total49_categories=dict(combined),lock_rows=19,locked_pairs=3)))


if __name__ == '__main__':
    main()
