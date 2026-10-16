"""Final raw reader. Never runs tests or changes literal design inputs."""
from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
R=Path.cwd();B=R/'.runtime/plan-reapproval-final/v2';O=R/'.runtime/plan-reapproval-oracle/final-v2'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
f=read(R/'.runtime/plan-reapproval-root/v2/freeze.json');source=f['source_sha']
assert source==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
for p,h in f['source_paths'].items():assert sha(R/p)==h,p
selection=read(B/'selection.json')['main_windows']
window_names=('new-core','new-independent','new-chromium');runs={};N=[];manifests={}
for window in window_names:
 run=read(B/(window+'.json'));assert run['source_sha']==source and run['exit_code']==0
 assert run['counts']['PASS']>0 and not any(run['counts'][k] for k in ('FAIL','ERROR','SKIP'))
 assert run['collection_junit_exact_match'] and run['unique_junit_nodes']
 assert not any(run[k] for k in ('source_drift','all_tracked_drift','runner_drift'))
 nodes=run['collected_nodes'];assert len(set(nodes))==len(nodes)==run['counts']['PASS']
 assert len(list(ET.parse(B/(window+'.xml')).iter('testcase')))==len(nodes)
 assert set(run['modules'])==set(selection[window])
 for m in selection[window]:assert any(n.startswith(m+'::') for n in nodes),m
 N.extend(nodes);runs[window]=run
 for suffix in ('.json','.xml','-collection.json'):manifests[str((B/(window+suffix)).relative_to(R))]=sha(B/(window+suffix))
assert len(N)==len(set(N))
art=B/'artifacts/new-independent/test_plan_source_reapproval_independent';assert art.is_dir()
public=[p for w in window_names for p in (B/'artifacts'/w).rglob('*') if p.is_file() and not p.name.endswith('.private.json')]
rawhash={**manifests,**{str(p.relative_to(R)):sha(p) for p in sorted(public)}}
def ev(needle):
 v=[n for n in N if needle in n];assert v,needle
 return [dict(identity=n,status='PASS') for n in v]
# Only the new completed window is mapped; prior suites are not silently credited.
M={
1:('test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals[material_fact]','HTTP_LITERAL','Exact source update, ADOPT, new Approval and replacement resource link.'),
2:('test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals','HTTP_LITERAL','Original full six-goal closure and complete worklist flags.'),
3:('test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals[resource]','HTTP_LITERAL','Resource-only original partial revision retains complete P1 lock.'),
4:('test_original_default_first_delivery_and_unapproved_reapproval_refuse','HTTP_BEHAVIOR_VARIANT','Unapproved new object refuses; unchecked UI independently covered in HTML.'),
5:('test_consumed_old_approval_cannot_authorize_new_source_delivery','HTTP_LITERAL','Consumed prior Approval cannot authorize new command.'),
7:('test_approved_new_object_never_revives_after_original_source_change[plan_revision]','HTTP_LITERAL','LOCK increments exact plan revision after Approval.'),
8:('test_approved_new_object_never_revives_after_original_source_change[preparation_revision]','HTTP_BEHAVIOR_VARIANT','Actual preparation REOPEN; does not execute all listed material/fact/P1 changes.'),
10:('test_approved_new_object_never_revives_after_original_source_change[resource_revision]','HTTP_BEHAVIOR_VARIANT','Capacity is changed; not all listed disabled/rule-revision variants.'),
11:('test_approved_new_object_never_revives_after_original_source_change[resource_aba]','HTTP_LITERAL','Resource capacity restored through two committed changes.'),
16:('test_expired_new_hold_refuses_quote_and_never_uses_old_approval','HTTP_BEHAVIOR_VARIANT','Expired hold quote refusal; not all date bounds/approval deadline variants.'),
18:('test_original_tenant_owner_and_role_cannot_read_or_commit_new_approval','HTTP_BEHAVIOR_VARIANT','Four actual nonowner actors cover commit/Approval read/cold recovery; not every named stage.'),
19:('test_actual_original_revocation_denies_new_reapproval_without_effect','HTTP_LITERAL','All five named capability revocations before delivery.'),
20:('test_approved_new_object_never_revives_after_original_source_change[authority_aba]','HTTP_BEHAVIOR_VARIANT','Owner EXECUTE revoked/restored; not all authority families.'),
21:('test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals','HTTP_LITERAL','Same exact key retry and cold GET; fixed single-effect counts.'),
22:('test_exact_old_key_replay_rejects_changed_reapproval_parameters','HTTP_BEHAVIOR_VARIANT','Actual reason/link_revision/approval_id/valid_until; member/scope variants not run here.'),
23:('test_full_original_html_source_reapproval_and_original_authority[lost_ack]','HTML_ACTUAL_HTTP','Controlled committed response loss; same original key GET only.'),
24:('test_unknown_original_key_get_never_executes_reapproval','HTTP_LITERAL','Actual NOT_OBSERVED GET with all business rows unchanged.'),
25:('test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals','HTTP_BEHAVIOR_VARIANT','Old superseded receipt NEEDS_RECHECK; expiry not independently crossed here.'),
28:('test_owned_pg_fault_rolls_back_entire_reapproval_transaction','OWNED_PG_SERVICE_VARIANT','Three actual PostgreSQL insertion faults through original Python service, not HTTP; consumption-specific fault not claimed.'),
29:('test_rehashed_owned_fixture_profile_downgrade_and_self_reference_are_conflicts','OWNED_ADMIN_CORRUPTION_HTTP','Owner fixture deliberately rewrites proofs (including temporary trigger disable), then actual recovery/P2/plan/goal409; not legal application mutation.'),
30:('test_original_default_first_delivery_and_unapproved_reapproval_refuse','HTTP_LITERAL','Missing expected_link_revision retains original first-delivery refusal.'),
31:('test_full_original_html_source_reapproval_and_original_authority[late_403]','HTML_ACTUAL_HTTP','Actual held403 with Case/mode/identity ABA.'),
32:('test_full_original_html_source_reapproval_and_original_authority','HTML_ACTUAL_HTTP','Node DOM actual shipped page; full positive/lost flows and denied read modes separate.')}
oracle=R/'docs/F2/PlanReapprovalOracle-20261016.json';design=read(oracle);assert len(design['rows'])==32 and design['status']=='DESIGN_ONLY_NOT_EXECUTED'
rows=[]
for d in design['rows']:
 i=int(d['id'][2:]);m=M.get(i)
 rows.append(dict(id=d['id'],literal_expected=d,execution='PASS_WITH_SCOPE_LIMIT' if m else 'NOT_RUN',coverage_kind=m[1] if m else 'NOT_RUN',evidence=ev(m[0]) if m else [],note=m[2] if m else 'No matching executed new-window identity. Prior suites are not credited automatically.'))
rows[22]['browser_variant']=dict(coverage_kind='CHROMIUM_ACTUAL_HTTP',evidence=ev('test_actual_installed_chromium_explicit_source_reapproval_to_six_goals[lost_commit]'),note='Actual browser committed response loss; source update and prerequisite P1 preparation occur through original Python controls.')
rows[31]['browser_variant']=dict(coverage_kind='CHROMIUM_ACTUAL_HTTP',evidence=ev('test_actual_installed_chromium_explicit_source_reapproval_to_six_goals'),note='Four installed Chromium modes, exact reapproval/commit and P2-P5 UI verification; initial source ADOPT/P1 repair are Python controls.')
coverage=dict(source_sha=source,formal_new_passes=len(N),formal_windows={w:dict(passes=runs[w]['counts']['PASS'],modules=runs[w]['modules']) for w in window_names},oracle_sha256=sha(oracle),design_status_unchanged=design['status'],rows=rows,counts={k:sum(x['coverage_kind']==k for x in rows) for k in sorted({x['coverage_kind'] for x in rows})},raw_sha256=rawhash)
html=[]
for mode in ('positive','lost_ack','current_403','late_403'):
 matches=[]
 for p in art.glob(mode+'-*.stdout.jsonl'):
  v=lines(p);end=[x for x in v if x.get('scope')=='FULL_ORIGINAL_HTML_PLAN_SOURCE_REAPPROVAL_ACTUAL_HTTP_ASGI_OWNED_PG']
  if end:matches.append((p,v,end))
 assert len(matches)==1,(mode,len(matches))
 p,v,end=matches[0];assert len(end)==1;last=end[0];calls=last['calls'];assert calls==[x['trace'] for x in v if 'trace' in x]
 assert last['real_browser']=='NOT_RUN' and last['fake_dto'] is False
 posts=[c for c in calls if c['method']=='POST'];commit=[c for c in posts if c['path'].endswith('/resource-delivery')];verify=[c for c in posts if c.get('body',{}).get('action')=='VERIFY']
 denials=[c for c in calls if c['status']==403];recovery=[]
 if mode in ('positive','lost_ack'):
  assert len(commit)==1 and commit[0]['status']==201 and commit[0]['body']['expected_link_revision']==1 and commit[0]['body'].get('approval_id')
  assert len(verify)==5 and len({c['body']['step_id'] for c in verify})==5 and all(c['status']==200 for c in verify)
  assert any(c['path'].endswith('/goal-results') and c['status']==200 for c in calls)
  assert any(c.get('worklist_items') for c in calls)
  if mode=='lost_ack':
   recovery=[c for c in calls if c['path'].endswith('/resource-delivery/recovery/'+commit[0]['request_key'])];assert recovery and all(c['method']=='GET' and c['status']==200 for c in recovery)
 else:assert not posts and len(denials)==1
 html.append(dict(mode=mode,actual_nativefetch_calls=len(calls),checks=last['checks'],method_counts={k:sum(c['method']==k for c in calls) for k in ('GET','POST')},resource_commit_count=len(commit),verify_count=len(verify),actual_403_count=len(denials),original_key_recovery_gets=len(recovery),context_events=last.get('context_events',[]),trace=str(p.relative_to(R)),trace_sha256=sha(p),real_browser='NOT_RUN'))
htmlsummary=dict(source_sha=source,modes=html,actual_nativefetch_total=sum(x['actual_nativefetch_calls'] for x in html),classification='SHIPPED_HTML_NODE_DOM_ACTUAL_HTTP_ASGI_OWNED_PG',python_control_http_total='NOT_RECORDED',raw_sha256=rawhash)
records={prefix:[r for p in art.glob(prefix+'-*.jsonl') for r in lines(p)] for prefix in ('closures','closure','refusals','source-adopt','rollback','html-results')}
assert len(records['html-results'])==4 and len(records['closure'])==2
assert all(r['six_goals_current'] and r['worklist_complete'] and r['stable_ids_history'] and r['worklist_recorded_only'] for r in records['closures'])
assert all(r['old_occupancy_preserved'] and r['old_receipt_cold_get'] and r['six_goals'] for r in records['closure'])
assert all(r['no_business_writes'] for r in records['refusals']+records['rollback'])
closure=dict(status='LIMITED_PASS',source_sha=source,formal_new_passes=len(N),record_counts={k:len(v) for k,v in records.items()},record_counts_are_not_unique_cases=True,python_control_http_total='NOT_RECORDED',raw_sha256=rawhash)
# Chromium is one distinct complete main window, never added twice to new union.
br=runs['new-chromium'];paths=list((B/'artifacts/new-chromium').rglob('*-calls.json'));assert len(paths)==br['counts']['PASS']==4
modes=[]
for p in paths:
 x=read(p);assert x['actual_browser']=='INSTALLED_CHROMIUM' and not x['page_errors'];calls=x['calls']
 com=[c for c in calls if c['method']=='POST' and c['path'].endswith('/resource-delivery') and c['status']==201];assert len(com)==1
 proposed=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/proposals')];approved=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/commands')]
 assert len(proposed)==len(approved)==1
 lost=[c for c in calls if c.get('committed_response_controlled_lost') or c.get('approval_response_controlled_lost')]
 if x['mode']!='positive':
  assert len(lost)==1 and lost[0].get('request_key')
  endpoint='/resource-delivery/recovery/' if x['mode']=='lost_commit' else '/plan-approval/recovery/'
  assert any(c['method']=='GET' and c['status']==200 and c['path'].endswith(endpoint+lost[0]['request_key']) for c in calls)
 modes.append(dict(mode=x['mode'],actual_browser=x['actual_browser'],browser_version=x['browser_version'],request_count=len(calls),resource_commits=len(com),proposal_posts=len(proposed),approval_posts=len(approved),controlled_lost_replies=lost,raw=str(p.relative_to(R)),sha256=sha(p)))
assert {x['mode'] for x in modes}=={'positive','lost_commit','lost_propose','lost_approve'}
browser=dict(source_sha=source,status='LIMITED_ACTUAL_CHROMIUM_PASS',formal_passes=br['counts']['PASS'],included_in_new_union=True,modes=modes,python_control_http_total='NOT_RECORDED',raw_window_sha256=sha(B/'new-chromium.json'),limitations=['Four Chromium modes exactly listed; Node403/ABA modes do not become browser coverage.','Source changes/ADOPT and prerequisite P1 repair use Python controls; Chrome performs reapproval then P2-P5 verification.','Windows and formal AT remain NOT_RUN.'])
O.mkdir(exist_ok=True)
for name,value in [('coverage.json',coverage),('html.json',htmlsummary),('closure.json',closure),('browser.json',browser)]:
 p=O/name;assert not p.exists(),p;p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(source_sha=source,new_passes=len(N),coverage_counts=coverage['counts'],html_nativefetch=htmlsummary['actual_nativefetch_total'],closure_counts=closure['record_counts'],browser_status=browser['status'])))
