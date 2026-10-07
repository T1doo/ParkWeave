# ENG091：同一产品Case只读路径与同步范围

基线68947eacf32eeff39996e6e32d42c4db0373c6e7。本轮优先修正真实产品页缺少同一Case跨阶段记录与合法Run访问前置总览的问题，没有继续增加独立Mock页面。这里“产品”指实际Store/PG/API/web代码，输入仍是合成资料；不等于真实园区业务或完整V1已验收。

## 实现与默认拒绝方案

新增产品GET `/api/preparations/{id}/case-path`，仅当前所属enterprise_operator的READ和PREPARE权限可读；真实Bearer认证、active身份、owner/park/org、SYNTHETIC preparation、当前owner Run及Case/Run绑定均独立检查。专员和执行者仍使用原有各自事项入口，不通过这条企业总览获得材料或其他Case可见性。

事务先设置READ ONLY；随后沿用现有auth shared advisory锁与当前授权复查。本模块没有schema迁移、INSERT/UPDATE/DDL、授予/续期/撤销assignment或新增能力配置。拒绝仍由既有API处理器记录authorization_audit；该审计不修改授权配置。现有assignment查询必须同Run/park/org、active绑定、active同tenant service_executor及当前active READ；仅返回是否存在，不枚举主体。其他Run、失效身份/READ/角色/tenant均不能满足前置。缺少绑定返回BLOCKED_NO_EXISTING_ASSIGNMENT；不能提交申请或把Mock批准映射为产品访问。

页面在四步计划中提供“核对此Case协作入口与已有Run访问”，统一显示同一Case/Run/资料版本的诉求覆盖、计划、材料、资源关联、接单和合成回执记录。资源与回执记录检查Case/Run/owner/tenant绑定；历史记录存在不等于当前有效。READ COMMITTED多次读取只形成读投影，不承诺原子数据库快照，各业务入口仍独立重验当前来源/权限。资格UNKNOWN、目标False，真实履约未核验。

刷新计划、切Case、切身份与代际变化清空旧投影；资料版本不匹配拒绝显示；临时读取失败清空并允许重试，观察到403后清空整个私有计划视图。迟到旧Case/旧身份回复不能回填。新入口无POST和自动办理，不改变原有P1–P4命令顺序或审核门。

## T01–T07逐项验收缺口与当前证据

| 项 | 尚缺验收项 | 当前可复核证据及限制 |
| --- | --- | --- |
| T01 入口与企业事实 | 完整锁定约束、跨材料事实冲突核验/裁决、三类来源真实性、按用途授权资料复用 | ENG085/evidence/eng085-persistent-request-coverage.json保存原诉求、必需目标和UNKNOWN/PARTIAL；ENG086/evidence/eng086-source-bound-material-readiness.json来源hash/版本绑定、补正FALSE/缺证UNKNOWN。人工本地核对不证明真实性或资格。 |
| T02 方案与目标 | 从注册服务通用编排DAG、全部必需目标覆盖、完整前置/产出/补正/验收闭环 | ENG084/evidence/eng084-case-plan-preview.json固定四步责任、前置、产出、验收可读；ENG085保存未覆盖目标并阻止省略/启用。有限工程模板不是通用ServicePlan。 |
| T03 资源 | 必需组合全绑定正式Approval/ServicePlan和已发布规则，透明替代及完整变化影响 | ENG025/evidence/eng025-acceptance-summary.json与ENG037固定模板实际PG/API两资源同事务、Case关联和失效重验；不覆盖全部AT09–11/28–29或外部资源原子性。 |
| T04 角色办理 | 通用CaseStep、接单后责任交接、完整业务通知/渠道、真实新Run申请授权与履约证据 | ENG032/evidence/eng032-dispatch-acceptance.json有分派/本人拒绝接受/合成回执补正重开；ENG033本地关闭、ENG035通知outbox。这些链需已有合法assignment；ENG089隔离Mock没有真实赋权。本轮仅补同Case已有访问只读/失败路径。 |
| T05 可靠执行 | 所有F2办理/通知贯通业务outbox，全链幂等消费、未知结果/变化核对/陈旧批准回归 | ENG025/032/035局部事务、CAS、幂等、崩溃恢复和通知证据；本轮只读无业务写digest变化。不能据此给AT16–20整体通过。 |
| T06 模板与新输入 | 审核发布后参数化服务包、合法新企业冷会话/新材料与完整AT08/35 | ENG037固定工程模板、ENG084预览、ENG085显式目标；ENG088候选发布仅隔离Mock。完整无fixture赋权的新Run冷办理仍未实现。 |
| T07 工作区与端到端 | 同一新Case原诉求→规划→确认→办理→核验→反馈完整V1链、用户视觉签收、真实手机/Win11与全部阶段AT | ENG080等实际局部PG/worker/Chromium、ENG083/086窄屏；ENG090明确历史证据Case不同不可拼链。本轮实际同Case只读记录导航与新Run阻塞，不宣称完整冷启动或F1/F2签收。 |

## 自797f426以来的准确同步范围

最后已知核实远端基线797f426dc2f6274a973a82bb7909dc5d820b8f79；本轮未查询网络，不能称为当前远端状态。其后、本轮开始前恰好8提交，顺序如下：

| 完整提交SHA | 内容与类型 |
| --- | --- |
| 49cc26846b47979c0f5ff1f4ca960aebb3282eba | 历史Case模板启用条件说明；产品代码+历史精确同步证据 |
| 498d5d2ed03aa241f2bdcba72d614546033d3945 | 产品固定四步方案预览与覆盖 |
| 6b647acc99432acee2299be033812981e4e1aff9 | 产品持久诉求/必需目标；migration019 |
| 5822b0296060a36721d90aa85b5bb8d3ce4a2e6c | 产品来源绑定材料准备度；migration020 |
| 31944ea2847145261d0e8b93d0b7c755f8cd98b4 | 既有发布权限边界测试/未实施授权方案 |
| 5cbff16bcdb5a8b447f64b57040db6452f1f048d | 隔离SQLite规则候选，不接产品PG |
| a73e252c4556dd8878277dcc73fd9d1308320458 | 隔离SQLite单Run访问候选，不写产品assignment |
| 68947eacf32eeff39996e6e32d42c4db0373c6e7 | 六份固定历史证据只读评审目录/隔离候选launcher |

此8提交累计72路径、5769新增/33删除；ENG091作为第9个本地提交加入本次同步候选，最终SHA由本地commit回报。不能把整个范围统称Mock-only。

migration019确实给产品既有preparations增加nullable request_intent JSONB，并给已有preparation_events动作约束增加UPDATE_REQUEST；migration020增加nullable bounded readiness_assessments JSONB（≤32）。这两项是正式Store.migrate代码，已在隔离合成PG测试中应用，不是仅文档候选。未证明部署库已经应用；API启动不自动migrate，显式setup/合法迁移身份执行时才应用。无新表、SQL GRANT、角色、principal或assignment写权。ENG091无迁移。

ENG089/090文档所提未来生产rule_versions/rule_reviews/rule_releases/rule_events、rule_publication_authorities、run_access_requests/run_access_decisions/run_access_events、run_access_authorities、受限赋权函数与managed expiry关联都仍未生成或执行。真实生产目标/账号/清单未确认，保持关闭。Mock数据库只在专用目录，不能拿候选批准作为Bearer权限。

roles.sql、schema.sql和`.github/workflows/windows-server-engineering.yml`相对797f426字节未变；现有迁移文件019/020明确单列。workflow push过滤包含src/parkweave/**、tests/**、scripts/windows_ci/**、pyproject.toml等，因此未来普通push dev/f1-foundation这些提交会匹配并触发现有workflow；当前job仅windows-2025独立controlled Job measurement、contents:read、无PG/app/pip/上传，不是完整Windows工程或Win11验收。不能把后续绿灯当1564/新全回归在Windows通过。

同步前仍须按后续获授权流程核实实时远端与祖先关系；若远端变化先比较，不force/reset丢代码。本轮只准备已验证产品成果及完整提交范围，未push、未新CI、未merge/deploy。

## 最终验证

新入口实际PG/API边界测试19项；产品请求/预览/准备度相关回归58PASS/2WARN。真实缓存Chromium运行实际产品web与独立合成PG API：同Case已存在材料/资源/本人接受/已核对合成回执路径可读，新Run无assignment阻塞；1200/390/320无横溢，刷新/读取失败/403/迟到Case与身份隔离均通过，整个业务/权限数据digest前后一致。仅合成测试夹具setup预置既有assignment，浏览器/新产品API本身没有授予；旧演示fixture仍未启动。

最终冻结227源码完整Linux回归1583PASS/0FAIL/9原生SKIP/2WARN，326.04秒，冻结差异0；累计同步候选9本地提交/77路径。完整冻结源码与回归、浏览器hash和独立复核见[evidence](evidence/eng091-same-case-path-sync.json)。本轮不启动生产、不改owner、安全配置、实际权限或模型预算；F1未签收/F2并行探索、Server非Win11、R4关闭/模型预算0、原环境与备份保留。
