"""Evidence reconciliation/publication only; never executes application actions."""
from pathlib import Path
import copy,hashlib,json,re,xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent;ROOT=Path('/workspace/ParkWeave')
SHA='c6aa4a9a7693079a96de4c4a9ec031012b48fc7e'
PARENT=ROOT/'.runtime/existing-preparation-access-20261018/frozen-c6aa4a9a'
WINDOWS=[BASE/'frozen-c6aa4a9a-window1',BASE/'frozen-c6aa4a9a-window2']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def write(path,value):
    with path.open('x') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
def reconcile(path):
    values=load(path/'collection.json');ids=[v['nodeid'] if isinstance(v,dict) else v for v in values]
    rows=[json.loads(s) for s in (path/'calls.jsonl').read_text().splitlines()]
    assert len(ids)==len(set(ids))
    tree=ET.parse(path/'results.xml').getroot()
    cases=list(tree.iter('testcase'));jids=[v.attrib['classname'].replace('.','/')+'.py::'+v.attrib['name'] for v in cases]
    assert len(jids)==len(ids) and set(jids)==set(ids)
    phases={}
    for phase in ('setup','call','teardown'):
        selected=[r for r in rows if r['when']==phase]
        assert len(selected)==len(ids) and set(r['nodeid'] for r in selected)==set(ids)
        phases[phase]={o:sum(r['outcome']==o for r in selected) for o in ('passed','failed','skipped')}
    return dict(collection=len(ids),nodeids=sorted(ids),phases=phases,JUnit=[v.attrib for v in tree.iter('testsuite')],collection_all_phases_JUnit_nodeids_equal=True),rows

records=[];passed=set();failed=[];tokens=set();all_maps=[]
for index,window in enumerate(WINDOWS):
    counts,rows=reconcile(window);control=load(window/'controller-result.json');runtime=load(window/'pytest-result.json');origins=load(window/'module-origins.json')
    size=9 if index==0 else 1;fail=1 if index==0 else 0
    assert counts['collection']==size and counts['phases']['call']['passed']==size-fail and counts['phases']['call']['failed']==fail
    assert counts['phases']['setup']['passed']==counts['phases']['teardown']['passed']==size
    assert control['source_sha']==control['actual_HEAD_at_start']==control['actual_HEAD_at_end']==SHA
    assert control['exit_code']==fail and control['frozen_input_count']==810
    assert all(not control[k] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
    maps=[load(window/name) for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json')]
    assert all(v==maps[0] for v in maps);all_maps.extend(maps)
    assert all(v['within_mirror'] and (v['matches_frozen'] or v['matches_independent_probe']) and sha(Path(v['path']))==v['sha256'] for v in origins)
    original=BASE/('test_independent_existing_preparation_access.v1.py' if index==0 else 'test_independent_existing_preparation_access.py')
    mirror=window/'mirror/tests/test_independent_existing_preparation_access.py'
    before=load(window/'independent-source-before.json');after=load(window/'independent-source-after.json')
    assert before==after and before['test_independent_existing_preparation_access.py']==sha(original)==sha(mirror)
    proof=dict(original_version=str(original.relative_to(BASE)),original_version_sha256=sha(original),mirror_before_sha256=before['test_independent_existing_preparation_access.py'],mirror_after_sha256=sha(mirror),private_input_equal=True,private_probe_separate_from_810=True)
    write(window/'probe-version-validation.json',proof)
    passed.update(r['nodeid'] for r in rows if r['when']=='call' and r['outcome']=='passed')
    failed.extend(r['nodeid'] for r in rows if r['when']=='call' and r['outcome']=='failed')
    tokens.update(load(window/'fixture-token-values.private.json'))
    records.append(dict(path=window.name,counts=counts,controller=control,pytest_main_seconds=runtime['pytest_main_seconds'],origins=dict(total=len(origins),frozen=sum(v['matches_frozen'] for v in origins),private_probe=sum(v['matches_independent_probe'] for v in origins),unexpected=0,actual_files_rehashed=True),probe=proof,owned_pg_after_exit=load(window/'owned-pg-after-exit.json')))
assert len(failed)==1 and records[1]['counts']['nodeids']==failed and len(passed)==9
changed=[key for key,value in load(WINDOWS[0]/'independent-source-before.json').items() if value!=load(WINDOWS[1]/'independent-source-before.json')[key]]
assert changed==['test_independent_existing_preparation_access.py']

parent_counts,parent_rows=reconcile(PARENT);control=load(PARENT/'result.json')
assert parent_counts['collection']==38 and all(r['outcome']=='passed' for r in parent_rows)
assert control['head']==SHA and control['exit_code']==0 and control['inputs']==810
assert control['shared_drift']==control['mirror_drift']==[]
for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json'):all_maps.append(load(PARENT/name))
assert all(v==all_maps[0] for v in all_maps)
assert control['archive_sha256']==records[0]['controller']['archive_sha256']==records[1]['controller']['archive_sha256']
theirs=set(parent_counts['nodeids']);overlap=passed&theirs
assert len(overlap)==3 and len(passed-theirs)==6 and len(passed|theirs)==44
parent_mirror=Path(control['mirror']);origin_checks=[]
for name,value in load(PARENT/'module-origins.json').items():
    path=Path(value['path']);relative=str(path.relative_to(parent_mirror))
    origin_checks.append(dict(name=name,relative=relative,recorded_sha256=value['sha256'],actual_sha256=sha(path),matches_frozen=all_maps[0].get(relative)==value['sha256']==sha(path)))
assert all(v['matches_frozen'] for v in origin_checks)
write(BASE/'root-evidence-cross-check.json',dict(source_sha=SHA,root_executed_by_reviewer=False,counts=parent_counts,origin_checks=origin_checks,all_12_maps_equal=True,archives_equal=True,actual_overlap=sorted(overlap),root_only_nodeids=sorted(theirs-passed),independent_only_nodeids=sorted(passed-theirs),combined_effective_unique_PASS=44,references={name:sha(PARENT/name) for name in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json')}))
ledger=load(WINDOWS[0]/'scenarios/actual-row-wait.json');assert ledger['actual_pg_wait'] and ledger['old_sha_rejected'] and ledger['no_grant_or_audit_write']
denials=load(WINDOWS[1]/'scenarios/old-marker-generation.json');assert len(denials['expected_denial_audits'])==2
assert all((v['principal_id'],v['category'],v['outcome'])==('executor-a','API_AUTHORIZATION','DENIED') for v in denials['expected_denial_audits'])
assert denials['original_generation']!=denials['reinserted_generation'] and denials['marker_unchanged']
advisory=list((WINDOWS[0]/'original-process-evidence').rglob('administrator-wait-proof.json'));assert len(advisory)==1
assert load(advisory[0])['actual_pg_wait'] and load(advisory[0])['old_sha_rejected']
chain=list((WINDOWS[0]/'original-process-evidence').rglob('configuration-business-chain.json'));assert len(chain)==1
chain_value=load(chain[0]);assert chain_value['api_processes']==chain_value['cli_processes']==2

report=dict(schema=1,scope='INDEPENDENT_LIMITED_EXISTING_PREPARATION_ACCESS_CODE_REVIEW',source_sha=SHA,source_tree='186fc147a6a43390ca4ce9bffbb5f5966757b27b',baseline_sha='a9c725babd36561a6a25733953cc374ee1b77bd5',conclusion='LIMITED_PASS',open_P1=[],open_P2=[],
 independent_windows=records,independent_effective_unique_PASS=9,independent_own_unique_PASS=6,actual_root_overlap_nodeids=sorted(overlap),root_single_window_unique_PASS=38,effective_combined_unique_PASS=44,
 counting_policy='Independent window1:9 collection/setup/teardown,8 callPASS1 private assertionFAIL; authorized window2:only original failed selector1PASS. Effective union9=6 private+3 root overlaps. Root actual same-SHA38PASS; combined unique44. Never describe independent single-window9PASS. No previous P5 42/39/54 or old slice results transferred/recounted.',
 private_failure=dict(attribution='probe-revision-attribution.json',original_nodeid=failed[0],original_probe='test_independent_existing_preparation_access.v1.py',revised_probe='test_independent_existing_preparation_access.py',exact_diff='probe-v1-v2.diff',classification='PRIVATE_ASSERTION_INCLUDED_EXPECTED_ORIGINAL_DENIAL_AUDIT',original_limit='Window1 truncated pytest counts cannot establish its exact per-row audit difference. The original final summary assertion failed only after cold ordinary/default403, historical200, deadline/marker/generation checks had passed.',new_evidence='Original unchanged API Denied handler writes authorization_audit. Supplement separately verifies exactly2 original executor-a/API_AUTHORIZATION/DENIED rows and unchanged protected business snapshot; it does not ignore audit side effects.'),
 source_oracle=dict(path='literal-oracle-plan.json',sha256=sha(BASE/'literal-oracle-plan.json'),count=16,not_overwritten=True),contract_diff='frozen-contract-diff.patch',baseline_preservation='frozen-static-validation.json',private_interwindow_executable_change=changed,
 source_boundaries=dict(frozen_Git_inputs_per_window=810,all_12_same_SHA_input_maps_equal=True,all_shared_mirror_PREPOST_drift=0,archives_equal=True,archive_sha256=control['archive_sha256'],private_probe_separate_from_810=True,actual_private_versions_match_both_mirrors=True,root_cross_check='root-evidence-cross-check.json'),
 verified=[
  'Actual READ ONLY/REPEATABLE READ dry-run and nested duplicate/unknown credential-shaped/boolean-version config rejection; no business/Grant/audit writes and no raw invalid value echo.',
  'One active existing PREPARE row retains exact bytes/xmin; only missing REVIEW_ASSIGNED is inserted with its original beneficiary audit. Current NO_CHANGE has no writes. A later inactive same key is blocked without repair.',
  'Reason changes the hidden plan fence without appearing in output. Normal app can preview the same state but cannot apply; Native/isolated/ordinary-provider-bound Stores reject as administrator contexts. No app privileges were added for testing.',
  'Real capability row FOR SHARE wait after original principal admission observes a generation change, then rejects old SHA with Conflict and no preparation-Grant/audit write. Root-overlap real catalogue advisory ABA also rejects stale SHA.',
  'A narrowly observed failure before the second original INSERT rolls back the first Grant and its audit; complete original table snapshot and original fence remain unchanged. No schema/role/fixture alteration or automatic replay.',
  'An intentionally deleted preparation Grant is reinserted only inside the owned synthetic DB; its new xmin cannot revive the old marker in a cold ordinary app or default app. Marker/absolute deadline/business rows stay unchanged and exactly2 original denial audits persist.',
  'Executed root overlaps here: default dry-run/explicit2Grant/apply/currentNO_CHANGE, actual catalogue ABA lock wait, and actual CLI dry/apply plus original material REVIEW/CONFIRM and cold reads across2 normal API processes. No NodeVM/browser test selected.'
 ],
 actual_row_wait=ledger,actual_marker_denial_audits=denials,actual_original_API_CLI_chain=dict(path=str(chain[0].relative_to(BASE)),proof=chain_value),
 coverage_limits=[
  'All16 oracle rows are design requirements, not16 independently executed end-to-end scenarios. Commit-after-success uncertainty is covered by the root-owned executed test/source/provenance cross-check, not one of this reviewer9 selected nodes.',
  'No new app INSERT privilege, SET ROLE grant, alternate DB owner/table ownership or second real database was installed for negative tests; actual owner/session/table checks are statically reviewed and app-role refusal is directly tested.',
  'No full withdrawal/corrupt publication-history fuzz matrix or complete initialization/security/concurrency matrix is claimed. Original catalogue proof/known-source and current capability/audit algorithms are unchanged.',
  'Endpoint/databaseOID/name/start-time is a fresh-state fence, not cryptographic cluster identity/signature/Approval/Native permit. No protection against trusted-admin DB rewriting or exact physical COMMIT-instant freshness is claimed.',
  'Main pytest imports are instrumented and rehashed. The original CLI/API subprocess helper points to frozen mirror src; no separate child import-audit claim. Local fake Run completion uses original Store.finish, no real model.'
 ],
 actual_remaining_inputs=['Existing legal current owner/reviewer subjects and capabilities, exact legitimate SYNTHETIC catalogue/source, correctly preinstalled schema32/33 and normal restricted DSN/session. Product code imports or creates none of those.','A separately authorized direct database/table-owner session and explicit apply plus current plan SHA are required for the two scoped preparation-grant inserts. The code and SHA do not supply independent administrative approval.'],
 remaining_not_run=['Any real identity/Grant/assignment/catalogue publication/approval/credential or production installation.','Real subject mapping/legitimate source acquisition/formal catalogue publishing, executor/resource management initialization and Native permit/writer installation remain separate.','Windows/formal AT35/real browser/real business or models/main/deployment/force push/fees. Existing migration32/33 production installation refusal remains.'],
 evidence_scope='Only fresh reviewer-owned /tmp SYNTHETIC PG/actual owner and original restricted app roles, actual original HTTP/CLI/API processes, bounded negative row/insert observers. No roles/schema/conftest/controlled source/Git mutation, real permission action, unknown lock/process cleanup or broad old-matrix execution.',
 publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json',raw_evidence_manifest='raw-evidence-manifest.json')
write(BASE/'independent-final-review.json',report)
with (BASE/'active-review-path.txt').open('x') as f:f.write(str(BASE)+'\n')

selected=[p for p in BASE.iterdir() if p.is_file() and '.private.' not in p.name]
for window in WINDOWS:
    selected.extend(p for p in window.iterdir() if p.is_file() and '.private.' not in p.name)
    for child in ('scenarios','root-overlap-evidence','original-process-evidence'):
        if (window/child).exists():selected.extend(p for p in (window/child).rglob('*') if p.is_file())
selected=sorted(set(selected))
assert not any('config.json'==p.name or 'token' in p.name.lower() for p in selected)
fragments=set()
names=r'(?:fixture-[abc]|prep-specialist-fixture-[abc]|executor-[abc]|unassigned|configured-owner|configured-reviewer)'
for path in selected:
    content=path.read_text()
    for match in re.finditer(r"'"+names+r"': '([A-Za-z0-9_-]+)\.\.\.",content):
        prefix=match.group(1)
        if any(token.startswith(prefix) for token in tokens):fragments.add(prefix+'...')
def scrub(value):
    count=0;result=value
    for token in sorted(tokens,key=len,reverse=True):
        n=result.count(token)
        if n:result=result.replace(token,'SYNTHETIC_SESSION_REDACTED');count+=n
    for fragment in sorted(fragments,key=len,reverse=True):
        n=result.count(fragment)
        if n:result=result.replace(fragment,'SYNTHETIC_TRUNCATED_SESSION_REDACTED');count+=n
    # Captured fixture repr can retain a prefix/suffix without its full value.
    for token in sorted(tokens,key=len,reverse=True):
        for size in range(len(token)-1,7,-1):
            for piece in (token[:size],token[-size:]):
                n=result.count(piece)
                if n:result=result.replace(piece,'SYNTHETIC_SESSION_REDACTED');count+=n
    return result,count
mapping=[];publication=[]
for path in selected:
    relative=str(path.relative_to(BASE));raw=path.read_bytes();replacements=0
    if path.suffix=='.xml':
        original=ET.parse(path).getroot();safe=copy.deepcopy(original)
        for node in safe.iter():
            if node.text is not None:node.text,n=scrub(node.text);replacements+=n
            if node.tail is not None:node.tail,n=scrub(node.tail);replacements+=n
            for key,value in tuple(node.attrib.items()):node.attrib[key],n=scrub(value);replacements+=n
        encoded=ET.tostring(safe,encoding='utf-8',xml_declaration=True) if replacements else raw
        parsed=ET.fromstring(encoded)
        assert [n.attrib for n in original.iter('testcase')]==[n.attrib for n in parsed.iter('testcase')]
        assert [n.tag for n in original.iter()]==[n.tag for n in parsed.iter()]
    else:
        value,replacements=scrub(raw.decode());encoded=value.encode()
    if replacements:
        target=BASE/'public'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(encoded)
        public=str(target.relative_to(BASE))
    else:public=relative
    publication.append(public)
    mapping.append(dict(raw=relative,public=public,raw_sha256=sha(path),public_sha256=hashlib.sha256(encoded).hexdigest(),replacement_count=replacements))
write(BASE/'raw-public-redaction-map.json',dict(schema=1,files=mapping,replacement_count=sum(v['replacement_count'] for v in mapping),captured_own_fixture_values=len(tokens),captured_context_fragments=len(fragments),policy='Only this reviewer two windows captured actual fixture values; recursively includes nested configuration_fixture configured-owner/reviewer tokens. Full values/context fragments/remaining captured prefixes or suffixes redacted once with pure ASCII. XML node text/tail/attributes serialized and parsed preserving testcase/outcome tags. All raw retained privately; no parent private inventories read, no mirror/PGdata/private token/config published. Canonical shadows must be copied without second redaction.'))
publication+=['publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json'];assert len(publication)==len(set(publication));publication=sorted(publication)
write(BASE/'publication-files.json',publication)
write(BASE/'raw-evidence-manifest.json',dict(schema=1,source_sha=SHA,self_hash_excluded=True,excludes=['mirror','PGdata','private fixture token inventory/config','token-bearing raw when canonical shadow selected'],files=[dict(path=p,sha256=sha(BASE/p),bytes=(BASE/p).stat().st_size) for p in publication if p!='raw-evidence-manifest.json']))
for relative in publication:
    text=(BASE/relative).read_text()
    assert not any(token in text or token[:8] in text or token[-8:] in text for token in tokens),relative
    assert not any(fragment in text for fragment in fragments),relative
    if relative.endswith('.xml'):ET.parse(BASE/relative)
for row in mapping:assert sha(BASE/row['raw'])==row['raw_sha256'] and sha(BASE/row['public'])==row['public_sha256']
print(json.dumps(dict(source_sha=SHA,report_sha256=sha(BASE/'independent-final-review.json'),publication_sha256=sha(BASE/'publication-files.json'),map_sha256=sha(BASE/'raw-public-redaction-map.json'),manifest_sha256=sha(BASE/'raw-evidence-manifest.json'),publication_files=len(publication),replacement_count=sum(v['replacement_count'] for v in mapping),independent_effective_unique_PASS=9,root_unique_PASS=38,overlap=3,combined_unique_PASS=44),sort_keys=True))
