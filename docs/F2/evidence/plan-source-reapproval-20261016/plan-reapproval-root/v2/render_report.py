from pathlib import Path
import json
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--remote-status',required=True,choices=['VERIFIED','AUTH_BLOCKED'])
args=parser.parse_args()
R=Path('.runtime/plan-reapproval-root/v2');A=Path('.runtime/plan-reapproval-oracle/final-v2')
load=lambda p:json.loads(p.read_text())
f=load(R/'freeze.json');v=load(R/'final-regression-verification.json');c=load(A/'coverage.json');h=load(A/'html.json');b=load(A/'browser.json');closure=load(A/'closure.json');review=load(R/'review'/('frozen-'+f['source_sha'][:12])/'review.json')
assert v['status']==review['status']=='PASS' and all(x['source_sha']==f['source_sha'] for x in (v,c,h,b,closure,review))
assert v['modules']==133 and v['unique_passes']==3642 and v['new_passes']==54
text=f'''# 明确来源变更后的原计划再批准与资源交付

基线 `a794a1802e15100d691a969f0813aa371d707c36`；冻结源码 `{f['source_sha']}`；开发分支 `dev/f2-source-plan-reapproval-20261016`。原V1产品§7.4/§8及F2-T03/T05的有限工程增量。root为唯一共享源码与Git写者；候选、独测、独审隔离。实际交付SHA、远端与工作树差异由最后交付回执给出。

已交付的机会 IMPORT/REFRESH/IGNORE/WITHDRAW、来源局部ADOPT和统一依赖传播保持。原Approval只允许首次Case资源交付，本片补齐**已明确批准且已交付的同Case、同稳定计划**：原机会手动刷新真实来源→绑定当前计划与版本并预览→明确采纳原局部修订→选择新HELD资源→原PROPOSE与明确APPROVE→原资源COMMIT、重绑定、CONSUME同一PostgreSQL事务→受影响原VERIFY→六目标及工作清单读取。

仅原已签发自有PG合成fixture可显式开启 `enabled_for_source_reapproval_tests`；原isolated Approval先决条件、owner/角色/capability/租户及Run校验保持。默认关闭；普通工厂/环境不新增开启路径。不是生产Approval、正式治理、新权限或自动批准。旧首次交付和独立重绑定协议保持，原Case历史、六目标、P1–P5及未受影响锁保留。

沿原端点增加可选 `expected_link_revision`，新purpose `CASE_RESOURCE_REAPPROVAL` 仍在原ledger和幂等空间。明确绑定旧link与snapshot、旧交付上下文/批准计划版本、新计划版本、原ADOPT事件及source-change哈希、新资源版本/占用/来源/权限与有效期。原旧资源占用不会被隐式释放。当前审批失效不复活；新方案不能复用旧来源采纳或旧批准。锁定同一parent、复用原资源确认和绑定，失败回滚全部业务效果；历史恢复只读保留已提交事实并按当前来源显示CURRENT或NEEDS_RECHECK。

严格校验原不可变link的实际递增版本、原组合回执与原消费证明。去掉新profile、重算哈希、自引用、两侧Approval引用缺失不能把后续关联变成第二次首次交付。原GET/P2/计划/目标读取使用同一守卫；不是只保护写端。正常受影响VERIFY增加计划revision不会单独使已消费交付失效，后续来源ADOPT或替换仍需重新核对。

页面仅在原隔离范围状态明确开启后显示再批准选项，用户显式选择。新旧模式、Case和资源选择均有generation隔离，ABA不能复活旧响应。提案/批准丢回执后仅原键GET核清原9字段句柄，保留只读历史，不自动切模式或重发；资源提交沿原3字段句柄恢复。机会依赖预览按钮纳入原busy/recovery/corrupt/readonly/plan-busy控制。

## 同一冻结源码的实际验证

{len(f['source_paths'])}个源码/测试/脚本路径、{len(f['all_tracked_sha256'])}个原跟踪路径及4个实际辅助文件在正式窗口前后哈希一致。**最终采纳的133个完整相关模块、3642个唯一pytest项PASS，0FAIL/ERROR/SKIP**；不是全仓。新增4模块54项已在总数内。原107模块整组重跑，新增22个完整旧批准/资源/协调/浏览器模块及4个新模块，无逐节点拼成绩。

|正式窗口|完整模块|PASS|
|---|---:|---:|
'''
for n,row in v['windows'].items():text+=f"|{n}|{row['modules']}|{row['passes']}|\n"
text+=f'''
最终V2原CI元数据12完整模块从调度开始即独占安排，在所有并行pytest结束后一次运行：{v['separate_ci']['counts']['PASS']}PASS、{v['separate_ci']['counts']['SKIP']}原Windows/PowerShell前提SKIP；随后原2秒资源时序所属完整30项独占一次运行。原预算、断言和解锁规则未改。远端CI触发情况由最终推送回执确认，未新增dispatch/workflow。

冻结独审重新运行完整客户端模块{review['pytest_counts']['PASS']}PASS，另{review['pure_protocol_probes']}条独立pure协议探针全部PASS，分开计数，与主集合重叠不相加。10个原协议模块字节、24个关键函数AST和6个schema/scope常量相对基线保持。见[完整回归](evidence/plan-source-reapproval-20261016/plan-reapproval-root/v2/final-regression-verification.json)与[冻结独审](evidence/plan-source-reapproval-20261016/plan-reapproval-root/v2/review/frozen-{f['source_sha'][:12]}/review.json)。

4条完整原HTML由Node机械DOM驱动，经native fetch→真实HTTP/ASGI→自有PostgreSQL，共{h['actual_nativefetch_total']}次页面请求。正向/提交丢回执各实际原源刷新、ADOPT、5个不同步骤VERIFY→六目标/清单；当前403/迟到403有真实拒绝回执。Case/模式/身份/资源选择ABA另由受控Node探针覆盖，不计为原生HTTP或浏览器场景。Node不是浏览器，Python前置控制HTTP总数NOT_RECORDED，不混入页面请求统计。

|Node页面模式|native fetch|POST|实际403|
|---|---:|---:|---:|
'''
for row in h['modes']:text+=f"|{row['mode']}|{row['actual_nativefetch_calls']}|{row['method_counts']['POST']}|{row['actual_403_count']}|\n"
text+='\n真实已安装Chromium四模式如下；请求数包括assets等观测网络请求，不能当作纯API调用数；每模式只有一次PROPOSE、APPROVE和COMMIT，丢回执分别沿原key冷GET恢复，随后P2–P5原VERIFY、六目标与清单。来源变更/ADOPT和P1前置修复用原Python HTTP控制，不宣称由浏览器点击完成。浏览器撤权/403/ABA负向未在本片四模式执行，不能把Node覆盖迁入。\n\n|Chromium模式|实际页面请求|资源COMMIT|\n|---|---:|---:|\n'
for row in b['modes']:text+=f"|{row['mode']}|{row['request_count']}|{row['resource_commits']}|\n"
text+='\n[Node逐请求分层](evidence/plan-source-reapproval-20261016/plan-reapproval-oracle/final-v2/html.json) · [Chromium四模式](evidence/plan-source-reapproval-20261016/plan-reapproval-oracle/final-v2/browser.json)。未拍本片新浏览器截图；旧完整浏览器模块的本地原始截图保留，但二进制不导出。\n\n'
text+='## 独立设计、实际覆盖及失败原件\n\n[32行原设计](PlanReapprovalOracle-20261016.json)始终保持DESIGN_ONLY_NOT_EXECUTED；逐行只按实际冻结身份映射，变体和未执行行明确列出，不把设计行数、分支数、重复记录相加为测试项。\n\n|证据分类|设计行|\n|---|---:|\n'
for name,count in c['counts'].items():text+=f'|{name}|{count}|\n'
text+='\nRA12合法旧link ABA等无对应执行仍NOT_RUN；RA28为原Python服务→自有PG插入故障，不是HTTP；RA29为临时fixture owner故意关闭旧不可变触发器并重写证明后进行读取拒绝，不能声称合法应用动作。跨tenant/owner/角色、五类原能力撤权、source/authority ABA、原键异参及NOT_OBSERVED只读等范围见[实际映射](evidence/plan-source-reapproval-20261016/plan-reapproval-oracle/final-v2/coverage.json)。\n\n'
text+=f"闭环记录分类 `{closure['record_counts']}` 是读取/断言记录，不是唯一业务场景数；六目标仅LOCAL_OUTPUTS_VERIFIED，工作清单仍recorded_states_only=true/evidence_verified=false/case_goal_completed=false。不是现实履约或Case正式完成。\n\n"
text+='''开发失败及修正均保留，不能迁入冻结分母：后端原候选包括ledger revision夹具错误、第三资源组合真实容量冲突（保留旧占用、改夹具时段）、原有效计划拒全替换（先走原请求保存），以及精确错误文本断言。根集成WIP暴露后续关联重哈希降级在P2读取未拒，已补原实际link版本与消费guard并做三类四入口拒绝回归。

独测首窗4PASS/28FAIL主要为artifact record形参kind冲突，原capture插件命名亦与pytest内置冲突，实际成绩和缺收集状态保真；第二完整32窗30PASS/2FAIL：resource-only不应重办仍有效原accept/receipt、expiry直接写无效时间违反PG约束。现保有效证据并原VERIFY，过期经原HOLD最小TTL5秒真实等待，未改schema、clock或预算。第三窗5PASS/1FAIL为Chromium positive响应记录登记晚漏status，业务闭环已过但末尾201计数失败；仅重排采集回调，断言不减，第四完整Chrome4预检通过。首三窗、None状态与各快照均保留，正式另重跑完整54。

首轮冻结 `929d4f7a13c0b074e8340dad21f4460c7ddacd23` 初始134模块/3643项计划完整保留。旧浏览器完整55项53PASS/2FAIL：跨租户身份切换仍等待目录READ的bundleActor非null；模板丢回执测试未填必填name/reason，实际422而非预期200。a794基线两原节点原样0PASS/2FAIL复现。只修两测试前提，保原身份/权限/预算/私有视图与旧opaque handle、原200/原key/body/CAS/六目标及历史一次断言；产品6源相对929逐字不变。旧首轮受控SIGINT，已完成及中断的完整原件均保留，所有成绩不迁入最终新SHA。最终133模块在新SHA全部fresh重跑。

旧附加单测试模块 `test_case_pg_vertical_integration.py` 在929普通pgserver夹具下实际FAIL：line24向不存在的pwci_writer授予USAGE，UndefinedObject；原449PASS/1FAIL/450项完整窗保留，不能改写SKIP/NOT_RUN。7份原协议源相对基线及最终源不变；该模块需专用OwnedPG入口、原完整27项选择和旧单次hosted/branch/approval-only门。最终冻结前明确将这一个完整模块从普通profile计划排除，初始134/3643与最终133/3642集合差仅此模块。未建角色、增权、改审批或绕门；专用27项NOT_RUN，整体工程范围状态为 **LIMITED_PASS_WITH_PROFILE_GAP**。正常profile133/3642通过不代表该专用流程通过。[原profile失败分类](evidence/plan-source-reapproval-20261016/plan-reapproval-root/profile-gap.json)。

V2首次 `related-08` 完整12模块508项为498PASS/10ERROR/0FAIL；10项均在原F2-T07 fixture teardown因原证据目录已有同名文件而触发防覆盖断言，collection/JUnit均508唯一且精确，源码/全跟踪/4helper无漂移。原采集列表漏了该固定目录，前V1 extra-backend写出的10份JSON原件保留，并按原字节另存导出；这些JSON无内嵌sourceSHA，仅以原窗collection、nodeid哈希及mtime归属，不伪造来源标记。重跑前预声明以原支持的 `PARKWEAVE_T07_EVIDENCE_DIR` 指向全新专属目录，只改该进程的证据输出配置，原完整12模块508项一次重跑；不改源码、4冻结helper、防覆盖断言或时间预算，不选节点、不迁原498项成绩。原完整错误窗、context及执行前后证明均归档。为保留原CI/恢复检查首次独占次序，仅停止尚在等待、未启动测试的旧协调器；完整并行窗口及该整窗重跑完成后，原CI12→恢复30各首次独占一次。

最终覆盖分析器首轮使用prepared参数名resource_revision而实际冻结用例参数为resource_capacity，分析失败原脚本和日志保留；修正为实际容量变体映射后成功，未改源码/测试/冻结helper，不将其称为资源revision原样覆盖。GitHub原连接曾出现认证错误，原失败日志保留；最终沿相同default只读检查恢复成功，81旧远端分支及main核验通过，未新增凭据或改传输。

保全辅助脚本首版错误假设本地main存在；实际只有只读origin/main，修正为真实引用，失败诊断/复现日志及旧脚本保留。它不是产品测试失败。此前静态“冷恢复模式死锁”告警已被原恢复函数实证撤回；静态发现和撤回记录同存。

归档仅导出本片原件与各WIP修改源，完整克隆内继承旧档/无关源码、PG/缓存/私有会话集合/截图不重复导出。精确替换已知合成会话值及夹具repr，JSON/XML保持可解析；原件不变，每件有原件和导出路径、字节及SHA。独立终门从原件独立转换并核完整inventory、冻结输入和公开副本；5749份此前原件、639旧档配对、81个旧远端分支及main保持。四份Plan/Log/关键路径历史原字节后缀保全。[主档索引](evidence/plan-source-reapproval-20261016/index.json) · [独立归档终门](evidence/plan-source-reapproval-audit-20261016/gate-v1/final-gate.json)。

## 剩余关键路径

继续按一周目标推进首版；本片完成有限同Case同计划的来源变更→明确再批准→原资源重绑定→受影响VERIFY工程闭环，默认隔离范围外仍不开放。下一关键路径是更多明确来源与在途升级/F5-T04、备份恢复，以及正式治理和真实运行前提；不把复杂迁移放入本片。

Windows/Win11、正式AT、人工语义、真实模型B0–B2、现实履约和生产未执行；仅上述限定Linux本地Chromium场景已执行，不能宣称全面浏览器验收。main与旧分支只读；未强推、部署、新增费用/凭据/安全权限或绕访问拒绝，真实产品模型调用0。
'''
if args.remote_status=='AUTH_BLOCKED':
 text=text.replace('独立终门从原件独立转换并核完整inventory、冻结输入和公开副本；5749份此前原件、639旧档配对、81个旧远端分支及main保持。', '独立本地核验从原件独立转换并核完整inventory、冻结输入和公开副本；5749份此前原件及639旧档配对保持。GitHub原连接实际返回认证拒绝，未新增凭据或绕过。81个旧远端分支及远端main的最终状态未核实；本地origin/main缓存仍为原SHA，不能代替远端验证。')
 text=text.replace('[独立归档终门](evidence/plan-source-reapproval-audit-20261016/gate-v1/final-gate.json)', '[独立本地归档核验](evidence/plan-source-reapproval-audit-20261016/local-integrity.json)。此核验仅LOCAL_INTEGRITY_ONLY，final_gate_pass=false；完整远端终门及正常开发分支推送尚未完成，等待恢复原GitHub连接')
else:
 preservation=load(R/'final-preservation.json')
 assert preservation['status']=='PASS' and preservation['actual_head']==f['source_sha'] and preservation['old_remote_heads']==81
Path('docs/F2/PlanSourceReapproval-20261016.md').write_text(text)
print('docs/F2/PlanSourceReapproval-20261016.md')
