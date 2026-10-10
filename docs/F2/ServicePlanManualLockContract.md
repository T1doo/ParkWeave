# 实施前冻结：原注册步骤核验的人工锁

基线 `9bc4ed59ed5156ee3a2a84c2023500eca355c426`，普通fetch及实际ls-remote一致；main `31e7acb7e53bb1ab6465b9daae59de28757f7583` 保持。仅root写源码，既有独审代理已结束，没有活动pytest/API/worker写入者；平台空索引刷新锁保留。不假定跨环境共享。原§8/F3-T03/AT25–26：既有1–5注册链、来源hash/真实检查、下游失效、8份历史、事实来源LOCK已存在，不重做一般依赖图。

缺口与范围：企业明确核验后的步骤决定没有人工锁，原VERIFY可在失效后直接改写该决定。本片只在原service_case_plan JSON、64个追加事件/CAS/actor-key幂等合同内增加LOCK/UNLOCK。无新表/迁移/Grant/角色/模型/通知/部署/真实完成。手工锁保护原核验内容，不阻止原角色在原适配器保存真实来源变化；变化仍使旧检查失效及阻塞下游。

仅原Case owner、当前READ/PREPARE/EXECUTE及原Run权限可LOCK/UNLOCK。LOCK要求当前VERIFIED、前置当前有效、所有来源无缺口、精确expected_revision/step UUID/current source SHA，并保存绑定plan/step、原owner、核验hash与来源快照的锁事件引用。UNLOCK要求当前计划仍有原锁，允许来源/诉求/目录已失效或前置被阻塞，以便原owner明确处理冲突；不复活任何检查。锁内禁止新BEGIN/REPORT_FAILURE/RETRY/VERIFY，原同键已成功事件仍可核对。解锁后保持原协调/核验内容与失效标记，再由原流程显式重验。

锁与当前来源不一致、绑定变化、或依赖失效时步骤显示LOCK_CONFLICT：保留旧核验正文/分配/决定和原事件，不静默改写；未解锁不能采用替换计划。明确解锁后原ADOPT可保留全部旧计划、步骤、锁/解锁事件并新建稳定UUID。依赖范围采用现有P1→P2→P3→P4→P5固定链，报告直接变化与受影响步骤，未改变的上游应保持；未知request/catalog/registry绑定变化扩大至此Case全部采用步骤。不是任意服务DAG或外部发布线性化保证。

Command仅增加LOCK/UNLOCK；LOCK和VERIFY要求expected_source_sha256，其他动作不允许hash。LOCK事件保留当时来源并证明hash，但不执行/重新核验业务；UNLOCK记录理由、原revision与step绑定，不修改原核验快照。恢复证据校验新动作的原指纹/owner/hash，保持原11字段≤640字节、8槽、24h、不含正文/hash/token的浏览器句柄。锁/解锁未知回复热/冷只GET，不自动重放；当前撤权及等待后的期限仍重验，隐私最小投影保留。

验证先冻结独立应更新/应保留集，真实PostgreSQL/API和实际loopback HTTP/Chromium验证：锁来源变化、未解冲突/替换拒绝、明确解锁重验历史、CAS/同键重复/同键改参/跨Case/跨企业/专员越权/撤权、丢响应冷恢复、迟到与并发、原业务无副作用及最小投影。完整相关测试与独审精确SHA通过后才正常整合dev。保存原失败与观察器故障的私有日志，不把历史窗口或Linux成绩当全仓/Windows/原AT通过。

关键路径只读盘点：当前contracts/service与contracts/plan只STRUCTURE_ONLY，目录/模板候选不是正式ServiceRelease/Approval。原§7.4–7.5要求明确发布/撤回/来源维护主体、不可变精确服务/动作修订与实例范围，Approval绑定方案/资源修订、运行身份、期限、授权版本和前置；在途Case逐件兼容核对、破坏性迁移拒绝。上述正式功能仍有缺口，可继续开发合成合同；真实主体发布、真实履约、Case FULFILLED和对外分享没有本片授权。旧a823a28不迁移，不扩大权限或改安全网络。

实施期间补充、实现前冻结：64事件上限内必须为每个活动人工锁保留一条UNLOCK额度。LOCK新增一个锁也需同时预留它的解锁额度；其它新协调/核验不得消耗既有锁的保留额度。UNLOCK可消耗自己的额度。界面与服务端同样限制，原同键历史核对不消耗额度。计划可最终到64但不留下无法解锁的活动锁；达到上限不能凭空清锁或重置历史。真实64边界与多锁额度用原API事件实际构造，不能只手改revision冒充有效账本。

0c2e5fa精确独审BLOCKED后、修复前补充：完整根363PASS与独审345PASS不覆盖独立发现的五条产品失败。原goal-results结构白名单遗漏合法LOCK/UNLOCK（2失败），且该只读路径未校验人工锁证明，缺失LOCK事件/错误owner/错误step可误报当前通过（3失败）。兼容要求：合法锁/解锁作为原协调事件进入目标结果结构校验，但当前核验只能来自原VERIFY，不由LOCK代替；带锁事件/锁字段的计划须核验原owner、指纹、来源hash和锁与核验内容的完整对应。来源/前置/绑定变化下目标结果保留原历史证明、当前未通过，并明确提示先解锁；UNLOCK不复活检查。goal-results仍只GET、零SQL观察写；损坏证明拒绝而不降级清锁。保持原(actor,key)事件身份：不同原角色使用相同字面key不应被错误当作重复同一操作。同一角色重复key仍拒绝。补真实API/页面的合法锁/解锁、来源变化、损坏证明、解锁/换版历史与既有目标结果兼容反例，再以新SHA独审；旧失败与原窗口不覆盖。
