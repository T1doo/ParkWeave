# 一次性host→Case取消真实运行：失败报告

本次已获用户针对候选与动作清单的明确一次授权，已执行并消耗；**不重跑、不补发activation、不复用该入口**。结果为 **1 PASS / 1 FAIL / 19 NOT_RUN / 0 UNKNOWN状态项 / 0 ERROR / 0 SKIP**，21项来自原公开封闭summary，不是合成测试结果。准备失败的具体异常类型/行位置仍 **UNKNOWN**，不与状态项UNKNOWN计数混淆。

受审源码：`e99bcf24e3da4cab6feee05e21f3a4d4fcaca3b7`；批准候选：`6aa12c75461994bfff5e16dc6a169877808ad908`；唯一执行提交：`9a5808b01b807712d272c6180990cc2e3969b1d7`。执行提交只有候选一个父提交，仅approval.json三字段改为true/指定候选SHA/USER_CONFIRMED_HOST_CASE_SECURITY_ONCE_20261013。19包哈希锁与--no-log-init及全部helper源码未变。

[Actions run 38373923111](https://github.com/T1doo/ParkWeave/actions/runs/38373923111)，job `115217411364`，首次push/run_number=1/run_attempt=1；公开原仓库、一个标准GitHub-hosted ubuntu-24.04 job（日志OS24.04.5），job09:06:16–09:06:27 UTC，11秒，低于25分钟上限。原API最终run/job结论均failure；试验step exit1，checkout和平台收尾success不能替代业务验收成功。

| 实际验收项 | 原summary状态 |
| --- | --- |
| GATE | PASS |
| PROTECTED_RUNTIME | FAIL |
| REAL_IDENTITIES | NOT_RUN |
| FRESH_CLUSTER | NOT_RUN |
| SETUP | NOT_RUN |
| BUSINESS_ACL | NOT_RUN |
| HOST_CHANNELS | NOT_RUN |
| API_PRIVATE_BOUNDARY | NOT_RUN |
| ACTUAL_ROLE_ACL | NOT_RUN |
| EXPLICIT_BIND | NOT_RUN |
| REQUEST_APPROVE | NOT_RUN |
| NATIVE_ACTIVATION | NOT_RUN |
| BUSINESS_BIND | NOT_RUN |
| CASE_CANCEL | NOT_RUN |
| ORIGINAL_KEY_RECOVERY | NOT_RUN |
| HISTORY_RETAINED | NOT_RUN |
| LATE_WRITE_REFUSED | NOT_RUN |
| OWNED_STOP | NOT_RUN |
| DATABASE_REMOVED | NOT_RUN |
| FILES_REMOVED | NOT_RUN |
| IDENTITIES_REMOVED | NOT_RUN |

审批门禁通过后，公开输出停在phase=PROTECTED_RUNTIME/error=FAILURE。没有达到真实身份、PG/SQL角色、host/private边界、业务取消、原key恢复或历史保留的验收。此前纯DI/离线wheel核验PASS不能填补这些NOT_RUN。本次不签完整Case、host或实际安装成功，也不把NOT_RUN当外部无副作用证明。

**cleanup=false，四项清理均NOT_RUN，未签清理成功。** failure_logs=SAVED仅说明程序报告将异常存入当次VM的T/private；diagnostics=[]。本片不上传私有文件，实际artifact数量0；没有取回该私有trace，无法由公开日志定位准确失败调用。已原样保全公开job文本（含平台***掩码、BOM/ANSI）、完整run/job/API原件和解析结果；不宣称私有日志在VM回收后可持久取得，不用平台Cleaning up orphan processes代替自有T/身份/库清理或VM擦除证明。

原公开证据、元数据/21项校验和独立只读失败审计归档至 `docs/F2/evidence/host-case-security-once-20261013/`，manifest逐项bytes/SHA256核对。独审只验证失败证据、提交链与一次性范围，不能将其审计PASS读为真实试验PASS；不运行测试或任何权限/SQL/安装动作，不猜私有异常。

交付只写独立报告分支 `dev/f2-host-case-actual-report-20261013`，基于候选6aa（approval仍false/null/null）；执行分支保持9a，无第二提交/推送。main/F1/F2不变，未调整任何凭据/网络配置或通过浏览器取得日志，没有rerun。最终交付完整SHA及远端干净/0未推差异由交付响应给出。

剩余阻断是实际保护环境准备失败且公开诊断不足。下一步须单独诊断准备边界、形成新源码/可审公开诊断及独审；任何再试都需新的一次具体授权和独立入口，不能继承本次已消耗的执行许可。本报告不自动启动后续动作。
