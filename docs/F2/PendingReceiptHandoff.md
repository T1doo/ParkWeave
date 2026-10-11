# 尚未回执事项的明确责任方交接

基线 `4a0ec78ec7d554204e6fea66a75afd26242c3cd5`，独立开发分支 `dev/f2-pending-receipt-handoff-20261011`，根唯一源码/Git写入者，独审只读。原通知分页保持此前68作者/25独审范围，不重新作为本片成果。

原需求是产品§5.5（原件 `docs/sources/V1/平台产品设计 (2).md`）“园区专员可调整责任方，但必须说明原因”，及F2-T04的角色协同、F2-T05的幂等/未知结果、F2-T07的可实际办理路径。原ENG032明确暂不支持已接单执行者变更。基线的WITHDRAW仅接受OFFERED；已有receipt只能材料换代后REOFFER，并强制原executor。真实owned PG/ASGI复现确认旧目录无可用交接及普通重分派409，需求断点日志私有保全，不复用旧通知测试成绩。

## 当前模块与原F2剩余核查

| 原任务 | 当前源码实际路径 | 仍未闭合的原整项依赖 |
| --- | --- | --- |
| T01 诉求/事实/材料 | preparation、request_intents、case_fact_clarifications、case_fact_bundle、material_corrections、material_reuse、material_preparation_drafts及fact_history_read_source | 通用三来源/多用途分享和现实材料真实性；历史持久登记不启用 |
| T02 规划/目标 | bounded_planning、registered_dependencies、service_case_steps、controlled_plans、case_goal_results | 正式ServiceRelease目录、真实模型规划、一般有界DAG与完整预览 |
| T03 资源 | resource_holds、resource_combinations、resource_bundles、case_resources、resource_plan_binding、case_resource_delivery | 真实权威资源、正式业务Approval及非合成发布来源；现有隔离Approval/目录协作不外推生产 |
| T04 协同/办理 | service_dispatches、executor_receipts、material_corrections、material_objections、dispatch_notices、case_lifecycle | 本片前已接单人员不能交接；真实业务/独立履约凭据仍无，Case本地关闭不等于FULFILLED |
| T05 可靠性 | store事务、事件/原outbox、当前权限/assignment、worker租约、各模块CAS/原key恢复 | 全业务统一外部对账/真实外部结果不明；不调用模型或外部系统 |
| T06 模板/新输入 | template_candidate/consumer/upgrade、catalog_publication、service_plan_approval的限定隔离路径 | 正式主体、来源维护与精准发布/实例适用；未消费Approval重启写及生产授权仍关闭 |
| T07 工作区/端到端 | 原web服务/协同/资源入口、case_path及上述实际业务API | 完整原F2/AT、新输入到真实履约、Windows/真实浏览器；明确浏览器拒绝持续暂停 |

并已核对readiness、handling_deadline、case_opportunities的现有补充路径，以及各isolated_*、*_preview_sql、history_summary/registration的独立边界。它们已有各自受限实现；不新增统一空列表、模型Mock、通知微项或信任登记冒充业务闭环。本片优先解开已有人工办理中“责任人不能继续但事项仍待回执”的实际阻塞。

## 行为与边界

只限普通SYNTHETIC人工步骤：当前资料仍合法本地确认，最新真实ACCEPT所指步骤AWAITING_RECEIPT、无current_receipt且没有任何已提交回执。已提交、补正、核对或重开过的回执不交接；隔离执行/访问/preview路径不开放本动作。

专员显式提交原因、新方、当前preparation/dispatch/旧step版本及前代offer/step ID；新方须已具有同Run当前合法assignment和READ。本事务在原parent→dispatch→旧step锁序下重核，追加REOFFER与原通知outbox并切换current_offer；旧步骤不改、立刻成为历史只读。新方须独立ACCEPT才创建新receipt UUID，不复制旧结果或权限。新方拒绝或专员撤回后不会恢复旧步骤写权；只有再一次明确交接才能继续。

Schema29仅去掉同材料版本最多一个receipt的旧约束，新增offer.receipt_step_id唯一约束；每次ACCEPT仍经CAS/当前offer/精确前代证明，直接CREATE及无交接lineage的同材料ACCEPT继续拒绝。既有新材料换代仍遵守原executor规则。迁移仅沿原fresh-owned Linux fixture创建凭证执行；角色、权限文件、安装/native授权和持久信任机制不改，不实施生产迁移或部署。

页面复用原专员分派表单呈现明确交接模式，显示另一位当前合法执行者及原因。发送前仅保存最多8条/24h的actor、dispatch/preparation UUID、原key及期限；不保存正文、理由或token。存储失败不POST，未知结果禁新动作，仅GET原key核对；刷新和身份切换不自动重发。当前授权在恢复时重新核对，历史回执只证明原事件提交，不能复活旧current_offer。原显式SUBMIT/企业ACK、OPEN/MARK_READ均不自动调用。

## 验收与证据

作者与独审应分别保全原始日志、JUnit及源码hash。验收核心为A接单未回执→专员明确交接给有权B→A旧step拒新写→B显式接单新UUID→B人工回执→企业ACK，旧记录和权限集合不变；补新方拒绝/撤回后再交接、多次回原方独立代际、并发、撤权/跨租户、陈旧资料/旧schema/任何历史回执拒绝、幂等/GET恢复、事件失败回滚及唯一约束/迁移重放。离线NodeVM仅执行原交接JS并使用DOM/fetch/storage doubles，验证迟到响应、身份切换、存储失败、原key核对和不自动POST。

原浏览器 `data: ERR_BLOCKED_BY_ADMINISTRATOR` 保持；不启动浏览器、不换URL/工具、无模型/部署/main或既有dev整合。完整AT/F2、真实履约、多worker、Windows/浏览器与持久信任登记不由此签收。初轮基线复现的collection error与修正后的真实需求FAIL均保留，不能把它们算成新实现PASS。

本片28项源码/测试/说明修改由本线程根作者产生，现有文件mtime为2026-10-11 09:52:50–10:05:04 UTC，需求复现始于09:49。独审只读，已完成静态审查，未发现阻断；尚须对冻结SHA运行独立探针。冻结前作者JUnit依次为131例（129 PASS/2 FAIL，outbox测试误把同一事件的两个收件人当成一行）、256例（255 PASS/1 FAIL，新唯一约束先阻止了旧corrupt-pointer测试的造坏数据）、331例（330 PASS/1 FAIL，未来版本测试误用当前29而非30），离线NodeVM另9 PASS。已分别修正测试oracle/一次性fixture造坏方式/未来marker，原失败记录私有保全；这些预冻结成绩不作为最终源码签收。最终冻结SHA、精确测试计数和独审记录随证据单独归档。
