"""Export frozen T07 evidence without changing any original failed window."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2] if Path(__file__).parent.name == 'f2-t07-full-chain' else Path(__file__).resolve().parents[4]
PRIVATE = ROOT / '.runtime/f2-t07-full-chain'
OUTPUT = ROOT / 'docs/F2/evidence/f2-t07-full-chain-20261011'
POLICY = ROOT / 'docs/F2/evidence/case-cancel-after-receipt-20261011/build_archive.py'
spec = importlib.util.spec_from_file_location('accepted_t07_evidence_policy', POLICY)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
sha = lambda value: hashlib.sha256(value).hexdigest()
identity = lambda c: c.attrib.get('classname', '')+'::'+c.attrib['name']
state = lambda c: 'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'


def outcomes(path):
    cases = ET.parse(path).getroot().findall('.//testcase')
    ids = [identity(c) for c in cases]
    assert len(ids) == len(set(ids)), (path, 'duplicate testcase IDs')
    return {identity(c): state(c) for c in cases}


def failure_map(final):
    last = outcomes(PRIVATE/'full-complete-final.xml')
    categories = {
        'first': 'DRIVER_ORACLE_RECOVERY_EVENT_FULL_OBJECT_VS_FIXED_READ_ONLY_PROJECTION',
        'second': 'DRIVER_ORACLE_CANCEL_STATE_IN_EVENT_NOT_TOP_LEVEL',
        'third': 'DRIVER_ORACLE_OPTIONAL_MANAGED_ACCESS_COLUMN_NOT_INSTALLED',
        'proof-check': 'DRIVER_ORACLE_COMBINATION_MEMBERSHIP_REQUIRES_MEMBERS_TABLE_JOIN',
    }
    rows = []
    for window, reason in categories.items():
        for id, status in outcomes(PRIVATE/(window+'.xml')).items():
            if status not in ('FAIL', 'ERROR'): continue
            assert last.get(id) == 'PASS', (window, id, 'failure not repaired in final full window')
            rows.append(dict(window=window, test_id=id, original_status=status, classification=reason,
                             final_window='full-complete-final', final_status=last[id]))
    record = dict(format='ORIGINAL_FAILURES_RETAINED_SAME_ID_FINAL_MAPPING',
        source_sha=final['source_sha'], original_failure_execution_count=len(rows),
        unique_failed_test_ids=len({r['test_id'] for r in rows}), rows=rows,
        stopped_full_window=dict(window='full-final', complete=False,
            process_exit=json.loads((PRIVATE/'full-final-run.json').read_text())['exit_code'],
            junit_counts=dict(Counter(outcomes(PRIVATE/'full-final.xml').values())),
            reason_file='full-first-window-stop.json',
            log_teardown_exception='KeyError after owned SIGINT; kept verbatim; not a completed regression',
            unrun_tests_are_not_pass=True),
        browser_module_selection_collection_error=dict(window='goal-results-complete',
            original_status='ERROR', process_exit=2, pytest_collection_error='ModuleNotFoundError: No module named playwright',
            actual_test_functions_executed=0, actual_browser_starts=0,
            browser_module_retried=False, final_browser_status='NOT_RUN',
            independently_allowed_pg_only_window='goal-results-pg-complete',
            no_same_id_repaired_claim=True))
    target = PRIVATE/'failure-to-final-map.json'
    assert not target.exists()
    target.write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


def main():
    final = json.loads((PRIVATE/'full-complete-final-run.json').read_text())
    assert final['exit_code'] == 0 and not final['source_drift'] and not final['uncommitted_source']
    assert not final['prior_test_ids_missing'] and final['complete_module_count'] == 39
    assert final['source_manifest_sha256'] == sha((PRIVATE/'final-frozen-source-manifest.json').read_bytes())
    failure_map(final)
    assert not (OUTPUT/'archive-manifest.json').exists(), 'freeze archive inputs once'
    allowed = {'.xml', '.log', '.json', '.md', '.py', '.txt'}
    candidates = [p for p in sorted(PRIVATE.rglob('*')) if p.is_file() and p.suffix in allowed
                  and '__pycache__' not in p.parts and p.name != 'archive-static-whitelist.json'
                  and 'archive-audit' not in p.parts]
    # A reviewer supplies this exact path/hash list after reading static inputs.
    # Merely discovering a .py file never authorizes copying its raw contents.
    whitelist = json.loads((PRIVATE/'archive-static-whitelist.json').read_text())
    assert set(whitelist) == {str(p.relative_to(ROOT)) for p in candidates if p.suffix == '.py'}
    assert all(sha((ROOT/p).read_bytes()) == h for p,h in whitelist.items())
    candidates.append(PRIVATE/'archive-static-whitelist.json')
    entries = []
    for source in candidates:
        original = source.read_bytes(); counts = Counter(); results = None
        if source.suffix == '.xml':
            tree = ET.fromstring(original); before = policy.policy.identity_results(tree)
            for suite in tree.iter('testsuite'):
                if 'hostname' in suite.attrib:
                    suite.set('hostname', 'synthetic-fixture-host'); counts['hostname'] += 1
            for element in tree.iter():
                if element.tag in ('failure', 'error', 'system-out', 'system-err', 'skipped'):
                    if element.text: element.text = policy.policy.scrub(element.text, counts)
                    for k in list(element.attrib): element.set(k, policy.policy.scrub(element.attrib[k], counts))
            assert policy.policy.identity_results(tree) == before
            payload = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
            results = dict(Counter(status for _, _, _, status in before[0]))
        elif source.suffix == '.json':
            data = json.loads(original); policy.check_json_credentials(data)
            payload = (json.dumps(policy.metadata_scrub(data, counts), indent=2, sort_keys=True)+'\n').encode()
        elif source.suffix == '.py':
            assert whitelist[str(source.relative_to(ROOT))] == sha(original)
            payload = original
        else:
            payload = policy.policy.scrub(original.decode(), counts).encode()
        relative = source.relative_to(PRIVATE)
        exported = OUTPUT/'raw'/relative.parent/(relative.stem+'.sanitized'+relative.suffix)
        compressed = len(payload) > 512_000
        content = gzip.compress(payload, mtime=0) if compressed else payload
        if compressed: exported = exported.with_suffix(exported.suffix+'.gz')
        exported.parent.mkdir(parents=True, exist_ok=True); assert not exported.exists()
        exported.write_bytes(content)
        entries.append(dict(original_local_path=str(source.relative_to(ROOT)), original_sha256=sha(original),
            original_bytes=len(original), exported_path=str(exported.relative_to(OUTPUT)),
            exported_sha256=sha(content), exported_bytes=len(content), sanitized_payload_sha256=sha(payload),
            sanitized_payload_bytes=len(payload), compression='gzip' if compressed else None,
            redactions=dict(counts), test_results_preserved=results,
            classification='STATIC_CODE_EXACT_SHA_ALLOWLIST' if source.suffix == '.py' else 'JSON_METADATA' if source.suffix == '.json' else 'JUNIT' if source.suffix == '.xml' else 'STDOUT_OR_REPORT'))
    manifest = dict(format='SANITIZED_COPY_WITH_ORIGINAL_HASH', raw_inputs_rewritten=False,
        source_sha=final['source_sha'], source_manifest_sha256=final['source_manifest_sha256'],
        input_file_count=len(entries), policy_source_sha256=sha(POLICY.read_bytes()),
        policy='Accepted stdout/JUnit redaction policy; JSON retains literal test IDs and SHA values. Static code exact SHA allowlist. Failed and interrupted windows retain their actual counts/status/durations. Gzip is lossless with fixed mtime.',
        artifacts=entries)
    (OUTPUT/'archive-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(files=len(entries), original_bytes=sum(e['original_bytes'] for e in entries),
                         exported_bytes=sum(e['exported_bytes'] for e in entries), utc=datetime.now(timezone.utc).isoformat())))


if __name__ == '__main__': main()
