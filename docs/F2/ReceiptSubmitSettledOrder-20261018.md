# SUBMIT 冷恢复的完整完成顺序

基线 `c66eb07f381eb3b5d1fe5791f3291ad784d861e2`，普通分支 `dev/f2-receipt-submit-settled-order-20261018`。接续父级独审指出的精确缺口：旧四节点均旧回复先交付，`new_before_old` 仅新恢复先开始，80ms 不证明旧处理结束。保留原四节点 ID／旧先回语义，补200／403两节点：新恢复完整处理完成后，才交付旧回复并等旧处理完整结束。本合同不预认通过，实际冻结与成绩另报。

测试观察原 recovery／refresh／release 按钮 onclick 返回的 Promise，原 handler 通过真实 DOM 点击、原 this／event 调用一次，返回原 Promise。附加 then 只记录序号／完成，不设置任何业务变量、权限或控件状态。屏障要求实际 Promise、fulfilled／settled 事件，覆盖原 catch／finally；不改产品函数，不用固定延时推定完成。route捕获的短轮询只等待已获取的真实服务器响应，不能替代完成屏障。

原未知人工提交先由服务器实际保存，再丢失回应并 reload 冷页。启动前 preparation、材料、review／confirm、精确 Run assignment 和 receipt step 都是明确的 SYNTHETIC fixture；不是零设置完整普通业务、真实身份／授权或正式批准。旧403只将捕获 GET 的 Authorization 换成既有另一 fixture 主体，由实际后端拒绝；它是运输注入，不是当前执行者真实撤权。原真实当前READ撤销测试保持，测试 request trace 不覆盖 route.fetch，另列实际转发方法／状态且不保存 header／token。

新先完成节点要验证当前完整 proof 等于新服务器回复、busy与operation已结束、可显式释放；旧 handler 尚未 settled 时才交付其200／403。旧完成后逐字段比较当前 proof、busy／operation、视图／上下文代与对象、按钮、完整存储句柄、正文和来源草稿及错误展示不变。之后原 release handler 完成才检查原句柄删除、proof为空、草稿保留。冷恢复段仅GET，一次原浏览器POST及一次实际转发POST，完整Case历史／权限快照不变；SUBMIT仅一事件，无ACK。此fixture没有service_case_plan，不能声称验证了已采用计划的P4正向流程；空计划及完整preparation行保持，且无新POST／P4写入。

只在实际失败暴露产品缺陷时最小改 src；不为补数量改算法或预算，不扩大范围。原2秒连接、DROP5000ms、ordinary循环15秒及health HTTP15秒保持；所有失败／诊断保全，不自动重跑。原历史UNKNOWN、localStorage非跨进程数据库CAS、HTTP未物理取消及不同port冷读边界保持。

完成后按原产品方案整理实质交付门：已完成的普通DOM用户流程不重复开工；正式来源合同与专用backend／主体／采纳代码、真实Windows／正式AT、书生工具／实际效果与原C0正式交付材料各自列真实缺口。不给新增外围证明制造范围。NativeRunAccess permit／writer默认拒绝，正式五证明UNAVAILABLE，资源批准读取不可消费，IsolatedPlanApproval只隔离测试。无main／强推／部署／真实模型／真实身份、Grant、分派、目录发布或批准／新增凭据、费用、安全网络权限。
