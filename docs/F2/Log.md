# F2并行工程日志


## ENG036 固定模板设计收敛（设计与合同验证）

按原V1收敛材料准备→资源组合→已有授权分派/本人接单→合成回执核对四步模板，冻结建议依赖/版本/当前权限/输入变化失效及未来独立oracle，见[短Plan](ENG036-ControlledTemplatePlan.md)。本轮没有实现模板执行器/复合持久计划、注册新动作或赋权；既有合同/单case.create持久修订离线回归29PASS与7项拒绝探针只验证原边界，不称四步或冷会话通过。原AT14预览隔离、AT08/35冷会话和完整F2仍缺；ENG035的808全量保持其原范围，148源hash无变化。下一产品决定是资源与分派先后、合法新Run访问入口、模板审核发布/升级及接受后失配处理。仅本地文档与验证，不push/CI/export/LIVE；R4/Windows/阶段门不变。


## ENG035 当前分派链站内通知（本地完成）

在ENG034明确建议后获新授权，实现当前新分派事件的业务+Outbox同事务、已有收件人平台通知、OPEN请求与本人已读、重复/并发/重启恢复及当前Case权限复查。仅SYNTHETIC内部三角色，内容最小，不新增Grant/Runassignment、无旧历史backfill，无外部消息。最终冻结808PASS/0FAIL/1WindowsSKIP/2既有WARN（232.54s），148源hash/137 runner源hash与8张独立当前截图匹配；三角色实际闭环与16时序检查通过。完成范围与最终证据见[ENG035](ENG035-DispatchNotices.md)。这只补当前分派链的小闭环；通用CaseStep/通知/全业务Outbox、原完整DAG/模板、承诺交付核验及实际FULFILLED仍未完成。F1/F2未签收、R4关闭、Win11/36AT6EX NOT_RUN；0LIVE/预算、不push/newCI/export，Server37420887816仍待已有安全JSON。下方记录保留各轮历史范围。

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


## ENG024 跨模块合成验收与通用UI隔离修复（本地完成）

实际恢复HEAD8e2195ad63dd19d0b7c8e3ef94f47e0c04044a6a/干净工作树与Python3.12.14，未回滚/重下旧ZIP。审计docs全部可解析.runtime PNG/hash引用，旧ENG02017+ENG0215命名图hash保持，ENG023回执10图保持；历史准备browser固定3图覆盖无法恢复，相关旧JSON追加NOT_REPRODUCIBLE，原运行成绩不改。恢复后ENG023 preparation目录3图缺失也追加明确限制，不用新图冒充。ScreenshotEvidence清单和审计script可复核，最终含本片新9图共41HASH_MATCH/3MISSING/3LEGACY_OVERWRITTEN；文字/文件存在不能替代历史hash匹配。

以原V1Status为界，仅现有接口：新企业资料诉求/两槽来源→获派专员纠错→企业材料新版本→专员核对/企业本地确认→两个不同资源预检/占位/组合同事务确认→显式SYN fixture owner为该Run准备现有assignment→合法执行者回执v1→企业纠错→v2→本地核对→重开→v3→reload→显式整组取消两条RELEASED。真实API/独立worker/PG/Chromium三角色PASS；资源保持到明确取消，回执不自动释放或关闭Case，Case仍NEEDS_INPUT。资源/Case仅测试手动关联ID/诉求标签，无ServicePlan/Approval绑定或跨模块全事务。并行与通用分派/接单/通知/真实履约缺口未虚构。

独立6.1sol medium cross_module_review首轮发现通用apiCall没有token/run/generation守卫、切身份残留JSON/运行/诉求/事实草稿，旧review/create迟到可回填新身份；原真实页面mock复现7项全false（预期复现FAIL保留）。最小web UI修复加入冻结context/响应后及caller DOM后二次检查/最新请求与run编辑导航失效、身份清JSON/表单/问题/重试、旧错误不改新状态。API/权限/业务表/桌面手机CSS未改，已经发送的POST仍可能提交的限制明确保留。review另发现第二资源wait可能复用旧卡，script改等待新唯一hold ID，文档“不能读企业决定”改“不能代企业决定”。最终只读复核无残留实质finding；review未跑API/DB/browser/测试或读私有runtime。

修复后冻结最终跨模块browser及通用事实候选补充/评审/取消browser均PASS，取消空run_id保留当前运行，事实UNKNOWN，历史不变；新generic7/7与旧资料23/23/资源31/31/回执18/18共79页面守卫PASS，不增加pytest数量。最终全聚合 **555 passed, 1 skipped, 2 warnings in 166.97s (0:02:46)**，555PASS/0FAIL/1WindowsSKIP，115包含JS源码hash冻结匹配，compileall/JS语法/diffcheck PASS。33原V1/Windows/R4/角色保护文件与roles SQL全字节不变，旧22命名图hash不变。新9图.runtime/eng024-ui-final，已实际查看资源确认/整组取消/企业纠错及320回执；320/390无横滚、页面错误0，不称用户视觉或真手机/Win11签收。

证据evidence/eng024-acceptance-summary.json、eng024-screenshot-audit.json；scope见ENG024-CrossModule。自有harness正常结束仅停自身children，无provider/预算/外部通知或真实身份办理，未push/newCI/backup/export/upload/LIVE。仍缺原计划注册服务DAG/目标覆盖、CaseStep/运营分派接单、通知/全业务Outbox、模板/冷会话/真实证明履约和完整F2端到端。F1F2未签收/R4关闭/Win11及whole36AT6EXNOT_RUN，Windows失败明细待用户，收到优先F1。安全本地提交后本片停止。

## ENG023 获派执行者合成回执完成（仅本地有界切片）

基线c2f3465，先按原V1 F2-T01—T07逐项整理V1Status的一页已完成子集/未完成/依赖，不改原计划。现有执行者仅Run READ，没有办理回执。新增schema13三张业务表和步骤有限状态：只有已LOCAL_CONFIRMED合成资料整理事项的本人企业创建，执行者必须当前合法run_assignments获派；执行者追加SYNTHETIC来源/版本/hash，企业当前hash核对、要求纠正或有理由重开，三版本与历史保留。核心角色上限/先前roles SQL prefix未改，新表只授权特定状态/版本/current receipt列，历史/绑定不可修改；不导入真实材料、身份或通知，不关闭Case。父资料state/revision/hash改变只保留历史并阻止新写，显式重规划仍待实现。

独立6.1sol medium reviewer executor_receipt_review两次同工作区只读，无实质finding，未跑API/DB/browser/测试或读私有runtime。初轮普通沙箱PG64ERROR（Operation not permitted）；正式授权本地测试调用后64相关用例PASS。补充首轮35PASS/1FAIL为owner故障fixture更改父state未清旧hash违反既有CHECK，修正显式fixture；保留失败日志，不计通过。最终冻结全聚合 **555 passed, 1 skipped, 2 warnings in 176.33s (0:02:56)**，555PASS/0FAIL/1WindowsSKIP，新增回执36PG/API均PASS；111个src/test/script含JS hash匹配，compileall/diffcheck通过。当前撤权先于重放、跨role/tenant/未获派、角色不能代另一方、父绑定/CAS/hash、并发同/不同key、失败全回滚、精确12→13和重复标记历史、最小权限/FK均有运行证据。

真实低权限本地API/独立worker/PG/Chromium三角色链PASS：新资料双槽→获派专员人工核对→企业本地确认→测试owner明确分配新SYN Run（非应用分派UI）→企业建步骤→执行者v1→企业纠错→执行者v2→企业本地核对→有理由重开→执行者v3→reload；7事件/3回执，来源/hash/作者可见、Case仍NEEDS_INPUT、外部NOT_SUBMITTED/线下NO_EVIDENCE/资格NOT_EVALUATED。执行者企业决定403、另一企业看不到、身份换清旧材料、脚本文字纯文本、320/390无横滚。新增18/18排序守卫与旧资料23/23、资源/组合31/31PASS；mock-response是页面时序证据，不代替PG授权。旧资料双角色实际UI也PASS，截图路径修改后再验证指定新目录。自有harness全部正常退出，仅停止自身children。

真实持久详情桌面/320/390和全页图已查看，保存.runtime/eng023-ui（10图）及.runtime/eng023-preparation-ui（3图），未导出/上传。旧ENG020/021命名截图22张hash一致。既有固定名.runtime/f2-*.png在首次旧资料复跑被覆盖，上次字节未保全；已如实记录限制并修改browser可选--screenshots/默认唯一目录，不能声称全部历史截图均保留。33个原V1/Windows/R4/角色保护文件逐字不变。详细证据evidence/eng023-acceptance-summary.json，限定范围与R01—R06后记见ENG023-ExecutorReceipts。

本片结束，不展开下片；还缺通用CaseStep/运营分派与接单完整语义、通知送达已读、真实证明/签名/履约、父资料变化后的显式重规划、业务Outbox全链、注册服务DAG目标覆盖、模板/冷会话和完整F2端到端。F1未签收/F2NOT_PASSED/R4DISABLED/Win11及36AT6EXNOT_RUN，Windows37324704568失败明细仍待用户，收到优先F1。provider/预算0，无push/新CI/备份/Library/导出/上传或真实外部办理。安全本地提交后停止本轮。

## ENG021 两资源同事务合成组合确认完成（仅本地有界切片）

基线3e146a5/干净工作树，对照原V1产品§5.4/7.4和F2-T03/AT09—11，在实施前ENG021规格冻结两条本人不同资源占位、不强加相同时间、无替代/优先级/外部业务。schema12新增组/成员/不可变回执；principal→actor请求key→resource UUID排序锁→记录锁，所有锁后一次DB clock_timestamp、当前授权/固定及登记版本/容量/开放重验。全部检查先于写入；两条CONFIRMED+组/成员/回执同事务，取消两条RELEASED+组CANCELLED+取消回执同事务。单成员禁止拆开确认/释放；失败保留原占位，仍依原TTL自然过期。单/组共享actor/key指纹与原回执回放+当前状态，取消后旧CONFIRM不恢复占用。

/root/combination_review（6.1sol medium）workingtree独立只读审查，无实质事务/越权finding；未跑API/模型/外网/私有runtime。提出取消故障/单条确认竞争/新表权限/精确11→12证据缺口后均补；资源名称JOIN再次只读复核未越权，轻微单条UPDATE返回名称缺失已修复并加断言。首轮资源93 PASS/1 FAIL是旧迁移夹具重建新表漏授app权限，修正显式setup后100 PASS；后续首轮全量518 PASS/1 FAIL/1 Windows SKIP为版本标记回放重复建组合表，改IF NOT EXISTS并验证既有组历史保留。失败输出和初轮报告留.runtime，不计PASS，不隐藏回归失败。

冻结最终全量 **519 passed, 1 skipped, 2 warnings in 154.36s (0:02:34)**，519 PASS/0 FAIL/1 Windows SKIP；33新增组合PG/API用例均通过。最终定向101 PASS含100资源用例+原授权迁移回归；双资源第二更新/确认回执及取消第二释放/组state/回执故障均全回滚，倒序同key/不同key双确认、跨企业竞争满容量、单条确认/释放竞争、锁等待后过期、当前任一撤权/跨园区、单/组key冲突、新表不可改历史、11→12及重复标记迁移保留历史均验证。所有聚合source hash与冻结字节一致；24个Windows/R4/角色保护文件逐字不变，roles原prefix字节/hash不变，只追加新业务表最小权限；原V1字节保留。

真正低权限本地API/独立worker/PG/Chromium双企业组合流程PASS：显式两资源占位选取→一起确认→整组取消两边容量恢复、另一企业看不到组/占位ID、TTL5真实过期时未部分确认（原HELD/EXPIRED）、禁用重复click无重复、返回清选择与迟到响应守卫。资源/组合排序31/31 checks与旧资料23/23 PASS，涵盖结果不明可能已确认、同key重试、回放已取消当前状态、失败错误色/不造部分成功；旧资料双角色browser也PASS。自有fixture清理exit0；页面错误0。保持ENG020视觉，组合成功/取消/过期失败桌面/320/390实际截图可视检查，5张最终图片.runtime/eng021-ui-verified，旧ENG020及本片初轮/final截图均保留，ENG020 17张hash相同。证据evidence/eng021-acceptance-summary.json；截图未导出/上传，原生picker/真实设备/Win11未测。

本片到此停止扩展。仅两个同库SYNTHETIC LOCAL_AUTHORITY资源，不含任意数量、部分替代、ServicePlan/Approval通用编排、执行者回执通知或完整模板/新企业端到端；剩余范围见Plan。全部AT/EX原规格仍NOT_RUN，F1未签收/F2NOT_PASSED/R4DISABLED，Windows37324704568失败明细待用户，收到优先F1。真实provider/预算0，无push/新CI/备份/Library导出/上传或真实外部预约。

## ENG020 确认审查修复与前端可审阅版本完成（仅本地）

起始50f7c4b/干净工作树。同工作区独立6.1 sol medium reviewer固定da69..50f7发现1项P2：CONFIRM响应丢失、另一页取消、原key重试时后端历史回执+当前RELEASED正确，但旧UI提示已确认。真实Chromium合成响应先复现22/23 true/1 false（.runtime/eng020-review-repro.json），最小修复按当前hold.state反馈，回执与状态不一致则标历史回执；后端、不可变回执、锁/授权不变。review未独立重跑API，不将已有成绩冒充审查执行；范围与未测见ENG020-UIReview/CloseoutReview。

依据V1三工作区和用户美观要求，小范围纯HTML/CSS优化：绿色/暖白、统一字号间距与卡片/表单、明确当前导航、服务诉求/材料和资源步骤层级、主确认/次取消、当前状态色/空态/全页错误反馈、UTC可读时间。事实候选折叠但真实可展开办理，JSON工程记录默认收起；合成/未真实预约/未受理/未履约标签仍可见。无需框架/字体/CDN/安装。初轮真实截图可视审阅后改善时间，最终17张截图保留.runtime/eng020-ui-final，原初轮目录也保留；证据有各图hash。桌面1200/手机320与390实图检查正常确认、空态/权限错误、服务/协同/资料状态，未用DOM成绩代替美观；用户视觉签收仍PENDING。

实际低权限API/独立worker/PG浏览器：资源双企业预检/占位/确认/取消/TTL5过期、匿名容量、本人记录/reload、disabled重复click无重复、返回导航清旧form、script纯文本 PASS；资料双角色补正/补交/人工核对/确认/重开及事实区块展开/补充仍UNKNOWN/取消历史均PASS，自有fixture清理exit0，页面错误0。最终资源排序23/23、旧资料排序23/23 PASS。实际PG/API67 PASS/2既有WARN，新增不同key双确认仅一次提交和等待身份锁时撤权拒绝，既有版本/期限/tenant/取消竞争/幂等保留。

冻结最终全量 **486 passed, 1 skipped, 2 warnings in 146.07s (0:02:26)**，486 PASS/0 FAIL/1 Windows SKIP，所有测试源hash与冻结文件一致；25个Windows/R4/角色及roles SQL保护文件逐字相同，原V1来源字节未改。证据evidence/eng020-acceptance-summary.json；日志/会话只在.runtime，不公开明文会话或DSN。F1未签收/F2NOT_PASSED/R4DISABLED，Win11/原生picker/真实手机/完整36AT6EXNOT_RUN；Windows37324704568失败明细待用户。无push/新CI/备份/上传/新凭据/真实provider或外部预约，预算0。

## ENG019 单资源本地合成确认完成（本地并行工程，非阶段签收）

基线da69ea6。同工作区独立只读resource_hold_review审查5849..da69占位/过期/释放，未发现实质finding；具体边界见CloseoutReview，本次确认不继承独立审查结论。按实施前ENG019规格新增schema11状态/action约束、Confirm typed API与明确的本地确认/取消按钮，不增加应用数据库权限、不改原输入/TTL。有效HELD才可确认；锁后DB时钟、当前角色/tenant/core及资源Grant、固定/当前版本、开放/容量重验，排除本条占位避免双计数；确认保留区间容量，显式release兼作本地取消，TTL保留历史，状态/不可变回执同事务。

新PG/API首轮与旧资源共63 PASS（17新增+46旧），后补锁等待过期和双owner满容量确认2项，最终全量 484 passed, 1 skipped, 2 warnings in 141.49s (0:02:21)。首轮全量483 PASS/1 FAIL/1 SKIP：健康schema断言修改发生在运行期间，收集的10与DB11冲突；失败项目.runtime保留，不算通过。最终源码冻结重跑，484 PASS/0 FAIL/1 Windows SKIP；全部测试source hash与冻结文件一致。迁移10→11/重复迁移保留占位及原回执，回执写失败确认全回滚；版本/停用/窗口/容量/期限/撤权/跨owner/非法字段/同key指纹/并发确认取消负向已验证。25个Windows/R4/角色/roles SQL保护文件逐字相同，无新授权。

实际Chromium低权限PG/API双企业资源browser PASS：显式确认、历史TTL不变、另一企业匿名容量冲突、本人取消释放；TTL5真实DB过期、反复读取/reload、纯文本、320/390窄屏和页面错误0仍通过。既有双角色资料待办browser PASS；资源排序21/21与旧资料排序23/23 PASS，包括迟到确认草稿守卫和结果不明同key重试。自有fixture进程清理exit0。实际截图可视检查标签可读，非视觉设计签收；后续统一配色/字号/间距/信息层次/各状态/手机设计已入Plan，日期picker手势NOT_RUN。

证据evidence/eng019-acceptance-summary.json；运行日志/会话仅项目.runtime不公开。CONFIRMED只表示本地合成账本，真实预约NOT_CONFIRMED、外部NOT_SUBMITTED、线下NO_EVIDENCE；组合确认未实现。F1未签收、F2NOT_PASSED、R4DISABLED、Win11NOT_RUN、完整36AT6EXNOT_RUN，真实provider/预算0。无push/Actions日志/新CI/备份/上传/新凭据；Windows37324704568具体失败子项仍待用户，收到优先F1。

## ENG018本地纵向切片完成（非F2签收）

在5849基线按实施前规格新增schema10：版本化合成资源/显式READ-HOLD Grant/占位/不可变回执；只新增新业务表权限（登记/Grant只读，占位INSERT和UPDATE state，回执SELECT/INSERT），既有角色上限和旧表Grant字节不变。Store未来版本拒绝门相应改>10，原schema断言9→10/未来11，不删oracle；新SQL纳入package-data。一个合成资源具UTC开放/容量2/前后300秒缓冲，最小REST与资源UI可预检→短期占位→本人状态/释放/过期；无正式/组合确认、后台清理或外部作用。源目录合法合成工程与真实样例许可分类已纠正；原V1两文件字节/hash保持。

后端首轮43 PASS/2 WARN/6.51秒，补跨资源key/身份及资源锁有界冲突后46 PASS/6.82秒；冻结最终46 PASS/0 FAIL/2既有WARN/7.81秒。真实PG覆盖峰值（不误算不相交数量）、半开端点/双缓冲、并发只有2份成功、DB锁等待后时间/无清理过期、同key不重复/不延长、UTC等价指纹、新已确认意图使用新key、撤权前置/同org非owner/跨园区、规则停用/版本变化、输入/TTL约束、回执失败全回滚、应用不可改TTL/原始输入/历史、9→10与重复迁移保留旧资料历史。

实际浏览器首轮及补采均FAIL：preview422后resourcePreview readiness timeout。合成安全诊断证实读取默认日期有效，cached agent-browser fill之后两日期变空（无HOLD写入）；harness改成原生控件赋值+真实input event，而非放宽后端校验。资源响应排序首次FAIL为oracle把CSS选择器当id，修正后17/17 checks PASS；失败留项目.runtime与汇总，不计产品测试PASS。最终真实本地低权限API/独立worker/PG双企业资源browser PASS：预检/显式占位、匿名容量冲突、仅本人记录、主动释放、TTL5实际DB过期且释放容量、重复刷新/reload、脚本文字、320/390无横滚、页面错误0。原生日期选择器手势NOT_RUN。自有harness退出0；既有双角色资料待办browser和23/23排序回归也PASS。

最终冻结全量 **465 PASS/0 FAIL/1 Windows SKIP/2既有WARN，141.70秒**，所有回归源hash与当前文件一致；24个Windows/R4/角色上限保护文件逐字相同。src/roles.sql仅旧内容之后添加新业务表最小权限；未改全局角色权限、安全/网络策略、Win11guard或production R4。新17checks不加入pytest数，旧独立审查仅c285/3aa，不继承给本片。证据在evidence/eng018-acceptance-summary.json、eng018-browser.json；不公开会话/DSN/runtime日志。

本片到此停止扩展；Server37324704568 native_suite具体子项仍UNKNOWN，待用户后优先F1有界定位。F1未签收、F2NOT_PASSED、whole36AT6EXNOT_RUN、R4DISABLED、项目真实provider/预算0；无push/新CI/备份/上传/源代码外发。当前登记支持合成工程；真实资源/价值主张需对应真实来源许可，不把该许可缺失误称全部F1或合成F2硬阻塞。

## ENG018实施前记录：来源分类修正与资源最小纵向范围

基线5849c02。重新读V1：F1-T06要求开始获取来源许可/记录假设，缺许可停对应真实样例而保留显式合成测试；F2允许明确合成目录。更正CloseoutReview矩阵，不再把真实试点许可笼统作为全部F1或合成F2工程硬阻塞；原V1/Windows/真实模型/安全门不降。既有独立review仅c285/3aa，不能继承给资源新片。

用户新授权F2-T03最小资源预检/占位/过期/释放。缺时段容量与占位表，先冻结ENG018-ResourceHolds/Plan。补最小schema10与显式合成登记/最小新表授权；现有角色上限、原身份/授权锁及R4/Win11边界不变，不新增资源管理或真实预订。数据库时钟、短事务、半开/缓冲/峰值容量、当前权限及独立回执；组合确认/正式确认仍未实现。H01—H10初始NOT_RUN，之后真实输出另记。不push/CI/恢复包/上传/源码外发，LIVE/预算0，收到37324704568失败细项先回F1。

## ENG017：两个本地增量的独立只读收尾（文档only）

固定审查6ff160a..3aa99e4，保留c285竞态修复与3aa待办、本地/远端历史，不扩功能。用户明确授权同工作区独立reviewer，按指定6.1 sol / medium由 /root/local_f2_review只读审查case/session响应与草稿、个人待办role/tenant/owner/assignment、重复/跨case导航和未授权材料。结论未发现所审两增量的实质finding；Python AST/JS语法/diffcheck、ENG016六源码hash匹配。reviewer没有改源码、安装、外网、API/项目模型、私有会话、复制/导出/上传或新测试执行。

既有最终成绩保留419 PASS/0 FAIL/1 Windows SKIP/2 WARN、新19 PG/API PASS、23/23合成排序checks与真实本地双角色browser PASS，不冒充本轮重新执行。CloseoutReview.md记录功能/用例矩阵、未测同org第二enterprise owner专属用例、非全时序/非生产审计、100件/64限制和完整F2未实现范围。当前无新实现finding需修复，但正式F1/F2门不转PASS。

立即等待run37324704568失败cases/计数；允许元数据不足以细分native_suite exit1。正式F1另保留E1 Win11原生、E2安全模型配置/核实额度与预算、E3真实来源/许可；R4有条件集成代码仍未完成，不把它伪装成纯外部问题。收到JSON先核对run/source、按命中子项有界定位/修复/本地验证，再依据届时授权比较远端、普通push实质变化并统一一次CI监测到终态；不取被拒日志/无证据重复CI。此收尾只有必要项目内文档提交，未push/merge/deploy/上传/恢复包，项目真实provider请求与预算0。

## ENG016：个人资料准备待办（2026-10-05，本地开发与验证）

用户在Windows失败子项待补期间明确允许独立F2切片；本轮同时明确禁止恢复包/源码外发/Library/第三方/上传。基线 c285da8 正确恢复副本 dev/f1-foundation，先冻结 docs/F2/ENG016-PersonalTasks.md 与 Plan/TestSpecification，再实施V1产品§3/§5.5、F2-T04/T07的最小“本人需补交/确认、获派核对”子集。不处理未证实Windows失败，不扩大到跨服务规划/资源/真实资格或履约；原阶段门保持。

新增只读 /api/preparation-tasks，从同一PG语句快照读取当前state、资料槽存在性、补正理由；复用当前身份、READ/准备Grant、精确owner或reviewer与园区企业交集。无Schema/Grant/后台任务/通知/outbox修改。100件未本地确认事项的检查边界和更早记录提示可见；revision64显示既有写上限阻塞。待办只含必要目标/引用/状态/下一步，不含材料正文。企业缺材料/补正/确认，专员材料齐全后核对；确认从双方待办退出，重开返回专员待办。点击待办读取当前详情再执行原有CAS命令；队列既有revision不替代重新授权。界面复用ENG015代次/身份守卫，迟到待办不会恢复旧身份或覆盖新case草稿。

新增真实PG/API测试首轮 **19 PASS/0 FAIL/2 既有 WARN，3.54秒**：状态链/双case/缺少槽/说明/无材料正文、跨企业园区/未获派与错误角色/伪造角色、撤权、重复读/Store重建、并发提交快照、64上限和101有权记录的100件读取提示。实际Linux Chromium + 自有低权限本地API/独立worker/PG首次浏览器 **PASS**：双case企业与专员的补交→补正→核对→确认→reload→重开、待办打开当前详情、重复读无新历史、错误身份清UI/错误确认拒绝、脚本字面文本、320/390无横滚、页面错误0。自有harness正常停止退出0；不重置既有smoke记录，未读取/输出真实凭据。独立响应顺序浏览器 **23/23 checks PASS**（ENG015原20项保留，增加迟到待办、旧身份待办、范围限制）。各产物留本项目内，最终冻结全量 **419 PASS/0 FAIL/1 Windows SKIP/2 既有 WARN**（125.71s (0:02:05)），全部回归源码hash与当前文件匹配；详情见 evidence/eng016-acceptance-summary.json；不把checks增加到pytest数。

原V1两个原件 bytes/hash与manifest一致；R4/Win11 guard、Windows脚本/workflow、角色SQL、迁移不改。Windows37324704568仍native_suite具体FAIL子项UNKNOWN，F1 IN_PROGRESS未签收、F2正式准入NOT_PASSED、whole36AT6EX NOT_RUN、R4 DISABLED、真实模型与预算0。没有push、CI重跑、恢复包、上传或新外部连接。当前并行切片停止于独立本地结果，不宣称完整F2或真实业务效果。

## ENG015：资料准备 UI 延迟响应与草稿串事项修复（本地，待独立复核）

基线 `6ff160abe979f9d1c28d0e7804fda668daf72cf5`，正确恢复目录与 dev/f1-foundation 分支，不回退初始 work 树。合成 Chromium oracle 只读提供该 commit 原页面并控制 fetch 响应顺序，实际复现同身份 A 迟到 GET 覆盖 B、B draft 发往 A 的 commands（有效 revision 1）、切角色后旧响应恢复事项，以及跨 case 保留材料/来源/说明草稿。原页面还在迟到写响应后清空新编辑。这是合成响应证据，不宣称发生真实数据泄露；它也不替代后端 tenant/角色验收。

修复限于 preparation UI：请求冻结身份 token、代次与选择 id；成功/失败/JSON 完成后均检查是否仍为当前请求，旧错误不能清空新选择。载入保存 case/id/revision 快照，提交前核对；请求发送后导航不会撤销已发出的事务，但响应不再推进别的事项。切 case 清空材料、来源、人工说明，同 case 刷新保留草稿；成功写后仅当草稿未被修改才清空内容/说明。目录、列表、New、导航和 token 变更均使旧链失效，离开后不继续建单轮询或 preparation 创建。保留相同输入失败重试的幂等 key；后端权限、授权锁、CAS 和不可变历史无改动。

首轮 oracle 因 ABA 测试队列选错请求而 CDP evaluate timeout（harness FAIL，非产品计数）；修正队列从末尾选择新请求，保留原失败事实。原页面复现 PASS（即确认四项缺陷）；修复后冻结浏览器响应顺序 **20/20 checks PASS**：延迟 GET/写、身份、A→B→A、跨事项全部草稿、同事项编辑/刷新、409 草稿与幂等重试、提交 case/id/revision、旧目录/列表、导航/New、取消建单链。原有真实本地合成 API/独立 worker/PG 的双角色表单流程也通过，包括补正→补件→核对→确认→reload→重开、历史、失败确认拒绝、纯文本脚本和 320/390 无溢出。自有 fixture harness 正常停止，退出 0。首轮全量 **400 PASS/0 FAIL/1 Windows SKIP/2 既有 WARN**；补齐 case/revision 快照守卫后再对最终源码回归，最终冻结全量同样 **400 PASS/0 FAIL/1 Windows SKIP/2 既有 WARN**（详情见 evidence/eng015-ui-race.json）。没有用浏览器 checks 增加 pytest 数。

复现命令（依赖已批准缓存 agent-browser 0.38.2 和本地 Chromium）：`.venv/bin/python scripts/preparation_race_browser.py --expect-vulnerable --report .runtime/prep-race-before.json`；最终 oracle 去掉 `--expect-vulnerable`；全量 `.venv/bin/python scripts/run_acceptance.py --report .runtime/prep-race-acceptance.json`。原页面使用 git show，当前源码不回退。报告不含 token、DSN 或真实数据。保留既有 ENG014 与迁移失败记录，不触碰被拒日志、不单独 push、不触发 Windows CI。Server native_suite 具体失败仍 UNKNOWN，等待用户失败子项；F1 IN_PROGRESS/未签收，F2 NOT_PASSED，whole36AT6EX NOT_RUN，R4 DISABLED，真实模型调用/预算 0。

## ENG014进行中checkpoint（2026-10-05）

用户明确授权GitHub/Windows阻塞期间继续一个有界用户功能，不改F1准入/F1PASS。原F2前置真实模型/Windows与完整基础门仍未通过，切片对应F2-T01/T04/T05/T07工程子集，完整F2/36AT6EX NOT_RUN，R4关闭。基线1828653，dev/f1-foundation；无AGENTS/.agents新指令，无子agent/Sim修改/隐藏凭据读取/真实模型/预算/付费服务。

实现版本化合成企业资料整理服务，链接真实本地Case/Run，企业追加两个材料槽来源/版本，获派专员补正/人工核对当前hash，企业确认本地资料准备或重开；任何新材料使旧review失效、历史不删。qualification始终NOT_EVALUATED、资料真实性UNVERIFIED、external NOT_SUBMITTED/offline NO_EVIDENCE，原Case NEEDS_INPUT。无外部受理或线下成效。显式PREPARE/REVIEW_ASSIGNED Grant+固定角色/同园区企业/owner或精确assignment交集；应用无DDL/Grant修改或历史UPDATE/DELETE。当前API写与不可变事件同事务，版本/幂等/并发保护；GET短行共享锁防止半快照，保持当前授权锁协议。创建锁原Run避免不同key同Case竞态。Schema9为新增业务表；原schema版本断言升级9，未来版本拒绝测试改10，未删oracle。

Linux定向第一次30 PASS/6.22秒，补并发同Case与审核-补件竞态、Grant范围/不重激活等后34 PASS/4.93秒；原基础21 PASS/2.91秒。当前相关三组81 PASS/1 Windows SKIP/2既有WARN/58.86秒。TestClient+实际PG用例均只SYNTHETIC；浏览器用loopback实际API/独立worker/PG16.2 Python3.12.14，cached agent-browser0.38.2/Chromium，无下载/远端连接。

真实浏览器前两次成功走通创建/资料/双角色补正核对确认/重开/reload/字面脚本text，然后320px横向溢出断言失败。首次给select加border-box和button最大宽度尚未解决，继续定位；**browser完整证据仍FAIL、全量回归未冻结**，不把此checkpoint标READY或PASS。两Library原档完整字节/行/hash和files.py/windows_files.py/Win11probe/workflow逐字不变。

用户新提供另一环境GitHub读取恢复线索；本环境尚未证实。先安全保存本地checkpoint，再在原环境/原代理/原身份各一次Actions原target与远端分支状态复核。没有fetch/push/runner前，不声称网络/权限恢复；若Forbidden停依赖不绕过；成功才fetch/比较history，保留双方工作，不force或主分支合并。最终backup待阶段成果仅更新一次，此checkpoint不上传备份。

## ENG014阶段成果：READY_FOR_REVIEW（非F2签收）

修复后诊断确认320px viewport/scroll406且控件盒本身未越界：资料历史中脚本文本长单词溢出。section overflow-wrap:anywhere使完整文本换行，不以隐藏overflow裁切材料。第三次浏览器全链PASS（320/390均等宽）；追加单事项64事件上限后重启实际API/worker，并对冻结最终源重新验证浏览器PASS。原owned harness parent cwd只读检查遭psutil AccessDenied，未发送信号；用精确原argv/相同uid/已记录API+worker均直属父进程的安全交叉校验，再向自己的harness SIGTERM；它退出0/停止自身children，不发现或广泛杀进程，不改策略。

最终新增35项pytest PASS/5.26秒（真实PG/TestClient，包括事务失败rollback、历史权限、版本/并发/撤权）；冻结全量 `.venv/bin/python scripts/run_acceptance.py --report docs/F2/evidence/eng014-acceptance-summary.json`：**388 PASS/0 FAIL/1 Windows SKIP/2既有WARN，108.474秒**，84个src/test/script hash匹配，compileall/diffcheck通过。原schema期望8升级9、未来版本拒绝改10，只随新增迁移合理调整，没有移除旧oracle。

最终Linux Chromium用实际低权限API+独立worker+PG16.2 Python3.12.14、双角色真实表单，不修改数据库完成资料流程。创建→一个槽→专员要求补正→企业追加目录→专员核对当前hash→企业确认本地资料准备→reload→重开→追加版本→拒绝未重新核对的确认；三材料版本/所有人工事件保留。320/390模拟无横滚、页面错误0、脚本文本未执行、切身份清空旧资料。只SYNTHETIC，未收到真实目录/资格证据，不宣称客户或园区试点。实际重启前的Preparation在重启后仍IN_PREPARATION/3材料版本/8事件；最终API回读Run SUCCEEDED但Case NEEDS_INPUT/external NOT_SUBMITTED/offline NO_EVIDENCE，见独立restart-and-case-check证据。

用户新授权的本线程网络复核仅一次：安全checkpoint be5742e之后，原Actions target依旧Get ...: Forbidden/CLI exit1，数值HTTP状态/header/requestID/拒绝层UNKNOWN；Git原origin分支只读查询exit0，5185cf4与基线相同。由此不能称Actions/全部通道恢复；未fetch/push/runner，不新登录/换代理/读token/改权限。完整非敏感错误及结果见eng014-access-recheck.json，官方Work Mode状态调查同源未证实。其他环境/Sim分支线索不继承到Park。

本轮功能切片至此结束：企业资料准备/人工核对有可见可操作闭环，不只辅助测试；F2完整多服务计划/资源/执行者接单与真实回执/模板仍未做。F1 IN_PROGRESS、F2正式准入NOT_PASSED、whole36AT6EX NOT_RUN、R4 DISABLED、Windows/LIVE/真实数据门保留，provider请求及预算0。原V1来源字节/行/hash和R4/Win11 guard/workflow保护保持；低权限Grant与纯文本新API均本地可信代码，不执行任意生成代码，无外部业务写入。FirstUse说明显式合成入口/角色与限制，Plan标注新授权仅替代此前当轮不扩F2限制。

暂存前检查凭据模式无命中、无真实个人数据或private runtime/会话/DSN日志，安全本地commit保留checkpoint历史。阶段成果后仅更新一次用户私有Library恢复备份；不频繁上传，不把备份或恢复验证称Windows业务验收。最终本轮停止，交父任务复核派下一切片。

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


## ENG033 本地Case记录关闭与重开

按原V1§5.5/7完成当前合成资料Case的最小本地记录闭环：显式四项重验→本地关闭（真实Case WAITING_CONFIRMATION）→重开（REOPENED）→新cycle显式重验。保留材料/分派/回执/资源历史，不宣称真实目标FULFILLED。真实三角色浏览器2轮5事件与reload/窄屏通过，受控时序23/23，独立只读审查通过；最终冻结全量775PASS/0FAIL/1WindowsSKIP/2既有WARN（228.266s）、142份hash一致与证据见[ENG033](ENG033-LocalCaseLifecycle.md)。仅本地commit，无push/newCI/export/LIVE；最新Server37420887816仍FAIL等待已有安全JSON，不猜根因或盲重跑。F1未签收、F2准入NOT_PASSED、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0；原环境与备份保留。


## ENG034 有边界阶段收口与现有bug修复

对照原V1 T01—T07，独立只读检查资料、资源、分派/本人接单、合成回执和本地关闭重开。只新增准确能力/差距/依赖说明，下一步仅建议当前分派链授权站内通知及业务Outbox，未实现。主代理真实PG复现Case关联锁前时钟P2，旧代码1FAIL（返回NEEDS_RECHECK而非拒绝）；最小挪至最后锁后，72相关PG/API PASS（29.185s），独立资源补审确认修复。原775成绩保持ENG033历史范围；本轮bug修复后全量776PASS/0FAIL/1WindowsSKIP/2既有WARN（225.250s）、142份冻结hash一致，另记[evidence](evidence/eng034-closeout-review.json)。见[ENG034](ENG034-CloseoutReview.md)。不push/newCI/export/LIVE，不重复索图；Windows37420887816安全JSON仍未到，F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、模型/预算0。


## ENG037 固定四步持久合成模板

基线2da286a，用户采用ENG036四个A默认后实现单一工程审查模板。版本18新增计划及不可变CHECK审计，资料/资源关联/分派/回执原入口同事务校验当前前置，缺合法assignment阻塞，不新增Grant。固定P1—P4由企业显式重验，源失配/观察撤权不自动复活；保留原材料、已接受责任、回执和资源。

三位只读复核发现并关闭只读门误加EXECUTE、executor资料入口、CREATE误清未使用草稿、补记锁忙500及失败门/门通过后业务409丢失观察等问题。失败业务先回滚，观察补记独立元数据事务仅同plan ID/revision生效；锁忙返回可重试409，不能当补记成功；未观察撤权恢复仍无统一授权epoch保证。真实PG含崩溃/重启/幂等/CAS/当前权限/越序零副作用及两条观察失败路径，最终29模板例PASS。初始139PASS/2FAIL和期间源码变化的全量836PASS/1SKIP均保留为中间记录，不挪作最终冻结成绩。

最终冻结全量837PASS/0FAIL/1WindowsSKIP/2既有WARN（261.69s），154完整源/142runner源hash匹配；397安全诊断函数ID，24保护文件与两份原V1源保持。真实三角色Chromium/API/worker/PG闭环及观察撤权恢复：初建缺assignment BLOCKED，fixture owner另行准备访问后四步完成，再P2—P4显式重验到revision8/events8；Case仍NEEDS_INPUT，资源/责任/回执保持。18新计划+16既有通知+23既有Case时序PASS，9张独立当前图hash匹配/320390无溢出/刷新持久。owned harness/API/worker精确PID停止，PG及历史环境/备份/证据保留。

证据见[ENG037](ENG037-ControlledTemplate.md)及[evidence](evidence/eng037-controlled-template.json)。只本地commit，无push/newCI/export/LIVE/真实模型/预算。完整DAG/发布/Approval/授权epoch/AT14预览/无fixture赋权冷会话/真实履约仍欠；F1/F2未签收、R4关闭、Win11和36AT6EX NOT_RUN。最新Server37420887816仍FAIL等待已有安全JSON，未重复索图或网络/盲重跑。


## ENG039 有界安全诊断annotations

用户授权本地实现，新增固定notice白名单摘要，8条/整条2KiB含LF/总16KiB/整批25无路径测试ID。两位只读审查定位并闭合Windows CRLF实际字节P2，真实本地模拟旧2049/16392超限→二进制2048/16384。最终相关169PASS/0FAIL/0SKIP/1既有WARN8.63s，4份冻结hash一致；唯一原保护文件授权变化publisher，业务src及原ENG037拒绝路径证据保留。不改原失败/清理、权限/环境策略，不上传日志/artifacts；异常常量关闭，stdout原JSON后追加annotations。见[ENG039](ENG039-SafeAnnotations.md)。仅本地commit，无push/newCI；当前Server37420887816根因仍UNKNOWN，实际新annotations送达/nativeWindows未验证，F1F2未签收/R4关闭/36AT6EXNOT_RUN/模型预算0。


## ENG040 普通同步与有界annotations真实送达

实时远端c5b389b到8ddf139为7提交普通快进，无他人提交覆盖；唯一标准run37439323047/attempt1精确head8ddf139已completed/failure。正常API收到5新安全annotations：harness5PASS/3FAIL/1NOT_RUN、零case省略；Doctor/Start exit1、API_browser_restart因START_FAILED未运行、完整回归regression_run TimeoutExpired且counts MISSING/无pytest ID。底层Doctor/Start原因与具体测试未知；不把旧run未知猜成同因。发布器成功，PG status/stop exit0/无超时，外层native_suite693.422秒exit1未超时。见[ENG040](ENG040-SyncCI.md)。结果docs-only同步不命中唯一workflow的paths，无重跑/权限runner更改/日志下载/artifacts/模型预算；原签收门保留。


## ENG041 Doctor/Start与回归等待最小阶段诊断

再次正常API确认37439323047的Doctor/Start exit1底层原因UNKNOWN、内部regression_run TimeoutExpired；本地真实缺解释器/UTF8配置/loopback连接/端口/自有PG角色schema、pytest三阶段与父超时后代存活探针分别验证。新增仅Doctor/Start固定stdout标记与UUID绑定pytest阶段，保持判定/600s/900s/权限/环境/产品清理。203相关PASS；最终完整895PASS/0FAIL/1SKIP/271.73s、冻结一致，两位只读复核无阻断。见[ENG041](ENG041-DiagnosticBoundaries.md)。只本地commit不push/newCI，实际Windows原因/PS5送达及产品后代回收仍待验证；不改阶段门/R4/模型预算。


## ENG042 单次诊断CI终态

ENG041普通快进push至9801259，唯一标准37444794329/attempt1 completed/failure。新安全字段真实送达：Doctor/Start BoundaryError/private_acl/ACL_REFUSED；完整回归内部600s TimeoutExpired、最后记录pytest_call，仍无ID/counts。发布器/ownedPGStop成功，外层684.516s exit1未超时。ACL具体子分支未知，优先检查Setup之后新文件初始化与严格ACL合同；本地自有测试后代存活单列OPEN，不能当Windows原因。见[ENG042](ENG042-SingleDiagnosticCI.md)。未再push/newCI或改600s/权限，修复范围仅方案，阶段门/预算保留。


## ENG043 只读ACL检查与等待调查

仅本地修复ACL元数据/SID解析：旧检查受控读取/转换错误可exit0，新检查fail-closed并保留原严格合同；Setup最终只读复查及固定有界错误沿已有协议传播，未改实际对象权限。后代测试flush竞态已修，受控ThreadPool退出等待模型不归因实际Windows600s；OWNED_REGRESSION_DESCENDANTS仍OPEN。两位只读复核无剩余阻断，最终冻结完整回归922PASS/0FAIL/1WindowsSKIP/2既有WARN/270.92s，148份源hash一致。见[ENG043](ENG043-ReadonlyACLAndWaits.md)。不push/newCI/提高600s或900s；真实Windows/PS5及具体ACL违规条件、实际超时原因未知，原阶段门/R4/预算和环境备份保留。


## ENG044 最小对象与最后测试观测

仅沿既有安全协议增加ROOT/SESSIONS/CONFIG对象及同一原子快照的白名单去参数active_test_id；称最后记录，不称确定根因。严格ACL合同、600s/900s/权限/身份不变，JobObject产品修复未混入，后代回收仍OPEN。定点264PASS及两位独立只读复核通过；连同ENG043普通推送至8da8e4a；唯一标准37450539320失败，Setup已明确SESSIONS/ACL_OWNER_MISMATCH，完整回归600s TimeoutExpired最后原子记录pytest_call及test_plan_revision::test_after_artifact_and_terminal_run_outbox_atomic_recovery_no_new_call，具体挂点/因果未知，PGStop成功；未再push/newCI。见[ENG044](ENG044-MinimalObservationsCI.md)。原签收门/R4/预算、环境与备份保留。


## ENG045 定点恢复等待与 SESSIONS owner 待审批方案

只读解释 TOKEN_OWNER 与父目录 ACE 继承分别决定默认 owner/访问权，实际 owner SID 未观测；最小候选仅 Windows 首次新建 SESSIONS 的 owner，在写 token 前验证，DACL/SACL/继承/其他对象保持，待用户确认，实际安全变更0。精确最后记录恢复测试原样1PASS；受控自有 PG 锁复现旧DSN等待、新测试DSN 1秒锁/5秒语句超时及释放后恢复，回滚/两份reservation/唯一成功outbox保持。独立复核通过，最终定点26PASS/0FAIL/2既有WARN/17.56s，三份源冻结，见[ENG045](ENG045-TargetedRecoveryAndACLPlan.md)及[evidence](evidence/eng045-targeted-recovery.json)。仅本地commit，无push/newCI/全量/权限执行/模型预算；Windows600秒根因UNKNOWN，600/900与产品清理保持，后代回收OPEN，原阶段门/R4/环境备份保留。


## ENG046 专用 JobObject 本地实现，原生验证待完成

保留Linux实际直接父超时后自有后代存活基线（性质FAIL、探针1PASS）；仅Windows outer native_suite/inner regression接入新无名不可继承Job，挂起创建→精确creation handle/PID与Job归属验证→恢复，绑定拒绝无fallback。正常/超时/协调器异常仅回收本Job默认继承的后代；外层包括本次生命周期新建后代，既有外部PG/无关进程不加入，原owned PG Stop保留。600/900不变，清理5秒确认；原非0/TimeoutExpired保持，cleanup失败单列不变PASS。两位只读复核定位并关闭创建期stdio关闭错误导致挂起child句柄丢失；低层注入覆盖。最终7份源冻结定点152PASS/0FAIL/4WindowsSKIP/2受限socketDESELECTED/1既有WARN/8.33s。见[ENG046](ENG046-OwnedJobRecovery.md)及[evidence](evidence/eng046-owned-job.json)。仅本地commit，无push/newCI/LIVE/ACL/提权/runner修改/模型预算；SESSIONS owner仍待审批，OWNED_REGRESSION_DESCENDANTS为IMPLEMENTED_NATIVE_VERIFICATION_PENDING未关闭，真实Windows挂点UNKNOWN，原阶段门/R4/环境备份保留。
