# 剩余四包装器 fresh prerequisite/refusal 子集

基线 `dc502414daac72f3f4c63bb8ce6b07082465e9fb`，分支 `dev/windows-four-wrapper-fresh-20261020`。用户批准一次有界免费标准Windows CI，并明确要求将已证实Doctor入口的同源命令绑定修复，仅推广到四个已知同构入口。main和Doctor已通过源码不改，不重复Doctor、阶段诊断、浏览器或网络检查。

## 最小入口修复与受测输入

Setup/Start/Status/Stop.ps1各仅一行，将原 `. (Join-Path $PSScriptRoot 'Common.ps1')` 改为 `. (Microsoft.PowerShell.Management\Join-Path $PSScriptRoot 'Common.ps1')`；原参数、路径目标、action及默认调用不变。不广泛替换Common或其他命令，不更改安全策略/环境白名单/执行权限。此前Doctor的实际阻塞定位和默认2.171秒验证见[原报告](WindowsDoctorBoundary-20261020.md)；未限定命令内部等待机制仍未知。

四个动作都在新CI隔离checkout中，经原 `powershell.exe -NoProfile -NonInteractive -File <原包装器> -Python <本窗RUNNER_TEMP私有venv解释器>` 各一次执行，不带TraceStages。每步原25秒门，Server原20秒真实版本门；继承原最小环境覆盖，仅PYTHONDONTWRITEBYTECODE/PYTHONUTF8固定值，不提供任何业务配置。仓库 `.runtime` 和 `.venv-windows` 必须在每步前后不存在；只允许公开T1doo/ParkWeave、新dev分支首次push/run1/attempt1、原生Windows2025 hosted runner和精确源码SHA。

| 顺序 | 原预期退出 | 原 fresh 结果 | 不进入的操作 |
|---|---:|---|---|
| Setup | 1 | OWNER_MUTATION_PAUSED | require_setup_readiness在check_python、应用venv/pip、数据库及ACL操作前拒绝 |
| Start | 1 | CONFIG_MISSING | load_config先拒绝，不进入端口检查、API/worker或DB |
| Status | 1 | 原setup-not-completed错误文本 | load_config先拒绝，不进入受管进程身份查询 |
| Stop | 0 | NO_MANAGED_RECORD原文/NOOP | 无STATE直接返回，不查询/终止进程、不删除数据 |

CI的RUNNER_TEMP工具venv仅沿用已批准psutil7.2.2 wheel/no-deps/no-cache/零重试，不是应用安装或Setup成功。模型/数据库调用、owner/ACL/安全权限变更均不属于本窗控制流。驱动复用原Server真实版本采集、fresh状态和17源码hash检查；只保留原四个预期步骤，删除Doctor调用。实际attempted_actions先登记，超时不把cases空误写为未调用；超时原类型/时间/两流hash和原字节临时文件保全，固定原错误协议在退出/拒绝判据之前记录，不输出原始环境/异常/凭据内容。

## 范围和本地核验

workflow保持公开标准windows-2025、contents:read、固定checkout、稀疏路径、单job6分钟、执行step3分钟及原工具准备步骤。没有新的secret、artifact/cache、外部服务、安装Python/数据库或关闭sandbox。单窗最多四个原25秒动作，不循环盲跑；若有失败，立即停止后续步骤并按原证据处理。

本地运行既有8项metadata标准库合同全部通过，含真实Linux隔离子进程拒绝及注入Server/guard验证；这不是Windows成绩。本片没有新增测试文件或测试用例。新driver语法及diff检查通过；既有pytest因当前环境缺模块仍NOT_RUN，未安装依赖。

本窗实际结果待回执，不预写PASS。即使四项原拒绝/NOOP全部符合预期，也仅证明Windows Server fresh prerequisite/refusal subset；不算完整安装、真实业务启动/停止/重启、业务隔离、Win11或正式AT01/04/05/34验收。Doctor来自前一独立窗口，不拼接成同一原生整窗通过。
