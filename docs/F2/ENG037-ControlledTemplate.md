# ENG037 最小持久四步合成模板

实施基线2da286a943191482ae9353104a15f8ccfc7bd51a。父线程已采用ENG036四个A默认：固定材料→资源→分派→回执；已有合法assignment，无自动grant；一个内置不可变合成版本，工程审查非业务发布；上游变化阻塞并显式重验，保留实际责任/回执/资源。

实施前边界：计划绑定当前合成资料Case，仅在尚无资源关联/分派/回执时创建，避免把旧流程补写成新模板执行。四步由owner显式CHECK_STEP保存当前版本/hash，原动作仍由原角色人工执行；附着计划的资源关联要求P1当前，OFFER/ACCEPT要求P1/P2当前，回执提交/核对要求P1/P2/P3当前，拒绝/撤回/纠错/重开沿原授权处理而不自动重派/释放；回执纠错/重开仍受原父资料版本fresh校验，父版本已变时409阻塞，不承诺自动恢复旧回执。入口不增grant，不改未附计划业务行为，不调模型/真实API或发送外部消息。

计划/审计修订独立持久，固定template hash/来源snapshot/CAS/idempotency；读取会同步持久化首次观察到的上游失配标记（仅计划元数据，不改变业务），即使源恢复原值也须显式CHECK_STEP。CHECK清除该步及下游当前指针再保存本步，旧事件/snapshot保留。只读身份也可触发真实观察失效，不拥有CHECK写权；角色最小投影不含其它源正文/快照。grant变化仅按当前权及观察失效处理，不宣称未实现的统一授权epoch或完整Approval。

兼容现有事务：原业务先取当前身份与preparation锁；计划读/创建/CHECK统一取preparation FOR UPDATE后计划锁，避免草案plan→source与原parent→plan逆序。业务gate/失效hook沿原同事务连接，无独立提前检查；跨源沿既有lifecycle dispatch→receipt→resource UUID→组合/成员→Case，末锁后DB时钟。附计划的写在同事务中验证当前checkpoint，再执行原动作；计划与新业务失效指针同事务，崩溃回滚。既有业务重放不产生新动作或复活checkpoint。业务gate即使前置通过也保存已经观察到的下游失配stamp；每个调用的独立ContextVar队列在finally恢复，后续业务Conflict/Denied/锁超时不会漏掉该观察。业务gate或CHECK拒绝会先回滚原事务，再以独立计划元数据事务补记已经观察到的失效；补记绑定当时plan ID/revision，不能使较新的显式CHECK重新失效。若补记锁忙，返回明确可重试409，此时不能声称失效标记已落库；必须重试/刷新并显式重验。该失败路径不承诺业务与补记的跨事务原子性。未被任何成功读取或补记观察到的撤权后恢复，没有统一授权epoch可供追踪，不宣称捕捉这类未观察变化。

验收：PG/API实际四步及越序零副作用、hash/CAS/幂等/并发、持久重启、源变化/资源时间结束/撤权/恢复需显式重验、历史完整、权限/角色/tenant投影、旧流程拒绝模板化、无assignment BLOCKED。独立事务/权限/UI审查，三角色真实Chromium/API/PG与受控迟到响应，最后冻结aggregate。只本地commit、不push/newCI/export/LIVE；F1/F2未签收、R4关闭、Windows37420887816待已有安全JSON，Win11/36AT6EX NOT_RUN。


## 已完成的独立审查与真实验证

初始相关141例为139PASS/2FAIL：一例结束时间fixture违反ends_at>starts_at，修正为同时设置开始/结束；另一例owner只读误要求EXECUTE，改为先核验当前读范围、直接取parent FOR UPDATE后重验，GET不要求EXECUTE。保留初次报告，不把测试数据错误混成产品失败。后续迁移、最小权限、旧stamp、真实锁忙等41定向例全部通过（48.74s）；最终模板29例全部通过（24.60s），含实际子进程提交前崩溃/重启同key不重复、并发GET/CHECK、撤权恢复、越序零业务副作用和独立复核找到的两条失效回滚路径。

三位独立只读复核分别覆盖后端事务/权限、UI时序/最小投影、迁移/Windows保护。关闭owner只读门、executor资料跳转、CREATE误清未使用草稿、补记锁忙500，以及门本身拒绝/门通过后业务409丢观察等问题。最终无剩余实质阻断；审查者未运行测试或访问网络，实际结果由实现者取得，不能合并成独立测试成绩。

真实Linux Chromium/本地API/worker/PG的新诉求三角色链：初建计划因无assignment明确BLOCKED，fixture owner单独为本次新Run准备合法访问后逐步P1—P4；应用不新增Grant/assignment。企业在资源界面确认并关联两资源，专员分派、执行者本人接受/提交、企业核对后四步完成，revision5/events5。观察HOLD撤权后恢复原授权，P2—P4仍须显式CHECK，最终revision8/events8；刷新读回，原ACCEPTED责任、CONFIRMED资源、LOCAL_ACKNOWLEDGED回执及Case NEEDS_INPUT保持。专员/执行者投影、跨企业隔离、token清理与320/390无横向溢出通过；9张当前图独立目录hash匹配，视觉检查未给用户签收。

真实页面受控迟到响应：新计划18/18、既有通知16/16及Case23/23全部通过；这些是UI响应顺序oracle，不冒称后端权限测试。当前Windows/权限/环境24份保护文件与两份原V1源字节保持hash，Windows仅补安全诊断测试标识名单。原截图审计的3缺图、3历史覆盖仍保留，不拿新图替代。

完整回归期间独立审查补出新路径，第一次全量实际836PASS/0FAIL/1WindowsSKIP仅为中间运行，源码期间变化，不作为最终冻结成绩；保留原报告和日志。最终源码重新冻结后另跑aggregate，当前证据见[evidence/eng037-controlled-template.json](evidence/eng037-controlled-template.json)。本轮owned harness/API/worker按精确PID停止，数据库、运行期及旧证据保留；没有新恢复/导出包、外部网络、push或CI。

最终重新冻结全量：837PASS/0FAIL/1WindowsSKIP/2既有WARN（261.69s）；154份完整冻结源与runner的142份被测源hash逐项匹配，397个安全诊断函数ID同步，9张当前图hash匹配。full36AT/6EX仍NOT_RUN，原生Windows不由Linux结果推定通过。固定计划结果仅LOCAL_RECORDS_CHECKED，原Case目标、完整Approval/授权epoch/通用DAG执行/模板业务发布/AT14预览/新企业冷会话赋权/真实履约缺口仍保留。
