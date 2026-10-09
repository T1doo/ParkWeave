# Job清理会计输出完整性候选

沿原F1-T01/F3-T06修复已复现的会计查询拒绝边界，先冻[合同](JobAccountingLengthContract.md)再实现。`WindowsBackend.stop_tree`每次class1查询使用独立DWORD输出长度，只在API成功、原deadline内且输出恰好48字节后读取ActiveProcesses；未写/短/超长均JOB_QUERY_REFUSED，不能把初始化零值算树停止。原单Job终止、五秒时钟、借用观察句柄、主退出/超时与清理失败分列、句柄关闭顺序不变。不获取新进程句柄/权限，不改ACL/owner/网络/部署，旧a823a28未取得或移植。

冻结相关 **311PASS/0FAIL/0ERROR/7SKIP/1WARN，7.275秒**，318项；含新14项真实生产控制流/注入WinAPI输出，原Job/受控测量/预算/调度/原生命令/安全诊断/分片兼容。305源码/测试/脚本和JSON哈希无漂移。7SKIP逐项保留为Windows原生限制，不计PASS；1WARN是现有Starlette/httpx弃用。本轮无需HTTP/PG页面重跑：修改仅Windows Job输出验证及离线诊断ID，未改变已审业务源码；资源461及独审111+5仍只属于其原受审字节。

首轮310PASS/1FAIL/7SKIP是诊断AST白名单未登记此前异议/组合及本轮新测试，守卫保持，按现有AST精确刷新1147→1221ID，全部旧ID保留；原失败日志在私有`.runtime/job-accounting-length/first.log/xml`。没有删测试/增跳过或弱化oracle，也未刷新/恢复完整Windows workflow、增加预算或称全仓PASS。

[JUnit](evidence/job-accounting-length/frozen.xml)、[日志](evidence/job-accounting-length/frozen.log)、[源指纹](evidence/job-accounting-length/source.json)、[机器记录及跳过原因](evidence/job-accounting-length/verification.json)。候选普通推送后独立只读审查，终态后补；未审不合dev。Linux注入只证明拒绝协议，真实Windows返回长度/Job后代终态、Win11安装信任、protected authority、42AT/EX及完整全仓仍未验收。底座未签收，不能由此声称月底完整V1已完成。
