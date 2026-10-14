from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as E,subprocess
root=Path('/workspace/ParkWeave');rawroot=root/'.runtime/proposal-planner-20261014';public=root/'docs/F2/evidence/proposal-planner-offline-20261014';out=Path('/workspace/parkweave-planner-review/.runtime/proposal-planner-20261014/independent/archive-review.json')
index=json.loads((public/'export-index.json').read_text());values=json.loads((rawroot/'redaction-values.private.json').read_text());marker=b'[REDACTED_SYNTHETIC_FIXTURE_SESSION]';issues=[];entries=[];total=0
assert len(values)==len(set(values))==index['session_values']==38
for row in index['entries']:
 raw=Path(row['original']).read_bytes();target=public/row['export'];export=target.read_bytes();expected=raw;count=0
 for value in values:
  encoded=value.encode();count+=expected.count(encoded);expected=expected.replace(encoded,marker)
 total+=count
 checks={'raw_sha':hashlib.sha256(raw).hexdigest()==row['raw_sha256'],'export_sha':hashlib.sha256(export).hexdigest()==row['export_sha256'],'raw_bytes':len(raw)==row['raw_bytes'],'export_bytes':len(export)==row['export_bytes'],'literal_only':export==expected,'redaction_count':count==row['redaction_occurrences'],'actual_session_absent':not any(v.encode() in export for v in values)}
 if not all(checks.values()):issues.append({'file':row['export'],'checks':checks})
 # Identify bearer literals while permitting only fixed explicit fake planner token.
 if target.suffix in ('.log','.xml','.json'):
  tokens=re.findall(rb'Bearer[ +]*([A-Za-z0-9_-]{20,})',export)
  suspect=[token for token in tokens if token not in (b'synthetic-proposal-token-not-a-credential',b'fake-offline-token-never-a-real-key',b'SYNTHETIC_template-new-enterprise-a',b'SYNTHETIC_template-new-reviewer-a')]
  if suspect:issues.append({'file':row['export'],'unrecognized_bearer_count':len(suspect)})
 entries.append({'file':row['export'],'checks':checks,'redactions':count})
assert len(entries)==index['exports']==134
# No original opaque session survives anywhere, including non-indexed report/index.
for p in public.rglob('*'):
 if p.is_file() and any(v.encode() in p.read_bytes() for v in values):issues.append({'file':p.relative_to(public).as_posix(),'residual_session':True})
manifest=json.loads((public/'source-freeze.json').read_text());assert manifest['count']==len(manifest['files'])==521
mismatch=[name for name,sha in manifest['files'].items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha]
if mismatch:issues.append({'source_mismatch':mismatch})
validation=json.loads((public/'validation.json').read_text());xmls={}
for p in sorted(public.rglob('*.xml')):
 suites=E.parse(p).getroot();s=suites if suites.tag=='testsuite' else suites.find('testsuite');n=int(s.get('tests'));f=int(s.get('failures'));e=int(s.get('errors'));sk=int(s.get('skipped'));xmls[p.relative_to(public).as_posix()]={'tests':n,'pass':n-f-e-sk,'fail':f,'error':e,'skip':sk,'seconds':float(s.get('time'))}
for label,name in (('root_final','final.xml'),('isolated_final','isolated-tests/final.xml'),('independent_final','independent/final.xml'),('independent_pages_separate','independent/pages.xml')):
 x=validation[label];actual=xmls[name];assert actual=={'tests':x['tests'],'pass':x['passed'],'fail':x['failures'],'error':x['errors'],'skip':x['skipped'],'seconds':x['seconds']},label
# Acceptance counts have no duplicate additions of page subsets.
assert xmls['final.xml']['tests']==510
assert xmls['independent/final.xml']['tests']==159
assert xmls['independent/pages.xml']['tests']==4
rootcases=E.parse(public/'final.xml').getroot().find('testsuite').findall('testcase');module_counts={}
for c in rootcases:module_counts[c.get('classname')]=module_counts.get(c.get('classname'),0)+1
assert len(module_counts)==16
assert sum('test_original_page_fake_planner_closed_loop' in c.get('name') for c in rootcases)==4
assert sum('test_original_page_candidate_consumer_never_hand_fills_candidate_json' in c.get('name') for c in rootcases)==21
assert sum(('test_original_page_second_unsupported_goal_opens_exact_selected_goal' in c.get('name','') or 'test_original_page_target_denial_clears_current_scope_only' in c.get('name','')) for c in rootcases)==26
failwindows={p:x for p,x in xmls.items() if x['fail'] or x['error']}
assert xmls['independent/development.xml']['pass']==2 and xmls['independent/development.xml']['fail']==7
assert xmls['isolated-tests/development.xml']['pass']==8 and xmls['isolated-tests/development.xml']['fail']==18
assert xmls['isolated-tests/repaired-development.xml']['pass']==15 and xmls['isolated-tests/repaired-development.xml']['fail']==11
assert xmls['boundary-dev.xml']['pass']==131 and xmls['boundary-dev.xml']['fail']==1
approval_sha='c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a'
approvals={}
for name in ('approval.json','prepare_approval.json'):
 p=root/'scripts/host_case_once'/name;approvals[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'json':json.loads(p.read_text())};assert approvals[name]['sha256']==approval_sha
report=(root/'docs/F2/ProposalPlannerOffline-20261014.md').read_text();assert index['source_sha']==validation['source_sha']==manifest['source_sha']=='a60c83c5cfc5b037c607f6f192f840dfdde42783'
for text in ('510 PASS','159 PASS','4 PASS','521','ERR_BLOCKED_BY_ADMINISTRATOR','Forbidden','NOT RUN','UNKNOWN/UNSUPPORTED','1024','134 件'):
 assert text in report,text
format_check=json.loads((public/'diff-check.json').read_text());assert format_check['source']['exit']==0 and format_check['report']['exit']==0 and format_check['staged_archive']['exit']==2 and format_check['staged_archive']['trailing_whitespace_notices']==40
result={'bearer_scan_oracle_correction':'Initial scan flagged intentional SYNTHETIC_<actor> NodeVM placeholder authorization literals in 11 denied page chains. Source tests/test_multi_goal_overview_denied.py maps placeholder to actual ephemeral fixture token only inside bridge; actual token never appears in page chain. Two exact fixture placeholder literals now explicitly recognized; initial HOLD retained as audit evidence, no public source/export changed.', 'format_checks':format_check,'status':'PASS' if not issues else 'HOLD','source_sha':index['source_sha'],'exports_checked':len(entries),'exact_session_values':len(values),'exact_session_literal_replacements':total,'redaction_method':'Only 38 exact private synthetic fixture session values replaced, all other bytes identical; no original values included in this review.','source_files':521,'source_drift':mismatch,'module_count':len(module_counts),'root_modules':module_counts,'xml_windows':xmls,'retained_failure_windows':failwindows,'approval_hash':approval_sha,'approvals_unchanged':True,'issues':issues,'entries':entries,'limits':'Archive consistency audit; no test rerun, browser, provider request, credential lookup or LIVE quota writes. Historical browser/prepare refusals remained untried; no PR0/native/real model signoff. Source/report diff-check exit0; staged archive exit2/40 pytest original E trailing spaces, retained deliberately and private stdout not recursively exported.'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'exports':len(entries),'redaction_values':len(values),'replacements':total,'source_drift':len(mismatch),'xml_windows':len(xmls),'retained_failure_windows':len(failwindows),'issues':issues},indent=2))
