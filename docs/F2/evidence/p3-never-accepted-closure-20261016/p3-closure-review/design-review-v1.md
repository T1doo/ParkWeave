# P3已有完整历史、从未ACCEPT、明确收束：独立合同审查

STATIC_ONLY / NOT_TESTED。实际clean HEAD `c6f0771f92b585829bda1e7496aee98945e6877d`；本轮仅写新p3-closure-review，无PG/浏览器测试，无共享源码/Git或旧十primary/audit写入。

## 结论与最窄新profile

可引入独立default-off版本资格，限定原issued owner fixture、出生前完整追踪、原P1/P2真VERIFY、完整P3历史已由原决定收束且从未ACCEPT、P4/P5无任何历史效果。不能把此状态命名KNOWN_NOT_STARTED、把epoch归零、删除dispatch/offer/event、创建替代空root、或回填旧prep。可以复用原追踪基础设施，但原KNOWN_NOT_STARTED的严格epoch0/八表空合同必须保持；新profile需独立literal/schema/proof验证及消费anchor门，不能unknown profile降级为旧分支。

## OFFERED、DECLINED、WITHDRAWN与UNKNOWN

- OFFERED仍有尚待本人决定的原offer。任何预览、source-change采纳、新计划ADOPT、新APPROVE或交付都不等于撤回。应由现有park_specialist按原`service_dispatches.command(WITHDRAW)`明确填写reason并携带当前dispatch revision/captured fence。该API原本允许材料stale时收束，不复活原失效材料/权限。
- DECLINED是原获派executor的明确拒绝；WITHDRAWN是原specialist明确撤回。完整历史与当前指针精确证明后，两者才可作为已收束；不把UNKNOWN/未观测/超界/分页/指纹损坏/撤回请求结果不明当终态。
- 当前被撤权的历史actor不应使已经合法记录的历史决定自动消失；新的WITHDRAW仍要通过原当前specialist/租户/READ/来源适用权限。企业owner批准新资源计划不能代替specialist撤回或executor DECLINE。
- 丢撤回回执只做原冷GET/原key只读恢复；必须验证真实当前offer和终态event，不能看一次重放返回payload就认定当前root仍收束。重放原key不得发新事件、改状态或隐式撤回新offer。

## 完整P3证明（禁止current-only捷径）

在原parent UPDATE锁内读取全部dispatch root、offers、events，使用原64历史上界+overflow UNKNOWN。root恰好一个且tenant/prep绑定正确；root.revision等于完整连续事件数，revision从1逐一连续，event IDs/actor+key唯一。每个offer恰有原OFFER/REOFFER及一次相应terminal决定；原current_offer_id指向最终offer，无任何悬空OFFERED、ACCEPTED、非空receipt_step_id或ACCEPT事件；所有旧代也如此。

逐事件证明原payload/action/state/executor/reason/offer/preparation版本、event actor、fingerprint与原请求形状：OFFER/REOFFER用原sd.Offer（缺省recovery_receipt_step_id在原fingerprint中省略），DECLINE/WITHDRAW用原sd.Command；historical_fields精确保存fence，rawpresent-null拒绝，不能改变正常request None兼容。无ACCEPT历史意味着不能有predecessor receipt/handoff lineage；出现该类extras或无解释字段应UNKNOWN/拒绝。历史fence属于捕获的原plan/generation/prep/epoch，不拿今天的plan/权限重写旧证据。

后五表（receipt_steps、step_receipts、receipt_events、case_local_lifecycles、case_local_events）全部历史为空，不走current_step/current_offer/latest-accepted，也不只检查current状态。既有通知/outbox应保留原事件锚定的完整历史；不把通知已读/消费当撤回或接单。

## positive epoch必须证明从未ACCEPT，而非仅看最终空表

原marker正数/ever_started=true必须保留。但“positive marker + 当前全历史无ACCEPT/receipt”仍不足：原ACCEPT后有权限owner删除receipt/event并把offer改终态，会留下当前无ACCEPT。必须拒绝删除ABA及未解释mutation。

最窄原API trace可精确匹配原marker.events顺序、table/operation/record_id/transaction：

|业务event|原八表DML三项|
|---|---|
|首次OFFER|dispatch INSERT → offer INSERT → event INSERT|
|REOFFER|dispatch UPDATE → offer INSERT → event INSERT|
|DECLINE/WITHDRAW|offer UPDATE → dispatch UPDATE → event INSERT|

每个三项同原事务，record IDs对应实际完整行，marker revision连续，最终epoch等于全部解释的原DML数。任何DELETE、events UPDATE、后五表操作、额外/缺失/重排marker项、手工只增长marker均不能建立neverACCEPT，必须拒绝。保留原全trigger/function/约束/列shape/继承拒绝及受信owner连续性边界；不宣称抵抗任意超管或不可见owner系统目录/DDL篡改。

## 全历史摘要与四阶段fence

预览、PROPOSE、显式APPROVE及COMMIT都绑定同一严格版本化资格：birth/protocol、previous plan ID、原P1/P2proof、dispatch root ID/revision/current_offer ID、全部offers/events摘要、原terminal决定event ID+fingerprint、positive marker epoch及完整trace摘要、后五空历史摘要。新增参数profile以及摘要必须进入原proposal/delivery指纹；同key换参数/降级/strip应冲突。

任何新OFFER/REOFFER/WITHDRAW/DECLINE/ACCEPT或直接DML都会改变epoch/摘要，旧预览或旧批准不得自动刷新、隐式采纳。A→B→A字段恢复仍凭单调trace/epoch拒绝。现有business_frontier五字段计划ID/revision/epoch CAS应继续用于所有新P3–P5及取消命令，不允许旧无fence请求在新ADOPT/P2后到达变成新plan授权。

## 同锁串行与事务回滚

原sd.offer/command/reassign均先parent UPDATE，再root锁；原deliver亦parent UPDATE。资格最终检查和anchor写入必须保持此顺序，禁止用只读preview锁当commit fence。ACCEPT先赢时：会产生receipt step/CREATE/ACCEPT和trace，新资格必须拒绝且不写新的资源/批准消费/anchor。closure消费先赢时：不允许原尚未terminal offer存在；后到旧ACCEPT会因已终态、dispatch revision、plan/epoch fence拒绝。

REOFFER先赢时必须阻断旧资格；closure消费先赢后，旧REOFFER请求因plan/epoch不匹配拒绝，合法新计划的重新GET+显式OFFER可按原门办理。新WITHDRAW不能隐藏新offer后的旧摘要变化。任何后半事务失败、sourcelease过期、撤权、current target变化、容量/Case锁后不一致都要整事务回滚：hold确认、approval consume、link/receipt/nativeanchor应全无新增；原P3历史及原资源占用保留。不得修改原锁超时/有限重试预算来“通过”。

## 历史容量和计划路径

原dispatch总revision上限64跨ADOPT保留；fresh plan不创建空dispatch代。若要继续新plan OFFER+ACCEPT，旧terminal revision需<=62（offer原拒>=63；ACCEPT原需<64），否则应资格/预览明确拒绝历史预算不足，不能批准后承诺可办。原resource holds/combinations/claims/links全部保留，不自动释放或复用已占容量。

source变更仍走原fresh full ADOPT（新plan/steps UUID、六目标及P1–P5全保留）、原P1 VERIFY、原明确新APPROVE与原资源事务、P2 VERIFY；后续P3/P4/P5各自原人工命令/VERIFY，不自动验证或由closure暗示Case完成。现有complete-five和KNOWN_NOT_STARTED两路径不可退化，新scope不支持的tail活动/owner metadata/current UNKNOWN一律原门拒绝。

## 新消费锚与冷GET

当前native anchor beforeguard是epoch0/八表空，只能扩展为精确profile分支，不能把旧guard改成“零或任意正数”。新锚需实际消费时positive epoch+完整terminal摘要，DB门独立检查真实closed/noACCEPT/后五无effect，并通过原deferred SQL binding关联同事务实际link、receipt、APPROVE、previous/newplan、请求fingerprint及资格摘要。

后续合法新OFFER/ACCEPT会改变当前root、marker、receipt/P5表；冷GET应核原消费锚和原批准/immutable link历史，保留COMMITTED与原receipt字节，不重用live closure资格拒绝历史，也不能把historic=True跳过当前表后伪造曾经closed。当前readiness可NEEDS_RECHECK，不能改写原采纳事实。未知/损坏anchor、指纹或ledger要拒绝；所有GET不写回/不重发dispatch/不自动撤回或重新批准。

## 冻结后建议最小实际证据（本轮全部NOT_RUN）

真实原OFFERED→quote拒绝→当前specialist原WITHDRAW→完整closure资格→fresh ADOPT/P1→明确APPROVE/交付/P2→新合法REOFFER/ACCEPT→后续原VERIFY，并在新业务开始后冷GET原receipt稳定。另DECLINE正向、多代DECLINE/WITHDRAW、旧迟到ACCEPT/REOFFER/WITHDRAW、ACCEPT与commit竞争、后半rollback、删行/改行ABA、超64历史、分页溢出、raw-null历史fence、profile strip/downgrade、撤权/源withdraw/目标失效、同key异摘要与丢回执冷GET。沿用原命令/解锁规则、完整受影响回归、冻结独审及公开归档；Windows/正式AT/真实模型/生产/通用旧prep迁移等既有未执行缺口保留。
