"""Map every actual failed testcase to its separate same-ID repair evidence."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
PRIVATE = ROOT / '.runtime/case-cancel-before-receipt'
OUTPUT = Path(__file__).resolve().parent


def outcomes(path):
    return {x.attrib['classname'] + '::' + x.attrib['name']:
            ('FAIL' if x.find('failure') is not None else 'ERROR' if x.find('error') is not None
             else 'SKIP' if x.find('skipped') is not None else 'PASS')
            for x in ET.parse(path).iter('testcase')}


def explanation(name):
    if 'cross_scope_even_with_misconfigured_assignment' in name:
        return ('UNCONFIRMED_HISTORICAL_CAUSE',
                'Original worker return0 followed by case_count0; original stdout and Run/operation states were not captured. Independent repeat observed SUCCEEDED/VERIFIED, cases1, empty worker stdout. No lease or requirement relaxed; final assertion adds failure diagnostics.')
    if 'stripped_later_accept_and_create' in name:
        return ('ACTUAL_PRODUCT_DEFECT_AND_OWNED_PG_REPRODUCTION',
                'Later ACCEPT/CREATE lineage removed together skipped if-extras proof; actual preview true and POST200. Repair always binds OFFER/REOFFER extras and requires a predecessor for every later actual ACCEPT; independent same-ID repeat rejects and preserves snapshot.')
    if 'wheel_installed' in name:
        return ('DIRECT_ARCHIVE_KEY_ERROR',
                'Actual wheel omitted migration-031.sql. Added only that file to original explicit package-data; actual installed wheel migration repeat verifies schema31.')
    if 'migration29_repeat' in name:
        return ('DIRECT_STRICT_MIGRATION_GATE_AND_FIXTURE_STATE',
                'Original owned migration029 replay fixture removed30 but retained31. Test removes30/31 only under original receipt in rollback transaction; production gate unchanged.')
    if 'additive_unreleased_grant_scope' in name:
        return ('DIRECT_VERSION_ORACLE_MISMATCH',
                'Current schema31 mismatched obsolete expected30. Current/future version oracles updated to31/32; privilege/record-preservation requirements retained.')
    if 'step_namespace' in name or name.endswith('[external]'):
        return ('DIRECT_PRE_API_CHECK_VIOLATION',
                'Original DB CHECK rejected unsupported corruption before API observation. Only the owned corruption fixture removes the specified CHECK; product constraint unchanged. API must then explicitly refuse and preserve all rows.')
    if 'closed_history' in name:
        return ('DIRECT_PRE_API_FOREIGN_KEY_VIOLATION',
                'Original damaged history fixture lacked referenced lifecycle row. Add its owned REOPENED row before old-close history; cancellation must still refuse historical closure.')
    if 'real_lock_wait' in name and name.endswith('[plan]'):
        return ('DIRECT_PLAN_PREREQUISITE_REFUSAL',
                'Old controlled plan cannot be adopted after acceptance. Race uses legal registered plan adoption, preloaded POST body, and real parent lock waits; production prerequisite retained.')
    if 'cancelled_history_reads' in name:
        return ('DIRECT_PLAN_PREREQUISITE_REFUSAL',
                'Controlled plan created after real acceptance correctly refused. Create/adopt/check original plan before resource link and ACCEPT, then cancel and verify all historical GETs leave snapshots unchanged.')
    if 'receipt_parent_bypass' in name:
        return ('DIRECT_TEST_HELPER_TYPE_ERROR',
                'Original helper dereferenced empty current receipt SHA before sending any API command. Construct valid decision payload and require server cancellation guard before receipt prerequisites.')
    raise AssertionError('unclassified failure: ' + name)


def main():
    final = json.loads((PRIVATE / 'full-final-run.json').read_text())
    assert final['exit_code'] == 0 and not final['source_drift'] and not final['prior_test_ids_missing']
    root_passes = outcomes(PRIVATE / 'full-final.xml')
    independent_passes = outcomes(PRIVATE / 'independent-review/proof-corrected-extra-probes.xml')
    entries = []
    windows = [(PRIVATE / (name + '.xml'), 'root') for name in
               ['first', 'second', 'full-attempt-1', 'schema-integration']]
    windows.append((PRIVATE / 'independent-review/pre-fix-extra-probes.xml', 'independent'))
    for path, label in windows:
        for x in ET.parse(path).iter('testcase'):
            problem = x.find('failure')
            if problem is None:
                problem = x.find('error')
            if problem is None:
                continue
            identity = x.attrib['classname'] + '::' + x.attrib['name']
            passes = independent_passes if label == 'independent' else root_passes
            assert passes[identity] == 'PASS', (identity, passes.get(identity))
            grade, reason = explanation(identity)
            entries.append(dict(test_id=identity, original_status='FAIL' if x.find('failure') is not None else 'ERROR',
                                original_window=path.stem,
                                original_sanitized_junit=label + '/' + path.stem + '.sanitized.xml',
                                direct_exception_type=problem.attrib.get('type'),
                                evidence_grade=grade, diagnosis_and_correction=reason,
                                repaired_same_id_status=passes[identity],
                                repaired_window=('independent/proof-corrected-extra-probes.sanitized.xml' if label == 'independent'
                                                 else 'root/full-final.sanitized.xml'),
                                final_source_sha=final['source_sha']))
    result = dict(format='ACTUAL_FAILED_ID_TO_SEPARATE_RECHECK',
                  old_results_rewritten=False, failed_occurrences=len(entries),
                  unique_failed_ids=len({x['test_id'] for x in entries}), entries=entries)
    (OUTPUT / 'failure-map.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'entries'}))


if __name__ == '__main__':
    main()
