# 已有人工回执后的取消请求与核对：有限合同

实施前冻结，从父审限定签收的交付 `189379b7f7c94dfacfff697ad06a4ea1a5780048`、源码 `3fc6fa712f14820d88fcf8cd94fa70fcf6120e0c` 正常创建独立开发分支 `dev/f2-case-cancel-after-receipt-20261011`。根任务唯一源码、测试、文档和 Git 写入者；原独审只读新实现并保存自己的独立运行证据。本合同不是测试通过声明。

## 原产品依据和有限对象

原 V1 §5.5 要求执行者只更新获派步骤，企业决定必须有实际凭据；§7.1 将成功建单 Run 与 Case 办理结果区分；§7.4 要求取消先记录请求、停止新步骤、核对在途结果，未决保持 RECONCILING，既有履约事实保留、预约独立受权释放。

仅成功且 VERIFIED 的普通 SYNTHETIC 建单 Case，已有真实 ACCEPT、至少一份真实本地人工 SYNTHETIC 回执。完整历史资料、ACCEPT/OFFER/CREATE、所有回执及企业决定必须可验证。支持此前合法换人、新材料重接单、原人工补正/重開历史；不能只查看当前回执指针。

任何外部受理/履约效果、adapter_execution、隔离 provider 或 managed Run 来源、legacy 无接单直建步骤、无法核实或损坏证明、任何本地关闭历史、已取消、非本片状态、超有限历史上限均明确拒绝。这里的人工合成回执是已提交的本地事实，核对不证明真实线下履约，也不能改写或抹除原事实。

原 `/case-cancellation` 首次接单前及 `/case-cancellation-before-receipt` 从未提交回执的边界原样保留；新接口 `/case-cancellation-reconciliation` GET/POST/recovery，独立 scope 与三个 action。取消后恢复、外部结果核对、真实业务履约、已关闭后取消和完整 Case 生命周期不在本片。

## 三次明确操作

1. `REQUEST_CANCEL`：企业原 owner 按当前 READ/PREPARE/EXECUTE，明确原因与布尔确认，绑定 Case UUID、资料版本、local 版本及完整来源 SHA。持久事件和 Case/local RECONCILING 同事务。即使全部既有回执已 ACK，也只记录请求，不自动核对或终结。
2. `RECONCILE`：同一 owner 明确核对原请求下的全部历史回执。逐项确认精确 step UUID、receipt UUID、version、正文 SHA，并记录 `KNOWN_LOCAL_RESULT` 或 `UNRESOLVED`；集合必须与全部已证明 SUBMIT 记录完全相等。核对事件保存完整原证明快照，local 版本递增，Case/local 仍 RECONCILING。原回执/步骤/企业 ACK 均不变；KNOWN 仅表示该本地提交结果已核实，不能表示原企业诉求已履约。
3. `CONFIRM_CANCEL`：同一 owner 再次明确终结原因/布尔确认，精确绑定原请求、最新核对事件、Case/资料/local/来源版本。最新核对必须覆盖全部历史回执且全部 KNOWN_LOCAL_RESULT、证明仍一致；任何 UNRESOLVED 或缺失/损坏来源都拒绝，继续 RECONCILING。终结事件和 Case/local CANCELLED 同事务。

每次都重新核对身份、租户、owner、当前 READ/PREPARE/EXECUTE；有权历史读取需要当前 READ/PREPARE。相同原 key 同参返回原事件，异参、跨 Case/action/scope 冲突。原请求与核对原 key 可在后续合法阶段恢复为历史提交证明，响应另带当前持久阶段，不能用旧事件复活写动作。所有原事件、请求指纹、snapshot SHA、版本和阶段转换均重验；损坏或伪造状态拒绝。

丢响应仅 GET 原入口原 key；NOT_OBSERVED 不能表示未生效，也不自动 POST 重发。页面最多保存有界、24h、不含正文/理由/回执结果/凭据的不透明原键句柄。请求、核对、终结分别由用户确认，不替用户选择 KNOWN 或提交下一阶段。

## 写入口、核对路径和锁序

请求、核对和终结沿 parent UPDATE → 原 key advisory → dispatch UPDATE → Case UPDATE → local ledger 至事务提交。现 SUBMIT/企业 ACK/换人/材料/方案/资源关联等先持同一 parent SHARE/UPDATE，因此请求先赢则晚写及旧业务 key replay 拒绝；原写先赢则来源变化使旧取消请求拒绝，必须刷新并重新明确确认。两次取消操作也串行并执行原键/版本核验。事件插入失败必须全部回滚。

RECONCILING 即停止所有新材料、事实、规划采用/检查/交接、OFFER/REOFFER/ACCEPT/DECLINE/WITHDRAW、legacy CREATE、人工 SUBMIT/原 ACK/REQUEST_CHANGES/REOPEN、资源关联交付和本地校验/关闭/重开，含执行者与 receipt_parent 内部旁路。允许的企业核对仅上面的专用账本路径，避免把原回执 ACK 的 current-generation/P3 gate/计划隐式失效写当核对通道。不能将所有 scoped(write=True) 误判业务写。

有权历史 GET、需 FOR UPDATE 的读取及旧通知打开保留，取消中/取消后不隐式失效 controlled/registered 计划，不新增可履约按钮。旧 outbox 消费者、通知、迟到 UI/POST/GET 回复重新核对阶段；RECONCILING 和 CANCELLED 均不能恢复接单或回执写。

Run SUCCEEDED、资料、全部 ACCEPT/CREATE/SUBMIT/企业决定、步骤、资源关联/预约和容量保留，不伪造 WITHDRAW。取消请求和终结不释放资源；原 hold/group 独立释放仍按自身当前授权和原资源锁。Case 资源关联与请求共 parent 竞争；独立释放不修改 Case，不宣称与取消构成一个组合事务。

## 安装与验证门

schema 32 仅扩现 Case/local 状态 CHECK 的有限 RECONCILING，以及原 local event action CHECK 三个新动作；复用原 snapshot/event 表，不新表、Grant、registry、角色或权限。只在有原创建票据、真实当前 owner/transaction/table 所有权的自有 Linux 临时 PostgreSQL 安装；旧/native 默认拒绝边界保留。成功建单 Run 不改状态，不声称实现 §7.1 全部 Case 状态。

验收包括：真实 owned PG 请求与 SUBMIT/企业 ACK/换人/材料/方案/资源关联双向锁等待，核对/终结及同异键并发，独立释放竞争与容量保留；全历史多世代/补正/重開/损坏与外部效果反例；全部写入口/旁路冻结与冷读无隐式写；跨租户/非 owner/撤权；事件失败全回滚；未决核对不终结、明确全已知后二次确认收束；原 key 冷恢复、UNKNOWN 和迟到页面回复；旧取消边界全部保留。

最终冻结源码单次完成上一37完整模块加新后端模块，旧1391精确测试 ID 全保留；独立审查与自有反例另窗记录。真实每窗 PASS/FAIL/ERROR/SKIP/NOT_RUN、原始 JUnit/stdout、源码及导出两端 SHA、失败同 ID 映射、正常 push 与远端/未提交/未推差异明确报告，不拼多窗成一窗。

历史合法 worker 后 Case_count0 异常根因仍 UNCONFIRMED，不冒称越权修复。浏览器 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 原拒绝保留，本任务不启动浏览器或替换重试。无部署、生产迁移、真实模型/付费调用、凭据/网络配置、强推或 main/dev 主线修改。
