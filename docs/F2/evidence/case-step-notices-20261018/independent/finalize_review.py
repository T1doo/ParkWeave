"""Pure evidence reconciliation, no project imports or tests."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

base = Path(__file__).resolve().parent
root = Path('/workspace/ParkWeave')
historical = base / 'frozen-928be187-window1'
window = base / 'frozen-1da2e6c2-window2'
parent_historical = root / '.runtime/case-step-notices-20261018/frozen-928be187'
parent = root / '.runtime/case-step-notices-20261018/frozen-1da2e6c2'
source = '1da2e6c28024e3d7f518a2b8d62ce271c5ddb749'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text())
write = lambda p, x: p.write_text(json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def exact_nodeids(path):
    collection = load(path / 'collection.json')
    names = [x['nodeid'] if isinstance(x, dict) else x for x in collection]
    assert len(names) == len(set(names))
    return set(names)


def verify_window(path, allow_failure=False):
    names = exact_nodeids(path)
    calls = [json.loads(x) for x in (path / 'calls.jsonl').read_text().splitlines()]
    xml = ET.parse(path / 'results.xml').getroot()
    tests = list(xml.iter('testcase'))
    junit = [x.attrib['classname'].replace('.', '/') + '.py::' + x.attrib['name'] for x in tests]
    assert len(junit) == len(names) and set(junit) == names
    phases = {phase: {outcome: sum(x['when'] == phase and x['outcome'] == outcome for x in calls)
                       for outcome in ('passed', 'failed', 'skipped')} for phase in ('setup', 'call', 'teardown')}
    for phase in ('setup', 'call', 'teardown'):
        selected = [x['nodeid'] for x in calls if x['when'] == phase]
        assert len(selected) == len(names) and set(selected) == names
        if not allow_failure:assert phases[phase]['failed'] == phases[phase]['skipped'] == 0
    return dict(collection=len(names), nodeids=sorted(names), phase_counts=phases,
                JUnit=[x.attrib for x in xml.iter('testsuite')],
                failed_reports=[x for x in calls if x['outcome']=='failed'],
                collection_setup_call_teardown_JUnit_exact=True)


controller = load(window / 'controller-result.json')
runtime = load(window / 'pytest-result.json')
verified = verify_window(window)
assert controller['source_sha'] == source and controller['exit_code'] == 0
assert controller['frozen_input_count'] == 792 and verified['collection'] == 9
assert controller['actual_HEAD_at_start'] == controller['actual_HEAD_at_end'] == source
for key in ('shared_drift', 'mirror_drift', 'shared_mirror_mismatch', 'independent_source_drift'):
    assert controller[key] == []
origins = load(window / 'module-origins.json')
assert all(x['matches_frozen'] or x['matches_independent_probe'] for x in origins)
for path in (historical,window):
    before=load(path/'independent-source-before.json')
    name='test_independent_case_step_notice_probes.py'
    mirrored=path/'mirror/tests'/name
    write(path/'independent-probe-mirror-hash.json',dict(path='tests/'+name,
        private_original_sha256_at_window_pre=before[name],
        mirror_PRE_sha256_from_exact_copy=before[name],mirror_POST_sha256=sha(mirrored),
        frozen_git_inputs=792,independent_probe_inputs=1,equal=before[name]==sha(mirrored)))
probe = load(window / 'independent-probe-mirror-hash.json')
assert probe['equal']
own = set(verified['nodeids'])
root_nodes = exact_nodeids(parent)
intersection = own & root_nodes
assert len(own) == 9 and len(intersection) == 3 and len(own-root_nodes) == 6
root_summary = dict(path=str(parent.relative_to(root)), collected=len(root_nodes),
                    executed_by_independent_reviewer=False,
                    collection_sha256=sha(parent/'collection.json'))
if (parent/'result.json').exists():
    result = load(parent/'result.json')
    assert result['head'] == source and result['exit_code'] == 0
    root_summary.update(status='ROOT_COMPLETED_REFERENCE_READ_ONLY',
                        verified=verify_window(parent),
                        raw_evidence_sha256={name:sha(parent/name) for name in ('result.json','collection.json','calls.jsonl','results.xml')})
    combined = len(own | root_nodes)
else:
    root_summary.update(status='ROOT_EXECUTION_PENDING_AT_INDEPENDENT_FINALIZATION')
    combined = None
html=[]
for path in sorted((window/'html').glob('*.jsonl')):
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    item=rows[-1]
    html.append(dict(path=str(path.relative_to(base)), flow=item['flow'], checks=item['checks'],
                     actual_HTTP_calls=len(item['calls']),
                     POST_calls=sum(x['method']=='POST' for x in item['calls']), real_browser=False))
report = dict(
    scope='INDEPENDENT_LIMITED_CASE_STEP_NOTICE_REVIEW', source_sha=source,
    baseline_sha='06186eef397a26bcf8ed8b6b3f07d6b1e9aa5cc5',
    conclusion='LIMITED_PASS_WITHIN_EXPLICIT_OWNED_SYNTHETIC_DI_CONTRACT',
    open_P1=[], open_P2=[], independent_windows=[dict(path=historical.name,
        role='HISTORICAL_928_NOT_TRANSFERRED_TO_FINAL_SHA',verified=verify_window(historical),
        controller=load(historical/'controller-result.json'),
        pytest_main_seconds=load(historical/'pytest-result.json')['pytest_main_seconds'],
        origins=dict(total=len(load(historical/'module-origins.json')),
            frozen=sum(x['matches_frozen'] for x in load(historical/'module-origins.json')),
            independent=sum(x['matches_independent_probe'] for x in load(historical/'module-origins.json'))),
        independent_probe_hash=load(historical/'independent-probe-mirror-hash.json'),
        owned_pg=load(historical/'owned-pg-after-exit.json')),dict(path=window.name,
        role='FINAL_SHA_CURRENT_EXECUTED_WINDOW',
        verified=verified, controller=controller, pytest_main_seconds=runtime['pytest_main_seconds'],
        origins=dict(total=len(origins), frozen=sum(x['matches_frozen'] for x in origins),
                     independent=sum(x['matches_independent_probe'] for x in origins), unexpected=0),
        independent_probe_hash=probe, fixture_names=runtime['fixture_names'],
        owned_pg=load(window/'owned-pg-after-exit.json'))],
    independent_effective_unique_PASS=9, independent_new_unique_PASS=6,
    actual_parent_overlap_nodeids=sorted(intersection),
    parent_frozen_evidence=root_summary,
    collection_union_with_parent=len(own|root_nodes),
    effective_combined_unique_PASS=combined,
    count_policy='Final1da independent9=6 new probes+3 original HTML overlaps. Historical928 independent9 and parent62PASS1FAIL retained, not accumulated or transferred. Parent final window is separate read-only evidence; combined PASS populated only after its completed phase/JUnit reconciliation. Old129 neither rerun nor transferred.',
    historical_parent_failed_window=dict(path=str(parent_historical.relative_to(root)),
        result=load(parent_historical/'result.json'),verified=verify_window(parent_historical,True),
        classification='62PASS1FAIL; sole old offline snippet harness missing real entryFailureFlows/failEntryFlow dependencies. Root reproduced same error on original06186 page with unchanged old harness. Not an identified CaseStep notice product P1/P2; old red retained.',
        raw_reference_sha256={name:sha(parent_historical/name) for name in ('result.json','collection.json','calls.jsonl','results.xml','stdout.txt','stderr.txt')}),
    harness_attribution='harness-attribution.json',
    independent_probe_sha256=sha(base/'test_independent_case_step_notice_probes.py'),
    oracle_sha256={name:sha(base/name) for name in ('literal-oracle-plan.json','literal-oracle-wip-supplement.json')},
    input_boundary=dict(frozen_Git_inputs=792, independent_probe_inputs=1,
        private_probe_not_in_792=True, shared_mirror_PREPOST_drift=0,
        private_original_and_copied_probe_PREPOST_drift=0),
    actual_HTML=html,
    static_findings_verified_resolved=[
        'Skipped/locked CaseA candidate callbacks discarded; controlled A deadline crossing does not roll back independent live CaseB delivery.',
        'False OFFER row at revision2 cannot borrow original revision1 marker; damaged candidate remains PENDING and normal proof delivers after fixture restoration.',
        'Before-LIMIT lane routing: SCAN_LIMIT1 foreign prefix does not starve later own work; default mode preserves all marker intents.'
    ],
    additional_verified_behaviors=[
        'Default consumer leaves markerless ACCEPT/WITHDRAW intent untouched; explicit consumer delivers proper lineage and suppresses terminal executor recipient only after original own proof.',
        'GET, OPEN and MARK_READ are separate; no MARK_READ before OPEN, duplicate timestamps unchanged; source event revision remains distinct from current dispatch revision.',
        'Notice responses omit original goal/material/dispatch reason. Default app does not inherit scoped inbox authority.',
        'Actual PG notice-row lock wait crosses first two-second offer deadline and rolls back executor MARK_READ; current owner minimal history remains accessible.',
        'Eleven actual HTTP-created/accepted synthetic Cases yield22 owner notices: 20+2 real pages, no duplicates/skips; same Navigation cursor cannot cross into default mode.',
        'Original full HTML NORMAL/LATE_OPEN/LATE_403 flows use actual prep-list/row/dispatch button and notice-list/card/OPEN/READ; late actual responses cannot restore old identity context.'
    ],
    authority_boundary='Six independent normal-business probes preserve original seven authority-table snapshot. Original fixture alone creates existing principals/grants before provider boot. Normal business uses original HTTP/worker; negative event corruption and exact owned outbox/inbox locks are fixture controls. No owner assign_status or new runtime identity/Grant/Run assignment/approval/credential in these probes.',
    timing_boundary='SKIP LOCKED cross-Case probe uses actual PG locks and separately labelled deterministic injected admission clock. Deadline MARK_READ probe uses actual PG lock wait and actual DB time. No physical COMMIT-instant atomic-expiry claim.',
    delivery_boundary='Queue lane SQL only routes candidates; it grants no authority and does not bound physical PostgreSQL scan work. consume False means bounded unit without progress, not queue exhaustion; damaged own proof remains PENDING for separately scheduled continuation.',
    remaining_limits=[
        'Explicit app-local original fresh-owned SYNTHETIC CaseStep provider only; configured_app and CLI do not issue/discover the provider; ordinary Run READ remains denied.',
        'No real cross-process persisted authority installation, real external notice/approval/business, Windows, real browser or formal AT35/whole P1-P5 completion claim.',
        'Formal reader/verifier concrete trusted source and Native installation gaps remain separate and unchanged.',
        'No additional DDL/roles/permissions beyond original fixture bootstrap; no real model, deployment/main/force push, native installer/root/seal retry, unknown process/lock manipulation.',
        'Owned PG ended naturally: post-exit state Z and owned data absent are recorded, not claimed reaped.'
    ],
    raw_evidence_manifest='raw-evidence-manifest.json', publication_list='publication-files.json',
    raw_public_map='raw-public-redaction-map.json')
write(base/'independent-final-review.json',report)
(base/'active-review-path.txt').write_text(str(base)+'\n')
files=[base/name for name in ('literal-oracle-plan.json','literal-oracle-plan.sha256',
    'literal-oracle-wip-supplement.json','literal-oracle-wip-supplement.sha256',
    'test_independent_case_step_notice_probes.py','execute_review.py','run_frozen_review.py',
    'finalize_review.py','independent-final-review.json','active-review-path.txt','harness-attribution.json')]
for path in (historical,window):
    files.extend(p for p in path.iterdir() if p.is_file() and '.private.' not in p.name)
    files.extend(p for p in (path/'html').iterdir() if p.is_file())
files=sorted(set(files));tokens=set(load(window/'fixture-token-values.private.json'))|set(load(historical/'fixture-token-values.private.json'));mapping=[]
for path in files:
    data=path.read_bytes()
    assert not any(t.encode() in data or t[:12].encode() in data for t in tokens), 'token occurrence in selected public evidence: '+str(path)
    rel=str(path.relative_to(base));mapping.append(dict(raw=rel,public=rel,raw_sha256=sha(path),public_sha256=sha(path),replacement_count=0))
write(base/'raw-public-redaction-map.json',dict(schema=1,
    policy='All selected raw retained byte-for-byte; captured fixture tokens and12-character prefixes scanned, no occurrences. No shadow or repeat redaction needed. Private token inventories/config/mirror/PG data excluded.',
    captured_fixture_token_values=len(tokens), replacements_total=0, files=mapping))
files.extend(base/name for name in ('raw-public-redaction-map.json','publication-files.json','raw-evidence-manifest.json'))
publication=sorted(str(p.relative_to(base)) for p in set(files))
write(base/'publication-files.json',publication)
write(base/'raw-evidence-manifest.json',dict(schema=1,source_sha=source,
    excludes=['mirror','pytest-temp','PGdata','private tokens','private config','*.private.json'],
    self_hash_excluded_to_avoid_recursion=True,
    files=[dict(path=p,sha256=sha(base/p),bytes=(base/p).stat().st_size) for p in publication if p!='raw-evidence-manifest.json']))
for rel in publication:
    data=(base/rel).read_bytes()
    assert not any(t.encode() in data or t[:12].encode() in data for t in tokens)
print(json.dumps(dict(report_sha256=sha(base/'independent-final-review.json'),
    publication_files=len(publication),publication_sha256=sha(base/'publication-files.json'),
    raw_manifest_sha256=sha(base/'raw-evidence-manifest.json'),
    map_sha256=sha(base/'raw-public-redaction-map.json'), independent_unique_PASS=9,
    parent_overlap=3, combined_unique_PASS=combined, root_status=root_summary['status'],
    token_replacements=0),sort_keys=True))
