# 第二次独立 Linux 验收：FAIL

本次新批准的一轮标准 Ubuntu 隔离验收已实际运行一次，结果 **3 PASS / 1 FAIL / 13 NOT_RUN**。新诊断将受阻检查定位为 `CATALOG_COMPARE`，具体失败原因及是否存在目录差异仍未知，不能认定某一 SQL 权限存在缺陷。没有修补后重跑，也没有 rerun、dispatch 或第三次试验。

冻结源码为 `4649970278e29b999a2a4f332ba7380f20795a3f`，基底为 `80ac6c86edd447d31e5f046b25eb335c63923102`，普通独立分支为 `dev/f2-restricted-linux-second-trial-20261013`。[实际 run 38332150145](https://github.com/T1doo/ParkWeave/actions/runs/38332150145)、[job 115084081632](https://github.com/T1doo/ParkWeave/actions/runs/38332150145/job/115084081632) 均 completed/failure；push、run_number=1、run_attempt=1。run 创建于 2026-10-13 01:26:37 UTC，固定公开摘要出现于 01:26:58.6689207 UTC，run 在 01:27:01 UTC 更新为完成。

第二次入口绑定新批准标记 `USER_CONFIRMED_SECOND_FREE_GITHUB_VM_2026-10-13T01:14:56Z`，由独立 workflow、新精确分支、固定 CLI 参数与环境入口、root 私有 controller context 串接；不复用旧批准标记。workflow 与 bootstrap 均检查 first run/attempt，controller 拒绝新旧标记交叉配对。只使用一个公共标准 `ubuntu-24.04` job，限 25 分钟，执行 step 限 23 分钟。公共仓库标准 hosted runner 的免费规则见 [GitHub 官方计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。旧 workflow 字节、旧 approved_context AST、worker 全文件和 SQL、生产 src、既有失败证据均未改。

| 窗口 | PASS | FAIL | ERROR | SKIP | NOT_RUN |
| --- | ---: | ---: | ---: | ---: | ---: |
| 冻结主测：纯契约、adapter DI、CI 诊断 | 236 | 0 | 0 | 0 | — |
| 独立审查：同一窗口加独立反例 | 251 | 0 | 0 | 0 | — |
| 实际 VM 的固定 17 项 | 3 | 1 | — | 0 | 13 |

两份纯测试精确重叠 236 项，独审另有 15 项，不相加。主测 431 个源码文件、独审 6115 个 tracked 文件在各自冻结窗口前后均无漂移；各有一个现有 Starlette/httpx 弃用警告。独审只签代码和纯 DI 的 LIMITED_PASS，在实际推送前完成，没有用纯测试成绩代替物理验收。

实际 PASS 为 `REAL_IDENTITIES`、`FRESH_CLUSTER`、`OWNED_STOP`。失败标签为 `ACTUAL_ROLE_ACL`，phase=`PG_SETUP`、error=`CHECK_FAILED`，新增诊断为：

```json
{"substage":"CATALOG","check_id":"CATALOG_COMPARE","status_code":0}
```

worker 的固定编号是在操作前设置的；本次已进入 `CATALOG_COMPARE` 阶段，包含 `preflight.analyze(...)` 调用以及后续 `report.status == PASS`、`report.changes` 为空的条件检查。公开投影没有携带原始异常或报告内容，因此不能证明报告已生成，也不能区分分析调用异常与报告不满足条件；具体失败原因及是否存在目录差异仍未知。状态码 0 表示该检查没有可公开的 HTTP 状态观察。此检查未完成，因此不得把前面的准备动作或宽失败标签改签为实际 ACL 验收 PASS，也不能反推第一次试验的未知根因。

实际 NOT_RUN 为 `PROTECTED_RUNTIME`、`HOST_CHANNELS`、`API_PRIVATE_BOUNDARY`、`EXPLICIT_BIND`、`EVENT_ROLLBACK`、`REAL_PARENT_LOCK`、`REQUEST_APPROVE`、`ACTIVATION_ROLLBACK`、`LOST_RESPONSE_GET`、`COLD_REBIND`、`LEASE_EXPIRY`、`CHANGED_SOURCE_REVOKE`、`NO_RENEWAL`。bootstrap 已做保护源码、解释器和依赖的准备，但 adapter 保护校验未到达；实际双 socket、身份边界、受限 writer 事务/锁等待、activation、恢复与租约到期仍未获得本次验收。此结果不宣称完整 Case 生命周期、生产安装或浏览器验收通过。

`cleanup=true` 且 `OWNED_STOP=PASS`，确认本轮自有子进程清理检查通过；GitHub job 的收尾步骤成功。临时用户、PG 数据和私有诊断属于这台一次性 VM，没有从 VM 取回或上传原始私有日志。artifact 查询为空，workflow 没有 artifact/cache 上传动作；没有生产部署、付费服务或模型调用。

原样公开结果和 exit-code 1 行见 [actual-allowed-output.txt](evidence/restricted-linux-second-trial-20261013/actual-allowed-output.txt)，[结构化摘要](evidence/restricted-linux-second-trial-20261013/actual-summary.json)、[Actions 元数据](evidence/restricted-linux-second-trial-20261013/actions-final.json)、纯测试有界逐项投影、独审原件和文件散列在同目录。纯测试 XML 含超长合成参数，完整原件在本地 `.runtime` 保留，公开投影绑定原 XML 和每个完整 testcase ID 的 SHA256；投影不是原 XML。旧真实失败与旧纯探针失败原件保持不变，见[第一次验收报告](RestrictedLinuxTrialOnceAcceptance-20261012.md)。

此前 CLI repository GET 的 Forbidden、旧 workflow 列表读取的本地解析错误及底层 UNKNOWN、Chromium data: 的 ERR_BLOCKED_BY_ADMINISTRATOR 均继续保持停止。本次正常分支推送及独立的新 Actions run 只读观察成功，未重试上述动作、配置凭据或网络。

下一步应先离线分析原目录收集/比较合同，提出只公开固定差异编号的有限诊断或有证据支持的修复；本轮没有导出目录报告、扩大权限或新增试验。任何再一次真实 VM 验收须另有明确决定，不能复用本次已执行的一轮授权。
