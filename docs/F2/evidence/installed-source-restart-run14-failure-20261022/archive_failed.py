from pathlib import Path
from hashlib import sha256
import json,shutil,zipfile,copy
src=Path(__file__).parent;dst=Path('/workspace/ParkWeave/docs/F2/evidence/installed-source-restart-run14-failure-20261022');dst.mkdir(exist_ok=False)
r=json.loads((src/'artifact/result.json').read_text());log=(src/'ci-original.log').read_text();rows=log.splitlines()
v=json.loads(next(s[s.index('{'):] for s in rows if '{"status": "PENDING_FINALIZATION", "stage"' in s));v['status']=v.pop('observation_outcome');v.pop('terminal_result');a=copy.deepcopy(r);a.pop('seconds');a.pop('seconds_scope');assert v==a
assert r['status']=='FAIL' and r['source_sha']=='abe7b018b8bedf3865969aa6a771f08cb2af9999' and r['stage']=='SOURCE_CHANGE_UI_PREVIEW'
assert 'Process completed with exit code 1.' in log and len(r['service_generations'])==1
assert r['request_budget']['POST']==21 and r['request_budget']['phase_POST']=={'API_PREPARATION':21}
assert not r.get('finalization_errors') and not r['violations'] and not r['page_errors']
f=r['installed_CJK_font'];assert len(f['required_codepoints'])==684 and not f['missing_codepoints']
g=r['service_generations'][0];assert g['wrapper_exit']==0 and not g['cleanup']['cleanup_errors'] and g['cleanup']['postgres_marker_absent'] and g['API_listener_refused_after_stop'];assert all(c['exit_code']==0 for c in g['cleanup']['children'])
assert sha256((src/'artifact.zip').read_bytes()).hexdigest()=='37710464df74eb19eacfbfd564448a418d386af213966dbc07ce43b558214956'
with zipfile.ZipFile(src/'artifact.zip') as z:
 assert len(z.infolist())==5 and sum(x.file_size for x in z.infolist())<8*1024**2
 for name in z.namelist():assert (src/'artifact'/name).read_bytes()==z.read(name)
for name in ['artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json','font-details.log','font-details.xml','archive_failed.py','refresh_manifest.py']:
 shutil.copyfile(src/name,dst/name)
for name in ['result.json','01-source-impact.png','failure-source-restart.png','installation-redacted.log']:
 shutil.copyfile(src/'artifact'/name,dst/name)
assert (dst/'01-source-impact.png').read_bytes()==(dst/'failure-source-restart.png').read_bytes()
validation=dict(scope='FAILED_RUN14_ORIGINALS_NOT_SOURCE_REAPPROVAL_OR_COLD_PASS',run_id=39758724680,job_id=119757241919,attempt=1,source_sha=r['source_sha'],
 status=r['status'],stage=r['stage'],exit_code=1,raw_job_log_bytes=(dst/'ci-original.log').stat().st_size,
 raw_job_log_sha256=sha256((dst/'ci-original.log').read_bytes()).hexdigest(),raw_result_normalized_equal=True,
 normalization='stdout PENDING_FINALIZATION -> observation_outcome FAIL; drop stdout terminal_result annotation and artifact seconds/seconds_scope only; all other fields equal',
 original_artifact_sha256='37710464df74eb19eacfbfd564448a418d386af213966dbc07ce43b558214956',artifact_members=5,original_members_exact=True,
 original_wheel='retained unchanged inside original artifact.zip; no duplicate wheel export',required_codepoints=684,static_font_missing=[],
 visible_observations=18,first_17_missing_empty=True,last_node_selector=r['font_observations'][0]['nodes'][-1]['selector'],
 actual_browser_DOM_POST=0,API_PREPARATION_POST=21,GET_HEAD=47,main_GET_HEAD=28,readiness_GET=19,
 source_change_ADOPT_executed=False,reapproval_executed=False,cold_restart_executed=False,
 cleanup_confirmed=True,independent_source_review='LIMITED_ACK_PAINTED_DETAILS_FIX_RUN15_ONCE; reviewer did not execute CI',
 local_targeted='7P closed/open/nested/second/missing SUMMARY; historical red fixture retained exactly, no historical Git runtime dependency; not real browser')
(dst/'validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False)+'\n')
(dst/'README.md').write_text('''# 安装态来源再批准冷恢复：run14失败原件与最小修复

[run14](https://github.com/T1doo/ParkWeave/actions/runs/39758724680)，attempt1，源码 `abe7b018b8bedf3865969aa6a771f08cb2af9999`。job 119757241919：依赖、安装态初态与来源预览已执行；浏览器字体oracle在第18节点失败，exit1。21次POST全部为API初态、47次GET/HEAD（28主请求+19readiness）；0次DOM POST。尚未执行来源ADOPT、再批准或冷重启，不转签run13。

`ci-original.log`是GitHub专用job log API返回全文，包含320483字符的结果行和exit1。stdout PENDING_FINALIZATION不是PASS；只按validation中明确规则去封装后与FAIL result逐字段一致。未另行读取step summary正文，不能宣称三者正文均已独读。原API元数据、官方ZIP及其完整5成员均保留；ZIP内有原wheel，另导出两张原图、result及安装日志。两个PNG逐字相同，未修图。

原图中来源证明details处于折叠态。静态目标实际684码点且缺失为空，前17可见节点CDP实际字体均通过；第18个closed details隐藏p因Range rect误入检查，无实际glyph。修复仅排除原生details未绘制内容，首个直接summary及其子节点保留，open详情继续原严格CDP/字体来源/字符覆盖检查。7项最小fixture回归包括历史红例、打开、嵌套、第二summary及无summary，不能冒充真实浏览器；不下载新字体、不削减覆盖或改业务预算。

第一代API/PG/wrapper全部exit0、PG marker消失、API监听拒绝，cleanup_errors空。尚无第二代服务。正常流导航首次预览截图无横溢、中文清晰，但再批准密度调整及冷热视图仍待新浏览器实测。待独审后仅安排新run15/attempt1一次修复验证，仍10min job、270s工作/360s绝对总时钟、40POST/400GET、10文件/8MiB、同一已批准官方字体及正常sandbox；失败保全后停止。无真实模型/正式来源/Windows验收。
''')
checks=''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(dst.iterdir()) if p.is_file());(dst/'checksums.sha256').write_text(checks)
print(json.dumps(validation,ensure_ascii=False))
