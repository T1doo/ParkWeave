from pathlib import Path
import ast, hashlib, json, re, shlex, subprocess, sys, time, traceback

ROOT=Path('/workspace/ParkWeave')
E=ROOT/'.runtime/material-two-case-demo-20261018'
OUT=Path(__file__).parent
SOURCE='24f6db12490b7ba7f01099d311af97e926eeddd0'
START=time.monotonic()

def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def strict(path):
    def unique(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError('duplicate JSON member')
            d[k]=v
        return d
    def bad(v): raise ValueError('non-finite JSON number')
    return json.loads(path.read_text(),object_pairs_hook=unique,parse_constant=bad)
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def dump(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

paths=[ROOT/'scripts/material_only_demo.py',ROOT/'scripts/linux_fixture_server.py',
       ROOT/'src/parkweave/web.html',ROOT/'src/parkweave/preparation.py',
       ROOT/'src/parkweave/controlled_plans.py',ROOT/'src/parkweave/store.py',
       ROOT/'src/parkweave/case_fact_clarifications.py',ROOT/'src/parkweave/process_env.py']
paths+=sorted(E.glob('*.json'))
paths+=[E/'sandbox-browser-original-error.txt']
pre={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
dump('inputs-pre.json',pre)
checks=[]
def check(name,condition):
    if not condition: raise AssertionError(name)
    checks.append(name)

try:
    check('exact_shared_HEAD',git('rev-parse','HEAD')==SOURCE)
    tree=git('rev-parse','HEAD:src')
    check('original_product_src_tree',tree=='9b21f97b8e25fd9a589e41bb9a3068d7943e0734')
    check('reviewed_worktree_paths_equal_HEAD',not git('diff','--name-only','HEAD','--','src','scripts/material_only_demo.py','scripts/linux_fixture_server.py'))
    source=(ROOT/'scripts/material_only_demo.py').read_text()
    syntax=ast.parse(source)
    rights=next(ast.literal_eval(n.value) for n in syntax.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SQL_RIGHTS' for t in n.targets))
    check('P2_minimal_controlled_plan_UPDATE_columns',rights['UPDATE(invalidated_from,invalidated_at)']==('controlled_plans',))
    check('P2_no_controlled_plan_INSERT',not any('INSERT' in op and 'controlled_plans' in tables for op,tables in rights.items()))
    check('P2_stop_children_failure_records_marker',"stop_children(children)\n                    except BaseException:\n                        (p / 'stop-unconfirmed').touch(exist_ok=True)\n                        raise" in source)
    check('resume_refuses_stop_marker',"if (p / 'stop-unconfirmed').exists():" in source)
    check('safe_loopback_probe_reuse',"probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)" in source and "probe.bind(('127.0.0.1', port))" in source)
    check('original_live_receipt_API_no_restore', 'cluster.record_created_database(c)' in source and 'owner._case_fact_fixture_receipt = receipt' in source and source.count('owner.migrate()')==1)
    docs={p.name:strict(p) for p in E.glob('*.json')}
    final=docs['final-material-validation.json']
    initial=docs['initial-business-snapshot.json']
    before=docs['before-restart-business-snapshot.json']
    after=docs['final-restart-business-snapshot.json']
    counts=dict(principals=2,capability_grants=3,action_grants=1,preparation_grants=2,preparation_catalog=1,run_assignments=0,field_grants=0,synthetic_resources=0,synthetic_resource_grants=0)
    check('exact_2_plus_3_plus_1_plus_2_plus_1_authority_counts',all(d['authority']['counts']==counts for d in (initial,before,after)))
    check('authority_aggregate_digest_equal_only_no_private_rows_read',initial['authority']==before['authority']==after['authority'])
    check('pre_restart_equals_final_snapshot',before==after)
    check('zero_initial_business_rows',all(n==0 for n in initial['counts'].values()))
    expected_counts=dict(runs=2,cases=2,preparations=2,preparation_evidence=4,preparation_events=10,model_steps=0,model_plans=0,run_assignments=0,controlled_plans=0)
    check('final_business_counts_and_forbidden_tables',after['counts']==expected_counts==final['final_business_counts'])
    check('SQL_restriction_observations_false',all(v is False for v in after['restrictions'].values()))
    check('three_distinct_source_stages_preserved',final['setup_source_commit']=='4e55fa77caa54bf15715189588c9dcd8fd0b890c' and final['material_write_tested_source_commit']=='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765' and final['restart_tested_source_commit']==SOURCE)
    check('first_window_failure_retained',final['first_window_overall_exit']==1 and docs['restart-settlement.json']['launcher_exit']==1)
    check('final_restart_launcher_exit_zero',docs['final-restart-settlement.json']['launcher_exit']==0 and docs['final-restart-settlement.json']['ready']['source_commit']==SOURCE)
    check('final_restart_9_GETs_no_business_POST',len(final['final_restart_traffic'])==9 and all(t['method']=='GET' and t['status']==200 for t in final['final_restart_traffic']))
    traffic=docs['http-partial-failure.json']['traffic']
    check('first_window_actual_26_recorded_HTTP',len(traffic)==26)
    neg=[t for t in traffic if t['status']==403]
    check('four_wrong_role_403_records',len(neg)==4 and len(neg)==final['negative_role_requests_403'])
    cases=final['cases']
    check('two_distinct_case_prep_run_ids',len(cases)==2 and all(len({c[k] for c in cases})==2 for k in ('case_id','preparation_id','run_id')))
    web=(ROOT/'src/parkweave/web.html').read_text()
    states={s['preparation_id']:s for s in after['states']}
    material_ids=set()
    details=[]
    for c in cases:
        label=c['label']; original_path=E/f'readiness-{label}.json'; restart_path=E/f'readiness-{label}-restart.json'
        r=docs[original_path.name]; rr=docs[restart_path.name]
        check(label+'_readiness_bytes_equal_after_restart',original_path.read_bytes()==restart_path.read_bytes())
        check(label+'_IDs_and_revision_bound',r['preparation_id']==c['preparation_id'] and r['case_id']==c['case_id'] and r['preparation_revision']==c['revision']==5)
        snapshot=states[c['preparation_id']]
        check(label+'_persisted_run_case_binding',all(snapshot[k]==c[k] for k in ('preparation_id','case_id','run_id')))
        check(label+'_local_confirmation_does_not_complete_Case',snapshot['state']=='LOCAL_CONFIRMED' and snapshot['run_state']=='SUCCEEDED' and snapshot['case_state']=='NEEDS_INPUT')
        s=r['sources']; ms=s['materials']; review=s['manual_review']; service=s['service']
        check(label+'_source_sha256_recomputed',sha(canonical(s))==r['source_sha256'])
        check(label+'_two_v1_materials',len(ms)==2 and {m['slot'] for m in ms}=={'need_summary','material_outline'} and all(m['version']==1 and m['authenticity']=='UNVERIFIED' for m in ms))
        check(label+'_every_material_SHA256_recomputed',all(sha(m['text'].encode())==m['source_sha256'] for m in ms))
        check(label+'_synthetic_distinct_input_texts',next(m['text'] for m in ms if m['slot']=='need_summary')==c['need'] and next(m['text'] for m in ms if m['slot']=='material_outline')==c['outline'])
        material_ids.update(m['id'] for m in ms)
        binding=dict(preparation_id=c['preparation_id'],service_id=service['service_id'],service_version=service['version'],materials=ms)
        check(label+'_review_snapshot_SHA256_recomputed',sha(canonical(binding))==review['review_sha256']==snapshot['review_sha256'])
        check(label+'_original_specialist_REVIEW_revision4',review['reviewer_id']=='material-demo-specialist' and review['current_authority'] is True and review['decision']['action']=='REVIEW' and review['decision']['revision']==4 and review['decision']['actor_id']=='material-demo-specialist')
        check(label+'_readiness_not_assessed_qualification_unknown',r['state']=='NOT_ASSESSED' and r['current_truth']=='UNKNOWN' and r['current_inputs']['local_preparation_truth']=='TRUE' and r['current_inputs']['qualification_truth']=='UNKNOWN' and r['current_inputs']['qualification_decision']=='NOT_EVALUATED' and r['current_inputs']['case_goal_completed'] is False and r['current_inputs']['external_acceptance']=='NOT_SUBMITTED')
        commands=[t for t in traffic if t['path']==f"/api/preparations/{c['preparation_id']}/commands"]
        check(label+'_recorded_role_status_order',[(t['actor'],t['status']) for t in commands]==[('enterprise',200),('enterprise',200),('enterprise',403),('specialist',200),('specialist',403),('enterprise',200)])
        e=docs[f'export-{label}.json']; er=docs[f'export-{label}-restart.json']
        check(label+'_export_hash_size_ID_metadata_stable',all(e[k]==er[k] for k in ('bytes','sha256','case_id','preparation_id','source_js_sha256')) and e['case_id']==c['case_id'] and e['preparation_id']==c['preparation_id'])
        check(label+'_exports_explicitly_not_browser_download',e['browser_download'] is False and er['browser_download'] is False and e['mechanism']=='ORIGINAL_PURE_JS_TEXT_GENERATOR_IN_NODE_VM_FROM_REAL_HTTP_READINESS')
        details.append(dict(label=label,case_id=c['case_id'],preparation_id=c['preparation_id'],revision=5,materials=2,material_versions=[1,1],source_sha256_recomputed=True,review_sha256_recomputed=True,export_metadata_equal=True,export_file_bytes_independently_read=False))
    check('four_unique_material_ids',len(material_ids)==4)
    check('two_distinct_export_hashes',docs['export-A.json']['sha256']!=docs['export-B.json']['sha256'])
    revision=docs['explicit-sql-source-revision.json']; revision2=docs['restart-explicit-source-revision.json']
    check('explicit_SQL_revision_bounded_metadata',revision['sql_column_update_added']==['controlled_plans.invalidated_from','controlled_plans.invalidated_at'] and revision['controlled_plan_insert'] is False and revision['new_setup_or_new_session'] is False and revision['schema']==32 and revision['authority_counts']==counts)
    check('explicit_resume_revision_no_setup_or_receipt_reconstruction',revision2['new_source_commit']==SOURCE and all(revision2[k] is True for k in ('authority_unchanged','sql_permissions_unchanged','creation_observation_bytes_unchanged','sessions_bytes_unchanged','no_new_setup','no_issued_receipt_reconstructed','old_state_bytes_retained')))
    check('root_summary_single_setup_no_model_real_business',final['setup_count']==1 and final['session_generation_count']==1 and final['real_model_calls']==0 and final['real_business']=='NOT_RUN' and final['windows_formal_at']=='NOT_RUN' and final['local_synthetic_demo_profile'] is False)
    browser=docs['sandbox-browser-result.json']
    raw=(E/'sandbox-browser-original-error.txt').read_text()
    launches=[line.strip().removeprefix('- ').strip() for line in raw.splitlines() if '<launching> ' in line]
    argument_vectors=[shlex.split(line.split('<launching> ',1)[1]) for line in launches]
    check('launch_vectors_not_no_sandbox',bool(argument_vectors) and all('--no-sandbox' not in args for args in argument_vectors))
    check('one_reported_refused_attempt_log_two_renderings_one_pid',browser['attempts']==1 and browser['chromium_sandbox'] is True and browser['no_sandbox_argument'] is False and browser['business_page_opened'] is False and len(set(re.findall(r'<launched> pid=(\d+)',raw)))==1)
    check('browser_and_browser_download_scope_not_run',final['real_browser']=='REFUSED_ONCE_NO_RETRY' and final['browser_download']=='NOT_RUN_SANDBOX_REFUSED')
    check('original_bind_failure_cause_remains_unproven','exact cause unproven' in docs['restart-bind-diagnostic.json']['original_failure'])
    post={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
    dump('inputs-post.json',post)
    check('all_reviewed_input_bytes_zero_drift',post==pre)
    check('HEAD_unchanged_after_review',git('rev-parse','HEAD')==SOURCE)
    draft=dict(source_sha=SOURCE,src_tree=tree,kind='INDEPENDENT_STATIC_AND_PARENT_PUBLIC_EVIDENCE_REVIEW',independent_business_tests_executed=0,passed_business_tests=None,pytest_executed=False,DB_executed=False,browser_executed=False,private_state_sessions_DBlogs_read=False,P1=0,P2=0,blockers=0,closed_findings=[dict(id='controlled_plans_row_lock_privilege',status='CLOSED_STATIC_WITH_PARENT_REPORTED_HTTP_POSITIVE',lines='scripts/material_only_demo.py:42-52'),dict(id='unconfirmed_application_stop_restart',status='CLOSED_STATIC_FAILURE_PATH_NOT_INJECTED',lines='scripts/material_only_demo.py:259-265')],checks=checks,check_count=len(checks),input_count=len(pre),input_manifest_pre='inputs-pre.json',input_manifest_post='inputs-post.json',input_drift=0,reviewed_script_sha256=sha((ROOT/'scripts/material_only_demo.py').read_bytes()),reviewed_web_sha256=sha((ROOT/'src/parkweave/web.html').read_bytes()),scenarios=details,evidence_count=len(docs),HTTP_parent_records=dict(initial=len(traffic),initial_wrong_role_403=len(neg),final_GET_only=len(final['final_restart_traffic'])),launch_log=dict(launch_line_renderings=len(launches),unique_launched_pids=1,no_sandbox_argument_in_vectors=False),limits=['No independent live setup, database, API, browser, model, Windows or actual business execution.','Parent public JSONs were independently cross-checked; private database rows, sessions, token hashes and private state/DB logs were not read. Aggregate authority digest equality is parent-evidence equality, not an independent database query.','Private TXT file bytes were not read; only public export hash/size/subject metadata was cross-checked. Parent NodeVM runs are not browser downloads.','Recorded command traffic has actor/path/status but no request action/body; action semantics are cross-checked through public material/review/readiness/state evidence.','Stop-failure marker fix was statically inspected; failure injection was not executed.','The first overall window exit1 and original restart OSError with missing original errno remain preserved; a later bind diagnostic does not prove its exact initial cause.','Readiness current_inputs local truth TRUE is distinct from NOT_ASSESSED/current_truth UNKNOWN; Case remains NEEDS_INPUT and qualification UNKNOWN/NOT_EVALUATED.','HEAD:src plus bootstrap SHA binding does not independently guarantee arbitrary uncommitted runtime source immutability.'],elapsed_seconds=time.monotonic()-START)
    dump('audit-result-draft.json',draft)
    print(json.dumps(dict(status='PASS_STATIC_AND_EVIDENCE_REVIEW',source_sha=SOURCE,checks=len(checks),inputs=len(pre),input_drift=0,P1=0,P2=0,business_tests_executed=0,output_dir=str(OUT)),ensure_ascii=False))
except BaseException:
    (OUT/'audit-failure.txt').write_text(traceback.format_exc())
    raise
