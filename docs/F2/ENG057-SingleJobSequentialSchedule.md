# ENG057 — 单个 25 分钟 job 的顺序调度候选

本轮仅本地实现和独立复核，没有 push、CI dispatch/rerun、新 runner、权限扩大或成本增加。原 job 仍一个 `windows-2025` runner、`timeout-minutes: 25`、`contents: read`，不引入并发矩阵或额外 job。原 `Test` / native_suite all 路径的 900 秒合同保留；新 workflow 显式使用两个顺序阶段，时间来自同一 job anchor，不能每阶段重新领取 900 秒。

身份绑定修复独立提交 `26f848b`（5 文件逐字节等于旧冻结候选）；原 opt-in 分片独立提交 `e5123b3`；本轮调度另一个提交。旧 `a8fc001` 分支仍保留，同 Case 导航 `1aa81a2` 在原工作树保留。导航曾在隔离 clone 合并 `e5123b3` 无冲突，7 个文件的 blob 全部保持原导航提交内容。最终调度提交仍需同样隔离复验。

## 截止与阶段安排

第一 workflow step 在 checkout/选 Python/Prepare 前记录 UTC 与系统 uptime 两个 anchor，均提前扣 30 秒 bootstrap allowance。30 秒是保守设计假设，不是已观测的 GitHub job 真正起点；原 Actions 25 分钟 hard timeout 始终独立生效。Windows uptime 使用 .NET TickCount64 与 Python GetTickCount64 同一内核时钟；所有阶段重新映射时取 wall/uptime 剩余时间的较小值，再以本进程 monotonic 扣费，墙上时钟回拨不能重新授予时间。

| 顺序 | 上限与时间来源 | 失败行为 |
|---|---|---|
| checkout / Python / Prepare | 使用共享 anchor；Prepare 命令保留原单命令限额并裁到剩余工作时间 | 失败仍运行后续 always 验证/发布/Stop；无自有 cluster 时明确拒绝 |
| Lifecycle：Setup/Doctor/Start/Status/API/restart/browser/final Stop | outer owned Job ≤300 秒，且不超过 anchor+1300；Python共享截止 anchor+1290 | 保留部分 checkpoint、原退出与 outer cleanup；后续验证只在清理已确认时获准 |
| guard / Server candidate | 先做 guard≤15、candidate≤180，按实际消耗扣费 | 失败保留，清理确认且有时间则继续取得分片证据 |
| 全局 collection / S1～S4 | collection≤60；每片≤600；顺序共享 coordinator 实际剩余预算 | 普通失败/超时但清理确认则继续；清理未确认时后续 NOT_RUN，缺片绝不完整 PASS |
| aggregate / 报告 / 内层 Job 回收 | Python截止1290；回归层与协调层另各留10秒报告/回收，不能满用1290给测试 | 保留真实 exit code、部分计数、JUnit、覆盖和清理结果 |
| outer Job 回收 | 最晚1300启动回收，原 Job 回收等待≤5秒 | 未确认保持 FAIL，controller sidecar 不允许 Python PASS 掩盖 |
| Publish / 最终 owned Stop | anchor+1300 后保留末200秒窗口 | 不因前阶段失败而省略；没有强杀外来进程或服务兜底 |

实际 pytest 的剩余量不是四片600相加。设进入回归前已消耗 E 秒，则 validation 给 acceptance 的预算约 `1290-E-10`，coordinator 再扣10秒预留；collection 和各片从这一个预算扣费。各片实际上限是 `min(600, 当前剩余)`；耗尽即固定 NOT_RUN/TOTAL_BUDGET_EXHAUSTED，不采用 max(1) 启动新片。跨子进程还传同一 wall/uptime 截止，重建预算也不能扩大金额。

末200秒按现有合同核算：app Stop 60+回收5，PG status 15+回收5，PG stop 60+回收5，合计150秒；publisher限15秒，余35秒供 shell/Python 启动、原子结果、报告和调度开销。outer Job 最多额外5秒已消耗这份余量。`pg_ctl -t30` 不等于外层 wrapper 的60秒上限。尾部操作拒绝或失败时原失败保留；200秒是明确预留而不是 Windows 最坏启动/文件系统耗时的已测证明。

## 容量数值与目前不能确认的部分

上一唯一 Windows CI [37470355894](https://github.com/T1doo/ParkWeave/actions/runs/37470355894) 的已观测数值：Prepare约27秒；native总692.187秒；回归内层600秒超时，故已执行其他 native 部分粗算92.187秒。597.547秒的checkpoint记录548次teardown/收集1027；不能解释成548 PASS，也不是全程无等待。

| 量 | 数值 | 解释 |
|---|---:|---|
| 原1027用例的简单线性趋势 | 1119.855秒 | 597.547/548×1027；仅趋势，不是完整运行预测 |
| 原回归趋势+已执行非回归+Prepare | 1239.042秒 | 未含 checkout/setup、成功Start后的浏览器路径、新增测试等 |
| 上项再计30秒 bootstrap allowance | 1269.042秒 | 已接近 Python1290；若给两层各10秒预留，约1270的pytest截止几乎无额外余量 |
| 上轮候选1108用例按同一吞吐外推 | 1208.179秒 | 新增81个用例仅机械外推；不同测试成本不等，此值不能证明容量 |
| 1108外推+92.187+27+30 | 1357.366秒 | 已超 Python1290约67.366秒、实际pytest约1270边界约87.366秒；尚未计未知路径 |
| 当前1162用例按同一吞吐外推+92.187+27+30 | 1416.248秒 | 机械趋势超过Python1290约126.248秒、pytest约1270约146.248秒；仍不是预测 |
| 四片独立最坏上限 | 2400秒 | 明确不能保证塞入1500秒；共享预算会提前停止并失败 |

本轮又加入调度/失败清理测试，当前49文件1162用例分片276/264/342/280；真实全局与四次分片collect-only证明完整互斥，原1027保留、新增135。新增测试主要是小型合成回归，但 Linux耗时不能替代 Windows 时间。四片各自在 Windows 的完整实际耗时仍 NOT_RUN，不能给伪造的逐片时间或宣称容量已确定。

因此这是安全、成本不变、可测量的本地调度候选，不是“25分钟必能跑完”的结论。现有900秒整组外壳已不能容纳约1120秒旧趋势；分阶段移除这个结构限制，却仍受1500总预算和200清理预留约束。需要真实顺序阶段耗时（尤其 successful lifecycle/browser、guard/candidate、collection、四片实际及 cleanup）才能确定是否有完整容量。目前保持不 push、不 CI。如果完整用例实测超过可用预算，应报告真实缺口并再讨论优化/安排；不能静默增 runner、并发数量或总job时限。

## 证据与清理合同

阶段 sidecar 只包含schema/current run/attempt/SHA/cluster绑定、typed exit code、timeout bool和cleanup枚举，16KiB严格读取、拒绝duplicate/NaN/reparse/不匹配路径。外层结果在 owned Job 清理后原子保存，DWORD退出码用long保留。validation将同绑定的 lifecycle COMPLETED 或 IN_PROGRESS 安全投影合并，保留先前FAIL；不完整阶段另标失败。outer lifecycle未确认清理则隔离 guard/candidate/regression，outer validation未确认或失败也由最终publisher追加FAIL。若只留下lifecycle报告，publisher明确验证未完成。

每个 Windows collection/shard使用原 owned Job。任何 collection或piece返回/异常的 cleanup 未确认，都停止启动后续piece，已有证据不删除；已确认清理的测试失败/超时仍可继续其他piece。聚合JUnit改用原`pytest-uuid.xml`安全命名，真实分片失败ID通过已有白名单诊断读取器，未扩大公开路径许可。覆盖仍用实际参数维度/索引多重集与每片raw JUnit精确核对；测试参数与断言保留，原publication顺序测试仅适配新的有界Publish入口并增加入口限额断言。

publisher保留原64KiB安全JSON与8条/每条2048字节/总16KiB annotation限制。专用capture最多96KiB，只允许安全完整JSON及与原生成器逐行相等的完整批次；超时、截断（包括整行边界短写）、缺终LF或超限都固定UNAVAILABLE且保原非0退出。PS最终以原始UTF-8/LF写出，避免Windows CRLF破坏边界。其他phase capture仍只接受exit0和64KiB。

本地定点验证和最终独立复核摘要见 [ENG057证据](evidence/eng057-job-validation.json)，当前四片清单见 [冻结manifest](evidence/eng057-job-shards.json)。collect-only不等于全量PASS；所有原生Windows进程句柄精度、Job实际回收和完整时长仍待Windows验证。

R4仍关闭、预算0，无LIVE/真实模型、main merge/deploy、自动资格判断或外部履约。F1未签收、F2仅并行探索；Server不是Win11，36AT/6EX保持NOT_RUN。原工作树、导航提交与备份均保留。
