# 迟到 OFFER 意图栅栏：独立静态结论

基线 `c2263edd889c2b9b4ada9f502b3a41b32eb9341f`。本次只读源码，**未运行测试、未实证 HTTP 利用或 PG 竞争**；以下是可达路径的静态反例与下一轮 oracle。原 `baseline-v1.json` 已绑定相关原件哈希。仅新增 frontier-oracle 文件，旧合同与记录保留。

## 结论

原材料 revision、原当前计划 gate、父 UPDATE 锁和 effects epoch0 **不能完整拒绝提交后迟到的旧 OFFER 意图**。它们证明处理时当前前置和事务串行关系，原请求没有携带它针对的计划身份/代际。新 tracked default-off 协议应要求原命令显式捕获并核验新的意图 fence；没有 fence 的旧 body 在该 scope 中拒绝，不能从服务端当前状态代填后执行。普通未启用 legacy 合同单独保持。

## 静态来源与逻辑

1. `service_dispatches.Offer`12–18仅有 expected_preparation_revision、expected_dispatch_revision、executor_id、reason和可选recovery_receipt_step_id，没有plan_id/source/generation/fence。指纹325–329从这份body生成，因而相同body无法区分旧/新计划意图。
2. `service_case_steps.adopt`759–785 full ADOPT生成新plan UUID和步骤UUID，保存旧history，`adoption_preparation_revision=parent['revision']`。`_save`503–504仅`UPDATE preparations SET service_case_plan=...`，没有增加材料`preparations.revision`。
3. `preparation.command`约190–232的REOPEN/REVIEW/CONFIRM确实各自增加材料revision。它能拒绝在这些动作**之前**捕获的请求；但不能拒绝在最后CONFIRM之后、fullADOPT之前捕获的请求。不能从常见夹具确有re-review推断所有迟到意图被拒。
4. `service_dispatches.offer`325–364拿父UPDATE，检查gate2、material_current、材料revision和dispatch revision。没有dispatch root时当前revision总是0。写入offer只保存当前材料revision/hash，没有请求的旧plan身份。
5. `controlled_plans.gate`191起转交`service_case_steps.gate`356–375。后者重新读取**执行时的当前plan**，只要求through2的P1/P2状态为VERIFIED和当前binding有效，没有验证它等于用户构造请求时的plan。
6. `service_dispatches.catalog`230–250返回材料/dispatch revision和ready，ready只检查资料/offer/执行者/历史容量，不把原gate2的计划定义和核验事件绑定进请求。
7. 原web.html约968–995从servicePlan进入dispatch时只比较preparation id/revision、case和run，body仍没有plan字段。即使浏览器随后丢弃旧响应，服务端也可能已经产生实际offer，不能把前端requireCurrent当服务端意图栅栏。

## 一个不靠缺失数据的静态反例

- 真实旧plan的P1/P2已经完成、P3从未派单，八表全空/marker0。
- 按原合法新目录来源变化完成REOPEN→REVIEW→CONFIRM，材料revision成为r。
- 此时读原dispatch catalog构造旧计划意图 `expected_preparation_revision=r, expected_dispatch_revision=0`，合法reviewer/executor/reason和全新key，暂不发送。
- 原full ADOPT生成newplan，材料revision仍r；明确新批准、原资源COMMIT、新P1/P2真实VERIFY，dispatch尚未创建，当前原gate2可满足，effects tracker仍0（P1/P2不是追踪八表）。
- 才发送原body。原材料和dispatch比较均相等，gate2查看的是newplan并可通过，原OFFER写入以当前资料与当前plan前置被接纳。

以上是代码条件构成的可达反例，不宣称已由本轮PG/HTTP执行复现。`r_old`请求会被新材料revision拒绝，不否定上述使用r的窗口。新COMMIT之后、P2VERIFY之前可能因gate拒绝，但随后P2VERIFY恢复可执行，不能把短暂拒绝当长期意图作废证明。

## 三种事务顺序必须分列

|情况|应有行为|原锁/epoch是否足够|
|---|---|---|
|旧原OFFER先提交，再新资格/新交付|marker非零/evertrue及完整历史使新资格拒绝；新资源/consume无效果|父UPDATE串行+八表追踪可支持，需真实PG证据|
|新交付先提交且P2VERIFY完成，再迟到旧意图|拒绝旧意图，不能当新plan业务动作；原offer/effects保持零|原锁/epoch0不足，必须显式意图版本fence|
|用户在当前newplan/新交付/P2前沿fresh读取并明确OFFER|在原动态授权/材料/来源/gate与新fence匹配时允许，之后原ACCEPT/回执/P5办理|不能永久禁用派单，也不能要求业务办理后epoch仍0|

## 推荐合同

对tracked新scope，用严格可选扩展类型实现协议，但是该scope内字段**必须**提供；missing/partial/malformed或旧代际直接拒绝。GET只提供真实当前上下文，用户命令明确回传；服务器不能用当前值填补旧请求。字段必须进入原请求指纹、event/receipt lineage及冷恢复匹配；同key不同fence拒绝，原提交回执的只读恢复保留。

最少要以当前完整plan UUID或在fullADOPT时推进的可信generation区分旧/新计划，且绑定issuer/database/install generation/birth、preparation/Case/owner/tenant/Run和当前trackerepoch。**纯effects epoch0不在fullADOPT/COMMIT/P2VERIFY时变化，不能独自充当意图generation。** 只expectedplan_id也不会拒绝“newplan已ADOPT但尚未新COMMIT/P2VERIFY时捕获、迟到到P2后”的同plan意图。若该窗口也在合同的旧意图范围，fence应额外绑定原new resource link revision/交付context、原P2实际VERIFY事件/证据和当前preparation物理row版本，或在这些前沿变化时推进可信独立generation。不要仅靠可回到相同外观的状态布尔。

在父UPDATE内，先重新校验动态身份和新fence，再处理业务gate/效果；等待任何锁后重验不能缩短原授权/时钟规则。只有gate2当前满足时才提供可执行的fence可减少提前捕获窗口，但仍不代表GET授权自动派单。fence保存/发送不会隐式PROPOSE/APPROVE/COMMIT或赋权。

相同语义应调查所有起步写入口：OFFER/REOFFER与legacy receipt CREATE是明确重点；ACCEPT/receipt/SUBMIT等已有实际dispatch/step identity和revision锚点也不能被新协议意外绕过。前沿scope允许原后续P3/P4/P5写入，必须使用**当前真实**上下文，不可把`ever_started=false`当所有后续写入的持续前提。

不要靠fullADOPT顺手增加材料revision解决这个问题；原材料review/hash/资料事件和计划修订是不同合同，随意增加会破坏已确认材料证据，且不能替代明确计划意图。

## 待执行独立变体

新 `late-intent-design-v1.json` 全部DESIGN_ONLY/NOT_RUN。集成后应实际保存旧body/key（私有，不打印token），完成新交付/P2后通过原ASGI请求发送，断言拒绝且八表/marker/容量/link/consume不变；再fresh读新fence与原用户命令真实OFFER成功。另分别覆盖旧写先提交、新写先提交、并发排队、同plan新COMMIT/P2前捕获、无fence拒绝、改fence幂等冲突、提交丢回执后原key冷GET。纯合同或字典测试不能替代以上实际PG/HTTP证据。
