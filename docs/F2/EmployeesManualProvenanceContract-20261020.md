# 员工来源证明与MANUAL说明：窄兼容

基线 `d974ecb39170f091362d8de07f1fc0bab75200da`。原F3-T02/T03组合原先有意拒绝，本片新增显式 `EMPLOYEES_USER_ASSERTION_MANUAL_V1` 请求scope与 `EMPLOYEES_MANUAL_PROVENANCE_PREVIEW`，保存source-change version5（v4已有统一传播用途）。原默认v2、原employees scope/v3及note v1/continuation v2均保持原义；不删旧组合拒绝门。

fact_provenance独立复用原v1：原VERIFY/ADOPT注册的before/current descriptor各按其原账本前缀、原断言与确认回执重建，不按当前facts补历史，仍为未核实用户自述，不公开额外事实值。manual_provenance v1另存当时唯一P1 MANUAL的完整note（包括全文、原source_ref/source_package）、最新note决定事件引用/指纹/proof SHA与note历史前缀摘要。计划原owner_amendments、事件、业务产物不改写，不把M变SOURCE或当成事实。

preview在当前plan revision构造manual证明；历史校验在目标ADOPT前一revision重放原plan note事件，原validate_plan_history与opportunity双向链接核对当时M，绝不用当前owner_amendments代替旧M。先独立严格验证fact/manual与封闭version5字段，再在深拷贝只移除已验证扩展并归一v2交原冻结validator；不清owner_amendments、不重写业务历史。

仅支持已有普通MANUAL/v1及精确原文继续v2。不支持SOURCE note、partial、template_migration、统一dependency_scope组合或已启用material_package_continuation的v3确认协议（普通MANUAL本身保存双材料来源包不代表启用双槽协议）。历史一旦有v3 package active仍拒绝，不只看最新origin。未知/损坏/跨时点/额外字段/非整数版本全Case UNKNOWN，preserved空，无adoption。

原build/adoption_guard的所有锁、权限、来源、容量和人工冲突blockers保留，影响分区不缩小。受影响锁必须原UNLOCK；KEEP_MANUAL/DEFER仍待处理；源冲突须原KEEP_AND_CONTINUE/MERGE_NOTE，后续任何编辑须重新明确继续，即使原文条件仍全。新preview不替代原ADOPT、补正/专员审核/企业确认及全部受影响VERIFY。最终复读沿原actor/Case/Run/plan/card/epochs/fact ledger与真实回执行代际，权限/来源ABA、撤权、陈旧编辑拒绝。幂等异参、原冷GET与未知结果不自动重发沿原协议。

页面增加独立明确员工+人工说明预览按钮，分别呈现原/当前员工来源和当时MANUAL全文；仅在当前scope/人工摘要完整匹配后才允许原ADOPT。旧按钮和默认协议不变；身份、事项、草稿与迟到响应隔离保留。

验证先保留原组合拒绝与新入口需求FAIL；实际owned Linux PG/API验证显式采用、原M/历史不变、锁/继续/编辑/KEEP/DEFER、冷恢复与幂等、权限/来源ABA、原注册历史不可补造、package/template/旧v3拒绝，及真实业务补正VERIFY。当前SOURCE/事实证明不代表现实履约。独立设计/源码/数据库审查、相关模块与精确collection分列，不拼数字签整体。只原Linux临时合成夹具，不做Windows owner/DACL/原生026–032/roles/seed、真实模型、费用/凭据/权限、main、部署或用户电脑操作。
