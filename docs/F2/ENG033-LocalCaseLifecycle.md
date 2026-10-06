# ENG033 当前合成资料Case的本地记录关闭与重开

基线05a8fec29f945b64765af3ddf3123ceda57d61a4。按原V1产品§5.5/§7与F2-T04推进最小本地切片。当前授权仅本地工程、PG/API、真实浏览器、独立只读审查、全量回归及commit；不push/newCI/export/LIVE。原环境、恢复包与旧证据保留。

## 关闭条件与真实状态

原计划FULFILLED需要承诺交付证据与有权确认，当前只有SYNTHETIC资料和回执。因此本轮关闭的是本地记录，真实Case保持WAITING_CONFIRMATION；重开本地记录时Case为REOPENED。数据库拒绝FULFILLED，qualification=NOT_EVALUATED、external_acceptance=NOT_SUBMITTED、offline_fulfillment=NO_EVIDENCE、case_goal_completed=false不变。不能称AT15整体通过或完整F2签收。

企业owner当前READ/PREPARE/EXECUTE与tenant/Case归属交集下，先显式REVALIDATE，再CLOSE_LOCAL_RECORD。四项全部当前有效：两槽资料与人工确认hash及专员权限；当前分派本人ACCEPTED及执行者Run访问授权；同一绑定步骤的当前合成回执LOCAL_ACKNOWLEDGED及来源hash；最新Case资源关联/唯一归属、两成员CONFIRMED、当前规则/容量/开放窗口/尚未结束时段与资源授权。没有接单的旧legacy回执不能自动补造接受事实。

每轮保存不可变事件、原因、来源快照及带cycle的SHA。重开仅需owner当前授权、关闭状态、revision/cycle和明确原因；旧资料、撤权执行者或已取消资源不会阻止安全重开。新cycle清除旧验证，必须显式重新校验后才可关闭。重开不修改材料/接单/回执历史，不自动释放或改派资源。旧key重放只返回原操作回执与当前状态，不复活旧轮次。

已关闭记录之后依赖改变不会自动抹掉历史；刷新显示校验失效，owner可显式重开。已接受事项责任调整仍待产品决定，此切片不处理handoff，未将限制改成永久业务规则。应用入口不创建Grant/Runassignment，不新增真实通知、外部履约或自动资格判断。

## 权限、事务及页面

schema16增加本地ledger与不可变事件，应用仅必要SELECT/INSERT和ledger revision/cycle/state/snapshot/hash列UPDATE，无事件更新或DELETE。v15升级及重复迁移保留既有业务数据；打包包含UTF-8 migration16，角色capability、Windows workflow/harness/PS/env边界未改。固定安全诊断IDs仅同步16个新可信测试函数，349→365。

锁序统一Preparation→dispatch→receipt→排序资源mutex→combination/holds→Case/ledger，数据库时钟在最后锁后取值。三个动作与Case状态/来源快照/事件同事务提交；当前授权检查先于幂等重放，actor/key互斥、revision/cycle CAS、3秒锁等待、64修订上限。重开预留下一轮校验和关闭所需历史空间。

专员限本人资料review，执行者限本人offer与当前Run访问，只读固定状态及简要历史；不返回owner说明、材料正文、资源组合IDs或核验snapshot/hash/checks。页面明确区分本地记录与真实Case状态，准备/分派/回执均有入口。token/事项/generation/cycle/revision/source SHA独立绑定；旧回复不回填，草稿变更后的旧非403错误忽略，当前403清私有面板并显示常驻反馈。动态内容纯文本。

## 验证、真实失败与范围

全量结果在[evidence/eng033-local-case-acceptance.json](evidence/eng033-local-case-acceptance.json)。142份源码、脚本、固定数据、打包与workflow在最终全量前冻结。最终775PASS/0FAIL/1WindowsSKIP/2既有WARN，228.266秒、exit0；41项Case生命周期测试全部通过。142/142冻结hash及run_acceptance自带132/132源码hash在运行后匹配；24份Windows/PS/env/role capability保护文件逐字未变。PG/API覆盖缺失条件、16类依赖变化、tenant/角色/当前撤权、旧回放、新cycle、绑定变化、同键/异键并发关闭、关闭/重开竞争、事件失败回滚、资源在等待真实Case锁期间结束、关闭与资源取消/回执重开竞争及v15升级。升级验证相关表数量、升级后的完整依赖检查和既有历史迁移回归，不宣称逐字检查了所有数据库字段。

首轮118PASS/1FAIL来自fixture尝试非法capacity=0，改为quantity2/capacity1后119PASS。补充轮39PASS/2FAIL为测试使用不存在的holds.combination_id和在UUID fixture库执行固定parkweave CONNECT grant；改用member关系及fixture适配。其后205PASS/1FAIL仅固定ID清单在测试启动后同步；最终2个guard PASS，全量以最终冻结源为准。资源到期oracle使用1秒窗口与1.05秒真实锁等待，属于Linux工程测试，存在负载敏感性，不能归因或替代Windows结果。

受控回复真实页面23/23PASS：事项/token/导航/ABA/旧cycle、草稿、重试key、revision/cycle/SHA/id guards、当前与陈旧403、回执导航、两只读角色、脚本文本。第一次22/23是oracle切换Case清草稿后错误期待旧草稿仍在，修正夹具后通过。此oracle替换fetch，业务API调用0，不是后端授权测试。

独立实际Linux Chromium/API/worker/PG三角色（执行者Runassignment由fixture owner在UI外显式准备）：新资料与确认→页面资源组合/Case关联→专员分派→本人接单→合成回执→未核对关闭受阻→owner核对→显式校验/本地关闭→专员/执行者最小只读→owner重开/显式校验/再次关闭→reload。2轮/5事件，Case等待真实确认；回执和资源状态保持。320/390无横向溢出，8张截图存于独立目录，无覆盖历史图片；已目视确认桌面最终状态与320详情。独立后端、UI、Windows范围只读审查未发现剩余阻塞性问题，审查者未运行测试/DB/browser/network。

## 原计划剩余与Windows边界

F2-T04仅增加当前合成资料Case本地记录闭环。通用CaseStep、接受后责任调整/回执handoff、站内通知/送达/已读、原Case完整生命周期与FULFILLED真实证据仍未交付。T01真实性/事实冲突/按用途复用、T02注册服务有限DAG/目标覆盖、T03任意组合/一般Approval/转移、T05业务Outbox和全流程未知结果、T06审核模板/新企业冷会话、T07完整原V1端到端仍缺。

唯一最新实际Server运行仍37420887816、源码e9e962d4a5e2b42ea3750c83ee8d7145cc3f24f1：PreparePASS、native_suite677.625秒exit1/timeoutFalse、安全发布器PASS、绑定PG StopPASS；真实cases/counts/report_state/根因UNKNOWN，等待此run已有安全JSON。不取私有日志、不猜根因、不盲重跑；本地通过不称修复Server。Server不是Win11，F1未签收/F2准入NOT_PASSED、Win11/36AT6EX NOT_RUN、R4 DISABLED、真实模型/预算0。
