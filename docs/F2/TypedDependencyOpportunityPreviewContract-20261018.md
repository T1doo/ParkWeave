# F3-T03 原机会卡类型图只读接线

基线 `9be4788bb068eeead64cda2f7a4eb70099a4df4f`，父级对该内核有限独审通过后接续原§8。只将原已有当前来源接入已审内核；不实现新图引擎或开放新authority，不签整体AT25/26。

沿原 `GET /api/preparations/{id}/opportunities/{card}/plan-revision`，显式 `dependency_scope=BOUNDED_MULTI_SOURCE_V1&graph_preview=VERSIONED_TYPED_GRAPH_V1` 请求附加只读 `typed_dependency_preview`。旧请求和原 `build`/v2/v4 change/hash/ADOPT证明保持；新投影只在 `read` 原事务内、当前owner/READ/PREPARE/同Case及当前机会卡和原计划证明核对后生成，不进入任何写请求或历史。

只读薄适配调用原schema2→`dependency_graph.from_unified_v1`，保留每消费者observation、旧图hash、原/current快照及确定/不确定影响、保留/删除和版本路径见证。原schema2不含锁，当前有效人工锁另由原 `_manual_lock` 读取核验、与受影响步骤相交展示；不把当前锁倒填为历史锁。绑定当前actor/资料/Case/Run/plan/revision/卡片/账本/旧preview和来源epoch；没有客户端图上传、发现关系或补造来源。

原机会卡新增一个只读按钮；原统一传播预览及旧ADOPT按钮/证明路径继续原行为。新按钮复用原页面机会/计划代次、身份/草稿/导航守卫与当前403清屏，独立显示只读结果且不设置可采纳的 `opportunityPlanView`。新投影只用textContent，哈希、精确绑定、集合分区与路径引用核验不另写传播算法。每次await后重验上下文，迟到200/403/JSON/运输失败不能覆盖后来的身份/Case/计划；无存储正文/token/图或自动重发。

定向验证实际自有SYNTHETIC PostgreSQL/原HTTP-ASGI及原完整HTML NodeVM，明示非浏览器。核当前来源变化、共享观察未变消费者、UNKNOWN、当前锁与历史、冷新API仅GET、当前撤权/跨角色scope、只读业务/权限快照、坏/自洽重hash DTO及迟到/ABA；精确证明旧请求/hash/ADOPT保持。保全所有失败、按冻结分窗计数，不泛跑全仓。禁止浏览器/root/seal/发行、真实模型、身份/Grant/分派/目录发布/批准/凭据/费用或部署；Windows与真实业务仍未验。

页面计划上下文沿原 command-recovery 的 NO_REQUEST/current 只读投影取得，避免普通计划 GET 的 invalidated 观察写。该投影有意去掉 source/verified hash：客户端只核当前锁布尔、最后 LOCK/UNLOCK 的事件与步骤身份，以及本次锁摘要格式；完整锁来源、actor 和核验相等证明仍由服务器原 `_manual_lock` 校验，摘要不构成认证。
