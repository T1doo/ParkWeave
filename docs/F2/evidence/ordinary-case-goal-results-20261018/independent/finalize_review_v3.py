"""Additive v3 evidence only. Original canonical116 and shadows never rewritten."""
from pathlib import Path
import copy,hashlib,json,re,xml.etree.ElementTree as ET
base=Path(__file__).resolve().parent;root=Path('/workspace/ParkWeave')
source='33aef7ab8f297c52bbb15d1ae0930ac33a253d7e';window=base/'frozen-33aef7ab-window3';recheck=base/'frozen-33aef7ab-lock-recheck-window4';parent=root/'.runtime/ordinary-case-goal-results-20261018/frozen-33aef7ab'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
def write(p,v):
    with p.open('x') as f:f.write(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def verify(path):
    rows=load(path/'collection.json');ids=[x['nodeid'] if isinstance(x,dict) else x for x in rows];assert len(ids)==len(set(ids))
    calls=[json.loads(x) for x in (path/'calls.jsonl').read_text().splitlines()]
    xml=ET.parse(path/'results.xml').getroot();cases=list(xml.iter('testcase'))
    junit=[x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in cases];assert len(ids)==len(junit) and set(ids)==set(junit)
    phases={p:{s:sum(x['when']==p and x['outcome']==s for x in calls) for s in ('passed','failed','skipped')} for p in ('setup','call','teardown')}
    for p in phases:
        actual=[x['nodeid'] for x in calls if x['when']==p];assert len(actual)==len(ids) and set(actual)==set(ids)
    return dict(collection=len(ids),nodeids=sorted(ids),phases=phases,JUnit=[x.attrib for x in xml.iter('testsuite')],exact_collection_phases_JUnit_nodeids=True),calls
immutable=load(base/'canonical-v1-immutability-pre-v3.json');assert immutable['publication_count']==116
assert {p:sha(base/p) for p in immutable['files']}==immutable['files']
prior=load(base/'independent-final-review.json');assert prior['source_sha']=='8e7e5b6e6e374ec3caac44e5b8b112744f35222f'
# Revalidate both old execution windows and preserve their existing proof bytes.
for old in prior['independent_windows']:
    path=base/old['path'];actual,_=verify(path);assert actual==old['counts']
    assert load(path/'independent-probe-mirror-hash.json')==old['probe']
    assert all(load(path/'controller-result.json')[k]==[] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
counts,calls=verify(window);controller=load(window/'controller-result.json');runtime=load(window/'pytest-result.json');origins=load(window/'module-origins.json')
failure_node='tests/test_ordinary_case_goal_results.py::test_actual_last_pg_lock_wait_crosses_first_deadline_without_false_current_or_commit[VERIFY]'
assert counts['collection']==8 and counts['phases']['call']['passed']==7 and counts['phases']['call']['failed']==1
assert [x['nodeid'] for x in calls if x['outcome']=='failed']==[failure_node]
assert controller['source_sha']==controller['actual_HEAD_at_start']==controller['actual_HEAD_at_end']==source and controller['exit_code']==1 and controller['frozen_input_count']==803
assert all(controller[k]==[] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
assert all(x['matches_frozen'] or x['matches_independent_probe'] for x in origins)
probe_name='test_independent_ordinary_goal_results.py';original=load(window/'independent-source-before.json')[probe_name]
proof=dict(private_original_PRE_sha256=original,mirror_PRE_sha256_from_exact_copy=original,mirror_POST_sha256=sha(window/'mirror/tests'/probe_name),equal=original==sha(window/'mirror/tests'/probe_name));assert proof['equal'] and original==sha(base/probe_name)
assert original==prior['independent_windows'][1]['probe']['mirror_POST_sha256'],'v2 probe unchanged'
write(window/'independent-probe-mirror-hash.json',proof)
final_window=dict(path=window.name,source_sha=source,role='FINAL_SHA_MAIN_WINDOW_7PASS_1_UNOBSERVED_WAIT_FAILURE',counts=counts,controller=controller,pytest_main_seconds=runtime['pytest_main_seconds'],probe=proof,
 origins=dict(total=len(origins),frozen=sum(x['matches_frozen'] for x in origins),private_probe=sum(x['matches_independent_probe'] for x in origins),unexpected=0),fixture_names=runtime['fixture_names'],owned_pg=load(window/'owned-pg-after-exit.json'),failed_nodeids=[failure_node])
rcounts,rcalls=verify(recheck);rcontrol=load(recheck/'controller-result.json');rruntime=load(recheck/'pytest-result.json');rorigins=load(recheck/'module-origins.json')
assert rcounts['nodeids']==[failure_node] and all(x['outcome']=='passed' for x in rcalls)
assert rcontrol['source_sha']==rcontrol['actual_HEAD_at_start']==rcontrol['actual_HEAD_at_end']==source and rcontrol['exit_code']==0 and rcontrol['frozen_input_count']==803
assert all(rcontrol[k]==[] for k in ('shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'))
assert all(x['matches_frozen'] for x in rorigins) and rcontrol['archive_sha256']==controller['archive_sha256']
rpre=load(recheck/'independent-source-before.json')[probe_name]
rproof=dict(private_original_PRE_sha256=rpre,mirror_PRE_sha256_from_exact_copy=rpre,mirror_POST_sha256=sha(recheck/'mirror/tests'/probe_name),equal=rpre==sha(recheck/'mirror/tests'/probe_name));assert rproof['equal'] and rpre==original
write(recheck/'independent-probe-mirror-hash.json',rproof)
recheck_window=dict(path=recheck.name,source_sha=source,role='FINAL_SHA_SINGLE_ORIGINAL_NODE_SUPPLEMENT_PASS',counts=rcounts,controller=rcontrol,pytest_main_seconds=rruntime['pytest_main_seconds'],probe=rproof,
 origins=dict(total=len(rorigins),frozen=sum(x['matches_frozen'] for x in rorigins),private_probe=sum(x['matches_independent_probe'] for x in rorigins),unexpected=0),fixture_names=rruntime['fixture_names'],owned_pg=load(recheck/'owned-pg-after-exit.json'),failed_nodeids=[],attribution='lock-recheck-attribution-v3.json')
root_counts,root_calls=verify(parent);root_result=load(parent/'result.json')
assert root_result['head']==source and root_result['exit_code']==0 and root_result['inputs']==803 and root_counts['collection']==34
assert all(x['outcome']=='passed' for x in root_calls) and root_result['shared_drift']==root_result['mirror_drift']==[]
ours={x['nodeid'] for x in calls if x['when']=='call' and x['outcome']=='passed'}|{x['nodeid'] for x in rcalls if x['when']=='call' and x['outcome']=='passed'};assert ours==set(counts['nodeids'])
theirs=set(root_counts['nodeids']);overlap=ours&theirs
assert len(overlap)==3 and len(ours-theirs)==5 and len(ours|theirs)==39
frozen=load(window/'mirror-before.json');root_mirror=Path(root_result['mirror'])
origin_checks=[dict(module=name,relative=str(Path(v['path']).relative_to(root_mirror)),matches_frozen=frozen.get(str(Path(v['path']).relative_to(root_mirror)))==v['sha256']) for name,v in load(parent/'module-origins.json').items()]
assert all(x['matches_frozen'] for x in origin_checks)
write(base/'root-evidence-cross-check-v3.json',dict(source_sha=source,counts=root_counts,origin_checks=origin_checks,actual_overlap=sorted(overlap),effective_combined_unique_PASS=39,executed_by_independent_reviewer=False,
 references={n:sha(parent/n) for n in ('result.json','collection.json','calls.jsonl','results.xml','module-origins.json','shared-before.json','shared-after.json','mirror-before.json','mirror-after.json') if (parent/n).exists()}))
html=[]
for path in sorted((window/'original-process-evidence').rglob('summary.json')):
    value=load(path);html.append(dict(path=str(path.relative_to(base)),assertions=value.get('assertions'),checks=value.get('checks'),state=value.get('state'),calls=len(value.get('calls',[])),real_browser=False))
post=dict(source_sha=source,original_source='8e7e5b6e6e374ec3caac44e5b8b112744f35222f',original_canonical_files=116,
 old_publication_list_sha256=sha(base/'publication-files.json'),all_original_canonical_bytes_unchanged=True,
 before=immutable['files'],after={p:sha(base/p) for p in immutable['files']})
assert post['before']==post['after'];write(base/'canonical-v1-immutability-post-v3.json',post)
report=copy.deepcopy(prior)
report.update(source_sha=source,publication_revision=3,conclusion='LIMITED_PASS_FINAL_P1_P2_GUARD_AND_CURRENT_SCOPE_ANNOTATION',independent_effective_unique_PASS=8,independent_new_unique_PASS=5,
 actual_root_overlap_nodeids=sorted(overlap),root_final_unique_PASS=34,effective_combined_unique_PASS=39,publication_list='publication-files-v3.json',raw_public_map='raw-public-redaction-map-v3.json',raw_evidence_manifest='raw-evidence-manifest-v3.json')
for old in report['independent_windows']:old['role']='HISTORICAL_NOT_TRANSFERRED'
report['independent_windows'].extend([final_window,recheck_window])
report['counting_policy']='Only final33ae source counts: main8 collection/setup/teardown with7 callPASS1FAIL; same failed original node supplement1PASS, effective unique8=5 own+3 root overlaps, root34 unique union39. Never described as one8PASS window; original missing response remains UNKNOWN. Historical163e independent5PASS/3FAIL(root32PASS), intermediate8e7 independent8PASS/root34PASS retained without transfer or accumulation. Previous54 and other slices neither rerun nor counted.'
report['intermediate_source']=dict(source_sha=prior['source_sha'],report='independent-final-review.json',report_sha256=sha(base/'independent-final-review.json'),old_publication='publication-files.json',old_map='raw-public-redaction-map.json',old_manifest='raw-evidence-manifest.json',effective_unique_PASS=8,root_unique_PASS=34,status='HISTORICAL_NOT_TRANSFERRED')
report.pop('nonblocking_display_note',None)
report['final_lock_observation_failure']='window3-lock-observation-failure.json'
report['final_single_node_supplement_attribution']='lock-recheck-attribution-v3.json'
report['diagnostic_sources']=load(base/'lock-recheck-attribution-v3.json')['diagnostic_source_sha256']
report['display_scope_resolution']=dict(historical_note='preview-contract-wording-note.json',resolved=True,evidence='annotation-source-transition-v3.json',protected_AST_and_file_checks=15,
 current_DI_only_metadata={'contract':'CASE_STEP_ASSIGNMENT_V1','run_access_granted':False},
 scope='Current bounded-planning and service-plan outer views only; original registry, ADOPT/adoption_preview, contract/source hashes, goal-results and pack algorithm unchanged. Current original full HTML process checks both exact metadata and visible limited-step explanation. No Run right or marker-based permission selection added.')
report['old_canonical_immutability']=dict(original_files=116,pre='canonical-v1-immutability-pre-v3.json',post='canonical-v1-immutability-post-v3.json',all_bytes_unchanged=True,old_shadows_reused_without_redaction=True)
report['source_boundaries'].update(root_and_final_independent_archive_equal=root_result['archive_sha256']==controller['archive_sha256'],root_recorded_origins_verified=len(origin_checks),root_cross_check='root-evidence-cross-check-v3.json')
report['actual_full_HTML']=html
write(base/'independent-final-review-v3.json',report)
with (base/'active-review-path-v3.txt').open('x') as f:f.write(str(base)+'\n')
# Old canonical metadata and every old shadow are reused exactly. Sanitize only
# newly generated third-window files with reviewer-owned third-window sessions.
selected=[base/n for n in ('finalize_review_v3.py','canonical-v1-immutability-pre-v3.json','canonical-v1-immutability-post-v3.json','annotation-source-transition-v3.json','root-evidence-cross-check-v3.json','independent-final-review-v3.json','active-review-path-v3.txt','window3-controller.stdout','window3-controller.stderr','window4-controller.stdout','window4-controller.stderr','window3-lock-observation-failure.json','lock-recheck-attribution-v3.json','execute_review_lock_diagnostic_v3.py','run_lock_recheck_v3.py')]
for path in (window,recheck):
    selected.extend(p for p in path.iterdir() if p.is_file() and '.private.' not in p.name)
    for sub in ('scenarios','root-overlap-evidence','original-process-evidence'):
        if (path/sub).exists():selected.extend(p for p in (path/sub).rglob('*') if p.is_file())
new_tokens=set(load(window/'fixture-token-values.private.json'))|set(load(recheck/'fixture-token-values.private.json'));all_tokens=set(new_tokens)
for old in prior['independent_windows']:all_tokens.update(load(base/old['path']/'fixture-token-values.private.json'))
truncated=set()
for path in selected:
    if path.suffix=='.xml':text='\n'.join((x.text or '') for x in ET.parse(path).getroot().iter())
    else:text=path.read_text()
    for match in re.finditer(r"'(?:fixture-[abc]|prep-specialist-fixture-[abc]|executor-[abc]|unassigned)': '([A-Za-z0-9_-]+)\.\.\.",text):
        prefix=match.group(1)
        if any(t.startswith(prefix) for t in new_tokens):truncated.add(prefix+'...')
def scrub(s):
    count=0
    for t in sorted(new_tokens,key=len,reverse=True):
        for piece in (t,t[:12]):
            n=s.count(piece)
            if n:s=s.replace(piece,'SYNTHETIC_SESSION_REDACTED');count+=n
    for piece in sorted(truncated,key=len,reverse=True):
        n=s.count(piece)
        if n:s=s.replace(piece,'SYNTHETIC_TRUNCATED_SESSION_REDACTED');count+=n
    return s,count
old_map=load(base/'raw-public-redaction-map.json');mapped=copy.deepcopy(old_map['files']);files=set(load(base/'publication-files.json'))
for path in sorted(set(selected)):
    rel=str(path.relative_to(base));raw=path.read_bytes();count=0
    if path.suffix=='.xml':
        original=ET.parse(path).getroot();safe=copy.deepcopy(original)
        for node in safe.iter():
            if node.text is not None:node.text,n=scrub(node.text);count+=n
            if node.tail is not None:node.tail,n=scrub(node.tail);count+=n
            for key,value in tuple(node.attrib.items()):node.attrib[key],n=scrub(value);count+=n
        public=ET.tostring(safe,encoding='utf-8',xml_declaration=True) if count else raw
        def shape(n):return (n.tag,n.attrib,n.text,n.tail,[shape(c) for c in n])
        parsed=ET.fromstring(public);assert shape(parsed)==shape(safe)
        assert [n.attrib for n in original.iter('testcase')]==[n.attrib for n in parsed.iter('testcase')]
        assert [n.tag for n in original.iter()]==[n.tag for n in parsed.iter()]
    else:
        value,count=scrub(raw.decode());public=value.encode()
    if count:
        destination=base/'public-v3'/rel;destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as f:f.write(public)
        pub=str(destination.relative_to(base))
    else:pub=rel
    files.add(pub);mapped.append(dict(raw=rel,public=pub,raw_sha256=sha(path),public_sha256=hashlib.sha256(public).hexdigest(),replacement_count=count))
new_metadata=('raw-public-redaction-map-v3.json','publication-files-v3.json','raw-evidence-manifest-v3.json');files.update(new_metadata)
represented={x['public'] for x in mapped}
for rel in sorted(files):
    if rel in represented or rel in new_metadata:continue
    mapped.append(dict(raw=rel,public=rel,raw_sha256=sha(base/rel),public_sha256=sha(base/rel),replacement_count=0))
assert len({x['public'] for x in mapped})==len(mapped)
write(base/'raw-public-redaction-map-v3.json',dict(schema=3,files=sorted(mapped,key=lambda x:x['public']),replacements_total=sum(x['replacement_count'] for x in mapped),
 prior_map='raw-public-redaction-map.json',prior_map_sha256=sha(base/'raw-public-redaction-map.json'),new_window_replacements=sum(x['replacement_count'] for x in mapped if x['raw'].startswith(window.name) or x['raw'].startswith(recheck.name)),
 policy='Every original canonical file and old shadow reused byte-for-byte. Original raw/public pairs copied from historical map, never redacted again. Only new third/fourth-window files scanned/sanitized using their reviewer-owned fixture values and captured truncated fragments and XML text/tail/attribute serialization. Private inventories, mirror, PGdata/config excluded; no root private-synthetic-tokens accessed.'))
publication=sorted(files);write(base/'publication-files-v3.json',publication)
write(base/'raw-evidence-manifest-v3.json',dict(schema=3,source_sha=source,publication_list='publication-files-v3.json',raw_public_map='raw-public-redaction-map-v3.json',self_hash_excluded_to_avoid_recursion=True,
 old_canonical_files=116,old_canonical_unchanged=True,excludes=['mirror','PGdata','private tokens/config','*.private.json'],
 files=[dict(path=rel,sha256=sha(base/rel),bytes=(base/rel).stat().st_size) for rel in publication if rel!='raw-evidence-manifest-v3.json']))
assert {p:sha(base/p) for p in immutable['files']}==immutable['files']
for rel in publication:
    text=(base/rel).read_text();assert not any(t in text or t[:12] in text for t in all_tokens),rel
    assert not any(t in text for t in truncated),rel
    if rel.endswith('.xml'):ET.parse(base/rel)
for item in mapped:assert sha(base/item['raw'])==item['raw_sha256'] and sha(base/item['public'])==item['public_sha256']
assert len(publication)==len(set(publication))
print(json.dumps(dict(source_sha=source,report_sha256=sha(base/'independent-final-review-v3.json'),publication_files=len(publication),publication_sha256=sha(base/'publication-files-v3.json'),
 map_sha256=sha(base/'raw-public-redaction-map-v3.json'),manifest_sha256=sha(base/'raw-evidence-manifest-v3.json'),old_canonical_unchanged=116,
 independent_unique_PASS=8,root_unique_PASS=34,overlap=3,combined_unique_PASS=39,new_window_replacements=sum(x['replacement_count'] for x in mapped if x['raw'].startswith(window.name) or x['raw'].startswith(recheck.name))),sort_keys=True))
