# 固定验收与本批缺口独立审查

审查基线：`3bc1e96ccc6b6d73a5f1488bee644f92a15ddd97`。本次仅静态只读审查，未执行测试，不把既有1476/91重新计数。固定用例全文及文件hash在`fixed-oracles.json`，没有修改原验收规格或其NOT_RUN。

## 逐AT结论

| AT | 固定oracle | 已有实质证据范围 | 本批尚缺 / 不可转签 |
|---|---|---|---|
| AT-07 | 必需目标不删；步骤有责任与验收；不可行明确等待/拒绝，软件输出不是虚假履约 | 三受信能力/six goals的有限选择、独立oracle、服务端P1–P5重建；实际B链候选→明确ADOPT→本地输出，LOCAL_OUTPUTS_VERIFIED且case_goal_completed=False；错误compact refs、UNSAT/UNKNOWN等单元及集成门已有 | 真实模型选服务/拆步骤/绑定动作未验。当前模型只选有限refs，拆步骤来自受信服务定义；这是可声明的有限适配，不能声称任意编排/真实模型效果。V4未将原已提交办理反馈显式输入后续候选并绑定证明。 |
| AT-08 | 产生新Case和结果；不复制旧材料/授权；错误明确处理 | V4冷输入精确配置/字段及Run新建，真实B原业务输出，旧A材料/结果字节保留；错字段/错版本/跨园区/权限缺失拒绝。旧template consumer已有两个企业加同企业第三不同新输入完整链，不能忽略后重做或冒充V4新成绩 | V4受信选择链尚缺同一次验收中再次不同新输入完整执行，以及语义错误材料→对应角色明确补正→实际新证据→复审确认的串行回放；不是仅422空字段。LIVE/浏览器/Windows无替代。 |
| AT-14 | 预览只影响测试命名空间，不能占用生产资源或沿用生产Grant | 既有P1/P2/P3/P4/P5 preview有实际原适配器/临时表/PG public逐表快照不变验收。V4候选生成本身不执行业务 | 不可将V4候选只读替代preview执行隔离；需V4采用路径与既有preview相接时验证精确适用性，若没有该新接线则只引用既有preview覆盖，不新增通过声明；真实production隔离部署未验。 |
| AT-33 | 结果可核对、不同园区隔离；统计人工配置/代码与回归问题，不预设一键迁移 | park-b独立字段、角色、资源、权限，真实本地业务A有限链；4资源Grant与2Runassignment明确是测试fixture初始化，运行期无新增Grant/registry；旧A保留 | A/B/C是产品§4.3业务分类，不是Case A与Case B。B=审核规则+授权事实三值准备度；C=已存在资源/规则变化→影响/替代→授权执行。第二园区B、C连贯回放未给出；readiness规则仍ENGINEERING_ONLY/DRAFT、qualification=NOT_EVALUATED，因此不能签正式资格业务B完备。人工配置、代码改动、回归问题需按本批准确计量。 |
| AT-35 | 关键状态持久化并能被对应角色操作；不靠手改源码/数据库；不同输入输出不混淆 | V4原角色完成选择→确认→办理→ACCEPT→SUBMIT→ACK→REVALIDATE，历史冷读一致。旧consumer三新输入实际执行已存在 | V4材料/回执错误→反馈补正→复审/重交→确认→重新核验、以及同一V4配置第二不同新输入未串成完整验收。上批B executor run assignment由owner fixture seed，故只能称权限预配置场景，不是新Run权利自助功能。完整Case履约生命周期未实现，不能以LOCAL_OUTPUTS_VERIFIED替代FULFILLED。 |

## 实质功能优先建议：受信选择的显式反馈修订入口

增加一个默认关闭、仅现有owned fixture启用的**只准备候选的反馈修订**能力，复用现有V4候选、原material corrections/objections、原receipt事件和ADOPT，不造第二套执行状态机。服务端投影已提交、当前有权可读的确定性反馈（事件ID/hash、受影响原步骤、有限原因码、必须保留目标、当前来源/计划指纹）。模型只能再选精确受信refs，服务器重建并独立预检；不把模型文字当新服务/授权/已解决。新候选持久绑定前版候选/计划与反馈集合hash；用户明确采用前无业务效果。资料、回执、权限、目录、反馈集合变化都使待采用候选失效。保留同key同参原结果、异参冲突，丢回复只原key GET；STARTED/UNKNOWN不得自动新请求。

最小有用页面行为是原计划内明确显示当前反馈与修订候选的关系、原版保留与受影响步骤，以及“明确采用”后去原办理入口操作。不要把所有反馈原文塞模型；尤其不泄露私有材料、服务执行者无权材料或跨角色原文。结构化原因码也须当前有权并绑定集合，不能仅接收客户端反馈ID声称真实。

必要时先以原补件流程建立一条完整**确定性闭环**，再增加显式反馈修订；仅追加大测试矩阵而无用户可达反馈入口不构成本批实质功能。现有service_case_steps.adopt已经支持binding改变后的显式replacement/history，不应重复开发。material_objections已经有RAISE/RESPOND/KEEP_OPEN/ACCEPT_RESPONSE/REBIND；executor_receipts已有REQUEST_CHANGES/再SUBMIT；应复用。

## 新验收最小串行回放

1. 第二园区新有效输入X：三能力→选择→明确采用；记录精确新ID、six goals、主体/配置/源hash，原A历史全量不变。
2. 原专员针对具体slot请求补件，错误/旧版本/错角色提交明确拒绝，原有效值不丢；owner提交真正不同的新材料，专员复审，owner明确确认。原候选、旧plan当前验证失效；受影响依赖不继续执行。
3. 由当前已提交反馈投影生成修订候选，断连原keyGET恢复，旧版本反馈/缺权限/换目标/跨Case feedback拒绝，原历史保留；owner明确ADOPT，原P1–P5继续，P4有REQUEST_CHANGES→真正不同新回执→ACK→P5重新核验。
4. 同一新配置冷进程输入Y（内容/时段/目标组合确实不同）再跑，Case/Run/prep/plan/receipt/材料ID不复用，X结果不变；不再重跑旧consumer三输入功能充新成绩。
5. 第二园区业务B：已有授权企业事实的TRUE/FALSE/UNKNOWN与当前来源检查，明确local preparation scope，不伪造正式资格结论；业务C：真实资源变更/过期触发影响→替代候选→显式对应权限采用→原业务结果核验，原资源事实保留。
6. 对新增接线执行preview写与原PG真实namespace全表/资源/Grant快照比较。所有写必须原API/适配器；fixture初始化独立列出，执行期间不得用SQL修状态。

上述可在owned Linux PG、进程内ASGI、wholeHTML NodeVM与exact offline MockTransport完成。本建议不要求新Grant/registry、真实provider或部署。真实模型效果、Windows原生启动、Chromium渲染、真实园区投用、完整PR0与正式履约必须继续NOT RUN/未验；禁止将Mock、NodeVM或Linux结果转签。

## 关键源码定位

- 产品§4.3：115–123行，三业务定义；§5.2/5.3/5.5/5.6明确编排/三值/反馈与变化。
- `service_selection_planner.py:compact_context/propose`：精确四项context和单轮compact refs；没有feedback字段或后续反馈轮。
- `service_selection_candidates.py:Capture/current/generate`：三hash捕获，继承原preparation依赖，V4producer；没有feedback修订父链。
- `service_case_steps.py:634`起：原explicit replacement、history、local_revision可复用。
- `service_instance_consumer.py:ParkInstanceConsumer`：只准备CREATE_RUN/CREATE_PREPARATION/SAVE_REQUEST/两slot ADD命令，不自动发送，不含审查/反馈/选择/采用。
- `material_objections.py`：原角色与source-bound异议事件、同key恢复、旧source REBIND；`preparation.py:205–228`是真实slot补件与REVIEW/CONFIRM。
- `model_chain.py:execute`：feedback限定case.create已提交receipt，对V4服务选择无反馈接线。
- `tests/test_service_selection_full_chain.py`：direct/API两种同类B完整链，旧A用于隔离前置。没有补件/回执退回序列，也未一场景再跑不同V4输入。
- `tests/test_new_enterprise_local_chain.py:250`：旧consumer的三份新输入已完成，避免重复。
- `readiness.py:_sources/_evaluate`：LOCAL_MATERIAL_CONTRACT、ENGINEERING_ONLY/DRAFT、qualification_decision=NOT_EVALUATED，严格限制B声明。

## 与集成者比较后的优先级修正：先做①原页面冷输入

上节反馈context是后续可选设计，**不是本批必要实现或固定AT35强制条件**。进一步比较原页面后，首优应为①：让实际ParkInstance新输入无需手写JSON、明确逐阶段提交并GET恢复，再复用已有补件/receipt反馈闭环验证新V4重放。②新增model反馈循环会扩大候选proof/producer版本、隐私与历史兼容面；原固定oracle并不要求每次反馈都必须调用模型，不能为了声称缺功能硬造循环。

已确认的直接用户阻断：`web.html`没有`/api/service-instance-cold-inputs`调用，现只有已存在preparation的/service-capabilities元数据展示和旧template-consumer历史打开。新ParkInstance的外部输入字段目前只能经facade/API传JSON，尚不能从原产品页面开始首个新事项。最小新增范围：

1. 当前本人实例发现GET。现在capabilities GET必须preparation_id，冷启动没有该ID。服务器在现有catalog authority/source lease/当前principal和映射范围内返回有限可用配置的精确ref、input_field→原slot映射及既有有限目标。只查本园区/本企业/本人可用实例，默认关闭；不增发布、Grant、registry。可操作性由原READ/PREPARE/EXECUTE/case.create与当前映射复核；有权历史READ仍独立保留。不可从另一Case借目录或客户端随意填写revision/hash/roles。
2. 页面从可信发现结果生成两份材料表单、目标与原因；文字明确全新材料、合成/本地范围。用户无需编辑JSON，原slot与外部field语义展示可核对。Material.source_kind/source_label用原合同，不发明无来源证明。实例变化则要求刷新/重新确认，不偷偷换配置。
3. 原facade admission POST只保存不可变冷输入和CREATE_RUN命令，不新建业务；页面每个阶段明确确认后仅提交一次对应原API。准备下一阶段是POST描述动作，也不得自动连发后续businessPOST。Run QUEUED/RUNNING只有GET观察，不能假造SUCCEEDED或页面自行finish；由获准原worker完成。
4. 句柄只含当前subject/opaque key/stage身份等最少恢复信息，禁止token、材料正文或整command体入localStorage。页面重启/换用户/切Case清除私有视图；延迟旧响应不能进入新表单。每次commit丢回复后通过现有`/service-instance-cold-inputs/recovery`查original stage key+fingerprint；NOT_OBSERVED并不证明未提交，阻止自动重发/更换新key。
5. 所有Run/preparation/request/material阶段确认完成后，仅打开原preparation/服务选择页；服务选择、ADOPT、资源、dispatch、receipt仍需各自原明确操作，不能冷输入一键自动采用或办理。
6. wholeHTML NodeVM→actual ASGI→owned PG验证：无JSON新输入X完整新链；同配置冷页新输入Y；无效字段/材料、变更配置、跨租户、权限撤销、丢回复/GET-only、迟到页面、默认关闭。运行模型始终exactMock，不签LIVE/浏览器。

这能补AT08/35实际可操作性，并让已有受信选择发挥产品价值。第二园区业务B/C仍按原定义独立列出，不靠新表单称全AT33通过。CI GraphQL Forbidden由root保留并停该动作，不因本功能去其他API或换凭据绕过。
