from pathlib import Path
from hashlib import sha256
from collections import Counter
import json,copy,shutil,zipfile,subprocess
from scripts.local_goal_txt_installed_browser_once import truth,unpack,digest
src=Path(__file__).parent;dst=Path('/workspace/ParkWeave/docs/F2/evidence/goal-txt-combination-20261022/run18');dst.mkdir(exist_ok=False)
r=json.loads((src/'artifact/result.json').read_text());log=(src/'ci-original.log').read_text()
x=json.loads(next(s[s.index('{'):] for s in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage"' in s));x['status']=x.pop('observation_outcome');x.pop('terminal_result');y=copy.deepcopy(r);y.pop('seconds');y.pop('seconds_scope');assert x==y
assert r['status']=='PASS' and r['source_sha']=='76e06a89891dea94fe2c49db29a9ee60ddb754e7' and r['stage']=='INSTALLED_GOALS_TXT_FRESH_CONTEXT_COMPLETE'
job=json.loads((src/'job-api.json').read_text())['jobs'][0];assert job['status']=='completed' and job['conclusion']=='success' and all(s['conclusion']=='success' for s in job['steps'])
assert not r.get('finalization_errors') and not r['violations'] and not r['page_errors']
b=r['request_budget'];assert b['POST']==30 and b['phase_POST']==dict(API_PREPARATION=25,BROWSER=5) and b['GET_HEAD']==119 and b['main_GET_HEAD']==103 and b['readiness_attempts']==16
posts=[v for v in r['responses'] if v['method']=='POST'];assert len(posts)==30 and all(200<=v['status']<300 for v in posts)
assert [v['status'] for v in posts if v['transport']=='BROWSER']==[201,200,201,200,201]
denied=[v for v in r['responses'] if v['status']==403];assert len(denied)==3 and all(v['method']=='GET' and v['path'].endswith('/fact-clarifications') for v in denied)
exports=r['exports'];assert len(exports)==3
for n,entry in enumerate(exports):
 state='UNVERIFIED' if n==0 else 'LOCAL_OUTPUTS_VERIFIED';truth(entry['goal_results'],r['record'],state)
 assert entry['GET_only'] and entry['named_business_projection_equal']
 assert digest(entry['pack'])==entry['pack_sha256']
 if n:
  raw=(src/'artifact'/entry['file']).read_bytes();assert len(raw)==entry['bytes'] and sha256(raw).hexdigest()==entry['text_sha256']
  assert unpack(raw.decode(),entry['goal_results'])==entry['pack']
 assert [s['state'] for s in entry['plan_UI']['steps']]==(['VERIFIED','NEEDS_RECHECK','BLOCKED','BLOCKED'] if n==0 else ['VERIFIED','VERIFIED','PENDING','BLOCKED'])
assert exports[1]['goal_results']==exports[2]['goal_results'] and exports[1]['pack']==exports[2]['pack']
assert exports[1]['plan_UI']==exports[2]['plan_UI']
a=(src/'artifact/current-case-record-pack.txt').read_bytes();assert a==(src/'artifact/fresh-case-record-pack.txt').read_bytes()
assert r['fresh_context']==dict(new_context=True,empty_localStorage_at_login=True,original_LINK_keys=2,full_receipts_equal=True,TXT_bytes_equal=True,full_goal_results_equal=True,business_POSTs=0,PG_restart=False,API_restart=False,setup_repeated=False)
fresh=[v for v in r['responses'] if v['stage'].startswith('FRESH_CONTEXT_')];assert len(fresh)==26 and all(v['method']=='GET' for v in fresh)
assert len(r['fresh_original_reads'])==len(r['receipts_before_fresh_context'])==2
for entry,receipt in zip(r['fresh_original_reads'],r['receipts_before_fresh_context']):
 assert entry['receipt']==receipt and entry['LINK_response']['status']=='COMMITTED' and 'COMMITTED' in entry['DOM_text']
 assert entry['key']==receipt['delivery_binding']['request_key'] and entry['LINK_response']['fingerprint']==receipt['delivery_binding']['fingerprint']
initial=r['initial_business_snapshot']['preparation']['service_case_plan'];assert all(s['coordination_state']=='PENDING' and s['verified_sha256'] is None and s['verified_sources'] is None for s in initial['steps'][2:])
for entry in exports:
 plan=entry['plan_UI'];tail={s['id'] for s in plan['steps'][2:]}
 assert not any(e['action']=='VERIFY' and e['step_id'] in tail for e in plan['events'])
 assert plan['steps'][0]==exports[0]['plan_UI']['steps'][0]
assert len(r['service_generations'])==1;g=r['service_generations'][0]
assert g['wrapper_exit']==0 and g['cleanup']['postgres_marker_absent'] and not g['cleanup']['cleanup_errors'] and g['API_listener_refused_after_stop'] and all(v['exit_code']==0 for v in g['cleanup']['children'])
assert r['setup_stop_status']=='CONFIRMED' and r['installed_worker_exits']==[0]
for role,items in r['process_installation_attestations'].items():
 assert len(items)==2 and items[0]['pid']==items[1]['pid']
 assert all(v['wheel_sha256']==r['installation']['wheel_sha256'] and v['verified_package_files']==191 and v['isolated'] and not v['PYTHONPATH'] for v in items)
assert 'web.html' in r['process_installation_attestations']['api-attestation'][-1]['actual_opened_package_resources']
assert 'local-resource-approval-schema.sql' in r['process_installation_attestations']['setup-attestation'][-1]['actual_opened_package_resources']
wheel=src/'artifact/parkweave-0.1.0-py3-none-any.whl';assert sha256(wheel.read_bytes()).hexdigest()==r['installation']['wheel_sha256']
with zipfile.ZipFile(wheel) as z:
 assert len(r['installation']['package_files'])==191
 for name,expected in r['installation']['package_files'].items():
  data=z.read(name);assert sha256(data).hexdigest()==expected
  assert subprocess.check_output(['git','show',r['source_sha']+':src/'+name],cwd='/workspace/ParkWeave')==data
font=r['installed_CJK_font'];assert len(font['required_codepoints'])==684 and not font['missing_codepoints']
assert [(v['complete'],len(v['nodes'])) for v in r['font_observations']]==[(True,16),(True,16),(True,12)]
assert all(not n['missing_codepoints'] and not n['invalid_sources'] for v in r['font_observations'] for n in v['nodes'])
assert len(r['screenshots'])==4
for shot in r['screenshots']:
 assert sha256((src/'artifact'/shot['file']).read_bytes()).hexdigest()==shot['sha256']
 assert shot['geometry']['width']==shot['geometry']['documentWidth'] and shot['geometry']['navPosition']=='relative'
ziphash='765a19767ee9807578a99071be269ff7a3c58a51d2d0f3312913f27eb4f73318';assert sha256((src/'artifact.zip').read_bytes()).hexdigest()==ziphash
with zipfile.ZipFile(src/'artifact.zip') as z:
 assert len(z.infolist())==9 and sum(v.file_size for v in z.infolist())==2263962
 for name in z.namelist():assert z.read(name)==(src/'artifact'/name).read_bytes()
for name in ['artifact.zip','ci-original.log','job-api.json','run-api.json','artifact-metadata.json','archive_run18.py']:shutil.copyfile(src/name,dst/name)
for path in (src/'artifact').iterdir():
 if path.suffix!='.whl':shutil.copyfile(path,dst/path.name)
shutil.copyfile(src.parent/'publication-map.json',dst/'source-publication.json')
v=dict(scope='LIMITED_INSTALLED_NO_MODEL_TWO_GOALS_FIXED_FOUR_STEPS_TXT_FRESH_CONTEXT',source_sha=r['source_sha'],run_id=39771824938,job_id=119800976040,attempt=1,status='PASS',job_and_business_step='success; nonzero exit would fail step',step_summary_body_independently_read=False,
 raw_job_log_bytes=(dst/'ci-original.log').stat().st_size,raw_job_log_sha256=sha256((dst/'ci-original.log').read_bytes()).hexdigest(),raw_result_normalized_equal=True,
 normalization='stdout PENDING_FINALIZATION restored from observation_outcome; remove terminal_result and artifact-only seconds/seconds_scope; all other fields exact',
 official_zip_sha256=ziphash,official_zip_members=9,official_zip_uncompressed_bytes=2263962,all_original_members_equal=True,wheel_sha256=r['installation']['wheel_sha256'],installed_files_verified=191,wheel_build_install_dependency_downloads=0,
 actual_Pytest_this_CI=0,local_affected_combination_test='1P30.64s separate before publication',collection='9516 cases/404 files at original77771b; collection only, not PASS',
 POST=30,successful_POST=30,API_initial_state_POST=25,browser_POST=5,GET_HEAD=119,main_GET_HEAD=103,readiness_GET=16,denied_GET_403=3,fresh_main_GET=26,fresh_denied_GET_403=1,fresh_business_POST=0,
 current_states_before=['LOCAL_OUTPUT_VERIFIED','NEEDS_RECHECK'],current_states_after=['LOCAL_OUTPUT_VERIFIED']*2,current_required_goals=2,original_adopted_steps=4,
 final_UI_steps=['VERIFIED','VERIFIED','PENDING','BLOCKED'],tail_no_VERIFY=True,Case_completed=False,
 TXT_bytes=len(a),TXT_sha256=sha256(a).hexdigest(),TXT_canonical_sha256=exports[1]['pack_sha256'],TXT_bytes_equal=True,full_goal_results_equal=True,full_literal_export_whitelist_equal=True,
 original_LINK_keys=2,full_original_receipts_exported_twice_and_equal=True,new_context_without_copied_storage=True,PG_restart=False,API_restart=False,setup_repeated=False,
 full_selected_plan_UI_hot_fresh_equal=True,runtime_named_business_projection_equal=True,whole_database_invariance_claimed=False,unverified_TXT_original_public_file=False,unverified_pack_hash_and_bytes_archived=True,
 stage_label_note='CURRENT_UNVERIFIED_GOALS_TXT persists after export returns into reapproval setup (8 later POSTs); whole-stage counting is not export interval evidence. Export function independently asserts its start/end response interval is GET-only. FRESH_CONTEXT stages are wholly read-only.',
 font_static_codepoints=684,font_visible_node_counts=[16,16,12],all_glyph_pixel_acceptance=False,screenshots=4,viewports=[1200,390],full_page_visual_acceptance=False,
 screenshot_scope='01/02 show status and P1 full card plus P2 heading, not full P2 card; 03 shows upper TXT and actual downloaded status; 04 shows only v2 LINK, v1 original body/DOM retained in result.',
 work_completion_seconds=r['work_completion_seconds'],through_artifact_scan_seconds=r['seconds'],API_PG_generations=1,API_pid=g['started']['api_pid'],PG_pid=g['started']['postgres_pid'],wrapper_pid=g['cleanup']['wrapper_pid'],all_owned_exit0=True,cleanup_confirmed=True,
 real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,P1_to_P5_full_chain=False,product_code_changed=False)
(dst/'validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
(dst/'README.md').write_text('''# run18：当前目标结果、TXT 与新会话原键读取

[唯一 attempt1 run18](https://github.com/T1doo/ParkWeave/actions/runs/39771824938)，受测完整 SHA `76e06a89891dea94fe2c49db29a9ee60ddb754e7`，job `119800976040`。最终 result PASS、所有 job steps success，未报 finalization_errors；stdout PENDING_FINALIZATION 只表示待收尾。按 validation 中限定规范化后与最终 result 全字段一致。未独立读取 step summary 正文。

普通独立 wheel 安装，191 个包文件与受测 Git 字节一致；隔离 Python 无 PYTHONPATH，实际打开包内 web.html / setup SQL。NO_MODEL 四步骤、当前仅 P1/P2 两目标的新合成输入，实际来源差异显式 ADOPT 后，第一 TXT 为 UNVERIFIED / P2 NEEDS_RECHECK；随后原页面明确 PROPOSE→APPROVE→交付，新原 API P2 VERIFY。第二 TXT 两目标 LOCAL_OUTPUTS_VERIFIED，四步骤 UI 为 VERIFIED / VERIFIED / PENDING / BLOCKED，尾步无 VERIFY，Case仍未完成。

全部完整 API row / trace 的原指纹先验，再核全部字面白名单导出；不从裁剪的 TXT 子对象重算原行 hash。两个最终真实下载 TXT 各11,485字节、逐字相同，规范化 pack hash 和全文 hash 均在 validation。新 context 重新登录、localStorage 起始空，原 v1/v2 LINK 编号 / 指纹及两完整 delivery receipt 均只读恢复，最终完整 goal-results 和重导 TXT 与热态相等。旧消费历史、占用与来源按原消费验证门保留；不新增 TXT 恢复键、外部批准或期限。

30 POST =25 API 准备 +5真实 DOM，均成功；119 GET/HEAD =103 main +16 readiness，3个 fact-clarifications GET403单列、不计成功、不绕拒绝。新 context 26个main GET、其中1个403，0 POST。第一 UNVERIFIED 导出返回后 stage 名延续至再批准准备，故该标签下后续8POST不能算导出写入或只读区间；导出自身 start/end offset 有 GET-only 断言，fresh 两个标签全区间为 GET。

四张未编辑原图已逐张核看，中文、卡片层次、TXT 按钮和原键结果可读；三张1200px与一张390px均无横溢，导航普通流。01/02仅拍到目标状态、P1整卡与P2标题，P2精确状态由原JSON/DOM断言，不声称图里展示全卡；03是TXT上部，04只视觉展示v2，v1另有DOM / API原件。日期控件含浏览器原生英文，不是手机实机或整页所有字形像素验收。静态684码点覆盖，实际可见字体节点16/16/12，不扩大该范围。

本轮一个 API / PostgreSQL 代和一次 worker；API2440、PG2432、wrapper2430均exit0，PG marker消失、监听拒绝、cleanup_errors空。只换浏览器context，未停启恢复数据库、未第二setup/seed/worker、不转签run17冷重启。工作57.245秒、through artifact scan57.283秒（不含其后最终文件/summary收尾），最终job仍SUCCESS；原270/360秒、10min job、40POST/400GET、10文件/8MiB预算均保留。

官方原 ZIP9成员、四PNG、两最终TXT、完整 result / installation log和官方job全文均保留，wheel仅在ZIP中。未完成态TXT原件未公开，结果保存其pack/指纹/字节与运行内校验，不重造为原下载。构建 / 安装零依赖下载；bootstrap仍用原锁定依赖、同已批准固定Noto/OFL私有字体，无系统安装。原SHA/新SHA等价tree与bundle映射见 source-publication.json。此前本地1P30.64s单列；9516是collection，不是CI测试通过数。

产品源码无改，本片关闭的是 NO_MODEL/LOCAL 再批准组合后的当前目标与TXT消费者门。未支持目标、P5与完整P1–P5履约链未在此执行；正式来源AT35、Windows/native、真实模型、全DB不变与全项目完成均未声称。
''')
(dst/'checksums.sha256').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(dst.iterdir()) if p.is_file()))
print(json.dumps(v,ensure_ascii=False))
