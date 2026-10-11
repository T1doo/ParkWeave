# 已有人工回执后的取消请求与核对：实施前独立静态审查

**STATIC_REVIEW_COMPLETE；合同方向无阻断。** 已完整读原设计§5.5、7.1、7.4及持久事件/幂等上下文，核对F2当前取消交付与原回执/材料合同。父任务所报合同commit `4416a3b`，文件 `docs/F2/CaseCancellationReconciliationContract.md`，SHA256 `a2302d0f69dd20932d78cd21aa64099ddb9a19a273641d715eab61343930c9b4`。基线交付 `189379b7f7c94dfacfff697ad06a4ea1a5780048`，产品源码 `3fc6fa712f14820d88fcf8cd94fa70fcf6120e0c`。本阶段只读，未操作Git；当前内容hash是静态观察，不是最终实现冻结。

三动作契合原设计：REQUEST_CANCEL明确记录意图且Case/local即RECONCILING；专用owner RECONCILE逐全部已证明人工回执核对KNOWN_LOCAL_RESULT/UNRESOLVED；CONFIRM_CANCEL再次明确确认、精确绑定最新all-known证明才原子CANCELLED。即便原回执已ACK也不自动推进。建单Run仍SUCCEEDED，人工合成回执不被抹除、不证明外部履约；资源保留且按原权限独立释放。§7.1未列完整Case RECONCILING谱系，但本片用户明确授权有限本地阶段投影，合同明确不签完整生命周期，因而没有原设计冲突。

## 必须落实的实现规则

1. `preparation.case_cancelled`应继续仅表示终态CANCELLED；另设冻结谓词覆盖RECONCILING/CANCELLED，避免“请求中”展示成“已取消”。旧业务守卫覆盖内部执行者/receipt父级、composition及原key replay，不能把所有FOR UPDATE读取当业务写。
2. 专用核对账本不走原receipt ACK/REQUEST_CHANGES/REOPEN。原路径依赖current_step、当前资料/P3门、当前executor权限并invalidate(4)，无法代表全历史核对；请求后全部冻结。历史owner核对证明精确原actor/event，不应要求旧执行者当前仍有活跃Run权或重绑旧步骤。
3. 共享manual lineage的默认no-receipt边界保持；新私有allow分支必须证明全部OFFER/REOFFER/ACCEPT/CREATE扩展一致、后来世代非空前驱，逐回执对应准确SUBMIT指纹及正文SHA，并重放企业决定的typed payload/连续revision/状态/当前指针。裸回执行、孤事件、重复/遗漏、布尔revision、non-object和历史adapter/managed来源拒绝。
4. REQUEST/RECONCILE旧key可在合法后续阶段恢复原事件与当前head，须验证完整因果链，不能复用旧terminal helper的`local revision == old revision`约束，也不能用历史事件复活写动作。同key异参/跨action/scope拒绝；丢响应仅GET原key，NOT_OBSERVED仍UNKNOWN。
5. 64条local ledger上限须预留核对和终结的合法容量；重复UNRESOLVED核对不能把最后可收束槽用尽。明确全历史大小及payload上限，不用LIMIT截断历史后声称完整。
6. `controlled_plans._inspect`和`service_case_steps._inspect`以及两处`persist_rejected_observation`都要在冻结态禁持久失效写，包括业务回滚后的独立metadata事务。历史投影可计算变化，不改原计划。资料/计划/资源依赖只给有权head id/revision/SHA，不泄露已撤权资源正文。
7. 服务端receipt/read/list/dispatch/notice和原页面区分RECONCILING/CANCELLED/writes_frozen；所有旧动作不可用。相同Case身份/代次/版本的冻结状态保持，迟到旧GET/POST/通知不降级；三个阶段分别明确操作、原入口/key恢复，不保存正文/理由/认证值或自动KNOWN选择。
8. 原成功Run、资料、全部步骤/ACCEPT/CREATE/SUBMIT/企业决定、关联、预约和容量不改。独立释放沿原资源锁和当前权限，可改变预约状态；不宣称与Case取消一体原子，也不因此重绑历史或隐式失效计划。
9. schema32仅既有CHECK有限增项，原创建票据/当前owner/事务/表所有权守卫不变。普通handoff保留29前置并明确允许32；installed wheel要含032；旧版本rollback夹具和未来33反例要保留原严格拒绝，不通过放宽迁移来修测试。

锁序按合同parent UPDATE→case-local原key advisory→dispatch→Case→local至提交；旧receipt命令共享parent SHARE，先提交者决定源版本。请求先则旧SUBMIT/ACK等包括原key回放拒；旧命令先则旧request source SHA拒，要求刷新明确确认。专用核对与终结也串行，event失败各阶段全回滚。

机器报告列12项具体风险/源码锚点及后续PG/ASGI/offline Node验收矩阵。本阶段**测试、PG、浏览器均NOT RUN；PASS/FAIL/ERROR/SKIP均0**，不是新功能签收。原浏览器管理员拒绝不重试，旧Case_count0历史根因保持UNCONFIRMED，不冒称权限修复。产品/测试/docs/Git写0，所有已签署旧报告原样保留。
