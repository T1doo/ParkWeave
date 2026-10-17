# 自有夹具连接诊断与原失败定向复验

基线 `96b37e1d9fd53e005bcb8a06c6e8df62f2a90ab0`，本批最终冻结 `8ff6f34ad68c36c0c529957a6edaf2c25e5bbb38`，分支 `dev/f3-runtime-connection-diagnostics-20261017`。父线程独审局部认可上一批只读接线及新增36项，独立解析的是429个JUnit元素/427唯一、425PASS/2FAIL/2teardown ERROR，完整门仍阻断。本批只诊断原连接及夹具生命周期，不叠加业务功能；全部产品 `src` 与基线相同。

**本批同一新冻结完整窗427PASS、0FAIL/ERROR/SKIP；历史超时根因仍未确立。** 本批没有推测性产品修复，也没有把插桩后成功当作历史问题已解决。新诊断片独审尚未执行，完整项目未完成。

历史失败分别为回执403后的owner业务快照 `Store.connect` 握手超时，以及 `WriterClient.invoke` 发送ACTIVATE之前的app预检握手超时。历史PG残留session无法与失败连接关联，因此不判为环境问题。上一批原日志与全部失败窗口留在原交付及原封存路径，不改写或迁移成绩。

## 有界诊断

`--owned-connection-diagnostics=<新输出目录>` 是仅pytest使用的显式选项。默认不启用；不进入产品启动配置或业务API。插件只识别本pytest实例通过原 `pg` 夹具创建的物理数据目录和Unix端点，以及其自有UUID数据库，其他连接直接调用原函数。支持原重启测试手动调用的第二个自有集群，登记项仅为端点/路径/连接字符串，不保留pgserver对象或数据库连接。

每次连接添加短 `application_name`，记录尝试编号、原预算、连接类、原调用点、单调/UTC起止、节点/阶段及进程/线程；成功时记录backend PID。原 `Connection.close` 调用前后记录单调时间及closed状态。只增加诊断参数，不重试连接、替换驱动、修改原2秒预算或吞掉原异常。writer侧沿原私有bootstrap传递的已有DSN仅加application_name，密钥与角色不变；原子进程退出/信号/回收事件另记单调时间。新诊断只转发既有观察器中的生命周期事件，不转发业务观察载荷。

插桩会增加启动包元数据与本地日志写入，可能扰动调度；本批成功窗口不能等同于未插桩环境的重复证明。实际运行版本为Python3.12.14、psycopg3.3.6 binary、libpq180006，没有换驱动或增加超时；完整依赖清单与版本原件一并保留。

本次新建的自有PG目录经实际 `SHOW data_directory` 核对后，仅启用连接/断开日志及PID/session/application_name前缀，关闭错误参数值记录。没有修改认证、角色、授权、安全边界、端口或网络设置。PG日志是服务器UTC毫秒时间；客户端同时记录UTC与单调纳秒，保留分辨率差异，不能把服务器日志当作单调时钟。

连接失败或用例失败时，每个失败fixture数据库最多尝试一次短维护连接：原2秒连接上限，1秒statement/0.5秒lock预算，只读 `pid/application_name/datname/usename/state/wait_event_type/wait_event/backend_start/xact_start/query_start/state_change`，最多64行。没有query正文、token、凭据或RPC载荷，不保留常驻观察连接。原连接失败的起止先记下，随后采样的耗时另记；观察连接自身失败时只记录类型，并明确没有返回连接的关闭状态未知，不把采样成功作为前提吞掉原失败。

运行器额外递增复制本轮自己的PG日志文件，不导入pgserver、不连接数据库、不持生命周期引用；夹具清理前也保存各自日志。常规fixture结束之前的日志可以关联，不保证含pgserver最终atexit删除目录前的所有关闭尾段。默认Uvicorn/worker子进程不被pytest连接函数补丁替换；本批客户端尝试级诊断覆盖pytest进程，writer独立进程连接按其application_name和服务器日志观察，不能称作所有进程都已插桩。

## 定向与诊断自身修正

按旧全序选择各失败的两个紧邻前驱及失败节点，共六项，顺序不变：

1. `test_material_change_after_real_parent_lock_wait_refuses_activation`
2. `test_expiry_after_real_parent_lock_wait_refuses_activation[2]`
3. `test_real_expiry_during_receipt_endpoint_rolls_back_all_business_writes[3]`
4. `test_unsigned_json_cannot_add_metadata_participant[True]`
5. `test_unsigned_original_get_is_explicitly_unverified_and_never_repairs`
6. `test_verified_recovery_becomes_unverified_when_writer_offline_without_changing_history`

三个有源码hash记录的开发定向窗口均6PASS：首窗19.65秒/230连接，第二窗23.252秒/231连接，第三窗23.826秒/231连接。各窗都保留原403、业务快照相等、实际访问拒绝、writer退出后的原键恢复/未验证状态及清理断言。三窗成功连接均与同名backend PID的PG授权及断开日志关联，且无未观察到close的成功连接。未出现ConnectionTimeout，失败时pg_stat_activity采样尚不能由这些成功窗口证明已执行。第三窗五个变更文件的实际SHA256与最终新冻结一致；定向开发成绩不加入完整427项。

首完整窗冻结 `55bb74ef14f3df254703ccc83869a1d599253eab`，收集427，执行到32个PASS时，静态复核发现诊断修改破坏原 `pg.__wrapped__(tmp_path_factory)` 手动调用契约，且单集群登记不足。核验本轮pytest PID及独有参数后发送SIGINT，未等到该潜在不兼容测试执行。该未完成窗还实际暴露插件自己的sessionfinish先关闭日志fd、原runner之后清理夹具而触发BadFD；原始输出保留，进程退出1，JUnit没有表示这段清理错误，不能按32PASS称完整成功。

随后恢复原pg函数签名、分别登记多个自有集群、限定生命周期事件转发，并以trylast在原runner夹具清理后关闭诊断。普通定向夹具清理已通过；修正后的再次SIGINT清理未另行实测，不能把它当作历史2秒连接超时的修复。两失败函数的原断言AST与基线完全相同，产品连接/权限/业务算法和原期限、清理断言均不改。

## 证据与未证范围

最终完整窗 `full-v2`：**13完整模块、427唯一/427JUnit元素、427PASS、0FAIL/ERROR/SKIP**；JUnit677.502秒、pytest墙钟677.54秒，4原警告。实际节点及顺序与原收集集合完全一致，两失败节点、各自前驱及新增36项都包含于427中，不另累加。实际物理PG重启用例亦通过，两个自有集群日志分别保存；未改原期限、403回滚/离线恢复或清理断言。

本窗记录8750次受测连接，全部成功并观察到close_end且closed=true，全部通过**精确application_name＋backend PID**关联PG授权及断开记录；插件结束时未观察到close的成功连接数为0。最长实际连接约437.455毫秒；这只是本窗测量，不能代替历史2秒失败的根因。writer准备、停止、SIGINT、回收事件保留客户端单调/UTC时间，PG断开记录保留原服务器时间。原始JSONL及逐连接关联表可独立复核。

没有自然连接失败，因此本窗单次pg_stat_activity采样尝试/成功均为0；只读采样实现已加入，但**失败采样通道未被本批成功窗口实际触发**。没有历史失败连接的application_name，无法事后补关联旧残留session，不能判断历史问题来自服务器、客户端、调度或环境。成功窗口证明原回滚/离线恢复断言在本次执行通过，不证明历史根因修复。

新冻结716输入及27289份继承证据hash在封存前再次核对为零差异，全部产品src与基线相同。新诊断片独审、未插桩重复执行、修后再次SIGINT清理、真实失败采样路径均未验；不据正常清理成功冒称这些边界通过。源码和文档格式检查单列；失败日志/XML保留其原有行尾空白，不为格式检查改写原件。

公开入口：[gate](evidence/owned-connection-diagnostics-20261017/gate.json)、[完整JUnit](evidence/owned-connection-diagnostics-20261017/full-v2.xml)、[原始测试日志](evidence/owned-connection-diagnostics-20261017/full-v2.log)、[连接/关闭JSONL](evidence/owned-connection-diagnostics-20261017/full-v2-diagnostics/connections.jsonl)、[逐连接关联与writer时间](evidence/owned-connection-diagnostics-20261017/full-v2-analysis.json)、[全部失败台账](evidence/owned-connection-diagnostics-20261017/failure-ledger.json)、[原件/公开副本配对](evidence/owned-connection-diagnostics-20261017/public-pairs.json)。私有原件保留于本实例 `.runtime/runtime-read-diagnostics/`；公开副本脱敏源常量/已审历史合成参数之外的43字符会话候选，逐件保留原件与副本hash，JSON/JSONL/XML解析及所有JUnit节点序列复核。结构化诊断检查未出现token/DSN/凭据/query/RPC载荷字段；该字段检查及格式特定的候选检查不声称通用秘密扫描。

首版导出曾把自身尚在写的完成日志列入原件，随后配对校验发现仅该日志hash变化，测试/诊断原件未变。首版保留在本实例 `export-v1-self-log-check-failed/`，排除活动导出日志后重新生成；[封存校验失败记录](evidence/owned-connection-diagnostics-20261017/export-v1-validation.json)和两个导出器版本均保留。最终401份配对重新核验，不重跑或更改测试结果。封存后环境一度报告启动中；等待就绪后重新读取实际HEAD、文件与测试退出结果，未假定跨实例共享。

没有Actions查询、main修改、强推、部署、真实模型、新费用、真实身份/Grant/分派/批准/凭据、安全网络权限变化，未删除未知锁/进程/session。普通资源方案Approval契约及原真实运行合法输入仍缺，沿[上一批精确清单](OrdinaryRuntimeReadWiring-20261017.md)拒绝；Windows原生、正式AT/AT35、真实业务/来源/批准、实际受保护生产host正向与部署仍未验，完整项目未完成。
