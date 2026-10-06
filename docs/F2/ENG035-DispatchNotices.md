# ENG035 当前分派链内部站内通知

实施基线a1508df9dacbf597ca08bba28e19d0c968dfb45b。原定义：V1产品§5.5通知创建、平台内送达、已读、履约分别记录；§7.2业务与outbox同事务、event ID去重、对象版本处理乱序；F2-T04/T05。本轮仅实现已授权当前分派事件的小闭环，不backfill旧历史，不扩通用CaseStep/模板/DAG/真实履约。

## 实施前固定边界与计划

1. OFFER/REOFFER/WITHDRAW通知该offer已有执行者及企业owner；ACCEPT/DECLINE通知既有reviewer及owner；排除操作本人。候选收件人不是授权新增：业务入口不创建身份、Grant或Runassignment，撤权后未投递的意图可保存但消费抑制。
2. 同一事务创建不可变dispatch event和唯一(event_id,recipient_id) outbox；只保存原事件/收件引用。平台投递记录独立delivered_at，本人OPEN请求时间seen_at（API字段open_requested_at，不证明实际页面打开或展示成功），本人明确已读read_at；不保存goal、分派原因、材料或回执正文。原事件不更新，动作理由仍只在当前获权事项详情读取。
3. 消费者每次检查当前principal READ、角色、tenant、资料负责范围或Runassignment，以及具体offer身份。未授权意图SUPPRESSED，不自动复活；已投递后每次列表/详情/OPEN/MARK_READ仍检查当前权，历史通知不缓存权限。锁序principal→preparation→dispatch→outbox→delivery，每候选savepoint与50ms有限锁等待，最多20候选；进程内扫描游标跨批次轮转，重启可重新扫描，数据库仍是唯一持久队列。consume=False只表示本批未消费，常驻worker下轮继续；并发SKIP LOCKED、投递与消费确认同事务，进程崩溃回滚后重启重试，不产生重复收件。
4. 乱序旧通知仅作为历史事件，不更新分派、接单或Case状态；界面按当前dispatch revision动态标记历史，点击总是重读当前事项。已读要求本人先OPEN，单调且幂等；查看、已读、通知送达都不证明服务完成。
5. 页面仅平台内收件列表、固定动作标签/版本/时间，打开当前事项、返回收件列表、本人已读。独立token/generation/通知ID上下文，身份/导航/别的事项切换使迟到回复失效；当前403清除通知和关联私有详情并给可见反馈。同一请求重试不重复，发送中的旧回复不回填别的事项。
6. 覆盖同事务故障、重复/并发消费、真实子进程消费崩溃与重启、版本乱序、撤权前后、tenant/角色/具体offer隔离、OPEN/已读幂等；三角色实际PG/API/worker/Chromium及独立受控时序；最后冻结源完整aggregate。独立审查事务与当前权限，修实际问题后本地commit。

全程SYNTHETIC内部账户、0LIVE/模型/预算；不发email/短信/Slack或真实外部通知，不export、暂不push/newCI。通知机制只覆盖当前分派事件，不把它当全F2事件/Outbox或完整通知系统。F1/F2未签收、R4关闭、Win11/36AT6EX NOT_RUN；Windows37420887816等待已有安全JSON，不重复索图或盲跑。原环境与备份保留。

## 独立审查与实际修正

后端独立审查发现，最前待发通知的Case持续占锁会挡住无关Case。已改为每候选savepoint/50ms超时，忙项保持PENDING；非持久扫描游标让下轮越过20项前缀并回绕。游标仅优化公平扫描，数据库唯一键和事务仍决定投递/确认。一次consume=False不是队列为空；常驻worker继续轮次，--once也不是“所有忙项已送达”的保证。实际PG测试把扫描上限压到1，让无关Case在前缀外，核对连续忙项未抑制、后续Case可消费及释放锁后全部投递。

页面独立审查发现，OPEN后的当前分派403在同时MARK_READ推进通知generation时可能被误当旧回复忽略。已按当前dispatchContext、token和通知ID处理该403，清除当前私有内容并显示反馈；新增受控真实页面时序验证此情形。token/选择/返回/导航的旧回复仍丢弃。

规格/Windows只读审查发现seen_at不应称“页面打开成功”，已统一本人OPEN请求时间。正式角色授权文件的升级验证不再复制三条GRANT，而是执行完整roles.sql，仅将CONNECT目标替换为现存UUID测试库名以保留隔离；最小表/列权限及无旧backfill实际验证。第一次完整回归暴露该数据库名称适配遗漏，独立负例1FAIL后修正针对项1PASS，最终另做冻结全量。所有Windows workflow/harness/PS及环境/核心授权保护文件保持原字节，无本轮Windows实机成绩。

实际浏览器早期出现源详情展开后自动化点击未发请求的等待失败；重新定位显式“我已读此通知”并等待两次绘制后验证。最终实际请求/持久已读成立；失败尝试和截图均保留，未把失败记作通过。

## 原规格仍剩余

本轮仅覆盖当前分派事件到已授权内部账户的站内通知。资料、资源、回执、通用CaseStep等全业务事件/Outbox、通知模板与其他渠道、完整DAG执行和版本模板复用未实现；不将原T01有限字段冲突和T02有限结构校验当完全没有，也不引入无限资源组合或默认多Case共享的原文外要求。真实Case的承诺交付、Verifier及授权目标状态变更工程，与实际凭据/结果均未完成。本地通知/打开/已读/接单/回执核对/记录关闭都不能当FULFILLED。历史分派没有补发，恢复授权不自动复活SUPPRESSED通知。列表本次检查最近100条本人收件记录，无分页/全历史覆盖承诺；未授权项不泄露额外计数。


## 最终本地工程结果

最终冻结全量808PASS/0FAIL/1WindowsSKIP/2既有WARN（232.54s）、exit0；148/148外部冻结源hash及137/137 runner源码hash全部匹配，380个固定诊断函数ID与源码准确匹配。原V1两份文档及24份Windows/PS/env/核心授权保护文件字节不变。第一次全量807PASS/1FAIL/1WindowsSKIP为隔离数据库CONNECT适配失败，保留独立失败报告；修正后本段为唯一最终成绩，不叠加各轮测试数。

最终实际Linux Chromium/local API/worker/PG三角色链：OFFER→DECLINE→REOFFER→WITHDRAW→REOFFER→ACCEPT（dispatch revision6），对应授权收件人通知可收取、本人OPEN及明确已读、历史通知读取当前分派、返回列表/reload已读持久、跨tenant不暴露、当前Runassignment撤销后403及清空私有视图；320/390无横向溢出。独立真实页面受控响应顺序16/16PASS，包含MARK_READ后当前源403清除、token/ABA/导航/返回的迟到回复隔离。8张独立最终截图均hash匹配，旧图与失败尝试保留。详细最小数据/源码/截图hash与失败纠正见[evidence/eng035-dispatch-notices.json](evidence/eng035-dispatch-notices.json)。

已停止本轮精确PID的本地API/worker，保留合成PG数据/日志/截图、原环境与备份。仅本地commit，不push/newCI/export/LIVE或外部消息；Windows37420887816仍FAIL、具体case/counts/rootcause等待已有安全JSON。F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、模型/真实预算0。
