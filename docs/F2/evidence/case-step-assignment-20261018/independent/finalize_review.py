"""Evidence-only reconciliation/publication; no project imports or test runs."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

base = Path(__file__).resolve().parent
root = Path('/workspace/ParkWeave')
source_sha = 'f6b76c5e030ffd7a055c7b4a3278bf911c05b4f1'
windows = ['frozen-f6b76c5e-window1', 'frozen-f6b76c5e-window2']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text())
write = lambda p, x: p.write_text(json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def reconcile(path, independent):
    controller = load(path / ('controller-result.json' if independent else 'result.json'))
    collection = load(path / 'collection.json')
    nodeids = [x['nodeid'] if isinstance(x, dict) else x for x in collection]
    calls = [json.loads(x) for x in (path / 'calls.jsonl').read_text().splitlines()]
    xml = ET.parse(path / 'results.xml').getroot()
    junit_ids = [x.attrib['classname'].replace('.', '/') + '.py::' + x.attrib['name'] for x in xml.iter('testcase')]
    assert len(nodeids) == len(set(nodeids))
    assert set(junit_ids) == set(nodeids) and len(junit_ids) == len(nodeids)
    for phase in ('setup', 'teardown'):
        assert {x['nodeid'] for x in calls if x['when'] == phase} == set(nodeids)
    passed = {x['nodeid'] for x in calls if x['when'] == 'call' and x['outcome'] == 'passed'}
    if controller['exit_code'] == 0:
        for phase in ('setup', 'call', 'teardown'):
            assert {x['nodeid'] for x in calls if x['when'] == phase and x['outcome'] == 'passed'} == set(nodeids)
    phases = {phase: {state: sum(x['when'] == phase and x['outcome'] == state for x in calls)
                      for state in ('passed', 'failed', 'skipped')} for phase in ('setup', 'call', 'teardown')}
    result = dict(collection=len(nodeids), collection_nodeids=nodeids,
                  phase_counts=phases, JUnit=[x.attrib for x in xml.iter('testsuite')],
                  collection_report_JUnit_nodeids_match=True, call_pass_nodeids=sorted(passed),
                  controller_result=controller)
    if independent:
        runtime = load(path / 'pytest-result.json')
        origins = load(path / 'module-origins.json')
        result.update(pytest_main_seconds=runtime['pytest_main_seconds'],
                      warnings=3 if controller['exit_code'] == 0 else 1,
                      fixture_names=runtime['fixture_names'],
                      origins=dict(total=len(origins), frozen=sum(x['matches_frozen'] for x in origins),
                                   private_probe=sum(x['matches_independent_probe'] for x in origins),
                                   unexpected=[x['name'] for x in origins if not x['matches_frozen'] and not x['matches_independent_probe']]),
                      owned_pg=load(path / 'owned-pg-after-exit.json'),
                      independent_probe_hash=load(path / 'independent-probe-mirror-hash.json'))
        assert not result['origins']['unexpected']
        for key in ('shared_drift', 'mirror_drift', 'shared_mirror_mismatch', 'independent_source_drift'):
            assert controller[key] == []
    return result


results = {name: reconcile(base / name, True) for name in windows}
root_path = root / '.runtime/case-step-assignment-20261018/frozen-f6b76c5e'
root_result = reconcile(root_path, False)
own_pass = set(results[windows[1]]['call_pass_nodeids'])
root_pass = set(root_result['call_pass_nodeids'])
assert len(own_pass) == 8 and len(root_pass) == 124
assert len(own_pass & root_pass) == 3 and len(own_pass | root_pass) == 129
assert results[windows[0]]['phase_counts']['setup']['failed'] == 8
assert results[windows[0]]['phase_counts']['call'] == {'passed': 0, 'failed': 0, 'skipped': 0}

html = []
for path in sorted((base / windows[1] / 'html').glob('*.jsonl')):
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    item = rows[-1]
    html.append(dict(path=str(path.relative_to(base)), flow=item.get('flow', 'ACK'),
                     assertions=item['checks'], actual_HTTP_calls=len(item['calls']),
                     explicit_POST_calls=sum(x['method'] == 'POST' for x in item['calls']),
                     real_browser=False))

report = dict(
    scope='INDEPENDENT_LIMITED_SYNTHETIC_CASE_ASSIGN_REVIEW', source_sha=source_sha,
    conclusion='LIMITED_PASS_WITHIN_EXPLICIT_OWNED_SYNTHETIC_DI_CONTRACT',
    open_product_P1=[], open_product_P2=[],
    independent_execution_windows=results,
    first_window_classification='8 fixture setup ERROR / 0 call; controller basetemp outside system /tmp accurately denied original owned-cluster proof. Not business FAIL; original fixture/proof unchanged. Raw retained.',
    correction='Only private controller basetemp changed to new owned /tmp path. Original controller 55ed5d224eea3709892e5b220d5a48ada622646f66e4b45a202e5f48ab6c44aa preserved; corrected controller 47d2236baa9f4211fb5a6c56d8deb6f16f174319e4fd4358b763fdcd44b5546e. Same private probe bytes in both windows.',
    actual_independent_effective_unique_PASS=8, independent_new_unique_PASS=5,
    actual_root_overlap_nodeids=sorted(own_pass & root_pass),
    root_frozen_evidence_read_only_reference=dict(path=str(root_path.relative_to(root)),
        unique_PASS=124, new_case_step_selectors=33, original_dispatch_selectors=53,
        original_receipt_selectors=38, source_sha=root_result['controller_result']['head'],
        collection_setup_call_teardown_JUnit_match=True,
        evidence_sha256={name:sha(root_path/name) for name in ('result.json','collection.json','calls.jsonl','results.xml')},
        executed_by_independent_reviewer=False),
    effective_root_plus_independent_unique_PASS=129,
    effective_PASS_count_derivation='Root124 + independent8 - actual HTML intersection3 =129. No initial setup ERROR counted as business failure or passed call; not a single independent129 or single-window16.',
    static_findings_resolved_at_source_freeze=[
        'DECLINE terminal response no longer rechecks a forbidden terminal executor GET inside transaction.',
        'Original page verifies exact DECLINE terminal response then clears private current view without automatic forbidden GET.',
        'Existing-root specialist catalog no longer requires revoked target/old source current authority before WITHDRAW.',
        'WITHDRAW clears required current offer receipt pointer while strict original ACCEPT/CREATE proof preserves owner historical list/GET.',
        'Strict original OFFER prefix and typed marker generations/hash/version validation; canonical current binding equality.',
        'Unknown acceptance key still requires original OFFER revision; committed recovery verifies original ACCEPT/CREATE and SUBMIT body/hash/version; malformed UUID/payload refused.'
    ],
    independent_probe_sha256=sha(base/'test_independent_case_step_probes.py'),
    selected_input_boundary=dict(frozen_git_inputs_each_window=789, independent_probe_input=1,
        frozen_git_inputs_do_not_include_private_probe=True, shared_mirror_PREPOST_drift=0,
        private_probe_source_and_mirror_drift=0, HEAD_before_and_after_each_window=source_sha),
    actual_full_HTML=html,
    runtime_authority_boundary='Five independent normal-business probes preserve original authority snapshot; normal new Run/manual material REVIEW/CONFIRM/OFFER/ACCEPT/SUBMIT/ACK/correction use original HTTP/worker. Existing original fixture creates identities/grants before explicit provider boot only. HTML WITHDRAW_REVOKED is a separately counted owned negative revocation, not new assignment/grant or a normal-user authority-write claim.',
    runtime_side_effect_boundary='No browser, real model, deployment, main/force push, additional DDL/roles/permission changes beyond original owned fixture bootstrap, real credentials, native installer/root/seal retry or unknown process/lock manipulation. Negative artifact corruption and owned exact parent lock are private fixture controls. Owned PG ended naturally; actual post-exit state Z and data directory absent are recorded, not claimed reaped.',
    remaining_limits=[
        'Explicit app-local fresh-owned SYNTHETIC provider only; configured_app remains default closed; ordinary executor Run access and marker interpretation via default app remain denied.',
        'Not a real durable cross-process authority installation, real business approval, Windows/browser/formal AT35 or P1-P5 completion.',
        'Formal reader/verifier/approval-provider concrete authorized source contracts and original Native installation gaps remain separate; this slice supplies none.',
        'Fixed first-offer deadline is last post-wait admission check, not physical COMMIT instant atomic expiry.',
        'Initial fixture setup rejection is retained and only safely corrected controller configuration was retried once.'
    ],
    raw_evidence_manifest='raw-evidence-manifest.json', publication_list='publication-files.json',
    redaction_map='raw-public-redaction-map.json',
)
write(base/'independent-final-review.json', report)
(base/'active-review-path.txt').write_text(str(base)+'\n')

files = [base/p for p in ('literal-oracle-plan.json','literal-oracle-plan.sha256',
    'literal-oracle-accepted-choices-wip-supplement.json','literal-oracle-accepted-choices-wip-supplement.sha256',
    'test_independent_case_step_probes.py','execute_review.py','run_frozen_review.py',
    'finalize_review.py','independent-final-review.json','active-review-path.txt')]
for name in windows:
    path=base/name
    files.extend(p for p in path.iterdir() if p.is_file() and '.private.' not in p.name)
    if (path/'html').exists():files.extend(p for p in (path/'html').iterdir() if p.is_file())
files=sorted(set(files))
tokens=set()
for name in windows:tokens.update(load(base/name/'fixture-token-values.private.json'))
mapping=[]
for path in files:
    data=path.read_bytes()
    full=sum(data.count(v.encode()) for v in tokens)
    prefixes=sum(data.count(v[:12].encode()) for v in tokens)
    assert full==prefixes==0, 'fixture token or 12-character token prefix in proposed public evidence: '+str(path)
    relative=str(path.relative_to(base))
    mapping.append(dict(private_original_relative_raw_path=relative, relative_public_path=relative,
                        raw_sha256=sha(path), public_sha256=sha(path), replacement_count=0))
redaction=dict(schema=1, policy='Exact raw retained. No credential occurrence found in selected files against all captured fixture tokens and 12-character prefixes; no shadow needed and no raw file edited. Private token inventories, mirror, pytest temp/PG data and config are excluded.',
               known_fixture_token_values_count=len(tokens), selected_raw_files_scanned=len(files),
               replacements_total=0, files=mapping)
write(base/'raw-public-redaction-map.json',redaction)
files += [base/'raw-public-redaction-map.json',base/'raw-evidence-manifest.json',base/'publication-files.json']
publication=sorted(str(p.relative_to(base)) for p in set(files))
write(base/'publication-files.json',publication)
manifest=dict(schema=1, source_sha=source_sha,
              excludes=['mirror','pytest-temp','PGdata','*.private.json','private tokens','private config'],
              self_hash_excluded_to_avoid_recursion=True,
              files=[dict(path=p,sha256=sha(base/p),bytes=(base/p).stat().st_size)
                     for p in publication if p!='raw-evidence-manifest.json'])
write(base/'raw-evidence-manifest.json',manifest)
assert len(publication)==len(set(publication))
for relative in publication:
    p=base/relative
    assert p.is_file()
    data=p.read_bytes()
    assert not any(token.encode() in data or token[:12].encode() in data for token in tokens)
print(json.dumps(dict(report_sha256=sha(base/'independent-final-review.json'),
    publication_files=len(publication),publication_sha256=sha(base/'publication-files.json'),
    raw_manifest_sha256=sha(base/'raw-evidence-manifest.json'),
    redaction_map_sha256=sha(base/'raw-public-redaction-map.json'),
    effective_independent_unique_PASS=8,root_overlap=3,combined_unique_PASS=129,
    raw_token_replacements=0),sort_keys=True))
