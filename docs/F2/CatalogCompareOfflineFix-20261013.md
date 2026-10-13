# CATALOG_COMPARE 离线定位与最小修复

已证实并修复一个 setup 合同矛盾：向 writer 单独 GRANT 函数 EXECUTE 不会移除 PUBLIC 的默认 EXECUTE，因此普通 app 仍具备 `pg_control_system()` 的目录执行权限，而既有预检明确禁止该权限。该缺陷可用原 worker ACL 代码和生产模型往返纯复现；不能据此声称它是已销毁 VM 的唯一实测根因，也不能把旧真实 FAIL 改签 PASS。

原执行源码 `4649970278e29b999a2a4f332ba7380f20795a3f`，修复基底 `83df9d826c93ecfe5e8d73435b7f9ad7f77bf159`，冻结修复源码 `e7c3cdd050465a2cf66cfd3cde5ad303a3dc7b6f`。独立分支 `dev/f2-catalog-compare-offline-20261013` 不匹配任一 workflow；本轮没有 CI、PG 连接、物理进程验收或实际权限变更。

PostgreSQL 16 的 NULL 函数 ACL 采用内建默认权限，其中包括 PUBLIC EXECUTE；首次 GRANT 先实例化这些默认权限再叠加指定授权。[官方权限说明](https://www.postgresql.org/docs/16/ddl-priv.html)说明这一行为。只读检查本地 bundled PostgreSQL 16.2 的 `postgres.bki` 和 `system_functions.sql`，确认 `pg_control_system` 的 bootstrap ACL 为 NULL，且该 SQL 文件没有改写它。文件版本、完整 SHA256 和该固定目录行保存在 `catalog-source-evidence.json`；它们属于源文件证据，不是旧 VM 的目录快照。

原 worker 对新库执行 `GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer`；collector 用 `has_function_privilege` 读取 app 的有效执行权，analyze 要求 `app:control_system_execute=false`。纯测试提取并执行原 worker 的整个 ROLE_CREATE/ACL 块，没有另抄一份待测 SQL。有限 ACL 模型只解释这个函数的 PUBLIC 默认和直接 writer 授权，由此生成关键 app/writer 权限值；其余目录事实仍为合成输入。随后使用真实 `InstallationSpec`、`CatalogSnapshot` 校验和 model_dump 往返，并执行原 CATALOG_COMPARE 块。

| 纯输入路径 | 分析器结果 | changes | 原比较守卫 |
| --- | --- | ---: | --- |
| 原 ACL 代码、默认 PUBLIC EXECUTE | REFUSED，唯一非 PASS 检查为 `forbidden.app:control_system_execute` | 0 | 抛原固定 AssertionError |
| 最小修复后的 ACL 代码 | PASS，app=false、writer=true | 0 | 通过，但所有安装/启用 authority 仍 false |
| 缺一个规定列的合成控制 | APPROVAL_REQUIRED | 1 | 拒绝 |
| 已通过 policy 模型但含非 JSON object 的 generations 控制 | TypeError，未返回报告 | 不适用 | 异常传播 |

最后一项仅区分“分析器抛异常”与“返回不满足条件的报告”；真实 worker 的 generations 查询产出 text 字段，并未发现它会产生该 object。旧 VM 的 `CATALOG_COMPARE` 检查编号同时覆盖 analyze 调用及 status/changes 守卫，仍无法从旧公开摘要确定它当时走了哪一条分支。

最小修改只在原新建 UUID 数据库的 owner 事务、WRITER_ACL 块内增加一条 `REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC`，随后执行原 writer GRANT。没有扩展权限；原 16 处 execute AST 均保留，唯一新增 SQL 为该 REVOKE。生产 src、预检与 runtime 守卫、原证明门、workflow、旧真实失败证据均不改，没有新增公开诊断字段。若 REVOKE 失败，纯反例确认流程在 writer GRANT 前停止。真实 PostgreSQL 事务回滚与权限效果本轮 NOT_RUN。

目录类型核对覆盖 OID/整数/布尔字段、已显式 cast 为 text 的内部 char 字段、NULL/default/identity/generated、ACL 数组与目录行顺序。坏列类型在 `CatalogSnapshot` 校验即失败，位于 CATALOG_COLLECT 内；顺序变化只影响摘要，不导致此次固定字段比较失败。owner/role 与多余有效写权限沿原合同拒绝，未将原 owner-as-writer 物理测试当作真实受限身份 PASS。序列与其它后续执行需求未因本缺陷假定正确，也未追加未经证实的权限修补。

原红测 **2 FAIL / 7 PASS** 的 stdout、JUnit、测试源码逐字节保留；两个原失败用例在修复后同 ID 通过。冻结主测 **305 PASS / 0 FAIL/ERROR/SKIP**，432 个源码文件首尾零漂移；7 项既有真实 PG 测试明确 deselected/NOT_RUN。主测涵盖新 10 项、原预检纯 59 项、trial 合同 84 项、adapter DI 93 项、CI 诊断 59 项，另有一个既有 Starlette/httpx 弃用警告。独审 **311 PASS / 0 FAIL/ERROR/SKIP**，与主测精确重叠 305 项，新增 6 项实际 `_read_catalog` 纯 DI 反例，不相加；同样 432 源码文件零漂移、7 项真实 PG NOT_RUN。独审确认 collector 使用完整函数签名及指定 app/writer 角色，并覆盖四种有效权限组合、缺失 app 观察和查询异常传播，结论 LIMITED_PASS、无代码 blocker。完整纯 JUnit 含超长合成参数，本地原件保留，公开有界逐项投影绑定原 XML 与完整 testcase ID 的 SHA256，投影不是原 XML。

一次辅助纯探针误用系统 Python，导入 psycopg 前产生 ModuleNotFoundError；完整工具输出转录保留，随后使用现有 `.venv/bin/python` 成功，不安装依赖或修改环境。主测与独审各有一次公共上游源文件网页读取返回 Internal Error，均停止对应 URL、保留各自返回转录且未作为证据；未重试任何历史被拒绝的 repo GET、workflow 列表或浏览器动作。这些观察不计入 pytest 成绩。

旧 [run 38332150145](https://github.com/T1doo/ParkWeave/actions/runs/38332150145) 仍是 **3 PASS / 1 FAIL / 13 NOT_RUN**。本轮可以签“代码缺陷及合成回归已修复”，不能签实际受限安装或完整生命周期。若将来另行批准一次真实验证，最小非敏感观测应一次区分分析器是否返回、固定 report status、闭集非 PASS check IDs，以及该单函数的 app/writer 有效 EXECUTE 布尔值；不输出任意报告字段、对象名/路径、DSN、SQL 或异常正文。此处只是下一次有界授权的观测建议，没有新增入口或启动试验。

独审另核 [PostgreSQL initdb 源码](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/bin/initdb/initdb.c)的默认权限处理；这是公开源码审查，不是物理观察。该单一 REVOKE 不会清除 app 的额外直接或继承权限，原有效权限守卫仍会拒绝这些情况；本修复仅限原 fresh UUID 合成试运行 setup。

可复核材料：[验证计数与同 ID 红绿对照](evidence/catalog-compare-offline-20261013/validation.json)、[主测有界逐项结果](evidence/catalog-compare-offline-20261013/bounded-pure-results.json)、[独立审查原件](evidence/catalog-compare-offline-20261013/independent/review.md)、[原失败 stdout](evidence/catalog-compare-offline-20261013/before-fix/stdout.log)、[原失败 JUnit](evidence/catalog-compare-offline-20261013/before-fix/results.xml)、[逐字节来源与散列清单](evidence/catalog-compare-offline-20261013/manifest.json)。其中复制、衍生摘要和工具转录分别标明，不把有界投影称为原始完整记录。

[最终文档与证据签收](evidence/catalog-compare-offline-20261013/independent/final-doc-review.json)已确认原 31 个证据条目的完整性及报告资格；其签收原件随后作为第 32 项逐字节归档。
