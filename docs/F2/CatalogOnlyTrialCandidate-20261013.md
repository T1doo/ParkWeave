# 默认关闭的 catalog-only 单次候选

本报告记录候选准备与纯测冻结窗口；该窗口尚未收到实际执行批准。归档期间收到的后续单次授权另记于末尾，原测试资格与证据不改写。冻结源码 `17cf9cdbff28ae759e68b7f66878e1c396ec6f0d`，基底 `a658516ff40e081096ee3f7b89c0593be2557250`；候选分支 `dev/f2-catalog-only-candidate-20261013` 不匹配任一 workflow。没有启动 runner、PostgreSQL、host/API/lifecycle，没有新 OS 身份、现有权限修改、现有数据库或密钥访问。

仅有六个源码/合同文件变化，生产 `src/`、原两次 trial、旧 workflow 与失败证据均不改：

| 文件 | 增量 | 用途 |
| --- | ---: | --- |
| `.github/workflows/catalog-only-once.yml` | +49 | 免费标准 ubuntu-24.04，整个 job 15 分钟、执行步 13 分钟，单 job/无矩阵/无上传缓存 |
| `scripts/catalog_only/approval.json` | +5 | `approved=false`、源码与审批引用为空；默认关闭 |
| `scripts/catalog_only/bootstrap.py` | +156 | stdlib 先验门、仅批准文件差异、单次 claim、临时依赖和封闭公开输出 |
| `scripts/catalog_only/probe.py` | +249 | 全新自有集群/目录权限及实际函数调用对照，原 collect→analyze，确定性清理观察 |
| `tests/test_catalog_only_candidate.py` | +355 | 67 项纯回归；进程/连接/信号动作全部被替身拦截 |
| `scripts/windows_ci/diagnostic-test-ids.json` | +15 | 登记新增可信测试函数 ID，未扩展任意诊断字段 |

未来的真实入口有明确前置条件：用户另行批准；仅向 `dev/f2-catalog-only-once-20261013` 首次推送批准提交，不能先推默认关闭候选消耗 run_number=1。workflow 仅监听该分支的 `scripts/catalog_only/approval.json`，同时核原公开仓库、push、run_number=1、run_attempt=1。bootstrap 再核相同上下文、github-hosted/Linux、当前非 root UID、完整提交 SHA、干净 checkout、严格批准文件 schema。批准提交必须只有一个父提交，父 SHA 等于批准文件的完整 `source_sha`，与父版本唯一差异必须是批准文件；父版本该文件必须仍是原始 pending 内容。此前执行许可与旧 workflow 不可复用。

批准文件应由另获授权的批准提交填写，不从本候选自行启用。其 `source_sha` 必须精确等于当次经过核准的父提交；若使用后续仅文档交付提交作为父版本，应填写该完整交付 SHA，并核与本冻结源码的代码无差异，不能误填更早源码 SHA。此文件和 GitHub 上下文是执行门，不替代人的实际授权，也不是抵御有权任意改仓库者的安全边界。

实际范围限于一个新私有临时目录中的 PG16 集群及 UUID 数据库，使用原 `capture_fixture_cluster` / `record_created_database` 证明、`Store.migrate` 和两份 owned 附加 storage 安装。没有 seed、Run/Case 建单、业务 Grant、host、IPC、UI、模型或生命周期动作。原 schema 与 writer 权限矩阵只在这个全新库内准备；没有连接现有服务或读取现有数据。

PG 使用 runner 既有非 root OS 身份、系统现有 PG16 二进制、空环境、私有 Unix socket、禁 TCP；不 sudo、apt、useradd、chown/chmod 现有文件。依赖仅按现有固定版本安装至新临时目录，180 秒超时、不缓存、不系统安装；新建空 NETRC、`PIP_CONFIG_FILE=/dev/null`、`--no-input --keyring-provider=disabled` 明确关闭 pip 的默认凭据/配置发现，不修改 HOME。只读本地 pip 源码验证这些选项的调用路径，不把它当作未来 runner 上的安装实测。PG initdb 60 秒、探针 480 秒总时限，结束时仅处理自有 Popen 和独占新目录。SQL 角色通过这个私有 socket 的 local trust 建立独立非 owner 会话，核 `session_user=current_user`、非 superuser、精确库/OID/host/port；不把它当密码认证、OS 身份隔离或 host 密钥边界的证明。新空 passfile 用 O_EXCL/0600 创建；owner/app/writer DSN 均显式指定它，并设置 `sslmode=disable`、`gssencmode=disable`，关闭默认 `.pgpass` 与 SSL/GSS 密钥发现。没有新密码或现有密钥读取。

待执行的顺序固定为：

1. 默认 PUBLIC 执行权下，给予原 writer 显式 GRANT；原 collector 读取 app/writer 有效权，期望二者 ALLOW。两个独立 SQL 会话实际调用函数都须返回同一自有集群标识（值仅私有比较）。
2. 原 analyzer 返回 REFUSED、changes 为空，唯一非 PASS 项必须是 `forbidden.app:control_system_execute`。其它失败不能被解释为预期成功。
3. 提交唯一修复 SQL `REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC`。再次原 collector 期望 app DENY、writer ALLOW。
4. app 实际调用须发生 `InsufficientPrivilege`/42501，事务回滚后同会话 `SELECT 1` 正控制通过；语法/连接/其它异常不当成权限拒绝成功。writer 实际调用仍须成功且集群标识一致。
5. 原 analyzer 须返回 PASS、changes 为空，且安装/启用/生产连接 authority 保持 false。policy 的业务 UUID、资料和 UID 是明确的合成声明，不读取或创造对应业务记录，不签原 Run/Case/受限 runtime 合同。
6. 自有 postmaster 只有明确正常 exit0 才允许删除新 cluster。initdb 未确认完成标 UNKNOWN；异常退出、强杀、清理异常均不能签清理 PASS，保留未证实可清理的目录直到临时 VM 销毁。私有失败日志尽力原样保留，写日志失败只标 `failure_logs=UNAVAILABLE`，不能把异常链抛到公开 stderr。

导入和探针运行同时重定向 Python 流与 FD1/2 到私有文件，使用 ExitStack 在正常/异常时恢复原描述符；合成 FD 写入及恢复已纯测，未新增 worker。公开输出仅含完整源码 SHA、13 个固定 case ID 的 PASS/FAIL/UNKNOWN/NOT_RUN、4 个权限枚举、前后 analyzer 的 RETURNED/RAISED/NOT_RUN 及有限 status/changes/nonpass 分类、失败日志保存状态。未知和未运行不合并；没有任意检查名、SQL、对象名、DSN、路径、函数返回值或异常正文。公开日志不上传私有日志；本候选的合成测试失败原件另按清单归档。

主测最终 **372 PASS / 0 FAIL/ERROR/SKIP**，437 源码文件首尾零漂移；7 项真实 PG 测试明确 deselected/NOT_RUN。新候选 67 项，其余为原目录、preflight、trial 合同、adapter DI 和诊断回归。独审最终 **378 PASS / 0 FAIL/ERROR/SKIP**，精确重叠 364 项、独审另 14 项、主测另 8 项，不相加。独审另 deselect 8 项已由主测执行的纯 pipeline，不能混入 7 项物理 NOT_RUN。两窗均为纯合同/DI；共享回归中实际运行了 6 次既有离线 preflight CLI 子进程。独审旧记录的过宽“无真实 child”表述保留原字节，另附澄清，最终观测记录明确子进程均禁 bytecode、使用私有 TMPDIR。

失败证据不改签：独审对初始候选 `a3a2ba2114d5b046c0b63ea79f7a95cd8404a842` 实际 **3 FAIL**，证明二次日志失败外泄及两种异常 PG 退出被误签清理；修复至 `736677706cab2852bb9c9c4af10939958d1309d4` 后同三个 ID 通过。另一次新回归在此版本提取真实 DSN 表达式，实际 **1 FAIL**，证明缺少显式 passfile 选项；它没有连接 libpq，也不声称已观察到密钥读取。最终源码同 ID 通过。独审另在 `75d487d458f43c657b2a69fa558231e33c5b4c8e` 实际 **1 FAIL**，证明原生 FD 写入能绕过 Python 流重定向；`6b4562ea7128c43508bceaa3756adf8719423f0f` 后同 ID 通过。随后 pip 默认发现边界的纯回归在该版本实际 **1 FAIL**，只拦截真实 bootstrap argv/env，未运行 pip/认证/网络；最终同 ID 通过。各阶段原 stdout、JUnit、探针源码、计数/退出码与来源分别保留，不抹除先前 FAIL 或相加重叠测试。

旧真实 run `38332150145` 仍为 **3 PASS / 1 FAIL / 13 NOT_RUN**；本候选和纯 DI 无权将其改签。所有新真实 PG 权限、函数执行、事务和清理效果仍 **NOT_RUN**，原始 Case/受限 host/lifecycle 验收仍未完成。候选冻结窗口没有推送执行分支、dispatch、rerun 或重试旧拒绝。

证据入口：[验证总表](evidence/catalog-only-candidate-20261013/validation.json)、[逐文件原件/派生清单](evidence/catalog-only-candidate-20261013/manifest.json)、[独审签收](evidence/catalog-only-candidate-20261013/independent/review-final.md)、[旧措辞澄清](evidence/catalog-only-candidate-20261013/independent/evidence-clarifications.json)。归档 99 份明确清单内原样副本，6 个原 FAIL 同 ID 最终均 PASS；大型通过 JUnit 留在本地，以完整原文件 SHA、逐 ID SHA 和有界结果投影绑定。

环境恢复检查于 `2026-10-13T02:36:20.703317+00:00` 成功：命令及文件可用、冻结 HEAD/分支正确、tracked 工作区干净、最后 372 PASS 记录哈希相符，437 源码零漂移；未创建第二写入者或恢复队列，见[恢复原始检查](evidence/catalog-only-candidate-20261013/root/environment-access-check.json)。

归档期间父任务 `01a123a4-3260-7036-854d-9af15b5eb0e7` 转达用户新的明确授权：由调度者自行接续合适的常规开发推送与免费测试，本候选可在审查后执行**仅一次**免费标准 Ubuntu runner、最多 15 分钟，只在全新自有临时 PG16/临时 SQL 角色验证 app 拒绝、writer 成功、原 collect/analyze 无意外变更并清理。本候选提交仍保持 pending；后续仅批准文件变更的独立提交绑定本次源码等价交付 SHA，再首次推送独立执行分支。授权不扩 host/lifecycle、既有数据库、凭据/安全网络权限、收费或 main；真实结果另以实际 run 归档，不回写此前 NOT_RUN。历史拒绝继续保留且不重试。
