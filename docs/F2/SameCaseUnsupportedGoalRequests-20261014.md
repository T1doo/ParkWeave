# 同Case未支持目标的人工请求、补证与责任记录

基线 `884538f2143012ad0636e19448a7a33e4caa3e90`；功能源码 `099cf1213b684ee0f141c9fc513db33a0ba07f97`；最终冻结源码 `bedbd36ee4dec5020f259c951ad79808e9e2c51c`，后二者产品src字节一致，后者仅修复PG锁监测测试的活动快照缓存。

先核原V1 §5.1/5.2/5.5及原F2：模板新输入经普通case.create与原资料事项，原页面模板locator→持久步骤计划→资料入口→原事实declare/confirm、三字段来源登记与FactBundle。独立实际PG/API及本轮完整HTML页面均验证同Case精确材料摘录、用途声明、三字段选择和CURRENT确认，Run和Grant不变。没有事实接线断点；未增加facts.assess Run或重写事实合同。原材料来源登记后按原入口显式刷新资料版本再确认，保留既有事实未知POST处理合同。

实际业务缺口是未支持目标此前仅显示MANUAL_SERVICE_CONTRACT_REQUIRED。新增独立人工协作ledger存于原service_case_plan JSON：不增加DDL、计划revision、资料revision、原步骤事件或隐式失效写。原企业明确REQUEST后仍等待原专员接受，原专员本人TAKE才记录人工接责；专员REQUEST_EVIDENCE后由企业SUPPLY_EVIDENCE选择此Case当前材料的精确ID/version/SHA及说明，再等待专员核对。企业可WITHDRAW留历史。每目标仍UNSUPPORTED，整体仍PARTIAL；不提供完成/受理/批准/履约动作，不新增服务、工具、角色或责任分派权限。

## 事务与原键

原READ/PREPARE/EXECUTE、case.create权限与原资料owner/reviewer范围是权限来源；专员只能用原REVIEW_ASSIGNED和本人资料范围，不获得企业事实字段或整Run读取权。parent SHARE/UPDATE锁沿原Case守卫；取消/RECONCILING、本地已关闭、旧计划绑定失效、材料bytes与保存hash不一致均禁新动作。既有有权读取与原键历史保留，材料换版或损坏使旧补证引用STALE，未变成真实性核实。

每操作校验原plan ID、独立ledger revision、当前资料/诉求source SHA和明确原因；SUPPLY额外核当前精确引用，事务内追加事件和保存状态，同actor原key同参返回原事件、异参409。原key跨Case拒绝，当前及计划replacement历史均保留原事件。任意保存失败整事务回滚。恢复GET按当前权限、原actor/Case/key只读返回COMMITTED或NOT_OBSERVED；后者不能证明迟到请求不会提交。

页面只持久化actor/Case/key，最多8个有界句柄。丢响应后禁新请求，只GET原key核对，未观察到、损坏、拒绝等保持原句柄未决；COMMITTED精确回执与磁盘原值核对后才删除。恢复展示原计划/原操作者/动作/说明的历史结果，当前责任另显示，不把历史接责冒充当前。身份、事项、资料导航清理私有说明和视图，迟到响应丢弃。

独审发现并实际复现了切Case输入→丢POST响应→原入口lease挡住GET的问题；改为以flow的精确Case/key和持久opaque句柄交接，清私有mgView不再影响原GET恢复。原错误log保留，focused完整HTML NodeVM复验与根真实HTML→ASGI→ownedPG同场景均通过。没有浏览器启动或变通重试。

## 验证窗口

最终冻结根16模块：**365 PASS、0 FAIL/ERROR/SKIP、2 WARN、320.23秒、exit0**。最终bedbd独立PG/API：**18 PASS、0 FAIL/ERROR/SKIP、2 WARN、JUnit11.399秒**；原完整HTML恢复专项另1 PASS。496文件hash零漂移。证据见归档，窗口独立不加总。完整原HTML实际页面涵盖模板locator、同Case事实表单和FactBundle、原专员人工协作、当前材料明确选择、真实提交后切Case丢响应、冷原键GET无重发、跨身份私有草稿清除和迟到GET丢弃。页面47断言/70次真实HTTP/5次人工POST，不等同浏览器布局验收。

前窗分别保留：根首窗17PASS/1夹具ImportError FAIL；expanded22PASS/1页面harness FAIL（等待原异步readback过早）；页面单窗失败与版本刷新harness问题；修正后76PASS冻结前兼容。独审事实链首窗1夹具KeyError FAIL后1PASS；manual开发14PASS；恢复lease原1FAIL与绿窗均留存。不得以这些窗口冒称最终冻结成绩。

首个099冻结根窗锁等待观测FAIL，主动SIGINT停止：128PASS/1FAIL、112.49秒、exit2，其余未执行；没有当成全量通过。单独诊断2项1PASS/1FAIL。原因monitor事务缓存pg_stat_activity活动快照，增加pg_stat_clear_snapshot后真实取消/材料parent阻塞2PASS，再冻结bedbd并重跑。099独审18PASS与focused1PASS、496首尾hash一致是旧独审窗，也不计最终bedbd成绩。

## 交付边界

没有新增Run/Grant、registry或迁移；所有tracked src/tests/scripts共496文件冻结，原两份host approval仍false/null/null。原prepare元数据Forbidden继续独立停止，没有换工具/URL或启动任务；浏览器历史拒绝保持，无真实模型、外部消息、部署或付费调用。本轮仅合成同Case人工协调记录，资料引用仍UNVERIFIED，不宣称新增真实机构服务或完整生命周期。

后续最有价值的是将未解决人工请求在原有有权工作清单中展示明确待推进状态，并继续验收原计划更换后的历史原键恢复；本轮已有独立读取入口和原专员范围，尚未新增通知或真实履约能力。

证据索引：[export-index.json](evidence/same-case-goals-20261014/export-index.json)。原错误private runtime证据与导出SHA均保留，仅生成夹具会话repr行脱敏。

归档中原pytest错误输出的 `E ` 空行末空格原样保留，因此归档全路径的diff空白检查会对这些log/XML告警；没有为让检查变绿而改写失败证据。产品src/tests/scripts路径检查通过。

交付前归档独审PASS：67件导出无缺件、无重复，原件与导出hash/字节数一致；14件仅夹具会话repr脱敏，所有历史失败窗口单列。独审未发现交付阻断。
