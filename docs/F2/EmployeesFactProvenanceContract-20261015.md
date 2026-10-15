# 员工人数自述断言：注册历史来源与影响合同

基线 `6dad1e3d6220f4b1a0711afd851ccd8e8b95343d`。本片只细化原事实用途 `SERVICE_PREPARATION` 中已明确选择的 `employees`、`USER_ASSERTED_SYNTHETIC` 来源；不重复双槽材料确认，不做语义推理、真实性认定或任意动态图。

before/current 各自由原 VERIFY/ADOPT 注册描述符的 decision_ref、decision_sha256、source_sha256 精确定位原事实确认事件及原快照。校验完整事件/快照 hash、同 owner/tenant/Case/Run/服务绑定、原 Declare/Confirm 指纹及实际 preparation_events 回执，选择必须唯一对应原快照的断言 ID/revision/fingerprint。严禁从当前事实补旧记录；缺失、损坏、类型不符、重复或不支持的来源明确 UNKNOWN。

细节点仅展示不含值/摘录的断言引用、版本、来源引用摘要和原适用 UTC 时间，保留 USER_ASSERTED_UNVERIFIED。完整值继续由原事实页面的字段权限控制。节点和已有聚合来源分列；已选行不变不代表整体来源不变。原事实确认会更新 preparation revision，可能使 P1–P5 全部受影响；分区始终沿原来源比较与原步骤依赖。资源、回执等其余来源保持原语义。

新路径显式选择固定 employees provenance scope；原请求缺该扩展时指纹及旧协议保持。采用仍走原计划 ADOPT、机会证明、UNLOCK、业务补正和 VERIFY。增强 source-change proof 独立 version3，旧 source-change v1/v2、typed graph schema1/build_v1、MANUAL v1/v2及双槽 v3 保持冻结原义。只在新路径保存不含事实值的 provenance 与历史回执绑定摘要，历史重建使用原注册 before/current 与对应的原账本前缀，不能按最新选择重新解释。

新预览及最终复读绑定当前 actor、Case/Run/plan/revision、机会代次、原来源 epochs，以及新增事实账本/回执行代际；撤权、迟到、ABA、失效、撤回和 UNKNOWN 均拒绝。新路径缺完整历史时全 Case unknown、preserved=[]、不提供可采纳动作；不能偷偷降级成已知聚合。已有 MANUAL/双槽或模板组合在未建立本片兼容合同时拒绝本片增强路径，旧默认路径继续原规则。

本人仍须原事实用途明确确认，再单独 ADOPT 与必要 VERIFY。丢回执用原冷 GET，不自动重发；幂等异参拒绝。保留原六目标、P1–P5、稳定 UUID、历史与未影响锁。来源投影和本人确认不产生新事实、Case 正式完成、Approval 或发布权。

字面 oracle 是设计输入，实际执行分列；已知影响/保留与 UNKNOWN 分开验证。完成原 HTML→HTTP/ASGI→自有 PostgreSQL 正反例、冻结源码独测/独审及完整受影响回归，保全失败原件后正常推送开发分支。Windows、真实浏览器、正式 AT、人工语义、真实模型及生产未执行；不改 main、不强推、不部署、不新增费用/凭据/安全权限，不绕访问拒绝。
