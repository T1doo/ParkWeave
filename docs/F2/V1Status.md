## ENG088 隔离候选规则审核发布（真实流程未启用）

在31944ea上实现默认关闭的独立合成候选合同、专用SQLite、显式提交/独立审核/候选发布/撤回、来源字节与内容版本绑定、当前权限重验及过期评估。生产API、目录只读、部署schema20、角色/Grant/assignment/owner均保持。相关29PASS，实际离线Mock Chromium全流程及1200/390/320通过，独立7图复核无误导；最终211源冻结完整Linux1526PASS/0FAIL/9nativeSKIP/2WARN（315.08秒），源码hash0差异。实际发布权限和新Run审批仍待权威合同及最小权限审查，逐项方案与证据见[ENG088](ENG088-IsolatedRulePublicationCandidate.md)。

不push/CI/merge/deploy，R4关闭/预算0，F1未签收/F2并行、Windows Server与Win11边界保留。下方ENG087是前轮阻塞记录；本轮新增授权仅限代码/隔离测试，不消除正式权限阻塞。

## ENG087 正式规则发布授权前置（BLOCKED）

从5822b029核实正式规则审核发布：当前READ/资料REVIEW_ASSIGNED不包含服务目录审批权，app对preparation_catalog只有SELECT，V1结构校验published=false；不存在可复用发布主体/API或正式授权合同。实际隔离PG/API前置28PASS验证目录UPDATE被拒绝、客户端审核标记/人工资料核对不能产生发布或资格结论，独立复核一致；205源完整拒绝边界/既有功能回归1501PASS/0FAIL/9nativeSKIP/2WARN（310.23秒），产品源码不变。未实现正向规则发布，不把ENG086材料流程或Windows隔离CI当正式发布验收。最小候选流程/权限决策待明项见[ENG087](ENG087-RulePublicationAuthorityGate.md)。

尚缺代码：来源/规则修订存储、提交/审核/发布/撤回API与UI及影响失效。尚缺授权合同：谁可提交/审核/发布/撤回、精确范围与授予/撤销/审计主体；实际扩角色能力、app目录写权或Grant属真实权限变化，本轮不做。已请求提供现成合同或明确仅代码/隔离测试候选流程范围，等待不会产生授权。仅本地测试/文档，不push/CI/owner或持久账户凭据操作；R4关闭/预算0，F1未签收/F2并行与Win11边界保持。

## ENG086 材料准备度与合法Run访问边界（仅本地）

在6b647ac上复用现有受控Rule/Truth合同，保存带材料/服务来源与人工审核快照的三值材料准备度；缺证据未知、明确补正不满足、当前完整人工核对仅表示本地材料条件满足。变化使旧评估STALE/当前未知，历史与刷新恢复；规则工程草稿未业务发布，资格始终未知、Case目标未完成。schema20只新增原资料表metadata，权限身份不变。相关107PASS/闭合15PASS；最终冻结204源完整Linux1497PASS/0FAIL/9nativeSKIP/2WARN（313.88秒），实际双角色三值/修改过期/reload/来源展开/响应时序及独立复核通过；详见[ENG086](ENG086-SourceBoundMaterialReadiness.md)及证据。

新Run仍缺获授权的产品访问准备/批准流程，应用assignment只读；先明确账号事实与单Run审批主体/撤销审计，不将当前P3阻塞归为Windows或外部账号问题。不创建Grant/身份/assignment或修改owner。本轮仅本地、不push/新CI/真实模型，预算0/R4关闭；F1未签收/F2并行、Server/Win11边界保留。下方历史记录保留原范围。

## ENG085 显式诉求与目标持久覆盖（仅本地）

在498d5d2上追加schema19：复用资料表/事件，不增权限身份；原诉求保留，当前诉求、用户主动必需目标及覆盖结果保存/刷新恢复。空目标UNKNOWN、未覆盖PARTIAL、旧模板STALE均可见，新保存路径阻止CREATE/P1；修改使旧预览/核对失效，保留旧业务历史。旧NULL不假造固定目标，原有限直CREATE兼容；私有intent仅owner。最终冻结200源完整Linux1482PASS/0FAIL/9nativeSKIP/2WARN（302.44s），相关130PASS、修复定点92PASS；实际新Case/响应丢失同key/迟到身份/1200/390/320及独立复核通过，授权摘要不变，CaseNEEDS_INPUT/P3访问缺失保持。详情、失败记录、可发布边界及后两缺口安全下一步见[ENG085](ENG085-PersistentRequestCoverage.md)。

合法新Run访问准备流程未具备，保持阻塞、不自动赋权；准备度复用已有ServiceSpec/三值结构合同冻结来源/候选审核发布/oracle，缺发布权限停该步骤。未push/新CI/外网/owner属性变更，R4关闭/模型预算0，F1未签收/F2并行及Windows/Win11旧边界保持。下方历史条目保留原范围。

## ENG084 当前事项方案预览（本地）

从49cc268回看原设计，按价值列三项核心缺口：启用前方案/必需目标覆盖、新Run合法协作访问、审核规则准备度。首项已交付有限固定合成预览：责任/前置/产出/验收/当前输入缺口，unsupported必需目标保留PARTIAL并阻止UI启用；新UI启用绑定当前预览hash/资料版本，旧固定支持目标直建API兼容合同保留。119相关PASS/0FAIL/2WARN，真实新Case页面/worker/PG/1200/390/320与迟到身份验证通过，授权摘要不变；明确启用后CaseNEEDS_INPUT、目标未完成/P3合法Run访问缺失仍阻塞。完整F2/DAG/审核发布模板未完成，不当资格或外部履约；独立审查与证据见[ENG084](ENG084-CasePlanPreview.md)。

下一步优先诉求与显式必需目标的持久覆盖关联；完整冷输入仍受合法访问入口限制，不自动赋权。仅本地、未push/CI/外网/owner操作；F1未签收/F2并行、R4关闭/模型预算0、Windows/Win11与日志边界保持。下方旧记录保留原范围。

## ENG083 精确同步与本地历史模板说明（旧记录保留各轮范围）

指定6提交已审无owner/权限扩大；精确797f426隔离完整Linux1454PASS/0FAIL/9nativeSKIP后，普通快进推送并核实远端同SHA。唯一run37574021406 attempt1 completed/success仅既有独立Job测量，metadata可证步骤success，直接JSON未取得；无日志/产物/rerun，不代表完整Windows/Win11验收。

其后独立本地切片修正历史Case模板启用可用性：企业看见资源关联/分派/回执及当前执行权前置，只允许无历史且有权的事项明确启用；其他角色不见详细原因，历史Case继续既有办理。109相关PASS、两Case三角色真实浏览器/1200/390/320通过，业务/授权/计划数据不变，独立复审无阻塞；该切片未推送，不在上述CI源码中。详情与两类证据见[ENG083](ENG083-SyncAndTemplateEntry.md)。

下一片选全新合成资料Case的明确启用冷入口，只用已有授权、不自动办理/赋权，尚未实施。F1未签收/F2仅并行、R4关闭/预算模型0，owner与被拒日志限制保持，新切片push/CI未执行。

## ENG082 当前本地角色导航（以下旧条目保留原验证范围）

四步计划返回同Case资料已绑定当前角色、计划/资料版本与模板；加载可在同工作区取消，收起/重新进入、身份/Case/工作区切换和迟到回复不恢复旧视图。105相关PASS，两个已有Case三角色真实Chromium/1200/390/320和28受控回复检查通过，独立复审无阻塞；无业务命令或授权变化，既有GET失效观察字段单独记录。源码、实际证据、可同步6提交范围及下一片见[ENG082](ENG082-PlanRoleContinuity.md)。

下一片选择历史已有办理Case的模板启用可用性说明，尚未实现。当前workflow字节未变，后续正常push dev会匹配src/tests过滤并触发独立Job测量，不是完整Windows工程验收；本轮未push/CI或远端查询。F1未签收/F2仅并行，owner/pushCI暂停、R4关闭、模型预算0，Windows/Win11旧边界保持。

## ENG081 当前本地产品增量（以下旧记录保留原范围）

Case页面已把已有四类检查的18个原因解释为具体阻塞、处理角色和现有入口，区分历史关闭与当前依赖；同Case资料入口保持实际企业/专员角色，执行者不见企业详情，真实待补材料/等待确认分别显示。本轮90相关PASS/0FAIL，两个已有Case三角色真实Chromium与1200/390/320验证通过，无业务写请求，业务/授权摘要不变；完整Linux1454仅为ENG080基线。详情、源码与实际证据见[ENG081](ENG081-CaseGuidance.md)。

下一片选择四步计划返回同Case资料的角色连续性，先复现回执→计划→资料入口；尚未修复，不当已验。F1未签收/F2仅并行，owner/push/CI暂停，R4关闭、模型/预算0，Windows/Win11旧缺口不变；本轮没有远端请求。

## ENG080 当前本地核对（以下旧条目为历史快照）

当前源码完整Linux回归 **1454PASS/0FAIL/9原生WindowsSKIP**，299.57秒；首轮三项旧workflow断言失败已修正后全量复验，用例未删/未增skip。实际同Case回执失败恢复、提交后丢响应的相同输入幂等重试、身份切换迟到响应、纠错新版重核/Case显式重验、收起计划返回及1200/390/320视图通过；原资源时段结束先正确阻塞，再经正常UI关联新有效组合v2，规则与授权不变。最终cycle5/本地revision17、回执revision18/v7，Case等待真实确认、目标未完成。

F1未签收/F2仅并行、R4关闭/模型预算0；完整工程Windows仍有ENG071失败与S4缺口，ENG078独立success缺直接JSON，owner保持暂停、完整CI未恢复、Win11未验。无新增GitHub请求/push/run；最后已核实远端381a20a，后续本地提交未推送，不当作实时远端。快速体验命令、前置与实际证据见[ENG080](ENG080-FullLinuxAndQuickExperience.md)；旧新Case/seed/赋权入口属于历史演示，不用于本轮只复用Case的复验。

> ENG075最新可体验增量：同一个保留Case的回执纠错/新版重核后，旧校验失效，必须显式重验才可本地关闭；修正摘要误导并实际浏览器/像素核验通过，无新增授权。见[短体验](ENG075-SameCaseReceiptCorrection.md)。目标仍未完成、F1/F2/Win11/R4边界不变。

> ENG073最新本地产品走查：同Case三角色本地记录闭环与另Case固定四步计划均实际Chromium通过，目标仍未完成，fixture owner赋权前置保留。入口/缺口见[最短体验](ENG073-QuickExperience.md)，当前权限暂停及Windows边界见[ENG073](ENG073-DecisionPackageAndProductWalk.md)。下方历史逐轮范围不作为本轮全量验收。

# F2 与原V1计划的真实对照


## ENG036 固定模板设计收敛（设计与合同验证）

按原V1收敛材料准备→资源组合→已有授权分派/本人接单→合成回执核对四步模板，冻结建议依赖/版本/当前权限/输入变化失效及未来独立oracle，见[短Plan](ENG036-ControlledTemplatePlan.md)。本轮没有实现模板执行器/复合持久计划、注册新动作或赋权；既有合同/单case.create持久修订离线回归29PASS与7项拒绝探针只验证原边界，不称四步或冷会话通过。原AT14预览隔离、AT08/35冷会话和完整F2仍缺；ENG035的808全量保持其原范围，148源hash无变化。下一产品决定是资源与分派先后、合法新Run访问入口、模板审核发布/升级及接受后失配处理。仅本地文档与验证，不push/CI/export/LIVE；R4/Windows/阶段门不变。


## ENG035 当前分派链站内通知（本地完成）

在ENG034明确建议后获新授权，实现当前新分派事件的业务+Outbox同事务、已有收件人平台通知、OPEN请求与本人已读、重复/并发/重启恢复及当前Case权限复查。仅SYNTHETIC内部三角色，内容最小，不新增Grant/Runassignment、无旧历史backfill，无外部消息。最终冻结808PASS/0FAIL/1WindowsSKIP/2既有WARN（232.54s），148源hash/137 runner源hash与8张独立当前截图匹配；三角色实际闭环与16时序检查通过。完成范围与最终证据见[ENG035](ENG035-DispatchNotices.md)。这只补当前分派链的小闭环；通用CaseStep/通知/全业务Outbox、原完整DAG/模板、承诺交付核验及实际FULFILLED仍未完成。F1/F2未签收、R4关闭、Win11/36AT6EX NOT_RUN；0LIVE/预算、不push/newCI/export，Server37420887816仍待已有安全JSON。下方记录保留各轮历史范围。

## ENG034 当前阶段收口审查

逐项能力/原定义差距与最小下一步见[收口审查](ENG034-CloseoutReview.md)。未新增业务功能；修复现有Case资源关联在等待Case锁期间跨过资源结束仍写入的P2，最终时钟现位于锁后。ENG033 775PASS/0FAIL/1WinSKIP保持原提交历史范围；本轮仅该bug修复后冻结回归776PASS/0FAIL/1WinSKIP（225.250s），证据单独登记，不把回归数量作开发目标。唯一下一步建议是当前分派链授权站内通知及同事务Outbox，尚未实现。F1/F2、真实履约和Win11门不解除；Windows37420887816仅等待已有安全JSON，不盲重跑、不重复索图。


## ENG033 当前合成资料Case的本地记录闭环（仅本地）

基线05a8fec，本轮仅本地commit。owner显式重新校验材料/当前接单/核对回执/Case资源依赖后关闭本地记录；真实Case仍WAITING_CONFIRMATION，目标未完成。重开保留历史与资源占用，新cycle必须重新校验；不伪造FULFILLED或真实证据。当前专员/执行者仅最小只读。三角色实际Chromium/API/worker/PG两轮5事件与reload/320/390通过，受控迟到回复23/23通过，142份源码冻结全量775PASS/0FAIL/1WindowsSKIP/2既有WARN（228.266s）见[ENG033](ENG033-LocalCaseLifecycle.md)及[证据](evidence/eng033-local-case-acceptance.json)。没有push/newCI/export/LIVE；原Server37420887816仍FAIL，具体子项等待已有安全JSON。本轮不销掉原完整Case生命周期/真实核验、接受后转派、通用CaseStep/通知/DAG/Outbox/模板/全F2缺口；F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、模型/预算0。下方旧暂停或缺本地闭环描述属于历史记录。


## ENG032 当前最小内部分派与本人接单（本地完成）

基线c5b389b，按原V1 F2-T04与产品§5.5完成最小本地内部业务分派：当前获派资料专员向已有同tenant Run访问权的执行者说明原因分派；本人拒绝、未接单撤回、原因重派及本人接受同事务衔接既有回执，保留版本历史。未新增Grant或Runassignment，不给resource_admin扩权；接受后调整待产品决定，本片暂不支持，原计划目标未改。真实PG/API定向132PASS，136份冻结源全量734PASS/0FAIL/1WindowsSKIP/2既有WARN（205.879s），实际三角色Chromium/PG/API/worker分派6事件→回执3版本/7事件及320/390PASS，受控迟到响应23/23PASS，独立只读审查通过。仅本地commit，不push/newCI/export/LIVE；原Server run37420887816仍FAIL、具体cases/counts等待新安全JSON，本地成绩不称修复Windows。F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。 见[ENG032记录](ENG032-InternalDispatch.md)。下方暂停/未实现分派/旧冻结源等描述均为当轮历史；完整原计划剩余以本轮记录与下表为准。

## ENG031 最新实际Server CI（代码e9e962d历史冻结源）

ENG030代码已普通快进同步，精确远端e9e962d4a5e2b42ea3750c83ee8d7145cc3f24f1；本地冻结129份源码仍匹配681PASS/0FAIL/1WindowsSKIP/2WARN（178.67s）。标准Server [run37420887816](https://github.com/T1doo/ParkWeave/actions/runs/37420887816)已completed/failure：PreparePASS，native_suite677.625秒exit1/外层timeoutFalse，独立安全发布器PASS，受绑定PG StopPASS。获准check title/summary/text仍为空，19条注释未给具体cases/counts，真实子项/报告阶段/根因仍UNKNOWN。发布器exit0结合已验证源码仅证明本次绑定报告SUMMARY_AVAILABLE且stdout/StepSummary写入成功，不能推定report_state=COMPLETED或回归通过。下一最小输入是此run“Windows Server safe engineering diagnostics”安全JSON的report_state/active_phase和FAIL/NOT_RUN行及已有有界计数；不需旧截图或私有日志。未改源码、猜测修复或盲重跑；F2-T04仍暂停于只读合同审查，F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。 见[ENG031记录](ENG031-SyncCI.md)。下方未同步/待截图描述保留为当轮历史，不覆盖本节。

## 历史ENG030本地诊断快照（后续同步见顶部）

最新截图仍仅wrapper错误：实际run37417713362的native_suite623.032秒exit1/外层timeoutFalse，真实case/counts/根因UNKNOWN。源码确认stdout/stderr私有捕获与失败后throw，但native_suite继承GITHUB_STEP_SUMMARY，不能断言子进程未写JobSummary。本地新增Test后Stop前独立always安全报告发布、版本/本次运行绑定、有限阶段检查点，详见[ENG030记录](ENG030-SummaryPublication.md)。仅本地测试/提交，未push或新CI；F2-T04暂停于只读合同审查，分派功能未改。预算0、R4关闭、F1/F2未签收、Win11/36AT6EX NOT_RUN。


## 历史ENG029同步与Server CI结果

ENG028代码已普通快进同步，精确远端ff00b6d8ad0880b24afaca49e33b9f8b982ceb87。标准Server [run37417713362](https://github.com/T1doo/ParkWeave/actions/runs/37417713362)已completed/failure：PreparePASS、native_suite623.032秒exit1/外层timeoutFalse、受绑定PG StopPASS。获准check summary/text为空，19条注释未给具体case/counts；仍UNKNOWN，不把时长推断成内部超时或根因。下一定位仅需此新run页面安全JSON，旧截图请求已过时。见[ENG029真实同步记录](ENG029-SyncCI.md)。下方ENG028“本地未push/待核对”等均为当时快照，现已被本节取代；F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。


## ENG028 本地诊断与UTF-8读取修复（待同步核对）

ENG028增加仅固定test ID、阶段、异常类别和有界统计的诊断；明确UTF-8读取规格、页面、SQL及结果文本。本轮为本地工程修改，尚未push或触发CI，实际Windows码页及原生失败根因仍UNKNOWN。最新已同步代码1baa2cf、docs头aae63a5；标准Server run37414981257仍FAIL，Prepare/受绑定PG停止通过，native_suite79.235秒exit1/no timeout，具体case/counts未知。新样例仅模拟格式，不是该run结果。见[ENG028本地记录](ENG028-SafeDiagnostics.md)。F1未签收/F2正式准入NOT_PASSED，R4关闭、Win11/36AT6EX NOT_RUN，真实模型/预算0。


## ENG027 当前同步授权

普通同步已完成：精确代码push头1baa2cf93f795dbf3036245b8f2ea2ec2ce15e56（含已验证54fad8c）。标准Server CI37414981257终态FAIL：Prepare成功、native_suite79.235秒exit1、owned cluster停止成功；具体case仍UNKNOWN。实际证据见[同步记录](ENG027-SyncCI.md)。旧ENG026未推送/暂停说明属于当时快照，不能当当前状态。未经精确远端验证不声称GitHub已更新，CI结果取得后据实记录；不force/merge main/deploy/LIVE，不重试被拒日志或换身份。F1F2/Win11/R4门槛保持。

当前收敛基线：已同步 `c5b389bf0ae45fd9601182114739a597da13dfa2` 加本地ENG032分派和ENG033本地记录闭环（本轮未push）。原V1《分阶段开发计划》F2-T01—T07及产品§3、5.2—5.5是来源；原文/验收规格未改。下表是实际子集，不是阶段或整项AT签收：F1未签收、F2准入NOT_PASSED、R4关闭，PR0-alpha未完成。

## 当前已能复现的合成链

新的合成诉求→Case/Run/独立worker建单→两槽资料版本/专员补正→企业追加资料→获派专员核对→企业本地确认→本人两资源预检/占位/短事务组合确认→企业明确选择并保存此资料Case的资源关联→资料重开显示需重验且不释放预约→重新人工核对确认后显式关联v2→合法获派执行者合成回执/企业纠错核对重开→reload历史→显式整组取消释放两条容量并保留关联失效原因。ENG025实际三角色UI/PG/API链及320/390记录见[证据](evidence/eng025-acceptance-summary.json)；ENG032补入内部专员分派→本人接受/拒绝→未接单撤回/原因重派→既有回执链，当前成绩见[新证据](evidence/eng032-dispatch-acceptance.json)。

关联已是产品API/UI持久记录，不能继续称为ENG024时的纯测试手动ID关联。但仅当前资料服务Case与本人已确认的两资源组合；已有有限DAG结构校验，但没有一般ServicePlan/DAG运行或业务Approval绑定，跨模块不构成一个总事务。一组合永久归一个Case，换组合保留旧归属/旧占用，取消是显式独立操作。资料REOPEN独立于Case本地记录重开。ENG033对当前合成资料Case新增本地关闭（Case WAITING_CONFIRMATION）与重开（Case REOPENED）；未开始该闭环时Case仍NEEDS_INPUT。资格NOT_EVALUATED、外部NOT_SUBMITTED、线下NO_EVIDENCE不变，原FULFILLED真实证据缺口保留。

执行者Run assignment由测试owner显式准备已有合法访问；ENG032新增当前资料专员的内部业务分派及本人接单，业务入口不创建Runassignment/Grant。只覆盖当前合成资料Case，不是通用办理步骤或完整责任转移。回执仅SYNTHETIC来源，不能证明真实办理或关闭Case目标。角色上限/当前授权交集不变，执行者无企业资料正文或资源操作权。

| 原项 | 已有真实工程成果/提交证据 | 尚未完成的原始项 |
|---|---|---|
| T01 服务入口与企业事实 | 合成建单、有限三字段候选冲突检出/UNKNOWN/必要澄清、资料两槽/来源版本/补正/核对、个人待办；`5173490`、`3aa99e4`、`c285da8`，ENG024修复通用身份/迟到回填。 | 完整锁定约束、跨材料事实冲突核验/裁决、三类来源真实性核验、按用途授权复用。新资料/自述仍可UNKNOWN；真实样例需对应授权。 |
| T02 ServicePlan生成与目标覆盖 | 已有有限DAG/必需目标覆盖/服务版本锁的类型与结构校验，API明确STRUCTURE_ONLY、未执行；无自动资格或外部办理。 | 书生从注册服务编排有限DAG、必需目标覆盖、责任/前置/输出/补正/不支持项及预览闭环，均未完整交付。真实模型/额度和安全门未通过。 |
| T03 资源预检与组合确认 | `da69ea6`预检/占位/期限；`50f7c4b`单资源确认；`c2f3465`两资源同事务确认/整组取消；`2fddcca`增加当前资料Case持久关联/明确重验/失效原因。真实PG故障/并发/撤权/幂等及浏览器证据见[ENG021](evidence/eng021-acceptance-summary.json)、[ENG025](evidence/eng025-acceptance-summary.json)。 | 按声明服务需求的必需组合、Approval/ServicePlan版本绑定、透明替代及完整变更影响。原规格不要求无限数量组合；多Case共享/归属转移需另定业务规则，非默认新增门槛。局部验证不能给全部AT09—11/28—29 PASS；真实资源/外部系统未接入。 |
| T04 角色协同与本地办理 | 企业补件/获派专员核对/确认/资料重开；`8e2195a`有来源/version/hash的获派执行者合成回执、企业核对/纠错/重开；`2fddcca`实际串联资料、Case资源关联及回执；ENG032本地专员分派/本人接受拒绝/未接单撤回/原因重派，接受事务衔接既有回执及必要历史；ENG033补入当前合成Case本地记录关闭/重开及逐轮重验；ENG035当前新分派事件内部站内通知、平台可收取/本人OPEN请求/明确已读及当前Case权限复查。 | 通用CaseStep、接受后责任调整/回执handoff、其余业务通知/完整渠道与模板、原Case完整生命周期与FULFILLED真实证据、真实核验履约。此前Operation receipt不是办理回执。 |
| T05 事件及可靠执行回归 | F1操作账本/租约/fencing/核对/取消/outbox；资料/资源/回执局部事务、幂等/CAS/当前撤权/失败回滚；ENG025不可变关联及归属事务；ENG035分派事件与通知Outbox同事务、消费者投递/确认同事务、重复并发/真实进程崩溃重启及忙Case隔离。 | 所有F2办理/通知与业务Outbox贯通、全流程幂等消费、失联/未知结果/变化核对/陈旧批准回归；局部PASS不等于AT16—20整体完成。 |
| T06 办理模板与新输入 | 新Case/输入及资料/资源/回执合成样例，不复制旧材料/真实身份；多企业隔离回归。 | 审核后参数化服务包模板、完整新企业冷会话/新材料样本、版本发布和全部AT08/35。现有SYNTHETIC fixture不是授权真实样例。 |
| T07 三工作区及端到端验收 | 服务/协同/资源局部真实UI、当前有边界三角色链、桌面/320/390截图；ENG033独立8张当前截图hash匹配；ENG035实际三角色通知闭环及独立8张当前截图，历史登记图审计保留，历史3覆盖/3恢复缺图见[ScreenshotEvidence](ScreenshotEvidence.md)。 | 新诉求→规划→确认→办理→核验→反馈完整原V1链、用户视觉签收、真实设备/Win11和全阶段端到端验收。当前有边界链不等于PR0-alpha。 |

## 实测入口与同步边界

[FirstUse](FirstUse.md)给出当前产品UI步骤；[ENG026同步前收敛说明](ENG026-SyncReadiness.md)列出仓库实际CLI入口、所需本地fixture/合法分配、提交链及检查限制。ENG025冻结源全量584PASS/0FAIL/1WindowsSKIP、95页面时序检查；本轮Windows验收脚本窄修复的独立结果见ENG026，不复用旧数字当新测试。

截至ENG026结束，本地缓存origin/dev/f1-foundation为6ff160a，积累11个本地提交尚未推送；该历史缓存不是实时GitHub状态。ENG027已恢复授权，并正常读取实时远端仍6ff160a，确认快进关系；普通同步精确验证1baa2cf，标准ServerCI37414981257FAIL，具体case待用户，详见同步记录。仍不force/reset丢代码、不备份/导出/上传/LIVE。

旧Windows事实：源码9a8cbc527503ab55978a4b50612207d3bf72de26的CI37324704568 Prepare通过，native_suite78.094秒退出1，失败case/日志未取得。新标准Server CI37414981257已对同步1baa2cf执行并FAIL：Prepare通过、native_suite79.235秒exit1未超时、owned cluster停止通过；case与根因仍UNKNOWN，不能用Linux模拟/AST替代。Server不是Win11。F1/F2未签收、R4关闭、36AT/6EX NOT_RUN；Windows失败明细仍待用户，不能用猜测替代。


## ENG037 固定合成模板当前增量

新增一个工程审查的不可变四步模板/持久计划，绑定当前合成资料事项，owner明确核验当前版本/hash并阻止已有业务入口越序。实际三角色链、撤权观察后恢复显式重验、历史/资源/责任保留见[ENG037](ENG037-ControlledTemplate.md)。T06现有固定模板首片已实现；审核后参数化服务包/版本发布、全新企业无fixture赋权的冷会话及AT35仍未完成。T02通用ServicePlan/DAG执行/原目标核验、完整Approval、统一授权epoch、AT14预览隔离和真实履约仍未交付。
