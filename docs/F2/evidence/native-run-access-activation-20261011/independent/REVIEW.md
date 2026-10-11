LIMITED_PASS — 限定有效 native provider / ACTIVATE 独立审查

源码完整 SHA：`13029ed5e19fd3ffbf8c8dba01a3afcfe7215893`。414 文件清单 SHA256：`a8a2c61aab735d9f769800021d5f1d92bff994039ecc17aa65eddbd9ad1caab4`。独立最终 PG/ASGI/离线 Node 窗源码首尾零漂移，全部 414 个 worktree/commit blob 字节一致。两个合同首尾及 commit 字节一致：Activation `0b2cada854812b3672cd6c6b36572349606150a5237dcb6e9b263f91f4317548`，decision `6fbc10b549e65d901db97ad9a93e295220d878edfb294e2dd3988fd6de0c234f`。

实际测试窗：

| 独立窗口 | 原实际结果 | 源码 | 进程秒 / exit |
|---|---|---|---|
| initial-provider-counterexample | 0 PASS / 1 FAIL / 0 ERROR / 0 SKIP | 58b0c989ed12d16ddd893102d3003044abb4b1c0，414 零漂移 | 4.330 / 1 |
| initial-cross-db-counterexample | 0 PASS / 1 FAIL / 0 ERROR / 0 SKIP | 同 58b0，414 零漂移 | 6.148 / 1 |
| repaired-frozen-full | 106 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 13029，414 零漂移 | 108.357 / 0 |
| vm-expiry-callback | offline Node exit 0，8 assertions；无 JUnit testcase | 同 13029，414 零漂移 | 0.150 / 0 |

最终 106 个唯一 JUnit ID：47 个完整 activation、35 个完整 decision、8 个完整 offline NodeVM，加 16 个独立自写 PG 反例。JUnit 时间 106.740 秒；原 stdout 汇总也为 106.74 秒。`repaired-frozen-full/{results.xml,stdout.log,run.json,source-before.json,source-after.json,contracts-before.json,contracts-after.json,result-summary.json}` 保留完整原件；命令、PID 508244、时间及 own probe 输入 SHA 在 run.json。不是转签根进程结果。

原两个 HIGH 缺陷均实际复现并保全。第一例用未知 provider 的 `assignment_allowed=lambda True` 让 native-marked Run GET 实际 200；第二例把原 issued permit 绑定 DB2 Store，让 DB1 owner writer 在原数据库完成 ACTIVATE 实际 200。修复后同两个 ID 在最终 106 窗各 PASS，`failure-map.json` 保留原 status / XML / log hash / 原源码 / 同 ID 修后关联。第一修复要求 exact native 类型、同 Store、可信类方法；第二修复先实际只读核业务 Store 的 endpoint/database，再在原 owner 同事务核身份、权限、原请求并写事件与 assignment。初始 FAIL 不改写为 PASS。初始第一 probe 整份 runtime 文件未在追加前另存，明确保留这项捕获限制；它的原完整 JUnit/stdout 与三个产品源快照仍在。

实际验证覆盖：默认/伪造/跨 DB / instance override 拒绝，同异键与 rollback，冷热可信重绑及旧键当前失效/原 receipt 保留，所有参与主体的当前权限代际，durable native marker 与 legacy 兼容，实际分派/ACCEPT/legacy CREATE/manual SUBMIT/旧通知/collections，真实 PG SUBMIT 与 REVOKE 父锁两种队列顺序和 commit 到期全回滚。真实取消三阶段 RECONCILING→CANCELLED 保留合法历史 READ，新激活与业务写拒绝；pending handoff 旧世代拒 SUBMIT，native 不能给另一方新权限。实际 CLI worker 建单、P1–P5/资源/人工 ACK/local close 链通过；新 assignment 对计划来源的改变必须原 API explicit local revision ADOPT，未自动重绑。

业务使用 `track=True` 并在 guarded commit 重核来源、代际及数据库 UTC；metadata 使用 `track=False`，REVOKE 不会因它观察旧可用状态而被自己的 commit guard 回滚。Case 状态从稳定 READ 版本比较排除，Run/material/review/权限版本仍强绑定。共享 parent→native Run advisory→Run/assignment 锁路径、执行者 parent/receipt base、列表 post-filter 和 outbox/OPEN 的当前参与人检查已静态复核。七份原 SQL 白名单/role bounds 与 f37 基线原字节不变；详见 `static-consumer-review.json`。这项静态覆盖不等于每个 API 都独立动态运行。

工作台显示当前 ACTIVE_SYNTHETIC_FIXTURE 与不可赋权的原 approval history 分开；ACTIVATE 仅受限 API，不增加生产按钮。额外 VM 窗调用真实到期 callback，清除有效展示并保留 UNKNOWN / original key，整个窗口只 GET、未自动 POST。此前 direct tool 调用也是 exit0，但未单独保存 stdout/stderr 文件；命名 VM 窗另有完整原始捕获。

setup 边界：自有 fresh PG cluster/UUID fixture 数据库、原 fixture SQL 角色/权限/主体/准备阶段由既有测试 setup 创建；它们不是业务 ACTIVATE 输出。手动 handoff probe 对另一现有合成执行者有一条明确 setup 的 legacy assignment，仅用于证明不同责任世代；不由 native 发行。ACTIVATE 只写精确已有批准 Run 的 native assignment 与 immutable activation event，未新增身份、capability/PREPARE/resource Grant、SQL GRANT、信任 registry。撤权反例只在自身 fixture 内改变并恢复原权限记录，属于负例 setup；不涉及生产授予。

本片无剩余阻断。生产安装/真实权限/生产 TTL 与审批政策/部署、Windows 原生验收、浏览器与付费模型、完整正式 AT35 均 NOT RUN，browser attempts=0。根 135 模块广窗在本签署时仍 RUNNING，已报告的旧 ACL readiness Oracle FAIL 原件另保留；只读核确认原 setup 在所有动作前 OWNER_MUTATION_PAUSED，该 Oracle 与前置 gate 错位，未修改或绕过生产 pause。此报告不宣称全仓 PASS，也不更新任何旧签署报告。
