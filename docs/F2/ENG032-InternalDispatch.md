# ENG032 最小内部分派、本人接单与既有回执

基线c5b389bf0ae45fd9601182114739a597da13dfa2。按原V1产品§3/5.5/7、F2-T04与此前只读合同安全保存点，恢复本地最小切片。只本地修改、PG/API/真实浏览器、独立只读审查与commit；不push/newCI/export/LIVE。ENG031实际Windows Server运行仍FAIL，具体子项等待其新安全JSON，本轮本地通过不称修复Windows。

## 实际业务边界

当前获派资料专员使用已有READ+REVIEW_ASSIGNED，仅对本人负责、同park/org且已LOCAL_CONFIRMED的合成资料Case分派；选择已有active service_executor READ+该Run active assignment。企业只能看本人状态，执行者只能看本人offer的必要目标/服务版本/分派原因与本人决定，不返回材料正文、企业事实、候选目录或其他执行者身份/原因。resource_admin没有既有资料review权限，因此拒绝，不新增Grant或扩大tenant权限。测试owner为新合成Run显式准备既有访问授权，属于测试前置，业务UI从不写授权。

业务分派与run_assignment授权分开：OFFERED → 本人ACCEPTED / DECLINED / 专员WITHDRAWN。拒绝或撤回后说明原因建立新offer，保留旧目标和决定历史；重派后的旧执行者只读本人旧offer，不能接受新offer。陈旧资料offer可拒绝或撤回；撤回不依赖旧执行者继续有权限、不要求父资料仍确认，不释放资源、不撤销已接单事项。

接受使用本人的真实actor，在同一事务中重验目标/专员/企业当前权限及父资料revision/hash/state，创建唯一既有AWAITING_RECEIPT步骤及CREATE事件、更新ACCEPTED和分派事件。随后执行者追加SYNTHETIC来源/version/hash回执，企业纠错、核对、重开；没有把接单或技术Run成功当作Case目标完成、资格满足、外部受理或线下履约。

本片接受后保留既有receipt责任关系，暂不支持转派。原§5.5有原因调整责任方目标仍保留：接受后的调整、历史回执跟随或新handoff语义待产品决定，不把本片限制写成永久规则。未新增真实通知、履约、通用ServicePlan/CaseStep/Approval/DAG或站内消息。

## 事务、历史与兼容

新schema15仅三个业务表，应用可SELECT/INSERT及根revision/current_offer和offer state/receipt_step必要列UPDATE；责任方/父绑定/原因/事件不可修改，无DELETE，无identity/grant/Run assignment写权。v14→15升级与重复迁移保留旧准备和回执。授权共享锁、actor/key互斥、有限3秒锁等待后统一Preparation → dispatch → receipt锁序；两个决定只能提交一个，事件故障整事务回滚。

最多64修订；offer最多到63，保留最后一次决定到64，之后历史可读、不再新分派。当前权限在列表/详情/幂等重放前检查；同键同指纹返回原操作回执与当前状态，不把已接受/撤回复活。旧legacy CREATE重放保留；有旧receipt不能新offer，有新dispatch后任何状态下旧CREATE都不能旁路建立步骤。

界面有本人分派列表、专员候选与原因、本人接受/拒绝、未接单撤回、版本历史、进入既有回执。身份/事项/工作区/generation/token/offer/revision上下文独立，迟到读取/写入不回填别的事项；同输入重试固定key，写期间新草稿保留，草稿变更后的旧409/422反馈忽略，当前403清私有面板并在常驻反馈显示。

## 验证与真实失败记录

最终PG/API定向132PASS/0FAIL（59.887s）：当前角色/tenant/READ/ReviewGrant/Runassignment、父revision/hash/state、target撤权与parent重开后撤回、本人旧offer投影、legacy旁路/重放/并发、不同决定竞争、同键并发、事件故障回滚、v14升级、最小列权限、3秒撤权锁等待、资源管理员拒绝、有界历史。初轮42PASS/41ERROR为新测试夹具导入缺失；第二轮54PASS/29FAIL暴露新事件SQL占位符多一个；修正后83PASS，再补边界132PASS。保留失败，不归因Windows。

独立后端只读审查未发现实质缺陷；独立UI审查发现两P2（旧失败污染新草稿、403反馈被隐藏），修复后二次只读核对关闭。审查者未运行测试/浏览器/PG/网络。真实页面controlled-response oracle23/23PASS，覆盖身份/事项/导航/ABA、迟到列表/目录/写、草稿、幂等key、绑定guard、当前403可见；此oracle不调用业务API，不冒充后端授权测试。首次CDP超时源于测试夹具响应了ABA旧请求，改选择最新请求后通过。

最终独立实际Chromium/local API/worker/PG三角色：新诉求与两槽资料→专员核对→企业确认→已有合法执行者访问前置→专员分派→执行者拒绝→原因重派→专员撤回→原因重派→本人接受→回执v1/企业纠错→v2/企业核对→重开→v3→reload。分派6修订/6事件，回执3版本/7事件；注入只文本、跨企业隔离、身份清理、执行者越权核对拒绝。分派及回执320/390均scrollWidth=innerWidth，12张最终截图hash可复核，已目视确认accepted与320详情；最初截图未滚到目标面板，最终另存目录，不覆盖旧图。Linux/模拟viewport不是原生Win11或手机实机。

全量冻结136份源码/脚本/固定ID数据/pyproject/workflow，最终734PASS/0FAIL/1WindowsSKIP/2既有WARN（205.879s）、exit0；运行后136/136哈希保持，run_acceptance自带127份源码哈希也全部匹配。既有诊断test-ID清单仅同步新增20个已提交测试函数（329→349），与AST严格一致；无publisher/workflow/超时/PS guard修改，无CI触发。全部证据见[evidence](evidence/eng032-dispatch-acceptance.json)。

## 原计划剩余

F2-T04仍缺接受后责任调整、通用CaseStep、站内通知创建/送达/已读、完整Case生命周期关闭/重开与真实核验。T02完整目标覆盖/有限DAG、T05业务Outbox与全流程失联/未知结果、T01来源真实性/事实冲突与复用、T06审核模板/新企业冷会话、T07完整端到端验收仍未完成。现有两资源组合与Case关联保留，无自动取消或真实履约。

F1未签收，F2正式准入NOT_PASSED，Win11/36AT6EX NOT_RUN，R4 DISABLED，真实模型/预算0；原环境与备份保留。本地提交不等于GitHub已更新。
