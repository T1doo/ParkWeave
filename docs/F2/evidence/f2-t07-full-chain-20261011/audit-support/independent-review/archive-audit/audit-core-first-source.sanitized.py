"""Read-only independent audit of frozen T07 core; writes only own audit results."""
from collections import Counter
from datetime import datetime, timezone
import ast
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / '.runtime/f2-t07-full-chain'
OUT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'docs/F2/evidence/f2-t07-full-chain-20261011'
SOURCE = 'b5ea90ac9b366b015b43c426ad94b72faf7c8b72'
SOURCE_MANIFEST = 'fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf'
CORE_MANIFEST = '54d7a30888aeae04ea94b651fe3b46a092317dd217b790e7ae70d2676cf9f325'
sha = lambda data: hashlib.sha256(data).hexdigest()
identity = lambda c: c.attrib.get('classname', '') + '::' + c.attrib['name']
state = lambda c: 'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'


def junit(data):
    tree = ET.fromstring(data)
    cases = tree.findall('.//testcase')
    ids = [identity(c) for c in cases]
    assert len(ids) == len(set(ids)), 'duplicate testcase identity'
    facts = [(dict(c.attrib), state(c),
              c.find('failure').attrib.get('type') if c.find('failure') is not None else
              c.find('error').attrib.get('type') if c.find('error') is not None else None)
             for c in cases]
    suites = [{k: v for k, v in s.attrib.items() if k != 'hostname'}
              for s in tree.iter('testsuite')]
    return tree, facts, suites, dict(Counter(state(c) for c in cases))


def json_literals(value, prefix='$'):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from json_literals(v, prefix + '.' + k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from json_literals(v, prefix + '[' + str(i) + ']')
    elif isinstance(value, str):
        yield prefix, value


def main():
    started = datetime.now(timezone.utc).isoformat()
    manifest_bytes = (PUBLIC / 'archive-manifest.json').read_bytes()
    assert sha(manifest_bytes) == CORE_MANIFEST
    manifest = json.loads(manifest_bytes)
    assert manifest['input_file_count'] == len(manifest['artifacts']) == 167
    assert manifest['source_sha'] == SOURCE and manifest['source_manifest_sha256'] == SOURCE_MANIFEST
    policy_path = ROOT / 'docs/F2/evidence/case-cancel-after-receipt-20261011/build_archive.py'
    assert sha(policy_path.read_bytes()) == manifest['policy_source_sha256']
    spec = importlib.util.spec_from_file_location('audit_accepted_policy', policy_path)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    approvals = json.loads((RUNTIME / 'independent-review/static-export-review.json').read_text())['approved_path_sha256']
    whitelist = json.loads((RUNTIME / 'archive-static-whitelist.json').read_text())
    assert approvals == whitelist and len(whitelist) == 12
    expected_sources = {e['original_local_path'] for e in manifest['artifacts']}
    expected_exports = {e['exported_path'] for e in manifest['artifacts']}
    assert len(expected_sources) == len(expected_exports) == 167
    current_sources = {str(p.relative_to(ROOT)) for p in RUNTIME.rglob('*') if p.is_file()
                       and p.suffix in {'.xml', '.log', '.json', '.md', '.py', '.txt'}
                       and '__pycache__' not in p.parts and 'archive-audit' not in p.parts}
    # Root declared these post-freeze support records explicitly. They are not
    # retroactively added to the fixed 167 core inputs or old signed reports.
    post_freeze_support = {'.runtime/f2-t07-full-chain/' + name for name in
                          ('archive-export-run.json', 'root-core-check.json',
                           'staged-whitespace-verification.json')}
    assert expected_sources <= current_sources, 'frozen original input missing'
    assert current_sources - expected_sources <= post_freeze_support, 'undeclared post-freeze candidate'
    actual_exports = {str(p.relative_to(PUBLIC)) for p in (PUBLIC / 'raw').rglob('*') if p.is_file()}
    assert actual_exports == expected_exports, 'export set changed'
    artifacts = []
    xml_windows = {}
    secret_findings = []
    for entry in manifest['artifacts']:
        local = ROOT / entry['original_local_path']
        exported = PUBLIC / entry['exported_path']
        raw = local.read_bytes()
        content = exported.read_bytes()
        assert sha(raw) == entry['original_sha256'] and len(raw) == entry['original_bytes']
        assert sha(content) == entry['exported_sha256'] and len(content) == entry['exported_bytes']
        payload = gzip.decompress(content) if entry['compression'] == 'gzip' else content
        assert sha(payload) == entry['sanitized_payload_sha256'] and len(payload) == entry['sanitized_payload_bytes']
        counts = Counter()
        if entry['classification'] == 'JUNIT':
            tree, facts, suites, statuses = junit(raw)
            _, sanitized_facts, sanitized_suites, sanitized_statuses = junit(payload)
            assert facts == sanitized_facts and suites == sanitized_suites and statuses == sanitized_statuses
            assert statuses == entry['test_results_preserved']
            for suite in tree.iter('testsuite'):
                if 'hostname' in suite.attrib:
                    suite.set('hostname', 'synthetic-fixture-host')
                    counts['hostname'] += 1
            for element in tree.iter():
                if element.tag in ('failure', 'error', 'system-out', 'system-err', 'skipped'):
                    if element.text:
                        element.text = policy.policy.scrub(element.text, counts)
                    for key in list(element.attrib):
                        element.set(key, policy.policy.scrub(element.attrib[key], counts))
            expected = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
            xml_windows[entry['original_local_path']] = dict(counts=statuses,
                tests=len(facts), identities=[d['classname'] + '::' + d['name'] if 'classname' in d else '::' + d['name'] for d, _, _ in facts],
                suite_seconds=sum(float(s['time']) for s in suites))
        elif entry['classification'] == 'JSON_METADATA':
            original = json.loads(raw)
            sanitized = json.loads(payload)
            policy.check_json_credentials(original)
            policy.check_json_credentials(sanitized)
            expected = (json.dumps(policy.metadata_scrub(original, counts), indent=2, sort_keys=True) + '\n').encode()
            # Hash, fingerprint and testcase identity literals retain their exact
            # original values; only the accepted execution/URI/Bearer policy runs.
            original_literals = dict(json_literals(original))
            for key, value in json_literals(sanitized):
                if re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', original_literals[key]):
                    assert value == original_literals[key], 'hash literal altered'
                if re.fullmatch(r'[A-Za-z0-9_-]{40,}', value) and not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}|[A-Z][A-Z0-9_]+', value):
                    secret_findings.append(dict(path=entry['exported_path'], json_key=key, value_sha256=sha(value.encode()), reason='unclassified opaque metadata literal'))
        elif entry['classification'] == 'STATIC_CODE_EXACT_SHA_ALLOWLIST':
            assert local.suffix == '.py' and whitelist[entry['original_local_path']] == sha(raw)
            tree = ast.parse(raw)
            literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            assert not any(re.search(r'Bearer\s+[A-Za-z0-9_.-]{15,}|postgres(?:ql)?://|-----BEGIN .*PRIVATE KEY', v) for v in literals)
            expected = raw
        else:
            assert entry['classification'] == 'STDOUT_OR_REPORT'
            expected = policy.policy.scrub(raw.decode(), counts).encode()
        assert payload == expected, 'sanitization reproduction differs: ' + entry['exported_path']
        assert dict(counts) == entry['redactions']
        expected_content = gzip.compress(expected, mtime=0) if entry['compression'] == 'gzip' else expected
        assert content == expected_content
        # Static reviewed source legitimately contains path/regex definitions.
        if entry['classification'] != 'STATIC_CODE_EXACT_SHA_ALLOWLIST':
            text = payload.decode()
            for pattern, reason in [(r'(?i)Bearer\s+(?!\[REDACTED\])[A-Za-z0-9_.~+/=-]+', 'bearer value'),
                                    (r'postgres(?:ql)?://[^\s\"<>]+', 'PG URI'),
                                    (r'/workspace/ParkWeave', 'absolute repo execution path'),
                                    (r'/tmp/[^\s\"<>]+', 'temporary execution path')]:
                if re.search(pattern, text):
                    secret_findings.append(dict(path=entry['exported_path'], reason=reason))
        artifacts.append(dict(original_path=entry['original_local_path'], exported_path=entry['exported_path'],
                              original_sha256=sha(raw), exported_sha256=sha(content), payload_sha256=sha(payload),
                              bytes_and_policy_reproduced=True))
    if secret_findings:
        (OUT / 'credential-candidate-findings.json').write_text(json.dumps(secret_findings, indent=2) + '\n')
    assert not secret_findings, 'credential/path/opaque candidate findings require review'
    freeze_path = RUNTIME / 'final-frozen-source-manifest.json'
    assert sha(freeze_path.read_bytes()) == SOURCE_MANIFEST
    source_files = json.loads(freeze_path.read_text())
    assert len(source_files) == 406 and all(sha((ROOT / p).read_bytes()) == h for p, h in source_files.items())
    prior_source = json.loads((ROOT / '.runtime/case-cancel-after-receipt/final-source-manifest.json').read_text())
    assert len(prior_source) == 405 and all(sha((ROOT / p).read_bytes()) == h for p, h in prior_source.items())
    baseline = json.loads((RUNTIME / 'accepted-archive-byte-baseline.json').read_text())
    assert len(baseline['files']) == baseline['file_count'] == 428
    assert all((ROOT / p).is_file() and sha((ROOT / p).read_bytes()) == h for p, h in baseline['files'].items())
    old_parents = {str(Path(p).parent) for p in baseline['files']}
    old_current = {str(p.relative_to(ROOT)) for d in old_parents for p in (ROOT / d).iterdir() if p.is_file()}
    assert old_current == set(baseline['files']), 'old artifact set has additions/deletions'

    def cases(path):
        tree = ET.parse(path).getroot()
        values = tree.findall('.//testcase')
        assert len(values) == len({identity(c) for c in values})
        return {identity(c): state(c) for c in values}

    full = cases(RUNTIME / 'full-complete-final.xml')
    supplemental = cases(RUNTIME / 'goal-results-pg-complete.xml')
    prior = cases(ROOT / '.runtime/case-cancel-after-receipt/full-final.xml')
    assert len(full) == 1571 and Counter(full.values()) == Counter(PASS=1570, SKIP=1)
    assert len(supplemental) == 44 and set(supplemental.values()) == {'PASS'}
    assert len(prior) == 1561 and set(prior) <= set(full) and len(set(full) - set(prior)) == 10
    assert not set(full) & set(supplemental)
    combined = full | supplemental
    assert len(combined) == 1615 and Counter(combined.values()) == Counter(PASS=1614, SKIP=1)
    failure_map = json.loads((RUNTIME / 'failure-to-final-map.json').read_text())
    expected_failures = []
    for window in ('first', 'second', 'third', 'proof-check'):
        for id, status in cases(RUNTIME / (window + '.xml')).items():
            if status in ('FAIL', 'ERROR'):
                expected_failures.append((window, id, status))
                assert full[id] == 'PASS'
    actual_failures = [(r['window'], r['test_id'], r['original_status']) for r in failure_map['rows']]
    assert actual_failures == expected_failures and len(expected_failures) == 22
    assert failure_map['unique_failed_test_ids'] == len({id for _, id, _ in expected_failures}) == 10
    assert all(r['final_window'] == 'full-complete-final' and r['final_status'] == 'PASS' for r in failure_map['rows'])
    stopped = cases(RUNTIME / 'full-final.xml')
    stopped_run = json.loads((RUNTIME / 'full-final-run.json').read_text())
    assert len(stopped) == 17 and set(stopped.values()) == {'PASS'} and stopped_run['exit_code'] == 1
    assert 'KeyError' in (RUNTIME / 'full-final.log').read_text()
    collection = cases(RUNTIME / 'goal-results-complete.xml')
    assert collection == {'::tests.test_case_goal_results_browser': 'ERROR'}
    collection_run = json.loads((RUNTIME / 'goal-results-complete-run.json').read_text())
    assert collection_run['exit_code'] == 2 and 'playwright' in (RUNTIME / 'goal-results-complete.log').read_text()
    assert failure_map['browser_module_selection_collection_error']['no_same_id_repaired_claim'] is True
    assert failure_map['browser_module_selection_collection_error']['final_browser_status'] == 'NOT_RUN'
    run_records = {}
    for window, count, modules in [('full-complete-final', 1571, 39), ('goal-results-pg-complete', 44, 1)]:
        record = json.loads((RUNTIME / (window + '-run.json')).read_text())
        assert record['source_sha'] == SOURCE and record['source_manifest_sha256'] == SOURCE_MANIFEST
        assert record['exit_code'] == 0 and not record['source_drift'] and record['tests'] == count
        assert record['complete_module_count'] == modules and not record['atexit_cleanup_diagnostic']
        assert record['log_sha256'] == sha((RUNTIME / (window + '.log')).read_bytes())
        assert record['xml_sha256'] == sha((RUNTIME / (window + '.xml')).read_bytes())
        run_records[window] = {k: record[k] for k in ['source_sha', 'PASS', 'FAIL', 'ERROR', 'SKIP', 'tests', 'complete_module_count', 'exit_code', 'elapsed_seconds', 'source_drift', 'xml_sha256', 'log_sha256']}
    review = json.loads((RUNTIME / 'independent-review/review.json').read_text())
    assert review['source_sha'] == SOURCE and review['root_39_module_window']['status'] == 'RUNNING'
    assert review['independent_total_test_count'] == 13 and review['aggregate_only_counts']['PASS'] == 13
    at_map = json.loads((RUNTIME / 'original-at-finite-map.json').read_text())
    assert at_map['whole_original_ATs'] == 'NOT_RUN' and at_map['AT35_production_new_Run_assignment'] == 'BLOCKED'
    original_at = json.loads((RUNTIME / 'independent-review/initial-full-chain-review.json').read_text())['at_mapping']
    assert at_map['original_scenario_steps_oracles_retained'] == original_at and len(original_at) == 35
    for group in at_map['finite_current_window_groups'].values():
        assert group['window'] == 'full-complete-final'
        assert group['exact_test_ids'] and all(full[k] == v == 'PASS' for k, v in group['exact_test_ids'].items())
    result = dict(status='LIMITED_PASS', source_sha=SOURCE, source_manifest_sha256=SOURCE_MANIFEST,
        core_manifest_sha256=CORE_MANIFEST, started_at_utc=started, ended_at_utc=datetime.now(timezone.utc).isoformat(),
        original_count=167, original_bytes=sum(e['original_bytes'] for e in manifest['artifacts']),
        exported_bytes=sum(e['exported_bytes'] for e in manifest['artifacts']), gzip_count=sum(e['compression'] == 'gzip' for e in manifest['artifacts']),
        classification_counts=dict(Counter(e['classification'] for e in manifest['artifacts'])),
        exact_hashes_and_reproduction=artifacts, junit_windows=xml_windows, completed_root_windows=run_records,
        combined_root_counts=dict(PASS=1614, FAIL=0, ERROR=0, SKIP=1, unique_ids=1615, complete_modules_across_two_windows=40),
        original_failures=dict(occurrences=22, unique_ids=10, same_id_final_PASS=True),
        stopped_window=dict(junit_PASS=17, process_exit=1, complete=False, teardown_KeyError_preserved=True),
        collection_error=dict(id='::tests.test_case_goal_results_browser', status='ERROR', process_exit=2, browser_functions_run=0, final_browser_status='NOT_RUN', same_id_repaired=False),
        secret_findings=[], source_drift=[], previous405_drift=[], old428_drift=[], old428_set_changes=[],
        declared_post_freeze_support_outside_core=sorted(current_sources - expected_sources),
        signed_independent_review_not_rewritten=True, remaining_blockers=[],
        limits=['Two completed root windows are not one 40-module execution window.',
                'No complete-repository, formal AT01-35, native Windows, real model, natural-person pilot or browser acceptance claim.',
                'Old worker Case_count0 remains UNKNOWN.',
                'Git delivery commit, normal push and remote comparison have not yet been independently audited.'])
    target = OUT / 'audit-core-results.json'
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'source_sha', 'core_manifest_sha256', 'original_count', 'original_bytes', 'exported_bytes', 'gzip_count', 'combined_root_counts', 'original_failures', 'remaining_blockers']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
