# 初稿实现独立静态审查

**STATIC_BLOCKED_PENDING_FIX_AND_RUNTIME。** 本阶段没有运行测试/PG/Git/浏览器；以下是源码控制流与证明检查的静态结论，不能记为实际pytest FAIL或运行复现。12个初稿源码/测试快照保存在`draft-static-source-snapshot.json`，不覆盖实施前合同报告或任何旧签署记录。UI未完成，不作为成品签收。

## 必须修正

- **HIGH — 合法终态64的原key恢复被容量门拒绝。** 在新模块`_source/recover/command`，合法61→REQUEST62→全已知RECONCILE63→CONFIRM64之后，公共`cc._source`追加LOCAL_HISTORY_LIMIT_REACHED；新GET恢复和同参POST都要求所有blocker/issue为空，所以已提交终结原key会409。应区分新动作容量与历史证明损坏；完整合法终态64保留可恢复性，写容量仍严格。需要owned PG完整正例及三动作原key在终态后的恢复。
- **HIGH — 历史snapshot顶层字段未与真实immutable source完整绑定。** `_record`只对比request.expected_preparation_revision和snapshot顶部同字段；`_phase`只比较immutable_source_sha。保持真实immutable prep7，把顶部和原request改为prep8、重算source/fingerprint与后续prior摘要，现比较可一致，虽不是合法CAS来源。需要按真实base/immutable、每事件之前local版本/阶段/cycle/prior摘要重建完整snapshot，canonical精确比较；全字段类型/形状和初始local head也要重验。此处仍是静态推演，不冒称已POST成功。
- **MEDIUM — 历史阶段未重验原容量前置。** `_phase`没有重复REQUEST原expectedlife<=61及revision62时UNRESOLVED不得消耗终结槽的规则。损坏/rehashed记录可能被当成原本合法的已提交阶段。与完整source重建一起补验；同时保留合法最后槽终结恢复。
- **MEDIUM — local lifecycle读仍可能展示可校验。** `case_lifecycle.py:129`的can_write仅排除CANCELLED。合法RECONCILING、原ACK/资源/资料满足时can_revalidate仍可true，POST已被新guard正确拒绝。所有业务动作投影应使用冻结态门。当前P1 read clamp已静态观察改为case_write_blocked；仍未跑投影测试。
- **MEDIUM — 继承建单来源的whole Run.input损坏可500。** `case_cancellation._source`捕获Intake验证失败后仍对成功Run的input直接.get；None/[]/数字/字符串可能AttributeError。应先验证dict形状并保持原指纹/建单回执拒绝。需要旧/新入口的明确blocker和零写检查。

## 已确认的静态方向

专用owner账本不会通过原ACK/REQUEST_CHANGES/REOPEN产生履约或计划写；default no-receipt helper边界保持。所有历史SUBMIT/企业决定按原模型重建指纹，检查payload精确键、严格类型、连续revision、状态机、当前指针和正文SHA。请求/核对/终结使用原parent→key→dispatch→Case→local序列，事件与双状态同事务；原receipt_parent在replay前使用冻结守卫。两个计划inspect和两个rollback后persist_rejected_observation都已纳入RECONCILING写冻结。schema032沿原票据/真实owner/transaction/table保护，只扩现CHECK，无新业务权限。独立资源释放与成功Run/历史事实保留。

后续独立探针应覆盖上述边界、全世代/来源形状损坏、原key在合法后续阶段恢复、元数据冷GET零写，以及不可信绑定的原回执投影不泄露其它范围内容。根正在运行的12基本用例不计入本独审成绩。独立实际PASS/FAIL/ERROR/SKIP均0，TESTS/PG/BROWSER为NOT RUN。原Case_count0根因依然UNCONFIRMED。
