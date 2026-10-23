"""Archive one already completed official run; never execute product or browser."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json,shutil,struct
private=Path(__file__).parent;raw=private/'official'
out=Path('/workspace/ParkWeave/docs/demo/evidence/workspace-visual-refinement-20261022/run27');out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text());digest=lambda p:sha256(p.read_bytes()).hexdigest()
run=read(raw/'run-api.json');job=read(raw/'job-api.json')['jobs'][0];a=read(raw/'artifact-metadata.json')['artifacts'][0];r=read(raw/'artifact/result.json')
source='01cb4a18d7396b542995116f41b576b82b39bb34'
assert run['id']==39876408749 and run['run_number']==27 and run['run_attempt']==1 and run['head_sha']==source and run['conclusion']=='success'
assert job['id']==120162978439 and job['conclusion']=='success' and all(s['conclusion']=='success' for s in job['steps'])
assert r['source_sha']==source and r['status']=='PASS' and r['stage']=='COMPLETE' and r['worker_final'] and not r['worker_output_truncated']
assert r['browser_close']=='CLOSED' and r['listener_after_cleanup']=='REFUSED'
assert not any(r[k] for k in ('cleanup_errors','page_errors','violations','unexpected_GET','business_POSTs','real_model_calls','product_API','database'))
assert len(r['requests'])==len(r['browser_requests'])==8 and all(x['method']=='GET' for x in r['requests']+r['browser_requests'])
assert [x['status'] for x in r['requests']].count(403)==1 and len(r['checks'])==14 and len(r['font_observations'])==13
assert all(x['documentWidth']==x['width'] and x['height']<12000 for x in r['checks'])
owned=r['owned_launch'];assert owned['status']=='CLEANUP_CONFIRMED' and owned['operation_status']=='PASS' and owned['worker_returncode']==0
assert owned['bound_processes_exited'] and owned['subtree_complete'] and not any(owned[k] for k in ('errors','signals','remaining_children','remaining_private_session_members'))
assert len(owned['processes'])==7 and all(p['exited'] and p['ownership_basis'] for p in owned['processes'])
assert r['work_and_cleanup_seconds']<=90 and r['seconds']<=360
assert r['installed_CJK_font']['status']=='INSTALLED_CHARSET_COVERS_UI' and r['installed_CJK_font']['rendering_observed']
assert len(r['installed_CJK_font']['required_codepoints'])==684
assert all(x['outside_style_identical'] for x in r['source_binding'].values())
assert len(r['historical_rendering'])==3 and len({x['text_sha256'] for x in r['historical_rendering']})==1
assert a['digest']=='sha256:'+digest(raw/'artifact.zip')=='sha256:07200d0b186550ac4ad1a21efef1e3b9fc93cd88d0b2dcdeb7704329383decc0'
assert digest(raw/'ci-original.log')=='188222cbda4890eb221b3f80b41fee933ba96ccf0aabfc6b7dc3400bf4ed5d0e'
log=(raw/'ci-original.log').read_bytes().decode();assert len(log)==439948
rows=[s.partition('Z ')[2] for s in log.splitlines() if s.partition('Z ')[2].startswith('{"scope": "REAL_CHROME_ORIGINAL_PAGES_PRESENTATION_NO_BACKEND"')];assert len(rows)==1
v=json.loads(rows[0]);assert v['status']=='PENDING_FINALIZATION';v['status']=v.pop('observation_outcome');v.pop('terminal_result')
assert v=={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')}
assert 'Cleaning up orphan processes' in log and 'FINALIZATION_OUTPUT_CHECKPOINT' in log and 'upload aborted' not in log.lower()
with ZipFile(raw/'artifact.zip') as z:
 infos=z.infolist();assert len(infos)==9 and sum(i.file_size for i in infos)<=8*1024*1024
 assert sorted(z.namelist())==sorted(p.name for p in (raw/'artifact').iterdir())
 for i in infos:assert z.read(i)==(raw/'artifact'/i.filename).read_bytes();shutil.copyfile(raw/'artifact'/i.filename,out/i.filename)
public_bytes=sum(i.file_size for i in infos)
for name in ('artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json'):shutil.copyfile(raw/name,out/name)
for name in ('archive_run27.py','source-binding.json','preflight.json'):shutil.copyfile(private/name,out/name)
visual={
 'status':'EIGHT_ORIGINAL_SCREENSHOTS_VIEWED_LIMITED_VISUAL_REVIEW_NOT_WHOLE_PRODUCT_ACCEPTANCE',
 'viewer':'author used actual view_image on all eight original PNGs; no regenerated or edited images',
 'observed_improvements':['02: green header, desktop left navigation and lighter secondary cards form a clearer hierarchy than01','04: nested Case sections use lighter dividers rather than repeated outer cards; identical historical content','06: same green/cream palette and grouped role buttons reduce guide height versus05','07/08: shown Chinese wraps within narrow panels; long Case and step IDs wrap; historical blocked states remain visible'],
 'remaining_quality_gaps':['07: step UUID and adjacent action can share the wrapped second line; controls are visually crowded','04/07: technical required-goal enums and repeated prose make the plan long and dense','08: invalid-session message remains in the regular green status treatment; an error-specific visual state would communicate refusal more clearly','06/08: native file chooser is English in this hosted browser; no claim of complete Chinese browser chrome'],
 'not_covered':['no contentful collaboration/resource/dispatch/receipt page screenshots','goal-result and TXT body not loaded; no business delivery performed','no actual mobile device, screen-reader announcement, forced-colors or every-codepoint visual proof','controlled loading/403 and keyboard focus have runtime observations but no dedicated retained PNG','no new installed-wheel, cold-restart, Windows, formal-source, LIVE or formal AT35 acceptance'],
 'screenshots':[{'name':p.name,'sha256':digest(p),'width':struct.unpack('>I',p.read_bytes()[16:20])[0],'height':struct.unpack('>I',p.read_bytes()[20:24])[0]} for p in sorted(out.glob('*.png'))]}
(out/'visual-review.json').write_text(json.dumps(visual,ensure_ascii=False,indent=2)+'\n')
validation={'status':'LIMITED_HOSTED_BROWSER_PASS_NOT_WHOLE_FRONTEND_COMPLETE','source_sha':source,'run_id':run['id'],'run_number':27,'attempt':1,'job_id':job['id'],'artifact_id':a['id'],'artifact_members':len(infos),'artifact_uncompressed_bytes':public_bytes,'browser':'real normal sandbox Chrome '+r['browser_version'],'server_GETs':8,'browser_GETs':8,'controlled_403':1,'business_POSTs':0,'geometry_observations':14,'glyph_observations':13,'screenshots':8,'static_UI_codepoints':684,'glyph_scope':'actual visible checked nodes only, not every codepoint of every page','historical_fixture':'run23 frozen SYNTHETIC VIEW_REPLAY through original renderer; not current health, authorization or new business recovery','historical_plan_text_sha256':r['historical_rendering'][0]['text_sha256'],'exact_step_IDs_preserved':True,'worker_returncode':0,'bound_pidfds_exited':7,'owned_scope_complete':True,'cleanup_signals':0,'browser_close':'CLOSED','listener_after_cleanup':'REFUSED','cleanup_errors':[],'UI_and_cleanup_seconds':r['work_and_cleanup_seconds'],'publication_scan_seconds':r['seconds'],'stdout':'PENDING_FINALIZATION is not terminal PASS; normalized observation matches result.json','terminal_evidence':'official run/job/step success plus result.json PASS and owned worker returncode0','summary':'body not independently retrieved; no summary-upload failure in full official job log','automatic_retries':0,'old_run26':'FAIL and original Chrome exit/root cause UNKNOWN remain preserved; no action on old PID','visual_review':'all8 original images viewed; improvements and remaining gaps in visual-review.json'}
(out/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
(out/'README.md').write_text('''# run27：原页面视觉切片限定通过

实际受测源码 `01cb4a18d7396b542995116f41b576b82b39bb34`，tree `46bc9b1ef251024e67dbb7da3d184cc385352a89`，[官方 run27/attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39876408749)，job `120162978439`。原正常 sandbox Chrome 真实执行，无业务 API／数据库／模型、0 POST；两侧各8 GET。8张原PNG、result.json、完整API job log和官方ZIP逐字保留。ZIP9成员合计3930322B，符合当次10文件/8MiB上限；本目录另含归档元数据和ZIP副本，不能把归档文件总数当CI上传数。未自动重跑。

原源码的run26门只重绑27，HTML/CSS及业务断言逐字未改；run26失败仍保留，旧Chrome退出与启动根因仍UNKNOWN，本次成功不反推旧根因。监督器记录7个已绑定pidfd退出、worker returncode0、受控子树闭合，未发清理信号；浏览器CLOSED、监听REFUSED、cleanup_errors空。工作与清理17.132秒，扫描发布17.151秒，保留原90/360秒和10分钟job预算。

逐张原图：01/02服务宽屏前后；03/04已归档合成计划面板宽屏前后；05/06演示导览宽屏前后；07当前历史计划面板390px模拟；08当前导览390px无效文件状态。07为362px宽面板截图，浏览器视口390px，不是手机实机。历史计划通过原render函数呈现，只是明示SYNTHETIC VIEW_REPLAY；不当作当前健康、权限、业务办理、核验或恢复成功。三次渲染的文字指纹和5个步骤ID保持一致，P1/P2历史VERIFIED、P3PENDING/P4/P5BLOCKED如实显示。

作者用真实view_image逐张看过8图：新深绿页头/左侧导航、较轻卡片和统一导览有可见改善，展示的中文可读、窄屏换行。仍有窄屏UUID与按钮拥挤、技术枚举与说明密、无效会话沿用绿色status等精致度缺口；原生file chooser在该环境为英文。具体观察和未覆盖范围见visual-review.json，不称整套前端已精美完成。协同/资源仅空态几何与真实glyph观察，未保留有内容关键页图；目标结果/TXT正文、实际办理与完整角色链不在本轮。

14项几何观察、13次可见节点glyph观察不是27个独立测试。固定字体完整静态集合为当前源码的684个码点，实际glyph只覆盖受检可见节点；不称所有页面全部码点视觉通过。focus-visible运行断言3px，非读屏播报实测。stdout仍为PENDING_FINALIZATION，最终以result.json与官方step结局及worker exit联合判断；summary正文未独立读取，完整日志无上传失败。757源码指纹预检与历史collection不算本轮业务回归。本片不含新wheel、冷启、Windows、正式来源、LIVE或正式AT35验收。
''')
(out/'checksums.sha256').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(out.iterdir()) if p.is_file()))
print(json.dumps(validation,ensure_ascii=False,indent=2));print(json.dumps({'archive_files':len(list(out.iterdir())),'archive_bytes':sum(p.stat().st_size for p in out.iterdir()),'checksums_sha256':digest(out/'checksums.sha256')}))
