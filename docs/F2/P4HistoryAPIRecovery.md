# 原P4历史跨API进程只读恢复：有限验收

运行候选 `ab0ece79710068d6a776e5281a09e01ed2c0c536`，开发基线 `28f7a4f659626c4e2d2c0736bd7827b1ffe41381`。先冻结[合同](P4HistoryAPIRecoveryContract.md)（10570911523a048a8277f63ccfa48f1d52fc5e0c），首候选被独审实际阻断后先补回复相关性合同（771b5a7a1fb7f8911aea5efbb65401637852a197）再修复。363个源码路径manifest `88a41baa8c071be950e67387d17ab0192c3c4092528fed9c8f6386920b2bd4e3`，1599个实际AST诊断测试函数；roles.sql SHA256 `604d084e12d84e9cad808ddd4a7e61289390faca49fd657d2ffe711b5a43afc3`。原P4执行、桥、managed访问、本地适配器、SQL闭包、角色和P1–P3代码/证据保持。

此片是原合法发行进程持续存活时更换API客户端进程。原issuer先通过真实HTTP执行一次原P4并保存结果，再让旧只读API读取；确认旧API实际退出且/proc不存在后，以不同PID启动新只读API，原issuer PID与两者不同。新API proof注册表为空、没有原bridge或本地provider，不向新API传输FixtureDatabaseEvidence、原bridge/lease对象或发行证明，不序列化或重发；仅按既有本地身份入口使用当前token和原app Store资格。读取原ACKNOWLEDGE及REQUEST_CHANGES结果精确保留执行UUID、原文档及hash/企业决定/事件/完整目标/未消费四条outbox；新API不重新generate/SUBMIT/ACK。

原issuer的仅GET Unix代理每次实际调用原ReceiptExecutionPreview.read和原live proof/owner连接校验，没有验权缓存。owner READ/EXECUTE/PREPARE、原获派专员、精确executor/assignment、双资源READ/HOLD、当前managed租约、原provider/proof及源快照仍共同限定读取。撤权、过期、跨企业/错角色、正文单改重hash与缺proof均拒绝且不泄历史。新客户端采用不同只读GET路径，原P4GET/POST仍403，新增历史POST405。原来源换版保留旧报告并标STALE；CHANGES_REQUESTED尚未核对，不自动解决或重绑。

IPC只允许固定六字段READ，4096字节请求、2MiB响应、3秒timeout、单worker/backlog8，0700临时根/0600 socket。逐请求绑定当前原issuer PID/Linux代际/UID、namespace、数据库身份、原P4合同与新只读transport合同，检查目录/socket inode。错operation/version/字段/frame/代际/namespace、socket失踪或替换、issuer真正退出均拒绝，不重新绑定或补Grant。issuer结束后返回503而不把旧授权audit连接到已关闭PG触发500；资格仍存在但拒绝时沿用原403/audit，不改全局验权路径。Linux显式合成测试开关，默认关闭；不开放外部listener或改安全网络配置。

回复必须与手填原key精确关联：COMMITTED只接受同scope/namespace/preparation、正式写入0的原文档，在history中唯一逐值相同；NOT_OBSERVED必须result=null，未知status拒绝。比较保留类型和array顺序、忽略对象key顺序。客户端错配503，页面空结果和明确核对错误；真实loopback返回另一个原key的合法已保存响应不能冒充当前未知请求。页面冷reload不保留token，人工填原ID/key后仅GET；身份/key/preparation改变清视图并丢弃迟到回复，撤权403清敏感结果。1200/390/320实际Chromium无溢出，元数据报告/全目标/P5未执行/Case未完成/未消费通知与正式业务0写均明确展示。

真实HTTP/PostgreSQL/SQLite窗口验证冷API、重复与4路并发GET、上述当前资格/越权/跨企业/到期/换版/篡改/不可用和回复错配。读前后五个原SQLite/RunAccess日志整文件字节保持；全部public业务表逐值及public列/索引/权限不变，排除原authorization_audit诊断表；无新增正式Grant/权限/政策批准、业务写入或外部通知。

| 窗口 | 实际结果 | JUnit / 受控秒数 |
| --- | --- | --- |
| 根冻结24完整相关模块 | 600 PASS，0FAIL/ERROR/SKIP，自然0 | 571.021 / 572.978205 |
| 独立24完整相关模块 | 600 PASS，0FAIL/ERROR/SKIP，自然0 | 567.329 / 569.176274 |
| 独立自写真实HTTP/PG | 9 PASS，0FAIL/ERROR/SKIP，自然0 | 74.270 / 75.167728 |
| 独立自写原页面Chromium | 8 PASS，0FAIL/ERROR/SKIP，自然0 | 71.454 / 72.470365 |

以上窗口分别保全，不累加成一个通过数。根24完整模块覆盖新历史API/页面和原22模块P1–P4、source CAS/幂等/提交保护/失响应、规划/资料/managed资格、资源/分派/通知/回执/本地适配器。独立自写probe另行验证原key错配修复、合法不同API冷页面、迟到key/preparation、socket替换/错误frame、当前门、原body-proof与readonly/formal0。该回归覆盖已有提交/执行行为，不能声称新增P5或完整AT14。

首候选 `2c964296488e42f2b162589b12e919647c96c13f` 的独审BLOCK永久保留：浏览器输入实际NOT_OBSERVED的independent-never-sent，却显示另一实际已提交key的CHANGES_REQUESTED报告且无错误，是真实产品失败（1FAIL，JUnit8.667/受控9.866557秒）。首SHA根597PASS（535.236/537.004210秒）、独立597PASS（523.565/525.465667秒）及8API PASS不能抵消它，也不作为新SHA验收。原独审报告hash `9a7606b3933c9f88f2459a1ab701ff999999ba674b973c3de5e1ba6b5ff5d962`、失败XML/log/320截图及安全观察hash全部保全。开发原factory观察器1FAIL、issuer退出后audit死PG500产品1FAIL、诊断inventory观察器assert失败同样保全；失败原raw含合成私有连接/身份片段，只留private.runtime及安全分类/hash，不公开。修复开发82PASS和后续规范JSON/API+页面5PASS是mutable窗口，不冒充冻结验收。

独审LIMITED_PASS仅签收上述原issuer存活下跨API只读范围。[独审原报告](evidence/p4-history-api-recovery/independent-report.json) SHA256 `5b200adb60130a9c2a26936e5d061eabcc29116f9ff7d1f67ba71cdc5b3d33f8`；[根冻结结果](evidence/p4-history-api-recovery/root-frozen-audit.json)、[首SHA阻断报告](evidence/p4-history-api-recovery/blocked-first-sha/independent-report.json)、[首SHA错误编号画面](evidence/p4-history-api-recovery/blocked-first-sha/wrong-key-response-320.png)、[修复后320px原CHANGES/STALE](evidence/p4-history-api-recovery/root/changes-stale-320.png)、[逐文件hash](evidence/p4-history-api-recovery/artifact-hashes.json)。原private路径/原hash保留，安全公开副本逐字节比较并重新锚定公开相对文件路径；原失败raw仅private保存。

恢复限原issuer存活，不签收原发行进程终止后证明生命周期恢复、PG重启/WAL、真实材料服务交付/线下履约、真人批准、新权限、正式Grant/政策审批、Case完成、P5、模型/外部通知消费者、完整AT14/全仓/native Windows。source_atomicity=false，STALE/SNAPSHOT_MATCH仅快照比较；同UID管理员控制源/证明/锚联改不在防护声明内。旧Windows Job/accounting未推送修复延后，资料包导出不重做。此项比原新PID403拒绝边界增加合法跨API GET成功，不将issuer重启拒绝说成成功恢复。

根唯一源码/Git写入者；修复运行候选普通push后冻结与独审，所有窗口自然结束/资源关闭/源码零漂移且获有限审查后才仅追加安全证据文档并ff-only开发分支普通push。main、凭据、安全配置不改，无部署/强推。失败证据与未推送私有日志保留。
