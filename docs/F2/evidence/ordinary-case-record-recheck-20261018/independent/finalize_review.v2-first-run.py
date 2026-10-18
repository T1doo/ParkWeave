"""Reconcile existing bounded evidence and produce XML-safe canonical copies."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import xml.etree.ElementTree as ET

parser=argparse.ArgumentParser()
parser.add_argument('--parent',required=True)
parser.add_argument('--supplement',required=True)
args=parser.parse_args()
base=Path(__file__).resolve().parent
root=Path('/workspace/ParkWeave')
window=base/'frozen-0d45e3c6-window1'
parent=root/args.parent
supplement=root/args.supplement
SOURCE='0d45e3c60ed62f40df242b462475a51d58c57cd7'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def write(path,value):
    with path.open('x') as file:file.write(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n')

def reconcile(path):
    collected=load(path/'collection.json')
    ids=[x['nodeid'] if isinstance(x,dict) else x for x in collected]
    assert len(ids)==len(set(ids))
    rows=[json.loads(x) for x in (path/'calls.jsonl').read_text().splitlines()]
    xml=ET.parse(path/'results.xml').getroot()
    cases=list(xml.iter('testcase'))
    jids=[x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in cases]
    assert len(jids)==len(ids) and set(jids)==set(ids)
    phases={}
    for phase in ('setup','call','teardown'):
        these=[r for r in rows if r['when']==phase]
        assert len(these)==len(ids) and set(r['nodeid'] for r in these)==set(ids)
        phases[phase]={k:sum(r['outcome']==k for r in these) for k in ('passed','failed','skipped')}
    return dict(collection=len(ids),nodeids=sorted(ids),phases=phases,JUnit=[x.attrib for x in xml.iter('testsuite')],nodeids_collection_all_phases_JUnit_equal=True),rows

counts,rows=reconcile(window)
control=load(window/'controller-result.json')
runtime=load(window/'pytest-result.json')
origins=load(window/'module-origins.json')
assert counts['collection']==9 and all(r['outcome']=='passed' for r in rows)
assert control['source_sha']==control['actual_HEAD_at_start']==control['actual_HEAD_at_end']==SOURCE
assert control['exit_code']==0 and control['frozen_input_count']==807
assert all(control[k]==[] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
maps=[load(window/name) for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json')]
assert all(x==maps[0] for x in maps)
assert all(x['within_mirror'] and (x['matches_frozen'] or x['matches_independent_probe']) for x in origins)
probe='test_independent_ordinary_record_recheck.py'
private_pre=load(window/'independent-source-before.json')[probe]
assert sha(base/probe)==sha(window/'mirror/tests'/probe)==private_pre
write(window/'independent-probe-mirror-hash.json',dict(original_PRE_sha256=private_pre,original_POST_sha256=sha(base/probe),mirror_POST_sha256=sha(window/'mirror/tests'/probe),equal=True,private_probe_separate_from_807=True))

root_windows=[];root_passes=set();root_failed=[]
for target,expected_size,expected_fail,expected_exit in ((parent,36,1,1),(supplement,1,0,0)):
    parent_counts,parent_rows=reconcile(target)
    parent_control=load(target/'result.json')
    assert parent_control['head']==SOURCE and parent_control['exit_code']==expected_exit and parent_control['inputs']==807
    assert parent_counts['collection']==expected_size
    assert parent_counts['phases']['setup']['passed']==parent_counts['phases']['teardown']['passed']==expected_size
    assert parent_counts['phases']['call']['failed']==expected_fail and parent_counts['phases']['call']['passed']==expected_size-expected_fail
    assert parent_control['shared_drift']==parent_control['mirror_drift']==[]
    assert all(load(target/name)==maps[0] for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json'))
    parent_origins=load(target/'module-origins.json');parent_mirror=Path(parent_control['mirror']);origin_checks=[]
    for name,row in parent_origins.items():
        file=Path(row['path']);relative=str(file.relative_to(parent_mirror))
        origin_checks.append(dict(name=name,relative=relative,recorded_sha256=row['sha256'],actual_sha256=sha(file),matches_frozen=maps[0].get(relative)==row['sha256']==sha(file)))
    assert all(x['matches_frozen'] for x in origin_checks)
    root_passes.update(r['nodeid'] for r in parent_rows if r['when']=='call' and r['outcome']=='passed')
    root_failed.extend(r['nodeid'] for r in parent_rows if r['when']=='call' and r['outcome']=='failed')
    root_windows.append(dict(path=str(target.relative_to(root)),counts=parent_counts,controller=parent_control,origin_checks=origin_checks,archives_equal=parent_control['archive_sha256']==control['archive_sha256'],references={n:sha(target/n) for n in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json')}))
assert len(root_failed)==1 and root_failed==root_windows[1]['counts']['nodeids']
assert set(root_windows[0]['counts']['nodeids'])==root_passes and len(root_passes)==36
ours=set(counts['nodeids']);theirs=root_passes;overlap=ours&theirs
assert len(overlap)==3 and len(ours-theirs)==6 and len(ours|theirs)==42
root_bad_proofs=list((parent/'process-artifacts').rglob('final-wait-proof.json'))
bad=[]
for file in root_bad_proofs:
    value=load(file)
    if value.get('operation')=='VERIFY_P5' and value.get('deadline_kind')=='resource_end':
        assert value.get('status')==409 and value.get('actual_pg_lock_observed') is False and 'remaining_after_view' not in value
        bad.append(dict(path=str(file.relative_to(root)),sha256=sha(file),proof=value))
assert len(bad)==1
supp_proofs=list((supplement/'process-artifacts').rglob('final-wait-proof.json'))
assert len(supp_proofs)==1
supp_proof=load(supp_proofs[0])
assert supp_proof['actual_pg_lock_observed'] and supp_proof['status']==403 and not supp_proof['clock_offset_used']
assert supp_proof['operation']=='VERIFY_P5' and supp_proof['deadline_kind']=='resource_end'
write(base/'root-evidence-cross-check.json',dict(source_sha=SOURCE,root_executed_by_reviewer=False,windows=root_windows,root_effective_unique_PASS=36,root_failed_nodeid_rechecked=root_failed,root_main_failure=dict(classification='TEST_PRECONDITION_NOT_REACHED',actual_status=409,actual_pg_wait=False,reason='Original POST began after actual original resource end. Preparation delay cause remains unknown; no concurrency attribution.',evidence=bad),root_supplement_proof=dict(path=str(supp_proofs[0].relative_to(root)),sha256=sha(supp_proofs[0]),proof=supp_proof),independent_archive_sha256=control['archive_sha256'],all_root_archives_equal=all(x['archives_equal'] for x in root_windows),root_and_independent_12_maps_equal=True,actual_overlap=sorted(overlap),root_only_nodeids=sorted(theirs-ours),independent_only_nodeids=sorted(ours-theirs),combined_unique_PASS=42))

ledger=load(window/'scenarios/actual-ledger-resource-end.json')
assert ledger['actual_ledger_wait_observed'] and ledger['status']==403 and not ledger['clock_offset_used'] and ledger['no_business_write']
assert 'case_local_lifecycles' in ledger['observed_wait']['query'] and 'FOR SHARE' in ledger['observed_wait']['query']
html=[]
for file in sorted((window/'original-process-evidence').rglob('summary.json')):
    value=load(file)
    html.append(dict(path=str(file.relative_to(base)),assertions=value.get('assertions'),checks=value.get('checks'),calls=len(value.get('calls',[])),state=value.get('state'),real_browser=False))
root_wait_proofs=[]
for file in sorted((window/'original-process-evidence').rglob('final-wait-proof.json')):
    value=load(file);assert value['actual_pg_lock_observed'] and value['status']==403 and not value['clock_offset_used']
    root_wait_proofs.append(dict(path=str(file.relative_to(base)),proof=value))
assert len(root_wait_proofs)==1
report=dict(
 schema=1,scope='INDEPENDENT_LIMITED_ORDINARY_P5_LOCAL_RECORD_RECHECK',
 source_sha=SOURCE,source_tree='259ac36d83ef2d98fa33b4826822bff81e3664a3',baseline_sha='1f7e4d4a11606a511062fecb1863803209f3831d',
 conclusion='LIMITED_PASS',open_P1=[],open_P2=[],
 independent_window=dict(path=window.name,counts=counts,controller=control,pytest_main_seconds=runtime['pytest_main_seconds'],origins=dict(total=len(origins),frozen=sum(x['matches_frozen'] for x in origins),private_probe=sum(x['matches_independent_probe'] for x in origins),unexpected=0),owned_pg_after_exit=load(window/'owned-pg-after-exit.json')),
 independent_unique_PASS=9,independent_own_unique_PASS=6,actual_root_overlap_nodeids=sorted(overlap),root_effective_unique_PASS=36,root_windows=root_windows,effective_combined_unique_PASS=42,
 counting_policy='One actual final-SHA independent window:9 collection/setup/call/teardown/JUnit PASS=6 private nodes+3 root overlaps. Root main36=35PASS1FAIL(test precondition), then exactly1 unchanged failed-selector supplementPASS; effective same-SHA root union36, combined union42. Never claim a single root36PASS window or erase the failure. No old39/54/69/129 or previous slice transferred or rerun wholesale.',
 root_main_failure_attribution=dict(nodeid=root_failed[0],classification='TEST_PRECONDITION_NOT_REACHED',actual_status=409,actual_pg_wait=False,evidence=bad,cause_of_preparation_delay='UNKNOWN',unchanged_single_selector_supplement=supp_proof),
 oracle=dict(path='literal-oracle-plan.json',sha256=sha(base/'literal-oracle-plan.json'),count=16,unchanged_since_contract_first_freeze=True),
 frozen_contract_transition='frozen-contract-diff.patch',frozen_static_validation='frozen-static-validation.json',extracted_original_proof_ast='event-proof-ast-comparison.json',
 actual_independent_ledger_wait=ledger,root_selector_actual_final_view_wait=root_wait_proofs,actual_original_full_HTML=html,
 independent_verified=[
  'Original standalone lifecycle without an adopted plan uses real preparation/resource/ACCEPT/manual SUBMIT/owner ACK; close requires original revalidation and creates no plan or Run assignment.',
  'Two original REVALIDATE events in the same cycle following actual receipt correction retain both histories. CLOSE and REOPEN original-key cold GETs report exact historical COMMITTED/current-version split. Original close POST replay does not restore a reopened cycle; a changed body under the old key409.',
  'Owner EXECUTE revocation retains authorized history and original-key recovery, but writes and original POST replay403. Restored owner capability plus executor READ revoke/restore does not revive old generations; explicit REOPEN succeeds without renewal, then new validation/P5 VERIFY remain blocked. Offer marker, deadline, holds and single offer remain unchanged.',
  'An altered original REVALIDATE reason and a changed original source Case ID are rejected409 by current lifecycle/P5/recovery while business digests remain unchanged; no alternate engine or self-rehashing oracle.',
  'The actual original lifecycle ledger FOR SHARE waits past a real resource end with an unexpired offer; precise database wait/UTC/status/detail retained,403 after expiry and no business writes.',
  'Original actor/key cross-Case mismatch409, executor/other-owner/default-lane history and whole-Case results403; reviewer gets original minimal status without event payload or source SHA; no whole-Run access or authority mutation.',
  'Root overlap executed here: original complete ordinary HTTP P5 chain/cold recovery, actual final-view PG wait across first-offer deadline during P5 VERIFY, original HTML P5 close/VERIFY/TXT cold start/reopen across3 normal API processes.'
 ],
 coverage_limits=[
  'P1/P2-only unrelated-step deadline scope is inspected statically: original bounded_planning/controlled_plans and prior ordinary selection behavior retained; new source wiring is inside actual P5 branch. Prior39 is historical, not a new dynamic node here.',
  'This bounded execution does not separately run every combination of all16 oracle rows; original CAS/rollback/history-limit algorithms are reused and inspected, not a complete new concurrency matrix.',
  'Legacy REOPEN optional ignored SHA retains original structural proof limits; no complete-body reconstruction, signature or protection against trusted-admin DB rewriting is claimed.',
  'Last-wait admission checks do not prove physical COMMIT-instant expiry or a global atomic all-source snapshot.',
  'Main pytest imports are instrumented against frozen mirror hashes. Original normal API child processes use frozen mirror source via existing helper; there is no separate child import-audit claim.'
 ],
 private_controller_issue=dict(path='oracle-controller-path-failure.json',classification='Pre-oracle read-only manifest path typo web.py, actual web.html corrected before execution; git128,0 business tests, not product failure; both script versions retained.'),
 runtime_required_inputs=[
  'Existing LOCAL schema/restricted DSN, explicit CURRENT_PREPARATION configured_app and current session; startup does not migrate, seed or repair.',
  'Current original same-domain owner READ/PREPARE and EXECUTE for writes, exact reviewer READ/REVIEW_ASSIGNED, existing selected service_executor READ, legal exact SYNTHETIC catalogue and original preparation/Case/Run binding.',
  'Source-backed material REVIEW/CONFIRM, current resource READ/HOLD and rules/time/capacity/confirmed combination/link/claim, original first-offer UUID/deadline/generations and actual ACCEPT/CREATE/manual receipt SUBMIT/owner ACK.',
  'For the plan loop: original explicit goals/ADOPT/P1-P4 owner VERIFY, actual original lifecycle revalidation/close, explicit current P5 owner VERIFY. Independent standalone lifecycle preserves original no-plan compatibility.'
 ],
 remaining_blockers=[
  'Real management initialization remains unimplemented here: needs real subject mapping, authorized management target/scope list and audited initialization/configuration flow; no real identity/Grant/assignment/publication/approval/credential/install executed.',
  'Formal provider concrete trusted source contracts and Native permit/writer installation/approval remain separate; default/Native/old isolated rejection was not bypassed.',
  'Real browser/Chromium, Windows native formal AT/AT35, real business/sources/models, physical fulfillment, deployment/main/force push/fees are NOT_RUN. case_goal_completed remains false.'
 ],
 source_boundaries=dict(frozen_Git_inputs_per_window=807,private_probe_inputs=1,all_4_maps_equal=True,all_shared_mirror_PREPOST_drift=0,all_private_original_and_mirror_probe_drift=0,root_cross_check='root-evidence-cross-check.json'),
 evidence_scope='Fresh reviewer-owned /tmp Linux PG and existing SYNTHETIC fixture only; business actions use original HTTP/ASGI and full original HTML NodeVM. Negative fault injections use owner SQL only inside owned fake DB. Original fixture preparation uses its existing Store.finish; no real model. No tracked/Git mutation, unknown-process cleanup, new permissions or safety-network changes.',
 publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json',raw_evidence_manifest='raw-evidence-manifest.json')
write(base/'independent-final-review.json',report)
with (base/'active-review-path.txt').open('x') as file:file.write(str(base)+'\n')

# Original files are retained; select a canonical public counterpart exactly once.
selected=[x for x in base.iterdir() if x.is_file() and x.name not in ('publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json') and '.private.' not in x.name]
selected.extend(x for x in window.iterdir() if x.is_file() and '.private.' not in x.name)
for sub in ('scenarios','root-overlap-evidence','original-process-evidence'):
    if (window/sub).exists():selected.extend(x for x in (window/sub).rglob('*') if x.is_file())
selected=sorted(set(selected))
assert not any('config' in x.name.lower() or 'token' in x.name.lower() for x in selected)
tokens=set(load(window/'fixture-token-values.private.json'))
truncated=set()
for file in selected:
    value=file.read_text()
    for match in re.finditer(r"'(?:fixture-[abc]|prep-specialist-fixture-[abc]|executor-[abc]|unassigned)': '([A-Za-z0-9_-]+)\.\.\.",value):
        prefix=match.group(1)
        if any(t.startswith(prefix) for t in tokens):truncated.add(prefix+'...')
def scrub(value):
    result=value;replacements=0
    for token in sorted(tokens,key=len,reverse=True):
        for piece in (token,token[:12]):
            count=result.count(piece)
            if count:result=result.replace(piece,'SYNTHETIC_SESSION_REDACTED');replacements+=count
    for piece in sorted(truncated,key=len,reverse=True):
        count=result.count(piece)
        if count:result=result.replace(piece,'SYNTHETIC_TRUNCATED_SESSION_REDACTED');replacements+=count
    return result,replacements
mapping=[];public=[]
for file in selected:
    relative=str(file.relative_to(base));raw=file.read_bytes();count=0
    if file.suffix=='.xml':
        original=ET.parse(file).getroot();safe=copy.deepcopy(original)
        for node in safe.iter():
            if node.text is not None:node.text,n=scrub(node.text);count+=n
            if node.tail is not None:node.tail,n=scrub(node.tail);count+=n
            for key,value in tuple(node.attrib.items()):node.attrib[key],n=scrub(value);count+=n
        encoded=ET.tostring(safe,encoding='utf-8',xml_declaration=True) if count else raw
        parsed=ET.fromstring(encoded)
        assert [x.attrib for x in original.iter('testcase')]==[x.attrib for x in parsed.iter('testcase')]
        assert [x.tag for x in original.iter()]==[x.tag for x in parsed.iter()]
    else:
        value,count=scrub(raw.decode());encoded=value.encode()
    if count:
        destination=base/'public'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as output:output.write(encoded)
        published=str(destination.relative_to(base))
    else:published=relative
    public.append(published)
    mapping.append(dict(raw=relative,public=published,raw_sha256=sha(file),public_sha256=hashlib.sha256(encoded).hexdigest(),replacement_count=count))
write(base/'raw-public-redaction-map.json',dict(schema=1,files=mapping,replacement_count=sum(x['replacement_count'] for x in mapping),captured_own_fixture_token_values=len(tokens),captured_truncated_fragments=len(truncated),policy='Only this reviewer window captured fixture tokens/prefixes; parent private token inventories never read. Pure ASCII placeholders; XML node values then serialized/parsed with original testcase/outcome shape. All raw retained; only canonical shadows included for altered files, never redacted twice.'))
public+=['raw-public-redaction-map.json','publication-files.json','raw-evidence-manifest.json']
assert len(public)==len(set(public))
public=sorted(public)
write(base/'publication-files.json',public)
write(base/'raw-evidence-manifest.json',dict(schema=1,source_sha=SOURCE,self_hash_excluded=True,excluded=['mirror','PGdata','private tokens/config','token-bearing raw replaced by canonical shadows'],files=[dict(path=x,sha256=sha(base/x),bytes=(base/x).stat().st_size) for x in public if x!='raw-evidence-manifest.json']))
for relative in public:
    value=(base/relative).read_text()
    assert not any(t in value or t[:12] in value for t in tokens),relative
    assert not any(t in value for t in truncated),relative
    if relative.endswith('.xml'):ET.parse(base/relative)
for row in mapping:
    assert sha(base/row['raw'])==row['raw_sha256'] and sha(base/row['public'])==row['public_sha256']
print(json.dumps(dict(source_sha=SOURCE,report_sha256=sha(base/'independent-final-review.json'),publication_sha256=sha(base/'publication-files.json'),publication_files=len(public),map_sha256=sha(base/'raw-public-redaction-map.json'),manifest_sha256=sha(base/'raw-evidence-manifest.json'),independent_unique_PASS=9,own_unique_PASS=6,root_unique_PASS=36,overlap=3,combined_unique_PASS=42,replacement_count=sum(x['replacement_count'] for x in mapping)),sort_keys=True))
