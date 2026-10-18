# 原普通页模板新输入：有限切片验证

本片完成原 F2-T06 中可独立实现的新输入表单、精确模板/当前有权服务目录绑定，以及原创建请求的只读核对。普通 `configured_app` 缺可验证模板来源时明确显示不可用并保持 404；正式模板消费尚未接通，F2-T06、真实 AT08/35 和完整项目均未完成。正向证据只来自原有、明确隔离的已审 SYNTHETIC 候选夹具，不代表正式批准。

基线 `0b7ee3544fa669e621c8b8ffd58714fa357264b3`；合同提交 `c482afe0ff8ab582072fcdfec3dbdfe380c1173d`；最终受测实现 `9f8c51fe58f6693be9ca185d90c0dee3524fa000`。合同见 [范围合同](OrdinaryTemplateInputContract-20261018.md)。原文 oracle 在读实现前冻结：14 条，SHA256 `4f1c51593ab850dd8b332d262f3c57a7831eb86e9622637f5f35fa65c39986f1`。

原 `web.html` 服务区读取已有可用候选和当前专员，输入本次目标、两项新材料、来源名称与原因，保留模板必需目标及固定参数合同。提交前再次 GET 核对精确 release/hash、定义、目录服务/version/source 指纹和当前专员；编辑、身份变化（包括 A→B→A）、导航后不显示或提交迟到响应。创建运行后，须另行只读核对实际运行成功，并明确确认保存新材料；复用原 `consume/read/resume`，停在 `PLAN_CONFIRMATION_REQUIRED`，不自动审核、确认、采纳或继续 P1–P5。

新增 `expected_catalog_sha256` 只钉住当前身份有权选择的原 `preparation_catalog` 精确行；包含 actor 摘要、park/org、service/version/name/source/namespace/qualification。省略字段保持旧请求指纹与旧实例兼容，显式 null 拒绝。新 pin 存在原不可变 binding，每一原阶段入口及当前可用性复读时重验。它与模板的独立 review/release/source/head/permit 验真各自保留，目录指纹不能提供模板发布权。本片没有增加跨 SQLite journal、PG 业务事务和目录管理源的原子提交机制；该 pin 是阶段入口预检，不能声称覆盖并发目录变更的分布式原子性。

`GET /api/template-consumer/creation-recovery` 使用当前有权 actor、原 key 和规范化扁平 `action=CONSUME` 指纹查询原 journal；从原不可变输入重算并核对 row.fp、actor/park/org/database 及实例绑定。错 hash、RESUME 键或歧义查询拒绝；其他 actor 的键不扫描，未观察到自身键返回 `NOT_OBSERVED`。GET 不调用 consume/resume、不改消费 journal 或 PG 业务记录。`RECORDED_INSTANCE` 仅表示原准入已记录；原建单仍 UNKNOWN 时继续保留未知，不从丢失回执推断未提交。当前 403 清除私有视图，不能否定此前提交。新表单只在本页内存保留原 opaque key、指纹与版本摘要，不保存材料正文或会话到浏览器存储；不承诺刷新后的冷恢复，也不扩称所有原消费者未知阶段均已闭合。

`CURRENT_PREPARATION` 与 provider 互斥、`TemplateConsumer` 的 fixture UUID/数据库/组织门槛、`TemplateEngine` 的隔离授权与来源验真、`ParkInstanceConsumer` 的独立 catalog/journal 要求均保留。没有更改 `api.py`、SQL/roles/conftest，没有向普通启动注入隔离消费者，也没有产生真实身份、Grant、分派、目录发布、批准、凭据或模型调用。

最终根冻结窗 **22 PASS**，pytest/JUnit 60.044 秒，外层 63.41436957201222 秒；16 个新切片节点与 6 个旧边界/兼容节点。823 份输入的 shared-before、mirror-before、shared-after、mirror-after 一致，115 个相关模块来自冻结镜像且哈希吻合。新正向链使用实际 worker、原 PostgreSQL、原完整页面 NodeVM 与实际 HTTP/ASGI；普通缺源拒绝另起实际 `configured_app` 进程。NodeVM 不是浏览器。旧 omitted-fingerprint/journal 兼容节点使用原 fixture finish 和原 ADOPT，仅供兼容验证；根原始 runner 的 `fixture_local_finish_selected=False` 是未区分该节点的元数据错误，原记录保留，已在各 `root-verification*.json` 明确更正，不能据此宣称所有节点都由实际 worker 完成。没有重复完整 P1–P5 或增加第三套业务范围。

独立原窗在 `b697718673e3902b2febc0efc3407b438a861831` 实际执行 6 节点：5 PASS、1 FAIL（pytest/JUnit 22.910 秒、pytest.main 24.834839057992212 秒、外层 25.97497346099408 秒；精确计时另见独立产物）。3 个节点与当时根窗重叠；另两个通过的独立节点为 literal/只读核对和完整页面迟到 403。失败节点观察到真实 SQLite `BEGIN IMMEDIATE` 等待：目录 source 推进后，preparations 从 0 增至 1，最后返回 409。根窗 20 PASS 不能覆盖该反例。最小补丁在 journal 等待及正文构造结束、原 send 开始前重验当前权限、模板、目录 pin 和专员，沿原 journal 保全拒绝，不新增跨库原子性承诺。

随后 `ef99c40d862aeb086360ac77dc0f1e3de09179f0` 根窗 21 PASS，但独立静态审查又确认：新增晚预检的当前拒绝会把旧非 planning STARTED/UNKNOWN 阶段标 REFUSED/BLOCKED，不能据此证明先前未提交。最终 `9f8c51fe58f6693be9ca185d90c0dee3524fa000` 只为该新增晚预检、旧非 fresh STARTED/UNKNOWN 保留原 UNKNOWN；新鲜/ADMITTED 首次拒绝、CONFIRMED 短路、无 pin 旧路径和原 send 异常分支不扩改。最终根窗新增两个明确回归：真实 journal 等待后不产生新 preparation；旧实际提交丢回执后，晚 pin 拒绝保持 UNKNOWN、正文/key 不变且不调用 send。独立最终静态审查只读明确 Git SHA，确认两项修补，未发现仍开放确定 P1/P2；**没有最终 SHA 的独立动态 PASS**。最终唯一通过数只报根窗 22，先前各 SHA 开发/根/独立窗均不叠加。

独审子线程首轮最终回报被平台风险标记中断；现有动态窗口实际上已结束并留下结果，未重复该窗口。读取原产物后继续已授权修补，并改为最终 SHA 的只读静态审查和证据整理；平台中断原文、具体目标和已完成工作保留在 `independent-platform-interruption.json`。这不是一次通过的独立动态复测，也没有伪造平台对具体工具动作的审批结论。

开发失败全部保留：一次测试 DOM 提取脚本标记错误，发生在测试前；首 pytest 窗 10 个 setup ERROR，原因是 basetemp 位于 workspace 而原夹具要求 owned `/tmp`，改用新 `/tmp` 目录且未修改夹具门槛；下一窗 8 PASS/2 FAIL，新增目录校验漏传原恢复路径会话参数，材料阶段已提交后恢复返回错误，修正所有原调用后定向 2 PASS，继而新模块 12 PASS，新增 ABA/403 两节点再获 2 PASS。失败 journal 以只读摘要保留，原 stdout/stderr/XML 不覆盖。以上开发窗不累计进冻结唯一用例数。

正式运行仍缺以下最小输入及可验证的权威映射。这是现有实现的缺口清单，不是新 DTO、任意配置 JSON 的接纳协议或创建权威的指令；字段齐全也不会解除原隔离门槛。

| 对象 | 最小对象/字段 | 必须来自的既有权威及当前缺口 |
| --- | --- | --- |
| 当前主体和业务权限 | 服务端会话解析的 principal.id/active/role/park_id/org_id；同范围 READ/PREPARE/EXECUTE、case.create；reviewer_id 的 READ/REVIEW_ASSIGNED 及撤权状态 | 原业务主体/授权源。现有资料准备授权不等于模板 REVIEW/PUBLISH；缺真实模板作者、审核者、发布者的合法主体/动作映射。 |
| 已审不可变模板发布 | park_id/template_id、内容版本/revision、release_id/hash/state；definition/service_id/service_version/required_goals/固定参数/注册步骤依赖；definition/registry/actions/contract hash；source id/revision/statement/validity；reviewer/decision/reason/定义绑定、author/publisher、有效期 | 既有受信模板发布和审核记录，以及其 reader/verifier。目前只有原隔离 SYNTHETIC 候选满足可执行来源证明；未提供正式只读来源、发行者和审核决定验真合同。 |
| 当前发布头和撤回状态 | contract revision/payload hash、当前 source revision/head/hash、withdrawal/supersession/state、各动作主体当前授权和有效期、release 与发布决定关联 | 既有模板/来源当前状态权威。缺正式 head/撤回证明、实时有效性和主体映射，不能从目录 hash 或字符串 REVIEW 推导。 |
| 当前服务目录的精确映射 | 模板对应的 service_id/version；本人 park/org 下 preparation_catalog 的 source(kind/id/revision/statement)、name/namespace/qualification；存在时原发布/head 证明；本次 expected_catalog_sha256 | 原当前业务目录/权限源，仍须独立模板发布证明。具体 pin 已实现；缺正式模板 release 到原目录的经授权映射及其来源。 |
| 原消费 journal/数据库绑定 | instance id/actor/park/org/database_name、原 input/binding；actor/key/fp/instance_id；release snapshot/hash/definition；原 stages/key/body/hash/state/result/error；原 CREATE_RUN 确认 | 原不可变消费 journal 与真实数据库范围的正式设计/准入证据。目前硬 fixture gate 保留，未授权改成正式启动或自造新 journal/信任根。 |
| ParkInstance（仅选择该原消费者时） | instance_id/config revision/hash/current ACTIVE；原 source_review 的 release/definition/registry/review/source/有效期；真实 enterprise/specialist/executor 及 field_key→两材料槽、用途；实际所需资源/动作映射和独立权限 | 原实例配置/角色/资源映射权威。当前只有原隔离 catalog 满足；本片不伪造 ParkInstance，也不把这条可选路线作为新表单前置。 |

正式浏览器、Windows 原生安装、正式 AT、真实业务、真实模板发布和模型均未验证。上片首次开发 HTTP 20 秒超时的具体动作/丢回执原因仍为 **UNKNOWN**，本片通过不关闭该历史失败；原 20 秒 HTTP、3 秒锁与 300 秒 offer 限制未为通过测试而增加。

证据索引：[最终根窗与精确节点](evidence/ordinary-template-inputs-20261018/runtime/root-verification-9f8c51fe.json)、[最终独立静态审查](evidence/ordinary-template-inputs-20261018/independent/static-final-review.json)、[独立完整结论](evidence/ordinary-template-inputs-20261018/independent/independent-final-review.json)、[正式对象/字段/权威映射](evidence/ordinary-template-inputs-20261018/independent/formal-minimum-object-authority-map.json)、[首次 journal 等待失败](evidence/ordinary-template-inputs-20261018/independent/frozen-b6977186-window1/scenarios/actual-journal-wait-catalog-recheck.json)、[公开清单](evidence/ordinary-template-inputs-20261018/publication-files.json)。

公开证据 338 文件，335 组原件/公开件哈希映射，其中 329 组逐字一致、6 文件共 10 处会话值或已暴露截断尾部脱敏；501 个已登记隔离会话值及其 16 字符前缀、2 个开发失败 repr 尾部片段均零命中，所有 JSON/JSONL/XML 可解析，XML 原用例与 PASS/FAIL/ERROR 形状保持。独立 canonical 60 文件按其原 SHA 原样复制，未二次脱敏。私有会话 registry、夹具配置和 PG 数据不发布。完整映射见 [脱敏映射](evidence/ordinary-template-inputs-20261018/raw-public-redaction-map.json) 与 [封存核验](evidence/ordinary-template-inputs-20261018/archive-validation.json)。
