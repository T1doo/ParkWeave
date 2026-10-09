# 生命周期原请求冷恢复：实施前冻结

基线`6d78f52f9a2c896ccdd9d108799b2713ba778c84`，本地/远端一致、88403af祖先已核、工作区干净，无挂起Git操作，平台索引刷新锁保留；本环境唯一源码写入者。既有`localCaseRetries`仅内存，clear/刷新即丢失；`case_local_events`有不可变原actor/key/指纹及修订，却只有需要EXECUTE和原正文的POST历史回放，无只读原键恢复。不得把此前投递当作已执行。

本切片补既有REVALIDATE/CLOSE_LOCAL_RECORD/REOPEN的冷刷新未知结果恢复，不重做结果检查、资料异议、生命周期状态或关闭逻辑。沿用CaseResourceDeliveryContract的opaque句柄及未知不重发原则，不扩大FULFILLED、正式Release/Approval、真实履约、模型、通知或权限；不改schema/grants/main/强推/部署/凭据及安全网络。

新增GET `/api/preparations/{id}/local-case/recovery/{request_key}`。重新认证当前active企业原owner、READ和PREPARE归属；历史恢复无需EXECUTE/HOLD，但历史快照及当前Case关联的全部资源须当前READ。原actor/key有Case错配则409；他人/跨企业/未授权Case403，不泄漏原事件。原键查询用既有同actor/key锁等待在途事务；lock_timeout/未观察不是未提交证明。GET不INSERT/UPDATE业务、验证、重开、完成或自动POST。

用实际不可变case_local_events行核对action/revision/cycle/actor/scope与payload、源快照及其周期sha、Case/Run引用，以及当前真实历史唯一修订。原回执分离返回id/key/actor、原动作/修订/周期与不可变payload；不索求原正文，不提供新的客户端批准字段。缺失/篡改证明409。NOT_OBSERVED保留未知状态。当前视图复用原read的同事务来源/时间/ledger检查，不另造结果核验器；当前无效/后续重开/资料或资源变化仍保留原COMMITTED，不把历史事件当当前有效或自动处理。现有POST权限/CAS/幂等语义保持，原READ新增actor_id仅用于真实当前身份匹配。

页面最多8条严格opaque `{actor,id,key}`（id为资料事项UUID），前缀`parkweave.local-case-recovery.v1.`，无token、正文、理由、方案、来源hash或原动作参数。明确动作在POST前安全保存；保存失败不POST。存储未知、损坏、超界、403、超时、NOT_OBSERVED锁住本Case新生命周期动作。清视图、切身份/Case/草稿或刷新不删原句柄；重新认证后仅GET原键，并核对原回执及当前历史精确payload后才移除句柄。明确409/422请求拒绝可以释放本次已保存句柄，其他情况必须保留。旧内存重试不自动迁移、无恢复POST。

身份/Case/代次/草稿变化，迟到成功或拒绝不回填/清空新私有视图；403清当前私有视图但保留原句柄。正常确认动作仍由原按钮明确触发；原回执历史与当前有效性分别显示。原REOPEN不取消占用、Case目标不完成，正式权限主体合同仍缺失。

完成判据：真实PG/API所有原3动作、NOT_OBSERVED与原历史/当前变化分离、并发GET等原actor/key、重复恢复无业务写入、跨企业/角色/撤权与READ/HOLD分离、腐坏/不可变/上限；真实HTTP/Chromium丢成功/拒绝响应、冷刷新及独立API进程重启只GET、存储隐私、未知禁POST、403、Case/身份/草稿迟到响应负例、三宽度；既有生命周期/资源/计划必要兼容。冻结普通候选推送→独立只读审查→通过后普通FF开发分支推送；故障私有日志保全。全仓/42AT/EX/Win11/真实业务及模型未由工程测试验收。
