from pathlib import Path
from hashlib import sha256
import json,copy,shutil,zipfile
src=Path(__file__).parent;dst=Path('/workspace/ParkWeave/docs/F2/evidence/installed-source-restart-run16-20261022');dst.mkdir(exist_ok=False)
r=json.loads((src/'artifact/result.json').read_text());log=(src/'ci-original.log').read_text();v=json.loads(next(s[s.index('{'):] for s in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage"' in s));v['status']=v.pop('observation_outcome');v.pop('terminal_result');a=copy.deepcopy(r);a.pop('seconds');a.pop('seconds_scope');assert v==a
assert r['status']=='FAIL' and r['source_sha']=='08ef7916743d331bbfdb4061d68ac3d180c62171' and r['stage']=='EXACT_NEW_ORIGINAL_POST_REPEAT_API'
assert 'Process completed with exit code 1.' in log and len(r['service_generations'])==1 and 'element is not visible' in r['error']
b=r['request_budget'];assert b['POST']==32 and b['phase_POST']==dict(API_PREPARATION=25,BROWSER=5,NEGATIVE_AND_REPEAT=2) and b['GET_HEAD']==81
posts=[x for x in r['responses'] if x['method']=='POST' and x['transport']=='BROWSER'];assert [x['status'] for x in posts]==[201,200,201,200,201]
assert r['sealed_hot_plan_UI']['steps'][1]['state']=='VERIFIED' and r['sealed_hot_plan_UI']['steps'][2]['state']=='PENDING' and r['sealed_hot_plan_UI']['steps'][3]['state']=='BLOCKED'
assert not r.get('finalization_errors') and not r['violations'] and not r['page_errors']
f=r['installed_CJK_font'];assert len(f['required_codepoints'])==684 and not f['missing_codepoints'];nodes=r['font_observations'][0]['nodes'];assert len(nodes)==22 and r['font_observations'][0]['complete'];assert all(not x['missing_codepoints'] and not x['invalid_sources'] for x in nodes)
g=r['service_generations'][0];assert g['wrapper_exit']==0 and not g['cleanup']['cleanup_errors'] and g['cleanup']['postgres_marker_absent'] and g['API_listener_refused_after_stop'] and all(c['exit_code']==0 for c in g['cleanup']['children'])
digest='a2405def707a96ef83c1da8032667edaf497743c81c78232d1b1a1f21710346c';assert sha256((src/'artifact.zip').read_bytes()).hexdigest()==digest
with zipfile.ZipFile(src/'artifact.zip') as z:
 assert len(z.infolist())==7 and sum(x.file_size for x in z.infolist())<8*1024**2
 for name in z.namelist():assert (src/'artifact'/name).read_bytes()==z.read(name)
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','history-navigation.log','history-navigation.xml','gate-validation.json','archive_run16.py']:shutil.copyfile(src/name,dst/name)
for name in ['result.json','01-source-impact.png','02-source-adopted.png','03-reapproval-approved.png','failure-source-restart.png','installation-redacted.log']:shutil.copyfile(src/'artifact'/name,dst/name)
shutil.copyfile(src/'api-publication/publication-final.json',dst/'source-publication.json')
v=dict(scope='RUN16_INSTALLED_ADOPT_PROPOSE_APPROVE_DELIVERY_SUCCESS_THEN_HISTORY_NAVIGATION_FAILURE_NOT_COLD_PASS',run_id=39764331836,job_id=119775916134,attempt=1,source_sha=r['source_sha'],status='FAIL',exit_code=1,recorded_stage=r['stage'],actual_failure='hidden #plan-approval-read after tab identity reset; selector is source/click-trace inference, not an original error field',raw_job_log_bytes=(dst/'ci-original.log').stat().st_size,raw_job_log_sha256=sha256((dst/'ci-original.log').read_bytes()).hexdigest(),raw_result_normalized_equal=True,normalization='stdout PENDING_FINALIZATION -> observation_outcome FAIL; drop terminal_result annotation and artifact seconds/seconds_scope only',artifact_sha256=digest,artifact_members=7,original_members_exact=True,installation_files=191,offline_wheel_dependency_downloads=0,API_PREPARATION_POST=25,DOM_POST=5,NEGATIVE_AND_REPEAT_POST=2,total_POST=32,successful_POST=31,denied_POST_409=1,GET_HEAD=81,main_GET_HEAD=63,readiness_GET=18,denied_GET_403=2,source_ADOPT_UI_HTTP=201,PROPOSE_UI_HTTP=201,APPROVE_UI_HTTP=200,delivery_UI_HTTP=201,exact_new_original_POST_repeat_assertion_passed=True,repeat_response_body_separately_archived=False,hot_plan_UI_sealed=True,UI_tail_states=['PENDING','BLOCKED'],tail_not_VERIFIED=True,required_codepoints=684,visible_font_nodes_pass=22,viewport=1200,narrow04_executed=False,cold_restart_executed=False,cleanup_confirmed=True,local_new_tests='4P actual Flow plus controlled locator identity-reset model, not browser; old6 not rerun/not added',independent_review='LIMITED_ACK_RUN16_ORIGINALS_AND_HOT_COLD_READ_IDENTITY_REPAIR; no new CI signed')
(dst/'validation.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
(dst/'README.md').write_text('''# run16：安装态再批准交付已执行；历史导航失败，冷恢复未验

[run16](https://github.com/T1doo/ParkWeave/actions/runs/39764331836)，attempt1，源码 `08ef7916743d331bbfdb4061d68ac3d180c62171`，job119775916134，最终 **FAIL/exit1**。源/清单整树等价发布映射见source-publication.json；字体、依赖及正常Chrome sandbox前置通过。当前wheel独立安装191文件，构建/安装阶段0依赖下载；bootstrap仍按既有锁文件，不能称整个job零下载。

实际页面完成原来源ADOPT201、交付preview200、显式PROPOSE201、APPROVE200、交付201；受测产品已包含修复，不再提交默认ledger0。其后API P2 VERIFY200、新交付原key POST重复201且原回执全等/无额外作用的运行内断言通过，再封存完整选定热UI计划字段。归档保存状态码/请求键和热视图，没有另存新增delivery完整响应正文；不冒称已保存或恢复完整新回执。旧P1/旧占用保留的运行内断言已过；UI中P3为PENDING、P4为BLOCKED（派生前置状态），均未VERIFY或开始，并非都显示PENDING。

32POST=25API初态/准备+5DOM+2负例/重复，其中31成功、旧批准fresh key409拒绝1次；81GET/HEAD=63main+18readiness，2次fact-clarifications GET403单列，不计成功、不绕拒绝。没有业务POST越界或pageerror。字体目标实际684码点静态全覆盖，来源预览22个可见节点CDP检查通过；不推广为全683/684字形视觉验收。

随后从服务页切资源页，脚本直接点已隐藏的批准历史按钮，scroll等待约15秒超时。原result阶段仍记上一API重复检查`EXACT_NEW_ORIGINAL_POST_REPEAT_API`，保留原值；具体selector由受测源码、最后可信click轨迹和无history GET推导，不伪造原error字段。原tab handler每次clearResources会清资源身份/批准标记并隐藏面板；遗漏了原目录入口bundleIdentify。第一代API/PG/wrapper全部exit0、marker消失、监听拒绝、cleanup_errors空。04窄屏图、真正停启/新context冷恢复均未发生，不能称冷恢复失败或成功。

已作最小脚本修复：热/冷两处统一原DOM切resource→点击resource-catalog→保留原30秒等待合法身份/批准状态并settled→填精确Case→原history读取→等2条CONSUMED。没有强显控件、直接写flag、改产品或增加业务POST；每处约3额外只读GET，原400累计门、15/30秒等待、270工作/360绝对时钟、冷0POST及cleanup全保留。4项针对性受控Flow/locator检查通过，覆盖热冷身份可用/缺失即停；不是浏览器/HTTP，旧6项未重跑、不累加。修后脚本未启动新CI，不准备run17。

四张原图已逐张查看：1200px来源影响、采纳及批准明细中文清晰，长编号换行、两个审批卡片分开，未见悬浮导航遮挡；失败图体现资源身份刚清空。只支持这些视口，未拍390px再批准图，也不是整页视觉/移动实机验收。完整官方job log、ZIP全部7成员（含wheel）、四张原图及校验保留；stdout PENDING_FINALIZATION不是PASS，按validation规则规范化后与FAIL result一致，含完整错误堆栈和exit1。step summary正文未独立读取。

正式来源、Windows/native、真实模型、P1–P5/TXT全链仍未验；不改main/权限/费用/凭据。既有免费CI本轮只执行run16一次，失败后已停止实际运行。
''')
(dst/'checksums.sha256').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(dst.iterdir()) if p.is_file()))
print(json.dumps(v,ensure_ascii=False))
