# ENG104 显式创建回执适配候选

基线完整SHA `25af47e270837aa30627d4f4dc47a2a8bf76cca8`。本轮按原离线合成授权实现代码与测试，不停在设计文件；不挂载 Windows setup、pytest native入口、API或CLI，不执行真实 installed Windows/owner/ACL/security 操作，不新增生产/演示授权合同、持久身份凭据或生产默认权限。新adapter及其专用测试不写角色/Grant；184原回归只沿用既有隔离fixture初始化，不把测试授权当实际新Run授权。模型预算0/R4关闭。

## 代码与实际保护

新增 `parkweave.installed_fixture_receipt.create_installed_synthetic_database_receipt(maintenance_dsn, target_owner_dsn, expected_data_directory)`。调用方必须已经获准使用这些明确的既有连接身份并创建此新合成数据库；函数名、布尔值或“批准”文本不代替授权。

两个DSN在打开任何连接前校验：维护库精确postgres、目标精确parkweave，相同显式numeric loopback host/port/user，拒绝多host、service、options、passfile等隐式输入。拒绝任何继承PG*配置而不修改环境。v1要求明确sslmode=disable、libpq>=17，限定trust/password/MD5/SCRAM，禁GSS/SSPI/OAuth与默认证书/口令文件发现。TLS、远端或其他认证输入直接拒绝，绝不静默降级。连接参数语义参照[PostgreSQL官方libpq文档](https://www.postgresql.org/docs/current/libpq-connect.html)；实际支持范围以本轮测试和显式拒绝为准。

issuer先读取实际维护集群system_identifier/data_directory/postmaster_start/current/session/database owner，确认精确目标不存在；自身成功执行CREATE DATABASE parkweave后，读取实际新OID并在目标连接重新检查cluster/start/OID/name/owner，才发行不可变、进程内registry精确对象与PID绑定的NativeDatabaseCreationEvidence。没有纯before/after观察即发行、名称白名单、Windows目录所有权推断或文件恢复receipt。DDL-capable owner本来可绕过SQL，不把此机制称为对该owner或恶意进程内代码的安全沙箱。

已有目标（包括空库/schema24）、创建竞争/异常/超时、成功不明或后续绑定不匹配均不发行，不自动DROP、重试或修复授权。创建连接的lock_timeout=3s、statement_timeout=10s仅约束issuer查询/CREATE，不承诺所有Store迁移的总时限。调用者的Store连接仍由其原DSN建立；不能把issuer两个连接的认证隔离声称为所有后续连接的认证策略。

Store仅接受原FixtureDatabaseEvidence和新NativeDatabaseCreationEvidence的精确类型，不做duck typing；每个issuer都独立检查发行来源与当前live身份。原fixture capture规则/registry不放宽。共享私有helper只提取原temp ticket DDL/DELETE/INSERT，原loader同连接/事务调用；SQL025实际执行正文逐字节不变，仍校验精确一行、owner/cluster/name/OID/backend/txid/nonces/schema24/表owner，COMMIT/ROLLBACK清除。无receipt的原installed setup/schema<25仍拒绝，schema25原no-op兼容保留。

## 实际针对性验证

| 独立运行 | 实际结果 | 范围 |
| --- | --- | --- |
| 新adapter模块 | 68PASS/0FAIL/0SKIP/2WARN，3.11秒 | 拒绝seams与真实自有Linux TCP PG，不是Windows |
| 原相关六完整模块+十精确原升级节点 | 184PASS/0FAIL/0SKIP/2WARN，69.79秒 | 原事实/事务票据/资料复用/启动/legacy升级，不拼成full |
| 原diagnostics/shards | 101PASS/0FAIL/0SKIP/1WARN，4.17秒 | 更新后的真实ID/manifest与脱敏合同 |

新模块实际PG正例自身CREATE新parkweave并由原Store同事务迁移25；已有24默认无receipt/任意方法对象拒绝且不改数据；真实autocommit/foreign DB拒绝、owned cluster重启失效、提交/回滚清票据及新事务重绑、八字段SQL票据篡改拒绝并回滚。copy/deepcopy/manual/subtype来自真实发行对象的拒绝；PID与live metadata字段变化是显式注入负例，CREATE/连接异常与未知结果是unit seams。没有模拟正例发行，也不称实际Windows进程重启/SET ROLE行为已验。

三份运行各自actual collection与同次JUnit raw nodes精确一致，均为新2369全局keys的子集。五个变更的实现/测试文件运行前后hash0差异，独立源码审查无实质阻断。collect-only 2369/84文件、四片606/566/632/565、1078真实AST诊断IDs、133实现bindings；旧2301（含full actual）/2296/2194/2183 keys全保留，预算/workflow/旧分配不变。不重复未变化完整工程，旧2292PASS全量只属ENG102冻结源；本轮无新全量PASS或native验收。

证据见[ENG104机器记录](../integration/ENG104-CreationReceiptEvidence.json)。正常dev同步与首次精确HEAD Server CI另留终态凭证，Server隔离Job测量不是Windows应用/Win11验收。

## 授权对象的精确现状

当前没有存活临时合成库、执行者或可绑定Run。最后冷走查曾用自有临时集群的parkweave，目录/tmp/pw-cold-0ea9ed1da0/data已删除，API/worker已退出；历史Run `12df6ade-577d-415d-ad9e-44734e590f44` 与Case `4ecc2c76-40fb-41a1-b664-6e0a7f957688` 随库销毁，不能拿它们作当前授权对象。

那次driver只初始化fixture-a/b/c与prep-specialist-fixture-a/b/c，没有任何service_executor/receipt-executor主体或READ Grant。此前“已有执行者身份”只描述Linux启动器明确receipt-fixtures分支的原初始化合同，不能套用到这次走查。建议的receipt-executor-fixture-a也不是当前存活身份；必须先核实原合成夹具初始化是否在既有授权范围、再核实际新库/tenant/主体READ和完整新Run UUID，本轮不猜填或创建该授权组合。

如获准给现有执行者写精确单Run active assignment，它开放Run读取、进入同Run执行者目录及后续被独立分派的本人offer读取、ACCEPT/DECLINE、已接受事项SUBMIT有来源的本地合成回执；企业原ACKNOWLEDGE/REQUEST_CHANGES/REOPEN不因此转给执行者。仍无EXECUTE/CONTROL/FILE_READ、审批、目录管理、其他Run或外部履约权。全部业务与来源必须合成，资格未知。当前实际只到事实和双角色资料确认，未写新Run绑定、分派或回执。

撤销沿原owner安装方法assign_status(principal_id,run_id,active=False)，精确当前绑定并用现有授权锁序列化；未来请求重验assignment，不能沿用旧缓存作权限。没有TTL、自动到期或新的审批/撤销审计合同；撤销不删除已有业务历史，也不能收回已经读取/复制的信息。临时库正常删除是夹具生命周期，不是TTL；未知清理结果必须保留并另核。不在本轮调用该方法。

## 还缺的原生验证

下一原生最小验证应另行明确一个已批准本地installed PostgreSQL目标：显式维护/目标owner身份、可核实的data directory、目标parkweave确实不存在、已安装libpq>=17且满足v1认证范围。仅在获准创建此新合成DB的范围内验证实际Windows同进程CREATE→真实新OID/cluster/start/owner→原Store同事务SQL025与回滚/重启拒绝，并保留失败结果；不顺带角色/GRANT/owner/ACL/security初始化。

当前实际installed维护对象/权限与原生结果均未提供，不能由Linux成功或ServerCI代替。原native pytest默认门与lifecycle不启用新adapter；显式入口集成、实际应用最小SQL权限和受保护Windows安装流程各按原暂停边界处理。F1未签收/F2并行、PR0完整目标、42AT/EX与T06/AT08/AT35、Win11仍未验收。
