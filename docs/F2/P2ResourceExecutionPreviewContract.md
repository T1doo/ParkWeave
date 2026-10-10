# P2 原资源适配器隔离执行冻结合同

实现后精确源码、独立分窗结果及未签收边界见[P2ResourceExecutionPreview](P2ResourceExecutionPreview.md)。本合同保留实现前冻结，不将局部预演外推为完整AT14或正式资源可用量。

基线 `24c6a9d2bfc2842fcbe2323b69f76f8117170f69`。root 单源码/Git写入者；正常fetch和远端HEAD已核实，无待合并操作，不碰main、权限、凭据或网络配置。先冻结本合同再实现；旧P1 v2产物及入口保持兼容。原AT14继续按局部预演报告，不签全AT。

新显式合成factory、独立0700目录/0600 SQLite、不同scope绑定原cluster/database；复用已审rollback-journal BEGIN EXCLUSIVE、当前权限优先于历史、不可变proof、有界128/每Case16/正文及proof64KiB、同key CAS/幂等和503后GET-only恢复。不迁移、清空或修改旧P1库。原Case/Run、资料revision、请求revision、双槽ID/version/hash、完整目标及P1/P2精确注册合同和两条既有授权资源规则hash均绑定。来源变化保留历史标STALE，匹配仅SNAPSHOT_MATCH/source_atomicity=false。

仅现有P1 preparation revision1与P2 case-resources revision1及原resource-link CREATE_OR_RECHECK_LINK；依赖须精确P2→P1，原service version1。固定既有两条合成资源，当前owner READ/EXECUTE/PREPARE及两资源READ/HOLD全交集；缺权限不建临时授权来绕过。拒绝未知目录、未知动作、任意SQL/路径/角色/资源。真实已授权规则只读复制，生成新资源UUID；不复制正式占位/组合/Case/Approval/通知/身份/Grant。预览空间初始占用为0，预演容量不代表正式可用量。

先真实执行原P1双槽ADD/REVIEW/CONFIRM，失败则P2明确NOT_EXECUTED，不填成功。P1成功后其新UUID及实际确认hash作为另一专属pg_temp事务的前置证据；生成仅预览身份与权限、Run/Case、资料影子及空controlled_plans。实际调用原resource_holds.preview/create、resource_combinations.confirm、case_resources.bind，预演从当前服务器时间一小时后开始，持续一小时、数量1，原窗口/版本/容量/CAS/角色/幂等检查运行。原P2关联未涉及正式Approval，不把临时Case NEEDS_INPUT改为完成；不生成任何P3–P5动作。

固定影子表名单仅这些原函数所需表，CREATE TEMP LIKE仅结构/default、不继承FK/触发器；SET LOCAL search_path仅pg_temp，无public回退。适配器代理只允许冻结的精确SQL模板；无DDL、schema限定、未知SELECT副作用、commit、任意游标或连接暴露。每个事务显式rollback/close。原方法需要的autocommit只读False。新触及模板或表必须拒绝，不运行被遗漏的依赖。原gate无正式计划副本，不绕过已有正式计划；这是新预览Case的本地动作，非正式P2批准。

实际预检、占位receipt、组合成员/receipt、Case link/claim从临时SQL读回；领域Conflict保存FAILED及已有临时证据，并明确未完成步骤；基础设施故障不伪造FAILED/SUCCESS。独立proof同时锚定完整artifact/state及全部来源与目标，改正文重hash不能改步骤或省目标。所有临时UUID只能在预览空间，不可被原正式入口消费。旧P1产物前后逐字节比较。

原bounded-planning页面增加独立P2明确预演、历史与原key只读恢复；沿用五字段不透明24h/8条句柄、上下文generation/身份/编辑/403清私有视图和迟到响应拒绝。句柄仅在不同P2 storage key保存，不含token、正文、原资源详情或完整产物，不自动POST。显示P1/P2实际结果及P3–P5未预演、正式写0/Case未完成/模拟角色/空隔离容量。

测试：真实HTTP/PostgreSQL/SQLite/Chromium，所有public表及逐行值快照（仅既有脱敏authorization_audit单列），实际原函数/pg_temp/关闭、成功/原窗口或禁用规则Conflict/原资料补正与规则换版旧历史、不支持目标、注册动作漂移、同key并发/不同body、丢响应冷热GET恢复、撤READ/HOLD/EXECUTE/PREPARE、跨企业与角色、源CAS、基础设施故障、原UUID消费拒绝、SQL/public回落负例、P1旧库字节不变、320/390/1200与隐私/迟到回复。候选普通推送后独立审查精确SHA；未审不合dev。WAL排斥、全来源原子性、全仓/完整AT14/Windows、正式容量/Approval/通知/履约和P3–P5执行均不签。
