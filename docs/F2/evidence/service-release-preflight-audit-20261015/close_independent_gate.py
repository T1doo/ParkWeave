"""Close the independent gate after pair, coverage and trace evidence passes.

Reads only frozen source and designated evidence, and writes only this new audit
directory. Existing root status is compared but never used as the verdict oracle.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import ast,hashlib,json,re,subprocess
from audit_archive_pairs import frozen,record,known_private,candidates
R=Path('/workspace/ParkWeave');O=R/'.runtime/service-release-preflight-audit'
A=R/'docs/F2/evidence/service-release-preflight-20261015'
S='0de44714499ff3ead538dd8dc1436e783ab8f944'
B='b2690b4316e2ca4e98c0b83ee2675db74239ccae'
def read(p):return json.loads((R/p).read_text())
def own(p):return json.loads((O/p).read_text())
def save(p,v):(O/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def now():return datetime.now(timezone.utc).isoformat()
def report_review():
    path=R/'docs/F2/ServiceReleasePreflight-20261015.md';text=path.read_text();readme=(A/'README.md').read_text()
    required=[S,'67个完整相关模块','2187个唯一测试','0 FAIL/ERROR/SKIP','不是一次全仓运行','599个受控源码路径','12078 tracked','known' if False else '已知15例/62对','UNKNOWN4例/20对','14明确分12条实际后端响应流','两条DOM/transport负向','5704','334','authorization_audit','PREPARE/EXECUTE','current_available=false','不会' if False else '不授权','F5-T04','NOT_RUN','模型调用0','64PASS/exit2','3ERROR','KeyError','预收集','原始节点从未归一','PENDING']
    assert all(x in text for x in required)
    assert '273' in readme and '36,174,819' in readme and '32处' in readme and '72行' in readme and '后续结果' in readme
    links=[]
    for m in re.finditer(r'\[[^\]]+\]\(([^)]+)\)',readme):
        target=m.group(1);p=(A/target).resolve()
        if 'service-release-preflight-audit-20261015' in target:
            links.append({'target':target,'state':'EXPECTED_SIBLING_TO_BE_COPIED_AFTER_AUDIT'});continue
        assert p.is_relative_to(A.resolve()) and p.exists();links.append({'target':target,'state':'EXISTS'})
    root=ast.parse((R/'src/parkweave/service_release_preflight.py').read_text())
    flag_call=next(x.value for x in root.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in x.targets))
    assert isinstance(flag_call,ast.Call) and isinstance(flag_call.func,ast.Name) and flag_call.func.id=='dict'
    flags={k.arg:ast.literal_eval(k.value) for k in flag_call.keywords}
    expected={'read_only':True,'automatically_replayed':False,'automatic_migration':False,'automatic_adoption':False,'automatic_execution':False,'execution_enabled':False,'provider_enabled':False,'new_grants':False,'business_publication':False,'case_goal_completed':False,'qualification_decision':'NOT_EVALUATED','future_validity_guaranteed':False}
    assert flags==expected
    web=(R/'src/parkweave/web.html').read_text();line=next(l for l in web.splitlines() if l.startswith('function serviceReleasePreflightBase('))
    for flag in ['automatic_migration','automatic_adoption','automatic_execution','execution_enabled','provider_enabled','new_grants','business_publication','case_goal_completed']:assert "'"+flag+"'" in line
    assert 'x.read_only!==true' in line and 'x.automatically_replayed!==false' in line
    result={'status':'PASS','source_sha':S,'report_path':str(path.relative_to(R)),**record(path),'primary_readme':record(A/'README.md'),'readme_links':links,'supported_claims':[
        'Exact sameSHA four disjoint complete affected-module windows; not whole repository and no old test reuse',
        'Original six goals/P1-P5/history/locks maintained; preflight evidence is never adoption/verification/grant',
        'Known15/62 versus conservative UNKNOWN4/20 kept separate; title-only current binding can require allCase recheck despite informational contract compatibility',
        '29 full original NodeVM modes:27 actual service paths plus2 designated transport/DOM negatives,12 actual newpreflight plus2 negative; controlled faults and no actual browser explicitly retained',
        '5704 Python and334 Node request surfaces not presented as fulfillment or added testcounts',
        'Business PG read-only with existing Denied authorization_audit writes explicitly retained',
        'Separate immutable ConsumerRepository evidence journal, no distributed atomicity or future-validity guarantee',
        'Current READ and owner required for historical log; PREPARE/EXECUTE-only withdrawal can preserve READ history/current_available=false',
        'Historical compiler probe is direct frozen validator seam; graph probes are actualHTTP/ASGI/ownedPG; all3 separate',
        'KeyError,3ERROR,64PASS interrupted reviewer window and backend/HTML/coverage development failures retained honestly',
        'Exact import-timeUUID precollection-only exception, raw per-window collection/JUnit never normalized',
        'Finite F3-T03/AT27 subset only, remaining formal AT24-27/governance/generalgraph/manualmerge/Windows/browser/models/production/remoteCI retained'],
        'flags_static_and_UI_parser_confirmed':flags,'flags_limits':'Static exact source flags and current UI parser contract, not an assertion that HTTP instrumentation saved every raw response field',
        'report_pending_archive_wording':'Correct at read time; parent may replace only PENDING archive section after final independentPASS and append sibling links',
        'remaining_scope_findings':[]}
    save('public-report-independent-review.json',result);return result

def close():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==S
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R).strip()
    pair=own('archive-independent-pairs.json');mechanical=own('final-gate-mechanical.json');prec=own('precollection-identity-independent.json');traffic=own('actual-http-mode-independent.json')
    assert pair['status']=='PAIR_REBUILD_PASS_FINAL_COVERAGE_GATE_PENDING' and all(x['status']=='PASS' and x['source_sha']==S for x in [mechanical,prec,traffic])
    assert pair['checks']=={'files':273,'bytes':36174819,'python':25,'xml':20,'json':79,'javascript':2,'jsonl':57}
    assert pair['redactions']=={'exact_private_value':32,'fixture_repr_line':72} and pair['known_private_residuals']==0 and all(x['exit_code']==0 for x in pair['javascript_syntax'])
    report=report_review()
    current=frozen(S);prepared=own('prepare-source-snapshot.json')['all_tracked']
    assert current==prepared and len(current)==12078 and sum(x['bytes'] for x in current.values())==299114094
    freeze=read('.runtime/service-release-preflight/final-freeze.json');assert len(freeze['hashes'])==freeze['source_paths']==599
    assert all(current[p]['sha256']==h for p,h in freeze['hashes'].items())
    for section,snapshot in [('raw','raw-snapshot.json'),('export','export-snapshot.json')]:
        for p,spec in own(snapshot).items():assert record(R/p)==spec,section+' drift: '+p
    assert set(own('raw-snapshot.json'))=={str(p.relative_to(R)) for p in candidates()}
    for p,spec in pair['supplemental_metadata'].items():assert record(A/p)==spec
    _,privates=known_private();assert privates==pair['private_sets']
    changed=subprocess.check_output(['git','diff','--name-only',B,S],cwd=R,text=True).splitlines()
    expected=['scripts/windows_ci/diagnostic-test-ids.json','src/parkweave/api.py','src/parkweave/service_release_preflight.py','src/parkweave/web.html','tests/service_release_preflight_real_html.js','tests/test_service_release_preflight.py','tests/test_service_release_preflight_independent.py']
    assert changed==expected and not any(p.startswith('docs/') for p in changed)
    save('final-source-archive-closure.json',{'status':'PASS','source_sha':S,'utc':now(),'tracked_source_paths':599,'all_tracked_paths':12078,'all_tracked_bytes':299114094,'all_tracked_same_as_preparation_and_git_blobs':True,'raw_export_metadata_private_registry_inventory_unchanged_since_pair_audit':True,'baseline_sha':B,'baseline_diff_paths':changed,'old_tracked_docs_and_archives_unchanged':True,'working_tracked_tree_clean':True,'head_still_exact_freeze':True,'source_change_or_Git_write_by_reviewer':False,'public_report_sha256':report['sha256']})
    differential=(O/'redaction-differential-final.log').read_text();assert '17 passed' in differential
    result={'status':'PASS','source_sha':S,'utc':now(),'new_blockers':[],
        'scope':'Linux synthetic isolated owned data: finite same-family/latest-reviewed-head singleCase ServiceRelease compatibility and currentCase recheck evidence only',
        'archive':{'primary':'docs/F2/evidence/service-release-preflight-20261015','index_sha256':pair['index_sha256'],'raw_export_pairs':273,'export_bytes':36174819,'raw_and_export_hash_size_and_inventory_rebuilt':True,'independent_deterministic_reconstruction':True,'root_producer_or_verifier_imported':False,'redactions':pair['redactions'],'known_private_values':pair['known_private_values'],'known_private_residuals':0,'structure_counts':pair['checks'],'raw_source_export_and_private_sets_unchanged':True,'metadata_complete':True},
        'redactor_assurance':{'prior_shared_fast_matcher_provenance_disclosed':True,'algorithmic_diversity_claimed':False,'current_differential_tests':17,'deterministic_random_cases':200,'non43pool_or_overlap_original_ordered_replace_fallback':True,'pool_values_disclosed':False},
        'source':{'tracked_source_paths':599,'tracked_plus_editable_metadata':604,'all_tracked_paths':12078,'all_tracked_bytes':299114094,'same_as_git_blobs_before_after':True,'old_tracked_docs_and_evidence_unchanged':True,'product_changes_from_baseline':expected},
        'formal_coverage':mechanical['coverage'],'separate_runtime_probes':mechanical['separate_runtime_negative_probes'],'literal_oracles':mechanical['oracles'],'html':mechanical['html'],
        'actual_http':{'Node334':traffic['node_methods'],'Python5704':traffic['python_methods'],'surfaces_not_added':True,'new_preflight_actual_posts6_only_private_log_endpoint':True},
        'precollection_exception':{'exact_function_case_id_UUID_only':True,'planned_only':prec['raw_difference']['planned_only'],'actual_only':prec['raw_difference']['actual_only'],'actual_same_invocation_raw_collection_JUnit_never_normalized':True,'original_source_unchanged_and_failed_postcheck_preserved':True},
        'independent_auditor_receipts':{'primary_metadata_missing_README_first_stop':'audit-first-stop-receipts.json','dependent_gate_missing_pairs_first_stop':'audit-first-stop-receipts.json','supplemental_literal_and_trace_field_setup_assertions':'supplemental-self-check-receipt.json','prepared_oracle_count_adjustment_before_execution':'preparation-oracle-count-adjustment.json','original_logs_and_scripts_preserved':True,'product_failures':False},
        'reviewer_test_runner_history':'Primary archive retains2 pre-pytest setup KeyErrors,3ERROR first fixture probe and interrupted64PASS/exit2 isolation-suspect window; none reused in67/2187 or3finalprobes',
        'public_report_review':'PASS_CONTENT_FLAGS_LINKS_LIMITS; its archivePENDING marker is intentionally updated by integrator only after thisPASS',
        'remaining_unverified':['Windows/Win11','Actual browser','Formal AT24-27 and complete AT27','General graph propagation/compatibility/manual merge beyond finite contract','F5 upgrade/migration/rollback/backup restore execution','Real product models/B0-B2','Formal source governance/business authorization and realworld outputs/receipts','Production/deployment','This branch remote CI'],
        'no_action_authorized_by_preflight':['publication','migration','rollback','Approval','ADOPT','VERIFY','execution','new grants'],
        'qualifications':['Business PG read-only excludes existing authorization_audit denial recording','CurrentREAD required for history; PREPARE/EXECUTE-only revocation may keep historicalREAD/current_available=false','No distributed atomicity among original SQLite,private evidenceSQLite andPG, or guarantee after finalsource read','Controlled lost/late/tampered and2DOM/transport fixtures remain synthetic, NodeVM is not actualbrowser','Known/UNKNOWN oracle counts remain separate, unknown conservative expansion is not precision'],
        'public_artifact_manifest':'final-artifact-index.json (produced after final publicability scan; excludes itself to avoid self-reference)',
        'reviewer_only_writes':'New .runtime/service-release-preflight-audit; no primary,raw,source,tests,Git or old evidence edits'}
    save('final-gate.json',result)
    (O/'final-gate.md').write_text('''# ServiceRelease 预检独立归档终门

PASS，精确源码 `0de44714499ff3ead538dd8dc1436e783ab8f944`，无剩余本范围阻断。仅 Linux 合成有限同谱系单 Case 只读兼容/再核对预检；记录不是采纳、VERIFY、发布、迁移、回滚或新授权。

独立重建273对/36,174,819B，raw/export hash、大小、清单、确定性去敏逐字节一致；32处指定合成值和72行fixture repr遮蔽，18,673个指定合成值残留0。20 XML、79 JSON、57 JSONL、25 Python、2 JS结构/源及用例状态核验通过。17个独立差分自检（含200个确定性随机样本）通过；共用fast helper来源明确，不声称算法多样性。所有原件、private集合、导出、四元数据与12078 tracked前后保持。

四个同SHA互不重叠完整模块窗：root27/900、root25/789、independent6/198、review9/300，合计67完整模块/2187唯一PASS，0 FAIL/ERROR/SKIP。另3边界probe PASS单列。并非一次全仓运行，不复用旧成绩。原预收集仅一个原函数case_id导入期UUID差异，窄形状归一后并集一致；每个实际窗raw collection/JUnit始终原样精确一致。

42份本窗字面oracle：新预检19例82对，分known15/62与UNKNOWN4/20，锁3对；旧typed11/38和shared12/24真实本窗重跑，漏更/误改/误保留/误锁0。29个完整原HTML NodeVM模式分27条实际服务链与pending/unknown_dto两条DOM/transport负向，新预检12+2；不冒充真实浏览器或29项后端拒绝。5704个Python loopback请求（4159POST/1545GET）和334个Node实际fetch（34POST/300GET）是不同观测面，不相加。新预检86请求中6POST全为独立私有证据日志。

原六目标、P1–P5、旧历史、未受影响锁及原授权门保持。业务PG只读，原Denied authorization_audit例外明确；新专用ConsumerRepository只记录不可变预检证据，不保证分布式原子提交或未来有效性。历史READ与PREPARE/EXECUTE撤权区分。599源码+5editable元数据，12078旧tracked/299114094B及Git blob无漂移；旧docs/archives未改。

保全首次缺README停点及其依赖gate停点；集成者仅补人读metadata后新前缀重建通过。独立补充脚本两次字面/schema断言修正的原脚本与日志保留，非产品失败。此前review runner2KeyError、3ERROR、64PASS/exit2中断窗保留，不并入最终成绩。

Windows、真实浏览器、正式AT24–27/完整AT27、真实模型/B0–B2、一般图/深层兼容人工合并、F5迁移回滚备份恢复、正式来源治理/业务批准与真实履约、生产和本分支远端CI未验证。模型0；无费用/权限扩展或发布部署。

主报告当前归档PENDING文字符合尚待本终门时点；集成者可在本PASS后只更新归档结果并复制本目录公开附件。详见final-gate.json、archive-independent-pairs.json、public-report-independent-review.json及final-artifact-index.json。
''')
    print(json.dumps({'status':'PASS','source_sha':S,'pairs':273,'formal_modules':67,'formal_PASS':2187,'separate_probe_PASS':3,'new_blockers':[]}))

if __name__=='__main__':close()
