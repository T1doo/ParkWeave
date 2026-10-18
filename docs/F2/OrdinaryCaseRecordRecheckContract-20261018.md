# 普通 P5 本地记录核对、关闭与重开

基线 `1f7e4d4a11606a511062fecb1863803209f3831d`，产品来源 `33aef7ab8f297c52bbb15d1ae0930ac33a253d7e`；普通开发分支。此前 P3/P4 片只读验收与39个有效节点保持历史，不为本片重复包装。

原文：产品设计 §5.5（175–179行）要求执行者只办理本人步骤，实际材料、预约、接单与凭据核验；本地软件记录与线下履约分开，不因超期自动关闭。分阶段计划 F2-T07（90/98行）要求持久化、正确角色和刷新可重放；AT-15（287行）要求无证据不关闭、冲突复核、重开不抹历史。原代码已有 P5、REVALIDATE/CLOSE_LOCAL_RECORD/REOPEN、冷恢复及原核对包；普通 marker 被生命周期入口拒绝，P5来源仍走 Run assignment，是当前具体断点。

本片只接通显式同Store `CURRENT_PREPARATION` 的既有合法 SYNTHETIC 资料：原 P1–P4 明确核验 → 经办人原入口 REVALIDATE → 明确 CLOSE_LOCAL_RECORD → 原计划 P5 VERIFY → 原目标结果和原核对包。保留原 revision/cycle、键指纹、原事件、资源规则、幂等和恢复算法，不新增工作流、存储层、批准或自动核验。关闭仍是 LOCAL_RECORD_CLOSED / Case WAITING_CONFIRMATION，`case_goal_completed=false`，不是线下完成或正式AT35。

沿用上一片显式普通DI和原CaseStep marker/ACCEPT→CREATE/人工回执证明；不能先用旧Run路径失败后回退。任意active/inactive Run assignment、Native痕迹、旧隔离marker、混合provider继续拒绝。普通执行者不因此取得全Case/P5/Run读取权；原reviewer只保留获派的最小状态读取，无经办人核验或关闭权。

普通P5快照必须绑定当前普通步骤及首次UUID/不超过300秒的原绝对期限、权限generation和材料目录。只核验P1/P2的计划不继承该期限。真正使用P5的读写在全部锁等待后重查步骤与资源时效；不能返回假当前或提交失效的核验。合法过期/撤权历史可读，但无当前产物。经办人的REOPEN沿用原规则，允许在旧依赖失效后明确重开并保留旧事实；它只开启新核对周期，不续期、重授、重发接单、重写回执或释放资源。下一次REVALIDATE仍须原当前前置。

原恢复接口只读取原请求结果，不重发。当前普通生命周期与P5来源复用原事件请求指纹证明，不能仅凭可伪造的ledger状态字段判当前；关闭、重开和新周期均保留历史。owner READ/PREPARE历史与写入EXECUTE分离；缺READ/PREPARE准确拒绝，缺EXECUTE禁止所有写入和原POST重放。

管理初始化与本片不同：cli现只有企业合成初态，专员/资料Grant/目录及执行者/资源配置仍由合成测试setup提供；真实主体映射、获授权管理目标清单与初始化/配置流程还缺。可在后续做受审代码和合成测试，本片不执行任何真实身份、Grant、分派、目录发布、批准、凭据或生产安装。原Native拒绝不绕过。

验证只用新拥有的临时Linux PG与合成配置，覆盖原API/完整原HTML、关闭/重开/原请求冷恢复、P5明确VERIFY、原TXT冷启动、权限/代际/资源变化、最后锁等待、证明损坏及默认旧路径拒绝。冻结源、独审、日志和失败均保全，有限安全重试。浏览器、Windows、正式AT35、真实业务和初始化保持未验；不改main、不强推、不部署、不调用真实模型或新增费用/网络权限。
