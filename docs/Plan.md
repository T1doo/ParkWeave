# ParkWeave 动态计划

基线：ParkWeave V1；来源见 [DocumentReview.md](DocumentReview.md)。35阶段任务、36 AT、6 EX为待实现定义，不是通过成绩。

F1 IN_PROGRESS：先严格契约/可信本地动作、数据库隔离、持久Run/Operation/outbox、API与worker骨架及合成测试；真实模型链与Windows门BLOCKED。F2—F6 PLANNED；不在本轮展开全部阶段。

C0规则核查从F1并行：模板正文、跨赛道关联作品政策、2026-11-05最终时刻/时区仍BLOCKED。无报名、公开部署或提交安排。

数据/身份/端口/日志/预算独立于Sim2Act；本轮不引用其代码。书生为自选模型。无安全注入或预算，不调用真实API，不读取隐藏凭据。

目标Windows 11 x64原生浏览器+Python API/worker+PostgreSQL；本云Linux测试不能替代Windows。无真实园区数据，全部工程fixture为明确合成。

首个工程增量ENG-001 READY_FOR_REVIEW：持久本地建单与安全/可靠执行子集可重跑；21工程pytest及Linux HTTP/Chromium流程有证据。F1整体仍未验收，完整AT/EX NOT_RUN，Windows/真实模型BLOCKED。详见[F1日志](F1/Log.md)及[工程测试范围](F1/TestSpecification.md)。

ENG-002 READY_FOR_REVIEW：40工程pytest回归（含原21），FAULT_INJECTION未知结果账本原型及严格计划边界。未知不盲重发；与正常worker的集成未完成。完整AT/EX状态未改变；F1后续独立缺口与外部阻塞见F1/Plan。

ENG-003 READY_FOR_REVIEW：正常API/worker已通过统一网关执行本地动作和显式故障适配器，支持未知结果核对、旧worker拒写及取消/撤权副作用边界的合成工程路径。完整F1仍IN_PROGRESS；完整V1契约、事实/字段Grant等继续待实现，Windows/LIVE/园区效果仍BLOCKED；完整AT/EX NOT_RUN。

ENG-004 READY_FOR_REVIEW：78工程回归、V1最小结构实际API校验、事实冲突与字段Grant实际API/worker、独立心跳和等待控制。Windows11仅用户自报确认，原生门仍BLOCKED；真实模型注入与预算仍待确认。事实核对成功不代表资格满足或服务履约，未进入F2。下一独立F1缺口见F1/Plan。

ENG-005 READY_FOR_REVIEW：四角色最小权限交集、当前outbox授权与本地交付撤回、逻辑文件ID及Linux路径边界工程子集；107 PASS/1 SKIP，浏览器桌面及320/390模拟PASS。完整AT/EX仍NOT_RUN，F1剩余工程与外部门槛见F1/Plan。跨平台网页目标保留Windows主门，不承诺手机本地后端或公网部署。

ENG-006 READY_FOR_REVIEW：F1收尾候选生命周期/固定AT汇总/离线模型边界与审查安全修复，146工程PASS/1 WindowsSKIP；完整阶段未签收。逐条清单见F1/Checklist、首次使用说明见首次体验。本轮交付停止新增；T01原生文件backend及T05真实传输/持久usage/共享配额/运行链绑定独立未做，外部Windows/LIVE/真实园区/C0门另列，不进入F2。


ENG-007 T05基础增量：固定HTTPS传输代码、共享账号持久预留/usage与产品上限、正常worker显式离线规划/可信动作/已提交Case回执反馈/恢复。仅合成MockTransport验证，LIVE安全注入与真实预算/共享部署/真实计费仍BLOCKED、实际调用0。Windows文件backend仍独立未做；本轮不扩F2，交付后停待复核。


ENG-008 READY_FOR_REVIEW：Windows原生只读文件候选代码/69 Linux policy与ABI单测/原生专属probe；生产Windows入口仍关闭，native NOT_RUN。最终243 PASS/1 SKIP；F1剩余不是仅外部验证，候选启用/owner注册、LIVE安全注入/计划修订与完整oracle仍需独立工程，详见F1/Checklist及WindowsFileCandidate。真实调用/预算0，本轮结束不扩F2。


ENG-009：按F1原任务/12AT断言收敛为Convergence有限清单，单项R1计划修订artifact与独立oracle已实现；原阶段不改、真实模型/预算0、Windows候选不动。残余固定R2账号速率/LIVE接入、R3有限候选/集中澄清、R4实机后通路集成，外门E1—E3；具体失败和退出断言均已列明，不泛称还有“完整”欠项，不扩F2。

ENG013：对ENG012候选CI作有限PG失败/state篡改/browser超时oracle与owner/admin环境审计；原应用子进程白名单边界保留，辅助命令按phase收窄。仅本地提交，Actions访问不重试、workflow不push、runner0；Linux/static/synthetic证据不能替代Server/Win11实测，生产R4关闭/真实模型预算0。供父任务复核后另派。
