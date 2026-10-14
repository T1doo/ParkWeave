# F2-T02 有界合成服务计划候选消费

从已接受 `3ae2215852c1c2e3aa8080ac4f3dde4d7643cace` 接续原产品§5.2及F2-T02/AT07/AT14，冻结源码 `85869726c1418816478facecc6dc0d21c7cdfdaa`，513个src/tests/scripts文件。只补原Case注册适配器子图的非可信候选ID、确定性验真、原页预览和明确采用，不签收完整T02或一般模型编排。

## 有限来源与验真

provider固定关闭，不调用模型、不读取凭据或扩大预算。合成producer从此Case原保存目标及既有P1–P5合同产出候选；服务端consumer包装生成UUID、actor、原request key和指纹。候选标明SYNTHETIC_UNTRUSTED_CANDIDATE，UUID仅定位，SHA仅一致性摘要，不是授权或真实性证明。页面不提供手填候选JSON、脚本、SQL或新增服务动作的入口。

复用preparations.planning_previews既有有界JSONB，候选和旧capture共同最多16条，不创建表／迁移／Grant／registry。旧capture文档不改写，原预览history不把新非可信候选记录当成原capture，单独显示candidate_metadata_count。READ/PREPARE/当前owner和原CaseRun归属由原auth检查；生成还需当前EXECUTE及Case写守卫，取消／对账状态停止新生成和采用，有权历史读取保留。

每次按ID预览由当前原保存诉求重新编译全部必需目标及完整注册DAG闭包，比较步骤、依赖、角色、动作路径／方法／命令、服务适配器版本、输入、责任、产出、验收及硬约束。Case/Run、资料和诉求版本、source/catalog/registry SHA均进入绑定；JSON以canonical SHA比较，布尔／整数／浮点不混同。validator_version=1及完整合同摘要进入验真指纹。候选不能自证approved/can_adopt或删掉不支持目标／原全局必需条件。

VERIFIED_STRUCTURE_ONLY仅允许原明确采用合同，不表示资料真实性、可接单性、资源容量或履约满足。STALE、REJECTED、UNKNOWN、BLOCKED不能采用；当前登记来源／依赖集合不完整时UNKNOWN不判满足。部分采用仅沿原partial_offer、全部required_goals保留、明确勾选独立部分，整体PARTIAL；不支持项和等待依赖／约束的步骤保留，不自动注册服务或执行动作。

## 同事务采用和历史恢复

原service_case_steps.Adopt增加三个同时存在的可选字段：candidate_id、expected_candidate_sha256、expected_verification_sha256。拒绝candidate与local_revision混用；旧局部修订仍走原合同。新增字段缺省不参与原fingerprint，旧请求字节／原key兼容。

采用仍在原parent→dispatch→Case及原actor key序列化、当前权限／版本CAS内完成，plan候选消费证明、完整adoption_request与原ADOPT事件同事务保存；事件指纹绑定候选三字段，采用步骤合同须与原验证闭包一致。异常全回滚，同key同参返回原结果、异参或跨Case冲突；新候选ID不授予任何写权。

历史证明使用原候选、保存adoption_preview和原请求／事件重核，材料或诉求后来变化不要求旧来源仍当前。候选计划进入history后，缓存ADOPT和GET command-recovery一致核原证明；证明缺失或损坏拒绝。普通当前计划读取也核原首ADOPT指纹，不能通过同时删掉候选消费证明和adoption_request降级为legacy。原legacy后续来源失效／核验投影合同保留，未把全部普通legacy历史后续事件处理泛化重写。

原资料／请求／CaseRun依赖锁和等待后授权重核复用，不新设candidate-first锁。本轮两项owned PG验收实际观察pg_stat_activity父行FOR UPDATE锁等待，再由持锁夹具SQL提交资料revision变化，旧生成／采用均409，未新增记录。这是夹具版本竞争，不冒称原ADD_EVIDENCE业务入口竞争全矩阵。非协作目录publisher最终读取至COMMIT窗口不据此签收为一般发布隔离或原子外部快照。

## 原页面消费与未决边界

当前原Case页面通过按钮生成合成候选、读取服务端原ID、按ID只读重验，显示完整目标、依赖、责任、产出、验收和阻塞。明确候选勾选与原采用原因／partial确认后才提交原ADOPT；取消勾选或版本变化不会自动采用。原无candidate的确定性采用仍保留。

生成前保存最多8条严格名称／六字段opaque句柄（v、actor hash、Case、Run、preparation、key），不持久化正文、token或候选文档。结果未知只GET该原key，NOT_OBSERVED不判失败或重发；COMMITTED核精确当前actor/CaseRun和原key后清原句柄。冷页只重新认证及GET核对，不自动POST。错名／损坏句柄fail closed并保留，不能按任意存储name清理。

候选面板在渲染前核CaseRun、资料／诉求版本、source和当前页面代次；刷新、选择、新Case／诉求和迟到回复不能覆盖新投影／草稿。403沿原清理边界清私有视图，opaque保留。ADOPT提交／未知／恢复期间，选择和列表除UI禁用外，原函数也拒独立候选读取；普通GET读取可由更新代次明确替换。原写入lease复用，候选未知请求交由opaque原key恢复，不堆积独立写。

## 失败原件与已执行开发窗

初始红验2FAIL是缺候选路由404，red原log/XML/exit保留。首个green API2PASS；扩展API26PASS；初次原页6PASS；扩展41PASS；cold/类型5PASS；source-scope46PASS；原页边界13PASS。开发窗分别保留，不与冻结结果相加。

独审发现历史缓存与GET不一致：替换计划后删旧候选证明，GET409但cached ADOPT201，history-red真实API/PG1FAIL；修复后history-green1PASS，合法旧来源与坏证明分别核对。独审又发现双删除降级，double-proof-red真实1FAIL；修复后double-proof-green1PASS，后续legacy-related四模块173PASS包含最终双删除、候选及legacy兼容。proof-green57PASS是此前开发窗口，不替代冻结验收；所有失败原件保留。

原页开发13窗使用完整原HTML在NodeVM调用真实ASGI/owned PG，不stub页面／不手填候选JSON：normal、partial、lost_generate、cold_generate、lost_adopt、cold_adopt、late、late_newcase、late_plan、source_change、pending_adopt、opaque_wrongname、revoke。页面POST只为原候选生成或明确原ADOPT；测试桥setup／故障／权限变更与页面操作分开。每次GET用全public表快照排除authorization_audit比较；正常拒绝审计保留，权限snapshot不由页面改变，不把“只读”说成零审计写。预约资源表也在该快照中，夹具行可为空，不签收已占用容量全部边界。

原环境曾一次exec-server transport disconnected，完整错误已保留；停止该源码读取后，原exec_command pwd成功、原文件读取／编译／Git／71远端heads核对成功，才续原会话。没有新写入者、换环境／工具／网络／权限或堆积拒绝重试。此前red/green测试均结束，无遗留在途测试。恢复证据是该时点原件，不当作后续新源码验收。

## 未验范围

浏览器历史ERR_BLOCKED_BY_ADMINISTRATOR及prepare Forbidden持续停止，无换URL／工具重试。浏览器、prepare、全仓、Windows/native、部署／生产迁移／目录发布、真实或付费模型NOT RUN。通用模型候选provider、任意DAG分支并行、正式ServiceSpec Release/Approval、一般目录发布竞争、真实承诺／履约和完整T02/AT07/AT14仍未签收。

下一步是父级按这一本地有界候选消费合同复核本片；不自动开启provider、费用、发布目录或扩大权限。最终冻结回归、独审及普通分支交付实际SHA在随附证据和交接中列明。

冻结最终根26模块 **678PASS、0FAIL/ERROR/SKIP、2WARN、539.321秒、exit0**；独立最终 **15PASS、0FAIL/ERROR/SKIP、2WARN、9.398秒、exit0**，含10PG/API和5原页，分别统计不相加。根候选13页及既有总览26页均包含在678中，独审5页包含在15中。513冻结文件零漂移，两原approval SHA256均保持c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a。

独审最终正向比较45public表（审计单列），生成仅planning_previews，原采用仅service_case_plan，其余所有列／表不变。独审实际PG锁等待中完整原ADD_EVIDENCE借用已锁自有连接后，真实HTTP ADOPT409；材料端不是独立HTTP。独立初窗14PASS/1FAIL是低级材料helper漏更新parent revision/event，单例首修1FAIL是runtime类名错误；原件都保留，修正单例1PASS之后完整15项重跑通过，不将14+1拼合。

模块数／耗时／每页实际HTTP见[validation](evidence/service-plan-candidates-20261014/validation.json)，[独审](evidence/service-plan-candidates-20261014/independent/review.json)，原件与导出哈希／字节／fixture会话repr行脱敏见[export-index](evidence/service-plan-candidates-20261014/export-index.json)。失败原文尾空格保留，源码／报告格式检查与归档原件空白告警分别记录。

归档首审HOLD发现double-proof-red失败展开中的夹具会话：XML属性与正文／log重复含3个真实合成fixture会话值。公开导出仅替换这3个确切值，共15处（log5、XML10），保留Bearer前缀、字典键、断言／状态／其余失败原文；raw不改，索引记录这一例外。首个精确tuple匹配器假设错误未改任何导出，原oracle错误保留。首审HOLD保全后，修正导出重新独审，不重跑冻结产品测试。

实际源码范围、报告及本轮完整归档git diff-check均exit0；未继承其它任务的尾空格告警为本轮失败。根与独审最终各2WARN为现有Starlette/httpx弃用及XDG_RUNTIME_DIR回退提示，不影响上述实测范围。

最终[归档复核](evidence/service-plan-candidates-20261014/archive-review.final.json) PASS：171项raw/export哈希、字节及精确必要脱敏差异一致，全部会话残留扫描通过；513源与两approval未变，无阻塞。[首审HOLD](evidence/service-plan-candidates-20261014/archive-review.hold.json)保全；两审查原件在171项导出索引之外单独附上。复核脚本首个summary层级读取错误在写文件前终止，已在最终审查原件记载，不改称产品测试失败。
