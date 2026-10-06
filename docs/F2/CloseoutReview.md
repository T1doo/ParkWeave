# F2 本地两个增量的有界收尾

## ENG024 当前独立验收收尾

独立reviewer cross_module_review（6.1sol medium）只读8e2195a后公开源码/测试/文档，发现通用UI跨身份残留和迟到回填、验收第二占位旧卡等待竞态与执行者权限措辞，具体复现/修复后只读复核无残留实质问题。未跑API/DB/browser/回归或读私有runtime，运行证据来自实现者。真实页面原generic7失败复现，最终7PASS；已有模块72守卫及真实跨模块三角色/通用事实browser PASS；冻结全聚合555PASS/0FAIL/1WindowsSKIP/2WARN、115源码hash匹配。原API/权限/业务模块/CSS及33保护文件不改。

新流程仍手动关联资源与Case，现有模块局部事务不等于完整ServicePlan或原阶段端到端签收。截图最终41图hash匹配，3旧通用覆盖图与3恢复缺图不可复验，旧运行成绩保留，新图不代旧图。scope/独立审查限制/真实链/未完成项详见[ENG024-CrossModule](ENG024-CrossModule.md)与[证据](evidence/eng024-acceptance-summary.json)。本轮只本地提交，F1F2未签收/R4关闭，Windows失败明细仍待用户；无push/newCI/backup/export/upload/LIVE。

当前复验注记（ENG024）：旧ENG023资料截图目录恢复后缺失，已在原证据追加不可复验标记，详见[ScreenshotEvidence.md](ScreenshotEvidence.md)。原报告运行成绩保留；32张已登记命名图（含旧阶段22张）hash匹配，不能用新图补造旧图。

## ENG023 独立本地收尾

本轮范围为c2f3465之后的获派执行者SYNTHETIC回执切片，并先整理[V1Status.md](V1Status.md)；原文未修改。独立只读6.1sol medium reviewer executor_receipt_review两次检查公开代码/测试/文档、fixture/browser/oracle，无实质finding。未运行任何API/DB/browser/测试，不将实现者555PASS或36新用例当独立复跑。授权先于重放、父锁先于步骤、当前READ/assignment/owner与owner EXECUTE、父绑定/CAS/hash、不可变表历史和本地有限事务均检查；UI token/id/generation、草稿和迟到响应检查。详情见[ENG023范围与结果](ENG023-ExecutorReceipts.md)与[运行证据](evidence/eng023-acceptance-summary.json)。

实现者冻结回归555PASS/0FAIL/1WindowsSKIP/2WARN，111源码hash一致；真实API/worker/PG三角色和旧资料双角色browser、18新/23旧资料/31旧资源页面排序检查PASS。图像已实际查看，用户视觉签收未替代。旧阶段22命名图hash未变，但旧通用固定名f2-*.png首次复跑覆盖且无法恢复其上次字节；唯一目录修复已运行验证，保留此交付限制。无push/新CI/备份/export/upload/LIVE；完整阶段、真实许可/履约/身份/通知、原生Windows和wholeAT门保留，本片提交后停止。

审查范围固定：已发布基线 `6ff160abe979f9d1c28d0e7804fda668daf72cf5` 到本地 `c285da844fcf86f397e052826743e4fe7360a9e8`（ENG015 请求/草稿竞态修复）、`3aa99e45e82517a80a5197d140a92ebce8c92ff2`（ENG016 个人待办）。没有扩大功能、修改原阶段门、推送或重跑Windows CI。本文件收敛既有证据，不产生新测试成绩。

## 独立只读审查

已完成同一工作区独立只读 reviewer `/root/local_f2_review` 的检查（用户指定6.1 sol / medium），范围 `6ff160a..3aa99e4`。它与实现 agent 分开，未修改/复制/导出源码，未安装/访问外网/执行业务API/项目模型动作；没有读取私有会话或DSN。

结论：**未发现所审两增量的实质 correctness/security finding**。reviewer 核对了 web.html:29—43 的token/事项/generation绑定、迟到成功失败守卫、草稿清理与写入case/revision绑定、重复键；preparation.py:159—195的后端当前role/READ/准备授权与tenant/owner/assignment过滤、单语句快照和无材料正文；详情/commands仍独立重新授权。它独立执行Python AST、页面/Oracle JavaScript语法、diffcheck，并确认ENG016记录的六个源码hash匹配，未重跑419项回归或19项新PG/API测试。

reviewer明确的限制：UI race oracle为mock fetch响应排序；实际本地API浏览器只证明所列顺序双角色/双case流程，不证明所有并发排列或完整生产安全，也不认定发生真实资料泄露。该审查不是外部审计、渗透测试、真实用户/生产数据验证，不代替原生Windows或完整AT验收；未因“无finding”把F1/F2改为签收。

## 功能与用例覆盖矩阵（实现 agent 对已有证据的整理）

| 断言/用户功能 | 当前可复核证据 | 未测或边界 |
| --- | --- | --- |
| case/session 请求代次、身份和选中 id 绑定；迟到 GET/写/失败不覆盖新选择 | ENG015原页面合成复现四项缺陷；修复20 checks，ENG016延伸23/23 checks；源hash记录 | 合成响应序列，不是后端授权测试或真实数据泄露证据；未穷举所有网络/事件时序 |
| 跨case材料/来源/人工说明清空；同case刷新/编辑保护；提交case/id/revision | 原竞态复现、A→B→A、编辑中迟到写、id/case/revision guard、失败草稿/幂等重试/导航/New oracle | 已发送事务不会因离开页面撤回；浏览器本地内存会话，未验证多设备真实身份接入 |
| 企业补交/补正/确认、获派专员核对的个人待办 | 新19项PG/API测试、真实本地低权限API/独立worker/PG双case双角色表单链；确认退出、重开返回专员、reload回读 | 仅固定两个合成材料槽；齐全不表示真实性/资格满足；无通用ServicePlan、跨服务办理或资源组合 |
| 待办role/tenant/owner/assignment范围与当前撤权 | 19项中跨企业/园区、同scope未获派专员、resource_admin/service_executor、伪造role/owner query、身份/READ/准备Grant撤销；现有command权限回归 | 同园区同企业第二enterprise owner的待办专属新用例未单独执行；owner_id过滤可静态核对，不能把静态检查计新测试PASS |
| 重复读取无新业务事件、历史与材料按case保留 | 新PG重复GET/Store重建、双case资料/说明隔离、浏览器重复读/确认/reload/reopen；既有不可变历史/CAS回归 | 待办是当前记录的只读视图，没有通知创建/送达/已读账本；没有真实站外消息渠道 |
| 一致快照、规模与阻塞明确 | PG并发提交/20次读取只接受完整已提交状态；单语句读取；101记录的100件上限/更早记录提示；revision64阻塞 | 100个最近未确认有权事项的检查范围，不是全部事项分页或全量待办；64上限用隔离owner fixture，非64步真实用户长程体验 |
| 纯文本与窄屏、失败回到正常读取 | 双角色浏览器中脚本文字不执行、错误身份清空队列、错误确认拒绝、320/390无横滚、页面错误0 | Linux Chromium与模拟viewport；不是真实手机、Safari、Win11桌面或生产渗透结果 |
| 工程回归与保护边界 | c285最终400 PASS/0 FAIL/1 Windows SKIP/2既有WARN；3aa最终419 PASS/0 FAIL/1 Windows SKIP/2既有WARN、23checks、原V1 bytes/hash、24保护文件逐字一致 | 成绩来自不同提交，不相加；checks不加到pytest；Linux/static不能替代Windows、LIVE或整项AT |

证据入口：[ENG015](evidence/eng015-ui-race.json)、[ENG016汇总](evidence/eng016-acceptance-summary.json)、[ENG016真实本地浏览器](evidence/eng016-browser.json)。该审查时点（3aa）源码hash与ENG016冻结源一致。后续ENG018修改共享web/api等源文件，不能把此旧审查继承为资源新片独立审计；独立审查不会改写旧失败或结果。

## 剩余依赖与恢复顺序

| 条件 | 当前已证实/未证实 | 下一步解锁范围 |
| --- | --- | --- |
| 最新Server失败明细（立即所需外部输入） | run37324704568 completed/failure；Prepare/受绑定PG启停PASS；native_suite exit1/78.094s/no timeout；具体FAIL/NOT_RUN子项与原生回归计数缺失 | 只需页面engineering JSON的失败cases及已有exit_code/category/reason，加full_engineering_regression.counts（如有）；据实定位Server命中子项 |
| E1 Win11 x64原生条件与证据 | Server不是Win11；Win11精确环境/权限/生命周期与candidate ACL/reparse/share/race没有验收 | 原Win11 guard不改；只有取得原生证据后，才复核条件性R4 reader/fixture集成；R4集成仍是未完成代码任务，不能包装成纯外部阻塞 |
| E2 真实模型安全配置、额度与授权预算 | 真实请求0、预算0；LIVE关闭；真实provider/跨产品shared配额/速率/usage与错误未证实 | 获明确安全注入/账号及核实总额度/预算授权后，才执行限定真实模型链验收；不把mock或其他项目成功继承为本项目PASS |
| 来源台账与合法合成fixture（F1-T06工程条件） | 已有原文来源manifest/数据台账、显式版本化合成fixture与oracle；真实来源获取未完成 | 可继续对应合成F1/F2工程；原文要求开始获取授权，不要求先拿真实样例才做全部工程 |
| E3 对应真实样例/试点价值许可 | 无真实园区资料/模型发送范围授权与真实用户效果证据 | 停对应真实样例/真实试点主张；获取受控来源/许可/验证者后另验，不把许可缺失笼统作为全部F1或合成F2硬阻塞 |

本地两增量已经保留，等待条件不意味着F1只剩日志、F2全量已完成或所有缺口都是外部因素。F1-T06的台账/合法合成fixture工程条件与对应真实样例的来源许可分开，F2原文允许明确合成测试目录；真实模型、Windows和安全门不降低。完整F2 ServicePlan/资源/模板/执行者与通知等原计划能力仍未实现，属于后续阶段而非本次收尾。C0规则/模板等提交条件独立于本轮工程验证，不新增任务充填等待时间。

收到最新JSON后：首先核对run id/源码9a8cbc5与失败子项，保留缺失字段和真实计数；将子项映射到原native_suite阶段及对应oracle，只修实际证实且在授权范围内的问题，留下复现/修复/本地定向验证。遇到需私有原始日志但现有字段不足的情况，明确说明最小缺项，不重试被拒日志或替代路线。恢复下一次Windows运行前比较原origin分支/历史，保留远端6ff与本地c285/3aa祖先；根据届时授权普通push实质修复与已审查增量并统一安排一次CI，监测到终态，失败如实保留。无新日志/实质修复时不原样重跑，不force/reset/merge main/deploy；Server通过仍不解除Win11/真实模型/安全门或R4条件性集成；对应真实样例仍须来源许可。


## ENG019 前置独立只读审查

用户明确授权同工作区reviewer，以6.1 sol medium检查5849c022..da69ea6资源占位/过期/释放。/root/resource_hold_review结论：未发现实质finding。检查DB锁后时钟、principal→key→resource锁序/3s边界、峰值半开容量/双缓冲、当前授权与回执回放、过期事实、新表最小权限及UI generation/token/resource/draft守卫。仅源码、测试和已有公开合成证据只读；未改文件、运行业务API/模型、访问外网或读私有runtime，465/46成绩是已有证据而非reviewer重跑。

owner登记规则更新/撤权遵循同资源锁/principal排他锁协议；日期picker和Windows仍未验证。新CONFIRM不继承此次独立审查覆盖；其本地测试另记ENG019 Log/evidence。


## ENG020 独立确认增量审查与修复

固定da69ea6..50f7c4b，由/root/confirm_review（6.1 sol medium）只读检查；未跑API/模型、外网或私有runtime。1项P2：原key CONFIRM回放在另一页取消后返回历史回执+当前RELEASED，旧UI按action提示已确认，与卡片矛盾。Chromium合成响应确实复现，eng020-review-repro的该check false；现按当前hold.state反馈，并标明原回执历史，不改后端或回执。后续23/23资源排序检查通过，新增实际PG不同key双确认和锁等待撤权测试补覆盖。

未发现有证据的后端并发/权限/版本/tenant漏洞，不声称完整时序审计。原生picker、Windows/真实设备、park身份迁移等未验证。完整验证与截图目录/hash见ENG020-UIReview、Log及evidence/eng020-acceptance-summary.json。界面可审阅版本不代表用户美观签收、F1/F2阶段通过或R4启用。


## ENG021 两资源事务与隔离独立审查

在3e146a5基线上由/root/combination_review（用户默认6.1sol medium）只读workingtree后端增量：未发现阻断/实质事务或跨企业缺陷。确认全部授权/期限/版本/窗口/容量检查先于写入，两条状态/成员/组/回执同一psycopg事务；principal→共享actor/key→resource UUID排序锁→记录锁，全部资源锁后DB时间。单条和组合回执共用key语义，旧key不重新占用；组成员禁止单条拆分释放。后续资源名称JOIN复核仍绑定本人/park/org和当前READ资源Grant，不引入越权；单条UPDATE返回名丢失的轻微显示问题由主代理补齐并加断言。

reviewer指出取消中途失败/单条confirm竞争/新表权限/精确11→12测试缺口，主代理已补实际PG验证；reviewer未独立跑API或写入测试、未读私有runtime/外网/模型。最后全量发现重复标记迁移重复建表，主代理改新增表IF NOT EXISTS，验证既有组合历史保留并冻结重跑；不把审查无finding当代码已完整通过。验收与失败/修复在ENG021 Log/evidence。

范围仍只有同库SYNTHETIC LOCAL_AUTHORITY的两条不同资源占位；不含任意数量、部分替代、ServicePlan/Approval通用编排、外部预约/履约、真实资源规则、管理员任意SQL并发/park迁移或Windows真实设备。本地成果不签收F1/F2，R4关闭。

## ENG025 Case资源持久关联（本地完成）

基线18f9f567。按原V1 T03/T04将当前合成资料Case与本人确认组合推进为真实产品API/UI持久关联，保留一组合一Case归属/资料版本/资源快照/原因。重开资料需明确重验，换组合不释放旧预约，取消/结束/规则变化明确显示；没有通用Case重开/关闭或真实履约。详见[ENG025-CaseResources](ENG025-CaseResources.md)。

独立6.1sol medium只读审查三项P2均修复，最终无剩余实质缺陷；不把主代理运行当独立复跑。新增29 PG/API PASS，最终真实三角色浏览器与通用事实候选链PASS，95页面时序检查PASS；全量584PASS/0FAIL/1WindowsSKIP/2既有WARN180.06秒，121源码hash冻结一致。保留最初fixture/约束失败与无效的初轮403 oracle预期，不改历史成绩。14张新独立截图，登记共55图hash匹配，3旧覆盖/3缺失继续不可复验。33保护文件、原V1源文与旧roles前缀未改，新表只SELECT/INSERT。

证据[evidence/eng025-acceptance-summary.json](evidence/eng025-acceptance-summary.json)及[截图审计](evidence/eng025-screenshot-audit.json)。并发真实线程未控制交错，无穷举保证；合法执行者assignment仍测试owner建立。F1F2未签收、R4关闭、Win11/36AT6EXNOT_RUN；Windows失败明细待用户。仅本地安全commit，无network/push/newCI/Library/备份/导出/上传/LIVE/provider/真实预算。

## ENG026 收敛、同步前判断与Windows验收弱点（本地完成）

基线2fddccae。起始树干净、git fsck通过；恢复5173490/旧5185cf4/旧CI9a8cbc/缓存6ff160a祖先与到ENG025的10个连续本地提交完整，无reset丢代码；未推送，缓存不是实时GitHub状态。V1Status更新当前有边界持久关联闭环、T01—T07未完成项及真实入口前置，不继续扩产品功能。

独立windows_native_review（用户指定6.1sol medium）只读发现并复核三处验收弱点：Status exit0不验证自有服务身份；清理类别丢失；注入直接写DOM伪证据。仅改Windows CI suite/browser及测试，修正Status安全JSON判定、结构化主/仅清理失败类别、实际SYNTHETIC intake/worker/API/UI渲染oracle；未改应用Windows文件候选/句柄/dispatch/角色/生命周期/ACL/环境白名单/workflow守卫。最终无剩余实质发现，reviewer未运行测试或读私有runtime。

冻结后全量594PASS/0FAIL/1WindowsSKIP/2既有WARN174.96秒，121源码hash一致；Windows相关本地136PASS，13 PowerShell AST/4拒绝守卫/YAML策略及真实Linux渲染链PASS。工具初次.venv无PyYAML与直接pwsh版本探针默认缓存只读失败保留，不当应用或Windows失败；最终使用已有系统解释器与工作区XDG隔离，无安装/改HOME/策略。31保护文件保留，仅2个验收文件明确变化；原V1源文/规格、产品代码与旧截图报告未改。

唯一旧CI事实仍9a8cbc的37324704568 PreparePASS，native_suite78.094秒exit1，失败case/根因UNKNOWN。未重试日志下载/网络或换身份。同步判断、可复现实测入口及证据见[ENG026](ENG026-SyncReadiness.md)和[evidence/eng026-sync-readiness.json](evidence/eng026-sync-readiness.json)。当前push明确暂停且未比较实时远端；Windows验证缺口阻止宣称F1原生通过，原始F2剩余项阻止业务签收，不能混作已知源码同步漏洞。仅本地commit后结束，无push/newCI/备份/导出/上传/LIVE/provider/预算。

## ENG027 普通dev同步与标准Server CI终态

用户解除临时push/newCI暂停。原默认沙箱proxy8080无法连接；同一默认origin/代理/身份经工具正式网络批准后正常只读远端6ff160a，与11个本地积累提交完整快进。扫描无私人附件/运行期文件及凭据模式命中，121冻结源码hash保留；普通push成功并实时验证1baa2cf93f795dbf3036245b8f2ea2ec2ce15e56，含已验证54fad8c和授权说明文档。未force/main merge/付费runner/Secrets/代理身份变更。

新标准CI37414981257精确head1baa2cf已completed/failure；Prepare成功，native_suite79.235秒exit1未超时，owned临时cluster停止成功。允许check摘要/text为空，注释无具体case；case/counts/根因UNKNOWN。未重试被拒日志下载，未根据相近耗时猜旧37324704568根因，未无证据修源码/重复CI。用户信息需求更新为新run Job Summary FAIL/NOT_RUN行（安全case/status/exit/category/counts）。细节见[ENG027](ENG027-SyncCI.md)及[evidence/eng027-sync-ci.json](evidence/eng027-sync-ci.json)。

结果仅追加准确docs并普通同步，源码未变，不声明CI测试了后续docs commit。当前dev成果GitHub可见，CI仍红，F1F2未签收/Win11和whole36AT6EXNOT_RUN/R4关闭；0LIVE/部署/备份/导出/Library/provider/预算。
