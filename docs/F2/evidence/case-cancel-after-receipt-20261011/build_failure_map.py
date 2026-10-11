"""Preserve every actual failure and link a separate same-ID passing window."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
PRIVATE = ROOT / '.runtime/case-cancel-after-receipt'
OUTPUT = Path(__file__).resolve().parent


def cases(path):
    items=list(ET.parse(path).iter('testcase'))
    assert len(items)==len({x.attrib['classname']+'::'+x.attrib['name'] for x in items}),'duplicate testcase ID: '+str(path)
    return {x.attrib['classname']+'::'+x.attrib['name']:
            ('FAIL' if x.find('failure') is not None else 'ERROR' if x.find('error') is not None
             else 'SKIP' if x.find('skipped') is not None else 'PASS')
            for x in items}


def explanation(window, identity):
    if window == 'first':
        return ('DIRECT_MISSING_TEST_FIXTURE_IMPORT', 'Pytest could not find preparation_fixture before any API call. Import the existing fixture explicitly; no product permission or assertion relaxed.')
    if window == 'schema-oracles':
        return ('DIRECT_STRICT_MIGRATION_GATE', 'Current owned fixture was schema32 but replayed historical031, whose unchanged gate accepts only30/31. Current fixture/repeat uses032 under the original ticket. Historical031 test separately removes32 under its original owner transaction; no new grant or gate relaxation.')
    if window in ('fourth', 'sixth'):
        return ('DIRECT_SCHEMA_VERSION_ORACLE_MISMATCH', 'Actual current schema32 mismatched obsolete expected31. Update only the current version oracle; preserve history, permissions and owned migration requirements.')
    if window == 'third':
        if identity.endswith('[adapter]'):
            return ('DIRECT_PRE_API_UNDEFINED_COLUMN', 'Ordinary schema has no adapter_execution column. Owned corruption fixture explicitly adds the column before modeling an activated adapter; server must refuse and preserve all business rows. Product schema unchanged.')
        if identity.endswith('[event_reason]'):
            return ('INCORRECT_UNSIGNED_OWNER_REWRITE_ORACLE', 'Original fixture changed reason and recomputed its valid fingerprint; unsigned self-consistent owner rewrite was not evidence of detectable corruption. Corrected fixture corrupts reason without rehashing, and requires recovery/replay409. No claim that arbitrary fully consistent privileged rewriting is detectable.')
        if identity.endswith('[plan]'):
            return ('DIRECT_PLAN_PREREQUISITE_REFUSAL', 'Controlled plan creation after dispatch correctly refused409, so it was not a legal writer-first race. Use legal registered-plan adoption with real parent PG lock waits; retain the original controlled-plan guard.')
        if 'legitimate_local_prefix_capacity' in identity:
            return ('DIRECT_ALREADY_VALIDATED_PREREQUISITE', 'Repeated identical REVALIDATE correctly refused409. Build61 genuine new source generations via independent original resource group cancel/create/bind APIs, then require62 request,63 reconciliation,64 final and cold recovery of every original key.')
        if 'history_get_and_rejected_plan_callbacks' in identity:
            return ('DIRECT_PLAN_PREREQUISITE_REFUSAL', 'Create/check/adopt the controlled plan legally before dispatch/SUBMIT, then freeze Case and verify historical GET and rejected callbacks leave all rows unchanged.')
        if identity.endswith('[late_dispatch]'):
            return ('DIRECT_OFFLINE_FIXTURE_MISSING_DEPENDENCY', 'NodeVM omitted original dispatchPendingUI dependency. Supply the existing fake dependency; late real production render must still preserve the Case freeze.')
    if window == 'fourth-extra-probes':
        if 'resource_release' in identity:
            return ('INDEPENDENT_ORACLE_ERROR', 'Independent group-release assertion expected CANCELLED; actual original API correctly persisted RELEASED. Correct only the oracle and retain current resource rights and Case recovery requirements.')
        if '[future_handle]' in identity:
            return ('INDEPENDENT_TIMING_ORACLE_ERROR', 'A1ms future deadline was consumed by Date.now before the production boundary; unresolved fake fetch exited with empty stdout. Use a deterministic future bound; preserve original log and same-ID recheck.')
    if window == 'fourth-cold-hydrate-failure':
        return ('ACTUAL_PRODUCT_DEFECT_OFFLINE_NODEVM', 'Cold opaque UNKNOWN recovery handle failed to stop all business form submit events. Hydrate before reads and capture both click and submit with explicit write selectors; reads and independent release remain available.')
    if window == 'fourth-prefix-projection':
        return ('ACTUAL_PRODUCT_DEFECT_OWNED_PG', 'Valid prior REVALIDATE events were accepted despite a divergent current local state/snapshot/SHA. Require exact latest READY projection and original verified snapshot/hash before REQUEST_CANCEL.')
    if window == 'fourth-rehashed-initial':
        return ('ACTUAL_PRODUCT_DEFECT_OWNED_PG', 'Self-consistent rehashed first request claimed an unearned cycle or initial Case state. Derive cycle1 and NEEDS_INPUT/WAITING_CONFIRMATION from the complete original local prefix and compare the full original snapshot.')
    if window == 'fifth-cross-case-capture':
        return ('ACTUAL_PRODUCT_DEFECT_OFFLINE_NODEVM', 'Capture used unrelated prep Case for some existing plan/delivery/approval actions and unrelated receipt view for CREATE. Bind each action to its authorized own Case projection; legacy CREATE uses its current preparation. Same-ID probes require allowing other Case and blocking this Case.')
    raise AssertionError('Unclassified actual failure: '+window+' '+identity)


def main():
    final = json.loads((PRIVATE/'full-final-run.json').read_text())
    assert final['exit_code']==0 and not final['source_drift'] and not final['prior_test_ids_missing']
    root_pass = cases(PRIVATE/'full-final.xml')
    independent_path = PRIVATE/'independent-review/sixth-complete-backend-ui-and-probes.xml'
    independent_pass = cases(independent_path)
    archive = json.loads((OUTPUT/'archive-manifest.json').read_text())
    exports = {x['original_local_path']:x['exported_path'] for x in archive['artifacts']}
    entries = []
    for path in sorted(ROOT/p for p in exports if p.endswith('.xml')):
        independent = 'independent-review' in path.parts
        passed = independent_pass if independent else root_pass
        pass_path = independent_path if independent else PRIVATE/'full-final.xml'
        for x in ET.parse(path).iter('testcase'):
            error = x.find('failure')
            status = 'FAIL'
            if error is None:
                error = x.find('error'); status = 'ERROR'
            if error is None:continue
            identity = x.attrib['classname']+'::'+x.attrib['name']
            assert passed.get(identity)=='PASS',(path,identity,passed.get(identity))
            grade, reason = explanation(path.stem,identity)
            entries.append(dict(test_id=identity,original_status=status,original_window=path.stem,
                original_sanitized_junit=exports[str(path.relative_to(ROOT))],
                original_exception_type=error.attrib.get('type'),evidence_grade=grade,
                diagnosis_and_correction=reason,repaired_same_id_status='PASS',
                repaired_window=exports[str(pass_path.relative_to(ROOT))],final_source_sha=final['source_sha'],
                repaired_window_source_manifest_sha256=(json.loads(independent_path.with_name(independent_path.stem+'-run.json').read_text())['source_manifest_sha256'] if independent else final['source_manifest_sha256'])))
    result = dict(format='ACTUAL_FAILED_ID_TO_SEPARATE_RECHECK',old_results_rewritten=False,
        independent_repair_binding='Actual sixth226 e103cb window; final cb47 differs only in ten old schema test files, statically reviewed. Not a fresh226 run on final source.',
        failed_occurrences=len(entries),unique_failed_ids=len({x['test_id'] for x in entries}),entries=entries,
        standalone_node_failure='Original independent unknown-handle-capture exit1 is separate from JUnit; its original and recheck records are archived without inventing a testcase ID.',
        historical_case_count_zero_root_cause='UNCONFIRMED; no old worker stdout or Run/operation state can be recovered by this slice.')
    (OUTPUT/'failure-map.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='entries'}))


if __name__=='__main__':main()
