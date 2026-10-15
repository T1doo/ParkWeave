# ServiceRelease 单 Case 只读预检：本批证据

最终验证源码：`0de44714499ff3ead538dd8dc1436e783ab8f944`。基线交付为`b2690b4316e2ca4e98c0b83ee2675db74239ccae`，开发WIP、失败设置/收口窗口与正式冻结窗口在归档中分别保留；`index.json`的source_sha是最终参考，不表示每个历史条目都在该SHA重跑。

四个不重叠完整窗口为root27模块900PASS、root25模块789PASS、independent6模块198PASS、review9模块300PASS：同一SHA共67完整相关模块/2187唯一项，不是全仓执行。另3个独审探针单列PASS。参见[实际并集与执行窗口](service-release-preflight/final-coverage.json)、[独测同窗核验](service-release-preflight-independent/freeze-0de4471-formal-validation.json)、[冻结独审](service-release-preflight-review/review-0de44714.md)。

本批preflight oracle按known15例/62对、intentionalUNKNOWN4例/20对分列；预检14个Node VM模式包含12条实际后端响应流及pending/unknown_dto两项DOM/transport负向。旧typed6/shared9本轮重跑；不能把29模式都说成真实后端拒绝，更不是真实浏览器验收。详细受控故障与输入/输出边界见[独测交接](service-release-preflight-independent/freeze-0de4471-formal-handoff.json)。

273个raw/export配对，公开配对载荷36,174,819字节。仅替换已登记合成会话值32处、pytest截断fixture repr72行；私有原件hash/大小保持。20 XML、79 JSON、57 JSONL、25 Python、2 JS的结构/状态或源字节分别核验，已知合成会话残留0。私有集合、SQLite/PostgreSQL文件、缓存、无关runtime不导出；共用旧模板去敏集合仅用于识别合成值，不是本批独占测试证据。通用fast redactor继承已验证方法，不能声称算法来源多样性。

`audit.json`保留根检查当时的checkpoint，独立重建和最终完整门的后续结果见[独立审计目录](../service-release-preflight-audit-20261015/)。不覆写初始失败/中断窗，不改XML用例名/状态充当通过；唯一预收集import-time UUID归一仅发生在另外的预收集比较，各正式窗raw collection/JUnit始终精确匹配。

业务PG/Case/六目标/P1–P5/原历史和锁保持；拒绝请求沿用原authorization_audit。新日志只保存只读预检证据，不授权发布、迁移、回滚、ADOPT、VERIFY或执行。Windows、真实浏览器、正式AT24–27、真实产品模型、生产及本分支远端CI均未执行；模型调用0，无费用/权限扩展、部署、强推或main修改。
