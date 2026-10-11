from pathlib import Path
from collections import Counter
import hashlib,json,gzip,re,ast,datetime,xml.etree.ElementTree as ET
R=Path.cwd(); P=R/'.runtime/case-cancel-after-receipt'; O=P/'independent-review'; D=R/'docs/F2/evidence/case-cancel-after-receipt-20261011'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_bytes())
Mbytes=(D/'archive-manifest.json').read_bytes(); Fbytes=(D/'failure-map.json').read_bytes(); M=json.loads(Mbytes); F=json.loads(Fbytes)
assert sha(Mbytes)=='6c24677c7a2b27c330d4da2b714f66561ec68ef44ecb962bccec42b413137096'
assert sha(Fbytes)=='3a7c38d7e1fc68ea24b5d183486d532b1655d67138f93f7da918aabdab371a25'
# Import only pure functions, so no output directories or Git commands are touched.
ns={'re':re}
policy=R/'docs/F2/evidence/case-cancel-before-accept-20261011/build_archive.py'
for src,names in [(policy,{'scrub','identity_results'}),(D/'build_archive.py',{'metadata_scrub','static_code','check_json_credentials'}),(D/'build_failure_map.py',{'explanation'})]:
 tree=ast.parse(src.read_bytes()); selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 exec(compile(ast.Module(body=selected,type_ignores=[]),'<read-only archive pure functions>','exec'),ns)
assert M['policy_source_sha256']==sha(policy.read_bytes())
E=M['artifacts']; assert len(E)==249; assert len({e['original_local_path'] for e in E})==249; assert len({e['exported_path'] for e in E})==249
W=read(P/'archive-static-whitelist.json'); assert (P/'archive-static-whitelist.json').read_bytes()==(O/'static-code-candidates-reviewed.json').read_bytes(); assert len(W)==55
static_review=read(O/'STATIC_INPUT_CONTENT_REVIEW.json'); assert {e['path']:e['sha256'] for e in static_review['entries']}==W
allids={}; failures=[]; evidence_checks=[]; actual_tokens=set(); credential_findings=[]; hash_strings_checked=0

def ids(tree):
 result={}
 for c in tree.iter('testcase'):
  key=c.attrib['classname']+'::'+c.attrib['name']; assert key not in result
  status='FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
  result[key]=(status,c)
 return result

def hash_values(v,path=()):
 out={}
 if isinstance(v,dict):
  for k,x in v.items():out.update(hash_values(x,path+(k,)))
 elif isinstance(v,list):
  for i,x in enumerate(v):out.update(hash_values(x,path+(str(i),)))
 elif isinstance(v,str) and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',v):out[path]=v
 return out

for e in E:
 p=R/e['original_local_path']; dest=D/e['exported_path']; assert p.resolve().is_relative_to(P.resolve()) and dest.resolve().is_relative_to(D.resolve())
 original=p.read_bytes(); exported=dest.read_bytes(); payload=gzip.decompress(exported) if e['compression']=='gzip' else exported
 assert sha(original)==e['original_sha256'] and len(original)==e['original_bytes']
 assert sha(exported)==e['exported_sha256'] and len(exported)==e['exported_bytes']
 assert sha(payload)==e['sanitized_payload_sha256'] and len(payload)==e['sanitized_payload_bytes']
 counts=Counter(); outcomes=None
 if p.suffix=='.xml':
  t=ET.fromstring(original); old=ns['identity_results'](t); allids[e['exported_path']]=ids(t)
  for suite in t.iter('testsuite'):
   if 'hostname' in suite.attrib:suite.set('hostname','synthetic-fixture-host');counts['hostname']+=1
  for element in t.iter():
   if element.tag in ['failure','error','system-out','system-err','skipped']:
    if element.text:element.text=ns['scrub'](element.text,counts)
    for k in list(element.attrib):element.set(k,ns['scrub'](element.attrib[k],counts))
  assert ns['identity_results'](t)==old==ns['identity_results'](ET.fromstring(payload))
  expected=ET.tostring(t,encoding='utf-8',xml_declaration=True); outcomes=dict(Counter(s for _,_,_,s in old[0])); classification='JUNIT'
  for key,(status,c) in allids[e['exported_path']].items():
   if status in ['FAIL','ERROR']:failures.append((e,key,status,c))
 elif p.suffix=='.json':
  data=json.loads(original); ns['check_json_credentials'](data); clean=ns['metadata_scrub'](data,counts); ns['check_json_credentials'](json.loads(payload))
  expected=(json.dumps(clean,indent=2,sort_keys=True)+'\n').encode(); assert hash_values(data)==hash_values(json.loads(payload)); hash_strings_checked+=len(hash_values(data)); classification='JSON_METADATA'
 elif ns['static_code'](p):
  assert W.get(e['original_local_path'])==sha(original); expected=original; classification='STATIC_CODE_EXACT_SHA_ALLOWLIST'
 else:expected=ns['scrub'](original.decode(),counts).encode(); classification='STDOUT_OR_REPORT'
 assert expected==payload and dict(counts)==e['redactions'] and outcomes==e['test_results_preserved'] and classification==e['classification']
 if classification!='STATIC_CODE_EXACT_SHA_ALLOWLIST':
  s=payload.decode()
  if re.search(r'postgres(?:ql)?://|Bearer\s+(?!\[REDACTED)[A-Za-z0-9_.~+/=-]+|password\s*[=:]\s*(?!\[REDACTED)[^\s,;\'\"<>]+',s,re.I):credential_findings.append(e['exported_path'])
  if re.search(r'/(?:workspace|opt|home|root|usr|var|tmp)/',s):credential_findings.append(e['exported_path']+':execution_path')
  for token in re.findall(r"['\"]([A-Za-z0-9_-]{40,})['\"]",original.decode()):
   if len(token)==43 and re.search('[a-z]',token) and re.search('[A-Z]',token) and not re.fullmatch('[0-9a-f]+',token):actual_tokens.add(token)
 evidence_checks.append({'original':e['original_local_path'],'export':e['exported_path'],'classification':classification,'original_hash':'PASS','export_and_payload_hash':'PASS','expected_policy_bytes':'PASS','JUnit_identity_result_time':'PASS' if classification=='JUNIT' else None})
assert not credential_findings,credential_findings
for e in E:
 if e['classification']=='STATIC_CODE_EXACT_SHA_ALLOWLIST':continue
 payload=(D/e['exported_path']).read_bytes()
 if e['compression']=='gzip':payload=gzip.decompress(payload)
 assert not any(token.encode() in payload for token in actual_tokens),e['exported_path']
assert Counter(e['classification'] for e in E)==Counter(JUNIT=17,STDOUT_OR_REPORT=28,JSON_METADATA=149,STATIC_CODE_EXACT_SHA_ALLOWLIST=55)
assert sum(e['original_bytes'] for e in E)==3465991 and sum(e['exported_bytes'] for e in E)==3461260 and not any(e['compression'] for e in E)
assert len(failures)==len({key for _,key,_,_ in failures})==34 and F['failed_occurrences']==F['unique_failed_ids']==34
mapped={x['test_id']:x for x in F['entries']}; assert set(mapped)=={key for _,key,_,_ in failures}
for entry,key,status,c in failures:
 x=mapped[key]; assert x['original_status']==status and x['original_window']==Path(entry['original_local_path']).stem and x['original_sanitized_junit']==entry['exported_path']
 error=c.find('failure') if status=='FAIL' else c.find('error'); assert x['original_exception_type']==error.attrib.get('type')
 assert x['repaired_same_id_status']=='PASS' and allids[x['repaired_window']][key][0]=='PASS'
 grade,reason=ns['explanation'](x['original_window'],key); assert grade==x['evidence_grade'] and reason==x['diagnosis_and_correction']
 assert x['final_source_sha']=='796b41ad8939ba1d067f84f137a4d2a1861f06d4'
 assert x['repaired_window_source_manifest_sha256']==('e103cb121d8396c7e566367705cbc44776e20feb66e325f96ca40dd2af81cb25' if '/independent-review/' in entry['original_local_path'] else 'cb47c652372f4aad3076c7adc995e77f505800f4aa1e28d39a94617b0a9d96b5')
final=read(P/'full-final-run.json'); finaltree=ET.parse(P/'full-final.xml'); finalids=ids(finaltree); priorids=ids(ET.parse(R/'.runtime/case-cancel-before-receipt/full-final.xml'))
assert len(finalids)==1561 and Counter(s for s,_ in finalids.values())==Counter(PASS=1560,SKIP=1)
assert len(priorids)==1391 and not set(priorids)-set(finalids) and len(set(finalids)-set(priorids))==170
assert final['exit_code']==0 and final['source_sha']=='796b41ad8939ba1d067f84f137a4d2a1861f06d4' and not final['source_drift'] and not final['uncommitted_source'] and not final['prior_test_ids_missing'] and final['complete_module_count']==38
assert len({x for x in final['argv'] if x.startswith('tests/')})==38
assert sha((P/'full-final.xml').read_bytes())==final['xml_sha256']=='77073956059174668caca9528dec3ac072f2d5c0bf37a6f34a89db8dd824f054'
assert sha((P/'full-final.log').read_bytes())==final['log_sha256']=='86925add0de4648e3a7a97acce1d04f334e131a96eacabe9b8f43259e8ec5106'
skipped=[(i,c.find('skipped').attrib) for i,(s,c) in finalids.items() if s=='SKIP']; assert len(skipped)==1 and skipped[0][0]=='tests.test_authorization_files::test_native_windows_file_backend_gate'
assert skipped[0][1]['message'].startswith('NOT_RUN: native Windows')
assert finaltree.find('testsuite').attrib['time']=='1560.155'
assert '1560 passed, 1 skipped, 2 warnings in 1560.20s' in (P/'full-final.log').read_text() and final['elapsed_seconds']==1562.358 and not final['atexit_cleanup_diagnostic']
source=read(P/'final-source-manifest.json'); assert len(source)==405 and sha((P/'final-source-manifest.json').read_bytes())=='cb47c652372f4aad3076c7adc995e77f505800f4aa1e28d39a94617b0a9d96b5'
assert all(sha((R/p).read_bytes())==h for p,h in source.items())
sixth=read(O/'sixth-complete-backend-ui-and-probes-source-manifest.json'); assert len(sixth)==405 and set(sixth)==set(source)
differences=sorted(p for p in source if source[p]!=sixth[p]); original_schema=read(P/'schema-oracle-before/manifest.json'); assert set(differences)==set(original_schema) and len(differences)==10
for p,meta in original_schema.items():assert sha((R/meta['snapshot_path']).read_bytes())==meta['sixth_sha256']==sixth[p]
assert sha((R/'docs/F2/CaseCancellationReconciliationContract.md').read_bytes())=='a2302d0f69dd20932d78cd21aa64099ddb9a19a273641d715eab61343930c9b4'
assert sha((O/'REVIEW.md').read_bytes())=='3a5c3f52c9db0444415929acea3847d584da24570f6724763f52c704abb8a25c' and sha((O/'review.json').read_bytes())=='e191c67726ec841698c5c9f8c366c625cd9c0fe89e3adb3cedda6fd1a4f937ad'
review=read(O/'review.json'); assert review['parent_full_final_status_at_signing']['status']=='RUNNING'
assert review['independent_tested_source_manifest_sha256']=='e103cb121d8396c7e566367705cbc44776e20feb66e325f96ca40dd2af81cb25'
orig_node=read(O/'unknown-handle-capture-run.json'); repaired_node=read(O/'final-unknown-handle-capture-run.json'); assert orig_node['exit_code']==1 and repaired_node['exit_code']==0 and orig_node['command']==repaired_node['command'] and orig_node['probe_sha256']==repaired_node['probe_sha256']==sha((O/'unknown_handle_capture.js').read_bytes())
assert repaired_node['source_manifest_sha256']==sha((P/'final-source-manifest.json').read_bytes()) and not repaired_node['source_drift_after']
old=read(P/'accepted-archive-byte-baseline.json'); prefixes={R/str(Path(p).parent) for p in old['files'] if Path(p).name=='README.md'}; current={str(p.relative_to(R)) for prefix in prefixes for p in prefix.rglob('*') if p.is_file()}
assert current==set(old['files']) and len(current)==149 and all(sha((R/p).read_bytes())==h for p,h in old['files'].items())
assert sha((D/'archive-manifest.json').read_bytes())==sha(Mbytes) and sha((D/'failure-map.json').read_bytes())==sha(Fbytes)
result={'status':'LIMITED_PASS','scope':'FINAL_ARCHIVE_AUDIT','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':final['source_sha'],'source_manifest_sha256':final['source_manifest_sha256'],'source405_worktree_drift':[],'frozen_contract_sha256':'a2302d0f69dd20932d78cd21aa64099ddb9a19a273641d715eab61343930c9b4','archive_manifest_sha256':sha(Mbytes),'failure_map_sha256':sha(Fbytes),'archive_artifact_count':249,'original_bytes':3465991,'exported_bytes':3461260,'gzip_artifacts':0,'classifications':dict(Counter(e['classification'] for e in E)),'all_original_export_payload_hashes_and_byte_sizes':'PASS','all_exact_expected_policy_bytes_and_redaction_counts':'PASS','metadata_literal_source_and_proof_hash_strings_checked':hash_strings_checked,'metadata_credential_gate_and_runtime_text_scan':'PASS','actual_opaque_auth_candidates_absent_from_nonstatic_exports':len(actual_tokens),'JUnit_windows':17,'JUnit_identity_status_counts_time_suite_preserved':'PASS','actual_failed_occurrences':34,'actual_unique_failed_ids':34,'original_FAIL_ERROR_retained_and_same_ID_separate_PASS':'PASS','root_final':{k:final[k] for k in ['source_sha','source_manifest_sha256','complete_module_count','PASS','FAIL','ERROR','SKIP','tests','unique_test_id_count','exit_code','elapsed_seconds','started_at_utc','ended_at_utc','source_drift','uncommitted_source','prior_test_ids_missing','atexit_cleanup_diagnostic','xml_sha256','log_sha256']},'root_final_JUnit_seconds':'1560.155','root_final_pytest_stdout_seconds':'1560.20','native_Windows_skip':{'id':skipped[0][0],'message':skipped[0][1]['message']},'prior_full_test_IDs':1391,'prior_IDs_missing':[],'new_test_IDs':170,'independent_repair_window':'Actual sixth226 e103cb, not a fresh cb47 run; all12 original independent failedIDs same-ID PASS.','sixth_to_final_test_only_differences':differences,'static55_exact_content_reviewed_whitelist':'PASS','static_whitelist_sha256':sha((P/'archive-static-whitelist.json').read_bytes()),'standalone_original_argv_and_probe_bytes_exit1_to_exit0':'PASS_NOT_A_JUNIT_ID','signed_REVIEW_original_bytes_and_RUNNNING_at_signing_preserved':'PASS','old149_exact_file_set_and_byte_hashes':'PASS','remaining_blockers':[],'not_operated':['No business tests rerun.','No browser (0 attempts), models, deployment, credentials or grants.','No child Git operations; committed source/delivery bytes and remote verification are parent delivery checks.','No public/product/tests/docs or original raw/report mutations.'],'historical_limits':['Old Case_count0 cause remains UNCONFIRMED; no old worker stdout/state recovered.','Old39API stderr gap and prior atexit diagnostics remain disclosed; new final full has no atexit diagnostic.','No whole-repository/full-lifecycle/native-Windows PASS claimed.'],'pending_parent_delivery':['Final documentation/evidence commit, normal push, remote protected/HEAD/clean/divergence checks.'],'per_artifact_checks':evidence_checks}
q=O/'archive-audit-check-results.json'; assert not q.exists(); q.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n'); print(json.dumps({k:v for k,v in result.items() if k!='per_artifact_checks'},indent=2,ensure_ascii=False))
