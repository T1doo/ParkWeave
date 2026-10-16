"""Read only final completed frozen raw; never runs tests or edits design oracle."""
from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
R=Path.cwd(); OUT=R/'.runtime/unified-propagation-oracle/final'; BASE=R/'.runtime/unified-propagation-final'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
freeze=read(R/'.runtime/unified-propagation-root/freeze.json'); raw=read(BASE/'new.json'); source=freeze['source_sha']
assert raw['source_sha']==source==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert raw['exit_code']==0 and raw['counts']==dict(PASS=88,FAIL=0,ERROR=0,SKIP=0)
assert raw['collection_junit_exact_match'] and raw['unique_junit_nodes']
assert not any(raw[k] for k in ('source_drift','all_tracked_drift','runner_drift'))
for p,h in freeze['source_paths'].items():assert sha(R/p)==h,p
nodes=raw['collected_nodes'];assert len(nodes)==len(set(nodes))==88
cases=list(ET.parse(BASE/'new.xml').iter('testcase'));assert len(cases)==88
assert all(not any(c.find(k) is not None for k in ('failure','error','skipped')) for c in cases)
art=BASE/'artifacts/new/test_unified_dependency_propagation_independent';assert art.is_dir()
public=[p for p in art.iterdir() if p.is_file() and not p.name.endswith('.private.json')]
raw_hashes={str(p.relative_to(R)):sha(p) for p in sorted(public+[BASE/'new.json',BASE/'new.xml',BASE/'new-collection.json'])}
oracle=R/'docs/F2/UnifiedSourcePropagationOracle-20261016.json';design=read(oracle);assert len(design['rows'])==36
assert design['status']=='DESIGN_ONLY_NOT_EXECUTED'
def evidence(needle):
 found=[n for n in nodes if needle in n];assert found,needle
 return [dict(identity=n,status='PASS') for n in found]
rows=[]
for d in design['rows']:
 k=d['id'];i=int(k[2:]);ev=[];kind='NOT_RUN';note='No exact execution assigned.'
 if i<=24:
  ev=evidence('test_frozen_literal_partitions_and_consumer_observation_seeds['+k+']');kind='PURE_LITERAL';note='Exact literal partition; synthetic snapshots, no HTTP.'
 else:
  mapping={25:('test_receipt_change_retains_three_original_locked_steps','HTTP_BEHAVIOR_VARIANT','Original design locks P1; actual also locks and preserves P2/P3.'),26:('test_resource_change_affected_manual_lock_needs_original_unlock','HTTP_LITERAL','Original explicit lock/unlock and full closure.'),27:('test_manual_source_conflict_reuses_original_explicit_package_decisions','HTTP_LITERAL','Original source conflict observed before both original decisions.'),28:('test_manual_source_conflict_reuses_original_explicit_package_decisions[KEEP_AND_CONTINUE]','HTTP_LITERAL','Original explicit package confirmation and closure.'),29:('test_manual_source_conflict_reuses_original_explicit_package_decisions[DEFER]','HTTP_LITERAL','Original explicit DEFER remains blocked.'),30:('test_resource_row_a_b_a_refuses_preview_after_values_restore','HTTP_LITERAL','Resource row committed ABA rejects original preview.'),31:('test_same_key_altered_scope_and_actual_original_cold_get','HTTP_LITERAL','Altered scope rejected with original key; unchanged retry idempotent.'),32:('test_full_original_html_unified_adoption_and_authority[lost_ack]','HTML_ACTUAL_HTTP','Actual commit then controlled response loss; original keyed cold GET.'),33:('test_new_v4_then_original_default_v2_is_nonsticky','HTTP_BEHAVIOR_VARIANT','Actual default v2 after v4; does not establish all original request bytes.'),34:('test_new_v4_then_original_default_v2_is_nonsticky','HTTP_BEHAVIOR_VARIANT','Only v4 to default v2 here; cannot claim all v1/v2/employees-v3 historical variants.'),35:('test_rehashed_forged_v4_graph_refuses_original_plan_goal_and_cold_reads','HTTP_LITERAL','Three mutations observation/edge/path and original read rejection.'),36:('test_full_original_html_unified_adoption_and_authority[late_403]','HTML_ACTUAL_HTTP','Actual held403 after original READ revocation; identity ABA and new Case preserved.')}
  needle,kind,note=mapping[i];ev=evidence(needle)
 rows.append(dict(id=k,literal_expected=d,execution='PASS_WITH_SCOPE_LIMIT' if ev else 'NOT_RUN',coverage_kind=kind,evidence=ev,note=note))
# Mixed source material/fact/resource/receipt and catalog mutation differ from UP09's exact direct sources.
variant_ev=evidence('test_actual_mixed_material_fact_resource_receipt_explicit_adopt_verify')+evidence('test_catalog_rule_contract_mixed_change_preserves_original_explicit_replacement_refusal')
rows[8]['variants']=[dict(coverage_kind='HTTP_BEHAVIOR_VARIANT',evidence=variant_ev,note='Same all-five partition, but actual direct sources are mixed across observations; rule catalog mutation is separately rejected by CATALOG_CHANGED. No positive rule replacement claimed.')]
counts={k:sum(r['coverage_kind']==k for r in rows) for k in sorted({r['coverage_kind'] for r in rows})}
coverage=dict(source_sha=source,formal_new_passes=88,oracle_sha256=sha(oracle),design_status_unchanged=design['status'],rows=rows,counts=counts,raw_sha256=raw_hashes,limitations=['Pure literal and HTTP variants are separate.','UP09 exact pure literal; actual mixed positive and catalog refusal are variants.','UP34 covers v4 then v2 only; old full history dispatch coverage must be separately identified.'])
html=[]
for mode in ('positive','lost_ack','current_403','late_403'):
 matches=[]
 for p in art.glob(mode+'-*.stdout.jsonl'):
  parsed=lines(p); finals=[x for x in parsed if x.get('scope')=='FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG']
  if finals:matches.append((p,parsed,finals))
 assert len(matches)==1,(mode,len(matches))
 p,parsed,finals=matches[0];assert len(finals)==1
 f=finals[0];calls=f['calls'];traces=[x['trace'] for x in parsed if 'trace' in x];assert traces==calls
 assert f['fake_dto'] is False and f['real_browser']=='NOT_RUN' and f['mode']==mode
 post=[c for c in calls if c['method']=='POST'];adopt=[c for c in post if c['path'].endswith('/service-case-plan')]
 verifies=[c for c in post if c.get('body',{}).get('action')=='VERIFY']
 recover=[c for c in calls if c['path'].endswith('/service-case-plan/command-recovery') and c.get('request_key')]
 denials=[c for c in calls if c['status']==403]
 if mode in ('positive','lost_ack'):
  assert len(adopt)==1 and adopt[0]['status']==201 and adopt[0]['body']['dependency_scope']=='BOUNDED_MULTI_SOURCE_V1'
  assert len(verifies)==5 and len({c['body']['step_id'] for c in verifies})==5 and all(c['status']==200 for c in verifies)
  assert any(c['path'].endswith('/goal-results') and c['status']==200 for c in calls)
  assert any(c.get('worklist_items') for c in calls)
  if mode=='lost_ack':assert recover and all(c['method']=='GET' and c['status']==200 and c['request_key']==adopt[0]['request_key'] for c in recover)
 else:assert not post and len(denials)==1 and denials[0]['method']=='GET'
 html.append(dict(mode=mode,actual_native_fetch_count=len(calls),methods={m:sum(c['method']==m for c in calls) for m in ('GET','POST')},checks=f['checks'],adopt_commits=len(adopt),verify_events=len(verifies),unique_verified_step_ids=len({c['body']['step_id'] for c in verifies}),actual_403_reads=len(denials),keyed_recovery_reads=len(recover),classification='ACTUAL_HTTP_ASGI_OWNED_POSTGRESQL_WITH_NODE_DOM',response_loss='CONTROLLED_AFTER_REAL_COMMIT' if mode=='lost_ack' else None,trace=str(p.relative_to(R)),trace_sha256=sha(p),real_browser='NOT_RUN'))
html_result=dict(source_sha=source,modes=html,actual_native_fetch_total=sum(x['actual_native_fetch_count'] for x in html),python_control_http_total='NOT_RECORDED',real_browser='NOT_RUN',raw_sha256=raw_hashes)
record_groups={}
for prefix in ('oracle','closures','adoptions','mixed-source-changes','catalog-rule-refusal','html-results'):
 entries=[row for p in art.glob(prefix+'-*.jsonl') for row in lines(p)];record_groups[prefix]=entries
assert len(record_groups['html-results'])==4
assert all(r['six_goals_current'] and r['worklist_complete'] and r['stable_ids_history'] and r['worklist_recorded_only'] for r in record_groups['closures'])
assert len(record_groups['catalog-rule-refusal'])==1 and record_groups['catalog-rule-refusal'][0]['no_business_writes']
closure=dict(status='LIMITED_PASS',source_sha=source,formal_new_passes=88,record_counts={k:len(v) for k,v in record_groups.items()},records_are_not_unique_cases=True,python_control_http_total='NOT_RECORDED',real_browser='NOT_RUN',windows='NOT_RUN',formal_AT='NOT_RUN',raw_sha256=raw_hashes)
OUT.mkdir(exist_ok=True)
for name,value in [('coverage.json',coverage),('html.json',html_result),('closure.json',closure)]:
 p=OUT/name;assert not p.exists(),p;p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(source_sha=source,counts=counts,html_native_fetch=html_result['actual_native_fetch_total'],closure_counts=closure['record_counts']),ensure_ascii=False))
