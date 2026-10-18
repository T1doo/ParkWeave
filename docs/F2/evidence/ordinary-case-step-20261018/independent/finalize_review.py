"""Pure reconciliation/publication inventory only; no project imports/tests."""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
base=Path(__file__).resolve().parent
root=Path('/workspace/ParkWeave')
source='954825efb66d16f7e41087e1c108b45042732703'
windows=[base/'frozen-954825ef-window1',base/'frozen-954825ef-window2']
parent=root/'.runtime/ordinary-case-step-20261018/frozen-954825ef'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def verify(path):
    collected=load(path/'collection.json')
    names=[x['nodeid'] if isinstance(x,dict) else x for x in collected]
    assert len(names)==len(set(names))
    reports=[json.loads(s) for s in (path/'calls.jsonl').read_text().splitlines()]
    xml=ET.parse(path/'results.xml').getroot()
    junit=[x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in xml.iter('testcase')]
    assert len(junit)==len(names) and set(junit)==set(names)
    phases={phase:{result:sum(r['when']==phase and r['outcome']==result for r in reports) for result in ('passed','failed','skipped')} for phase in ('setup','call','teardown')}
    for phase in phases:
        ids=[r['nodeid'] for r in reports if r['when']==phase]
        assert len(ids)==len(names) and set(ids)==set(names)
    return dict(nodeids=sorted(names),collection=len(names),phases=phases,JUnit=[x.attrib for x in xml.iter('testsuite')],exact_collection_phase_JUnit_nodeids=True),reports

summaries=[];all_pass=set();all_collected=set();failure_node=None
for index,path in enumerate(windows,1):
    counts,reports=verify(path);controller=load(path/'controller-result.json');runtime=load(path/'pytest-result.json')
    assert controller['source_sha']==controller['actual_HEAD_at_start']==controller['actual_HEAD_at_end']==source
    assert controller['frozen_input_count']==798
    assert all(controller[k]==[] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
    origins=load(path/'module-origins.json')
    assert all(x['matches_frozen'] or x['matches_independent_probe'] for x in origins)
    before=load(path/'independent-source-before.json')
    probe_name='test_independent_ordinary_case_step.py'
    mirror_probe=path/'mirror/tests'/probe_name
    proof=dict(private_original_sha256_at_window_pre=before[probe_name],mirror_PRE_sha256_from_exact_copy=before[probe_name],mirror_POST_sha256=sha(mirror_probe),equal=before[probe_name]==sha(mirror_probe))
    assert proof['equal'];write(path/'independent-probe-mirror-hash.json',proof)
    passed={r['nodeid'] for r in reports if r['when']=='call' and r['outcome']=='passed'}
    failed=[r for r in reports if r['outcome']=='failed']
    if index==1:
        assert len(passed)==8 and len(failed)==1 and failed[0]['when']=='call'
        failure_node=failed[0]['nodeid']
    else:
        assert len(passed)==1 and not failed and passed=={failure_node}
    all_pass|=passed;all_collected|=set(counts['nodeids'])
    summaries.append(dict(path=path.name,counts=counts,controller=controller,
      pytest_main_seconds=runtime['pytest_main_seconds'],
      origins=dict(total=len(origins),frozen=sum(x['matches_frozen'] for x in origins),private_probe=sum(x['matches_independent_probe'] for x in origins),unexpected=0),
      probe_hash=proof,fixture_names=runtime['fixture_names'],owned_pg=load(path/'owned-pg-after-exit.json'),
      failed_nodeids=[r['nodeid'] for r in failed],
      classification='8PASS_1_PRIVATE_PROBE_TIMING_FAILURE' if index==1 else 'ONE_SELECTOR_SUPPLEMENT_PASS'))
assert len(all_pass)==len(all_collected)==9
assert summaries[0]['probe_hash']['mirror_POST_sha256']==sha(base/'test_independent_ordinary_case_step.v1.py')
assert summaries[1]['probe_hash']['mirror_POST_sha256']==sha(base/'test_independent_ordinary_case_step.py')
pcounts,preports=verify(parent)
presult=load(parent/'result.json');assert presult['head']==source and presult['exit_code']==0 and presult['inputs']==798
assert len(pcounts['nodeids'])==48 and all(r['outcome']=='passed' for r in preports)
assert presult['shared_drift']==presult['mirror_drift']==[]
root_names=set(pcounts['nodeids']);intersection=all_pass&root_names
assert len(intersection)==3 and len(all_pass-root_names)==6 and len(all_pass|root_names)==54
# Independently compare the root recorded module hashes to this review's frozen input hashes.
root_origins=load(parent/'module-origins.json');frozen=load(windows[0]/'mirror-before.json');root_mirror=Path(presult['mirror'])
origin_checks=[]
for name,item in root_origins.items():
    path=Path(item['path']);relative=str(path.relative_to(root_mirror))
    origin_checks.append(dict(module=name,relative=relative,matches_frozen=frozen.get(relative)==item['sha256']))
assert all(x['matches_frozen'] for x in origin_checks)
write(base/'root-evidence-cross-check.json',dict(source_sha=source,executed_by_independent_reviewer=False,counts=pcounts,
  origins=origin_checks,root_module_count=len(origin_checks),parent_overlap=sorted(intersection),combined_unique_PASS=54,
  raw_reference_sha256={p:sha(parent/p) for p in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json') if (parent/p).exists()}))
html=[]
for path in sorted((windows[0]/'original-process-evidence').rglob('html.stdout')):
    rows=[]
    for line in path.read_text().splitlines():
        try:rows.append(json.loads(line))
        except json.JSONDecodeError:pass
    if rows:
        x=rows[-1];html.append(dict(path=str(path.relative_to(base)),phase=x.get('phase'),keys=sorted(x),actual_HTTP_calls=len(x.get('calls',[])),real_browser=False))
report=dict(scope='INDEPENDENT_LIMITED_ORDINARY_CASE_STEP_REVIEW',source_sha=source,
 baseline_sha='7b98f454bee96947f2bc1c824a2b50c10939e77a',
 conclusion='LIMITED_PASS_EXISTING_CURRENT_PREPARATION_ORDINARY_CONFIGURED_APP_AND_ORIGINAL_WORKER',
 open_P1=[],open_P2=[],independent_windows=summaries,
 independent_effective_unique_PASS=9,independent_new_unique_PASS=6,actual_parent_overlap_nodeids=sorted(intersection),
 parent_frozen_evidence=dict(path=str(parent.relative_to(root)),counts=pcounts,recorded_origins_verified=len(origin_checks),executed_by_independent_reviewer=False),
 effective_combined_unique_PASS=54,
 count_policy='First independent window:9 collection,9 setupPASS,8 callPASS/1 private timing-design FAIL,9 teardownPASS. Only the failing node rerun:1 collection/setup/call/teardown/JUnit PASS. Effective unique PASS union9=6 new independent probes+3 root overlaps; never described as a single9PASS window. Root48 separate current-SHA execution, intersection3, union54. Previous69/129 neither rerun nor transferred.',
 initial_failure_attribution='probe-revision-attribution.json',private_probe_exact_diff='probe-v1-v2.diff',
 source_and_oracle_sha256={name:sha(base/name) for name in ('literal-oracle-plan.json','contract-observed.md','static-review-01.json','test_independent_ordinary_case_step.v1.py','test_independent_ordinary_case_step.py','run_frozen_review.py','execute_review.py')},
 input_boundary=dict(frozen_Git_inputs_per_window=798,private_probe_inputs=1,private_probe_not_in_798=True,
   shared_mirror_PREPOST_drift=0,private_sources_and_copied_probe_PREPOST_drift=0,
   root_and_independent_archive_sha256=presult['archive_sha256'],equal_archive=presult['archive_sha256']==summaries[0]['controller']['archive_sha256']==summaries[1]['controller']['archive_sha256']),
 static_findings_verified_resolved=[dict(id='STATIC-P2-01',result='Ordinary full-page DECLINE exact terminal branch passed from original list navigation without forbidden follow-up GET; old strict offer/event/actor/revision checks retained.'),dict(id='STATIC-UI-02',result='Frozen page distinguishes ordinary and isolated limited-step language and preserves no-Run-access/SYNTHETIC limits; no implementation labels added to business scope.')],
 independently_verified=[
  'Different existing enterprises, reviewers and executors concurrently offer/accept via a single cold ordinary API; exact Case/Run/preparation and accept-recovery coordinates stay separate, cross-domain reads and swapped Case recovery deny.',
  'Owner history and separate notice OPEN/MARK_READ remain available without current EXECUTE, while ACK denies. Responsible reviewer can withdraw accepted work after executor READ revocation and material revision change; original receipt remains historical.',
  'After executor READ revoke/restore generation ABA, two fresh original worker processes suppress only executor intent, deliver owner history once, preserve the original deadline and do not create business or authority rows.',
  'Catalogue name restored to identical content with a new xmin remains changed across a cold ordinary API; executor read/ACCEPT deny and owner minimum history/WITHDRAW remain possible; reoffer conflicts.',
  'An ordinary marker with boolean preparation_revision fails strict proof in a fresh worker/API; both original outbox intents remain PENDING and no inbox is delivered or suppressed.',
  'Only initial bounded test deadline injected; actual cold API reads it unchanged. Actual PG notice-row lock wait crosses persisted deadline, MARK_READ returns403 and read_at rolls back while owner history still exposes the same original deadline.',
  'Three actual root-overlap nodes separately pass: normal receipt/notices without Run grant; original full HTML with three ordinary API/worker process restarts retaining UUID/deadline/read receipt; ordinary DECLINE clears terminal view without forbidden GET.'
 ],actual_full_HTML=html,
 authority_and_fixture_boundary='No CaseStep issuer, new identity/Grant/assignment/policy/approval/credential or installer in the independent probes. Original fixture bootstraps existing synthetic principals/grants/catalogue. Six private probes reuse original preparation helper Run creation plus original Store.finish local execution (no authority mutation), then original HTTP business operations; selected complete-page overlap independently uses original worker for Run completion. Owner SQL mutations in private probes are labeled negative permission/source/proof controls only; no positive runtime authority editing. Seven authority tables compared unchanged around authorized actions and after the explicitly labeled negative control.',
 process_boundary='Actual ordinary configured_app uvicorn child processes and original worker --once processes, restricted app Store DSN. Main pytest loaded project/test/helper module origins and hashes recorded; child commands point to the frozen mirror source via original minimal_environment. Origin inventory is the instrumented pytest process, not a claim of a separate import audit inside each child.',
 timing_boundary='Initial3s private timing probe failed before lock setup after3.541s, at the contract-correct filtered empty inbox; preserved as test-design failure. Supplement sets an original15s bounded test deadline, proves cold OPEN is live, then waits near that same original deadline before actual PG lock. No renewal or physical COMMIT-instant atomic-expiry claim.',
 delivery_boundary='Lane predicates only route before LIMIT and never grant authority. Unknown/damaged own proof remains pending; bounded consume False is not exhaustion. Fresh current source/recipient and original proof remain required.',
 remaining_limits=[
  'Normal explicit CURRENT_PREPARATION serves existing legal LOCAL SYNTHETIC preparation only; missing PREPARE/REVIEW_ASSIGNED/catalogue and unchanged Native/Run-assignment guards still deny. No real source substitute or new rights.',
  'Formal source reader/verifier concrete trusted inputs, Native permit/writer installation, real authority initialization and independent approval remain outside this slice and unresolved without their required actual inputs.',
  'No real browser, Windows, formal AT35, whole Case/P1-P5 completion, real external business/approval, real model, external messages, deployment, main/force push, fees or root/seal retry.',
  'Owned original helpers stop their own uvicorn children; normal SIGTERM child exit(-15) is lifecycle evidence, not exit0. PG post-exit Z/data absent is recorded without claiming reaped. No unknown process/lock manipulation.'
 ],
 raw_evidence_manifest='raw-evidence-manifest.json',publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json')
write(base/'independent-final-review.json',report)
(base/'active-review-path.txt').write_text(str(base)+'\n')
selected=[base/name for name in ('literal-oracle-plan.json','literal-oracle-plan.sha256','contract-observed.md','static-review-01.json',
 'test_independent_ordinary_case_step.v1.py','test_independent_ordinary_case_step.py','probe-v1-v2.diff','probe-revision-attribution.json',
 'run_frozen_review.py','execute_review.py','finalize_review.py','independent-final-review.json','active-review-path.txt','root-evidence-cross-check.json',
 'window1-controller.stdout','window1-controller.stderr','window2-controller.stdout','window2-controller.stderr')]
for path in windows:
    selected.extend(p for p in path.iterdir() if p.is_file() and '.private.' not in p.name)
    for sub in ('scenarios','root-overlap-evidence','original-process-evidence'):
        if (path/sub).exists():selected.extend(p for p in (path/sub).rglob('*') if p.is_file())
tokens=set()
for path in windows:tokens.update(load(path/'fixture-token-values.private.json'))
# Exact fixture values,12-character prefixes, and narrowly located truncated
# fixture-a value in pytest's safe repr are replaced only in public shadows.
files=[];mapping=[];total=0
for path in sorted(set(selected)):
    rel=str(path.relative_to(base));raw=path.read_bytes();public=raw;count=0
    for token in sorted(tokens,key=len,reverse=True):
        for fragment in (token,token[:12]):
            if fragment.encode() in public:
                count+=public.count(fragment.encode());public=public.replace(fragment.encode(),b'<REDACTED_SYNTHETIC_FIXTURE_SESSION>')
    # Pytest cuts the middle of a fixture tuple, including the first token value.
    pattern=rb"('fixture-a': ')([^'\n]*\.\.\.[^'\n]*)(')"
    public,n=re.subn(pattern,rb'\1<REDACTED_TRUNCATED_FIXTURE_VALUE>\3',public);count+=n
    if public!=raw:
        destination=base/'public'/rel;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():assert destination.read_bytes()==public,'canonical shadow must never be rewritten differently'
        else:destination.write_bytes(public)
        pub=str(destination.relative_to(base));files.append(destination)
    else:pub=rel;files.append(path)
    mapping.append(dict(raw=rel,public=pub,raw_sha256=sha(path),public_sha256=hashlib.sha256(public).hexdigest(),replacement_count=count))
    total+=count
write(base/'raw-public-redaction-map.json',dict(schema=1,files=mapping,replacements_total=total,
 captured_fixture_token_values=len(tokens),policy='All raw originals retained privately. Canonical public shadows replace only exact synthetic fixture-session values/prefixes and the narrowly located truncated fixture value in failure repr; nodeids, assertions and outcomes unchanged. No second redaction of canonical shadows. Private token inventories/config/mirror/PGdata excluded.'))
files.extend(base/name for name in ('raw-public-redaction-map.json','publication-files.json','raw-evidence-manifest.json'))
publication=sorted(str(p.relative_to(base)) for p in set(files));assert len(publication)==len(set(publication))
write(base/'publication-files.json',publication)
write(base/'raw-evidence-manifest.json',dict(schema=1,source_sha=source,self_hash_excluded_to_avoid_recursion=True,
 excludes=['mirror','PGdata','private tokens','private config','*.private.json','token-bearing raw files replaced by listed canonical shadows'],
 files=[dict(path=p,sha256=sha(base/p),bytes=(base/p).stat().st_size) for p in publication if p!='raw-evidence-manifest.json']))
for rel in publication:
    raw=(base/rel).read_bytes();assert not any(t.encode() in raw or t[:12].encode() in raw for t in tokens),rel
assert len(publication)==len(set(publication))
print(json.dumps(dict(report_sha256=sha(base/'independent-final-review.json'),publication_files=len(publication),
 publication_sha256=sha(base/'publication-files.json'),map_sha256=sha(base/'raw-public-redaction-map.json'),
 manifest_sha256=sha(base/'raw-evidence-manifest.json'),independent_effective_unique_PASS=9,own=6,root_overlap=3,
 root_unique_PASS=48,combined_unique_PASS=54,public_replacement_count=total),sort_keys=True))
