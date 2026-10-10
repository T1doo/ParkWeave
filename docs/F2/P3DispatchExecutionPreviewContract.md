# P3 原分派隔离执行冻结合同

基线 `31336f74f187f4268c31af1ff6284426aea19d26`，候选开发分支 `candidate/p3-dispatch-execution-preview-20261010`；root 是唯一源码/Git写入者。P2 已独立 LIMITED_PASS。本合同和 [SQL 闭包](P3DispatchPreviewSQLClosure.json) 在实现前冻结。完整 AT14、Windows、P4/P5 不签收。

新独立 scope、0700 根和 0600 SQLite，沿用128条/每Case16条/正文及proof64KiB、不可变记录、BEGIN EXCLUSIVE、当前授权先于历史、源CAS、同key/不同body拒绝和丢响应 GET-only 恢复。不得改旧P1/P2格式或库。请求仅已有三项CAS加显式 decision ACCEPT/DECLINE（默认ACCEPT）；没有任意SQL、资源、角色、身份、路径或提交回执参数。

原owner READ/EXECUTE/PREPARE和两资源READ/HOLD仍为交集。原 preparation.reviewer_id 必须是当前同企业的获派专员并有READ/REVIEW_ASSIGNED；执行者必须是此精确Run唯一当前获派且具READ的service_executor，走原 assigned_executors、_executor/scoped_run/assignment_allowed，缺失或多候选均关闭。对受管理Run继续原租约/指派bridge及提交前重验；不得给正式身份补Grant或assignment。原专员和执行者身份、授权、Run指派generation进入来源hash，资料、Case/Run、双槽版本/hash、请求revision、完整目标、精确P1/P2/P3注册合同和资源规则绑定；来源变化保留历史STALE，不自动完成或重绑定。

先运行既有隔离P1/P2原函数，实际产物作为P3前置：同一预览Case/Run/preparation、双槽证据和确认hash、实际资源关联/组合/receipt。仅将这些本轮产物复制到专属临时表，生成新模拟executor及临时精确Run资格，角色明确SIMULATED_ROLES_ONLY；不是原真人批准或正式接单。资料影子使用原enqueue所要求的SYNTHETIC，外层scope及独立UUID仍为PREVIEW_EXECUTION。

实际调用原 service_dispatches.offer（模拟原获派专员）和 command ACCEPT/DECLINE（模拟该executor本人token）。原角色、CAS、材料fresh、Run READ/指派、owner/获派专员交集、controlled_plans.gate/invalidate和dispatch_notices.enqueue不替换、不stub。P3使用空新预览Case的controlled_plans，不复制正式plan/Approval。完整SQL闭包包含service_dispatches/offers/events、service_receipt_steps/events、dispatch_notice_outbox和空dispatch_notices；不能落回public。封闭代理仅精确冻结字符串，无commit、DDL、游标、新连接或未知函数。任何新增模板需先修订冻结，不能绕过allowlist。

ACCEPT须真实生成OFFER/ACCEPT事件和CREATE receipt-step（AWAITING_RECEIPT，无receipt正文）；DECLINE保存OFFER/DECLINE而无step，明确尚未接单。原enqueue实际写临时PENDING outbox；不调用consume，不生成delivered notice，不开启worker或外部通知。临时事务最终rollback/close，formal dispatch/receipt/notice和所有public表零业务写入。预览UUID不得被正式入口消费。领域Conflict保留实际已有影子证据及FAILED，基础设施失败不假装领域结果。

页面在原bounded-planning增设P3明确ACCEPT/DECLINE预演，独立五字段不透明24h/8条恢复句柄，无token/资料正文/完整产物；上下文切换、身份/草稿变化及403清私有视图、拒绝迟到回复，不自动POST。显示实际P1/P2/P3、DECLINED未接单、P4/P5未预演、正式写0/模拟角色/Case未完成及全目标。独立proof锚完整artifact/state/decision/来源与目标，单独重hash正文不能改事件或判定。

验证真实HTTP/PostgreSQL/SQLite/Chromium：实际原函数、关系与PENDING outbox闭包、全部public表前后值和旧P1/P2字节；ACCEPT/DECLINE、OFFER后原ADD_EVIDENCE换版拒绝；精确Run撤权/错Run/跨企业/身份/READ/获派专员/managed资格；CAS/同key并发/异body、SQL逃逸/未知模板/P4写入/UUID消费、来源变化旧历史、持久proof篡改、丢响应GET冷热恢复/实际API进程重启、320/390/1200布局与隐私/迟到回复。保全所有失败日志并分窗报告实际计数。候选普通推送后精确SHA独审，未审不得合dev。main/凭据/权限/安全网络配置不改，不部署。
