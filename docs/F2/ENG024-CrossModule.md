# ENG024 有边界跨模块合成验收

基线8e2195ad63dd19d0b7c8e3ef94f47e0c04044a6a，工作树干净且环境实际执行已核实。原V1与阶段门不变；只本地测试/具体缺陷修复/提交，不push/newCI/export/upload/backup/LIVE。

冻结断言：E01同一新合成企业诉求，企业两槽材料→获派专员纠错→企业新版本→专员核对→企业本地确认；E02同一企业按诉求标签预检两个不同合成资源，占位/同事务确认，另一企业不可读其组合；E03测试owner明确准备本次新SYN Run的合法既有assignment，应用不增加分派API，执行者提交有来源/hash/版本的回执，企业纠错/核对/重开，历史三版本；E04切角色/事项草稿和迟到响应不串，现有授权/事务/CAS/撤权回归；E05回执结束不自动释放资源或完成Case，明确整组取消清理且两条RELEASED；E06真实本地API/worker/PG/Chromium和桌面/320/390截图，旧22命名阶段图hash保持，冻结聚合源码匹配。

跨模块串联目前只是验收script手动关联Case/Run/Preparation、组合/占位与Receipt的ID和同一诉求标签。资源API没有通用Case/ServicePlan/Approval绑定，不能称自动依赖/目标编排、业务整体原子事务、接单或外部履约已完成。每个现有模块仍使用自己的当前授权与局部事务。执行者既有赋权明确来自合成测试owner，角色上限不增加；执行者不能读材料正文/企业事实，也不能代企业作出决定；本人步骤的企业纠错/核对/重开理由可读。真实资格/外部通知/证明核验未实现。

截图审计见ScreenshotEvidence与evidence/eng024-screenshot-audit.json。旧通用f2固定输出必须NOT_REPRODUCIBLE，不用新图冒充；无hash的历史图不能补造hash。旧ENG023 preparation目录在恢复后缺失也明确不可复验，历史测试报告保留，不把缺图说成测试FAIL或改历史成绩。新图用独立目录/manifest，本轮只补新流程的当前证据。

独立只读6.1sol medium审查现有模块角色隔离/事务/迟到响应与新验收代码，不把旧审查或实现者成绩当其独立执行；最终实际结果后记。F1/F2未签收、R4关闭、Win11/whole36AT6EX NOT_RUN，Windows37324704568失败明细仍待用户。


## 审查发现与修复

独立review发现通用apiCall无token/run/generation守卫、身份切换未清通用JSON/运行/诉求/事实草稿，旧事实review/create可在新身份回填。真实页面mock-response在原8e2195a复现7/7守卫失败（旧源码，不称后端越权或实际泄露）；最小修复只通用UI：冻结身份/运行/最新请求代际、响应返回与后续DOM写二次检查、旧错误忽略，身份变更清通用JSON/Run/表单/问题/clarification重试，Run编辑/导航清旧review与在途请求。业务API/角色权限/账本/模板不改。发送过的POST仍可能提交，忽略迟到UI不代表回滚服务端事务。

review另指出验收第二次占位可能把旧HELD卡当新响应；脚本改等待与之前不同且未收集过的新hold ID。原顺序browser已经PASS也不消除竞态风险，最终重跑冻结修正script。文档执行者“不能读企业决定”改为“不能代企业作出决定”，自己的步骤企业纠错理由依法可读，不扩过滤或权限。最终结果后记。


## 最终实际结果

E01—E03/E05—E06既有范围的真实低权限API/独立worker/PG/Chromium链PASS，材料纠错、新版本、人工核对/确认、双资源组合、合法获派回执纠错/核对/重开三版本、reload及显式整组取消两条RELEASED。执行者企业决定403、另一企业组合403/回执列表隔离；Case仍NEEDS_INPUT，外部NOT_SUBMITTED/线下NO_EVIDENCE。通用事实补充/评审/取消真实browser PASS，取消run_id=null不误改当前运行，事实仍UNKNOWN，原评审历史保持。第一次跨模块也PASS，但独立发现的旧卡等待竞态已修后重跑，不以一次PASS代替该修复。

E04实际排序oracle：原generic7/7失败明确复现，最终generic7/7、旧资料23/23、资源/组合31/31、回执18/18共79页面检查PASS；是mock-response，不当后端授权测试。最终全量555PASS/0FAIL/1WindowsSKIP/2既有WARN，166.97秒，115个包含JS的src/test/script hash与冻结字节一致；现有PG回归覆盖授权/撤权/事务/CAS/父变化，不新增pytest数或据此签收阶段。compileall/JS syntax/diffcheck PASS。

reviewer cross_module_review（用户指定6.1sol medium）独立两次只读：首轮通用UI身份/迟到回填实质缺陷、验收脚本旧卡等待竞态与文档措辞；均具体修复，最终未发现残留实质问题。它未执行API/DB/browser/测试或读私有runtime，不把实现者运行成绩当独立复跑。业务API/模块/权限未改；33原V1/Windows/R4/角色保护文件、roles SQL全字节不变，桌面/手机CSS未改。

截图审计最终41张登记图hash匹配（旧阶段22、ENG023回执10、本片新9），3旧通用图覆盖和3恢复缺图均不可复验。旧报告追加精确限制，不替换原成绩或补造旧hash。已查看新真实截图的资源确认/整组取消、企业纠错和320回执；窄屏320/390无溢出，用户视觉签收/真实设备/Win11未做。截图与初轮/最终日志保留本地，不上传。详细[evidence/eng024-acceptance-summary.json](evidence/eng024-acceptance-summary.json)。

本片到此停止扩展；注册服务有限DAG/目标覆盖、通用CaseStep/分派接单、通知/可靠Outbox全链、模板/冷会话和真实身份/证明/履约仍缺。资源绑定仅测试手动关联，不能称原V1完整端到端验收。F1/F2未签收R4关闭，Windows失败明细仍待用户。安全本地提交后停止，无push/newCI/backup/export/upload/LIVE，provider/预算0。
