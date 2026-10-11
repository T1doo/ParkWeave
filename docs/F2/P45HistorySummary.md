# P4/P5 本人历史摘要有限实现

用户已批准凭仍有效的当前READ查看本人历史的产品方向，本片实现原P4 v2/P5 v3纯校验、固定摘要投影及内存只读适配，未启用持久登记或生产API。合同先于实现：[P45HistorySummaryContract.md](P45HistorySummaryContract.md)。正常case.create失联恢复已获接受，本片未重做其既有任务，也不改既有验收结论。

实际实现为`history_summary.py`的`MemoryHistorySummaryReader.read(store, token, preparation_id, key=None)`。通过实际Store的当前active/READ、本人park/org与preparation/Case/Run归属、稳定数据库身份及合成目录/双资源READ，先验权后处理旧记录；EXECUTE、PREPARE、HOLD、接单分配及旧发行者proof不构成独立摘要读取许可。服务端测试内存独立提供固定scope/namespace/database/owner/Case/Run、绝对UTC截止、撤销状态和完整原行摘要的基线，无HTTP输入、自登记、文件加载、续期或新签发资格。

摘要保留旧状态、显式企业决定、事件动作/修订、P5历史Case/cycle与当时校验值；省略正文、标签、理由、报告、proof、参与者UUID及租约。legal版本变化为STALE，当前执行资格NOT_EVALUATED，不把历史verification当现在有效。当前材料必须双槽完整、本人来源及正文/hash相符；数据库仅返回hash匹配布尔，不返回正文，不加extension/Grant。缺材料、不可信来源或任一所需READ、基线期限、归属/完整性失效即拒绝。声明事实用途来源暂无独立READ合同，保守拒绝；缺槽的原FAILED历史也不在本适配器兼容范围，纯校验仍支持FAILED文档。

原API/provider/SQLite存储/live-issuer代理资格不变；新内存对象放入旧provider/client属性仍403。当前EXECUTE/PREPARE/HOLD和执行者接单撤回后的独立摘要读取实际通过，但原GET/POST仍拒绝。正式业务、身份/权限、outbox等原表及产物字节逐案比较保持；原HTTP403 handler仍写authorization_audit，该表按原snapshot明确排除，不声称所有表零写。关闭历史Case仍WAITING_CONFIRMATION，重开仍原cycle2/REOPENED；不真人批准、不正式履约。

源码冻结25740641d03802e50558724c037a40895b00e669，375路径清单2d7e34866fcebe7f5f560f70390eb7f15f46b7f2b6ae40025eaaa76adfe9adc4。仅新增1产品文件/2测试文件；P5两处纯helper改显式原P4基类调用以复用原纯校验，旧资格/API未改；诊断allowlist仅加10固定测试函数。根实际最终新摘要/边界/诊断138PASS（pure46、Store33、诊断59），原P4/P5/API历史代理87PASS。原87在e56窗口运行，相关原源码及依赖对最终SHA保持字节相同，不把旧窗口转签最终SHA；最终精确SHA由独审另行实跑。根225唯一节点collected/JUnit一致，最终两个窗582已知子进程代际核退出，无资源拒绝；旧shared OUT在运行前转为各窗私有路径。

开发3失败保留：1+1 Case列误用、17PASS1FAIL事实声明字段漏读；改后单独窗口通过，原日志/SHA保留。e56独审CHANGES_REQUIRED记录材料缺失/篡改误为STALE及非法row/anchor形状，修为拒绝并补实际负测/合法新材料STALE测试，新SHA再冻结。027精确独审另229PASS1FAIL：合法P5 REQUEST_CHANGES形成FAILED/NOT_STARTED/NEEDS_INPUT历史，被摘要枚举错误拒绝；该源码CHANGES_REQUIRED报告完整保留。根接受修复为允许原NEEDS_INPUT这一历史状态，永久actual用例覆盖仍FAILED/verification_at_execution=false，未补ACK、未恢复任何权限。257重新冻结和实际复验，不将027 PASS转签新SHA。早期PASS窗口不重复计入最终计数，旧P5/正常恢复失败和证据不覆盖。

最终独审LIMITED_PASS：[independent-report-safe.json](evidence/p45-history-summary/independent-report-safe.json)，报告SHA256 822d95297266a275f4a21a8cf44814a3fae1015ae0557c649efaece7fd1b0b43。精确257源码225指定（46+33+59+87）及6独立边界均新窗实际通过，共231PASS0FAIL0ERROR0SKIP，collection/JUnit逐节点相等，无missing/extra/duplicate。原FAILED/NEEDS_INPUT私有反例字节未改且1PASS；过期/撤销后新对象不续期、读取过程中绝对截止、合法Unicode材料版本STALE及资源READ撤销均实际核验。375路径漂移0；611个已知wrapper/pytest/driver/descendant PID代际全部absent，独占资源释放。旧027报告229PASS1FAIL及其日志、JUnit、runner、probe保持，25旧P5/normal安全JSON对base97逐字节保持。通过仅内存/policy/实际只读适配，不签持久启用或全重启恢复。

本轮不做浏览器页面/原生Windows/完整仓库/真实模型与付费/真实批准和履约；无网页接入，原默认门保持。本内存片不证明发行者完全退出、PG重启或持久恢复通过，P4/P5完整持久资格仍OPEN。生产启用仍需明确维护者、管理写/API只读可信边界、精确DB及受信安装绑定、namespace本人/Case范围、绝对截止与撤销传播；没有可信旧基线不能自动接纳。任何持久身份/密钥/ACL/Grant另需明确授权。

Git/网络：本地dev仍97a1d1d5ea5a7f5c7f01fcbf8c6e4972f19789cc，main无本地分支写入，cached origin/main仍31e7acb7e53bb1ab6465b9daae59de28757f7583；origin fetch配置只main，cached origin/dev为aac548，不能冒称当前远端。只读gh Actions查询返回Forbidden后停止网络操作，不重试、不扩大权限/配置，不远端集成推送。候选独立本地branch acceptance/p45-history-summary-20261011待交付；当前远端/既有CI状态未核验，新候选CI未请求。保留存储90%预警，不删除旧证据、改预算/retention、manual-dispatch或反复推dev。网络拒绝解除并正常核远端祖先后，才可按已有授权普通dev快进/单次推送并完成必要原CI；不main/强推/部署。

证据：[source-contract.json](evidence/p45-history-summary/source-contract.json)、[source-freeze.json](evidence/p45-history-summary/source-freeze.json)、[root-report-safe.json](evidence/p45-history-summary/root-report-safe.json)、[开发失败](evidence/p45-history-summary/development-failures-preserved-safe.json)、[e56独审修改要求](evidence/p45-history-summary/independent-static-e56-changes-required-safe.json)、[027实际独审失败](evidence/p45-history-summary/independent-027-changes-required-safe.json)、[027根先前有限结果](evidence/p45-history-summary/root-027-before-independent-failure-safe.json)、[环境与交付边界](evidence/p45-history-summary/environment-delivery-safe.json)。全部仅安全摘要，原日志/JUnit/合成产物私有保全。
