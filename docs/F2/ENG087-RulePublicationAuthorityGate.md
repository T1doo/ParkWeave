# ENG087：正式规则审核发布的授权前置

基线 `5822b0296060a36721d90aa85b5bb8d3ce4a2e6c`。本轮请求是正式规则审核/发布产品流程，不能将ENG086的合成材料准备度当作正式规则发布。状态 **BLOCKED_CURRENT_AUTHORITY_CONTRACT**：没有可复用的发布主体/能力合同，应用对现有目录没有写权限。未实现正向发布或冒称浏览器验收通过。

## 可复核的当前合同

| 层 | 当前事实 | 不能推出的权限 |
| --- | --- | --- |
| `permissions.py` | enterprise_operator有READ/CONTROL/EXECUTE/FILE_READ；其余三角色只有READ | READ不授予规则审核或目录发布；EXECUTE只结合现有可信动作/当前Grant使用 |
| `migration-009.sql` / `preparation.grant` | PREPARE和REVIEW_ASSIGNED；后者仅park_specialist当前获派事项，现有动作核对合成材料包 | 资料核对不是园区/组织目录审批权 |
| `roles.sql` | 应用对preparation_catalog、preparation_grants只有SELECT | 不能用当前app身份INSERT/UPDATE目录，不能写授权表 |
| `V1ServiceSpec` | publication只有DRAFT/REVIEWED_SYNTHETIC、受控Rule/Truth与SourceRef | 请求中的reviewer_id或reviewed标记不构成实际审批、发布或公开来源真实性 |
| `/api/contracts/service` | 认证后只结构校验，明确published=false | 不是发布API；没有持久审核/发布记录 |
| ENG086 readiness | 规则ENGINEERING_ONLY/DRAFT；材料人工核对可以TRUE | 资格仍UNKNOWN/NOT_EVALUATED、business_publication=false |

原设计《平台产品设计》§5.3/§6.2要求服务来源→候选→人工审核→发布及受控表达式，§6.2明确“审批权不从 ServiceSpec 文本自动产生”；§11要求当前授权、Case范围、服务发布所需能力、运行身份和当前Grant取交集。原设计没有给当前角色配置具体发布能力或批准/撤销主体。因此缺口同时包括产品代码和授权合同；不是把一条缺失API补上就能安全启用，也不是Windows/外部账号故障。

新增规则存储/迁移/API/审核历史/UI本身属于尚缺代码。让真实角色成为规则审核/发布主体、扩大现有资料审核能力范围、授予app对目录或新发布表的写权限、新增/修改实际Grant，都涉及真实权限变化，本轮不做。不能用preparations的可写metadata绕过目录只读，不能用owner或setup helper替应用完成发布。

## 可评审的最小流程（待授权合同，不是已实现）

先确定三个主体及范围：谁可提交服务规则来源/草稿；谁可审核精确来源版本；谁可发布或撤回哪个组织/园区的服务。是否允许同人审核与发布、谁批准这些权限、如何撤销与审计均由现有权威合同决定，本轮不默认指定park_specialist/resource_admin或新增角色。发布适用组织/园区、服务ID、有效区间和来源版本必须明确，不能由请求体自行扩大范围。

合同确定后复用既有V1ServiceSpec/Rule/Truth/SourceRef，引入独立版本化来源正文/摘要/来源日期/有效期与不可变内容hash，不把SourceRef指针本身当已核实来源。流程为DRAFT→REVIEW_REQUESTED→REVIEWED→PUBLISHED；REJECTED/WITHDRAWN/EXPIRED明确保留；具体状态枚举需随实现冻结。提交、审核和发布必须显式操作并绑定expected_revision/source_sha256；后端记录实际actor/current authority，不能信任客户端reviewer字段。审核不等于发布，发布不等于企业资格或最终审批。

修改形成新修订，不改旧来源/决定/Release。新修订须重新审核；旧发布版本是否继续适用由明确生效区间及撤回决定判断，不能把所有历史事项删成未办理。撤回使未来评估不可沿用该release，历史保留。评估绑定具体release/source/rule/material/事实版本与当前适用时点，变化后标STALE、当前UNKNOWN；未审核/未发布/过期/来源缺失/未授权事实/人工条件未决均UNKNOWN。公开规则发布也不能把用户自述从UNVERIFIED变成已确认资格。

数据库需为来源/规则修订、提交/审核/发布/撤回事件与不可变release提供持久存储。选择复用目录扩展或独立业务表需受原只读registry边界约束；任何实际app写权限启用应由已有获授权迁移/权限流程处理，不能应用自授。角色/范围/当前授权撤销和来源锁必须先于行版本CAS，幂等绑定actor/对象/操作指纹，重复恢复原回执；失败原子回滚，无未知资格副作用。

界面应分开来源、当前修订、最近历史决定、当前授权与发布适用范围；未具合法权限只显示必要读视图与阻塞原因。换身份或导航立即清空私有来源，迟到成功/错误不回显。刷新只读取当前状态和历史；不能因reload自动审核、发布、恢复撤回或判断资格。

## 验收与实际证据

正向验收矩阵待上述合同：已授权主体提交来源→另一当前合法审核主体审核→合法发布主体明确范围→当前有效规则被只读使用；并发版本/同key/丢响应重试、修改须重审、撤回/过期UNKNOWN、历史与刷新、跨tenant/身份/权限撤销零副作用、真实1200/390/320浏览器及独立全量回归。没有正向授权合同就不能伪造发布身份、演示mock正向结果或在真实环境赋权来完成验收。

本轮已执行真实隔离PG/API前置回归：28 PASS/0 FAIL/2既有WARN（13.95秒），日志 `.runtime/eng087-authority-preflight.log`。新增4个用例使用已有标准隔离夹具，不操作保留产品数据库：实际app SELECT成功但目录UPDATE被InsufficientPrivilege拒绝并且目录/Grant/Run访问/业务数据不变；企业与专员提交自称已审核的结构合同仍published=false/无写入；获派材料审核虽TRUE，规则仍DRAFT/资格UNKNOWN/目录授权不变。该成绩只验证拒绝边界，不证明正式发布产品完成。

新增边界测试及原功能在205份冻结源完整Linux回归 **1501 PASS/0 FAIL/9原生Windows SKIP/2既有WARN**（310.23秒），source hash0差异。产品src及权限文件与5822b029字节一致；完整回归不代表正式发布正向流程已实现。源/日志hash与缺口证据见[evidence/eng087-rule-publication-authority-gate.json](evidence/eng087-rule-publication-authority-gate.json)。

独立只读审查 `/root/frontend_demo_readiness` 同样确认无现成发布主体/API/目录写权限。最终独立核验日志/205源/前置测试/文档哈希一致，确认真实阻断，不视为正向实现完成。当前缺的发布授权合同已请求澄清；不因等待时间推定授予权限。owner暂停、无真实持久身份/凭据/Grant/Run访问新增；不push/CI/merge/deploy，R4关闭/真实模型预算0。ENG086完整1497PASS及实际浏览器成绩保留原范围；Windows隔离CI仍不能代替全量或Win11。
