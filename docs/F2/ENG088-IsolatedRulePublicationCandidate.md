# ENG088：隔离候选规则审核与发布

基线 `31944ea2847145261d0e8b93d0b7c755f8cd98b4`。用户已明确授权候选合同、流程代码及离线 Mock 测试，不授权实际权限激活。本轮实现独立候选应用，**候选流程未启用**指实际业务发布始终未启用；显式测试配置只启用隔离合成状态机。正式目录、部署 API、主体、凭据、Grant、assignment、owner、schema20 和权限 SQL 保持原样。

## 总设计与最小合同

沿用原设计§5.3/§6.2的来源→候选→人工审核→发布，以及§11当前身份、范围、能力、Grant交集。审批权不能从客户端 ServiceSpec 审核字段产生。复用严格 V1ServiceSpec、受控 Rule/Truth、SourceRef、Validity；候选仅接受 SYNTHETIC 来源，不把来源指针当真实已核实材料，不执行资格表达式或模型调用。

| 合同 | 实现与边界 |
| --- | --- |
| 发布主体 | MockPrincipal 的显式角色、active；CandidatePermit 的主体/动作/范围/有效期/active。仅测试内存配置，没有部署账户或Grant。测试中的专员审核、resource_admin发布是演示 RACI，正式审批与授予主体仍待权威合同确认。 |
| 对象/范围 | stable object_id与精确park_id/org_id/service_id；草稿owner_org与service必须相符。不得跨组织或扩大适用范围。 |
| 版本/来源 | 每个命令revision CAS、每次保存content_version递增、内容SHA；SourceRef精确绑定正文与有效期。已出现的同名来源版本不能换字节或有效期，必须新版本。 |
| 审核/发布 | 作者提交后另一当前合法Mock主体明确REVIEW；发布须另一主体、当前审核hash及当前审核/发布能力。REVIEWED没有发布快照，PUBLISH才产生隔离快照。 |
| 撤回/审计 | 每次操作记录actor、scope、permit、contract_revision、内容hash、理由、时间、版本；事件禁止UPDATE/DELETE。WITHDRAW保留发布来源和审计，关闭当前适用性。 |
| 默认拒绝 | 生产api未挂载候选路由；默认无配置、不建存储。演示工厂须同时有明确命名空间开关和专用*.candidate.sqlite3路径。X-Mock-Actor仅离线选人，不是真实认证。 |

DRAFT→REVIEW_REQUESTED→REVIEWED→PUBLISHED；提交可RETURN_DRAFT；REJECTED必须实际修订后再提交，不能只更改规则或来源版本号，也不能仅重排来源数组。已发布内容修改会SUPERSEDE旧快照、新版回到DRAFT且须重新审核；撤回后需重新保存/审核。所有来源及规则须当前有效，发布区间不能超出任何来源/规则区间。拒绝、过期、当前审核/发布主体撤销和未发布使当前候选不可用，资格始终UNKNOWN/NOT_EVALUATED，真实business_publication、deployment_enabled和case_goal_completed始终false。

候选评估只冻结当时候选可用性，绑定对象版本、来源hash、当前完整Mock合同及适用状态。变更、撤回、过期或权限撤销让旧评估STALE/当前UNKNOWN。历史发布回执可幂等重放，但不能恢复撤回状态，界面随后GET当前状态。刷新只读，不自动审核/发布/资格确认。

SQLite只用于隔离候选夹具，无PG连接或部署迁移。外来/部分/不同版本的旧库拒绝，拒绝前不DDL；含正确namespace但混入legacy表同样拒绝且文件字节不变。现有产品旧数据和目录读取保持兼容；不会把旧业务库转换为候选库。事务BEGIN IMMEDIATE+版本CAS，actor范围幂等key绑定全部对象/动作指纹，当前授权先于历史重放，失败完整回滚。测试仓库上限64操作、32评估，超限拒绝。

## 界面与可运行演示

新独立HTML始终显示“候选流程未启用”，清楚展示Mock主体、固定范围、来源正文/版本/有效期/内容hash、当前内容审核记录、候选发布及评估历史。换身份立即清空私有来源、表单与历史；跨范围拒绝保持清空，迟到成功/错误不回显。真实浏览器验证会使用隔离SQLite与127.0.0.1，不启动真实产品数据库，不读取凭据。

本地显式演示入口：`scripts.rule_candidate_demo:configured_mock_app`（uvicorn factory，仅绑定127.0.0.1）；测试开关 `PARKWEAVE_CANDIDATE_ENABLE_TESTS=ISOLATED_SYNTHETIC_CANDIDATE` 与专用 `PARKWEAVE_CANDIDATE_TEST_DB`。该入口不能替代部署认证/权限合同。生产API的service结构校验仍published=false，现有目录仍只读。

## 将来激活所需的逐项审查

| 能力 | 当前候选/现状 | 正式激活需要的权威决定或最小权限 |
| --- | --- | --- |
| 规则身份与RACI | 仅内存Mock标签；作者与审核者分离、审核与发布主体分离 | 明确实际提交、审核、发布、撤回、授予/撤销审批主体与同人限制；真实认证得到actor，核对active与精确园区/组织/服务能力及期限。不能沿用演示角色作为已授权事实。 |
| 规则存储 | 仅专用SQLite；preparation_catalog仍SELECT | 审查来源/修订/审核/发布/撤回表迁移；最小业务表SELECT/INSERT、仅必要状态字段UPDATE、不可变审计INSERT，或窄受控函数EXECUTE。app不得写授权表或自授Grant；目录写权限只有实际需求与权威审批后才可能考虑。 |
| 实际发布接入 | 未挂载产品API；无真实资格oracle | 审查真实认证和当前权限、服务范围、来源真实性与实际目录解析器，绑定release版本和时间；单独审查资格事实/人工条件与来源可信度，不从发布推定资格。 |
| 单Run访问请求 | 目前scoped_run只读核对active principal/token、role上限、同park/org当前READ Grant；非企业还要求active精确Run assignment | 先明确谁能申请/批准/撤销、申请者与批准者分离、有效期和理由。申请/批准/撤回命令须显式、actor来自认证、CAS/幂等/不可变审计。审批主体尚未指定，不能从park_specialist等角色推定。 |
| 单Run访问授权数据 | app对run_assignments只有SELECT；现有表缺版本/期限/审批审计合同 | 权威批准后才审查精确Run assignment INSERT/必要列UPDATE或受限函数EXECUTE，审批/撤销审计表INSERT；核对现有目标principal active、service_executor角色、同tenant READ及Run归属。不调用owner/setup assign_status、不给其他Run/Case或动作隐式权限。 |
| 单Run使用/撤销 | 每次读取仍核对当前READ与assignment | 明确授权期限、撤销传播及当前绑定；访问授权只表示ParkWeave内部Run访问，不代表外部OS/Windows账户或履约证明。现有P3阻塞保持，直到真正合同与最小权限获批准。 |

上述均为待审查合同/代码需求，没有执行候选部署迁移，没有真实发布主体、凭据、Grant或assignment新增。F1未签收，F2并行探索，Windows Server不是Win11；R4关闭，模型调用和预算0；不push/CI/merge/deploy，owner限制保持。

## 验证记录

最终候选与现有目录只读边界相关测试：29 PASS/0 FAIL/2既有WARN（2.03秒）。覆盖默认双开关、角色/范围拒绝、独立审核发布、来源版本不可重写、修改重审、撤回/历史、过期/权限撤销、同key并发与CAS、跨对象key、撤回后历史回执不能重新生效、原子回滚、外来旧库字节保留及真实隔离PG目录UPDATE拒绝。失败浏览器尝试保留，不计为通过。

最终修复后实际Chromium浏览器 `88bd184af0c3` 全流程通过：审核未发布/候选发布、修改SUPERSEDED/评估STALE、撤回和驳回修订、丢已提交回复同key只一事件、跨scope换身份迟到回复不回显、过期来源拒绝提交、刷新恢复。最终revision17/content_version6/history17/releases2/assessments1；1200/390/320无横向溢出；模型调用0、预算0、真实发布false、无部署PG/迁移，子进程已回收。独立审查已实际看最终7张图并核验9件图/JSON哈希。

最终211源冻结完整Linux回归 **1526 PASS/0 FAIL/9原生Windows SKIP/2既有WARN**（315.08秒），源码hash0差异。JS语法与git diff检查通过。完整成绩只覆盖Linux/隔离候选与既有工程回归，不能替代正式发布、Win11、完整Windows或F1验收。

独立复核修复了含正确marker却混入外表的旧库接受、REJECTED直接重新提交、仅升规则/来源版本号的驳回绕过；各有DB不变gold。早期浏览器因原生日期填值或窄屏工具未交付目标click失败，明确保留；最终脚本先显式滚动到按钮，使用真实原生click并验证目标事件到达。前修复全量1525PASS因执行中源码修复不计最终，日志/旧冻结另存`.runtime/eng088-before-review-fix-*`。相关29PASS、最终浏览器和最终完整回归的hash及部署边界见[evidence](evidence/eng088-isolated-rule-publication-candidate.json)。最终独立核验已完成，无阻断；211源、完整/相关日志、最终9件浏览器证据哈希及6项生产边界文件均相符。
