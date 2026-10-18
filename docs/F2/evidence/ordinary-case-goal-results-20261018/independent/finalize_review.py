"""Pure reconciliation and XML-safe publication; never runs project tests."""
import argparse,copy,hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--sha',required=True);p.add_argument('--window',required=True);p.add_argument('--parent',required=True);args=p.parse_args()
base=Path(__file__).resolve().parent;root=Path('/workspace/ParkWeave')
historical=base/'frozen-163e1f79-window1';final=base/args.window;parent=root/args.parent;parent_old=root/'.runtime/ordinary-case-goal-results-20261018/frozen-163e1f79'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
def write(p,v):
    with p.open('x') as f:f.write(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def verify(path):
    collected=load(path/'collection.json');ids=[i['nodeid'] if isinstance(i,dict) else i for i in collected]
    assert len(ids)==len(set(ids))
    calls=[json.loads(s) for s in (path/'calls.jsonl').read_text().splitlines()]
    xml=ET.parse(path/'results.xml').getroot();cases=list(xml.iter('testcase'))
    jid=[x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in cases]
    assert len(jid)==len(ids) and set(jid)==set(ids)
    phases={phase:{outcome:sum(r['when']==phase and r['outcome']==outcome for r in calls) for outcome in ('passed','failed','skipped')} for phase in ('setup','call','teardown')}
    for phase in phases:
        names=[r['nodeid'] for r in calls if r['when']==phase];assert len(names)==len(ids) and set(names)==set(ids)
    return dict(collection=len(ids),nodeids=sorted(ids),phases=phases,JUnit=[n.attrib for n in xml.iter('testsuite')],exact_collection_phases_JUnit_nodeids=True),calls
windows=[]
for path,source,expected_fails in ((historical,'163e1f7926e50f273c6490d9f2e8f7fbfc90e5a8',3),(final,args.sha,0)):
    counts,calls=verify(path);control=load(path/'controller-result.json');runtime=load(path/'pytest-result.json');origins=load(path/'module-origins.json')
    assert control['source_sha']==control['actual_HEAD_at_start']==control['actual_HEAD_at_end']==source
    assert control['frozen_input_count']==803 and counts['collection']==8
    assert all(control[k]==[] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
    assert counts['phases']['setup']['passed']==counts['phases']['teardown']['passed']==8
    assert counts['phases']['call']['failed']==expected_fails and counts['phases']['call']['passed']==8-expected_fails
    assert all(x['matches_frozen'] or x['matches_independent_probe'] for x in origins)
    original=load(path/'independent-source-before.json')['test_independent_ordinary_goal_results.py'];mirrored=path/'mirror/tests/test_independent_ordinary_goal_results.py'
    proof=dict(private_original_PRE_sha256=original,mirror_PRE_sha256_from_exact_copy=original,mirror_POST_sha256=sha(mirrored),equal=original==sha(mirrored));assert proof['equal']
    write(path/'independent-probe-mirror-hash.json',proof)
    windows.append(dict(path=path.name,source_sha=source,role='HISTORICAL_NOT_TRANSFERRED' if expected_fails else 'FINAL_SHA_EXECUTED',counts=counts,controller=control,
      pytest_main_seconds=runtime['pytest_main_seconds'],probe=proof,origins=dict(total=len(origins),frozen=sum(x['matches_frozen'] for x in origins),private_probe=sum(x['matches_independent_probe'] for x in origins),unexpected=0),
      fixture_names=runtime['fixture_names'],owned_pg=load(path/'owned-pg-after-exit.json'),failed_nodeids=[r['nodeid'] for r in calls if r['outcome']=='failed']))
assert windows[0]['probe']['mirror_POST_sha256']==sha(base/'test_independent_ordinary_goal_results.v1.py')
assert windows[1]['probe']['mirror_POST_sha256']==sha(base/'test_independent_ordinary_goal_results.py')
root_counts,root_calls=verify(parent);root_result=load(parent/'result.json')
assert root_result['head']==args.sha and root_result['exit_code']==0 and root_result['inputs']==803 and all(r['outcome']=='passed' for r in root_calls)
assert root_result['shared_drift']==root_result['mirror_drift']==[]
ours=set(windows[1]['counts']['nodeids']);theirs=set(root_counts['nodeids']);overlap=ours&theirs
assert len(ours)==8 and len(overlap)==3 and len(ours-theirs)==5
old_root_counts,old_root_calls=verify(parent_old);assert old_root_counts['collection']==32 and all(r['outcome']=='passed' for r in old_root_calls)
root_origins=load(parent/'module-origins.json');frozen=load(final/'mirror-before.json');mirror=Path(root_result['mirror'])
origin_checks=[dict(module=name,relative=str(Path(v['path']).relative_to(mirror)),matches_frozen=frozen.get(str(Path(v['path']).relative_to(mirror)))==v['sha256']) for name,v in root_origins.items()]
assert all(x['matches_frozen'] for x in origin_checks)
write(base/'root-evidence-cross-check.json',dict(source_sha=args.sha,counts=root_counts,origin_checks=origin_checks,actual_overlap=sorted(overlap),effective_combined_unique_PASS=len(ours|theirs),executed_by_independent_reviewer=False,
 references={name:sha(parent/name) for name in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json') if (parent/name).exists()}))
# Selected process evidence comes from original full HTML/API helper files.
html=[]
for file in sorted((final/'original-process-evidence').rglob('summary.json')):
    value=load(file);html.append(dict(path=str(file.relative_to(base)),assertions=value.get('assertions'),checks=value.get('checks'),state=value.get('state'),calls=len(value.get('calls',[])),real_browser=False))
report=dict(schema=1,scope='INDEPENDENT_LIMITED_ORDINARY_CASESTEP_P3_P4_GOAL_RESULTS_REVIEW',source_sha=args.sha,baseline_sha='5e657633ea9b132f994a7a5ed4e35e9556100a2d',
 conclusion='LIMITED_PASS_AFTER_P1_P2_CALLBACK_SCOPE_REPAIR',open_P1=[],open_P2=[],independent_windows=windows,
 independent_effective_unique_PASS=8,independent_new_unique_PASS=5,actual_root_overlap_nodeids=sorted(overlap),root_final_unique_PASS=root_counts['collection'],effective_combined_unique_PASS=len(ours|theirs),
 counting_policy='Only final source SHA counts: independent8=5 private probes+3 root overlaps; root final separate window and actual nodeid union. Historical163e independent5PASS/3FAIL retained:1 productP2 and2 private assertion errors. Historical root32PASS does not transfer to final SHA. Prior54 and earlier slices neither rerun nor counted.',
 historical_root=dict(path=str(parent_old.relative_to(root)),counts=old_root_counts,classification='32PASS_BUT_INDEPENDENT_COUNTEREXAMPLE_FOUND_PRODUCT_P2',executed_by_independent_reviewer=False,
 raw_sha256={name:sha(parent_old/name) for name in ('result.json','collection.json','calls.jsonl','results.xml') if (parent_old/name).exists()}),
 historical_failure_attribution='probe-revision-attribution.json',private_probe_exact_diff='probe-v1-v2.diff',scope_source_transition='scope-source-transition.json',nonblocking_display_note='preview-contract-wording-note.json',
 verified_P2_resolution='P1/P2-only adopted outputs stay LOCAL_OUTPUTS_VERIFIED across an actual final PG wait past an unrelated accepted offer deadline. Initial historical case late403/fresh200 with unchanged authority; final case200/fresh200. Ordinary P3/P4 final deadline guard remains active in overlapping real VERIFY lock-wait test.',
 separately_verified=[
  'Current manual correction creates a real second receipt version with original SUBMIT/REQUEST_CHANGES/SUBMIT/ACK history; exact actual v2 reference and source fingerprints survive a cold ordinary API process. Owner original request remains allowed; material/receipt bodies stay out of goal-results.',
  'A verified source hash without the exact original owner VERIFY actor/event cannot produce current P4 verification, including a cold process; no runtime authority is issued.',
  'Owner EXECUTE revocation preserves authorized minimal historical VERIFY references while current P3/P4 output and new VERIFY deny; executor Run read still403.',
  'Explicit normal DI is Store-bound. A fresh default Store does not infer ordinary authority from markers; P5 stays unverified and direct original lifecycle writes refuse. No lifecycle ledger or Run assignment created.',
  'Overlaps: full original ordered HTTP P1/P2/ordinary receipt/P3/P4 verification; real final VERIFY lock crossing original deadline rolls back; full original HTML in3 normal API processes VERIFY/generate/download/coldGET/revoked-source degradation.'
 ],
 source_oracle_sha256={name:sha(base/name) for name in ('literal-oracle-plan.json','contract-observed.md','test_independent_ordinary_goal_results.v1.py','test_independent_ordinary_goal_results.py','run_frozen_review.py','execute_review.py')},
 source_boundaries=dict(frozen_Git_inputs_per_window=803,private_probe_inputs=1,private_probe_separate_from_803=True,all_shared_mirror_PREPOST_drift=0,all_private_original_mirror_drift=0,root_and_final_independent_archive_equal=root_result['archive_sha256']==windows[1]['controller']['archive_sha256'],root_recorded_origins_verified=len(origin_checks),root_cross_check='root-evidence-cross-check.json'),
 actual_full_HTML=html,
 ordinary_runtime_inputs=[
  'Explicit CURRENT_PREPARATION on normal configured_app/worker with original preinstalled LOCAL schema32/33 and existing restricted application DSN/session; startup does not migrate/seed/repair.',
  'Existing same-domain enterprise owner READ/PREPARE and EXECUTE for writes plus original case.create action; exact responsible preparation reviewer READ/REVIEW_ASSIGNED; selected existing service_executor READ. Ordinary CaseStep does not need or issue Run assignment, and any surviving legacy/Native Run authority still refuses.',
  'Exact existing SYNTHETIC synthetic-material-preparation service version1 and current catalogue proof/source; legitimate successful original case.create Case/Run/VERIFIED operation; no old isolated or corrupt business marker.',
  'Current source-backed two-slot material records with original reviewer REVIEW and owner CONFIRM; explicit current request goals, original ADOPT and owner VERIFY decisions.',
  'For P2: existing owner resource READ/HOLD, current original rules/time/capacity, confirmed combination and Case claim/link; P3/P4 require original live300s offer/generations, actual executor ACCEPT/receipt and independent owner ACK.'
 ],
 missing_management_initialization=dict(status='NOT_IMPLEMENTED_OR_AUTHORIZED_BY_THIS_SLICE',evidence=[dict(path='src/parkweave/cli.py',lines=[13,24,34],finding='CLI provides migrate, enterprise-only seed-synthetic and revocation; no normal principal/Grant/preparation-catalogue management initialization path.'),dict(path='src/parkweave/preparation.py',lines=[368,380],finding='seed_synthetic is explicitly fixture-owner-only and supplies reviewer/PREPARE/REVIEW_ASSIGNED/catalogue in tests; it is not production initialization or normal approval.'),dict(path='README.md',lines=[130,134],finding='Ordinary startup consumes existing legitimate records; real initialization/Windows/formal AT35 still not accepted.')],
 required_followup='A separately authorized existing management actor, exact target/scope/input list and audited initialization/configuration code for actual principals/current permissions/catalogue/resources. The gap is not merely a request for user permission; do not invent identities/Grant/catalogue publication/approval/credentials or run fixture issuance as real setup.'),
 evidence_scope='Owned Linux PostgreSQL, restricted application Store, original HTTP/ASGI and normal configured_app processes, original full HTML NodeVM. Main pytest imports are instrumented with origins/hashes; child commands use frozen mirror src via original minimal_environment, not a separate child import audit. Existing original preparation helper completes local Run via Store.finish; business preparation/OFFER/receipt/plan decisions use original HTTP. Only labeled negative owner SQL alters fake proof/current grants; positive initialization is original fixture before ordinary app boot.',
 remaining_limits=['Real browser/Chromium, Windows native formal AT/AT35, real business/source/model/external messaging, deployment/main/force push/fees and root/seal installation NOT_RUN.','Formal source reader/verifier concrete trusted source inputs and Native permit/writer installation/independent approval remain separately blocked; no IsolatedPlanApproval used as ordinary success.','P5/local lifecycle, unsupported/PARTIAL targets, full original goal fulfillment/physical service/institution acceptance remain uncompleted; case_goal_completed=false.','Final checks follow actual owned lock waits; no physical COMMIT-instant expiry or all-source atomic snapshot claim. Own helper SIGTERM(-15) is normal child cleanup; PG Z/data absent recorded without reaped claim; no unknown process/lock action.'],
 publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json',raw_evidence_manifest='raw-evidence-manifest.json')
write(base/'independent-final-review.json',report)
with (base/'active-review-path.txt').open('x') as f:f.write(str(base)+'\n')
selected=[base/name for name in ('literal-oracle-plan.json','literal-oracle-plan.sha256','contract-observed.md','test_independent_ordinary_goal_results.v1.py','test_independent_ordinary_goal_results.py','probe-v1-v2.diff','probe-revision-attribution.json','scope-source-transition.json','preview-contract-wording-note.json','run_frozen_review.py','execute_review.py','finalize_review.py','independent-final-review.json','active-review-path.txt','root-evidence-cross-check.json','window1-controller.stdout','window1-controller.stderr','window2-controller.stdout','window2-controller.stderr')]
for path in (historical,final):
    selected.extend(x for x in path.iterdir() if x.is_file() and '.private.' not in x.name)
    for sub in ('scenarios','root-overlap-evidence','original-process-evidence'):
        if (path/sub).exists():selected.extend(x for x in (path/sub).rglob('*') if x.is_file())
tokens=set()
for path in (historical,final):tokens.update(load(path/'fixture-token-values.private.json'))
truncated=set()
# Only captured-session prefixes in fixture-key positions of pytest's safe repr.
for path in selected:
    if path.suffix=='.xml':content='\n'.join((x.text or '') for x in ET.parse(path).getroot().iter())
    else:
        try:content=path.read_text()
        except UnicodeDecodeError:continue
    for match in re.finditer(r"'(?:fixture-[abc]|prep-specialist-fixture-[abc]|executor-[abc]|unassigned)': '([A-Za-z0-9_-]+)\.\.\.",content):
        prefix=match.group(1)
        if any(t.startswith(prefix) for t in tokens):truncated.add(prefix+'...')
def scrub(value):
    count=0;result=value
    for token in sorted(tokens,key=len,reverse=True):
        for piece in (token,token[:12]):
            n=result.count(piece)
            if n:result=result.replace(piece,'SYNTHETIC_SESSION_REDACTED');count+=n
    for piece in sorted(truncated,key=len,reverse=True):
        n=result.count(piece)
        if n:result=result.replace(piece,'SYNTHETIC_TRUNCATED_SESSION_REDACTED');count+=n
    return result,count
mapped=[];public_files=[]
for path in sorted(set(selected)):
    rel=str(path.relative_to(base));raw=path.read_bytes();count=0
    if path.suffix=='.xml':
        original=ET.parse(path).getroot();safe=copy.deepcopy(original)
        for node in safe.iter():
            if node.text is not None:node.text,n=scrub(node.text);count+=n
            if node.tail is not None:node.tail,n=scrub(node.tail);count+=n
            for key,value in tuple(node.attrib.items()):node.attrib[key],n=scrub(value);count+=n
        public=ET.tostring(safe,encoding='utf-8',xml_declaration=True) if count else raw
        def shape(x):return (x.tag,x.attrib,x.text,x.tail,[shape(c) for c in x])
        parsed=ET.fromstring(public);assert shape(parsed)==shape(safe)
        assert [x.attrib for x in original.iter('testcase')]==[x.attrib for x in parsed.iter('testcase')]
        assert [x.tag for x in original.iter()]==[x.tag for x in parsed.iter()]
    else:
        try:value=raw.decode();value,count=scrub(value);public=value.encode()
        except UnicodeDecodeError:public=raw
    if count:
        destination=base/'public'/rel;destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as f:f.write(public)
        pub=str(destination.relative_to(base));public_files.append(destination)
    else:pub=rel;public_files.append(path)
    mapped.append(dict(raw=rel,public=pub,raw_sha256=sha(path),public_sha256=hashlib.sha256(public).hexdigest(),replacement_count=count))
write(base/'raw-public-redaction-map.json',dict(schema=1,files=mapped,replacements_total=sum(x['replacement_count'] for x in mapped),captured_fixture_token_values=len(tokens),captured_truncated_fragments=len(truncated),
 policy='Only reviewer-owned original fixture values and their captured prefixes/truncated repr fragments are used privately. Pure-letter public placeholders; XML sanitized only through text/tail/attribute nodes then serialized/parsed with exact testcase/outcome shape. All raw retained privately; no root private-synthetic-tokens accessed, no mirror/PGdata/config/token inventory published; canonical shadows never redacted twice.'))
public_files.extend(base/name for name in ('raw-public-redaction-map.json','publication-files.json','raw-evidence-manifest.json'))
publication=sorted(str(x.relative_to(base)) for x in set(public_files));assert len(publication)==len(set(publication))
write(base/'publication-files.json',publication)
write(base/'raw-evidence-manifest.json',dict(schema=1,source_sha=args.sha,self_hash_excluded_to_avoid_recursion=True,excludes=['mirror','PGdata','private credentials/config','*.private.json','token-bearing raw replaced by canonical shadows'],files=[dict(path=x,sha256=sha(base/x),bytes=(base/x).stat().st_size) for x in publication if x!='raw-evidence-manifest.json']))
for rel in publication:
    content=(base/rel).read_text()
    assert not any(t in content or t[:12] in content for t in tokens),rel
    assert not any(t in content for t in truncated),rel
    if rel.endswith('.xml'):ET.parse(base/rel)
for item in mapped:assert sha(base/item['raw'])==item['raw_sha256'] and sha(base/item['public'])==item['public_sha256']
print(json.dumps(dict(source_sha=args.sha,report_sha256=sha(base/'independent-final-review.json'),publication_sha256=sha(base/'publication-files.json'),publication_files=len(publication),map_sha256=sha(base/'raw-public-redaction-map.json'),manifest_sha256=sha(base/'raw-evidence-manifest.json'),independent_unique_PASS=8,root_unique_PASS=root_counts['collection'],overlap=3,combined_unique_PASS=len(ours|theirs),replacements=sum(x['replacement_count'] for x in mapped)),sort_keys=True))
