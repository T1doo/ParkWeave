# F1 计划

F1-T01/T02/T03/T04/T06 IN_PROGRESS：首个有界增量为严格领域契约、合成身份、持久队列与本地case.create动作；不含预约、任意代码或外部受理。F1-T05 BLOCKED：未获模型安全注入、预算及共享总配额确认。

目标：API 202落库，独立worker领取，事务内本地Case/Receipt/outbox，重复键指纹核对，租约fencing及当前授权重验。Run成功仅表示本地建单，Case保持NEEDS_INPUT。

Windows AT-01/34 BLOCKED；AT其余完整门NOT_RUN，工程子集另记证据，不把局部覆盖计整个AT PASS。本轮结束于首个可测增量，供复核。

初始上限：请求目标2000字符、JSON 16 KiB、计划16步骤、目录100条；仅case.create/1可信动作。文件导入与其他动作仍禁用；真实模型额度为未配置/禁用。

## 首个增量复核状态

增量ENG-001 READY_FOR_REVIEW：21项工程pytest、实际Linux HTTP与Chromium三工作区流程通过，见evidence。阶段F1仍IN_PROGRESS，六任务仅部分实现，完整AT与Windows/模型门未通过；下一轮由父任务复核后派发。本輪不继续F2—F6。

## 第二有界增量ENG-002

READY_FOR_REVIEW：显式FAULT_INJECTION持久账本，独立模拟效果事务，丢响应/无结果查询/失联/旧worker/暂停取消/撤权/跨企业核对；补计划目标与引用边界。全量40工程测试PASS；完整AT仍NOT_RUN，F1整体IN_PROGRESS。

下一独立缺口（非外部阻塞）：V1完整ServiceSpec/Plan及事实冲突；字段级Grant、多角色作用域；正常worker长任务心跳和未知结果账本集成；outbox当前授权/消息撤回与并发回归；逐AT初态和oracle执行器。不要把这些未实现项写成环境BLOCKED。

真正外部阻塞：Windows11 x64实机/安装权限/精确依赖验证；真实书生安全配置、预算及跨产品总配额；真实园区目录/许可/用户流程证据。C0模板/规则/准确截止仍待核实。此次不进入F2业务实现。

## 第三有界增量ENG-003

READY_FOR_REVIEW：正常API/独立worker共用ExecutionGateway，持久DISPATCHED/OUTCOME_UNKNOWN、核对、撤权/控制与旧fence路径；Schema2保留历史；明确测试适配器默认关闭。实际HTTP/worker/PG工程回归和浏览器证据见ENG-003。F1整体IN_PROGRESS，完整AT/EX状态不变。

本轮不补完整V1最小契约/事实冲突/字段级Grant，以避免散开；这些是下一有界增量的独立工程缺口。仍未实现长任务心跳、outbox当前授权/消息撤回完整语义、逐AT全范围执行器。仅未知结果账本的正常worker接入从“未实现”改为“已有合成工程证据”，不声称真实外部连接已验证。

## 第四有界增量ENG-004

READY_FOR_REVIEW：当前闭环所需V1最小完整结构（校验不发布）、带来源事实冲突/缺证据、单企业经办角色字段READ/WRITE Grant、正常worker独立心跳及实际等待/撤权/取消/失联路径。78工程pytest PASS，browser与事实HTTP/worker证据见ENG-004。

配置命名：新增项目优先PARKWEAVE_INTERN_API_TOKEN、通用INTERN_API_TOKEN fallback的只读兼容助手，SecretStr不打印，仅虚构值单测；仓库原来无token读取实现，LIVE仍关闭，安全注入/预算尚未确认。

用户确认电脑Windows11系统家族；精确构建/架构/硬件/原生权限和测试仍BLOCKED，不能把自报系统视为AT-01/34通过。F1整体IN_PROGRESS，未进入F2，完整AT/EX NOT_RUN。

剩余独立F1工作：多角色/获派步骤权限与全部交集及审计、outbox当前授权/消息撤回、文件类型/路径/渲染边界执行器、原生生命周期脚本及固定AT全范围落地；当前仅三字段/一用途事实闭环、模型等待只mock。真实模型/Windows/真实园区资料依赖另列BLOCKED，不掩盖未实现部分。


## 第五有界增量ENG-005

READY_FOR_REVIEW：按执行前ENG005-Mapping冻结F1-T01/T02/T03/T04中AT-03/04/05/16/19工程子集；四角色可信上限/当前能力动作Grant/own或同scope单Run状态指派/执行身份/字段交集；正常worker outbox消费重验、LOCAL_INBOX抑制及撤回；逻辑UUID纯文本合成文件下载与Linux descriptor边界；107 PASS/1 Windows SKIP/2 WARN，浏览器桌面+320/390模拟PASS。Scope不进入F2 CaseStep/办理，不增加外部消息或真实文件导入。

模型0调用/预算0；intern-s2与官方Intern-S2已知同型号大小写兼容只登记后续真实链要求，不放行其他型号。跨平台目标用响应式网页，Windows本地后端主验收保留；Mac本地后端及手机浏览器实机独立验证，手机不承诺运行数据库。本轮仅Linux Chromium模拟，不部署公网。

剩余独立F1工程：Windows Doctor/Setup/Start/Status/Stop/Test脚本及完整固定AT初态/oracle执行绑定；完整生命周期、模型故障/限流/usage仍需对应实现与证据，不能把全量AT状态仅改成外部BLOCKED。CaseStep/正式服务执行权限、真实消息适配器、通用文件产物协议属尚未开放范围，不借本轮扩平台。外部门槛：Park模型安全配置/预算及共享总限流确认（其他项目验证不继承）、Windows11 x64原生机器/安装权限/精确版本、真实园区来源/许可与试点评测、C0模板/跨赛道/准确截止核实。F1仍IN_PROGRESS，完整AT/EX NOT_RUN，本轮交付后停待复核。


## 第六有界增量ENG-006：收尾交接

READY_FOR_REVIEW：六Windows候选生命周期脚本/安全配置/首次体验、42固定AT/EX绑定及独立汇总、正式HTTP模型离线边界；附独立审查目录0777缺口修复和子进程最小环境。完整146 PASS/1 Windows SKIP/2 WARN；Linux PowerShell7.6.6 AST零错误、六guard拒Linux原生流程。Windows实际运行/ACL/filebackend/真实模型仍未通过，完整AT/EX NOT_RUN。

本轮交付即停止新增，不进入F2。准确逐任务实现/独立缺口/外部门槛见Checklist：Windows文件backend仍关闭；真实传输、持久调用usage、共享额度协调和worker真实规划链绑定尚未做，不把它们混为仅外部验收。预算授权0，不因其他项目回包成功探测Park。候选安装不覆盖数据/配置或改既有ACL/全局策略。


## 第七有界增量ENG-007：T05模型链基础

先冻结ENG007-Mapping并按Checklist只补T05，不做Windows backend或F2。HTTP传输代码、账号级共享持久usage/配额、正常worker显式离线两阶段链及持久恢复已实现；最终全量174 PASS/1 Windows SKIP/2既有WARN（82.06秒）。独立的provider account总额保护，产品额度与身份/业务库仍独立，第二产品仅合成模拟，不改Sim2Act。wrong model/secret echo/不完整参数/未知收费/无预算失败关闭；反馈失败不抹去已知Case。

真实安全注入、账户审批、两真实产品同协调点配置、实际HTTP/usage/计费/AT02/30仍BLOCKED，真实调用与授权预算0。Windows安全文件backend单独下一候选；Windows实机/版本/ACL门NOT_RUN。未来窗口滚动/货币账单校准及完整业务oracle另列工作；不把本轮称完整成本系统。交付后停止新增供复核。


## 第八有界增量ENG-008：Windows只读文件候选

READY_FOR_REVIEW：Microsoft官方handle API核对后实现未启用Windows候选（RootDirectory单名称、每级no-follow与对象检查、private protected ACL、同句柄读取/完整性），69 Linux policy/ABI/实参测试；原生Windows专属合成probe，不改既有ACL/策略。最终全量243 PASS/1原生WindowsSKIP/2 WARN，84.97秒；Linux PowerShell AST10项零错误与两个新guard拒绝。这不是Windows通过，产品文件入口继续关闭，注册写入未启用。

F1仍IN_PROGRESS，残余并非全部外部验证：native验证后生产dispatcher/owner注册、安全LIVE注入接入、计划修订artifact/完整before-after oracle与部分F1完整业务oracle仍独立未做。Windows/LIVE0预算/共享真实部署/真实资料/C0门BLOCKED或NOT_RUN，后续金额/窗口及F2+业务不扩建。详见WindowsFileCandidate及Checklist，本轮提交push后停止。


## 第九有界增量ENG-009：F1收敛/R1

按原任务与12个F1首次AT逐断言映射为Convergence有限清单，阶段/标准不改。只实现R1正常worker计划revision1/2、实际回执修订/哈希与调用ID、immutable历史/当前权限读取、原子终态/outbox与恢复独立oracle，真实模型仍0。该投影仅一goal本地case.create，不是F2 ServicePlan。

剩余固定R2（原产品§10默认30RPM具体失败：固定长窗口<60秒允许31发送标记；需最小account发送门/LIVE配置元数据）、R3（三字段候选/集中必要澄清）、R4（native通过后最小通路集成，目前暂停backend）。E1—E3外门另列，F2/F3保持原首次阶段，不把高级计费/通用平台搬入F1。原Windows候选不启用/不改/不操作。交付push后停止，不串行做其余任务。

## 第十有界增量ENG-010：仅R2

账号行锁30RPM发送预约、未决持续占位/完成后60秒冷却、旧代次拒绝、未发退款与有界next_attempt_at恢复；显式LIVE默认关闭/审批前提/变量名存在性只用Fake Mapping。实际provider/预算0，正常CLI仍SYNTHETIC。真实共享两产品同协调点部署未验，独立DB不自动共享。R3/R4未操作，Windows候选不启用，完整AT/EX NOT_RUN；回归/Log/远端核实后本轮停止。

## 第十一有界增量ENG-011：仅R3

正常facts.assess请求/worker接入三字段合成候选projection、明确MockCandidateModel、USER_STATEMENT/DOCUMENT_EVIDENCE/MODEL_CANDIDATE来源及版本，统一UNKNOWN/必要问题、immutable review/hash/append-only澄清子Run。权限/源绑定/冲突缺失/取消/重试/恢复oracle及Linux浏览器证据；真实provider请求/预算0、资格NOT_EVALUATED。R4未操作/仍关闭，Windows实机/LIVE/真实来源外门保持，完整AT/EX NOT_RUN。回归及commitpush后停待复核。

下一轮接续候选（用户优先云端，不依赖用户电脑）：标准免费公共仓库GitHub windows-2025 CI，Python3.12 x64、runner原生PG17 PGBIN fresh cluster、显式PARKWEAVE_TEST_OWNER_DSN及parkweave_app role，全部mock。Windows Server不是Windows11；现有file_candidate_probe的严格release11 guard不绕过，后续独立Server工程harness仍保留生产候选未启用和Win11门。本轮只记录，不创建CI/付费runner、不调整仓库权限/网络或持续凭据；具体CI下一轮独立核实和实施。

## 第十二有界增量ENG012：仅本地Windows云CI准备

LOCAL_ONLY/NEEDS_REVIEW：窄push workflow、标准Server2025/Python3.12x64/原生PG17 fresh loopback PowerShell准备与停止、原有生命周期/实际APIworker/本地浏览器/回归、独立Server文件候选工程harness。当前Actions读取Forbidden，按用户最新指示只做本地Linux/静态验证，不重试/换路线、不推送workflow或启动runner，不改权限。错误原文与缺失HTTP数值状态已记录，Server/Win11实际全NOT_RUN，R4关闭；详见WindowsServerCI.md。

## 第十三有界增量ENG013：有限清理故障与CI凭据边界

仅ENG013-Mapping.md冻结范围：PG start失败/自有state篡改/browser超时，合成command doubles与实际原API/worker启动循环的mock环境捕获；收窄CI辅助命令owner/admin暴露面。不重试Actions/gh、不换身份路线、不读隐藏凭据、不push workflow、不启动runner、不改权限。全部本地commit待复核，WindowsServerCI.md只列恢复授权后一次标准mock job的最小计划；原Win11/R4/LIVE/E1—E3与完整AT/EX门不变。本轮结束不扩新F1产品范围或F2。

最新接续授权：ENG014允许F1未签收时并行开发一个独立F2合成资料准备切片。历史“不扩F2”是此前当轮限制，现由用户新指示替代；F1任务、Convergence R4与E1—E3外门不转PASS。开发不等于F2正式准入或完整AT签收。详见../F2/Plan.md。
