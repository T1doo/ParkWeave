# ENG096 持久注册步骤计划、交接恢复与目录决定有效性

基线 `7f85abca90f4b5c9d25c43819cbeda88e3d41d6b`。本片对照原始 [V1 产品设计](../sources/V1/平台产品设计%20(2).md) §5.2/§5.5/§6.3、[阶段计划](../sources/V1/分阶段开发计划%20(2).md) F2-T02/T03/T04/T05，把工程预览与实际 Case 的步骤状态分开持久化。不修改原规格，不把原固定四步模板、只读导航或协调意向称为通用执行闭环。

## 明确验收目标

1. 从已保存的显式必需目标编译 1–5 个受支持注册适配器的依赖闭包，明确采用独立计划；每个 CaseStep 有稳定 UUID、服务/适配器版本、前置、责任、动作引用、输出与核验要求。未知/不支持的必需目标不删除，不能采用。
2. 原合法主体从原业务 API 办理，真实资源关联/分派/本人接受/回执来源驱动核验；已选前置没有当前有效核验时，直接调用原业务 API 也不能绕过计划。P5 的本地 Case 重验同样检查前置。
3. 保存协调意向/阻塞/恢复事件；本人拒绝后专员重新分派、本人接受；企业要求回执补正后执行者提交新版、企业核对。核验真实来源才允许步骤 VERIFIED，文本说明不是办理成功。
4. 提交成功但丢响应时同 body/key 恢复原事件；跨 Case、身份、版本、撤权和错绑来源拒绝。显式采用新版本保留旧计划/步骤/事件；一般 GET 的观察失效不能复活旧核验。
5. 目录决定保存内容版本与副本，后续用途明确检查当前版本；保留没有发布写者协议时的最后读取→COMMIT 窗口。无新 GRANT/凭据/审批权。
6. 同 Case 实际浏览器流程、独立审查、最终完整 Linux 回归与冻结字节；按既有授权普通同步开发分支，核实远端 SHA 与现有 CI 范围。

## 新持久对象与受限能力

新增 `service_case_steps.py` 和 migration022：在 `preparations` 加 `service_case_plan` JSONB 列。应用已拥有此表 UPDATE 权限；roles.sql/Grant/安全配置不变。迁移只在隔离测试数据库应用，生产部署尚未确认。Store 支持 schema22，打包包含022；既有升级保留/未来版本拒绝测试相应使用22/23。

计划保存采用时的 preparation revision、显式诉求/目标版本及指纹、Case/Run/service 引用、目录副本、注册表/动作版本、预览和目标覆盖。材料补充与正常业务变更使用步骤当前来源，不把正常版本推进当作整个目标变更。诉求/目录/注册表变化则阻塞旧计划；企业明确新 ADOPT 才建立新 UUID 计划和步骤，最多保留8份旧计划。每个活动计划最多64个协调/核验事件，乐观 revision 与全局 actor/key 指纹校验保持。

当前只支持已有注册 P1–P5（资料、资源、内部接单、合成回执、本地 Case 重验）的有界子图；可以采用1/2/3/4/5节点，不是任意 ServiceSpec/DAG/外部工具执行器，不自动创建旧 fixed controlled_plan。已有 fixed 模板若存在仍受原合同检查，不能借新计划暗中扩大固定模板目标支持。

GET/POST `/api/preparations/{id}/service-case-plan`；POST `/commands`。`BEGIN`、`REPORT_FAILURE`、`RETRY` 仅记录该原角色的办理意向、协调阻塞与恢复准备，不执行、重试或撤回业务命令，不创建回执/资源/assignment。未知业务结果仍通过原适配器的幂等键和核对恢复，不能用协调 RETRY 当作新业务请求。企业 `VERIFY` 须当前 READ/PREPARE/EXECUTE，核对真实当前来源、前置与 SHA 后保存；专员/执行者没有替企业 VERIFY 的能力。

真正业务状态单独显示（OFFERED/DECLINED/ACCEPTED、CHANGES_REQUESTED/LOCAL_ACKNOWLEDGED 等），不让协调意向覆盖业务账本。原绑定、分派/接受、回执和本地重验入口已接入活动计划 gate：前置必须当前 VERIFIED。合法原角色仍办理原动作，计划不代接单、代提交或批准。

## 当前来源与事件出处

P1 材料/人工确认，P2 当前关联/资源/规则/目录决定，P3 当前本人接受及同 Case/Run 的唯一回执步骤，P4 当前回执版本、内容 hash、执行者来源及企业 ACK，P5 当前本地生命周期核验。

独立审查发现“ACCEPT 事件存在”不足以证明当前回执步骤已被接受。现精确比较事件表列与 payload 的 dispatch/offer/receipt_step/action/state/actor/executor/revision；P4 同样检查实际版本表连续性、当前最后版本、SUBMIT/ACK 表列/payload、操作者/内容 hash/步骤绑定、顺序及最终 ACK revision。24个错绑/损坏来源反例证明不能误核验。通用 preparation GET 移除内部 planning_previews/service_case_plan 列；专用接口给企业来源，专员/执行者保留最小投影，专员不获 P4 回执决定状态。

计划 JSON 历史由应用合同逻辑追加/保留，**不是数据库 INSERT-only/不可变表**。GET 检查当前来源时可写入“已观察失效”元数据，保留 revision/事件；这是失效观察，不是业务执行或新增授权。正式不可变发布版本与 Approval 仍未实现。

## 目录版本决定与最小依赖

strict 资源影响记录新增 `immutable_catalog{document,source_revision,sha256}` 与 `decision_ref`；旧 strict 可从已存 P1 副本派生，历史不改写。当前目录内容 hash 与保存副本不同即 `STALE`，P1 按新目录重验不会更新旧资源决定；P2/P3/P4 及实际下游入口（含无 fixed plan 的既有回执入口）拒绝。须用户明确 strict 同组合重关联或选择替代，建立新决定；旧目录副本、关联历史与占用保留。没有 impact 的 legacy 关联是 `NOT_VERSION_BOUND`，维持原合同，不声称它是强版本决定。

适用保证是：每次用途检查所读到的已提交目录版本发生变化，就不能将旧决定当当前有效核验/授权；该决定本身也不产生任何新增授权。仍不保证管理员恰在该次最后读取之后、业务 COMMIT 之前提交变更时该次业务被挡住，下一次读取会失效。没有重复 SERIALIZABLE 矩阵，也不将快照隔离称为足够保证。

**一个最小外部依赖**：已授权目录写者采用正式发布/撤回协议，保留不可变内容版本及有效性，并与业务用途共同遵守版本锁/协调协议。当前只有初始化插入，没有受支持更新发布者；无需本片新增应用 GRANT，但缺写者协作就不能封闭管理员竞争窗口。Formal ServiceRelease/Approval 没有实现。

## 实际流程与证据

最终同一 Case、没有 fixed controlled_plan：明确采用 → P1 VERIFY 真提交后受控丢响应、同 body/key 恢复 → 原 UI 关联资源 → P2 VERIFY → 专员 OFFER → 本人 DECLINE → BEGIN/报告协调阻塞/RETRY（原分派仍 DECLINED，没有回执）→ 原专员重新 OFFER → 本人 ACCEPT → P3 VERIFY → 执行者 SUBMIT v1 → 企业 REQUEST_CHANGES → 执行者 SUBMIT v2 → 企业 ACK → P4 VERIFY → reload。四个步骤 UUID 和8个计划事件保留；导航无业务 POST、授权表不变。数据仍为原 SYNTHETIC 合同，Case 目标未完成，不能证明现实履约。

最终计数、源码冻结、日志/JUnit 与浏览器证据在 [机器记录](evidence/eng096-persistent-service-case-steps.json)。专项步骤68通过，目录11通过；专项目录首轮11失败为新 decision_ref 中 UUID 未规范化，已修复并真实重跑通过。独立审查的来源与最小投影缺口已补反例；此前通过成绩按其旧源码/覆盖范围保留，不替代最终成绩。

F1 未签收，F2 仅并行探索，R4 关闭，模型/预算0。完整正式 ServicePlan/CaseStep、正式服务时限/批准、真实履约与原目标核验、AT14/AT35 和完整 Windows/Win11 验收仍未签收；现有 Server CI 仅独立隔离 Job。

ENG096最终本地验证：完整Linux1784PASS/0FAIL/0ERROR/9nativeSKIP/2WARN（452.95秒），244冻结文件0差异；最终步骤68PASS、目录11PASS、同Case浏览器1PASS与12张真实截图/14项产物哈希独审。全部计数与SHA见机器证据，不把专项重复计入全量。
