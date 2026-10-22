from pathlib import Path
from hashlib import sha256
import json,copy,shutil,zipfile,collections
src=Path(__file__).parent;dst=Path('/workspace/ParkWeave/docs/F2/evidence/installed-source-restart-run17-20261022');dst.mkdir(exist_ok=False)
r=json.loads((src/'artifact/result.json').read_text());log=(src/'ci-original.log').read_text();v=json.loads(next(s[s.index('{'):] for s in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage"' in s));v['status']=v.pop('observation_outcome');v.pop('terminal_result');a=copy.deepcopy(r);a.pop('seconds');a.pop('seconds_scope');assert v==a
assert r['status']=='PASS' and r['source_sha']=='ae49ed75dbb3c71b0b3a3a678d2e1c38f070c10a' and r['stage']=='INSTALLED_SOURCE_REAPPROVAL_TRUE_RESTART_COMPLETE'
job=json.loads((src/'job-api.json').read_text())['jobs'][0];assert job['status']=='completed' and job['conclusion']=='success' and all(x['conclusion']=='success' for x in job['steps'])
assert not r.get('finalization_errors') and not r['violations'] and not r['page_errors'] and 'Process completed with exit code 1.' not in log
b=r['request_budget'];assert b['POST']==32 and b['phase_POST']==dict(API_PREPARATION=25,BROWSER=5,NEGATIVE_AND_REPEAT=2) and b['GET_HEAD']==126 and b['readiness_attempts']==29
posts=[x for x in r['responses'] if x['method']=='POST'];assert len(posts)==32 and sum(200<=x['status']<300 for x in posts)==31 and sum(x['status']==409 for x in posts)==1
browser_posts=[x for x in posts if x['transport']=='BROWSER'];assert [x['status'] for x in browser_posts]==[201,200,201,200,201]
assert r['sealed_hot_plan_UI']==r['restored_cold_plan_UI'] and len(r['cold_original_reads'])==2 and all(x['API_delivery_receipt_equal'] and 'COMMITTED' in x['DOM_text'] and x['UI_link_id'] in x['DOM_text'] for x in r['cold_original_reads'])
assert r['cold_recovery']==dict(new_context=True,inherited_localStorage=False,UI_original_LINK_reads=2,API_original_delivery_GETs=2,business_POSTs=0,projection_equal=True,deadline_or_validity_renewed=False,setup_or_seed_repeated=False)
assert r['negative_checks']==dict(stale_old_approval_with_fresh_key_http=409,new_original_POST_repeat_same_receipt=True,no_additional_business_effect=True)
snapshot=r['before_restart_snapshot'];assert [x['revision'] for x in snapshot['links']]==[1,2] and len(snapshot['holds'])==6 and all(x['state']=='CONFIRMED' for x in snapshot['holds'])
tail=snapshot['preparation']['service_case_plan']['steps'][2:];assert all(s['coordination_state']=='PENDING' and s['verified_sources'] is None and s['verified_sha256'] is None for s in tail)
receipts=r['receipts_before_restart'];assert len(receipts)==2 and all(x['plan_approval']['scope']=='LOCAL_CASE_RESOURCE_APPROVAL_V1' for x in receipts) and [x['delivery_binding']['approved_plan_revision'] for x in receipts]==[3,5]
f=r['installed_CJK_font'];assert len(f['required_codepoints'])==684 and not f['missing_codepoints'];assert [(x['complete'],len(x['nodes'])) for x in r['font_observations']]==[(True,22),(True,12),(True,6)]
for obs in r['font_observations']:assert all(not n['missing_codepoints'] and not n['invalid_sources'] for n in obs['nodes'])
gens=r['service_generations'];assert len(gens)==2 and gens[0]['started']['state_dir']==gens[1]['started']['state_dir']
for role in ['api_pid','postgres_pid']:assert gens[0]['started'][role]!=gens[1]['started'][role]
assert gens[0]['started']['url']!=gens[1]['started']['url']
for g in gens:assert g['wrapper_exit']==0 and not g['cleanup']['cleanup_errors'] and g['cleanup']['postgres_marker_absent'] and g['API_listener_refused_after_stop'] and all(x['exit_code']==0 for x in g['cleanup']['children'])
assert r['installed_worker_exits']==[0] and r['setup_stop_status']=='CONFIRMED'
for name,items in r['process_installation_attestations'].items():
 assert len(items)==(4 if name=='api-attestation' else 2)
 for x in items:assert x['verified_package_files']==191 and x['isolated'] and not x['PYTHONPATH'] and x['wheel_sha256']==r['installation']['wheel_sha256']
assert len(r['screenshots'])==6 and all(s['geometry']['width']==s['geometry']['documentWidth'] and s['geometry']['navPosition']=='relative' for s in r['screenshots'])
digest='25e262c17bd63411b5666612d876aa3ca6a5cfdcf762ea06a456205f1cb4632c';assert sha256((src/'artifact.zip').read_bytes()).hexdigest()==digest
with zipfile.ZipFile(src/'artifact.zip') as z:
 assert len(z.infolist())==9 and sum(x.file_size for x in z.infolist())<8*1024**2
 for name in z.namelist():assert (src/'artifact'/name).read_bytes()==z.read(name)
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','gate-validation.json','archive_run17.py']:shutil.copyfile(src/name,dst/name)
for file in sorted((src/'artifact').iterdir()):
 if file.suffix!='.whl':shutil.copyfile(file,dst/file.name)
shutil.copyfile(src/'api-publication/publication-final.json',dst/'source-publication.json')
v=dict(scope='LIMITED_INSTALLED_LOCAL_SAME_PLAN_SOURCE_REAPPROVAL_HOT_NARROW_TRUE_STOP_RESTART_COLD_READ_ACCEPTANCE',run_id=39766682299,job_id=119783761665,attempt=1,source_sha=r['source_sha'],status='PASS',job_and_business_step='success/exit0',raw_job_log_bytes=(dst/'ci-original.log').stat().st_size,raw_job_log_sha256=sha256((dst/'ci-original.log').read_bytes()).hexdigest(),raw_result_normalized_equal=True,normalization='stdout PENDING_FINALIZATION -> observation_outcome PASS; drop terminal_result annotation and artifact seconds/seconds_scope only; all other fields exact',step_summary_body_independently_read=False,finalization_errors=[],artifact_sha256=digest,artifact_members=9,original_members_exact=True,wheel_sha256=r['installation']['wheel_sha256'],wheel_members_verified=191,wheel_build_install_dependency_downloads=0,browser_POST_key_proofs=len(r['browser_POST_key_proofs']),POST=32,successful_POST=31,denied_POST_409=1,GET_HEAD=126,main_GET_HEAD=97,readiness_GET=29,denied_GET_403=3,cold_business_POST=0,setup_repeated=False,seed_repeated=False,source_ADOPT_UI_HTTP=201,PROPOSE_UI_HTTP=201,APPROVE_UI_HTTP=200,delivery_UI_HTTP=201,old_new_original_LINK_UI_reads=2,cold_delivery_API_GETs=4,cold_delivery_unique_original_keys=2,cold_main_GET=28,cold_GET_403=1,report_cold_recovery_delivery_GETs_field_scope="cold_browser phase2; cold_api_check adds2 more",original_receipts_equal_in_runtime=True,cold_delivery_response_body_duplicate_exported=False,full_receipts_before_restart_archived=True,hot_cold_selected_plan_UI_equal=True,named_business_projection_equal_in_runtime=True,whole_database_invariance_claimed=False,deadline_or_validity_renewed=False,old_resource_holds_preserved=True,local_approvals=2,original_approved_plan_revisions=[3,5],raw_tail_coordination_states=['PENDING','PENDING'],UI_tail_states=[r['sealed_hot_plan_UI']['steps'][2]['state'],r['sealed_hot_plan_UI']['steps'][3]['state']],tail_no_VERIFY=True,font_static_codepoints=684,font_actual_visible_nodes=[22,12,6],complete_glyph_pixel_acceptance_claimed=False,screenshots=6,viewports=[1200,390],full_page_visual_acceptance_claimed=False,mobile_device_claimed=False,cold_link_v2_screenshot=True,cold_link_v1_visual_screenshot=False,cold_link_v1_DOM_text_archived=True,cold_stage_admission_seconds=r['cold_stage_admission']['elapsed'],work_completion_seconds=r['work_completion_seconds'],result_seconds_through_artifact_scan=r['seconds'],API_PG_generations=2,all_owned_processes_exit0=True,cleanup_confirmed=True,actual_worker_runs=1,real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,P1_to_P5_TXT_full_chain=False,tests_or_collection_reexecuted_this_gate_only_round=False)
(dst/'validation.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
(dst/'README.md').write_text('''# run17：安装态同计划来源再批准、390px与真实停启后只读恢复

[run17](https://github.com/T1doo/ParkWeave/actions/runs/39766682299)，attempt1，受测完整SHA `ae49ed75dbb3c71b0b3a3a678d2e1c38f070c10a`，job119783761665，最终result PASS、job/业务step success（exit0）、finalization_errors空。本轮只执行该次有界免费CI，没有重跑run16或新增测试套件。stdout仍为PENDING_FINALIZATION，不能直接算PASS；规范化仅还原observation_outcome、去封装和独有计时后，与最终result逐字段一致。step summary正文未独立读取，最终化路径未报写入/超时错误。

新建合成实例、NO_MODEL原固定P1–P4（本事项要求P1/P2），首次交付API初态；旧P1人工锁和P2原VERIFY后，一次精确可见资源fixture CAS容量/revision变化，原机会IMPORT/REFRESH，真实页面来源预览→明确ADOPT201→新HELD占位→显式PROPOSE201→APPROVE200→交付201，随后原API P2 VERIFY。旧批准fresh key提交409；新原POST同key只回原完整回执，运行内无额外作用断言通过。两条LOCAL批准最终CONSUMED，原批准计划版本3、新版本5；旧3条占用与新3条均CONFIRMED，旧关联v1与新v2均保留。P3/P4底层coordination_state仍PENDING、verified_sources/hash为空、从未VERIFY；UI派生状态为PENDING/BLOCKED，差异观察或来源ADOPT不算实际步骤验证。

热历史和冷历史均通过原resource-catalog入口重新识别当前身份后读取；没有强显控件或直接改flag。热计划完整选定字段封存（actor_ref/role/preparation/Case/Run/plan/revision/goals/binding/events/steps），冷新context重新登录后全等。此处只核这些字段及原namedSQL投影（精确preparation计划/LOCAL ledger、links、holds、receipts），不宣称全数据库、全权限或所有派单视图不变。

同一state/config，真正停止首代API2450/PG2442/wrapper2441并确认监听拒绝，再启动API2650/PG2642/wrapper2640；API随机端口58837→41425，不冒称同端口。第二段没有setup/seed/补写业务数据、续deadline或复制localStorage。冷读取2条原键LINK的COMMITTED编号/指纹并保存DOM全文；浏览器阶段配套原delivery GET2次，后续API检查再读2次，共4次、2个唯一原键，与停机前完整回执逐字段相等。停机前两份完整回执和冷读取比较结果在result里，冷API正文未再次复制导出，不伪造第二份原件。两代全部API/PG/wrapper exit0、PG marker消失、监听拒绝、cleanup_errors空，worker0仅一次exit0，未运行worker1。

32POST=25API准备+5DOM+2负例/重复，其中31成功、1预期旧批准409拒绝；126GET/HEAD=97main+29累计readiness，3次fact-clarifications GET403单列不计成功、不绕拒绝。冷阶段业务POST为0。原40POST/400GET、270秒工作/360绝对总时钟、job10分钟、attempt1及清理保留；冷准入41.916秒，工作完成49.117秒，result记录through artifact scan计时49.155秒（不含后续文件/summary最终化，终末step/job仍SUCCESS），未靠缩短原15/30秒等待。

本次wheel独立安装并核191文件，API/PG两代的安装态attestation来自实际site-packages、隔离Python且无PYTHONPATH；实际读取wheel内web.html、setup读取local-resource-approval-schema.sql。wheel构建/安装零依赖下载，bootstrap仍使用原锁定依赖。官方固定Noto与OFL仍只临时私有使用，字体二进制不进8MiB包。静态684码点全覆盖，实际三个命名视口CDP字体检查22/12/6节点；不推广为全码点像素验收。

六张未编辑原图逐张核看。01来源预览、02采纳后、03批准记录为1200px；04消费历史、05冷后展开审计、06冷后v2 LINK为390px。中文可读、长编号/指纹换行、卡片分离，六视口documentWidth等于viewport、导航普通流没有遮挡。04不是全页，05是展开审计的滚动中段而非完整两卡全文，06只视觉展示v2；v1另有DOM原文及严格断言。日期和长ID仍多行；不算整页精修或手机实机验收。

完整官方原job log、官方ZIP全部9成员（含原wheel）、六张PNG、最终result和哈希均保留；未用旧成绩代签。源发布等价tree/SHA与原bundle映射在source-publication.json。本轮只有编号与绑定变化，未重跑原22P/4P/9515项collection；9515只是此前a55实际collection，不能算9515PASS。本目录是该限定合成安装态/真实浏览器门通过，正式来源AT35、Windows/native、真实模型、P1–P5/TXT全链、整计划替换和在途迁移仍未验。main与原授权边界未变。
''')
(dst/'checksums.sha256').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(dst.iterdir()) if p.is_file()))
print(json.dumps(v,ensure_ascii=False))
