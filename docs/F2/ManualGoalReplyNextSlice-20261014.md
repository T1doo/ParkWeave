# 本片合同：原人工答复与企业明确知悉

本文件为实施合同；有限实现源码 `3feab9acce5affcbd5bee9a7da224ce11178fb65`，实际验收另见 [人工答复交付报告](ManualGoalReplyDelivery-20261014.md)。依据原产品 §5.5 的明确责任／授权人工确认、§7.1 的业务结果与Run技术成功分开，以及§7.3/7.4 的幂等、未知结果与当前授权重核，接续已有人工请求／补证链。既有 REQUEST/TAKE/REQUEST_EVIDENCE/SUPPLY_EVIDENCE/WITHDRAW 没有原专员正式人工答复或企业知悉事件，责任不能据“材料已交”自动结束。

本片只为当前计划已合法REQUEST的未支持目标增加两次明确动作：原已接责专员提交带说明和当前资料引用的人工答复；原企业owner只读核对该精确答复后明确知悉，结束该次人工协作责任。提交答复后企业形成知悉待办；知悉后该目标不再进入当前人工责任待办，完整历史保留。未请求私有目标、旧计划和撤回仍不变成当前任务。

结束只表示本次人工协作责任结束。目标继续UNSUPPORTED，整体PARTIAL，Case未完成；不产生资格／批准／外部受理／线下履约／服务能力／Grant，不用“已知悉”填补必需目标。Case取消与资源释放保持原独立合同。

沿当前original owner/reviewer权限与parent锁，新增事件仍在原计划独立有界ledger；绑定当前Case/Run/plan、精确原答复事件、ledger revision、资料版本／source SHA、原key及原因。同key同参原结果、异参409，状态与事件同事务。丢响应只GET原key核对，不自动重发。实际换计划、撤权、关闭／取消、资料变版或损坏证明时禁止新写，合法历史保留；旧页面迟到读取必须遵守本次渲染前守卫。

必须验收：当前/冷读两角色答复→明确知悉→责任结束的真实PG/API/原页链；专员未接责／企业未看精确答复／跨租户或非owner拒绝；撤权和来源变化；同异key及并发CAS；事件失败全回滚；丢响应冷热原key恢复；待办撤出与旧历史读取；全过程原目标、Case、Run、资源、Grant和原计划步骤修订不被伪推进。不得重试被拒绝浏览器或prepare，不引入真实／付费模型。

实施细化：REPLY只能由UNDER_MANUAL_REVIEW原专员提交。INFORMATION至少一份本Case当前材料引用；UNABLE_TO_HANDLE可无材料引用，但须明确无法办理说明，仍绑定当前Case/请求/资料来源整体SHA。两者进入WAITING_OWNER_ACKNOWLEDGEMENT；owner的ACKNOWLEDGE_REPLY必须绑定该目标原REPLY事件ID与请求fingerprint、相同source SHA，进入COORDINATION_ENDED。记录不证明实际阅读或人工意见真实，状态不是Case的业务终态。

原五动作历史按exclude_none=True保留原canonical fingerprint；新可选字段只出现在相应动作。32条原有界ledger按等待知悉数保留收尾槽：新REPLY须额外保留ACK槽，其它目标不能消耗已保留槽，ACK或该答复的明确WITHDRAW消耗并释放本槽。容量不足时拒绝新答复，不扩大账本。
