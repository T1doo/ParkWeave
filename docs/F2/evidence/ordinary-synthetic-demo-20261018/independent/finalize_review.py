"""Reconcile frozen evidence and publish once; no project/test/DB execution."""
from pathlib import Path
import copy,hashlib,json,re,xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent;ROOT=Path('/workspace/ParkWeave')
SHA='5b36291a22aae8dd74346ae9f2b54c148a4b1ef0'
WINDOW=BASE/'frozen-5b36291a-window1'
PARENT=ROOT/'.runtime/ordinary-synthetic-demo-20261018/frozen-5b36291a'
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
    return dict(collection=len(ids),nodeids=sorted(ids),phases=phases,JUnit=[v.attrib for v in xml.iter('testsuite')],exact_collection_all_phases_JUnit=True),rows

counts,rows=reconcile(WINDOW);control=load(WINDOW/'controller-result.json');runtime=load(WINDOW/'pytest-result.json')
assert counts['collection']==5 and all(v['outcome']=='passed' for v in rows)
assert control['source_sha']==control['actual_HEAD_at_start']==control['actual_HEAD_at_end']==SHA
assert control['exit_code']==0 and control['frozen_input_count']==814
assert all(not control[k] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
maps=[load(WINDOW/name) for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json')]
assert all(v==maps[0] for v in maps)
origins=load(WINDOW/'module-origins.json')
assert all(v['within_mirror'] and (v['matches_frozen'] or v['matches_independent_probe']) and sha(Path(v['path']))==v['sha256'] for v in origins)
scripts={v['name']:v for v in origins if v['name'].startswith('scripts.')}
assert set(scripts)=={'scripts.ordinary_synthetic_demo','scripts.material_only_demo','scripts.linux_fixture_server'}
probe='test_independent_ordinary_synthetic_demo.py'
private_pre=load(WINDOW/'independent-source-before.json');private_post=load(WINDOW/'independent-source-after.json')
assert private_pre==private_post and private_pre[probe]==sha(BASE/probe)==sha(WINDOW/'mirror/tests'/probe)
write(WINDOW/'probe-version-validation.json',dict(original_PRE_sha256=private_pre[probe],original_POST_sha256=sha(BASE/probe),mirror_POST_sha256=sha(WINDOW/'mirror/tests'/probe),all_equal=True,private_probe_separate_from_814=True))

parent_counts,parent_rows=reconcile(PARENT);parent_control=load(PARENT/'result.json')
assert parent_counts['collection']==11 and all(v['outcome']=='passed' for v in parent_rows)
assert parent_control['head']==SHA and parent_control['exit_code']==0 and parent_control['inputs']==814
assert parent_control['shared_drift']==parent_control['mirror_drift']==[]
assert all(load(PARENT/name)==maps[0] for name in ('shared-before.json','mirror-before.json','shared-after.json','mirror-after.json'))
assert parent_control['archive_sha256']==control['archive_sha256']
ours=set(counts['nodeids']);theirs=set(parent_counts['nodeids']);overlap=ours&theirs
assert len(overlap)==2 and len(ours-theirs)==3 and len(ours|theirs)==14
root_origins=[];parent_mirror=Path(parent_control['mirror'])
for name,value in load(PARENT/'module-origins.json').items():
    file=Path(value['path']);relative=str(file.relative_to(parent_mirror))
    root_origins.append(dict(name=name,relative=relative,recorded_sha256=value['sha256'],actual_sha256=sha(file),matches_frozen=maps[0].get(relative)==value['sha256']==sha(file)))
assert all(v['matches_frozen'] for v in root_origins)
write(BASE/'root-evidence-cross-check.json',dict(source_sha=SHA,root_executed_by_reviewer=False,counts=parent_counts,origins=root_origins,root_origin_scope='Recorded parkweave/test/support modules only; original root observer omitted scripts.*, not an all-subprocess import audit.',independent_main_script_origin_audit=scripts,all_8_input_maps_equal=True,archives_equal=True,actual_overlap=sorted(overlap),independent_only_nodeids=sorted(ours-theirs),root_only_nodeids=sorted(theirs-ours),combined_unique_PASS=14,references={n:sha(PARENT/n) for n in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json')}))

states=load(WINDOW/'owned-demo-state-observations.json');assert len(states)==4
bound={key:value for key,value in maps[0].items() if key.startswith('src/parkweave/') or key in ('scripts/ordinary_synthetic_demo.py','scripts/material_only_demo.py','scripts/linux_fixture_server.py')}
source_checks=[]
for row in states:
    state=Path(row['state_dir']);marker=load(state/'state.json')
    assert row['state_retained'] and row['data_retained'] and not row['stop_unconfirmed']
    assert marker['source']['files']==bound
    raw=json.dumps(bound,sort_keys=True,separators=(',',':')).encode()
    assert hashlib.sha256(raw).hexdigest()==marker['source']['sha256']==row['source_binding']
    source_checks.append(dict(state_dir=str(state),source_files=len(bound),complete_runtime_and_lifecycle_files_match_frozen=True,source_sha256=row['source_binding'],schema_version=row['schema_version'],retained_postmaster_marker=row['postmaster_marker_exists']))
assert sum(row['postmaster_marker_exists'] for row in states)==1
unknown=load(WINDOW/'scenarios/unknown-state-not-adopted.json')
assert unknown['process_creation_attempts']==0 and unknown['unknown_postmaster_marker_retained']
write(BASE/'demo-state-source-binding-validation.json',dict(source_sha=SHA,states=source_checks,unknown_marker_explanation='Exactly1 marker was deliberately written by the independent negative probe after setup had stopped its own PG; its contents are a fake out-of-range PID, Popen was observed0 times. It is retained and is not evidence of a live postmaster. No unknown marker/process was deleted or signalled.',no_state_or_PGdata_published=True))
chains=list((WINDOW/'original-process-evidence').rglob('ordinary-demo-chain.json'));assert len(chains)==1
chain=load(chains[0]);assert chain['physical_postgres_restart'] and chain['worker_processes']==2 and chain['fixture_finish_calls']==0 and chain['run_assignments']==0 and len(chain['cases'])==2
assert chain['starts'][0]['postgres_pid']!=chain['starts'][1]['postgres_pid']
assert chain['nodevm_checks']==[19,19]
tokens=set(load(WINDOW/'fixture-token-values.private.json'));assert len(tokens)==12

report=dict(schema=1,scope='INDEPENDENT_LIMITED_ORDINARY_SYNTHETIC_SETUP_AND_RETAINED_SERVE',source_sha=SHA,src_tree='69c81c4e939095208cb5992a931400bd46156aec',baseline_sha='6067cd3070ef3987d9013b1f47768df667d3f612',conclusion='LIMITED_PASS',open_P1=[],open_P2=[],
 independent_window=dict(path=WINDOW.name,counts=counts,controller=control,pytest_main_seconds=runtime['pytest_main_seconds'],origins=dict(total=len(origins),frozen=sum(v['matches_frozen'] for v in origins),private_probe=sum(v['matches_independent_probe'] for v in origins),unexpected=0,scripts=scripts,actual_files_rehashed=True)),
 independent_unique_PASS=5,independent_own_unique_PASS=3,actual_root_overlap_nodeids=sorted(overlap),root_single_window_unique_PASS=11,effective_combined_unique_PASS=14,
 counting_policy='One actual final-SHA independent5 collection/setup/call/teardown/JUnit PASS=3 private+2 root overlaps; root actual11PASS, exact union14. No independent failure/retry/supplement. Prior planning/P5/configuration or broader matrices are not rerun/recounted as this demo.',
 source_oracle=dict(path='literal-oracle-plan.json',sha256=sha(BASE/'literal-oracle-plan.json'),count=9,unchanged=True),contract_transition='frozen-contract-diff.patch',baseline_preservation='frozen-static-validation.json',state_source_validation='demo-state-source-binding-validation.json',
 verified=[
  'Gitless private archive works with complete source binding; an additional Gitless source copy plus unrelated documentation has the same content hash and actual demo/lifecycle/store module paths in that copy. Altering only its copied material lifecycle helper denies before PostgreSQL. Frozen814 files are never edited.',
  'Initial state/session/receipt-observation/entry-lock files and parent directory are private; session bytes match the bound hash and setup stdout contains no token/DSN. A controlled sessions mode drift is denied without server repair; parent state remains0700 and the negative state is retained.',
  'A held original entry lock, an independently fabricated unknown postmaster PID marker and an old material-only directory prefix stub all reject with observed0 process-creation attempts. No old material setup/database is created and no unknown state/listener/process is adopted/deleted/signalled.',
  'Only a fresh owned fake cluster receives the negative pg_read_all_data membership. Actual serve rejects before API/worker launch, stops its exact validation PG child, retains state/session bytes and does not repair membership. Original business and Run assignment remain0.',
  'Executed root overlap from actual fresh setup: original ordinary worker creates new Runs/Cases; explicit material/review/confirm/planning-preview/ADOPT and original P1-P5 complete A, two-resource link, manual receipt, local revalidate/close and owner VERIFY; physical PG/API/worker restart cold-reads same A/TXT, then different new B input completes with new identities while A stays unchanged.',
  'Executed root live creation-receipt gate denies a plain Store before connection. Root11 additionally covers business/SQL ACL drift, busy-port listener retention, setup failure, exact owned child failure cleanup and unchanged original provider guards; those extra root nodes were not separately rerun here.'
 ],
 actual_two_case_chain=dict(path=str(chains[0].relative_to(BASE)),proof=chain,actual_API_processes=2,actual_worker_processes=2,actual_PG_restart=True,NodeVM_assertions=[19,19],real_browser=False),owned_states=dict(observations=states,retained_for_forensics=True,data_not_deleted=True,unknown_marker=unknown),
 evidence_limits=[
  'Old material-only refusal is exercised with its actual directory-prefix gate on an owned empty stub. No real old material database/setup is adopted or rerun.',
  'Role membership drift is the additional actual SQL negative here; role flags/table ACL and setup/child failures are covered by source review/root11, not a new full role/DDL matrix.',
  'Main pytest source origins include actual scripts.ordinary_synthetic_demo/material_only_demo/linux_fixture_server SHA checks. The copied diagnostic audits its3 module paths and complete source binding. Actual API/worker subprocesses use original source selection and bound files; no claim of separate full child import instrumentation.',
  'Exactly12 new launcher-created session values are privately captured; no parent token inventory is read. Preserved state includes one deliberately nonprivate-mode session file under its still0700 private parent and one deliberately fabricated PID marker, each denied by serve. These are retained negative cases, not a clean ready-to-serve installation claim.',
  'Content/cluster/database/authority/SQL ACL checks are retained synthetic-state fences, not production trust or administrator approval. Files under/tmp can still be removed by the platform; persistence across this observed restart is not a permanent-storage guarantee.'
 ],
 runtime_inputs=['Existing nonroot Linux/Python3.12 and repository dependencies including pgserver0.1.4; this launcher performs no package installation/download.','Full source tree including src and the3 lifecycle scripts; .git is unnecessary. setup creates only its own new private Unix-socket cluster/database and fixed marked SYNTHETIC initial state.','Use serve with that same owned state and an available unprivileged loopback port; source/session/authority/SQL ACL/private files must remain unchanged. Normal current owner/reviewer/executor decisions and original deadlines still apply.'],
 remaining_not_run=['Real identity/Grant/capability/assignment/catalogue publication/approval/credential/production installation or real institution/business/model execution.','Windows/native formal AT35/real browser and complete project acceptance; this is bounded Linux/HTTP/worker and original HTML NodeVM evidence.','V4/local-demo provider combination, formal source/Native/resource-approval providers and strict approval delivery are not enabled or bypassed; old guards/src remain unchanged.'],
 source_boundaries=dict(frozen_inputs=814,all_shared_mirror_PREPOST_drift=0,all_8_root_and_independent_maps_equal=True,archives_equal=True,archive_sha256=control['archive_sha256'],private_probe_separate_from_814=True,modified_source_negative_only_in_additional_private_copy=True),
 publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json',raw_evidence_manifest='raw-evidence-manifest.json')
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
write(BASE/'raw-public-redaction-map.json',dict(schema=1,files=mapping,replacement_count=sum(v['replacement_count'] for v in mapping),captured_own_launcher_session_values=len(tokens),policy='Only this review4 fresh launcher states and12 actual sessions privately captured via own demo_state fixtures; no parent inventory. Full values and captured fragments/prefixes/suffixes sanitized once if present, with XML node values serialized/parsed preserving case/outcome shape. Retain all raw privately; no sessions/state/creation observation/whole mirror/PGdata/source-fault copy published. Canonical files copied byte-for-byte without second redaction.'))
publication+=['publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json'];assert len(publication)==len(set(publication));publication=sorted(publication)
write(BASE/'publication-files.json',publication)
write(BASE/'raw-evidence-manifest.json',dict(schema=1,source_sha=SHA,self_hash_excluded=True,excludes=['mirror','PGdata','private session/state/creation observation','private token inventory','whole extra source-fault copy'],files=[dict(path=v,sha256=sha(BASE/v),bytes=(BASE/v).stat().st_size) for v in publication if v!='raw-evidence-manifest.json']))
for name in publication:
    value=(BASE/name).read_text();assert not any(t in value or t[:8] in value or t[-8:] in value for t in tokens),name
    if name.endswith('.xml'):ET.parse(BASE/name)
for row in mapping:assert sha(BASE/row['raw'])==row['raw_sha256'] and sha(BASE/row['public'])==row['public_sha256']
print(json.dumps(dict(source_sha=SHA,report_sha256=sha(BASE/'independent-final-review.json'),publication_sha256=sha(BASE/'publication-files.json'),map_sha256=sha(BASE/'raw-public-redaction-map.json'),manifest_sha256=sha(BASE/'raw-evidence-manifest.json'),publication_files=len(publication),replacement_count=sum(v['replacement_count'] for v in mapping),independent_unique_PASS=5,root_unique_PASS=11,overlap=2,combined_unique_PASS=14),sort_keys=True))
