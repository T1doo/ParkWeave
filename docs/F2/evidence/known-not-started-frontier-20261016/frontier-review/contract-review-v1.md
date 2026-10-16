# KNOWN_NOT_STARTED 独立合同审查 v1

状态：STATIC_ONLY / NOT_TESTED。实际基线 HEAD `c2263edd889c2b9b4ada9f502b3a41b32eb9341f`。本报告只读源码和后端未冻结候选；未运行测试，不表示实现通过。仅写本新 review 目录；旧归档、源码、tests、Git 均未改。

## 独立结论

可以限定为新出生、明确启用、原签发自有 PostgreSQL fixture 的独立协议。必须先安装版本化追踪再 INSERT preparations；既有 preparation 一律不可回填。零行、PENDING、当前指针、列表第一页及旧 source_change_adoption.epochs 单独均不证明从未开始。旧完整五步原 VERIFY 替换路径保持不变。

当前首要阻断是迟到命令缺少计划意图栅栏：原 Offer 只有 expected_preparation_revision/expected_dispatch_revision，无 plan_id。当前 gate 证明的是执行时现计划，不证明请求是在现计划下明确作出的。parent 锁和 epoch0 只隔离并发事实，不能隔离迟到意图。

## 具体迟到攻击时序

1. oldplan 的 P1/P2 完成，parent revision=r、dispatch不存在。A 构造 OFFER(r,0) 后网络迟到。
2. B 完成 frontier 预览、明确 APPROVE 和原交付事务；绑定 fresh newplan。full ADOPT 本身不保证更新 preparation revision。
3. 新计划合法完成 P1/P2，parent 仍可能 r；business epoch 仍0。
4. A 才到达。若只检查当前 gate、r、dispatch0、epoch0，则原请求可变成新计划首次派单。

应对：新协议 preparation 的每一个实际 P3/P4/P5 命令必须携带捕获的计划/generation CAS；可用精确 current plan_id + 不回退 generation（必要时计划定义/批准 revision），不能只依赖可循环状态。旧无 fence 请求对协议 preparation 拒绝，旧默认 preparation 原行为保留。所有 fence 必须进入幂等 fingerprint；同 key 改 fence 必须冲突。重放已提交同参数不能产生新效果；执行新写前最终同 parent 锁内复核。不能把新计划一次合法写成功当成旧请求已被拒绝的证据。

## 八表及写者清单

|表族|完整历史范围|原业务写者/入口|原父锁|
|---|---|---|---|
|service_dispatches/offers/events|任何 OFFER/REOFFER/ACCEPT/DECLINE/WITHDRAW；包含旧代和终态|service_dispatches.offer/command/reassign|parent UPDATE，再 root UPDATE|
|service_receipt_steps/step_receipts/receipt_events|所有 preparation_revision、所有 receipt generation；CREATE/SUBMIT/ACKNOWLEDGE/REQUEST_CHANGES/REOPEN|executor_receipts.create、command、ExecuteLocal；dispatch ACCEPT 调 _insert_step|create/ACCEPT父UPDATE；command父SHARE，后step UPDATE|
|case_local_lifecycles/events|任何 REVALIDATE/CLOSE_LOCAL_RECORD/REOPEN/CANCELLED/RECONCILING 及事件|case_lifecycle.command；case_cancellation._commit；before_receipt取消；cancellation_reconciliation.command|父UPDATE，再case/local等原锁|

SQL allowlist 的 dispatch/receipt/lifecycle_execution_preview 写的是隔离 shadow 表，不能当真实原业务效果或批准。协议不得混入 managed/native/真实执行适配器。dispatch_notice_outbox/notices 的原FK锚定 dispatch event；只在完整八表历史为空且约束定义被固定的范围内可由无dispatch event排除通知历史。直接改 cases.state 等不属于八表的其他人工决定仍须原 case/plan/current target 门拒绝，不能以八表为空抹掉。

roles.sql 允许 app 对 preparations 全列 INSERT/UPDATE，并允许各业务表的原 INSERT/指定UPDATE。不能只约定 API 不改 marker。app 原无 DELETE/TRUNCATE/DDL；测试owner可做历史删除攻击，追踪必须覆盖其 DML，权限owner不作为对抗任意超级用户的安全承诺。

## 最小版本化资格与四阶段复核

- installation：原 issued fixture identity、database/owner/endpoint 绑定；default-off；schema精确版本；八表+prep 的追踪在任何prep出生前完成，拒绝已有prep/二次安装。无新role/GRANT。
- birth：不可变 generation、prep/case/run/owner/tenant 身份及出生事务；marker epoch0/ever_started=false 由原 BEFORE INSERT 生成；用户显式供marker拒绝；UPDATE不可初始化NULL、改birth、降低epoch、true改false、剪历史；DELETE prep拒绝或保留不可删独立墓碑。
- live eligibility：同父UPDATE锁内原P1/P2真实VERIFY及proof重建、原完整六目标/P1–P5 scope/current targets、旧tail无任何协调活动、八表完整历史不存在、birth/trigger/function/constraint/owner/DDL epoch连续性、marker严格0。
- preview → PROPOSE → APPROVE → COMMIT 每阶段重核相同不可替换proof，最终仍走原明确批准和原资源交付事务。source/authority/target/plan ABA均不可仅凭最终值相同接受。预览及导入文字不是事实或授权。
- historical：消费时原epoch0/空历史proof和原APPROVE/COMMITTED事件封存；后续合法新P3会使marker>0。此后冷GET必须保留原receipt/COMMITTED事实，区分当前资格与历史证明，不能重新要求live epoch0，也不能以historical=True跳过live行后新造epoch0/count0。

对空性断言，原表约束及无分页的 `NOT EXISTS` / LIMIT1 正确查询可证明该快照不存在；对于任何需枚举内容的历史proof须上界+overflow UNKNOWN，不能返回伪完整count。所有关联应覆盖全部旧step/dispatch代，不走 current_step/latest/current_offer 快捷入口。

## 必须解决的锁与追踪风险

1. receipt.command 现为父FOR SHARE → step FOR UPDATE；child BEFORE trigger 再父FOR UPDATE会升级锁。A持child，B持父SHARE等child，A升级等B，可死锁。新协议必须在任何child锁前统一父UPDATE；逐入口包括原取消、重放恢复、legacy receipt.create核实，不用禁用trigger规避。
2. 八表 INSERT/UPDATE/DELETE 必须同父锁单调epoch+ever_started；UPDATE迁移父关联时 OLD/NEW 两边都标记、按稳定次序锁。多行跨父批处理仍可能死锁，应事务回滚拒绝并有限重试，不视为成功；未知/断裂FK映射拒绝。
3. TRUNCATE 行trigger不触发，八表和prep需 statement级拒绝或不可回退失效标记。不能TRUNCATE后把空表当新历史。
4. marker允许任意app主动单调增加只会fail-closed；不能用可设置GUC/pg_trigger_depth作为“内部”重置授权。trigger函数应无SECURITY DEFINER、固定schema/源表OID/origin；TEMP shadow不得冒充public追踪。
5. 精确校验全部相关trigger（包括额外trigger）、tgfoid/定义/事件/timing/enabled/args/WHEN/columns、函数owner/语言/配置/securitydefiner、表owner/OID/约束/分区或继承。catalog xmin/对象身份提供受信owner的DDL连续性拒绝，不能声称抵抗任意管理员重写系统目录。
6. 事务回滚会回滚marker，正确承诺是“无已提交本地P3–P5历史”，不是“从未尝试命令”或“无外部副作用”。真实/外部provider不在该profile范围。
7. source_change_adoption.epochs目前含 lifecycle 而不含case_local_events；不能复用它作为完整八表证明。应独立完整marker证明；如该旧epoch仍进入新审批签名，应加入local events或明确由新proof覆盖。
8. 原幂等key actor作用域、fingerprint、丢回执冷GET、跨tenant/owner撤权与sourcelease/current target拒绝原规则不变。未知marker/schema/丢trigger/旧prep/已开始后删行/删除再同ID插入/关闭再恢复均拒绝。

## 后续冻结后最小独立验证建议（本轮未运行）

真实HTML→ASGI→自有PG：原P1/P2 +新出生epoch0→新机会明确采纳/批准/交付→新计划P1/P2→新合法P3，并验证旧消费receipt冷GET稳定；另精确旧迟到OFFER在new P2后必须拒绝且八表/marker/资源无效果。逐八表DML与删除ABA、TRUNCATE、marker改写、trigger禁用/重建、老prep无marker、源withdraw/权限false→true、迟到批准、同key异fence、丢回执冷GET都需原始失败日志保全。原完整五VERIFY路径需受影响回归。Windows/正式AT/真实模型/生产等既有缺口保留。
