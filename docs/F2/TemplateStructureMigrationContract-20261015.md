# 有限模板结构增强合同（2026-10-15）

基线交付：`aceb01d2351a695fa1358d91ea944615ba4a468c`。本片扩展原有限模板迁移；不宣称通用结构迁移或完整生命周期。原产品 V1 §7.5、§8 与 F2 原计划要求保持历史、显式确认、精确失效和不兼容拒绝。

## 允许范围

仅允许同 scope、service/version、参数 schema、registry/contracts 的前向模板版本，把已注册必需目标严格追加到原目标列表末尾。原模板步骤必须原样保留，新增闭包必须由既有注册编译器生成。新增模板义务、目标闭包必须已经存在于原 Case 的初始请求、原采用证明及不可变计划中；不添加或删改 Case 目标、coverage、步骤 ID 或依赖边。主正例为 Case 原已声明全部六目标/P1–P5，模板从 P1 增强至包含 P5。

结构分支要求原计划底层当前全部 VERIFIED；旧模板因目标版本发布而失去当前可用性不构成业务来源失效。尚未验证的原计划明确拒绝。既有权限、来源、Run、关闭/撤销、隔离与租户限制继续适用。

## 精确影响与容量

影响种子是新增模板闭包节点的 adapter 与新增目标映射 adapter 的并集，再沿原 Case 图取下游闭包。P1→P5 影响 P2–P5；P1–P4→P5 仅 P5；新增 P4 别名影响 P4/P5。若实际模板 source 同时变化，保守重验全部 Case 步骤。

仅影响步骤的人工锁冲突；保留步骤及其锁、来源 hash 不变。64 事件容量必须容纳一次采用、全部影响步骤 VERIFY 与所有现存人工锁的 UNLOCK；不足时零写拒绝。原同结构迁移合同不扩张。

## 显式确认、证明及恢复

原 Apply 的 11 字段、旧事件 9 键不变。新增 StructureApply 额外要求 expected_structure_sha256 与严格布尔 true 的 confirm_structure_change（整数 1 拒绝）；使用独立 `/apply-structure`。原 `/apply` 不接受结构变更。check.application 提供 structure_change、structure_sha256、requires_structure_confirmation。

沿用 TEMPLATE_UPGRADE 行为与原事务/租约/CAS；结构事件只额外增加 structure_change 这一封闭、版本化证明。证明从前后 release、初始 Case 请求/计划独立重算，绑定新增目标、闭包、影响/保留集合与不可变计划。source_changed 仅表示实际 source 差异。每个历史结构事件的证明 hash 仅累计到其影响步骤的核验来源；后续说明修订、多跳结构增强不得抹去旧来源，也不得改变未影响步骤的 hash。

同 key 同参恢复原结果、异参冲突；丢响应只 GET 原 key，不自动重新提交。热/冷页面均核验原请求与证明，结构采用前需独立明确勾选与原因。旧事件与原始历史读取保留，读取不得隐式写入。

## 验收与限制

真实 owned PostgreSQL 检验：六目标与原输出保留、精确重验、人工锁、事件上限、事务故障全回滚、同异 key 并发、丢响应恢复、撤权/跨租户、初始证明篡改、unsafe 结构拒绝及多跳来源累积。UI 只使用完整原 HTML 的离线 NodeVM/进程内 ASGI；不启动或重试历史被拒浏览器。独立实现、独测、独审均在私树；root 唯一共享写入及正常开发分支推送。保留每次原始 FAIL/ERROR 与实际 PASS，不提升为正式原生/生产验收。
