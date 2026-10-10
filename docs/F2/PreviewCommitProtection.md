# P1预览提交保护：独审后有限签收

获审运行源码 `cadc7a34ecece7d77d793c4676e1b552838f41cc`，开发基线 `a0bfbf1ed78485bf4c9fb50a32bbc688cfbb698b`。实现前冻结合同 `18cdbe541d94d91db9c68d57b222d9d78e3e9748`，独审真实阻断后的补充合同 `5670dd4967b4132ece5d71f1d89888dfb7e2598b`，见[来源、写入者和稳定锁序](PreviewCommitProtectionContract.md)。本任务不扩P2–P5、正式写入、Grant、政策批准、服务发布、外部通知、Case完成或模型调用。

原实现末次来源采样后INSERT/commit，再用旧current返回CURRENT。现在在目录读取前取得原合作发布source-key共享锁，复用原principal/资料父行及依赖锁，保持至SQLite提交；BEGIN EXCLUSIVE把rollback-journal读者等待移到权限/已观察managed时效检查之前；执行后和INSERT/proof读回后再次检查。合作发布、撤回、资料补件、身份撤权必须沿既有协议等待；未合作owner直写、集合/缺行/未来来源、动态注册声明、时间和I/O不纳入全来源原子保证。

所有历史读取、重放、恢复及POST响应仅给SNAPSHOT_MATCH或STALE，返回source_atomicity=false和COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON，页面明确“采样时来源匹配仅为快照比较；不保证提交时全部来源不变”。提交后新采样仅用于响应比较；503可能发生在产物已提交之后，原key须GET核对，不自动POST。原不可变v2正文/proof、完整目标、两槽绑定及执行合同hash保持，旧产物不迁移、不重写。

## 精确验证

348源码路径清单SHA256 `4d180df651434d42401f4892bd83ca22c3a02ef0f86a74c06bcb355bb90df794`，1539个诊断AST函数ID。根执行和独审前后均零源码漂移；仅本地Linux原合成fixture、真实HTTP/PostgreSQL/SQLite/Chromium。public全部表及逐行值都纳入比较，只有既有脱敏authorization_audit单列允许原拒绝记录，不排除planning_previews。

| 窗口 | 实际结果 | JUnit / 受控秒数 |
| --- | --- | --- |
| 根冻结10完整模块，cadc | 268 PASS，0FAIL/ERROR/SKIP，自然0 | 150.419 / 152.205956 |
| 独立reader到期复验 | 1 PASS，0FAIL/ERROR/SKIP，自然0 | 2.708 / 3.761394 |
| 独立并发与故障边界 | 7 PASS、1观察器FAIL、0ERROR/SKIP，自然1；原件保留 | 13.098 / 14.488120 |
| 独立旧v2纠正窗 | 1 PASS，0FAIL/ERROR/SKIP，自然0 | 2.535 / 3.649551 |
| 独立10完整相关模块 | 268 PASS，0FAIL/ERROR/SKIP，自然0 | 159.952 / 161.810236 |
| 独立原页面及真实自有PG/API重启 | 3 PASS，0FAIL/ERROR/SKIP，自然0 | 14.741 / 16.300523 |

这些是独立窗口，不能相加冒充一次无失败运行。根与独审10模块范围为preview_commit_protection及browser、isolated_execution_preview及browser、catalog_approval_coordination、isolated_run_access、bounded_planning、preparation、request_intents、ci_diagnostics。

首候选 `791c518da37ef6048156029d67d6141ef80bee99` 的根266PASS不抵消独审真实1FAIL/BLOCKED：BEGIN IMMEDIATE允许独立reader持SHARED，末次_guard后COMMIT等待中lease过期，HTTP403但存了1个SUCCEEDED，GET为COMMITTED。原报告SHA256 `357196add885cf1ba7ff5bbf89115ddde85f8814ca8ed0419c2f7d41d84e937b`保留。修补后同业务oracle实际为初始BEGIN EXCLUSIVE等待、首次_guard尚未执行，跨原issued有效期后403、0产物、冷GET NOT_OBSERVED。迟到reader在末次_guard后实际SELECT为LOCKED，不能重新引入COMMIT读者等待；实际3秒忙锁503后只读NOT_OBSERVED，再本人明确同key重试才产生一条结果。

独审并发边界的观察器FAIL发生在旧5c25类被attach到当前API后，当前既有精确类gate按合同403，尚未生成旧产物。纠正窗用私有原5c25类直接执行其原认证和PG原动作产生实际v2，再用当前cadc类真实HTTP冷GET：doc/proof和SQLite整文件完全相同，完整目标保留、仅GET、public全值相同。未修改当前API、权限或原失败结果。根开发窗dev01另有1观察器FAIL/1fixture ERROR，dev03另有4旧SQLite读取观察器FAIL，故障原件/hash都保全，均不作为获审通过计数。

独审故障窗覆盖提交前503/0行/冷NOT_OBSERVED与提交后503/1行/冷COMMITTED原proof完全相同；未合作目录在末次采样后真实变更，返回STALE/source_atomicity=false；合作publisher确在PG advisory not-granted等待至预览rollback后才发布。原页面冷GET不盲POST、320历史完整目标无私有文本/token。实际自有PG与API PID重启后原库同identity/旧key冷GET恢复，默认新API读/写403；无Grant重签、无正式写入、无模型。

[独审报告](evidence/preview-commit-protection/independent/report.json) SHA256 `b2e0ee0ae65c2db080a212c6b9dfdda383e8af89883a968c547c2f9f9e8d08f9`，决策LIMITED_PASS；[验证索引](evidence/preview-commit-protection/verification.json)、[安全文件hash](evidence/preview-commit-protection/artifact-hashes.json)、[原阻断报告](evidence/preview-commit-protection/prior-blocked/report.json)及私有故障hash可复核。原失败XML/log保持私有，没有公开带fixture值的失败trace，也没有覆盖或重命名成PASS。所有独审窗口已自然结束、自有运行资源关闭后才允许正常整合。

## 未签收边界

只签收原factory-created rollback-journal库的P1合成预览提交保护。实际WAL观察中迟到reader可读且不阻塞commit，不能外推为WAL reader排斥保证；不自动修改或修补任何模式。SNAPSHOT_MATCH不是全来源CURRENT，锁不能冻结时间、磁盘I/O或未合作来源，不能外推为分布式事务。完整AT14覆盖表仍NOT_RUN，全仓、Windows、真实业务/履约、P2–P5实际执行、正式Case完成/权限/发布/部署未验收或授权。旧Windows Job/accounting未推送修复没有重做或声称通过；资料包导出已完成，没有重做。Dot unknown原因未定位，独审工具续跑可用不等于消息界面恢复。

root是本环境唯一源码/Git写入者；未改main、强推、部署、凭据、权限或安全网络配置。获审cadc后只追加docs/F2安全文档与证据，运行代码不变；候选普通push后仅以merge --ff-only进入dev。最终精确远端SHA、未推送文件与平台锁状态以整合末尾实际核验为准。
