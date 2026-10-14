# 原键收尾的两项父侧 HOLD 修复

接续 `237e9d574558e3e61682f1dd01bafae7ac1b387f`。该交付的首次拒绝清理及CAS授权保持两项被父侧HOLD；先前212PASS和独审12PASS不能证明这两项安全闭合。原源码、原反例和已核归档保留，未补造旧结果或重修缺件。最终源码 `0cc8e0e54ad90b83c2f8e2e5245bca074d6670a7`。

首次FIRST_DEFINITE_REFUSAL不证明原inner key永久不提交。现仅精确COMMITTED或严格单调版本推进的永久非提交证明允许显式收尾与句柄清理。REFUSED_FIRST_SEND仍保持原key、日志及句柄未决，不能自行结束、解锁或重发；GET只读、精确CAS、防重和其他句柄隔离保留。旧错误FIRST终态元数据也不能作为清理证明，恢复409保持锁，不自动修写或删除。页面同步去掉FIRST终态资格及错误永久承诺。

真实反例重现：首次拒绝GET以前错误给出finalizable=true。修后拒绝收尾且日志不变；以同inner key和同参数调用原已授权API实际201，再GET精确COMMITTED，才可明确收尾。没有新增服务或Grant，不改变原API自身合同，不以consumer拒绝否认后续实际成功。

授权HOLD也实际重现：最后一次PG检查通过后、SQLite CAS前，按原principal独占锁协议撤EXECUTE先提交；旧实现仍写日志，最终GET403。原反例记录为revocation_committed_before_cas=true、journal_changed=true、response_status=403，403不是回滚证据。

现_auth和_reviewer可借用同一PG connection；PG授权事务置于SQLite事务外层，持有企业与专员的原shared principal授权锁，直到SQLite CAS和commit完成。SQLite BEGIN IMMEDIATE若等待，仍在该PG事务上重新核当前权限。支持的撤权者沿现有exclusive principal锁协议竞争，不增加身份行UPDATE权限或新锁命名空间。撤权先赢，READ/PREPARE/EXECUTE各实测403且journal不变；收尾先赢，pg_stat_activity/pg_blocking_pids实际观察撤权等待PG Lock，日志在授权保护下提交CONFIRMED。最后GET可因随后撤权403；只据journal事实判断，不把403当回滚。保留原文件键锁、正文/inner key/旧状态/result/error精确CAS及同异参幂等合同。此日志收尾不改业务数据，不是跨数据库原子业务事务。

最终冻结根十模块 **219唯一PASS、0FAIL/ERROR/SKIP、2WARN，158.846秒，exit0**。独立owned PostgreSQL另窗 **3唯一PASS、0FAIL/ERROR/SKIP，3.83秒，exit0**；原完整HTML NodeVM **34断言PASS**（包含原25恢复/隔离断言和首次/旧错误终态边界），不是后台授权证明。227冻结文件hash一致，各窗不加总。原容量第9次采纳、丢收尾响应、冷恢复和原办理/目标/工作清单回归也通过。

失败原件保留：根237红窗2FAIL分别命中两HOLD；独审首外置测试缺conftest产生1收集ERROR，修命令加载原conftest后红窗1FAIL命中首次拒绝错误资格。根中间18PASS只列过程窗口，不算最终或加总。见[结果](evidence/template-hold-20261014/results.json)、[原撤权反例](evidence/template-hold-20261014/red-auth-cas-race.json)、[修复锁竞争](evidence/template-hold-20261014/auth-cas-race.json)和[独审](evidence/template-hold-20261014/independent/review.json)。公开导出仅脱敏4份log/XML的生成fixture会话repr，私有原件和SHA、XML统计、失败尾部空白均保留。

浏览器NOT RUN，历史Chromium data: ERR_BLOCKED_BY_ADMINISTRATOR仍保留且没有换URL/工具重试。无schema迁移、部署、模型/付费调用、凭据/网络配置、新Grant/registry或强推。main/F1/原F2及两host_case_once审批文件未改，仍false/null/null。

另收到的一次免费冻结prepare许可按独立边界处理：原批准范围已重读，但执行前GitHub API核查明确Forbidden，无法确认历史消耗情况；已停止依赖动作，未创建激活commit/执行branch，未执行prepare。详见[独立BLOCKED NOT RUN记录](PrepareOnlyApprovedBlocked-20261014.md)，不与业务PG测试或旧Windows/完整试验混算。下一步是恢复可授权核查后处理这一次原批准检查；本任务不会绕拒绝或自动重跑。业务当前无新增HOLD发现，未知/首次拒绝/当前拒绝或缺证明继续保持未决。
