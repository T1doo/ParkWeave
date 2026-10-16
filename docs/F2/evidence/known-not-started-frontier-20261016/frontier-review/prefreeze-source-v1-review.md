# source-v1 集成前冻结独立静态复核

范围：HEAD仍c2263edd开发DIRTY态；读取main产品及source-v1，12/12文件SHA与backend manifest相同（记录prefreeze-source-v1-check.json）。没有测试或CPUprobe，没有改src/tests/Git/旧roots。本结论不是冻结批准。

## Blocking A：遗漏旧取消迟到意图栅栏

`case_cancellation.py:16-25` 的Cancel DTO未含business fence；`_source:87-94`只含prep/material/case/lifecycle/dispatch/run/service，不含service_case_plan/generation/epoch。`cancel:159-178`重放后直接校验旧source并_commit。

攻击：旧计划P1/P2后生成before-first-accept取消请求并延迟；新frontier替换消费、newplan完成P1/P2后，如果prep/material/case/run/dispatch/lifecycle原值未变，原取消source仍相同，可写cases CANCELLED和P5 lifecycle/events。追踪触发器只能留下epoch，不能证明新计划意图。可选择新协议prep拒绝所有新取消（先保留原已提交同key重放），或把该入口完整纳入捕获CAS。旧默认路径保持。

## Blocking B：新增None字段破坏原取消历史指纹重建

- `case_cancellation_before_receipt.py:54-55`构造sd.Command后直接model_dump；新增expected_business_frontier默认None会被序列化，而实际dispatch.command用frontier_request去掉None，原ACCEPT fingerprint因此不等。
- `case_cancellation_reconciliation.py:78/87/93`构造er.Command后同样直接model_dump，破坏原receipt事件指纹重建。
- 同文件`:147-151`构造lc.Command后直接model_dump，破坏原REVALIDATE前缀指纹重建。

这是原默认路径回归，不依赖新协议开启。必须以统一原字节helper重建，并对有fence的新历史精确携带原payload fence；不能把exact指纹/原extras校验改成忽略。新fence字段在before_receipt原extras里也会被视为handoff字段，需明确新协议取消范围，不能默许可用。

## 已解决的原静态阻断（仍待实际验证）

七DTO显式捕获generation/preparation_id/plan_id/plan_revision/epoch，request helper保持旧None不入指纹；主七入口在原重放后新写前校验，GET提供捕获值。receipt.command tracked父UPDATE在step UPDATE前，legacy仍原SHARE。八表DML追踪、prep不可回退birth/marker、TRUNCATE拒、完整19 frontier triggers和全部原trigger/constraint catalog固定、Approval原schema-only预装方向正确。

消费前后精确重建live qualification；原BEFORE anchor要求marker0/八表空，不可裁剪/同次marker变更；deferred trigger关联actual immutable link/combinationreceipt/approval binding；历史通过native append-only anchor读取原qualification而非再造current0。代码上原历史和当前业务状态已区分。本轮未验证真实SQL/并发。

## Scope限定，不作为额外superuser防护要求

_catalog固定9表全部trigger/constraint含OID/xmin及函数定义，不包含pg_inherits/relkind/relispartition。普通owner CREATE继承子表不会复制parent触发器；子表INSERT/DELETE、再DROP可能不改被固定catalog。当前contract已明确不可检测的owner create/drop/rollback DDL在可信owner连续性外，因此不可报告“所有DDL历史均可检测”。若允许未知继承/分区schema进协议，至少当前无继承/分区需拒；不能靠系统目录fabrication外界限替代此普通DDL边界说明。

剩余验证：后续修正版精确冻结独审；迟到OFFER及CANCEL、原取消/对账全模块、真实P4并发、八表DML删除ABA/DDL/TRUNCATE、历史COMMITTED在新合法P3后稳定、HTTP/Chrome与完整受影响回归。Windows/正式AT/真实模型/生产等原缺口保留。
