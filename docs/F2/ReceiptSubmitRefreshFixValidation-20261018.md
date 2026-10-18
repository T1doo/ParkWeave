# 普通人工回执刷新并发：实际验证与产品剩余项

基线 `b3f64488cbcce8b29a8152509e3b2dac59d6aa84`；源码、测试与合同冻结 **`5bd4aecc18eccc4c939e035cfba66fbc3b5ecea7`**，src 树 `74b5b08951ecbf5ea1f4b36eab91fb57386266a7`、tests 树 `78b16d606045d7610f7c5fa2e0e19c5260cc3555`。分支 `dev/f2-receipt-submit-refresh-fix-20261018`。本片修父级独审指出的可用性卡死，未发现越权。项目继续 IN_PROGRESS。

## 已修行为

冷页带有效未知 SUBMIT 句柄，只读恢复 GET 挂起时允许刷新当前回执。此前 generation 增长而 busy 留在旧代，旧 finally 不清理，核对/释放永久禁用。现在 send/recover 各持独立 operation 对象；刷新使旧操作失效并重建内存状态，保留 localStorage 原句柄。旧 finally 不能结束新操作的 busy；原 current、raw、TTL、ABA、确定拒绝、当前撤权、草稿和全局 UNKNOWN 写门保持。

4 新浏览器节点实际覆盖旧200/403，以及旧回复前是否已启动新核对；两支都先交付旧回复，不能称两种回复完成顺序。先真实人工提交并丢回包，再 reload、普通控件挂起 GET、刷新、再次 GET 和明确释放；当前草稿保留、原句柄精确核验、无新 POST/ACK/P4。旧403为运输注入：仅捕获旧 GET 使用已有另一企业 fixture-b token，从真实后端取得403再迟到交付；不是当前执行者撤权，原当前 READ 撤销测试仍保留。

## 各窗结果分别结算

**没有一个17模块382项单窗全绿的结果。** 当前冻结实际执行382唯一节点：主首窗381PASS，一个节点 setup+teardown 两个ERROR；该节点原预算诊断复验1PASS。54项独测首窗53PASS/1FAIL，唯一一次完整串行确认窗54PASS。54逐ID全部与主窗范围重叠，不相加；定向1项也是原382之一。

| 窗口 | 实际结果与边界 |
| --- | --- |
| red-browser | 2唯一FAIL，未改生产源码，旧200/403返回后 busy=true、核对仍禁用；755输入0漂移 |
| green-browser | 修复后4PASS，755输入0漂移；共同755字节逐项等于最终冻结，新合同随后加入756输入 |
| final | 17完整模块382唯一；381PASS/0FAIL/同一节点2ERROR/0SKIP，外层 708.693738s；756输入0漂移 |
| diagnostic-one | 同一节点1PASS/0FES，外层 16.063253s；启既有连接诊断，原2秒连接/5秒清理/15秒启动预算与断言均未改；756输入0漂移 |
| 独测首窗 | 54唯一53PASS/1FAIL/0ES，普通API启动15秒截止，未进入该节点浏览器业务 |
| 独测串行确认 | 54唯一54PASS/0FES，原完整两模块、无节点自动重跑，756共享/镜像PREPOST0漂移 |

主窗唯一错误节点为 `test_cold_recovery_refresh_releases_only_its_own_busy_operation[new_before_old-403]`：preparation_fixture 的 seed_synthetic 前 owner.connect 在 connect_timeout=2 下抛 ConnectionTimeout；其已创建UUID测试库随后 DROP DATABASE 在 statement_timeout=5000ms 下抛 QueryCanceled。这些是配置预算，不是测得的整段耗时。不是恢复业务断言失败，仍不能据阶段排除底层产品/运行环境因素。主窗原日志、JUnit、包含该超时的PG日志前缀保留。采样时该库已无 backend，不证明事发时阻塞因果。

独测首窗失败为同函数 `[old_then_new-200]`，ordinary_demo 等待健康启动15秒截止；该case未进入Chromium。API日志实际为空，首窗自有PG已按原cleanup_mode删除，不能事后补出完整PG/逐次health记录。主窗错误与独窗失败的底因都仍 **UNKNOWN**；后续PASS不解释、不修复或抹除首次失败，不称负载flaky已修。

只读诊断首次误用当前OS用户名 agent 连接该自有测试server被拒；核已安装 pgserver 固定的既有 postgres owner 后，一次元数据读取成功，未创建role/凭据/Grant。独测确认前另有私有runner目录字面量错误，由一次执行保护在pytest创建之前阻止；错误脚本/调用/trace保留，未启动PG/API，不计第二测试窗。两种harness/诊断失败均不移作业务测试成绩。

红窗178个生产源码文件实际与b3f Git字节相等，完整旧HTML及新测试原件保留；红绿测试文件同最终冻结，绿窗共同755输入同冻结。详见[开发来源核验](evidence/receipt-submit-refresh-fix-20261018/runtime/development-provenance.json)。

| 主窗完整模块 | 唯一范围，非全部PASS列 |
| --- | ---: |
| `test_assigned_demo_chain_browser` | 2 |
| `test_case_cancellation_offline` | 51 |
| `test_dispatch_accept_recovery` | 31 |
| `test_dispatch_accept_recovery_browser` | 5 |
| `test_dispatch_accept_recovery_offline` | 31 |
| `test_dispatch_recovery` | 46 |
| `test_executor_receipts` | 38 |
| `test_f2_t07_full_chain` | 10 |
| `test_frontier_business_client` | 10 |
| `test_frontier_p4_race` | 1 |
| `test_pending_receipt_handoff_offline` | 9 |
| `test_receipt_submit_recovery` | 38 |
| `test_receipt_submit_recovery_browser` | 15 |
| `test_receipt_submit_recovery_frontier` | 1 |
| `test_receipt_submit_recovery_offline` | 39 |
| `test_resource_approval_host_browser` | 2 |
| `test_service_dispatches` | 53 |

[主调用](evidence/receipt-submit-refresh-fix-20261018/runtime/final-invocation.json)、[原主JUnit](evidence/receipt-submit-refresh-fix-20261018/runtime/final.xml)、[定向诊断JUnit](evidence/receipt-submit-refresh-fix-20261018/runtime/diagnostic-one.xml)、[分窗结算](evidence/receipt-submit-refresh-fix-20261018/runtime/accepted-tests.json)、[独测确认结算](evidence/receipt-submit-refresh-fix-20261018/runtime/independent-final-review.json)。独测首窗原review的SHA256为 `d50603964bfc4bbcbe679b68103fe98786014a9245c425ac2479dc05a90a9265`，未覆盖；actual重叠另存结算。

## 已实际推进的原办理全链

在同一冻结执行已有 `test_f2_t07_full_chain` 全部10项，全部PASS，未新增T07测试或产品包装。599次实际HTTP请求、23个独立LOCAL CLI worker、1个冷 configured_app API进程。覆盖新输入/材料版本、实际5类本地产物、纠错补件/反馈、两次不同输入历史分离、冷读、取消保留占用后独立释放、关闭/重开cycle2、当前撤权与跨主体拒绝。已有普通DOM六产物2项也在主窗实跑。

T07数据、初始权限均为显式SYNTHETIC fixture；assigned分支在Run创建后由测试owner记录精确assignment前置，这不是普通业务API自动分派。未分派的新Run分支准确403，无修权；普通工厂不补目录/Grant。不能把fixture前置算零设置正式AT35。Run成功、本地产物齐全和本地记录关闭均不代表线下履约或Case目标完成。见[原链实际摘要](evidence/receipt-submit-refresh-fix-20261018/runtime/original-t07-actual-summary.json)及各原始链记录。

## 原产品验收剩余具体项

| 原范围 | 当前事实及还缺的工作/输入 |
| --- | --- |
| AT07/12/35 人工协作 | 未支持目标的请求→专员接责→补证→答复→企业明确知悉状态机及API/Node已存在；尚缺完整普通Chromium DOM链验收，须从原合法partial计划/材料/角色开始，保持PARTIAL/UNSUPPORTED。可在当前授权合成环境继续，无需新来源合同或新算法。 |
| AT15/35 关闭重开 | T07实际API全链已通过；普通DOM六产物后继续纠错、关闭、重开、重新P5整链尚未验。已有单动作browser不能替代。可继续执行。 |
| 普通正式 preparation 接入 | 正式专用backend、来源主体与原采纳映射仍需按现有来源合同实现，不能只填凭据。最小字段原文保留在[来源合同](ReceiptSubmitRecovery-20261018.md)：既有来源ID/版本/只读结构和获准样本；preparation/Case/Run/已采纳计划ID、关系、版本与current-head；原采纳决定及actor/精确plan hash/状态；来源主体到已有本地主体映射、现有权限/用途/期限/撤销；公开trust/验真协议。不要发送token、私钥、密码或DSN。 |
| 普通运行前置 | 还须已存在且当前合法的记录、会话/READ、PREPARE、REVIEW_ASSIGNED、精确preparation_catalog及相应Run assignment/当前业务前置；缺项由原入口拒绝。未创建真实身份、Grant、分派、目录、批准或凭据。 |
| AT01/34 Windows11 | 本环境未验原生安装、完整停启/关机/干净复现。现原生pytest还要求既有受限测试owner环境及已审迁移025创建回执适配器；LinuxPG/Chromium不替代。 |
| AT02/07/30/31 模型与对照 | 本片0真实模型调用；真实书生工具闭环、冻结任务集/预算/usage及B0/B1/B2仍待获准环境与实际执行，本片不启用。 |
| AT21–27/29/33 F3/期限/迁移 | 原算法不重做，本次未覆盖全F3。正式规则/合法日历与停表权、第二园区现有配置及新合法作用域仍需来源和独立验收，不编SLA、不预设一键迁移。 |
| AT32/36 效果与交付 | 无真实园区试点/用户材料/履约和收益证据；正式申报单PDF、规则/模板逐栏、视频二维码/访问及实际提交回执未验。不能由合成技术验收代替。 |

正式五证明仍UNAVAILABLE，NativeRunAccess permit/writer默认拒绝，已有资源批准读取不可消费，IsolatedPlanApproval不进入普通批准。项目未完成；上述可执行DOM验收与现有业务继续开发不因外部合同缺失而停止。

## 保全与限制

本片公开 408 对raw/public映射、34处临时合成会话候选脱敏；严格JSON/JSONL/XML、PNG CRC/解压、SHA/长度及 497 个JUnit标识一致。见[manifest](evidence/receipt-submit-refresh-fix-20261018/manifest.json)。私有fixture bootstrap/tokens及PGdata不导出；原清理机制删除的PGdata不称完整保留，主日志只保存前缀，诊断窗另有既有observer日志。raw原件在.runtime，公开副本只脱敏会话候选，不改test ID/原结果。

继承 31932 个证据Git blob的实际文件字节已逐一重算，零改变。源码/测试/脚本/合同756输入在各执行窗PREPOST核对；新增报告/计划/证据不改变冻结树。独测实际pytest imports来自等字节镜像src，子API未额外origin插桩。只计本片所列范围，不是全仓或正式AT。localStorage compare/remove不是跨进程数据库级CAS，HTTP请求未物理取消。

正常开发分支提交推送另存实际回执，不在自引用提交中预写最终SHA。未改main、强推、部署、新费用或安全网络权限，未调用真实模型；未知锁与未知进程保持。正式来源/批准/真实业务、Windows11、正式AT/AT35均未验。
