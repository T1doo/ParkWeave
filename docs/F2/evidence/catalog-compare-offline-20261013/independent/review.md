# CATALOG_COMPARE 离线修复独立审查

结论 **LIMITED_PASS，无代码 blocker**。冻结 SHA `e7c3cdd050465a2cf66cfd3cde5ad303a3dc7b6f`；基底 `83df9d826c93ecfe5e8d73435b7f9ad7f77bf159`。可以按本轮既有授权归档并正常推送离线开发分支 `dev/f2-catalog-compare-offline-20261013`；该分支不匹配现有任何 workflow。前一 VM 许可已消耗，本审查不授权 CI 或新的真实验收。

根因链：原 setup 只给 writer 显式执行权限，未撤销函数默认 PUBLIC 执行权限；既有 collector 通过 has_function_privilege 检查指定 app 角色的有效权限，既有 analyzer 必须拒绝 app:control_system_execute=true。因此证实的是原 setup 与既有保护合同的代码矛盾。PostgreSQL 16 权限文档、acldefault/has_function_privilege 文档、本地 bundled 16.2 的 pg_proc 定义及 BKI、官方 initdb.c 的默认权限处理相互支持。公共文档/源码读取不是 PG 实测，更不是被销毁 VM 的目录快照。

仅新增 `REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC`，位于原 ROLE_CREATE owner 连接事务内的 WRITER_ACL 阶段，后续原 writer GRANT 保留。AST 删除该单一语句后与基底 worker 完全一致；新增语句没有改变 app/writer guard、SQL 角色范围、生产 src、workflow 或旧 docs/evidence。默认 PUBLIC 撤销不会撤销另行显式给 app 的权限或继承权限；既有有效权限检查继续拒绝这类未满足合同的情况，不能把本修复解释为任意现有数据库的通用 ACL 清理器。

独立窗口 **311 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，另 **7项真实 PG 用例 deselected / NOT_RUN**。与主测精确重叠 **305项**，新增 **6项**，不得相加。一个现有 Starlette/httpx 弃用警告。432个源码文件前后 SHA256 零漂移。

新增探针直接调用生产 `_read_catalog`，以纯 cursor DI 断言实际 SQL 使用完整 pg_catalog.pg_control_system() 函数签名和分别指定 pwci_writer/pwci_app，并覆盖四种有效权限组合、app 角色缺失不自动当作拒绝成功、查询异常原样传播。两个返回值再进入真实类型与 analyzer；其余 catalog 字段来自明确的合成 fixture。该测试验证 Python 查询/映射/状态逻辑，不独立执行或模拟完整 PostgreSQL ACL、继承、SQL 事务及权限改变。主测的有限 ACL model 同样只能验证单函数逻辑，不是物理 PASS。

| 项目 | 结果 |
| --- | --- |
| 唯一 worker AST 增量及修复范围 | PASS |
| 实际 reader 指定角色/完整函数签名及返回值映射 | PASS（纯 DI） |
| app 有执行权仍 REFUSED；缺失 app 观察仍 NOT_CONNECTED；异常传播 | PASS（纯 DI） |
| 新分支不匹配现有3个 workflow | PASS（静态） |
| guard、src、workflow、旧证据不变 | PASS |
| 原子事务效果、真实 PG 权限与函数执行 | NOT_RUN |
| 第三次 VM/CI、UID/ACL 修改、浏览器、部署 | NOT_RUN |

两次历史真实 FAIL 完全保留；第二次仍为 3 PASS / 1 FAIL / 13 NOT_RUN，CATALOG_COMPARE 仅定位进入阶段。此次代码缺陷能解释一种拒绝路径，不能声称它是旧 VM 唯一实测根因，不能宣称实际安装、ACL 边界或下游验收已通过。

公开源码 pgcontroldata.c 一次读取返回 Internal Error，已停止未重试，完整显示错误项转录在 public-source-read-failure-transcription.txt，不能据此推断函数实现。该读取失败不是 pytest 失败。本窗口无测试失败。原 XML 含长合成参数，仅保留本地；可归档 bounded projection 和完整散列，不能称其为原 XML。

权威依据：[PostgreSQL 16 Privileges](https://www.postgresql.org/docs/16/ddl-priv.html)、[System Information / Access Privilege Inquiry](https://www.postgresql.org/docs/16/functions-info.html)、[官方 REL_16_STABLE initdb.c](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/bin/initdb/initdb.c)。
