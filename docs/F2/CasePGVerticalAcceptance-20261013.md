# Case / owned PG 纵向子集实际验收

本次 **27 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 0 UNKNOWN / 0 NOT_RUN**；另有 7 个编排阶段全部 PASS，阶段数不计入测试数。[run 38341687876](https://github.com/T1doo/ParkWeave/actions/runs/38341687876)、job `115113871538` 均 success，`run_number=1`、`run_attempt=1`。原公开仓库的标准 `ubuntu-24.04` runner 单次执行，job 上限 25 分钟；北京时间 2026-10-13 11:26:06 开始、11:26:39 完成更新（原元数据 `03:26:06Z` 至 `03:26:39Z`），元数据跨度 33 秒。没有重跑或 dispatch。

| 提交 | 完整 SHA | 用途 |
| --- | --- | --- |
| 冻结源码 | `54b15947f89eb1ba7524edb1119133d37ebc5326` | 主测 435 PASS、独审 444 PASS 的源码 |
| 审查父提交 | `a52ad8c7101bbea12fc6a95904d3d5e19f3f30e1` | 仅增加候选文档/证据，445 源码完全相同 |
| 执行提交 | `b38bab37a072ee7db3d28bbd9aeb291d467e564f` | 单父为上行，唯一差异是当次 approval.json；其余 444 源码相同 |

公开摘要 `source_sha` 绑定审查父提交；实际 checkout 的 `head_sha` 为执行提交。候选和执行分支已分别正常推送，执行分支保持不动。本报告在独立正常开发分支 `dev/f2-case-pg-vertical-acceptance-20261013` 交付，该分支不匹配执行 workflow。本次单次授权已消耗。

| 本次实际范围 | 用例数 | 结果 |
| --- | --- | --- |
| 原 7 项 PG 回归：collector 无业务读写/锁、storage 定义/冲突、伪造证明/错误连接、既有危险系统角色识别 | 7 | PG01–PG07 全 PASS |
| 原准备、本地关闭/重开与冷读、未分派/OFFERED 取消、跨租户拒绝、事件失败回滚 | 7 | PG08–PG14 全 PASS |
| 取消先获得锁：ACCEPT、材料、首次分派、方案采用、资源关联 | 5 | PG15–PG19：取消 200，竞争写入 409 |
| ACCEPT 先获得锁 | 1 | PG20：ACCEPT 200，等待后的取消 409 |
| 材料、分派、方案采用、资源关联先获得锁并提交 | 4 | PG21–PG24 全 PASS，按各自源变化重核 |
| 取消仍占资源容量、独立释放；旧通知消费/打开重核 | 2 | PG25–PG26 全 PASS |
| 同一 owned 库串联 catalog 修复与原成功 Run/Case 的取消、原 key GET、异参冲突及独立释放 | 1 | PG27 PASS |

原 7 项曾在 catalog-only 交付中 NOT_RUN，本次已实际执行，旧快照仍保持原状态。它们的 PASS 包含正确的 analyzer REFUSED：owner-as-writer、危险系统角色及损坏 storage 不能被接受；不是所有预检均返回 PASS。错误连接用的是本次新集群的维护库，没有访问既有业务库。

10 个竞争用例的源码断言要求实际观察 `pg_stat_activity` 锁等待。PG21/22 中材料/分派先提交导致旧源取消 409，原测试随后使用新源继续；PG23/24 中采用/关联返回 201，取消重核后返回 200，不能写成所有 writer-first 情况都拒绝。取消先和 ACCEPT 先两个方向均得到唯一胜者。持久事件、同 key 读取与冲突、事件失败全回滚、资源保持及迟到通知的结论限于上述精确用例。

实际使用新自有 PG16 集群、原签发的 cluster/database 创建证明及原逐用例 UUID 库 fixture。19 个原 Case 用例在各自新库提交单函数 PUBLIC REVOKE，并以真实 app 会话验证 42501、rollback 后 SELECT 1 正控制。新桥接用例在同一库验证修复前 app/writer 实际允许、原 analyzer REFUSED 且 changes 空；修复后 app 42501、writer 仍允许、原 analyzer PASS 且 changes 空，然后以原 API 取消普通 Case，保留建单 Run 的 SUCCEEDED 事实。取消后的 catalog PASS 只证明 catalog 状态，不证明被取消 Case 仍有执行授权。

7 个阶段同时验证精确收集、全部 setup/call/teardown、session provider 只替换一次、19 次 app ACL 检查、新 fixture 库全部删除以及 owned postmaster 正常整数 exit0 后 cluster 删除。清理结论不独立证明整个临时 root 擦除或托管 VM 销毁。应用日志/JUnit 留在 VM 私有目录，未上传或取得；公开证据是封闭摘要、实际 Actions 原日志和精确源码控制流，不能宣称取得每个断言的私有原始 transcript。

主测 435 PASS、旧独审 444 PASS，重叠 427；另 8/17 项分别属于各自窗口，不能相加，也不与此前 catalog 的 13 项或本次 27 项合并为一次测试。候选原失败 112 PASS/1 FAIL、434 PASS/1 FAIL及独审启动失败均保留；过期 pending oracle 未改签，diagnostic 注册失败已同 ID PASS。两次 Git upstream 简写检查 exit128 的原记录与资格另存：origin fetch refspec 仅覆盖 main，明确 remote ref 对比为 0/0，没有修改凭据或 fetch 配置。

已有实际独审在模型切换前启动并于安全点完成，原件作为既有证据保留：[限定实际独审](evidence/case-pg-vertical-acceptance-20261013/independent-existing/actual-review.md)。本次归档与报告已通过[新只读归档审查](evidence/case-pg-vertical-acceptance-20261013/independent-sol/review.md)的限定 PASS（审查请求参数 `gpt-6.1-sol`、medium），没有剩余阻断；运行本身未重跑。

host/IPC **NOT_RUN**，仍缺受保护 launcher、分离 OS 身份和私有凭据的前提。本次是 in-process ASGI 与真实 PG 的 27 项纵向子集，不签完整 Case 测试、host 生命周期、OS/密码隔离、进程重启/崩溃恢复、浏览器、外部履约或生产部署/迁移。下一步是补齐这些明确前提后进行 host→原 Case 的独立范围验收。既有浏览器和 GitHub 明确拒绝没有重试。

实际归档 `git diff --check` 为 FAIL（exit2）：两个原始 Git push stderr 共 8 行尾随空格原样保留；报告正文检查 PASS。候选归档中原失败日志的 4 行尾随空格也保持原样。

证据：[原始公开摘要行](evidence/case-pg-vertical-acceptance-20261013/root/actual-public-summary-original-line.log)、[27 项精确结果](evidence/case-pg-vertical-acceptance-20261013/test-results.json)、[完整性清单](evidence/case-pg-vertical-acceptance-20261013/manifest.json)、[资格](evidence/case-pg-vertical-acceptance-20261013/validation.json)。候选及原失败见[候选记录](CasePGVerticalCandidate-20261013.md)。
