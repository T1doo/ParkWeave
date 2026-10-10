# 原P1注册材料链的隔离执行预览合同

基线 `f5f187fb1a390e724a3b471f82243425349b4f85`，原§6.3/F2-T02/AT14。原controlled-plan/preview仅结构与来源检查、planning-preview仅确定性子图与元数据持久化，均executed=false。原冻结覆盖表保持NOT_RUN，不把已有SYNTHETIC业务链当隔离执行。先冻结本合同，再实现。

## 最小实际执行与边界

仅已登记 `P1 / preparation / revision1`、原合成资料服务version1及其原ADD_EVIDENCE、REVIEW、CONFIRM动作。新执行必须精确匹配P1原adapter/ref/revision、无依赖、method/path/role/commands完整动作声明和服务ID/version；改变任一项仅可读历史，execution_available=false且新POST409，不以旧动作伪装新注册合同。读取当前owner合成资料两槽及原完整目标、Case/Run/资料revision/请求revision/目录和registry/source指纹，全部目标保留。P1存在且目录来源已知才可明确预演；其他已选P2–P5或不支持目标列NOT_PREVIEWED/UNSUPPORTED，整体仅PARTIAL_PREVIEW，不省略目标或开放任意图/脚本/SQL/动作。缺槽可实际进入原REVIEW产生已知FAILED，不能假填成功。

原动作函数preparation.command实际执行两次ADD_EVIDENCE、独立合成reviewer的REVIEW、合成owner的CONFIRM。输入为当前两槽实际文本/来源种类/标签，不接受任意路径、Grant、角色、命名空间或生成动作。动作的授权与CAS/幂等/缺槽/审核hash检查仍运行；不把预览reviewer冒称原获派真人或正式审核。预览对象/Case/Run/材料/event全部新UUID，actor为带共同新UUID命名空间的独立合成ID，与原对象只存只读绑定关系。

执行用新专属PG连接，在一个事务创建只含所需固定表的pg_temp影子表、无FK/正式触发器；执行search_path仅pg_temp（pg_catalog隐式），没有public回落。原Store动作通过只持该连接的代理运行；代理只接受本原动作实际使用的18条精确SQL模板，禁止显式schema、DDL、事务提交、未知SQL与set_config/advisory-unlock等SELECT副作用；不能借函数修改search_path回落正式表。临时角色/READ/EXECUTE/PREPARE/REVIEW_ASSIGNED仅本预览生成，真实principals/Grant不复制/写入。既有app TEMP数据库能力缺失即拒绝，不补权限。无资源/Approval/dispatch/notice/正式成果表影子或执行能力。正式源连接仅认证/只读来源核验，原授权锁和父行锁保持到隔离产物提交；提交SQLite前再次读取规划来源，执行期间观察到的目录/registry变化即409不保存产物。原principal/父行协作锁保护原资料与撤权协议；目录/registry最后一次取样之后的无协作写入不承诺跨SQLite/PostgreSQL原子线性化，下一GET按当前来源标记STALE，历史产物不变。没有正式Case、材料、计划/preview metadata或其他业务UPDATE。

每次执行结束均显式ROLLBACK/close该临时连接。真实隔离材料、不可变动作事件与原snapshot hash由实际SQL读回，写入专属本地SQLite预览命名空间；SQL临时写是真执行，持久结果仅预览产物，不是原材料/Case成果。不启动worker、模型、网络外部调用、资源占位/释放、政策批准、Case完成或通知。

## 有界持久化、幂等与恢复

明确本地合成配置才attach该存储；默认configured API无预览存储/执行能力，读状态disabled，不建文件/表，不自动创建/恢复授权。存储根为显式新建0700私有普通目录、DB0600；拒绝symlink/foreign目录/外来schema，既有本类库须严格marker/schema核对，不自动迁移/清空/chmod。完整预览实例UUID/版本化合同/原数据库身份绑定，以current_database/pg_database OID/pg_control_system.system_identifier三者绑定，Unix socket没有端口也不能混用另一实际cluster；该只读函数须既有app可用，否则拒绝，绝不补Grant。跨库拒绝attach。SQLite存储格式version2，单列不可变proof独立锚定原Case/Run/资料/请求/双槽绑定、完整required_goals/goal_coverage/not_previewed/coverage_state和执行合同hash；正文重算sha也不能省略目标或改变覆盖。读取/恢复/重放均比对独立proof；历史仅比对当时proof，不强行替换为新诉求。每次打开均重新验证meta的scope/version/实例UUID/实际cluster/database，条数、单文档和proof各最多64KiB，拒绝损坏或超限。旧version1库明确拒绝，无自动迁移/清空/修补。SQLite独立事务BEGIN IMMEDIATE；最多128结果、每Case最多16，max document64KiB，超限拒绝。不得将该库接入业务读者、Case结果核验或正式动作。

命令body仅expected_preparation_revision、expected_request_revision、expected_source_sha256，原actor/Case/Run/两槽ID/version/hash/完整目标/登记动作指纹由服务端绑定；idempotency key与owner+原Case+完整body指纹绑定。当前READ/PREPARE/EXECUTE先于历史重放及恢复。相同key/body仅返回原结果；不同body/Case409，未知keyGET为NOT_OBSERVED，不能据此认定原命令失败；并发不同key各自独立预演，不写正式对象，相同key至多一持久结果/事件链。

原动作产生已知领域Conflict时回滚临时事务，保存FAILED结果与已有隔离事件/材料副本（明确未CONFIRMED），不会把部分执行变为正式成功。修补原输入后由用户明确新key/当前来源重跑，旧FAILED/history保持；来源变化只显示STALE，不改旧产物。基础设施/存储中断不保存虚假成功；事务回滚，GET核对后由本人明确决定重试，禁止自动POST、自动续写部分步骤或通知。

页面沿原bounded-planning区增加明确执行按钮和原结果/历史/只读恢复控件，不新检查页。关闭/换Case/身份/编辑/403清旧私有投影，迟到回复不得复活。丢响应仅存最多8条、24h不透明句柄：资料ID/key/原revision/原sourcehash/到期；第9条活跃句柄拒绝新POST，不能FIFO淘汰未核对旧请求；GET/POST回复及明确释放前均重验持久句柄的全部五字段和TTL，变化拒绝显示/删除，须再次只读核对。无token、正文、理由、姓名/角色/Grant或完整产物。重新认证后GET恢复，失权清私有视图；结果显示PREVIEW_EXECUTION、SIMULATED_ROLES_ONLY、正式写0、Case目标未完成，显式释放核对后才允许新预演。

## 冻结独立oracle

| 输入/操作 | 预览存储实际应变 | 正式表/权限/资源/通知应保留 |
| --- | --- | --- |
| 当前双槽完整，P1原链 | 新namespace、两真实ADD材料、REVIEW及CONFIRM四事件、原实际hash匹配，LOCAL_CONFIRMED只在预览 | public全部业务表/Grant/目录/正式材料/Case/Approval/资源占位/通知逐值相同；不排除planning_previews |
| 缺一/两槽 | 原REVIEW真实Conflict→FAILED；部分预览产物明确未确认 | 正式全部相同；旧真实review/产物不被采纳 |
| 原资料补齐后本人新预演 | 新完整产物，旧FAILED/原ID/事件/来源保留STALE | 预演本身正式全部相同；仅此前明确原ADD可能改变原业务 |
| 相同key并发/丢201响应 | 一持久结果；旧keyGETonly、冷热页/新API实例仍同ID/hash/events | 正式全部相同，0自动POST、0重复正式效果 |
| 撤权/越权/跨企业/改source/CAS/keybody | 403/409；原预览库不新增/不改历史，403私有视图清 | 正式业务全部相同；既有拒绝审计可按原API写脱敏记录，单列 |
| 原动作中断/SQLite提交前中断 | PG临时事务销毁、无SUCCESS/不完整持久确认；GET NOT_OBSERVED | 正式全部相同，恢复不盲重发 |
| 将预览UUID用于原Case/材料/资源/Approval命令 | 原权限/归属/存在性拒绝，无消费 | 正式业务及权限相同 |

真实HTTP/PostgreSQL/Chromium测试需全public逐值快照（仅脱敏authorization_audit单列）、独立SQLite结果重开回读、实际原函数调用、临时relation命名空间/connection关闭、错误输入/失败修补/基础设施中断、CAS/key并发/失响应/冷热恢复/撤权/跨企业/迟到回复/原页320/390/1200与隐私负例。独审精确候选普通push后冻结源码，未审不合dev。仅原P1注册链，不签完整AT14、一般图/全部资源执行、正式服务发布、Windows/fullrepo/fullAT或真实履约。旧失败保全，main/强推/部署/凭据/安全网络配置禁止。

补充冻结（修复前）：首候选 `7dd4ada06847b5eae7da32d228c6b20877ae4748` 独审实际6FAIL/BLOCKED（3个单正文重hash省略目标/覆盖、3个P1动作声明漂移）。该候选root252PASS不抵消阻断；独立报告hash `071dbc5bbe2851996d57f7062a5995ec30922e4058e72bbd070f395114e89a8d`，原私有日志与观察器故障窗保全。本补充先commit，再实现与重新冻结候选。
