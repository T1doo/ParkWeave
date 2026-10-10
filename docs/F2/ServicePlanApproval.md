# 原首次资源交付的持久方案 Approval

沿原产品§7.4及F2-T03/T05，在原owner已有权限的首次同Case合成资源交付前增加明确PROPOSE→APPROVE→可REVOKE→原提交CONSUME。原资料异议与资料包导出已完成，本片不重做；批准消费不核验P2，不完成Case，不批准政策、真实预约或线下履约。

仅显式隔离测试可启用：原LOCAL Store、同进程签发的FixtureDatabaseEvidence、全新自有PG endpoint/database OID/postmaster与最多16个既有preparation范围一致。configured_app没有启用入口，环境变量不会开启；默认原资源交付保持原合同。合成setup只给既有preparations增加两个有界候选JSONB列及固定不可变前缀触发器，不接生产迁移，不新增业务Grant、数据库Grant或角色。

每个独立Approval UUID绑定原Case/Run/park/org/owner、计划UUID/revision/定义与目标、service ID/version/catalog完整hash、资料revision和双槽ID/version/hash、P1当前依据、所有成员ID/resource修订/规则/时段/数量/来源/占位到期、精确原Deliver命令与原请求版本、固定CASE_RESOURCE_DELIVERY用途、原owner HTTP及Run状态/fence/修订、当前owner和原专员身份/能力/准备与资源授权版本。目录/资源规则/Run的PG xmin在≤120秒合成批准窗口内捕捉变更后恢复旧值；无revision的授权也绑定实际行版本。它不是正式全局epoch或新增审批角色。

账本每Case最多64事件、8个批准对象；活动对象预留撤销或消费额度。不可变事件链、原CAS与幂等键决定状态，独立head与SQL前缀保护拒绝清空、截断、改写。来源或授权变化、撤权后恢复、过期都不能复活旧批准；旧事件保留，必须显式新提案和批准。同key同正文核对原事件，不同正文或跨Case拒绝。

批准消费、组合确认、实际成员、Case claim、不可变Case关联及原回执同一PG事务提交。原Case关联另存批准引用，原P2/goal读取验证消费证明；剥离回执引用或单侧损坏账本不能降级为旧式未批准交付。最后等待后、COMMIT之前重验原授权/来源/期限，故障全部回滚。批准期限≤原预览120秒≤任一占位期限，不延长预约。

原资源页面明确展示批准的Case/计划/材料/资源版本、执行身份与期限。未批不能点提交；来源变化后保留历史并可明确撤销。每次写前仅保存最多8条/24h的9字段不透明恢复句柄，无正文、hash或token；答复丢失、硬刷新、重新认证后只GET核对原key，不自动POST。迟到Case/身份/句柄替换答复不得填入新视图；403清私有内容。COMMITTED只证明历史保存，NOT_OBSERVED不推断失败。

目录来源的最后读取到COMMIT仍有非协作owner发布窗口，正式ServiceRelease/独立审批主体/任意资源路由/在途兼容或一般DAG不在本片验收。candidate capability同进程签发，本片验收新Store/新App与浏览器冷恢复，不签收新的API进程或PG重启后重新启用；默认production factory继续关闭。可信数据库owner同时改写全部账本/head/回执/关联不受加密外部锚保护。全仓、完整原AT/EX、Windows和真实履约均未验收；无部署、凭据、安全网络改动或模型调用，旧a823a28未迁移。

精确运行源码 `11b756db4e164fafb7756ec63bffb286178e0a73`（合同依次8c52f07、318a4f1、05efd32、1f32db6先于对应实现冻结）。根14个完整相关模块524PASS/0FAIL/ERROR/SKIP，JUnit540.769秒/受控542.552443秒；独审11个完整模块443PASS/415.815秒，额外API17PASS/33.576秒、实际浏览器8PASS/27.655秒，全部exit0且零失败/跳过。根和独审计数分别保留，不相加为全仓成绩。328路径首尾零漂移，manifest SHA256 `48c99bad9420ddd3976fa3498b7d4ef5d65fc40be2a5a14d3bbe428956d188ec`。独审报告 SHA256 `729592298b8f2e02b2baa056bdd09b90d5d71b3ced7f9a64eefb007cd1c5eb4b`，精确LIMITED_PASS。

独立实际边界为8个已批对象：1次消费、7次明确撤销、共24事件，原16事件不变。64为配置上限，8对象每个最多3阶段的合法图只能到24，不冒称跑过64事件耗尽。五种SQL账本/head损坏写拒绝、六种消费证明损坏下原交付恢复/P2/goal拒绝降级；实际迟到三动作Case/身份替换、恢复GET等待跨本地句柄期限、存储失败零POST均通过。

此前46/14及后续55/6等只属于各自未提交开发窗口，不代替精确11b最终验收。1个初始夹具导入错误、1个错误数据库连接观察器，以及时间规范化、按钮/面板、冷身份状态竞态四次产品失败原日志/XML均私有保全，修复后上述冻结窗口全部通过；本次独审没有产品或观察器失败。公开仅安全汇总、最终PASS日志/XML、补充源码和三幅原页面图，失败原件不推送。

入口：[实施前合同](ServicePlanApprovalContract.md)、[最终机器证据](evidence/service-plan-approval/verification.json)、[最终独审](evidence/service-plan-approval/independent-review/report.json)、[开发窗口历史](evidence/service-plan-approval/developer-window-history.json)、[工件哈希](evidence/service-plan-approval/artifact-hashes.json)。已完成的资料异议闭环和导出保持原验收范围；本片只是后续批准前置。最终候选/dev/main远端SHA与未推送文件见[正常整合](ServicePlanApprovalIntegration.md)。
