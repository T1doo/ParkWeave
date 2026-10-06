# ENG074 单一清理时钟与精确后代接线候选

基线055d9f7，仅本地Job切片。owner所有流程保持暂停；不做权限实验、原生Windows运行、push/CI/LIVE，不扩大权限或预算。

## 已落地的最小接线

生产WindowsBackend.stop_tree现在在任何观测及TerminateJobObject之前保存唯一cleanup_started，所有终止、原Accounting循环与opt-in观测沿用同一个+5秒截止；原查询前后和最终返回前均gate。同步API自身若阻塞不能被Python抢占；超期返回后拒绝成功，不能声称强制抢占或原生时限已验。

显式候选仅在WindowsBackend提供HeldDescendant(handle,expected_pid,expected_created)时启用。调用方须合法预持有query/synchronize句柄并保留至run返回/抛出后自行close；本层不OpenProcess、不按PID发现或终止、不创建/扩充访问权限、不关闭借用句柄。精确目标必须独立于本run拥有的thread/parent/job句柄，数值别名提前拒绝；连duplicate handle但同parent PID也拒绝。

通过同一heldhandle GetProcessId/GetProcessTimes/Wait0重读，按既有创建时间10微秒容差比对预期身份，再读取其实际innerJob membership、Accounting和signal。beforeTerminate、afterTerminate、accountingZero及finish均在process/job关闭之前；UNKNOWN/nonmember/身份不符、采样上限或截止均FAIL。观测失败仍尝试原owned Job终止，不能因为观测拒绝跳过应做的清理。

默认CLI/CI不传目标，未激活精确后代观测。默认Accounting=0语义仍只是旧聚合清理结果；精确receipt.scope=EXACT_PROCESS_ONLY，不能泛化成所有后代已结束。opt-in成功要求原Accounting=0和目标精确signal；其他后代仍未逐一证明。

本次不是新增后代获取机制：未来原生调用方仍须在同次controlled recipe中合法保留并核对目标句柄，再在清理前传入backend。没有把parent当descendant，没有新增owner/ACL行为，未自动启用CI。现有Windows normal descendantLIVE/S4缺口不因此关闭。

## 验证与可用价值

注入测试调用实际生产stop_tree与run，仅替换底层kernel/只读API，而非整体替换stop_tree。覆盖原退出0/17/timeout、Accounting0但精确handle LIVE→SIGNALED、持续LIVE/UNKNOWN/nonmember/身份错/parent及同PID重复句柄拒绝；主17/timeout保留，错误清理为UNCONFIRMED。finish发生在thread→parent→job close之前，借用目标不被关闭。模拟Terminate或Query耗时正好5秒，默认及opt-in均拒绝刷新budget或超期返回成功。

实际pytest owned_job模块97PASS/4nativeSKIP，相关minimal observations/shards模块76PASS。新增thread/job数值别名拒绝测试，原Job终止仍执行且自有句柄正常关闭；主线程和独立只读审查NO_BLOCKERS_LOCAL。fresh collection1403，四片345/345/349/364与global精确相等，ENG073全部1371 stable keys保留+32；collect不是全仓PASS，历史S4结果不改写。当前价值是让可控清理候选在真实生产函数中检验完整终止时序和精确句柄，避免mock替身绕过生产缺口；它还不能证明Windows上真实后代结束。

固定证据：[JSON](evidence/eng074-optin-descendant-cleanup.json)。原环境、合成数据与备份保留；F1未签收/F2并行、R4关闭、Server非Win11、模型/预算0。
