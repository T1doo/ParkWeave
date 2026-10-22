# AT31 业务应用层配对设计（待审）

状态：**DESIGN_ONLY / NOT_IMPLEMENTED / NOT_RUN；双臂恢复当前 NOT_EXECUTABLE**。初稿基线 `bca7e8152b7a435906ac83133f008441e96068db`；本次只读核验 `af7ae9fc0fb91206fc372fc6c1ddc8176f67cac1`（产品树相同）。本页不授权执行，不修改 AT 规格、API、批准范围或原拒绝门；不宣称业务配对或效果通过。

依据原[计划§10–11](../sources/V1/分阶段开发计划%20%282%29.md)：B2 在同一已存在计划上比较全量重规划与依赖修订，安全保护相同，全部失败及修复成本保留。[候选层比较](B0B2PlanningOnlyValidation-20261019.md)已经完成，不重做。这里提出一个更窄的 LOCAL/NO_MODEL 业务应用候选，待根侧审定后才决定是否实现；它不是旧 V4 六目标样例的续跑，也不是 B1/LIVE 或完整 AT31。

## 已核实的现合同

- `service_case_steps.adopt` 的局部路径要求 binding 未变、当前来源/依赖已知、受影响锁已解除；原非局部替换路径在同 binding 下拒绝“已有计划”。二者不能靠换请求字段互通。
- `LocalResourceApproval` 只允许同计划来源续接；`plan_replacement_enabled=False`，账本和 `_source` 均拒绝前驱计划字段。原 V4 替换另依赖隔离批准与 ServiceRelease 预检，不是普通 LOCAL 的备用通道。
- `case_resource_delivery._source_reapproval` 验原关联/回执、同 plan ID、较新显式来源 ADOPT 与实际 P2 影响；新批准消费、新组合和关联修订沿原事务。其历史验真读取原事件，不能用新事件覆盖旧证明。
- `difference_observation` 的尾步基线只作差异观察，不能作为 VERIFY。原 LOCAL 续接还检查未开始历史；缺权限/损坏/未知不能当作空。

对应源码：[采纳](../../src/parkweave/service_case_steps.py)、[LOCAL批准](../../src/parkweave/local_resource_approval.py)、[交付](../../src/parkweave/case_resource_delivery.py)、[来源采纳](../../src/parkweave/source_change_adoption.py)、[观察基线](../../src/parkweave/difference_observation.py)。本轮只读，不将旧动态成绩转签本基线。

## 共同合法初态与唯一变更

候选初态复用现有 `tests/test_no_model_difference_observation.py::staged` 的五目标输入（从 `test_service_case_steps.GOALS` 冻结完整字节，不删目标），同三份已支持的 LOCAL release、P1–P5、原合法角色及现有权限。由原命令完成候选→首次 ADOPT→材料核对/P1显式VERIFY→首次明确PROPOSE/APPROVE/交付→P2显式VERIFY。

此时原 plan/五 step UUID、请求/目录/注册动作、差异观察封存与候选消费证明全部可验；P3–P5 持久 `coordination_state=PENDING`、无 VERIFY，未 BEGIN、分派、接单、回执或本地结案。页面派生状态另列：初态 P3 可 PENDING、P4/P5 可 BLOCKED，不能统称页面均 PENDING。原八类尾步表及历代计划事件实际核查，失败即拒绝；不借用隔离 frontier 权限。保留 P1 的原 LOCK、原说明与完整 VERIFY 证明作为必须保全对象，P2–P5 无锁；有未决写或历史不明不能入组。

v1只接受本页共同初态：原计划事件按初ADOPT→P1 VERIFY→P1 LOCK→P2 VERIFY，首次LOCAL批准已CONSUMED且只有原link revision 1。拒绝partial、template_migration、owner_amendments/MANUAL正文、fact_provenance_scope/dependency_scope专用组合、既有FULL/后续来源ADOPT及replacement历史；保留LOCK理由/原用户说明不等于支持人工正文合并。下列消费者表指出必须审查的共享入口，不声明支持它们全部组合；LOCAL/FULL每臂均从该同一前缀各追加一次来源应用，不串用另一臂事件。

唯一变更冻结为原 park-a 两资源 `fa161ea0-b665-4ec5-b345-a070bfec764d`（空间）及 `fb161ea0-b665-4ec5-b345-a070bfec764d`（设备）：各行 revision 1→2、buffer_seconds 300→360、source.revision 字符串 `1`→`2`；空间 source.statement 同步将“前后缓冲各5分钟”改为“前后缓冲各6分钟”，设备原说明不变。其余字段逐字保持，包括 capacity=2、enabled=true、UTC/SYNTHETIC/LOCAL_AUTHORITY、来源ID和原开放窗口；不改 request、catalog、pack、角色或 Grant，不调用会新增资源/Grant 的旧 `changed()` helper，旧占用不释放。

窗口模板也先冻结：共同初态时点 T0，原三成员为上述资源按空间/设备/空间顺序、quantity=1，时间为 T0+[5,6)、[8,9)、[11,12) 小时；新三成员用 T0+[15,16)、[18,19)、[21,22) 小时，缓冲后均在原开放窗口且不与旧占用相交。T0、实际UUID、各原始行/hash/期限目前没有物化，不编造值或声称初态已冻结。现有 `current_sources`/`registered_dependencies.collections` 会读 resource_rules、resource_collection 及 P5嵌套资源来源，故变更具有可观察字段；是否完整满足全部门仍须未来独立核对，不能仅据此签可执行。

## 双臂恢复：当前构造器不能兑现

初稿“各自绑定由已有构造器验证”过于乐观，现明确撤回。两新 Case 不等于同一已存在计划，两臂不能在首臂写完的库上接着跑，也不能删行倒回。以下是只读可行性结论，未尝试 restore 或操作数据库。

| 构造器/对象 | 绑定及不能搬移的内容 | 当前结论 |
| --- | --- | --- |
| `tests/conftest.py::pg/fixture`；`capture_fixture_cluster`→`FixtureClusterEvidence.record_created_database`→`FixtureDatabaseEvidence.authorize_migration` | 必须本次新建数据库；真实内存注册对象绑定 cluster nonce、database nonce、system_identifier、data_directory、postmaster_start、owner、database name/OID。迁移ticket还绑定同事务/backend，不能序列化重签冒充原出生证明 | 只有新建/migrate/seed，没有恢复共同业务初态的构造器 |
| `LocalDemoCatalog.validate/snapshot`；`demo_inputs` | config/journal 的 database name/OID/address/port/user、pack/journal SHA、preparation_catalog完整行hash及 xmin 精确相等；database_sha256/journal_sha256 又进入能力快照、candidate及ADOPT消费链 | 逻辑导入新库改变 OID/xmin；重写 config/journal 会改变原hash，不能保原证明 |
| 持久业务及历史 | 至少保全 principals/capability_grants/action_grants/field_grants/run_assignments/preparation_grants、runs/operations/cases、preparation_catalog/preparations/evidence/events、两资源/Grant/holds/receipts/combinations/members/combination_receipts、resource_case_claims/case_resource_links、outbox/projection；`preparations`内原candidate/ADOPT/差异基线/机会/LOCAL批准head与事件全保，原八类尾步表仍空。`source_change_adoption.epochs`还核相关行xmin | 不能只搬Case JSON或重放命令生成新事件；session凭据不作为拷贝材料 |
| 原 same-state 停服再启 | LOCAL原目录及持久业务可按原绑定读回；迁移创建receipt不是每次LOCAL冷读的必需输入 | 已有冷重启不等于初态回滚或双臂分叉；不据此发明恢复能力 |

业务UUID、原事件/事实/授权版本、到期、旧hash及出处必须保持。新HTTP端口、浏览器context/PID、执行日志位置和每臂新命令ID可不同；数据库 address/port/user/OID、目录 xmin 若进入原绑定就**不可**当环境噪声归一化。原same-state正常重启的postmaster_start可变，但旧出生证明随后不能再授权迁移，不能制造新证明替代。重认证须各自由既有合法机制完成，不复制session、不新增授权或续期。`scripts/ordinary_synthetic_demo.py::serve`还核 source/sessions hash、system_identifier、DB OID和完整authority摘要；它只有保留state的serve路径，没有checkpoint/restore能力。

现无已审构造器能在这些约束下做第二实例恢复；物理PGDATA分叉或原位checkpoint/rollback也无现成实现/合同。结论是 **NOT_EXECUTABLE**，不是被平台拒绝或某个restore结果未知。需另审合法初态恢复能力后才可能实施配对；本页不设计新的恢复信任根、不运行 `pg_dump/restore`、不重签出生证明，F5备份恢复不升为PR0/C0前置。

## FULL 的拟议应用语义

**建议选择“同计划全量重算后受控协调”，而非创建新计划身份的 replacement。** 全量重规划描述计算范围，并不要求丢弃稳定 ID。这是待审的 B2 有限语义；若评测要求 FULL 必须产生新 plan ID，本候选不满足，须另审替换/迁移合同，不能改名充数。

FULL 从同一完整当前输入重新构造全部五步契约、目标覆盖、约束与来源见证，逐步核对全部旧契约/历史/人工决定。不得以 LOCAL 的 affected 集合裁剪重算，也不得将旧节点直接当作重算输出。可共享原确定性注册重建器、权限及提交校验；“五步都重新观察/构造”须有实际工作记录，不能仅在原局部 ADOPT 外贴 FULL 标签。

重算后，独立比较完整新旧契约及来源，映射原稳定 step ID；本候选仅接受契约/目标/责任/动作/依赖不变、来源变化已知且确实影响 P2 的情形。实际需重核的源及下游步才失效，未变的 P1 保留原 LOCK/VERIFY；不能把全量计算等同全部失效或自动重办。未知、契约变化、无法一一映射、受影响锁、已开始尾步均拒绝应用，保留旧版。

应用须有可历史重建的完整重算输入、结果、差异及本人明确决定证明；提交前重新核权、未开始门、时钟与 CAS，原键恢复不得重复追加。**当前没有该业务应用入口或消费接线。** 下列是具体候选合同，不是可提交给现API的DTO，不新增replacement权限。

## FULL v1证明及全部消费点（候选，未实现）

记 `H(x)=controlled_plans._hash(x)`；业务值先按原 `_normal` 处理、列表按明确原顺序，不任意删字段/归一化期限。证明hash用于原应用记录一致性，不是签名或数据库管理员不可伪造的权威。

| 对象 | v1精确字段及约束 |
| --- | --- |
| 请求DTO | `schema='local-full-source-adopt/1', expected_preparation_revision, expected_request_revision, expected_plan_revision, expected_source_sha256, expected_rebuild_sha256, required_goals, opportunity_proof, reason`；均必填、extra forbid，revision/goal/key/reason沿原上限；禁止 local_revision/partial/candidate/replacement 字段。同actor/key全局Case指纹沿原幂等域 |
| 机会子DTO | `schema='full-opportunity-binding/1', card_id, expected_ledger_revision, expected_card_version, expected_basis_sha256, expected_card_entry_sha256`，均必填/extra forbid；最后一项=H(原账本前缀投影出的card.entry)，仅最新PENDING_REVIEW卡可写。不是旧OpportunityProof，不能借用其LOCAL preview hash或引用包含本请求的FULL proof自身；历史按该原前缀逐项核，不要求旧卡现在仍待办 |
| 事件 | 沿原 `_event` 精确公共字段，`action='FULL_SOURCE_ADOPT'`、step_id/source_sha256/sources均null、coordination_only=true，额外仅 `dependencies, full_source_adoption`。revision连续、owner本人。fingerprint=`H({preparation_id,action,**原DTO})`，不能作为普通ADOPT或VERIFY重放 |
| `full_source_adoption` | 精确键 `schema='local-full-source-proof/1', request, binding, predecessor, input, output, transition, sha256`；sha256=H(其余全部)。binding精确含 preparation_id/case_id/run_id/plan_id/owner_id/park_id/org_id/preparation_revision/request_revision/plan_revision。predecessor精确含 `initial_adoption_event_id, initial_adoption_event_sha256, candidate_consumption_sha256, event_prefix_sha256, steps, steps_sha256, dependency_manifest, dependency_sha256, source_evidence`；source_evidence按五adapter完整映射，每项含 `kind, event_id, snapshot, sha256`，kind仅VERIFY/DIFFERENCE_OBSERVATION，事件按原前缀验其快照与引用。缺旧基线拒绝，不读取时补录 |
| input | 精确分组 `request_intent, original_goal, service_contract, catalog_snapshot, capability_snapshot, frozen_registry, step_id_map, source_snapshot, source_rows, epoch_rows, opportunity_prefix, observed_at, verifier_version`。保全部五步来源、原源码版本对应注册契约/声明、bounded原始作用域查询行及其完整count/hash；epoch保存原查询行/xmin而非仅digest。机会只封存原card所属精确账本前缀。原权限与来源版本及有效期在内，不含session/凭据；查询错/超界/未知不能封成空 |
| output / transition | output精确 `rebuilt_steps, goal_coverage, constraints, dependency_manifest, current_sources, input_sha256, sha256`；input_sha256=H(input)、sha256=H(output其余键)。五步全量重建、一一映射原UUID、契约及必需目标与旧版全等，仅允许本资源来源差异。transition精确 `directly_changed, affected, preserved, before_steps_sha256, after_steps_sha256`，各集合用稳定UUID、affected非空且含P2、affected/preserved完整互斥覆盖五步；后态仅按原失效语义改变受影响步，P1全文/LOCK/VERIFY保全。request.expected_rebuild_sha256=output.sha256，request.expected_source_sha256=H({binding,input_sha256:H(input)})；所有嵌套SHA按已保存完整值重算，不信生产者摘要 |

以上嵌套组的字段字典必须对应本页冻结源码的完整原投影/SQL列（不得只留可变hash）；epoch查询原界仍用 `epochs` 的逐类上限，资源/查询集合沿原256行、目录32行。候选新增存储界：单证明规范UTF8≤256KiB、追加后整份plan≤1MiB、五步/64事件/8层历史原界不变；任一不足拒绝而非截断、分片或抬限。它们只是待审新增限制，不是当前已经生效的产品门。

历史验真只使用原事件前缀与保存的完整输入：先重建初ADOPT、各VERIFY/观察来源、旧依赖及机会前缀，再用该版本冻结注册重建器重新构造五步契约/覆盖/约束及依赖manifest；按完整source_rows重建本次source_snapshot、按epoch_rows重算epoch和input hash，逐字段比较output，不由今天的DB或当前声明补历史。再从前后完整来源、原声明边及旧manifest独立计算direct/closure，与transition和后续step状态逐项核对。锁后当前写入重查全部业务行/epoch、权限和原期限；observed_at保留原预览UTC，校验当前时刻不倒退及余量，不把新的clock值写回原input导致指纹漂移。重放验证输出一致不证明当时实际计算耗时，不能把自报计数当性能证据。当前身份/读取权仍在外层实时核对；来源真实性受原自有数据库信任边界限制。

| 必须接线的现消费点 | 拟议处理；本轮均未修改 |
| --- | --- |
| `service_case_steps._recovery_proofs`, `recover(expected_request)`及 `_replay` | 独立识别FULL DTO/动作及原指纹，验连续revision/前缀/完整proof，再核依赖与后态；按原键只读恢复。旧Adopt/Command序列化、缺省字段和指纹逐字保持 |
| `registered_dependencies.plan_proof`、`adopted_preview_steps`相关契约验证 | 新动作显式分派，按FULL前后manifest重放；依赖声明采用事件冻结版本，不能换当前VERSION或把FULL当local_revision |
| `source_change_adoption.evidence_sources/validate_history`、`difference_observation` | 来源history折叠FULL完整current_sources；前缀内原VERIFY优先语义保持、未VERIFY尾步仍仅观察。版本分派须明确，旧v1–5继续走原逻辑；新证明不伪装旧source_change |
| `case_goal_results.structure/verification`、人工锁/注记及template历史验证 | 当前动作白名单和VERIFY/LOCK引用显式支持FULL，重建保全/失效而非继承审核；新动作不是履约证据。当前范围仍拒契约/模板变化 |
| 批准 `_ledger/_source/_view`、`LocalResourceApproval.ledger/verify_receipt` | 同LOCAL scope与原CASE_RESOURCE_REAPPROVAL purpose，严格新锚 `full_source_reapproval_v1`；不得fallback到旧LOCAL/isolated/replacement账本。新锚精确含旧 link_id/link_revision/snapshot_sha256/previous_delivery_context/previous_approved_plan_revision、approved_plan_revision、full_event_id/full_event_revision/full_event_sha256/full_proof_sha256。与旧source_reapproval/plan_replacement互斥；按原已批准plan前缀验，不取现在最新事件 |
| `case_resource_delivery._source_reapproval/_candidate/deliver/_verify/recover` | 新锚验较新FULL实际P2影响、原同plan及关联/完整回执，提交锁后再验当前证明/权限/epoch/期限；新组合/关联/消费同事务，源变或异常整体回滚。历史GET核原事件而非新FULL覆盖旧锚 |
| `plan_replacement_compatibility.verify_history`、`resource_plan_binding.catalog_decision` | 这些共用读路径也处理LOCAL旧关联；须精确识别新锚并逐层递降原link，保持旧receipt hash/消费前缀，未知/混合/自引用拒绝；不因此启用replacement |

上述新事件/证明/锚必须同时发布所有生产与读取消费点才可实施；任一点尚不支持，FULL写入默认关闭。已知旧事件逐字兼容；未知新动作、schema、字段或混合锚整体拒绝，不能落回普通ADOPT、视为首次交付或省略证明。重启只加载既有持久内容，不能改hash、补历史或续批准。

## 独立oracle与时间/失败口径

独立oracle固定为 `AT31-LOCAL-RESOURCE-REVISION-BUFFER/1` 的本页输入模板，不复用旧V4六目标分母。其期望不能调用产品 `current_sources/source_impact/closure/typed.build` 或FULL/LOCAL输出生成；未来从独立只读SQL行及原保存证据，按本基线静读的完整投影字段清单制作字面映射。来源范围必须齐全：P1含Case/请求/材料/事实用途/目录/owner授权与原模板；P2含关联/组合/成员、holds、两资源完整规则/权限和查询集合；P3含分派/offer/acceptance/receipt-step、Run访问与当前角色映射；P4含step/全部receipt版本及事件；P5含完整本地核对嵌套来源与生命周期。现有 `typed_source_impact` 的分组可作字段清单参照，不能调用其算法当独立答案；新增/缺失字段和未知行均拒绝完整判分，不能只验affected摘要。

字面期望：契约、五目标、P1全部源/LOCK/VERIFY不变；资源当前行只按上述唯一变更更新，旧holds/回执/关联及尾步空历史不改，相关resource_rules/collection count与排序行hash独立重算；P3/P4自身空源可不变，但P2→P3→P4→P5传播需重核，P5资源嵌套值按原投影独立核对，不能仅复制新P2摘要。应影响P2–P5分母4、应保全P1分母1；完整direct集合须先由这份独立逐字段映射冻结，不能猜测只有P2直接变化。三阶段分别核源、持久状态、派生状态与目标结果；期望原始行、实际T0/UUID及完整字面字典尚未物化，故当前没有可运行的完整oracle或配对初态，不能将本模板标PASS。

未来执行候选顺序固定FULL→恢复共同初态→LOCAL，每臂都重新实时核权/源/原截止，不冻结数据库时钟。工作绝对截止仍≤270秒（不重置），其中包含共同准备、FULL自身新增proof准备/验证/存储和全部恢复；每臂计算与应用合计≤60秒，并非两阶段各60秒，余下共同准备/恢复预算≤150秒，缺余量立即准确失败。新holds沿原300秒TTL、quote最多120秒；进入任一臂时全部未完成动作的最早原期限余量须≥该臂60秒+30秒停止余量，不能重签或续期凑余量。恢复慢/期限不足也记失败及已耗成本，不删臂或换新输入补成功。清理另预留≤90秒；不超现有10分钟job边界，此页不触发或承诺这些预算已可达。

先纳入后缺臂/拒绝/部分/失败均保留，未生成结果为INCOMPLETE而非相等；终态业务错误与清理错误并列。共同创建/配置/目录审核、快照/恢复、重认证、每臂proof收集/重放/编译/校验/存储、SQL/锁等待、业务动作、失败/修复及清理分别记实际秒/次数；准备工作不是免费。顺序固定有熟悉/剩余期限偏差，仅一固定例不推统计优势，后续扩大需先审预算和顺序。LOCAL同样完整proposal，两臂新增开销全计；人工主动未观察则UNKNOWN，不能以0或脚本秒替代。

## LOCAL 与共同业务终点

LOCAL 沿现有机会预览→本人显式局部 ADOPT→同计划来源续接，不改算法/批准边界。两臂均保留原 Case/Run/preparation/plan/step ID、原事件/消费前缀、旧关联与完整回执、旧占用和原期限；来源 ADOPT 不完成目标、不核实事实、不续期限。

各臂应用后分别使用原合法新 HELD 组合，显式 PROPOSE→APPROVE→交付，原 link revision 递增、批准仅消费一次；仍用原 P2 显式 VERIFY，P3–P5 持久协调状态仍 PENDING 且无 VERIFY，页面派生的 NEEDS_RECHECK/BLOCKED 等按各阶段真实展示。新组合/关联/消费必须原事务原子提交，失败保全旧状态且不提前释放旧占用。原键只读恢复核旧新两份精确回执；不重复验证 P1/P2/TXT 的既有通用门，更不补尾部履约凑完整率。

此终点仅为“来源变化后本地资源关联重新有效”；Case 仍未全履约，整体目标状态按实际结果显示。应用前后观察基线与 VERIFY 证据分列，不能把未核验尾步变 VERIFIED。独立预期从原注册依赖与固定资源变更先冻结：P2–P5 需重核、P1 保全；来源采纳后、资源交付后、P2 VERIFY 后三阶段分别判分，持久协调状态与页面派生状态分开，不能拿后阶段结果覆盖中途错误。

## 等价判据、成本与未来执行门

两臂比较命名业务投影：全部必需目标、五步契约/稳定ID、当前源有效性、P1原证明和锁、P2新关联/明确核验、尾步状态、旧历史/占用与当前权限。不同臂新产生的事件/批准/回执 ID 不要求逐字相等，但每臂必须以原键逐字恢复自己的原件；仅在这些新 ID 上显式建立对应关系，不能归一化历史、actor、资源、期限、拒绝或丢字段。新证明的类型和额外观察成本允许不同，均保留原件。两臂不同实例的数据库绑定不作业务等价字段，但必须各自真实有效，源行/hash/输入差异须分列，不能静默抹去。

漏更与误改分别按先冻独立 oracle 计数，未知不能记零；重算全部节点本身不是误改。终点只报告上述有限本地结果，未完成必需目标仍列在分母，预先纳入后失败/拒绝/部分均保留。记录共同准备/恢复、每臂输入读取、实际重建节点、工具/查询/写入、等待/锁、核验、全部失败/修复及墙钟；计时边界和包含关系先冻结，顺序偏差明示。LOCAL 原路径本身也调用完整 `planning._proposal`，不能预设只重建四步或有计算优势；按真实调用及内部节点工作计量，允许 FULL 无优势或更慢。模型调用为0（NO_MODEL），人工主动时间没有真实观察记 UNKNOWN，不用脚本秒推人工节省、收益或 ROI；单固定样例不推总体优势。

实施决策前须独审：①接受上述 FULL 同计划语义；②完整重算证明与原消费/历史验真有可实施方案，非标签或后门；③两臂初态恢复、独立数据库绑定与原期限公平性有合法实现；④唯一资源变更实际可观察且独立 oracle 一致；⑤精确动作/请求/时限/清理预算另冻。任一不成立，保留设计/失败原因，不跑配对、不新建替换权限。此页不安排新 CI、浏览器或测试窗口。

Windows 原生/owner-DACL/026–032、LIVE 书生授权预算与共享额度、C0 官方模板/截止时区/关联规则和实际提交材料仍按 [RemainingDeliveryGates](RemainingDeliveryGates-20261018.md) 独立保留。正式来源、部署、费用、凭据及安全权限不扩展，F4–F6 不作本片前置。
