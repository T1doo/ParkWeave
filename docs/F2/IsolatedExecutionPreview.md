# 原P1注册材料链的隔离执行预览

后续获审提交保护源码 `cadc7a34ecece7d77d793c4676e1b552838f41cc` 和实际剩余边界见[PreviewCommitProtection](PreviewCommitProtection.md)。下文的5c25验收与OPEN记录是历史窗口；当前不再输出CURRENT强保证，原v2不可变产物保持兼容。

仅原§6.3/F2-T02/AT14的P1合成隔离范围获得LIMITED_PASS。获审运行SHA `5c25aa08c7ab499764bc2aa145dd932ee8a2a417`；修复前合同SHA `959c020cc7c8221f60028a956e9460ea13b158af`；基线dev `f5f187fb1a390e724a3b471f82243425349b4f85`。原冻结覆盖表AT14仍NOT_RUN，不将本局部预览签为完整隔离工程执行。

原controlled-plan preview仍只做结构与来源检查，planning-preview仍只保存确定性规划元数据。新入口沿原bounded-planning区明确执行原 `preparation.command` 的ADD_EVIDENCE×双槽、REVIEW、CONFIRM；缺槽实际进入原REVIEW产生FAILED。专属PG连接创建固定八个pg_temp影子表，search_path仅pg_temp，代理只允许原18条精确SQL模板，结束始终ROLLBACK/close。独立新UUID资料/Case/Run/材料/事件与带新UUID命名空间的合成actor用于SIMULATED_ROLES_ONLY；原获派真人、正式材料审核和Case目标不被替代。持久结果仅专属SQLite v2预览库，默认API未attach，明确合成配置才可运行，不创建真实权限。

v2独立不可变proof列锚原Case/Run/资料和请求revision、两槽ID/version/hash、完整目标及覆盖、未预演步骤与执行合同。正文重算sha不能删目标或改槽版本类型。新执行核对P1原adapter/revision/全部method/path/role/commands、无依赖、既有service version1；新登记动作或服务version2只可读旧历史，新执行409。历史来源变化显示STALE、保留当时完整目标和产物；不强行改为新诉求。SQLite根0700/库0600，逐开核cluster system_identifier/database OID/名字、meta、精确schema/不可变trigger与条数/UTF-8字节上限；旧v1库明确拒绝，不迁移/修补/清空。

当前READ/PREPARE/EXECUTE先于读历史、重放和GET恢复。相同key/body并发仅一结果，CAS或key/body不同409；基础设施中断不保存成功，NOT_OBSERVED不等于失败。原页面仅存最多8条/24h的五字段不透明句柄，第9条活跃请求拒绝发送而非淘汰；回复和释放均重核持久句柄与期限。换Case/身份/编辑及403清私有投影；迟到成功或403不复活旧视图。明确补正原输入后新key预演，旧FAILED不变；丢响应、冷页、新API实例和实际PG/API重启均只GET原key，不自动POST。

[根验收](evidence/isolated-execution-preview/root-frozen-v2-related-audit.json)为精确5c25的10模块270PASS，JUnit301.394秒、实际受控303.430秒，0FAIL/ERROR/SKIP、自然exit0。346个源码路径清单hash `3acd646c4a75308478dbacd0dcf5dc798f66bbdfda677ae8efb62ab88f82ca3a`，首尾0漂移；1530个诊断AST函数ID完整匹配。原页实际检查1200/390/320无横向溢出，不显示材料正文或token。

[独立报告](evidence/isolated-execution-preview/independent-review/report.json)hash `ea75280abeffdb58b18335ddad678cd94b7c1747281ecb16b37663a15e625b6a`。以下是独立分窗，不能合称一次193测试，也不借根270：

| 独立窗口 | PASS | JUnit秒 | 实际受控秒 |
| --- | ---: | ---: | ---: |
| 旧六负例复验 | 6 | 7.494 | 8.791 |
| 自写HTTP/API | 16 | 19.364 | 20.713 |
| 七完整相关模块 | 166 | 114.281 | 116.026 |
| 自写原页面 | 2 | 6.635 | 7.750 |
| SQL闭包/原v1库拒绝 | 2 | 2.990 | 4.077 |
| 实际PG/API重启 | 1 | 6.439 | 7.487 |

所有通过窗口0FAIL/ERROR/SKIP、自然exit0。独立真正stop/start自有PG，postmaster PID/start变更、system_identifier/OID保留；三个不同API PID，默认新API GET/POST403，明确同v2存储的冷页仅GET原key恢复同产物/proof，SQLite和正式public逐值相同，无重签fixture capability或Grant。全部public业务表/所有行纳入快照，仅既有脱敏authorization_audit另列为允许拒绝审计，不排除planning_previews。

首候选7dd4ada独审6真实FAIL/BLOCKED（正文省略目标/覆盖、P1动作声明漂移）及首观察器6FAIL完整保留；其根252PASS不抵消阻断。新独审首窗6ERROR为basetemp夹具配置错误，产品断言未执行，原源码授权/创建证据检查未放宽；私有runner修正后另窗复验。开发01观察器失败、identity首probe设置错误和开发07七个平台skip亦保全，均不算最终运行通过。[安全证据与hash](evidence/isolated-execution-preview/artifact-hashes.json)不含失败原日志/XML，原件仍在ignored0700私有.runtime目录。资料包导出未重做。

P2–P5/unsupported目标保留但不执行；正式Case/材料/资源占位/Approval/通知/正式成果及Grant写入0，Case目标未完成，model calls0。最后source取样到SQLite提交之间的无协作来源写入仍有OPEN竞态；下一GET可标STALE，不签跨PG/SQLite原子线性化。测试含实际SQLite锁与REVIEW/CONFIRM后、SQLite INSERT后提交前故障注入，未签设备断电耐久性。完整AT14、全仓、Windows、真实履约、正式服务发布/部署均NOT_RUN；旧Windows Job/accounting修复仍延期，dot unknown未定位。
