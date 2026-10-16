# P3 从未接单且已明确收束：独立执行前合同

基线实际 `c6f0771f92b585829bda1e7496aee98945e6877d`。本文件及32行 oracle 是**设计/静态调查，实际测试0**。仅新 `p3-closure-oracle` 可写；旧十根封存、共享源码/Git不写。接口尚待后端稳定快照，不能把本文件当实际PG/HTTP通过。

## 最小资格与独立身份

新profile精确 `P3_NEVER_ACCEPTED_CLOSED_V1`，qualification schema1/state `CLOSED_WITHOUT_ACCEPTANCE`，compatibility schema3；原整替换14字段绑定保持。新资格与原 `KNOWN_NOT_STARTED_V1` 分开，不复用其epoch0规则/消费锚点；监测出生及八表DML可复用同一原子签发的原监测子协议。安装必须在preparation出生前一次原子完成base+closure schema及原Approval前置DDL，之后固定OID/owner/完整trigger/function/constraint/xmin身份，无backfill或resnapshot。

原P1/P2真实完成（原VERIFY事件/来源hash/旧明确批准COMMIT/link/CONSUME/容量锚点），P3存在完整OFFER/REOFFER历史、任何时候都没有ACCEPT和receipt_step_id，P4三表与P5两表完整零结果且永久marker也无此类操作。marker epoch必须真实大于0，ever_started必须true，原完整事件保留，不删除/清空/伪造“尚未开始”。缺birth、部分查询、溢出、未知/矛盾历史均UNKNOWN/拒绝。

根明确允许两个已知终态，**分别证明**：DECLINED是原当前执行者DECLINE；WITHDRAWN是原assigned specialist WITHDRAW。OFFERED没有被收束，必须先用户以原当前授权/原五字段fence明确WITHDRAW。不能自动撤回、把DECLINE改名WITHDRAW、把UNKNOWN当已闭合，不能用补一条伪历史凑资格。无P3历史属于原独立zero路径，不属于本profile。

## 事件、DML、摘要与fence全链

P3 root唯一绑定prep，所有offers和events必须完整重放到root.revision，revision1开始无缺口/重复；头指针指向最后真实offer。首事件OFFER，后续REOFFER须前offer真实DECLINE或WITHDRAW；各offer只从OFFERED进入其原终态，从不ACCEPT。现限定闭合revision偶数2..62，完整历史有界64，保留下一REOFFER/ACCEPT预算；不足不得扩原64/4096限制。

每条原事件验证actor/executor/action/state/offer/root/preparation语义、request_key、原输入fingerprint、payload和原捕获的五字段BusinessFrontierFence；必须从真实历史重建，不能用当前fence或材料状态填历史。summary q精确19字段，dispatch摘要8字段，event摘要10字段（后端已声明，独测用literal集合核对，不直接导入实现常量当oracle）。事件摘要、payload SHA、marker SHA、birth/protocol/oldplan identity必须进预览、新PROPOSE、明确APPROVE、COMMIT与最后事务重验。

永久marker中的每条table/op/record_id/transaction必须与原实际动作对应。按当前源码的静态有限SQL预期：OFFER/REOFFER及DECLINE/WITHDRAW每一事件对应root/offer/event三类DML；首OFFER计数尚待实际PG trace核实，不能凭常数调整通过。所有实际DML必须有来源解释、正确顺序/同一事务和真实行xmin；拒绝events UPDATE/DELETE、遗漏/重造、P4/P5历史即使当前行被删空。具体trace oracle要在合法原命令实际PG原件上预先核定并保留失败，不仅做`epoch>0`判断。

## 可达的事务顺序与原父锁

原P3 OFFER/REOFFER/ACCEPT/DECLINE/WITHDRAW均先prep UPDATE，root/offer再写；新资格/批准/交付亦须相同父锁内读完整摘要并最后重验。旧key同指纹重放只能返回原事实，不能再增加epoch；新key业务必须当前fivefence。原source/authority/时钟/资源规则仍动态核验。

必须分别报告以下**真实可达阶段**，不拆原gate制造同一已批准状态的双胜者：

1. 原旧P1/P2当前且OFFERED时，executor ACCEPT先获得原父锁：真实接单/CREATE receipt保留；reviewer WITHDRAW旧fence409；后来closure资格拒绝。反方向先WITHDRAW：真实闭合、无receipt；迟到ACCEPT409，fresh closure资格可成立。
2. 原旧closed且旧P1/P2仍当前时，fresh REOFFER先提交：状态重新OFFERED，资格拒绝；须再原reviewer WITHDRAW，新的事件摘要/epoch变化，旧proof不能消费。
3. fullADOPT/newP1之后但newP2未核验时，原REOFFER受gate2拒409，这是正确边界；不能用ownerSQL构造“合法REOFFER赢新批准交付”。闭合head上的ACCEPT本来也是409。
4. 新closure COMMIT/P2之后，旧捕获fence/旧plan意图迟到应拒；fresh newplan GET及用户明确REOFFER/ACCEPT可办，旧资源/receipt及闭合prefix保留。

至少对第1项做两方向真正PG等待：owner观察连接持原prep UPDATE；先启动指定winner原HTTP请求，观察pg_stat_activity/pg_blocking_pids证其确在父锁排队，再启动other确认排队，立刻释放锁。两请求的body/fence分别来自原真实角色GET、同fence、不同key，不伪造actor或值；原3秒lock_timeout不改。同步观测本身不修改产品函数/查询结果或权限。任何Deadlock/timeout是失败且保真，不能吞为PASS。串行两事务/控制队列与其他强并发范围明确分列。

## 真事务回滚和历史冷读

原P3 `_event`写事件/marker之后调用 `dispatch_notices.enqueue`。可在不属于已固定tracked schema的dispatch_notice_outbox放受控owner测试故障trigger，在真实原OFFER/REOFFER/WITHDRAW后置阶段抛错，核所有root/offer/event/marker/outbox与原批准/资源效果回滚。须先确认新protocol固定schema未纳入该outbox；若已纳入不能停用guard或resnapshot逃过门。原组合确认/link/CONSUME及独立closure消费anchor也必须原事务整体回滚。

消费资格必须绑定真实持久独立anchor和原link/receipt/Approval消费，不只保存可重哈希JSON。历史读取验证当时已闭合的原prefix，不要求当前root仍是旧terminal；新REOFFER会合法更改root.current_offer_id/revision，新ACCEPT生成新receipt，不应抹旧消费事实。old resource-delivery original-key GET、ApprovalGET及新协议历史验证须在新P3/P4/P5后仍保留原receipt，完整数据库快照证明读操作未写；当前read撤权仍拒。

原P3只有专门reassignment-recovery GET，强制PENDING_MANUAL_RECEIPT，不能用它为普通OFFER/WITHDRAW伪200。若本轮不新增通用P3 key恢复，应把该缺口明示；原resource-delivery/key冷GET确实可测，不把POST重发或当前view当key恢复。

## 范围与执行层级

fixture接口为新 `tests/p3_closure_fixture_support.py`：closure_case indirect action/cycles/stage，build_closure factory，old_p2/offered/closed/new_adopted原合法阶段；所有输出通过 `P3_CLOSURE_ARTIFACT_ROOT` 重定向新oracle根，不能执行旧frontier/replacement硬编码输出fixture。源码import根/哈希及真实PG issuer验证后再按根授权有限运行。纯字典变异、owner SQL故障、直接PG组件资格、TestClient ASGI、native HTTP、真浏览器分别记账。32设计行不可相加为实际测试或宣称32PASS。

正向新计划仍原六目标/P1-P5、五次真实VERIFY、明确新批准/原资源事务和P3-P5业务，到LOCAL_OUTPUTS_VERIFIED与recorded_states_only工作清单；不是正式Case履约。旧人工决定/锁/历史和CONFIRMED容量不得自动释放或改写。原完整五VERIFY与zero前沿路径各自保持，当前target来源撤回/UNKNOWN/破坏性不能靠新profile复活。

Windows、广覆盖浏览器、正式AT、专用PG27、真实模型、正式治理/履约、生产、一般在途迁移/备份恢复未执行。新旧角色/权限/凭据/模型调用/部署/费用不新增。
