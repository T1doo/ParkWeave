# ENG046：专用 Windows JobObject 后代回收（本地实现）

基线 88feb1d。用户单独授权处理已复现的自有后代存活；SESSIONS owner 审批尚未收到，当前轮未实现或执行该权限变更，未 push、新 CI、LIVE、提权或修改 runner/ACL。原环境、恢复包、运行历史与 ENG041 失败性质证据保留。

## 保留失败基线

本轮在 Linux 再次运行原直接父超时探针：测试本身 1 PASS/2.10 秒，但被验证的生命周期性质是 **FAIL：直接父被杀后，身份验证的自有后代仍活**。独立监督器随后仅回收该探针自有后代。原测试没有被改成期待新 Job 的成功，未把基线 PASS 写成后代清理已通过；XML 在 `.runtime/eng046-descendant-before.xml`。

## 实现与所有权边界

新增 `scripts/windows_ci/owned_job.py`，只接入 Windows 外层 `native_command` 的 `native_suite`（仍 900 秒）以及内层 regression 的 run_acceptance（仍 600 秒）。其他 native_command 阶段保持原直接子进程机制；单次 PowerShell 生命周期调用未单独改用新 wrapper，以免其返回时就杀掉需要持久运行的服务。

外层 Job **会默认包含 native_suite 随后创建的生命周期/PowerShell 等所有后代**，包括该子树后来创建的 PG 进程（若有）。这不是仅包 Python 的名单；超时、正常协调器结束或 Job 最后句柄关闭会停止该 Job 内残留后代。已在外部启动且不属于该 Job 的 PG/无关进程不加入、不扫描、不终止，工作流原独立 owned PG Stop 保持。内层 Job 包含本次 run_acceptance→pytest→测试后代；两层嵌套允许条件仍须原生验证。

每次新建无名、不可继承的 Job，仅设 KILL_ON_JOB_CLOSE。通过 CPython `_winapi.CreateProcess` 挂起创建同一身份的新进程；不使用 alternate token/RunAs。使用本次返回的 kernel process handle 与 PID 对照，再 Assign 到本次 Job 并 IsProcessInJob 验证，之后 ResumeThread，预期单次 suspend count 为 1。持有 creation handle 避免 PID 重用带来的错误对象；不 OpenProcess、枚举进程或按名称/记录 PID 杀进程。

stdin DEVNULL、stdout/stderr 普通私有文件；STARTUPINFOEX 的继承白名单仅含三个本次复制的 stdio handles，Job/process/thread handles 不继承。不设置 breakaway、security/UI/资源限制，不调试提权或改变身份。绑定拒绝停止本次新建进程并失败，绝不重新以无 Job 方式启动。

正常直接父退出后也终止本 Job 残留后代；超时或协调器异常时同样只处理本 Job。TerminateJobObject 后在 5 秒内查询 ActiveProcesses=0 才标记 OWNED_TREE_STOPPED；确认失败明确 UNCONFIRMED，仍释放本次句柄。最后 Job 句柄关闭作为进程异常退出的内核回收后盾，不能代替确认。API 与继承依据：[AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)、[Job limits/KILL_ON_JOB_CLOSE](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)、[CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)。

## 失败与公开诊断

原非零退出码保持（测试用 17）；原 TimeoutExpired 保持，外层仍 exit124/timed_out。清理失败单列，不将失败转 PASS；直接父成功但清理失败则整个执行失败。固定 `owned_tree_cleanup` 四状态沿既有回归摘要/annotations 传播，原 8条/2KiB/16KiB/25测试ID边界保持；不公开 PID、路径、命令、WinAPI 原始错误、stdout/stderr 或凭据。

两位独立复核发现并关闭创建期句柄缺口：CreateProcess 成功但返回前 stdio 复制句柄关闭失败，原会丢掉挂起 child 的 creation handles；现在创建函数自己精确终止该 child，逐项尝试关闭所有 stdio/thread/process，保留原拒绝与清理状态。设限失败后的 Job 关闭错误也保留。新增低层 fake 注入三个关闭失败、CreateProcess 拒绝和 Job 设限/关闭失败；不把 fake 当真实 Windows 行为。

## 验证和未验证项

Linux 的原后代存活基线实际复现；portable 合同/fault injection 覆盖绑定先于运行、无 fallback、精确句柄清理、非零/超时保持、清理失败不能 PASS、固定 Win32 宽度及 x64 结构大小、stdio handle list、600/900 集成和安全投影。

原生 Windows 专用四用例已编写但当前全部 SKIP：正常非零父结束后的后代退出、父超时后的后代退出、绑定拒绝后正文零执行、协调器突然退出时最后 Job handle 关闭后后代退出。用例同时观察独立无关进程存活；只按已返回 Popen 回收自身无关对照/协调器，不按探针记录 PID 扩大清理。突然退出记录采用原子替换，退出观察容忍进程已消失的正常竞争。

初始相关执行 92PASS/3FAIL/3SKIP：两项既有 loopback/isolated PG 探针因默认沙箱 socket PermissionError 失败，另一个白名单待更新；没有为它们改网络策略或权限。低层注入中间 14PASS/3FAIL/4SKIP 为新测试事件列表解包错误，已修正，原证据保留。更新后候选102PASS/4SKIP/2DESELECTED，publisher/preparation50PASS，最终冻结定点 **152PASS/0FAIL/4WindowsSKIP/2受限socketDESELECTED/1既有WARN/8.33秒**；7份变更源 SHA256 与测试后字节一致，完整成绩见 [证据](evidence/eng046-owned-job.json)。两个受限 socket 探针不属当前回收修复验证，最终显式 deselect，不记 PASS。

**OWNED_REGRESSION_DESCENDANTS：IMPLEMENTED_NATIVE_VERIFICATION_PENDING，尚未关闭。** 当前 Linux/mock 不能证明 Windows Job ABI、真实后代退出、嵌套 Job 与 runner 限制。实际 Windows 600 秒挂点仍 UNKNOWN，不能把此独立生命周期修复作为该根因证明。F1/F2未签收、Server不是Win11、36AT6EX NOT_RUN、R4关闭、真实模型/预算0。
