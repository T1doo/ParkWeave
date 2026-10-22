from pathlib import Path
from hashlib import sha256
import json,shutil,zipfile,copy
src=Path(__file__).parent;dst=Path('/workspace/ParkWeave/docs/F2/evidence/installed-source-restart-run15-failure-20261022');dst.mkdir(exist_ok=False)
r=json.loads((src/'artifact/result.json').read_text());log=(src/'ci-original.log').read_text()
v=json.loads(next(s[s.index('{'):] for s in log.splitlines() if '{"status": "PENDING_FINALIZATION", "stage"' in s));v['status']=v.pop('observation_outcome');v.pop('terminal_result');a=copy.deepcopy(r);a.pop('seconds');a.pop('seconds_scope');assert v==a
assert r['status']=='FAIL' and r['source_sha']=='cceae5be9ba1867443221725801b87cac390f330' and r['stage']=='STALE_APPROVAL_NEGATIVE_API'
assert 'Process completed with exit code 1.' in log and len(r['service_generations'])==1
b=r['request_budget'];assert b['POST']==28 and b['phase_POST']=={'API_PREPARATION':24,'BROWSER':3,'NEGATIVE_AND_REPEAT':1} and b['GET_HEAD']==48
assert not r.get('finalization_errors') and not r['violations'] and not r['page_errors']
f=r['installed_CJK_font'];assert len(f['required_codepoints'])==684 and not f['missing_codepoints']
nodes=r['font_observations'][0]['nodes'];assert len(nodes)==22 and r['font_observations'][0]['complete'];assert all(not x['missing_codepoints'] and not x['invalid_sources'] and x['fonts'] for x in nodes)
g=r['service_generations'][0];assert g['wrapper_exit']==0 and not g['cleanup']['cleanup_errors'] and g['cleanup']['postgres_marker_absent'] and g['API_listener_refused_after_stop'];assert all(c['exit_code']==0 for c in g['cleanup']['children'])
digest='8bcbc6d01ac1d985768fe83c9f67e967b8eb8e97c8ef3610adacd830ee68752c';assert sha256((src/'artifact.zip').read_bytes()).hexdigest()==digest
with zipfile.ZipFile(src/'artifact.zip') as z:
 assert len(z.infolist())==6 and sum(x.file_size for x in z.infolist())<8*1024**2
 for name in z.namelist():assert (src/'artifact'/name).read_bytes()==z.read(name)
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','proposal-red.log','proposal-client.log','proposal-client.xml','archive_failed.py']:
 shutil.copyfile(src/name,dst/name)
for name in ['result.json','01-source-impact.png','02-source-adopted.png','failure-source-restart.png','installation-redacted.log']:shutil.copyfile(src/'artifact'/name,dst/name)
shutil.copyfile(src.parent/'installed-source-restart-run14-20261022/api-publication/publication-final.json',dst/'source-publication.json')
posts=[x for x in r['responses'] if x['method']=='POST' and x['transport']=='BROWSER'];assert [x['status'] for x in posts]==[201,200,409] and posts[-1]['path'].endswith('/plan-approval/proposals')
v=dict(scope='FAILED_RUN15_SOURCE_ADOPT_ONLY_NOT_REAPPROVAL_OR_COLD_PASS',run_id=39760827816,job_id=119764269696,attempt=1,source_sha=r['source_sha'],status='FAIL',recorded_stage=r['stage'],actual_failure='explicit DOM /plan-approval/proposals HTTP409',exit_code=1,raw_job_log_bytes=(dst/'ci-original.log').stat().st_size,raw_job_log_sha256=sha256((dst/'ci-original.log').read_bytes()).hexdigest(),raw_result_normalized_equal=True,normalization='stdout PENDING_FINALIZATION -> observation_outcome FAIL; drop terminal_result annotation and artifact seconds/seconds_scope only; other fields exact',artifact_sha256=digest,artifact_members=6,original_members_exact=True,required_codepoints=684,static_font_missing=[],visible_node_font_observations=22,visible_node_font_checks_pass=True,API_PREPARATION_POST=24,DOM_POST=3,negative_POST=1,GET_HEAD=48,main_GET_HEAD=36,readiness_GET=12,source_ADOPT_UI=True,new_PROPOSE_succeeded=False,new_APPROVE_executed=False,new_delivery_executed=False,cold_restart_executed=False,cleanup_confirmed=True,failed_request_body_saved=False,root_cause='SOURCE_CONTROL_FLOW_INFERENCE_CONFIRMED_BY_CONTROLLED_RED_ORACLE: history reset -> expected_revision0 vs existing local ledger3; failed actual POST body not archived',local_tests='22P current consumer module: original9 + new13 actual PROPOSE handler controlled cases; not browser/HTTP; prior20P is superseded, not added')
(dst/'validation.json').write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
(dst/'README.md').write_text('''# run15原件与再批准页面账本版本修复

[run15](https://github.com/T1doo/ParkWeave/actions/runs/39760827816)，attempt1，源码 `cceae5be9ba1867443221725801b87cac390f330`，job119764269696，FAIL/exit1。依赖、wheel安装、字体门通过；实际来源预览22个可见文字节点均有合法CDP字体来源且缺字为空，静态684码点全覆盖。真实页面明确来源ADOPT201、资源交付预览200；旧批准fresh-key交付409拒绝正确。接下来显式PROPOSE页面POST409，尚无新APPROVE/交付/冷重启。28POST=24API初态+3DOM（含失败提出）+1旧批准负例；48GET/HEAD=36main+12readiness。

原result的stage仍是上一API负例标记`STALE_APPROVAL_NEGATIVE_API`，保留原值不改写。真实失败命令由responses最后DOM POST和failure原图确定。原件没有保存失败请求正文或后端原错误体；expected_revision0与账本3冲突是受测安装web控制流和红例推导，并非冒称观察到了请求正文。已有ledger3，切换再批准清空planApprovalView，而旧处理器默认`?.revision||0`。原`proposal-red.log`实际执行旧页面处理器失败0!==3；后端保持CAS严格拒绝。

修复只在用户明确PROPOSE点击的首次await前封存quote/body/身份/来源/Case/Run。只读取同Case当前ledger，严校验相同身份、Case、Run、scope、0..64安全整数revision与原quote/body未变后，使用该revision发出一次原key的显式提出。GET失败、403、畸形版本、Case/Run/scope/身份或quote变化均不POST；不调用会覆盖quote的历史Render，不续期、不自动重发或批准。APPROVE/REVOKE仍使用用户已读版本与原最终CAS，409照常保留。

本地22P是原9消费者+13个真实处理器的可控Node oracle；覆盖首次0/已有3、跨身份Case/Run/scope、负/超界revision、GET403、两段await中的quote变化/ABA、POST竞态409与原键恢复。不冒充浏览器/HTTP或再批准成功。中间20P不累加。本轮停止新CI，不准备run16；新产品代码尚待未来安装态真实页面及冷恢复实测。

三张原截图已逐张看：1200px来源影响和采纳内容中文可读、导航没有遮挡；失败页准确显示重新预检提示。未执行390px再批准视图，不能把原图当窄屏或整页视觉验收。仅第一代API/PG/wrapper全exit0、PG marker消失、监听拒绝、cleanup_errors空；没有第二代服务。完整专用API job log、官方ZIP全部6成员、三张原图和元数据保留并校验；原wheel在ZIP内。stdout PENDING_FINALIZATION不是PASS，按validation明确规范化后等于FAIL result；step summary正文未单独读取。

正式source、真实模型、Windows/native、P1–P5/TXT全链仍未验。main/权限/费用/凭据边界不变。
''')
(dst/'checksums.sha256').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(dst.iterdir()) if p.is_file()))
print(json.dumps(v,ensure_ascii=False))
