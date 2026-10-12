# SETUP 固定诊断候选：仅代码与纯 DI 验证

冻结源码 `3617bd0cb67b2d667cfcbb4ba53d37c101d8df07`，基底 `4f90af58ea1ab4faa5b503e7762665be40e949b3`；普通独立分支 `dev/f2-restricted-linux-setup-diagnostics-20261012`。本候选只增加 SETUP 诊断，不修 SQL 权限、不放松 adapter，不执行第二次 CI。

原唯一真实运行仍为 [38256730195](https://github.com/T1doo/ParkWeave/actions/runs/38256730195)，源码 `86bd07ef65135d749d6f0f9e9ae43039c4bd8fc8`，**FAIL：3 PASS / 1 FAIL / 13 NOT_RUN**。`ACTUAL_ROLE_ACL` 是进入整个 SETUP 前设置的宽标签，不能认定为权限缺陷；旧失败具体原因仍 UNKNOWN。原摘要、未知原因报告与全部原始失败证据保持不变，见[单次实际验收记录](RestrictedLinuxTrialOnceAcceptance-20261012.md)。

补丁在 [bootstrap](../../scripts/linux_trial/bootstrap.py) 定义 10 个固定 substage、31 个固定 check_id，以及严格整数状态码白名单：`0,200,201,202,400,401,403,404,409,422,500,502,503`。`0` 表示没有可公开的白名单 HTTP 观察；未列入状态同样归零，不公开任意值。只有六个实际 HTTP 检查可携带非零码：RUN_CREATE、PREPARATION_CREATE、两个 EVIDENCE、REVIEW、CONFIRM。substage 必须与 check_id 的固定映射一致。

[worker](../../scripts/linux_trial/worker.py) 在实际动作前推进检查编号，覆盖真实 UID/输入、创建证明、建库及 receipt、迁移、合成初始资料与 HTTP、存储安装、来源/策略、角色与 ACL、目录收集和比较。编号表示正在尝试的检查，不能单凭标签推断底层 SQL 原因。失败时只在 root 私有管道写一个 `FAIL + diagnostic` 帧，没有 DSN/tokens/result；原始异常仍写原有 VM 私有 stderr。成功的原私密 result 只留在 root 管道。

[controller](../../scripts/linux_trial/controller.py) 校验唯一、完整、UTF-8、大小不超过 524288 字节且无重复 JSON 键的终态帧；PASS 必须对应退出码 0、RESULT 检查与私密 result，FAIL 必须对应退出码 1 且无 result。缺帧、坏帧、信号退出或冲突仅保留固定 HELPER_FRAME，未获得观察前用固定 HELPER_ENTRY。helper 入口通过 SystemExit 保留退出码。根公开投影再次独立校验三字段及其组合；bootstrap 在全部 child 字段验证通过后才替换安全 fallback。

公开输出仍是一份封闭结果摘要，仅可增加 `setup_diagnostic` 三字段；不增加原始日志、SQL/SQLSTATE、请求/响应正文或 header、DSN、凭据、环境、repr、堆栈出口。旧五字段摘要仍能按原合同读取。下面仅为纯合成示例，不能反向用于解释旧失败：

```json
{"setup_diagnostic":{"substage":"SYNTHETIC","check_id":"PREPARATION_CREATE","status_code":403}}
```

源码只改三个 trial 脚本、相关纯测试和诊断测试 ID 清单。离线 AST 比对确认原 16 处 SQL execute 表达式完全相同；生产 `src`、既有证据字节和 workflow 均不变，bootstrap approved_context AST 相同。workflow 和 bootstrap 的 `run_attempt=1/run_number=1` 双层门保留。仓库仅两个 workflow；Linux 只匹配旧 trial 分支，Windows 只匹配 `dev/f1-foundation`，当前新诊断分支均不匹配。此次正常推送不会触发它们。

冻结主测实际 **200 PASS / 0 FAIL/ERROR/SKIP**：诊断合同 48、原 adapter 93、CI 诊断 59；430 个源码文件首尾零漂移。独审实际 **208 PASS / 0 FAIL/ERROR/SKIP**：同一 200 项精确重叠，加 8 个独立纯反例；432 个源码与合同文件首尾零漂移，计数不相加。独立控制覆盖嵌套重复键、非 HTTP 检查携带 HTTP 状态、信号退出、真实 setup 函数在 MIGRATION/SEED 前记录以及异常只进私有 stderr。结论 LIMITED_PASS，只签代码/纯 DI；真实 VM、PG、UID/ACL、sealed FD、锁、事务、activation/recovery/expiry 均 NOT_RUN。冻结窗口的有界逐项 JUnit 投影、原始纯 stdout、独审和字节 manifest 见 `evidence/native-writer-setup-diagnostics-20261012/`。

一次后续现有 Actions workflow 列表读取发生本地结果解析错误 `SyntaxError: "undefined" is not valid JSON`，已停止且未重试/改端点；底层返回未在解析前保存，不能推定读取成功或具体拒绝原因，该刷新为 NOT_VERIFIED。报错转录另存，未改变已取得的实际运行失败。此前 CLI repo GET 的 Forbidden 与 Chromium data: 的 ERR_BLOCKED_BY_ADMINISTRATOR 仍保持停止；本候选未重做这两项动作。

下一步可批准的范围仍限一次新的公共标准 `ubuntu-24.04` 独立 VM、25 分钟以内、零付费服务/模型、无 artifact/cache 上传，在全新目录/PG 内准备两个短期非 root OS 身份与 IPC 组、root 保护的源码/完整解释器依赖、原 issued 创建证明和必要技术 SQL 角色/ACL及固定合成初始数据，执行原有限 17 项验收并只停止自有子进程。下一次必须另建并审查精确单次入口（独立 workflow 与精确分支、first run/attempt、bootstrap 对应此次批准范围），冻结实际执行完整 SHA 并获得父级下一明确决定。当前候选没有第二次执行入口，旧用户确认、旧 workflow 或失败 rerun 不能当成新的执行授权。本轮没有新增该入口、修改权限或实际运行。

新纯窗口全部 PASS；原始 XML 含超长合成参数，保留本地原字节并在投影中绑定完整 SHA/字节数，每个原始 testcase ID 另绑定 SHA256，公开只列静态测试名和固定结果。该投影不是原 XML；旧真实与纯探针失败原件未改。
