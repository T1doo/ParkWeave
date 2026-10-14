# 人工目标共享隐私HOLD、当前写权与旧计划原键恢复

父级在交付 `424449371590a14eb56f03f4ca567a288f3dfeec` 发现真实隐私HOLD：原专员能通过新人工请求接口读取全部未支持required_goals自由文本，即使企业尚未REQUEST。旧资料接口删request_intent，旧步骤接口将必需目标/manual_goals/history限企业可见；此前365根、18独立及页面通过不能覆盖或掩盖此边界。

隐私源码提交 `77c93ba38c8e0d68cb27dff49dd1591c4df62112`；补齐当前写权与历史验收后的最终源码 `6ab9e6d9dff7f469356b2e1b587e37d4310f8499`。

共同view先验证完整ledger，再从原owner的合法REQUEST事件建立当前计划shared集合。企业仍看全目标；原专员只看当前计划已合法REQUEST的项，空列表保持空，请求一个不暴露另一个。GET、POST结果/同参结果与原键恢复共用此投影；撤回保留已合法共享的历史。未将旧计划共享集合并入新计划当前items，历史原键可返回此前合法共享的原事件。

原owner的allowed_actions另重核原Run的当前EXECUTE和case.create写权。撤写权时历史GET仍可读，但不再显示REQUEST、WITHDRAW等动作；POST保持原403。原专员沿既有READ/REVIEW_ASSIGNED合同，没有新增EXECUTE或任何Grant要求，也没有扩权。

## 真实更换计划与未知结果

通过原request-intent API明确修改诉求并保留全部目标，再从当前planning-preview由原service-case-plan API显式采用新计划。新计划ID/独立ledger与旧计划分开：旧key GET返回COMMITTED、原plan ID与完全相同旧事件；同参POST返回该原事件，异参409，不修改业务记录。新计划原专员起初空items；企业新REQUEST另一目标后只显示新共享项，旧回执仍独立可恢复且新ledger不改旧历史。

原core更换计划会将空history=[]容器移除并归档扁平旧plan；测试只规范化这个已有记账形状，全部其余字段、旧manual events与fingerprint精确保留。更换后先抓当前已保存history，再验证GET/同参/异参及新ledger操作不改该历史。没有改写旧core合同。

权限撤销后原键历史GET及缓存POST仍按各自当前权限拒绝。原完整HTML页面冷句柄在真实API更换计划后，只GET核对原键；精确旧事件与原计划证明核实后才清句柄。撤读权403会清私有视图并保留原句柄，不把无法读取或NOT_OBSERVED当收尾依据。另一页面窗口实际专员POST成功后丢回应并切Case、冷原key GET无重发，及企业迟到完整目标响应切专员后丢弃。

目标仍UNSUPPORTED，所有必需目标保留，整体PARTIAL。未新增Run、Grant、服务能力、registry、迁移、外部通知、资格或批准结论。待办投影按最新续接范围暂缓，优先关闭此HOLD及补充边界。

## 各窗口保全

基线双私有目标红窗4FAIL，其中2项是真实目标泄露，另2项为测试误把正常DENIED authorization_audit当业务写；完整原日志/XML/exit保留。产品过滤后中间2PASS/2同类审计oracle FAIL；修正测试明确3条拒绝审计且11业务表不变后，5专项PASS。隐私77冻结根9模块200PASS与旧独立6PASS单列，不计最终源码窗口。

补充写权红窗5FAIL，其中4项真实allowed_actions错误，1项测试误取preview缺少的request_revision字段；通过原UPDATE_REQUEST响应取版本修正。其后历史测试的两类oracle失败分别是把旧合法共享A回执误当新泄露、及空history归档容器形状；均原样留证，未修改产品历史或扩大专员分享。根补充完整11PASS后再最终冻结。

旧独审初窗4PASS/2FAIL是正常DENIED审计oracle，修正后6PASS；补充独审初窗10PASS/2FAIL是同一空history容器oracle，原probe/log/XML/exit另存。最终根和独审统计见归档，窗口不加总。完整HTML NodeVM使用原页面脚本、真实ASGI和owned PostgreSQL，布局浏览器未运行。

499份tracked src/tests/scripts冻结（含原两份approval），未改main/F1/原F2；源码到交付仅文档证据。prepare元数据Forbidden及浏览器历史ERR_BLOCKED_BY_ADMINISTRATOR继续保持停止，不换工具、URL、凭据、安全权限或模型重试。

[机器证据索引](evidence/manual-goal-privacy-20261014/export-index.json)。原件留指定环境.runtime，导出仅生成夹具会话repr脱敏，失败空白行与XML统计保留。

最终6ab9冻结根9模块 **206 PASS、0 FAIL/ERROR/SKIP、2 WARN、184.52秒、exit0**。同源码独立12项实际PG/API **12 PASS、0 FAIL/ERROR/SKIP、2 WARN、13.20秒、exit0**；499文件前后hash零差异。原HTML隐私页 **29断言PASS/17HTTP/3POST**；原HTML历史恢复页 **17断言PASS/5HTTP/0POST**，分别记录。56导出hash验证一致，不将旧200/6或此前365/18窗口加总。

交付前归档独审PASS，56件原件与导出hash/字节数一致。产品src/tests/scripts与报告空白检查通过；原pytest错误log/XML空白行末空格保留，不以修改失败原件让归档空白检查变绿。独审归档转换预期的初次oracle错误另留runtime，未修改导出或其hash。
