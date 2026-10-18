# 原资源查询集合及成员的版本图适配

基线 `f522b6bfb4080d1fc557f1695dd6c909a61bda80`。父级有限接受上一片后，接原§8/F3-T03/AT25–26：本片必须从已有实际来源构图，不能只转换旧schema2。仅只读资源影响；不改旧ADOPT、P1–P5/六目标、来源算法、目录/批准/provider或执行权限，不签正式AT/真实业务。

## 原件边界

原 `registered_dependencies.collections` 资源集合只保存 `known/count/sha256`，原始查询行不进历史。原P2 VERIFY或明确来源修订的 `resource_rules` 与 `resource_grants` 已保存被选资源的原字段。复用 `evidence_sources` 与原history验证，按原查询字段和排序，仅从这些历史原件重建能证明存在的active授权行；重建行数、hash与历史resource_collection均精确相等且原known时，才认定旧成员全集。否则仅保留有原件的部分，collection.complete=false、明确UNKNOWN；绝不从当前行补旧规则/授权/成员。inactive=false不能证明旧行存在，不凭它重建行。

当前数据沿原owner/READ/PREPARE、同Case/Run/计划/卡片事务读取；新查询只读取当前具有active READ的同园区/组织资源原始规则及原查询授权行，不读取其它主体或当前无权资源详情。字段/排序沿原有界资源查询。当前可见行数/hash也须匹配原本次collection stamp才认定全集；被遮蔽或不完整保持UNKNOWN，不把截断集变known；超过读取/图界限准确409，不返回截断成员图。当前来源epoch在新读取后复核；变化准确拒绝409，不自动重发。历史仅用当前仍有权读取的原Case核验原件，不从外部恢复未授权记录。

## 图和差异

新增薄适配调用已审 `dependency_graph.snapshot/preview`，不修改内核或另写传播算法。稳定资源节点 `resource:<原UUID>`，查询节点依owner/park/org/query_version稳定，scope绑定原plan；每成员有原始字段/授权行指纹。查询CAPACITY_SNAPSHOT保存成员指纹、原集合stamp和complete语义；实际成员→集合→原P2的CAPACITY边，原计划依赖用PRECEDES传播到相应消费者。原P1及未达步骤保留；本图只说明资源查询影响，不取代其他来源的完整Case预览。最多96资源成员、原查询最多256行（第257检测溢出），超界不返回伪全集。

明确before/current、确定/不确定影响、路径见证及成员差异。只有前后全集均可证时，成员新增/移出才为确认差异；否则分别列“当前新见／不再观察，不能确认新增或删除”。移出只表示原查询集合成员关系变化，不宣称物理资源删除或释放预约。原人工锁仍由 `_manual_lock` 校验、当前锁冲突单列，历史不倒填；未知只沿明确资源集合范围及实际下游扩大，不静默重写内容。

## 接口与页面

原机会 `plan-revision` GET新增显式 `graph_preview=RESOURCE_QUERY_MEMBERS_V1`，仍必须同时 `dependency_scope=BOUNDED_MULTI_SOURCE_V1`，拒绝多余/重复query。原未选项及 `VERSIONED_TYPED_GRAPH_V1` 响应/证明保持；新模式沿原read加 `resource_dependency_preview`，旧 typed_dependency_preview和旧v4证明保持。新字段不进build、ADOPT或历史，无客户端图上传、新写入口或快照仓库。

升级现有只读类型图按钮以显示本次资源细粒度部分，复用原身份/代次/callerCurrent/草稿/403清屏/迟到守卫、只读command-recovery上下文及旧ADOPT清除/隐藏。不增加另一套旧预览。页面只检查binding/hash/节点成员/路径引用和边界，不重算传播闭包；新内容仅textContent，无正文/token/图落localStorage。

## 最小有界验收

1. 字面原件覆盖：完整历史精确复证、插入/移出/规则修订、只有摘要或部分原件、false授权不当存在、排序/重复/数量界限；断言稳定ID、集合指纹、明确路径、P1保留和P2及实际下游影响。
2. 少量原HTTP/ASGI/自有临时SYNTHETIC PG复合场景：实际资源变化与未知历史、当前不可读资源不投影、拒绝scope与epoch变化、全业务/权限快照（拒绝审计另列）不变；旧query/旧hash逐项兼容。
3. 原完整HTML NodeVM的本片细粒度展示/无新增POST或普通观察GET、坏DTO及一次跨Case迟到/当前403保护；明示不是浏览器。独立oracle与少量自有反例，实际selectors/交集分窗结算，旧17/141矩阵不重跑。

不新增真实身份/Grant/分派/目录发布/批准/凭据/费用或安全网络权限；不真实模型、不浏览器降级、不root/seal/发行、main/强推/部署或未知进程/锁操作。普通provider与真实来源仍未接通，本片有合法离线实现范围，不能把缺代码归为必须等待生产权限。

P2适用边界：显式资源mode要求原plan已有P2，否则准确409 original resource consumer required。原typed按钮取得当前只读plan后，只有实际P2才请求资源mode；P1-only明确用原VERSIONED_TYPED_GRAPH_V1正常展示原图，不发资源查询，不虚构消费者，也不由资源API静默降级。

共同成员指纹也区分确认变化与仅观察变化：两端全集均可复证才列changed；任一端partial时差异仅列observation_changed，不能把历史缺少inactive行的观察差异称为确定规则变化。内核确定/不确定图影响仍各自展示，集合不全沿原资源范围扩大重验。
