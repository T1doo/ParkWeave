# Run 29 与调试附加握手修正

本次精确构建通过，实际原生运行仍 failure。新数字诊断记录原 ResumeThread 前暂停计数 2、Win32 error null；原进程句柄 WaitForSingleObject 返回 258，说明该次观察仍存活，未观察到退出码。不能把它解释为 API 返回 -1、进程已崩溃或数据库已可用。

原 before_resume 调用 watch，只等待 DebugActiveProcess 调用返回；泵线程此时可能尚未处理初始调试事件。微软文档说明 DebugActiveProcess 会临时挂起目标线程，初始事件需要 ContinueDebugEvent。该时序与计数 2 相容，但尚非完整原生根因证明。

本地修正为等待同一原调试泵的 ready；这个事件只在初始断点被原有验证器识别、ContinueDebugEvent 成功后设置。还核对初始事件、断点、未退出、无泵失败，并重验原进程 birth 与原 deadline。ResumeThread 的成功条件仍恰好为 1，不接受额外计数、不循环恢复、不卸载调试器、不改线程上下文。

37 项相关协议/拒绝/所有权检查通过，19 Linux-only skipped。新时序尚未在原生云端验证；可能仍有后续事件竞争或握手不支持，失败须据实保留。禁止把单元测试当成数据库/API/worker 或界面验收。

官方依据：[DebugActiveProcess](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-debugactiveprocess)、[调试线程控制](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/controlling-processes-and-threads)。对当前项目的解释是结合文档与本次观测作出的推断。
