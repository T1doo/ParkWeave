资源确认有界修复只读独审（未冻结）

实际 HEAD: abea250abb68273bd192f300482ce8a281002575
产品文件 SHA256: 08ece2ea37b8ba0833abed1d34aa20976e762624e40d18cbc5a6b6ad7dd42254

结论：本轮 predicate 扩展静态可接受，未发现新增授权或原业务门绕过。将这一处 predicate 恢复后，整个模块 AST 与基线相同；原 case_resources / controlled_plans / resource_holds / resource_combinations 逐字节相同。

实际独立 HTTP→ASGI→自有 PG 窗口：
- resource-gate-wip-01: 5 PASS / 3 FAIL / 0 ERROR；JUnit 26.572s，runner 28.238s；601 源码路径前后零漂移。
- resource-gate-wip-02: 4 PASS / 0 FAIL / 0 ERROR；JUnit 13.224s，runner 14.917s；601 源码路径前后零漂移。

首窗 3 FAIL 是审查 oracle 把拒绝 audit 也错误算作不得变化。原请求均正确 403；补窗逐表仅 authorization_audit 变化，其余业务/权限表不变。原日志、JUnit、脚本完整保留。9 个独立场景各有成功证据，不称单窗 9 PASS。

Change is limited to allowing an adopted nonpartial currently compiler-supported registered plan through the pre-existing exact P1 proof branch; no new business write or Grant is introduced.
The existing V4 branch and legitimate existing current_partial delivery contract are preserved. The new non-V4 branch excludes partial_adoption=True; this is not a claim that all product partial deliveries are forbidden.
Original resource confirmation retains current role/PREPARE/EXECUTE/HOLD scope, Case/Run/key/resource locks, fingerprint/revision comparison, controlled_plans.gate, final full proposal reread and after-insert source status refusal.
Existing Read Committed catalogue boundary remains: a trusted uncoordinated administrator may change the SELECT-only catalogue after the final observation and before commit. This change does not add publication locking or atomicity.
Corruption probes prove conservative refusal, not resilience against every arbitrary trusted-database administrator rewrite.
All runs are WIP development evidence on Linux synthetic owned PostgreSQL over actual HTTP/ASGI. A commit HEAD plus source manifest is recorded because this branch condition remains an uncommitted product delta; final frozen validation and archive are pending.

详见 resource-gate-wip-review.json；正式冻结独审/完整回归/归档门仍未执行。
