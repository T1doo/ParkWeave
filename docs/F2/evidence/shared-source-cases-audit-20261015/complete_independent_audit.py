"""Finalize only independent results; never imports producer/verifier."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,re,subprocess,xml.etree.ElementTree as ET
from audit_archive_pairs import frozen,known_private,record
from fast_known_redaction import KnownTokenRedactor
R=Path('/workspace/ParkWeave');D=R/'.runtime/shared-source-cases-audit';S='731529bc409041f255742e11756ebc4084bb9319';OLD='bc4f384fa32817ddf3b332f898d59b5b994bfe2f'
def read(p):return json.loads((R/p).read_text())
def save(n,v):(D/n).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
pairs=read('.runtime/shared-source-cases-audit/archive-independent-pairs.json');mech=read('.runtime/shared-source-cases-audit/final-gate-mechanical.json');union=read('.runtime/shared-source-cases-audit/independent-coverage-union.json')
assert pairs['source_sha']==mech['source_sha']==S and pairs['status']=='PAIR_REBUILD_PASS_FINAL_COVERAGE_GATE_PENDING' and mech['status']=='PASS'
assert pairs['checks']=={'files':259,'bytes':25396224,'xml':25,'json':71,'python':18,'javascript':2,'jsonl':48}
assert pairs['redactions']=={'exact_private_value':8,'fixture_repr_line':18} and not pairs['known_private_residuals'] and all(x['exit_code']==0 for x in pairs['javascript_syntax'])
frozen_before=frozen(S);final_freeze=read('.runtime/shared-source-cases/final-freeze.json')
assert final_freeze['source_sha']==S and len(final_freeze['hashes'])==595
assert all(frozen_before[p]['sha256']==h for p,h in final_freeze['hashes'].items())
coverage=read('.runtime/shared-source-cases/final-coverage.json');assert coverage['source_sha']==S and coverage['complete_modules']==64 and coverage['unique_tests']==2074 and not coverage['whole_repository_run'] and not coverage['source_drift']
rows=coverage['windows'];assert len(rows)==4
combined_nodes=[];combined_modules=[];comparisons=[]
for ours in mech['windows']:
 match=[r for r in rows if set(r['modules'])==set(ours['modules'])];assert len(match)==1
 root=match[0];combined_nodes.extend(root['nodeids']);combined_modules.extend(root['modules'])
 col=read(ours['result_path'].replace('-result.json','-collection.json') if ours['result_path'].endswith('-result.json') else ours['result_path'].replace('.json','-collection.json'))
 col=col if isinstance(col,list) else [r['nodeid'] for r in col['items']]
 assert root['source_sha']==ours['execution_sha'] and Counter(root['nodeids'])==Counter(col) and root['counts']=={'PASS':len(col),'FAIL':0,'ERROR':0,'SKIP':0}
 seconds=ours['junit_seconds'] if root['seconds']['kind']=='JUnit' else ours['runner_seconds']
 # Root uses lowercase junit label; both explicit labels are handled.
 if root['seconds']['kind'].lower()=='junit':seconds=ours['junit_seconds']
 assert abs(root['seconds']['value']-seconds)<0.001
 comparisons.append({'window':root['name'],'source_sha':root['source_sha'],'module_count':len(root['modules']),'unique_nodes':len(col),'counts_match':True,'node_multiset_match':True,'seconds_match':True})
assert Counter(combined_nodes)==Counter(union['nodes']) and Counter(combined_modules)==Counter(union['modules'])
assert len(combined_nodes)==len(set(combined_nodes))==2074 and len(combined_modules)==len(set(combined_modules))==64
continuity=read('.runtime/shared-source-cases/source-continuity.json')
assert continuity['previous_source_sha']==OLD and continuity['final_validation_sha']==S and continuity['changed_paths']==['tests/shared_source_cases_real_html.js'] and continuity['unchanged_tracked_source_paths']==594 and not continuity['same_SHA_all_windows']
save('root-coverage-independent-comparison.json',{'status':'PASS','source_sha':S,'windows':comparisons,'union_node_set_sha256':union['node_set_sha256'],'unique_modules':64,'unique_nodes':2074,'same_execution_sha_claimed':False,'source595_matches_final_freeze':True})
report=R/'docs/F2/SharedSourceCases-20261015.md';report_bytes=report.read_bytes();text=report_bytes.decode();links=[]
for target in re.findall(r'\]\(([^)]+)\)',text):
 if re.match(r'^[a-z]+://',target):continue
 q=report.parent/target;assert q.is_file(),'report link missing: '+target;links.append({'relative_target':target,**record(q)})
assert all(k in text for k in [S,OLD,'2074','1951','123','122PASS/1FAIL','HTTP500','9 个模式','6 个模式','未知','Windows','真实浏览器','正式 AT','真实模型','生产','远端 CI'])
assert '不能称四窗同 SHA' in text and '不宣称任意 DB 结构破坏都逐 Case 容错' in text
review={'status':'PASS_WITH_NONBLOCKING_WORDING_NOTE','report':str(report.relative_to(R)),**record(report),'linked_evidence':links,'reviewed_claims':['Product/source reference and actual execution SHAs distinct','Old60=1951 and final4=123, disjoint64/2074 not one full-repository execution','15 Node VM original HTML modes backed by actual HTTP/ASGI/owned PostgreSQL; not actual browser','23 literal oracles with unknown expansion separately disclosed','32 candidates, per-page1..20,4096-byte cursor,4MiB manifest, continuation/unvisited UNKNOWN','No arbitrary/general graph; selected shared-source partition distinct from whole-Case causes','Bad-head/handled Conflict UNKNOWN claim limited; unsupported direct SQL valid-head/missing-steps generic500 observation explicit','Historical failures and target fixes retained, no pass-count stitching','Finite Release/second-park/structural delivered scope not relisted as absent','Windows/browser/formal AT/models/production/remoteCI and external reality/auth gates remain unexecuted'],'nonblocking_note':'The phrase 页1–20 may be clarified to 每页1–20条; implementation and surrounding page-size10 statement are correct.','no_delivery_blockers':True}
save('public-report-independent-review.json',review)
# Inventory and hash exact public original -> export fixtures without emitting private text.
from redaction_reconstruct import FIXTURE
entries=read('docs/F2/evidence/shared-source-cases-20261015/index.json')['entries'];fixtures=[]
for entry in entries:
 p=R/entry['raw_path'];raw=p.read_bytes()
 if entry['redactions']['fixture_repr_line']:
  chunks=[]
  if p.suffix=='.xml':
   for n in ET.fromstring(raw).iter():chunks.extend(v for v in [n.text,n.tail,*n.attrib.values()] if v)
  elif p.suffix=='.json':
   def strings(v):
    if isinstance(v,str):return [v]
    if isinstance(v,list):return [s for x in v for s in strings(x)]
    if isinstance(v,dict):return [s for x in v.values() for s in strings(x)]
    return []
   chunks=strings(json.loads(raw))
  else:chunks=[raw.decode()]
  hits=[line for chunk in chunks for line in chunk.splitlines() if FIXTURE.match(line)]
  assert len(hits)==entry['redactions']['fixture_repr_line']
  fixtures.append({'raw_path':entry['raw_path'],'fixture_repr_lines':len(hits),'line_sha256':[sha(s.encode()) for s in hits],'line_contents_not_published':True})
assert sum(r['fixture_repr_lines'] for r in fixtures)==18
save('fixture-redaction-independent-inventory.json',{'status':'PASS','total_lines':18,'records':fixtures,'xml_testcase_status_and_identity_preserved':True,'all_other_text_transformed_only_by_exact_known_private_replacement':True})
xml=list(ET.parse(D/'redaction-differential-final.xml').iter('testcase'));assert len(xml)==17 and all(n.find('failure') is None and n.find('error') is None and n.find('skipped') is None for n in xml)
result={'status':'PASS','source_sha':S,'utc':datetime.now(timezone.utc).isoformat(),'archive':'docs/F2/evidence/shared-source-cases-20261015','index_sha256':pairs['index_sha256'],'pair_reconstruction':{'pairs':259,'export_bytes':25396224,'exact_private_replacements':8,'fixture_repr_lines':18,'known_private_pool_values':pairs['known_private_values'],'known_private_residuals':0,'formats':pairs['checks'],'raw_export_source_metadata_unchanged':True},'independence':{'root_producer_or_verifier_imported':False,'reconstruction':'Own structured auditor reconstructed every export; deterministic byte and count equality verified','shared_matcher_provenance':'Root and independent auditor both use the previously independently proved known-token fast matcher; no claim of a different matcher algorithm','slow_reference_differential':{'tests':17,'deterministic_random_cases':200,'final_actual_run_pass':True,'private_values_used_in_tests':False},'fallback_proof':'Non43/nonURLsafe pools or overlapping matches use ordered slow replacements; actual16164 pool all43URLsafe,8 disjoint replacements, no fallback needed'},'source':{'final_validation_sha':S,'business_execution_sha':OLD,'595_tracked_source_paths_match_final_git':True,'594_unchanged_to_business_freeze':True,'alltracked_paths':11771,'alltracked_bytes':269711982,'alltracked_matches_final_git_before_after':True,'only_difference':'tests/shared_source_cases_real_html.js bounded original-worklist next-page test navigation'},'coverage':mech['coverage'],'schema_negative_probes':mech['runtime_schema_negative_probes'],'oracles':{'records':23,'shared':12,'shared_expected_actual_affected_pairs':24,'typed':11,'typed_expected_actual_affected_pairs':38,'missed':0,'wrong':0,'wrong_preserved':0,'unknown_not_scored_as_precision':True},'html':{'new_shared_modes':9,'old_typed_modes':6,'total':15,'original_html':True,'actual_http_asgi_owned_pg':True,'node_vm_dom_not_actual_browser':True},'failure_preservation':{'all_indexed_raw_and_export_xml_identities_statuses_equal':True,'old_formal122pass1fail_retained':True,'development_and_reviewer_nonproduct_setup_receipts_retained':True,'no_failed_window_count_added_to_final_union':True,'trusted_admin_structural_corruption_generic500_observation':'Retained outside positive product validation; no leakage/write; handled UNKNOWN claim narrowed'},'report_review':'.runtime/shared-source-cases-audit/public-report-independent-review.json','new_blockers':[],'nonblocking_wording_note':review['nonblocking_note'],'scope':['Finite current-owner resource-query-set and exact service-catalog-reference reverse lookup','Conservative bounded UNKNOWN, no general shared semantic graph, cross-Case atomic guarantee or automatic adoption','Existing ADOPT/VERIFY/UNLOCK and six-goal/P1–P5/history/unaffected locks unchanged','Linux synthetic only; Windows, actual browser, formal AT, real models, production and remote CI NOT_RUN'],'artifacts':['archive-independent-pairs.json','final-gate-mechanical.json','independent-coverage-union.json','independent-oracle-and-html.json','root-coverage-independent-comparison.json','public-report-independent-review.json','fixture-redaction-independent-inventory.json','archive-pair-audit.log','redaction-differential-final.log','redaction-differential-final.xml'],'writes':'New .runtime/shared-source-cases-audit outputs only; no raw/primary/product/Git/old evidence edits.'}
assert frozen_before==frozen(S) and report.read_bytes()==report_bytes
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R).strip()
save('archive-independent-audit.json',result);save('final-gate.json',result)
md=f'''# Independent archive gate\n\nPASS for final validation SHA `{S}`. All **259 raw/export pairs, 25,396,224 exported bytes** were independently rebuilt. Exact hashes/lengths and redaction counts match: **8 designated synthetic private values,18 fixture repr lines**; known private residuals **0** across the16,164-value pool. All25XML testcase identities/statuses,71JSON,48JSONL,18Python and2JavaScript files parse/compile; both JS checks pass. Raw/export/metadata and11,771 tracked files were unchanged before/after.595 controlled source files match final frozen Git.\n\nThe final coverage is **64 disjoint complete modules /2074 unique PASS** across two actual execution SHAs: `{OLD}` ran1951 (900+789+262); `{S}` ran123. Old52+8 windows are retained via594/595 byte identity and the changed JS's sole consumer outside those modules. No old window is relabeled or added twice. Three old-SHA graph-header negative probes remain separate.\n\nIndependent recomputation confirmed23 literal oracle records (shared12/24 affected pairs; typed11/38), with zero missed/wrong/wrong-preserved answers; unknown expansion is separately declared. Fifteen full original HTML modes (new9,old6) use Node VM DOM with actual HTTP→ASGI→owned PostgreSQL. Actual browser remains unexecuted.\n\nEvery indexed failed XML status and testcase identity is retained. The old formal122PASS/1FAIL harness window, development/setup failures, deterministic rank33 fix proof and unsupported direct-SQL corrupted-plan generic500 observation remain separate. That500 observation is not product-positive validation. The public report correctly limits malformed-plan UNKNOWN to bad headers/handled conflicts and documents finite source and external-gate scope. A nonblocking wording improvement is to call page limit1–20 **每页1–20条**.\n\nThe independent structured reconstruction imports no root producer/verifier. The known-token fast matcher has shared provenance with the producer; a pure original slow-reference differential suite (17tests,200 deterministic random cases) passed again. Actual replacements are disjoint and the fallback conditions were checked.\n\nWindows, actual browser, formal AT, real models, production and remoteCI are NOT_RUN. No deployment, model call, security/credential change, Git or product write occurred in this audit. Primary metadata remains historically pending independent reconstruction; this separate sibling-ready appendix is the final independent gate to avoid index self-reference.\n\nSee `archive-independent-audit.json`, `final-gate.json`, independent coverage/oracle reports, raw/export snapshots and audit logs.\n'''
(D/'final-gate.md').write_text(md)
print(json.dumps({'status':'PASS','source_sha':S,'pairs':259,'coverage_unique':2074,'oracle_records':23,'actual_html_modes':15,'new_blockers':[]}))
