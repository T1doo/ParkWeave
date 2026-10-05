# ParkWeave 动态计划

基线：ParkWeave V1；来源见 [DocumentReview.md](DocumentReview.md)。35阶段任务、36 AT、6 EX为待实现定义，不是通过成绩。

F1 IN_PROGRESS：先严格契约/可信本地动作、数据库隔离、持久Run/Operation/outbox、API与worker骨架及合成测试；真实模型链与Windows门BLOCKED。F2—F6 PLANNED；不在本轮展开全部阶段。

C0规则核查从F1并行：模板正文、跨赛道关联作品政策、2026-11-05最终时刻/时区仍BLOCKED。无报名、公开部署或提交安排。

数据/身份/端口/日志/预算独立于Sim2Act；本轮不引用其代码。书生为自选模型。无安全注入或预算，不调用真实API，不读取隐藏凭据。

目标Windows 11 x64原生浏览器+Python API/worker+PostgreSQL；本云Linux测试不能替代Windows。无真实园区数据，全部工程fixture为明确合成。

首个工程增量ENG-001 READY_FOR_REVIEW：持久本地建单与安全/可靠执行子集可重跑；21工程pytest及Linux HTTP/Chromium流程有证据。F1整体仍未验收，完整AT/EX NOT_RUN，Windows/真实模型BLOCKED。详见[F1日志](F1/Log.md)及[工程测试范围](F1/TestSpecification.md)。

ENG-002 READY_FOR_REVIEW：40工程pytest回归（含原21），FAULT_INJECTION未知结果账本原型及严格计划边界。未知不盲重发；与正常worker的集成未完成。完整AT/EX状态未改变；F1后续独立缺口与外部阻塞见F1/Plan。

ENG-003 READY_FOR_REVIEW：正常API/worker已通过统一网关执行本地动作和显式故障适配器，支持未知结果核对、旧worker拒写及取消/撤权副作用边界的合成工程路径。完整F1仍IN_PROGRESS；完整V1契约、事实/字段Grant等继续待实现，Windows/LIVE/园区效果仍BLOCKED；完整AT/EX NOT_RUN。
