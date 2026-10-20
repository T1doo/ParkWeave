# Windows 预检 OS_METADATA 有界采集修复

从 `fcb191bd81b5e8cba1e076e1832c8af3c5923669` 接续。执行环境已恢复，Git工作区干净，远端一致；已成功的通知浏览器CI不重复。新分支 `dev/windows-native-metadata-20261020`，main和旧分支不改。

## 新收到的旧失败原始事实

父侧在正常登录的助手云浏览器成功读取旧 [job118403953546](https://github.com/T1doo/ParkWeave/actions/runs/39353828380/job/118403953546) step4第17行：受测源 `eb7f5377eba58aea69db7a2f1d9716a62b8cb8d9`、psutil7.2.2，`OS_METADATA` 阶段 `subprocess.TimeoutExpired`，timed_out=true、20.11秒，stdout/stderr空、cases=[]，随后driver exit1／FRESH_NATIVE_SUBSET_FAILED。此前该错误未送达，并非认证失败；原生包装器尚未启动。这里记录可信父侧原始观察，本实例没有重读旧日志或调用已拒绝API。

按该提交源码核实，原实际子进程为：

```text
powershell.exe -NoProfile -NonInteractive -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,BuildNumber,ProductType | ConvertTo-Json -Compress"
```

父进程原20秒超时已终止该采集调用；PowerShell启动、模块加载或CIM提供者内部究竟卡在哪一步，现有空输出不能判定。不是五个原生用例已失败的证据，也不据此修改OS权限、服务或执行策略。

## 精确改动与真实版本门

原 `scripts/windows_ci/fresh_preflight_once.py` 改为同一次已选择的venv `sys.executable -I -S -B -c <固定stdlib代码>`：仅导入json/sys，`sys.platform`必须win32，再读取 `sys.getwindowsversion()` 并输出有界ASCII JSON。父进程仍经原capture调用，**一次、20秒、无重试或fallback**；不启动另一个PowerShell/CIM元信息进程，不加长预算。

复用仓库 `server_candidate_probe.py` 已有的原生build/product_type方式，并明确严格类型：major/minor/build/platform必须10/0/26100/2，product_type必须2或3；Windows工作站即使build26100也拒绝。未知、非零退出、坏JSON、超4KiB响应或字段错误都不能继续原生用例。原始字段直接保存，不编造Caption；ImageOS只作日志，不作为OS真实性证据。

[Python3.12官方说明](https://docs.python.org/3.12/library/sys.html#sys.getwindowsversion)确认该函数包装Win32 GetVersionEx，product_type区分工作站／域控制器／服务器；platform_version取自kernel32，按官方要求仅记录诊断，不用于版本判定或替代原门。[Microsoft发布表](https://learn.microsoft.com/en-us/windows/release-health/windows-server-release-info)列Server2025为build26100。兼容模式／manifest造成的版本不匹配仍保守拒绝，不伪装或恢复权限。

原五步Doctor／Setup／Start／Status／Stop、25秒各步预算、原预期拒绝／NOOP、fresh状态、文件hash、模型关闭、owner/ACL暂停门均未改。17个 `scripts/windows` 与原process_env/session底层文件和本片基线逐字节一致；不创建应用runtime/config/session、数据库或API/worker。超时记录补充明确limit与elapsed秒数，仍不发布原异常命令／环境。

## 测试与独审

本地标准库8项全部通过，包含实际Linux隔离child退出2/空输出、工作站/错误版本/类型与坏响应拒绝、单次原20秒调用、超时和非零退出不fallback，以及精确CI身份／分支／次数门。独立再执行同8项通过，范围重叠不相加；这不是Windows成绩。有限静态独审无开放P1/P2，没有启动本地Windows或操作用户电脑。

新一次性workflow沿旧已审路径复制：仅公开T1doo/ParkWeave、新分支run1/attempt1、标准windows-2025、一个job6分钟；原固定checkout/稀疏路径、仅psutil==7.2.2 wheel/no-deps/no-cache/零重试和RUNNER_TEMP私有venv保持。没有升级依赖、安装Python/PG/浏览器、secret、artifact、发布或安全权限变化。依[GitHub官方计费规则](https://docs.github.com/en/billing/concepts/product-billing/github-actions)，公开仓库标准runner免费。

原Windows workflow及通知浏览器workflow没有修改。没有重跑旧run；新CI实际回执另记，不预写PASS，不把Windows Server预检当Win11、成功安装／启动／停止／重启或正式AT01/04/05/34通过。
