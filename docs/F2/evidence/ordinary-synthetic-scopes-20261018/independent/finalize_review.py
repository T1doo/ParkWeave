"""Read-only frozen evidence reconciliation; one-time canonical publication."""
from pathlib import Path
import copy,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parent;ROOT=Path('/workspace/ParkWeave')
SHA='b5f3a4a491a7f7c70c0c7ca23c35bb6b3d89c595';OLD='a396f63eed027d4ccf8dc1ed6f591766915449ae'
WINDOW=BASE/'frozen-b5f3a4a4-window1';PARENT=BASE.parent/'frozen-b5f3a4a4'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def write(path,value):
 with path.open('x') as file:file.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def reconcile(path):
 collected=load(path/'collection.json');ids=[v['nodeid'] if isinstance(v,dict) else v for v in collected]
 assert len(ids)==len(set(ids))
 rows=[json.loads(x) for x in (path/'calls.jsonl').read_text().splitlines()]
 xml=ET.parse(path/'results.xml').getroot();cases=list(xml.iter('testcase'))
 jids=[v.attrib['classname'].replace('.','/')+'.py::'+v.attrib['name'] for v in cases]
 assert len(jids)==len(ids) and set(jids)==set(ids)
 phases={}
 for phase in ('setup','call','teardown'):
  actual=[v for v in rows if v['when']==phase]
  assert len(actual)==len(ids) and {v['nodeid'] for v in actual}==set(ids)
  phases[phase]={o:sum(v['outcome']==o for v in actual) for o in ('passed','failed','skipped')}
 assert not any(c.find(t) is not None for c in cases for t in ('failure','error','skipped'))
 return dict(collection=len(ids),nodeids=sorted(ids),phases=phases,JUnit=[v.attrib for v in xml.iter('testsuite')],exact_collection_all_phases_JUnit=True),rows

counts,rows=reconcile(WINDOW);control=load(WINDOW/'controller-result.json');runtime=load(WINDOW/'pytest-result.json')
assert counts['collection']==5 and all(v['outcome']=='passed' for v in rows)
assert control['source_sha']==control['actual_HEAD_at_start']==control['actual_HEAD_at_end']==SHA
assert control['exit_code']==0 and control['frozen_input_count']==820
assert all(not control[k] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
maps=[load(WINDOW/name) for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json')]
assert all(v==maps[0] for v in maps)
origins=load(WINDOW/'module-origins.json')
assert all(v['within_mirror'] and (v['matches_frozen'] or v['matches_independent_probe']) and sha(Path(v['path']))==v['sha256'] for v in origins)
scripts={v['name']:v for v in origins if v['name'].startswith('scripts.')}
assert set(scripts)=={'scripts.ordinary_synthetic_demo','scripts.material_only_demo','scripts.linux_fixture_server'}
probe='test_independent_ordinary_synthetic_scopes.py'
private_pre=load(WINDOW/'independent-source-before.json');private_post=load(WINDOW/'independent-source-after.json')
assert private_pre==private_post and private_pre[probe]==sha(BASE/probe)==sha(WINDOW/'mirror/tests'/probe)
write(WINDOW/'probe-version-validation.json',dict(original_PRE_sha256=private_pre[probe],original_POST_sha256=sha(BASE/probe),mirror_POST_sha256=sha(WINDOW/'mirror/tests'/probe),all_equal=True,private_probe_separate_from_820=True))
parent_counts,parent_rows=reconcile(PARENT);parent_control=load(PARENT/'result.json')
assert parent_counts['collection']==7 and all(v['outcome']=='passed' for v in parent_rows)
assert parent_control['head']==SHA and parent_control['exit_code']==0 and parent_control['inputs']==820
assert parent_control['shared_drift']==parent_control['mirror_drift']==[]
assert all(load(PARENT/name)==maps[0] for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json'))
assert parent_control['archive_sha256']==control['archive_sha256']
ours=set(counts['nodeids']);theirs=set(parent_counts['nodeids']);overlap=ours&theirs
assert len(overlap)==2 and len(ours-theirs)==3 and len(ours|theirs)==10
root_origins=[];parent_mirror=Path(parent_control['mirror'])
for name,value in load(PARENT/'module-origins.json').items():
 file=Path(value['path']);relative=str(file.relative_to(parent_mirror))
 root_origins.append(dict(name=name,relative=relative,recorded_sha256=value['sha256'],actual_sha256=sha(file),matches_frozen=maps[0].get(relative)==value['sha256']==sha(file)))
assert all(v['matches_frozen'] for v in root_origins)
assert {x['name'] for x in root_origins if x['name'].startswith('scripts.')}==set(scripts)
write(BASE/'root-evidence-cross-check.json',dict(source_sha=SHA,root_executed_by_reviewer=False,counts=parent_counts,origins=root_origins,root_origin_scope='Main pytest parkweave/test/support and scripts imports, not complete child-process import instrumentation.',all_8_input_maps_equal=True,archives_equal=True,actual_overlap=sorted(overlap),independent_only_nodeids=sorted(ours-theirs),root_only_nodeids=sorted(theirs-ours),combined_unique_PASS=10,references={n:sha(PARENT/n) for n in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json')}))
baseline=load(BASE/'baseline-inputs.json')['files'];source_baseline={k:v for k,v in baseline.items() if k.startswith(('src/','tests/','scripts/')) or k=='pyproject.toml'}
changed=[k for k,v in source_baseline.items() if maps[0][k]!=v['sha256']]
assert sorted(changed)==['scripts/ordinary_synthetic_demo.py','tests/test_ordinary_synthetic_demo.py']
assert len(source_baseline)==798
contract='docs/F2/OrdinarySyntheticScopesContract-20261018.md'
assert maps[0][contract]==load(BASE/'literal-oracle-plan.json')['contract_sha256']
src_tree=subprocess.check_output(['git','rev-parse',SHA+':src'],cwd=ROOT,text=True).strip()
assert src_tree==subprocess.check_output(['git','rev-parse',OLD+':src'],cwd=ROOT,text=True).strip()
write(BASE/'frozen-static-validation.json',dict(baseline=OLD,source_sha=SHA,src_tree=src_tree,src_tree_unchanged=True,all798_baseline_code_input_files_checked=True,unchanged796=[k for k in source_baseline if k not in changed],changed_only=changed,new_test='tests/test_ordinary_synthetic_scopes.py',contract_unchanged_since_oracle=True,product_algorithm_changes=0))
states=load(WINDOW/'owned-demo-state-observations.json');assert len(states)==5
bound={key:value for key,value in maps[0].items() if key.startswith('src/parkweave/') or key in ('scripts/ordinary_synthetic_demo.py','scripts/material_only_demo.py','scripts/linux_fixture_server.py')}
source_checks=[]
for row in states:
 state=Path(row['state_dir']);marker=load(state/'state.json')
 assert row['state_retained'] and row['data_retained'] and not row['stop_unconfirmed'] and not row['postmaster_marker_exists']
 assert marker['source']['files']==bound
 raw=json.dumps(bound,sort_keys=True,separators=(',',':')).encode()
 assert hashlib.sha256(raw).hexdigest()==marker['source']['sha256']==row['source_binding']
 source_checks.append(dict(state_dir=str(state),source_files=len(bound),complete_runtime_and_lifecycle_files_match_frozen=True,source_sha256=row['source_binding'],schema_version=row['schema_version'],postmaster_marker=False))
write(BASE/'demo-state-source-binding-validation.json',dict(source_sha=SHA,states=source_checks,all5_setup_PG_stopped=True,negative_states_retained_not_automatically_repaired=True,no_state_session_or_PGdata_published=True))
old_pre=load(WINDOW/'scenarios/independent-old-state-before.json');old_post=load(WINDOW/'scenarios/independent-old-state-after.json');assert old_pre==old_post
old_proof=load(WINDOW/'scenarios/independent-scope-binding.json');assert old_proof['process_attempts']==0 and old_proof['old_files_hashed']==len(old_pre['files'])
for relative,recorded in old_pre['files'].items():assert sha(Path(old_pre['state_dir'])/relative)==recorded['sha256']
chains=list((WINDOW/'original-process-evidence').rglob('two-scope-chain.json'));assert len(chains)==1
chain=load(chains[0]);assert chain['physical_pg_restart'] and chain['run_assignments']==chain['fixture_finish_calls']==0 and chain['first_case_preserved'] and chain['second_scope_first_case']
assert chain['nodevm_checks']==[19,19,19] and chain['authority_unchanged']
assert chain['starts'][0]['postgres_pid']!=chain['starts'][1]['postgres_pid']
assert len(chain['refusals'])==40
for name in ('independent-parent-and-source-proof','independent-cross-resource'):
 value=load(WINDOW/'scenarios'/ (name+'.json'));inv=value['invariants'];assert inv['business_before']==inv['business_after']
 assert len(inv['denial_audit_delta'])==sum(r['status']==403 for r in value['refusals'])
tokens=set(load(WINDOW/'fixture-token-values.private.json'));assert len(tokens)==30
for node in counts['nodeids']:assert 'test_fresh_setup_two_new_cases_original_worker_full_chain_and_physical_restart' not in node
report=dict(schema=1,scope='INDEPENDENT_FINITE_TWO_ENTERPRISE_TWO_PARK_ORDINARY_SYNTHETIC_DEMO',source_sha=SHA,src_tree=src_tree,baseline_sha=OLD,conclusion='LIMITED_PASS',open_P1=[],open_P2=[],
 independent_window=dict(path=WINDOW.name,counts=counts,controller=control,pytest_main_seconds=runtime['pytest_main_seconds'],origins=dict(total=len(origins),frozen=sum(v['matches_frozen'] for v in origins),private_probe=sum(v['matches_independent_probe'] for v in origins),unexpected=0,scripts=scripts,actual_files_rehashed=True)),
 independent_unique_PASS=5,independent_own_unique_PASS=3,actual_root_overlap_nodeids=sorted(overlap),root_single_window_unique_PASS=7,effective_combined_unique_PASS=10,
 counting_policy='Final same-SHA single independent5PASS=3 private negatives+2 actual root overlaps; root7PASS, union10. No independent failure/retry/supplement. Previous same-enterprise A/B and old14 are neither selected nor counted.',
 source_oracle=dict(path='literal-oracle-plan.json',sha256=sha(BASE/'literal-oracle-plan.json'),count=10,unchanged=True),baseline_preservation='frozen-static-validation.json',state_source_validation='demo-state-source-binding-validation.json',
 independent_verified=[
  'Own fresh CLI setup; same retained database hosts two scopes. Only minimal fresh HTTP material/review/confirm and planning observations are used for two source-proof/parent negatives. No explicit ADOPT, dispatch, receipt or complete P1-P5 positive chain is duplicated in this private probe.',
  'Both directions deny foreign Run/preparation/plan/goal/local reads, material edits, old-Run preparation, foreign reviewer and self-consistent other-scope planning SHA.22? exact request totals are in scenario records. Original business table digest and counts stay equal; original403 denial audits are checked separately and exactly.',
  'A genuine reviewer-owned prior5b36 schema1 state is passed only to current serve with PG/Popen forbidden; every original file byte SHA/mode/size remains unchanged. Its sessions file is read only as opaque hash bytes, never parsed, printed, captured as tokens, or published. No old PG/main/failure log or business operation is run.',
  'Fresh private state missing/swapped/foreign-owner scope bindings deny before process creation, preserve the deliberately bad bytes and are retained without repair. The root overlap separately covers missing and5 field mutations.',
  'Each scope independently confirms its own two-resource group in exactly the same interval; fourteen actual bidirectional foreign preview/hold/read/release/group/cancel/mixed-member operations return403. Both original combinations remain unchanged, with zero Run/Case in this private resource probe.',
 ],
 actual_overlap_chain=dict(path=str(chains[0].relative_to(BASE)),proof=chain,actual_API_processes=2,actual_worker_processes=2,actual_PG_restart=True,NodeVM_assertions=[19,19,19],real_browser=False),
 historical_first_development_failure=dict(outcome='1PASS1FAIL root development, not independent test and not final-SHA pass',classification='READ_TIMEOUT_ROOT_CAUSE_UNKNOWN',proof='wip-static-first-failure-review.json',supplement='wip-static-first-failure-supplement.json',boundary='SecondREVALIDATE committed/READY; noCLOSE observed on later read-only inspection. Original action/key/response missing, so exact timed-out action/outcome cannot be reconstructed. Final test-only request metadata and finite read-only timeout sampling preserve20sHTTP/3sSQL/300s deadline. LaterPASS is not evidence of repairing the original unknown cause.'),
 owned_states=dict(observations=states,retained_for_forensics=True,data_not_deleted=True,genuine_old_state_files_hashed=len(old_pre['files']),genuine_old_state_all_hashes_unchanged=True),
 evidence_limits=[
  'Two fixed park/org pairs in one database do not cover the full Cartesian park/org matrix or formal cross-park migration. Existing historical baseline AT04 remains historical.',
  'Distinct resources at the same interval do not prove concurrent shared-resource capacity contention. Private probes add only their finite refused surfaces; original full chain is covered by selected root new main overlap.',
  'Main pytest origins include three actual scripts; source binding covers runtime and lifecycle files. No claim of complete import tracing in every API/worker subprocess.',
  'All30 new own fixture sessions, including second_* roles, are privately captured for redaction. No parent inventory or old session values are parsed. No raw state, sessions, receipt observation, whole mirror or PGdata is published.',
  'Five new owned states are stopped and retained. Two deliberately metadata-invalid states remain invalid; do not describe them as clean ready-to-serve states.',
  'State/source/authority fences are synthetic retained-state checks, not production trust or signed administrator approval. Files under/tmp are not permanent persistence.',
 ],
 runtime_inputs=['Existing nonroot Linux/Python3.12 and repository dependencies including pgserver0.1.4, complete source tree and three lifecycle scripts; no Git required, no package installation here.','Fresh setup only; choose explicit primary or second_* private session keys. Serve only same state schema2/unchanged source, sessions, authority/ACL and scope metadata on a free unprivileged loopback port.','Use current matching owner/reviewer/executor, own catalog/resources and explicit original human review/confirm/adopt/verify/manual receipt; first offer300s and resource windows still apply. Old schema1 is refused and retained, not migrated or reseeded.'],
 remaining_not_run=['Template governance/publication and complete formal AT04/08/35 or entire product acceptance.','Windows/WSL/native install, real browser/Chromium, real identities/Grant/publication/approval/credentials, real business/models/external production.','V4/demo coexistence, Native/formal/resource approval providers remain disabled or rejected; original guards/src unchanged.'],
 source_boundaries=dict(frozen_inputs=820,all_shared_mirror_PREPOST_drift=0,all_8_root_and_independent_maps_equal=True,archives_equal=True,archive_sha256=control['archive_sha256'],private_probe_separate_from_820=True,only_controlled_source_writer='root'),publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json',raw_evidence_manifest='raw-evidence-manifest.json')
# Scenario counts are asserted from actual records, not the prose placeholder.
parent_negative=load(WINDOW/'scenarios/independent-parent-and-source-proof.json')
report['independent_verified'][1]=report['independent_verified'][1].replace('22? exact request totals are in scenario records.',str(len(parent_negative['refusals']))+' exact refused requests are in scenario records.')
write(BASE/'independent-final-review.json',report)
with (BASE/'active-review-path.txt').open('x') as f:f.write(str(BASE)+'\n')

selected=[p for p in BASE.iterdir() if p.is_file() and '.private.' not in p.name]
selected.extend(p for p in WINDOW.iterdir() if p.is_file() and '.private.' not in p.name)
for child in ('scenarios','root-overlap-evidence','original-process-evidence','owned-state-logs'):
    if (WINDOW/child).exists():selected.extend(p for p in (WINDOW/child).rglob('*') if p.is_file())
selected=sorted(set(selected));assert not any(p.name in ('sessions.json','state.json','creation-observation.json') or 'token' in p.name.lower() for p in selected)
fragments=set()
for path in selected:
    for match in re.finditer(r"'(?:enterprise|specialist|executor)': '([A-Za-z0-9_-]+)\.\.\.",path.read_text()):
        if any(t.startswith(match.group(1)) for t in tokens):fragments.add(match.group(1)+'...')
def scrub(value):
    result=value;count=0
    for token in sorted(tokens,key=len,reverse=True):
        n=result.count(token)
        if n:result=result.replace(token,'SYNTHETIC_SESSION_REDACTED');count+=n
    for fragment in sorted(fragments,key=len,reverse=True):
        n=result.count(fragment)
        if n:result=result.replace(fragment,'SYNTHETIC_TRUNCATED_SESSION_REDACTED');count+=n
    for token in sorted(tokens,key=len,reverse=True):
        for size in range(len(token)-1,7,-1):
            for piece in (token[:size],token[-size:]):
                n=result.count(piece)
                if n:result=result.replace(piece,'SYNTHETIC_SESSION_REDACTED');count+=n
    return result,count
mapping=[];publication=[]
for path in selected:
    relative=str(path.relative_to(BASE));raw=path.read_bytes();count=0
    if path.suffix=='.xml':
        original=ET.parse(path).getroot();safe=copy.deepcopy(original)
        for node in safe.iter():
            if node.text is not None:node.text,n=scrub(node.text);count+=n
            if node.tail is not None:node.tail,n=scrub(node.tail);count+=n
            for key,value in tuple(node.attrib.items()):node.attrib[key],n=scrub(value);count+=n
        encoded=ET.tostring(safe,encoding='utf-8',xml_declaration=True) if count else raw;parsed=ET.fromstring(encoded)
        assert [v.attrib for v in original.iter('testcase')]==[v.attrib for v in parsed.iter('testcase')]
        assert [v.tag for v in original.iter()]==[v.tag for v in parsed.iter()]
    else:
        value,count=scrub(raw.decode());encoded=value.encode()
    if count:
        target=BASE/'public'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(encoded)
        public=str(target.relative_to(BASE))
    else:public=relative
    publication.append(public);mapping.append(dict(raw=relative,public=public,raw_sha256=sha(path),public_sha256=hashlib.sha256(encoded).hexdigest(),replacement_count=count))
write(BASE/'raw-public-redaction-map.json',dict(schema=1,files=mapping,replacement_count=sum(v['replacement_count'] for v in mapping),captured_own_launcher_session_values=len(tokens),policy='Only this review5 fresh launcher states and30 actual sessions privately captured via own demo_state fixtures, including second_* keys; no parent inventory or old sessions parsed. Full values and captured fragments/prefixes/suffixes sanitized once if present, with XML node values serialized/parsed preserving case/outcome shape. Retain all raw privately; no sessions/state/creation observation/whole mirror/PGdata/source-fault copy published. Canonical files copied byte-for-byte without second redaction.'))
publication+=['publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json'];assert len(publication)==len(set(publication));publication=sorted(publication)
write(BASE/'publication-files.json',publication)
write(BASE/'raw-evidence-manifest.json',dict(schema=1,source_sha=SHA,self_hash_excluded=True,excludes=['mirror','PGdata','private session/state/creation observation','private token inventory','whole extra source-fault copy'],files=[dict(path=v,sha256=sha(BASE/v),bytes=(BASE/v).stat().st_size) for v in publication if v!='raw-evidence-manifest.json']))
for name in publication:
    value=(BASE/name).read_text();assert not any(t in value or t[:8] in value or t[-8:] in value for t in tokens),name
    if name.endswith('.xml'):ET.parse(BASE/name)
for row in mapping:assert sha(BASE/row['raw'])==row['raw_sha256'] and sha(BASE/row['public'])==row['public_sha256']
print(json.dumps(dict(source_sha=SHA,report_sha256=sha(BASE/'independent-final-review.json'),publication_sha256=sha(BASE/'publication-files.json'),map_sha256=sha(BASE/'raw-public-redaction-map.json'),manifest_sha256=sha(BASE/'raw-evidence-manifest.json'),publication_files=len(publication),replacement_count=sum(v['replacement_count'] for v in mapping),independent_unique_PASS=5,root_unique_PASS=7,overlap=2,combined_unique_PASS=10),sort_keys=True))
