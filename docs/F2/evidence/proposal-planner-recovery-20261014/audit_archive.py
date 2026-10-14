from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as E,subprocess
root=Path('/workspace/ParkWeave');rawroot=root/'.runtime/proposal-planner-recovery-20261014';public=root/'docs/F2/evidence/proposal-planner-recovery-20261014';out=Path('/workspace/parkweave-planner-review/.runtime/proposal-planner-recovery-20261014/independent/archive-review.json');sha='a26a6c84e67bc85d8a24651886261fdb8c605e83';index=json.loads((public/'export-index.json').read_text());values=json.loads((rawroot/'redaction-values.private.json').read_text());marker=b'[REDACTED_SYNTHETIC_FIXTURE_SESSION]';issues=[];entries=[];total=0;raw_by_hash={}
assert len(values)==len(set(values))==index['session_values']==11
allowed={b'synthetic-proposal-token-not-a-credential',b'fake-offline-token-never-a-real-key',b'SYNTHETIC_template-new-enterprise-a',b'SYNTHETIC_template-new-reviewer-a'}
def redact(raw):
 expected=raw;count=0
 for value in values:
  token=value.encode();count+=expected.count(token);expected=expected.replace(token,marker)
 return expected,count
def residual_checks(name,data):
 if any(v.encode() in data for v in values):issues.append({'file':name,'residual_actual_session':True})
 tokens=re.findall(rb'Bearer[ +]*([A-Za-z0-9_-]{20,})',data)
 unexpected=[t for t in tokens if t not in allowed]
 if unexpected:issues.append({'file':name,'unrecognized_bearer_count':len(unexpected)})
for row in index['entries']:
 raw=Path(row['original']).read_bytes();target=public/row['export'];export=target.read_bytes();expected,count=redact(raw);total+=count
 checks={'raw_sha':hashlib.sha256(raw).hexdigest()==row['raw_sha256'],'export_sha':hashlib.sha256(export).hexdigest()==row['export_sha256'],'raw_bytes':len(raw)==row['raw_bytes'],'export_bytes':len(export)==row['export_bytes'],'literal_only':export==expected,'redaction_count':count==row['redaction_occurrences']}
 if not all(checks.values()):issues.append({'file':row['export'],'checks':checks})
 residual_checks(row['export'],export);raw_by_hash.setdefault(row['raw_sha256'],raw);entries.append({'file':row['export'],'checks':checks,'redactions':count})
assert len(entries)==index['exports']==307 and total==22
for p in public.rglob('*'):
 if p.is_file():residual_checks(p.relative_to(public).as_posix(),p.read_bytes())
manifest=json.loads((public/'source-freeze.json').read_text());assert manifest['count']==len(manifest['files'])==524 and manifest['source_sha']==sha
mismatch=[n for n,h in manifest['files'].items() if hashlib.sha256((root/n).read_bytes()).hexdigest()!=h];assert not mismatch
validation=json.loads((public/'postformat-validation.json').read_text());assert validation['source_sha']==index['source_sha']==sha
xmls={}
for p in sorted(public.rglob('*.xml')):
 tree=E.parse(p).getroot();s=tree if tree.tag=='testsuite' else tree.find('testsuite');n=int(s.get('tests'));f=int(s.get('failures'));e=int(s.get('errors'));sk=int(s.get('skipped'));xmls[p.relative_to(public).as_posix()]={'tests':n,'pass':n-f-e-sk,'fail':f,'error':e,'skip':sk,'seconds':float(s.get('time'))}
for label,name in (('root_final','postformat-final.xml'),('isolated_final','isolated-tests/postformat-final.xml'),('independent_final','independent/final.xml')):
 x=validation[label];assert xmls[name]=={'tests':x['tests'],'pass':x['passed'],'fail':x['failures'],'error':x['errors'],'skip':x['skipped'],'seconds':x['seconds']},label
rootcases=E.parse(public/'postformat-final.xml').getroot().find('testsuite').findall('testcase');modules={}
for c in rootcases:modules[c.get('classname')]=modules.get(c.get('classname'),0)+1
assert len(modules)==18
page_counts={pattern:sum(pattern in c.get('name') for c in rootcases) for pattern in ('test_original_page_attempt_recovery_and_explicit_new_key','test_original_page_fake_planner_closed_loop','test_original_page_candidate_consumer_never_hand_fills_candidate_json','test_original_page_second_unsupported_goal_opens_exact_selected_goal','test_original_page_target_denial_clears_current_scope_only')};assert list(page_counts.values())==[10,4,21,15,11]
assert sum(page_counts.values())==61==validation['root_page_cases_already_in530']
indcases=E.parse(public/'independent/final.xml').getroot().find('testsuite').findall('testcase');assert sum(('test_original_page_attempt_recovery_and_explicit_new_key' in c.get('name') or 'test_original_page_candidate_consumer_never_hand_fills_candidate_json' in c.get('name')) for c in indcases)==31==validation['independent_page_cases_already_in141']
assert xmls['independent/state-outcome-red.xml']['fail']==1
assert xmls['isolated-tests/product-red.xml']['pass']==6 and xmls['isolated-tests/product-red.xml']['fail']==2
assert xmls['isolated-tests/red.xml']['fail']==8 and xmls['independent/consumer-extra-red.xml']['pass']==10
# Archived before-format/final is a copy of the earlier480 final, not another execution.
assert (public/'before-format/final.xml').read_bytes()==(public/'final.xml').read_bytes()
# Read only the known locally committed draft public paths. No Git write/network.
def git(*args):return subprocess.run(['git',*args],cwd=root,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
historic_paths=git('diff-tree','--no-commit-id','--name-only','-r',sha,'--','docs/F2').decode().splitlines();historic_blobs={p:git('show',sha+':'+p) for p in historic_paths};historic_evidence=[p for p in historic_paths if p.startswith('docs/F2/evidence/proposal-planner-recovery-20261014/')]
for p,data in historic_blobs.items():residual_checks('historical '+p,data)
oldindex=json.loads(git('show',sha+':docs/F2/evidence/proposal-planner-recovery-20261014/export-index.json'));historic_checked=[]
for row in oldindex['entries']:
 p='docs/F2/evidence/proposal-planner-recovery-20261014/'+row['export'];export=git('show',sha+':'+p);raw=raw_by_hash.get(row['raw_sha256'])
 assert raw is not None,('historic raw hash missing',row['export'])
 expected,count=redact(raw)
 checks={'raw_sha':hashlib.sha256(raw).hexdigest()==row['raw_sha256'],'export_sha':hashlib.sha256(export).hexdigest()==row['export_sha256'],'raw_bytes':len(raw)==row['raw_bytes'],'export_bytes':len(export)==row['export_bytes'],'literal_only':export==expected,'count':count==row['redaction_occurrences']}
 if not all(checks.values()):issues.append({'historical_file':p,'checks':checks})
 historic_checked.append({'file':p,'checks':checks})
approval_sha='c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a'
for name in ('approval.json','prepare_approval.json'):assert hashlib.sha256((root/'scripts/host_case_once'/name).read_bytes()).hexdigest()==approval_sha
format_checks=json.loads((public/'diff-check.json').read_text());assert format_checks['source']['exit']==format_checks['report']['exit']==0 and format_checks['cumulative_archive']['exit']==2 and format_checks['cumulative_archive']['trailing_whitespace_notices']==12
assert format_checks['final_staged']['exit']==0
report=(root/'docs/F2/ProposalPlannerRecovery-20261014.md').read_text()
for text in (sha,'530 PASS','141 PASS','10 PASS','303.697','77.456','9.863','307件','11实际临时session','22处','before-format','180草稿','NOT RUN','exit2','12处'):assert text in report,text
result={'status':'PASS' if not issues else 'HOLD','source_sha':sha,'exports_checked':307,'actual_session_values':11,'exact_replacements':22,'redaction':'Only exact actual temporary SYNTHETIC fixture session values replaced; all other bytes identical. No session originals included in audit. Known SYNTHETIC_<actor> frontend placeholders proven by prior source bridge review and excluded from credential classification.','source_files':524,'source_drift':mismatch,'xml_windows':xmls,'root_modules':modules,'root_page_subsets_already_in530':page_counts,'independent_page_subsets_already_in141':31,'counts_never_summed':True,'historic_source_commit':{'sha':sha,'public_doc_paths':len(historic_paths),'evidence_paths':len(historic_evidence),'indexed_exports_verified':len(historic_checked),'original_session_residuals':0,'entries':historic_checked,'scope':'Known180 earlier draft exports individually verified against preserved exact raw bytes found by indexed rawhash; all183 public doc blobs inspected. Final report corrects earlier480 source and counts without history rewriting.'},'approval_hash':approval_sha,'format_checks':format_checks,'format_scope_note':'Cumulative base387 evidence diff exit2/12 original pytest E whitespace. Current staged0 is narrower than cumulative; not treated as cumulative0. Check stdout private, never recursively exported.','issues':issues,'entries':entries,'limits':'Archive validation only. No tests rerun, credential reads, LIVE quota/provider/Gateway/browser/prepare/config or Git mutation. Existing refusals remain untried, no full PR0/native/real model signoff.'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'exports':307,'session_values':11,'replacements':22,'source_drift':0,'xml_windows':len(xmls),'historic_doc_paths':len(historic_paths),'historic_exports_verified':len(historic_checked),'issues':issues},indent=2))
