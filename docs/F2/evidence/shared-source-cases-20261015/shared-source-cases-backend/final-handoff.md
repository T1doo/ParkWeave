共享来源反向定位后端已冻结于 `bc4f384fa32817ddf3b332f898d59b5b994bfe2f`。本 agent 仅实现 `shared_source_cases.py` 和其 23 项真实 HTTP/PostgreSQL 测试，未写 Git；冻结后仅写本目录交接文件。

最终开发完整窗 23 PASS / 98.36s，日志与 JUnit 为 `final-focused-second.log` / `.xml`。此前两窗的 2 项、1 项失败均为夹具构造错误，原日志完整保留；修复未放松数据库约束。坏对象目标重跑 1 PASS / 3.07s。根负责另外 64 模块冻结 SHA 正式回归。

已覆盖两个真实共享源身份、资源 P2–P5 与 P1 锁保留、目录精确版本、无计划/无 preparation、不混入材料整体影响、所有者/租户/角色/撤权拒绝、来源和 preparation ABA、跨页版本变化、分页未核对 UNKNOWN、界限溢出、忙锁 409、损坏对象安全 UNKNOWN 与递归/重复游标拒绝。两类图版本字段明确固定，未改原历史编译器或事件。

有限范围为原 owner/tenant/park 的最多 32 个合成 Case；每 Case 原事务读，首尾快照校验，不宣称跨 Case 原子快照或客户端页访问历史。未执行 Windows、真实浏览器、正式 AT、真实模型、生产或真实治理验收。无后端已知阻断；后续按根的冻结回归结果推进。
