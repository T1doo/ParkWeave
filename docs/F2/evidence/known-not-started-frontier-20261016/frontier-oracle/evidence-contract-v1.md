# KNOWN_NOT_STARTED 单一前沿：独立证据合同 v1

本文件是执行前 oracle，**静态调查完成，实际测试 0；30 行设计全部 NOT_RUN**。起点实际 HEAD `c2263edd889c2b9b4ada9f502b3a41b32eb9341f`。只写新 `.runtime/frontier-oracle`；旧档、共享源码、测试和 Git 未写。源码哈希见 `baseline-v1.json`，逐变体预期见 `oracle-design-v1.json`。未启动回归、真实模型或生产操作。

## 资格与有限适用范围

本增量只能覆盖**新独立默认关闭的 issued owner PG fixture，在 preparation INSERT 之前已经安装并验证原追踪协议**的 Case。部署前或安装前已经存在的 preparation，哪怕当前八表全空、P1/P2完成，仍 UNKNOWN；不得回填出生 marker 后称“从未启动”。本地合成证据不能被宣传为正式部署、一般在途迁移、通用 ServiceRelease 或真实履约。

应同时满足：同 Case/owner/park/org/Run/原 request 和六目标；原完整 P1/P2 实际 VERIFY（原 verification 事件、source/hash、P2 原新批准和真实 COMMIT/CONSUME/link/资源证明）；原 P3 无任何派单或接单，P4 无任何 receipt step/版本/事件，P5 无任何 lifecycle 或事件；出生 marker 精确归属且 `epoch == 0`、`ever_started is False`；原八表所有生命周期查询成功、完整、有界并精确零结果；触发器与 issued authority 身份完整；其余原兼容/来源/权限/锁/版本守卫保持。

P3 曾 OFFER 后 DECLINE 或 WITHDRAW 仍是已启动；P4 仅 CREATE 而未 SUBMIT 仍是已启动；P5 仅 REOPEN/CANCEL/reconcile 也不是未启动。不可只过滤当前材料 revision/current_offer/current_receipt；须覆盖该 preparation 的全部历史代际。显示的 PENDING、null current id、空 DTO、LIMIT 1 查不到、无 query descriptor、缺 marker 或一个布尔 can_record 均不构成资格。已知“没有发生”与“不知道发生过没有”严格分开。

## 原始完整表集与静态依据

|集合|原表|资格查询及追踪事件|
|---|---|---|
|P3 root|service_dispatches|该 preparation 全生命周期，INSERT/UPDATE/DELETE|
|P3 offers|service_dispatch_offers|通过所有 root 关联，INSERT/UPDATE/DELETE，含非当前 offer|
|P3 events|service_dispatch_events|通过所有 root 关联，INSERT/UPDATE/DELETE，含 OFFER/REOFFER/ACCEPT/DECLINE/WITHDRAW|
|P4 steps|service_receipt_steps|所有 revision/代际，含 legacy CREATE，INSERT/UPDATE/DELETE|
|P4 versions|service_step_receipts|所有 steps 的全部版本，INSERT/UPDATE/DELETE|
|P4 events|service_receipt_events|所有 steps 的全部事件，INSERT/UPDATE/DELETE|
|P5 ledger|case_local_lifecycles|同 preparation/Case，INSERT/UPDATE/DELETE|
|P5 events|case_local_events|同 preparation 的全部事件，INSERT/UPDATE/DELETE|

原 `service_dispatches._view` 约199–219行 root不存在立即返回 history=[]，executor还有自身投影过滤，不能作为 owner 全历史证明。`executor_receipts.current_step` 约82行只选当前接单或 legacy 单行；`_view` 的历史仅单个 step。`case_lifecycle._view` 约128行虽查询本 prep 全事件，但无显式完整 descriptor。`source_change_adoption.epochs` 约54–94行包含七类上述表的 xmin 集合，**漏 case_local_events**，不是新八表证据协议。

查询结果应绑定固定 schema/查询定义身份、scope、各精确 key、success/known、count、完整集合摘要、overflow/incomplete 标记和 birth/epoch。缺 key、错误类型、权限拒绝、数据库失败、未知 schema/函数或截断不得被 except 后替换成 []。应用合法角色原有 SELECT,INSERT 以及限定列 UPDATE（roles.sql 约33–46）；无事件 UPDATE/DELETE/TRUNCATE。应用模型不能宣称能抵抗任意数据库 owner/superuser，追踪协议也不得通过加权限实现。

## 追踪安装与不可重置证明

安装必须在新 preparation 出生前完成，marker只能由可信 INSERT 路径创建，不接受 caller JSON/现存 prep backfill。marker绑定 DB/issuer/安装 generation/preparation/Case/owner/tenant/Run/birth 身份，原始初值和后续 epoch/ever_started 不能删除后重建0或 UPDATE回0。一次原命令可影响多表，epoch增量不要求等于动作数，但 committed effect 必须导致单调非零；事务回滚也回滚该事务的epoch变化，不能把未提交效果称成历史。

行触发器必须涵盖八表的全部 INSERT/UPDATE/DELETE，OLD/NEW 归属变化必须更新两边或直接拒绝跨 prep 移动。存在 FK 不能替代追踪。**TRUNCATE不触发行触发器**，必须由独立 statement trigger拒绝或永久撤销受影响资格；仅当前数据全空不准复活。marker/schema自身篡改同样不能复活。

校验需查真实 pg_catalog 的固定关系/函数身份、namespace、owner、语言、完整函数定义/配置、security-definer属性、pg_trigger作用表/tgtype/tgattr/tgenabled和真实定义摘要，不以同名对象当真实原件；还需证明session replication配置不会跳过已声明的触发器。缺 trigger、停用、定义替换、owner变更、未支持额外触发器/表结构等均拒绝或UNKNOWN。

**当前目录定义恢复成原样不能证明追踪从未停过。** 如果 fixture owner 禁用→写/删→启用是受信管理员边界外，必须明确声明本协议只约束受控原应用写者和连续受信安装；不得把此变体记为已检测。若产品声称支持该威胁，则需另有不可由同一不可信管理员重置的真实持续generation证明，并实际PG测试。不可凭保存的“installed=true”补全此事实。

## 共同父锁、竞态与四阶段重验

静态写者清单：P3 offer/reassign/command先 `service_dispatches._parent(...write=True)`（约271/325/368行）拿 prep UPDATE，再dispatch/offer；ACCEPT同事务创建原receipt step和CREATE event。legacy `executor_receipts.create`约174行拿 prep UPDATE。P4 command约207–229行先 `_parent` **FOR SHARE** 再receipt UPDATE；P5 command约224行 `_auth(...write=True)`拿 prep UPDATE。取消 `case_cancellation.cancel`约160行及 reconciliation.command约268行也先 prep UPDATE，并可写 P5两表。三套 preview SQL 文件只是允许语句声明，不是另一个业务执行器；扫描到的实际八表写者均归以上模块。

新资格预览、PROPOSE、APPROVE、COMMIT各自必须在原同一 prep **UPDATE锁** 内重建证据并绑定 source/marker/epoch，不存在的child row FOR UPDATE锁不到不存在的未来插入；只读epoch前后相同也不能封住最后读后的竞争。COMMIT必须与资源确认/link/receipt/CONSUME原事务一致；取消和授权变化继续按原锁后时钟/原能力规则。

父UPDATE可排斥原P4父SHARE，因此已有写者可被新提交串行化。但新触发器若在原P4持SHARE、已拿effect行锁之后升级父UPDATE，两个P4 writer可能 SHARE互等或与effect行锁形成死锁。**触发器事后拿父锁不能自动证明全局锁序正确。** 候选需明确新fixture下写者锁顺序或安全拒绝语义；实际两个连接屏障覆盖迟到OFFER/receipt/P5，记录实际等待/失败/回滚，不把deadlock/locktimeout吞成PASS或扩原预算。

四个阶段之间真实已提交OFFER会使旧proof失效。若COMMIT先拿父UPDATE并提交，后来的旧派单只能在当前plan gate下重新判断，不能利用新资格替旧版本默许派单。反过来旧派单先提交则新提交拒绝，容量/link/consume零新增。所有线程/连接和错误日志保全，只有自有测试可有限停止。

## 历史与新办理链

新未消费申请须live重验；完成消费之后新原P3–P5会合法推进epoch，历史GET/P2/ApprovalGET/目标验证应验证**消费时保存的真实初始资格与原不可变ledger**，不能要求当前epoch仍0从而抹去合法历史，也不能把historical分支用于未消费fresh批准。正向必须真正新OFFER/ACCEPT→SUBMIT/ACK→REVALIDATE，加原P2–P5 VERIFY，六目标`LOCAL_OUTPUTS_VERIFIED`及工作清单原边界。P1在full ADOPT之后原VERIFY，合计新五VERIFY。Case仍不等于正式FULFILLED。

原“旧全部五VERIFY已经完成”的合同路径应独立保留，不能硬性套出生marker而回归拒绝；frontier不是删除旧known gate的借口。六目标、P1–P5、原history/容量/人工决定/未影响锁、原全部权限和来源约束继续原样要求。UNKNOWN一般业务包、破坏性或撤回来源不能通过frontier变合法。

## 执行与证据等级

`oracle-design-v1.json`预先冻结30种变体；目前全部DESIGN_ONLY/NOT_RUN。集成后独立候选测试先验证实际import位置、源码SHA/哈希、PG issuer/database和新独立artifact根；再按root给定有界窗口运行，保留所有失败，不自动重跑拼分。实际owned PG原产品函数、TestClient ASGI、真实native HTTP、Node受控DOM、真浏览器分别记载。组件查询缺失模拟或纯字典畸变不能冒充HTTP事实；owner故障SQL标明受控注入，不能说原API允许删除。丢回执必须实际提交后丢响应、原key冷GET、精确一次效果；仅人工构造receipt对象不合格。

本轮静态发现不是PASS测试。Windows、正式AT、特殊PG27、真实模型、生产、一般旧prep迁移及备份恢复未执行。
