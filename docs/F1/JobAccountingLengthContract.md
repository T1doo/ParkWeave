# Job会计查询：实现前拒绝合同

基线 `b6db56256df1c29c155faa67acf8463def87f5b9`；原F1-T01/F3-T06、AT01/17/18/34的底座可靠清理子条件。用户要求尽快消除交付关键阻塞、保持质量；本轮只修生产`WindowsBackend.stop_tree`已有会计查询结果验证，不恢复原生创建/完整CI，不改安全配置、权限或清理范围。旧未推送a823a28未取得，不称迁移/重建该提交。

已在当前基线以离线kernel注入复现：`QueryInformationJobObject`返回成功但不写任何会计数据，生产传入NULL返回长度，初始化`ActiveProcesses=0`被当作`OWNED_TREE_STOPPED`。这不是真实Windows观测，而是缺少完整输出校验的故障实证。

[微软QueryInformationJobObject契约](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)明确class1为[基本会计结构](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)，输出返回长度表示实际写入字节数。候选每次查询提供独立DWORD返回长度，先核对API成功和精确`sizeof(Accounting)=48`，再消费ActiveProcesses；未写/短/超长输出均固定`JOB_QUERY_REFUSED`，不能用默认零值认定树停止。每次重试新建输出/长度对象，不能复用上次长度或成功状态。原结构宽度/字段布局、查询class1、原Job句柄和原五秒预算不变。

当前后置deadline重验、单次原Job终止、最多原观察样本、借用已持有后代句柄、无目标时默认路径、主退出17/timeout保留、thread→parent→job关闭顺序和清理失败独立报告保持。长度错误不产生新的terminate/retry/fallback；不新OpenPID、扩大杀进程、提权或获取安全对象。只读观察者原返回长度检查不削弱。

冻结验证应覆盖：完整零输出可结束；完整非零等待到零；API失败及无长度/短/超长拒绝；前次完整非零后次缺长不能继承；原deadline耗尽拒绝；主成功/17/timeout与清理失败分别记录、原句柄全部按顺序关闭；受控测量/原观察/预算/固定诊断兼容。全部Linux注入/ABI证据明示，native跳过保持跳过，不能称Windows/任意树验收PASS。

源码候选普通推送后独立只读审查；未审不合dev。独审若限定通过，按现有授权普通FF/dev推送并核验远端。原生正常后代、受保护authority、Windows/Win11及正式AT仍未签收；原生返回长度及真实进程终态仍须获准设备上实测。日志与失败保全。

首轮兼容发现固定诊断test-ID白名单落后于已集成的资料异议/资源组合及当前新测试，守卫正确拒绝。本轮只按所有现有test函数的AST精确刷新该白名单，保留全部旧ID、schema与数量/隐私约束；不恢复完整workflow或改时间预算/原生状态。原310PASS/1FAIL/7SKIP日志保全。
