# Doctor PowerShell 入口有界诊断

基线 `f8efe74aa80157139db679038c38489da36acabb`，分支 `dev/windows-doctor-entry-20261020`。恢复时实际差异为三个未跟踪文件：一次性 workflow、入口探针、5 项合同；没有已跟踪文件差异。三个文件与此前只读独审的 SHA256 完全一致，已保全并提交。网络核验已完成，本任务没有重复网络检测。

## 本轮唯一 Windows 实测

受测提交 `525a89813f32d69d38e1e17e0f47fa74a3d5ae0f`，[run39361011240](https://github.com/T1doo/ParkWeave/actions/runs/39361011240)／[job118426947418](https://github.com/T1doo/ParkWeave/actions/runs/39361011240/job/118426947418)，run1/attempt1，公开标准 `windows-2025`，job 实际成功，公开总时长39秒。只读取本次新 job 的日志，未重试旧已拒绝日志目标。[原始 driver JSON](evidence/windows-powershell-entry-ci-20261020.json)完整保留，未将局部结果改写为 Doctor 或原生验收通过。

真实 Server 门通过：`sys.getwindowsversion` major10/minor0/build26100/platform2/product_type3，0.047 秒。Python3.12.10、psutil7.2.2，ImageOS `win25-vs2026`、ImageVersion `20261007.264.1`。沿用原 Server20秒门和 RUNNER_TEMP 私有 venv，仅原已批准依赖 pin，无额外安装或权限变更。

单次固定命令为 `powershell.exe -NoProfile -NonInteractive -Command "[Console]::Error.WriteLine('PS_ENTERED'); [Console]::Error.Flush(); exit 0"`。父进程沿用原 `minimal_environment(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")`，没有扩展白名单，子进程键集合已记录在 JSON；没有换成 pwsh 或增时。

实际 **2.047 秒**、exit0、未超时，stdout 为空，stderr 仅 `PS_ENTERED\r\n` 并 flush。stderr SHA256 为 `411bd85022a02ea289ccda71d9e6c79246a9b291bb0c083974b90697da323421`。父进程上限仍为25秒；报告 `PASS_POWERSHELL_ENTRY_ONLY`，driver 总2.141秒。该 CI 执行时17个原启动器及底层文件 hash 前后不变，应用状态始终不存在。

这仅证明本次 runner、同最小环境的一次简单 `-Command` 命令进入并正常退出；不能证明旧 `-File Doctor.ps1` 已进入，也不能排除此前瞬时启动问题。此前 Doctor25秒无输出失败没有复测或修复结论，内部卡点尚未定位。Doctor 未调用、内部标记未执行、Setup/Start/Status/Stop 未运行，Win11、完整 AT 和原生包装器验收保持 NOT_RUN。

## 实测通过后准备的内部标记（尚未 Windows 执行）

按“先证明入口，才加内部阶段标记”的条件，另行准备默认关闭的 `Doctor.ps1 -TraceStages`，经 Common/解析器传递 switch，并向原 lifecycle 命令追加固定 `doctor --trace-stages`。仅显式开关开启且 action 为 Doctor 才输出固定 `PW_STAGE:` 字面标记，stderr 每次立即 flush；不打印解释器路径、参数内容、子进程响应、异常内容或环境值。

覆盖 Doctor 入口和 Common 加载前后、Repo/managed Python 检查、Get-Command/Test-Path/Get-Item、lifecycle 调用前后、Python 首入口/导入完成/main/native guard、Doctor/check_python 调用前后及 JSON 输出前后。Python 开关仅接受规范的 `doctor --trace-stages`，其他 action 或反序选项在动作前拒绝。普通调用不输出阶段标记；原 subprocess 命令、环境、版本拒绝条件和退出判定保持。

这批准备修改了 `Doctor.ps1`、`Common.ps1`、`PythonCommand.ps1`、`lifecycle.py` 四个源码文件；上述17文件不变结论仅属于受测提交525a8981，不延伸到标记准备后的源码。原 Doctor25秒门、Server20秒门、fresh 状态检查、安全策略和最小环境实现均未改。没有第二次实际 Windows 测量；workflow 的 job 前 run1/attempt1 门设计为拒绝归档 push 的 run2，不启动 runner，这是门禁规则，非本文归档时已观察的回执。下一步准确待办是另一个有界窗口内执行带标记的 Doctor 并按最后标记缩小阶段；当前不能推断具体根因。

## 验证和独审

入口5项标准库合同通过；独审独立同5项通过，范围重叠不叠加。入口实测边界再次独审通过：局部 PASS 不代表 Doctor、AT、Win11 或原生验收通过。

标记5项标准库合同通过，独审独立同5项通过，重叠不叠加；无开放 P1/P2。包括真实 Linux CLI 默认/带标记拒绝的 exit1 和 stdout 一致、拒绝非规范参数、解释器检查原单次命令和最小环境、异常前后标记差异、不允许其他 action 进入诊断。它们仅为 Linux 拒绝路径及 mock 合同，不是 Windows 内部阶段成绩。静态独核原 lifecycle 函数在移除新增标记后结构不变；原最小环境源码和 fresh preflight 驱动未改。

尝试现有 `tests/test_lifecycle.py`、`tests/test_lifecycle_diagnostics.py` 及新增合同的 pytest 回归命令，在测试收集前因当前 Python 缺少 pytest 退出：`No module named pytest`。环境中未找到 pytest 可执行文件或已有工作区虚拟环境；未安装依赖，该批既有 pytest 回归记 NOT_RUN。新增合同随后以标准库 unittest 实际通过，未将依赖失败写成回归通过。尚未运行的 Windows 标记不计测试成绩。
