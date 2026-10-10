# 原持久步骤未知操作的安全冷恢复

从32879934025bb2148156797f39b91d22075e895e继续，先冻结[有界合同](ServicePlanColdRecoveryContract.md) ae9fa1381732664d6f86f967c0955c59ddafea83，再补原ADOPT、BEGIN、REPORT_FAILURE、RETRY、VERIFY提交的持久只读核对。原计划/步骤ID、64事件、8代替换历史、CAS及actor/key/fingerprint幂等保持，没有新业务写命令、表、迁移或Grant。

原提交前只存11个白名单元数据字段，最多8条、640字节、24小时；不存正文、理由、token或凭据派生值。同参数保存保留原到期时刻。存储不可用或容量满在POST前拒绝。刷新、新页或API进程重启后，重新认证并从原入口进入同Case；按服务器本人actor_ref找原句柄，仅GET核对原key，不自动重发未知提交。热页“只读核对此次原提交”也只GET。

热GET前、接受GET/原POST回包前及结束核对前重新核对strict存储全部字段和期限。句柄到期/删除/损坏/同名有效替换时拒绝旧证明，保留有效替代句柄；旧私有pending/重试key丢弃，手工草稿和PG历史保持。失效页面用正面白名单构造，单个event、理由、来源及其它属性清空，只留未经当前重读的最小状态。没有自动普通GET或POST，原写/导航/目标结果暂停，显式刷新才重新进入原读。

原事件COMMITTED只证明原动作已保存。当前来源状态独立计算，旧计划历史不成为当前有效核验；NOT_OBSERVED不表示失败，迟到请求仍受原CAS和幂等保护。核对专用GET不会调用普通计划GET的观察失效写；所有可能等待的源锁后重新取数据库时点，返回前复核当前原角色/身份/权限与Run期限。恢复响应移除理由、目标/材料/回执正文、私有来源快照及可写动作，仅保留原事件证明与当前最小只读状态。

未知句柄保留期间原计划写、步骤导航与目标结果读取暂停。匹配原Case/Run、原plan/step/action与提交前版本后，用户可明确“结束原提交核对，重新读取当前步骤”；这一步才清句柄、调用原普通计划读。核对不清新手工草稿。当前403强制清私有内存/DOM并保留原句柄；切换身份或Case后的旧200/403/POST忽略，不清另一原请求。句柄到期或格式损坏只清句柄，原历史仍须原合法入口人工核对。

真实隔离PostgreSQL、loopback HTTP及Chromium验证范围包括：五动作实际提交后丢响应、只读热/冷恢复、新页与同origin API重启、原获派专员/执行人、当前撤权/到期/换offer、跨身份/企业/园区/Case、来源与原请求换版/历史替换、同key重复和不同正文冲突、并发与等待后到期、未观察到的迟到原请求CAS、存储边界、元数据篡改和隐私负例。实际窗口、精确SHA与独立审查结果在本片机器证据及整合记录中逐项登记；不同窗口不相加当作完整验收。

最终运行源码23f9a2f9285366a9cd6f3192ec159fc148d84f21：根6完整相关模块246PASS/0FAIL/ERROR/SKIP，JUnit396.249秒、受控397.769329秒；独审4完整相关模块184PASS/317.771秒，另4个自有probe模块23PASS/63.776秒，最终LIMITED_PASS。323源码首尾零漂移，manifest SHA8689a60548cb3969de8a28c01f4de47461fe384f9c507367a307f02ac29e8bde，诊断AST1361。两轮BLOCKED分别是热/在途24h期限漏检、失效单event理由/来源残留，先补合同再最小修复，五条实际失败均独立复验通过。d5根697PASS/独审306PASS、92根649PASS/独审326PASS仅各自历史源码窗口，不能抵消阻断或作23最终验收。根最终范围聚焦本片及目标结果/异议页面/诊断；没有再次运行原全仓或完整老smoke driver。原driver已调整单POST+GET核对及显式结束核对的17次业务写预期，五动作真实页面恢复另有实测。

公开证据：[最终核验](evidence/service-plan-cold-recovery/verification.json)、[独审](evidence/service-plan-cold-recovery/independent-review/report.json)、[首次阻断](evidence/service-plan-cold-recovery/first-independent-review/report.json)、[二次阻断](evidence/service-plan-cold-recovery/second-independent-review/report.json)、[原窗口](evidence/service-plan-cold-recovery/window-history.json)、[故障私有保全清单](evidence/service-plan-cold-recovery/private-artifacts.json)、[真实窄屏](evidence/service-plan-cold-recovery/browser/recovery-390.png)。失败XML只导出明确标注的passing subset，time是节点和而非完整夹具窗口；原失败栈/日志不公开。独审末尾一次Python子进程Git128认证上下文故障保全后，默认工具shell只读重试成功；没有修改凭据/安全网络配置。正常dev整合和最终远端核验另记[整合记录](ServicePlanColdRecoveryIntegration.md)。

仅原授权合成合同。正式ServiceRelease/Approval发布主体与用途/在途版本协议、真实服务承诺产物及独立核验、Case FULFILLED判据/权限、多用途资料分享仍需要独立业务授权。Windows、全仓、原AT/EX未由本片验收，旧a823a28未迁移，已完成资料包导出不重做。没有真实业务、模型调用、外部通知、政策审批、部署、main变更、强推或凭据/安全网络配置变更。
