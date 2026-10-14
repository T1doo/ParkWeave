# 有来源人工答复、精确知悉与本次责任收尾

从父级有限签收f758aa19b9a1eb0f30520cda0ce2db1e47952340接续原合同，源码冻结 `3feab9acce5affcbd5bee9a7da224ce11178fb65`。原专员本人接责后提交有材料引用的人工意见或明确无法办理，企业owner精确核对原答复事件ID、fingerprint与当前source SHA后另行明确记录知悉。知悉结束本次人工责任及当前待办；历史保留，无自动答复、自动知悉或恢复旧任务。

新增REPLY→WAITING_OWNER_ACKNOWLEDGEMENT、ACKNOWLEDGE_REPLY→COORDINATION_ENDED，仅原计划独立人工ledger，不改原计划步骤修订、Run成功事实、Case、目标结果、资源或Grant。INFORMATION须当前同Case资料引用；UNABLE_TO_HANDLE只是本人明确无法办理说明，不要求假造材料来源。两种答复均绑定当前原Case/Run/计划/请求/资料来源；意见真实性未核实、知悉不证明实际阅读或真实答复。目标仍UNSUPPORTED、整体PARTIAL、Case未完成、资格／批准／外部受理／履约均不推进。

企业知悉待办使用当前合法共享ledger，原专员答复后不再是其待核对任务；企业知悉后两角色无该人工待办。从未REQUEST的自由文本不外泄，撤回、旧计划及原key历史不变成当前任务。原界面展示答复类型、说明、材料引用、事件ID和指纹，额外明确确认知悉才保存原key并POST。沿已修caller代次的渲染前核对，失效响应不改新草稿／句柄。

来源变化、Case取消/核对中/本地关闭、撤权或换计划时按原当前授权与来源拒绝新办理；原READ有权历史保留。ACK还要求reply保存的source SHA与当前来源一致。原actor key跨Case限定，同参返回原事件、异参409，丢响应仅GET原key，不自动重发；当前读/写授权仍分别核验。当前parent锁及key锁与最后等待后的权限重核保持，reply状态和事件同JSON事务保存，失败完整回滚。

32条有界ledger为每个待知悉reply保留一个ACK/明确撤回槽；新reply不能用光最后收尾槽，其他目标不能占用保留额度。capacity仅约束allowed_actions，不扩schema/Grant或篡改原历史；原五动作fingerprint按排除新optional None精确保留。

## 身份、环境和已执行开发窗

实际使用原隔离夹具 `template-new-enterprise-a` owner、`template-new-reviewer-a`原专员；拒绝矩阵另用 `template-new-enterprise-b`和`template-new-reviewer-b`。均是原合成测试身份，沿原fixture种子权限；feature API全过程Grant snapshot不变，不创建新业务Grant。数据为自有临时PostgreSQL、原ASGI API及完整原HTML NodeVM；没有浏览器或现实自然人签收。翻页等旧回归夹具不计现实业务。

先行红窗两种REPLY均422拒绝，2FAIL，原log/XML/exit保全。实现后核心与原五动作27PASS；新增API独立窗口28PASS；原页6窗6PASS（normal/unable/lost_reply/lost_ack/cancel/late）；收尾容量2PASS。开发窗不与最终冻结回归及独审加总。真实PG parent锁等待材料变版／Case取消胜出后ACK409，原答复历史保留；并发同key一事件、异key一胜一409，事件保存失败rollback与冷热原key恢复均专项验证。

最终冻结统计、模块清单、独审与归档核验将在最终记录中列明；只签实际运行范围，不转签前片80/222或旧365全仓成绩。

浏览器历史ERR_BLOCKED_BY_ADMINISTRATOR、prepare元数据Forbidden持续停止；浏览器、prepare、部署、生产迁移、真实/付费模型及全仓均NOT RUN。没有配置凭据/网络、安全权限、真实通知、新服务/registry或保护分支写入。两approval沿原false/null/null和原SHA256保留。

独审实际快照覆盖原11业务表（仅独立manual ledger变化）及Grant；资源表未在独立12中另作占用快照，资源不写是源码审查范围，不宣称本片重验取消/释放容量全矩阵。

冻结根13模块 **306PASS、0FAIL/ERROR/SKIP、2WARN、267.983秒、exit0**；独立实际PG/API **12PASS、0FAIL/ERROR/SKIP、2WARN、14.563秒、exit0**。505文件前后hash零漂移，源码到证据交付仅文档。

根模块实际数量：

- `tests.test_manual_goal_reply`：36
- `tests.test_manual_goal_tasks_late`：4
- `tests.test_manual_goal_tasks`：15
- `tests.test_preparation_tasks`：19
- `tests.test_manual_goal_requests`：25
- `tests.test_manual_goal_privacy`：11
- `tests.test_case_worklist`：17
- `tests.test_case_worklist_offline`：21
- `tests.test_template_full_chain`：4
- `tests.test_service_case_steps`：68
- `tests.test_template_consumer_planning`：25
- `tests.test_template_partial`：17
- `tests.test_case_goal_results`：44

原完整HTML6专项分别：

- `normal`：14断言／11HTTP／2POST，PASS。
- `unable`：14断言／11HTTP／2POST，PASS。
- `lost_reply`：16断言／11HTTP／2POST，PASS。
- `lost_ack`：16断言／11HTTP／2POST，PASS。
- `cancel`：12断言／8HTTP／1POST，PASS。
- `late`：12断言／8HTTP／1POST，PASS。

6页窗包含在根36项新模块中，不与306或独立12加总；cancel窗的明确原Case取消为单列原API测试驱动桥，不算manual page POST。无浏览器布局验收。

[机器证据索引](evidence/manual-goal-reply-20261014/export-index.json)、[精确统计](evidence/manual-goal-reply-20261014/validation.json)、[独审结论](evidence/manual-goal-reply-20261014/independent/review.json)。原件保留.runtime，导出仅脱敏fixture会话repr；红窗失败文本/统计/尾空格原样保留，不改失败来消除空白告警。

归档只读独审PASS：40件原件／导出hash、字节数和唯一脱敏范围准确；505源码及两approval零变化，统计、失败保全、身份和资源验收边界一致。原件 `.runtime/manual-goal-reply-20261014/independent/archive-review.json`。源码／报告空白检查PASS，归档失败log/XML尾空格原样保留。
