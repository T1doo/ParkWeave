# ENG056 — 严格 launcher 绑定与四分片本地候选

本候选从远端已推送的 `aa3dc550765d3a23d598b0e282dde6bfe84784eb` 隔离到 `local/eng056-targeted`。只做本地实现、验证和独立复核；没有 push、dispatch、rerun、新增 runner 或修改 workflow/job 限额。同 Case 导航保留在另一工作树的 `1aa81a2ea43f07dc8099d46077a128b01a94affd`，没有混入本候选。原环境和恢复备份保留。

## 严格 Start、Status 和 Stop

Start 保留 health PID 比较。Windows 上只能接受原 launcher 本身（ROOT）或它的已证明直接 server child（DIRECT_CHILD）；其他情况 REFUSED。证明链包含原 psutil.Popen 借用创建句柄、只读 query/synchronize 句柄、内核 PID/创建时间/存活状态、已有可信完整命令和 cwd 检查，以及直接父子关系。借用句柄不关闭。创建时间核验容差为 10 微秒，child 创建时间须在 launcher 创建后 60 秒窗口内；这些精度和真实 venv 父子形态仍需 Windows 实测。

私有 STATE 仍保留两个 launcher 根记录，已证明的执行 child 嵌套保存。即使 mode/model 尚未匹配，也立即保存已证明的 API child；以后不允许悄悄换 child。保存前两次核验原 STATE 字节，使用独占临时文件和原子替换，失败进入 process_record 清理路径。HTTP 完成后的元数据异常不会被吞成网络重试。

Status 核验同一严格绑定。Stop 在任何 child/root 信号前保持根和 child 的句柄证明，直到根停止结束；child 停止使 launcher 自行退出时，在原持有句柄上证明退出，不重新按 PID 打开。尚未保存 child 时，仅允许从可信 launcher 的唯一直接 child 重建同一证明；歧义、外来或未知身份均保留记录并拒绝。缺失 launcher 而 child 仍在时拒绝孤儿终止。没有扩大终止权限、关闭 PID 比较或任意进程接纳。

公开诊断仅增成对的 bool `server_pid_valid` 和枚举 `server_relation`（ROOT/DIRECT_CHILD/REFUSED），原安全投影与大小上限保留，不公开 PID、命令、路径或异常正文。created/stopped 的两条根记录不能解释为所有物理后代均被证明或清理。

独立复核发现的“根句柄过早释放”和“STATE 写入 OSError 被当成网络重试”均已修复并加入回归；最终冻结身份实现复核 NO_BLOCKERS。

## 四分片完整性与失败证据

分片为显式 opt-in，默认原整组 600 秒行为保留。当前 47 个测试文件、1108 个用例划分为 S1/S2/S3/S4：271/264/326/247。真实全局 collect-only 与四次独立 shard collect-only 的稳定参数身份多重集完全相等且互斥；这不是 1108 PASS。

原 1027 个用例均保留原参数位置和断言：1023 个 raw ID 字节相同；另 4 个展示 ID 含随机 UUID，来自两个源码未改的参数化测试。跨进程覆盖以原函数及真实 callspec 各维度索引核验，不删参数、合并测试或按去参数名冒充覆盖。每片执行 JUnit 与该片自己的 raw collection 精确多重集核验。私有 collection 的单 raw ID 限 1 MiB、整文件限 4 MiB，以容纳已有 512 KiB 异常输入测试；公开诊断限额没有扩大。

每片独立 600 秒上限，顺序执行，当前协调器总窗口最多 900 秒。失败、超时、解析失败和 cleanup 拒绝即时保留原 exit code、cleanup、部分计数及 JUnit，并在剩余预算内继续其他片。覆盖缺失、重复、源码漂移或不完整收集都不能完整 PASS；状态采用 FAIL 优先于 SKIP、再优先于 PASS。无剩余预算明确 NOT_RUN/TOTAL_BUDGET_EXHAUSTED，不能挤出 1 秒启动新片。诊断 checkpoint 是每片局部进度，不能当全局完成数。

Windows 子阶段使用原 owned Job；Linux 小型真实四片测试仅验证收集、执行、合并及失败路径，不证明 Windows 进程树清理。最终冻结分片实现和 manifest 独立复核 NO_BLOCKERS。

## 本地证据

源码与 manifest 中全部测试/实现 SHA256 核验相等。证据见 [冻结 manifest](evidence/eng056-local-shards.json) 和 [验证摘要](evidence/eng056-targeted-local-validation.json)。原始 JUnit/collection 留在本地 `.runtime`，未公开参数值。

- 身份/lifecycle/清理组：137 PASS、3 SKIP；随后离线已有 PowerShell 的 portable cluster fault 单项 1 PASS。两个原生 Windows 身份测试仍 SKIP。
- 分片/acceptance/publication/diagnostics 冻结组：112 PASS。
- 分片/acceptance/owned Job/safe annotation/publication 冻结组：115 PASS、4 Windows SKIP。

上述组有重叠，不相加冒充总通过数。没有执行全量 1108 回归。Windows 原生 handle 精度、真实 launcher→child、四个 owned Job 测试及完整分片均 NOT_RUN。

## 同一标准 runner 的容量与下一次 CI 方案

上一唯一 CI [37470355894](https://github.com/T1doo/ParkWeave/actions/runs/37470355894) 终态失败：准备约 27 秒，native 总耗时约 692.187 秒，其中整组回归内层 600 秒超时。597.547 秒时观察到 548 次 teardown、总收集 1027；它不是 548 PASS。简单线性趋势 `597.547 / 548 * 1027 ≈ 1119.855 秒` 仅提示累积预算不足，不是完整时长预测，也不能断言没有等待。native 其余已运行部分粗算 92.187 秒，仍有浏览器与新增测试、Windows 开销未知。

当前 native 900 秒还为独立 guard/candidate/cleanup 预留 210 秒，直接 opt-in 不足以承诺完成四片。因此本候选不能直接作为“下一次必全量通过”的 CI 配置。

建议仍用现有一个标准 runner、同一 25 分钟（1500 秒）job，先做明确阶段拆分：准备 → lifecycle/server 验证 → 全局 collection → S1～S4 顺序运行 → aggregate → 原独立 guard/candidate → publish/Stop。各片维持 600 秒上限，所有阶段共用 job 起点截止时间，并为 publish/Stop 和未执行独立阶段保留预算。单片失败不跳过有预算的其他片；耗尽则保留证据并明确缺失失败。粗算既往准备+非回归+回归趋势约 1239 秒，可能落入 1500 秒，但余量尚不足以证明完整 Windows 运行。四片最坏上限共 2400 秒，本来就不能保证容纳在 1500 秒内；若实测超过，报告需要的具体时间/布局，不暗增 runner 或总限额。

这里没有自动修改 Engineering.ps1/workflow，也没有实施上述新的共享 job 阶段调度。下一步先审定并实现该同-job 调度方案，再决定一次 native CI；观察只需安全 ROOT/DIRECT_CHILD/REFUSED 类型字段，同时验证真实创建时间精度和借用句柄链。不能据 Linux 结果自动签收 Windows。

R4 关闭、预算 0、无 LIVE/真实模型调用、无部署或 main merge；Server 不等于 Win11。F1 未签收、F2 仅并行探索，36AT/6EX 保持 NOT_RUN，不自动资格判断或外部履约。
