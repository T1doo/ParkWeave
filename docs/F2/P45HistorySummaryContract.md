# P4/P5 本人历史摘要：方向已批准，持久启用未批准

基线dev 97a1d1d5ea5a7f5c7f01fcbf8c6e4972f19789cc，main31e7acb7e53bb1ab6465b9daae59de28757f7583不改。用户只批准“凭仍有效的读取权限看自己的历史，不恢复执行或批准权”。本合同先于实现；root唯一源码/Git写入者，独审仅私有证据。沿原F1-T03/AT04、AT19，F2-T04/T07/AT14–15与原历史保留原则，不重做正常建单失联验收，不签完整AT或全项目。

实现有限片：固定P4/P5纯校验、摘要投影、原文档版本兼容，以及内存基线/内存记录的只读适配器，调用签名与原历史读取相同：read(store, token, preparation_id, key=None)。每次直接用现有Store的实际当前active/READ/企业本人/park/org/Run/Case/preparation归属、合成来源与双资源READ及数据库身份检查，数据库时间控制有效期；EXECUTE/PREPARE/HOLD/审批者/执行者当前租约不是独立摘要读取资格。仅其执行权撤回而READ仍有效可读；任何所需READ、来源、身份、tenant、登记有效期或完整性失效拒绝。当前sources前后核验，明确协作锁/快照边界，不声称全来源原子性。

本片兼容未声明事实用途的原P4/P5产物。已声明fact_clarifications或有DECLARE_FACT_PURPOSE原事件则保守拒绝：事实用途来源的独立当前READ合同尚未实现，不调用其旧执行/签发gate，不拿历史数据补资格。合法的当前材料或资源版本变化可读但STALE；这种历史摘要不表示当前可执行或当前校验通过。

当前两个材料槽必须各有本人已登记来源，正整数版本、已知source_kind及完整hash；仅在现有SQL SELECT权限内计算正文hash匹配布尔值，不返回正文或标签、不加extension/Grant。缺材料、非本人来源、摘要/正文不一致保守拒绝，不当合法版本变化放为STALE；缺槽时的失败历史不在本内存适配器兼容范围，纯摘要校验本身仍识别原FAILED文档。原正文读取接口资格不变。

不是持久访问实现：没有文件/凭据/Grant/租约/管理员或API权限修改；没有新HTTP/IPC协议、生产路由挂接、auto-attach/env开关或基线加载/登记/续期入口。原P4/P5 GET/POST和旧live-issuer代理的精确资格保持；将新内存适配器塞入旧provider属性也须仍403。configured_app默认拒绝，禁止把纯适配器通过称全发行者退出/PG重启恢复通过。

可信基线只由测试服务端在内存提供，不能来自HTTP参数或历史自述hash。绑定stage/scope/namespace、原数据库稳定身份(name/OID/system_identifier)、owner/park/org、原preparation/Case/Run、原合同与版本、每个原记录id/key及完整SQLite行摘要、独立读取来源指纹、显式绝对UTC valid_from/valid_until与撤销状态。没有外部基线即拒绝，不能自己根据读到的历史登记。时间不以新进程启动重算，GET不续期；过期/撤销不能靠新对象或新READ恢复。重建的执行bridge“now+8h”绝非历史读许可。

支持仅已审P4文档version2、P5文档version3及各自原精确execution_contract。先当前验权，后scope/归属/namespace/database/基线期限、记录数量/字节/重复键限制、外部摘要，再原文档结构/hash/proof一致性和闭包语义校验。旧proof只作为被基线锚定的文档数据，不创建、反序列化、登记或重签FixtureDatabaseEvidence，不调用bridge/provider/execute，不能靠hash自证授权。保留旧文档原字节，未知版本/合同、错key/错Case、正文/proof/行元数据篡改或替换库均拒绝，不修补迁移。

只投影固定获准摘要：原记录id/key、P4/P5历史状态、原显式企业决定、历史事件动作/修订、原模拟Case状态/cycle/是否当时校验，SYNTHETIC/NO_EVIDENCE等原限制。省略材料正文/标签、理由、报告全文、proof、参与者身份/其余UUID、资源占位用途、原授权/租约详情和SQL。仅视为过去；当前执行/批准资格不评估或恢复，source_atomicity仍false。来源仍可信可读但版本变化仅历史STALE，不能把原verification_current投影成现在有效。来源未知/撤回拒绝；正文读取本片未实现，必须另按原权限核验。

返回沿原只读history/key envelope：COMMITTED仅当前精确key的唯一原记录摘要，NOT_OBSERVED仅result=null，automatically_replayed=false；summary-only结果不冒充原完整文档/proof或旧IPCtransport。适配器不挂原网页，旧页面相关性/403/迟到回复保护不改。无新业务/schema/权限/outbox/通知/执行写；原拒绝audit按旧API独立列示，本库方法本身无业务写。

合成验证分窗串行：纯边界/版本/篡改/期限/投影泄漏；现有隔离PG与实际原P4/P5产物验证同签名只读、当前EXECUTE撤回仍能摘要而原执行/读资格仍拒绝、READ/tenant/来源撤回/数据库替换拒绝、真实GET入口默认门、所有formal表/旧产物字节保持。只为测试设置内存基线，不产生真实持久授权。短唯一/tmp与私有日志，原OUT重定向，已知自有PID代际退出；资源/访问拒绝停止相关动作，不改限额/锁/未知进程。失败保留，新SHA冻结独审；相关回归通过再普通dev快进推送。

未获授权的持久启用，需要一次明确选择最小集合：维护者及管理员写/API只读可信边界；精确库(name/OID/system_identifier及真实数据目录/受信安装绑定)、P4/P5 namespace与本人/Case范围；明确绝对截止；撤销维护者/状态及失效传播。不存在或没有可信外部基线的旧历史不得自动接纳；建立受信登记、签名密钥/独立身份、任何文件ACL/权限或SQL Grant改变均另批，本片不执行。旧源存储不自动迁移/续权/删除。

既有GitHub Actions存储90%预警：不删除旧证据或改预算/retention，不manual-dispatch，不重复推dev触发；仅最终一次普通dev源码推送的必要原CI，记录实际状态与未跑范围。候选分支不匹配既有push触发。Windows原生与PowerShell故障oracle、真实模型账户/预算/凭据、真实批准/履约/外部回执仍各有前提。本片不是项目唯一缺口，P4/P5完整持久资格/全重启恢复仍OPEN，部署/main/强推/付费/模型/新协议接受均不做。
