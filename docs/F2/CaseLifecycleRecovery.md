# 既有本地Case动作的冷刷新恢复

基线`6d78f52f9a2c896ccdd9d108799b2713ba778c84`；先冻结`CaseLifecycleRecoveryContract.md`再实现。仅原REVALIDATE、CLOSE_LOCAL_RECORD、REOPEN的未知结果恢复，既有POST、CAS、状态和权限逻辑保留。旧`localCaseRetries`只在内存，刷新/清视图会遗失；新增最多8个严格opaque原actor/事项UUID/request UUID句柄，明确动作POST前持久保存。保存失败不发送；未知、损坏或超界不自动重发。

重新认证原企业owner后GET原actor/key。实际不可变事件的scope/动作/修订/周期/actor、源快照及周期SHA、Case/Run、真实历史须匹配。REVALIDATE/关闭还核对由原理由及源SHA重建的原请求fingerprint。旧REOPEN允许ignored optional SHA，完整原正文无法重建；保持实际不可变原行与历史证明，不声称管理员级篡改可被全部侦测。历史恢复要求当前READ/PREPARE及历史/当前资源READ，不要求EXECUTE/HOLD；这些写权限仍决定当前可操作性。原同actor/key锁等待在途事务；NOT_OBSERVED或锁超时不证明未提交。

COMMITTED返回原回执与单独当前视图；后续重开、资料换版、资源取消、规则或原reviewer撤权使当前无效时，历史回执仍保留。GET没有业务INSERT/UPDATE，未调用新核验、关闭、重开、取消或完成。页面核对原回执与真实当前历史后才移除句柄；身份/Case/草稿变化的迟到成功及403均不回填或清空新私有视图。未知句柄保留，不因刷新、换身份或清视图被删除。

证据在`evidence/case-lifecycle-recovery/`：310文件冻结SHA清单、实际PG/API/HTTP/Chromium JUnit、9张1200/390/320宽度截图、独立API进程重启同PG只GET证据、失败历史和独立审查。测试中的篡改由合成fixture管理员制造，运行账号的事件DELETE被实际PostgreSQL权限拒绝；未新增schema/grants。失败原日志留在私有`.runtime/lifecycle-recovery/`。

本切片不代表Case FULFILLED、正式Release/Approval、42项AT/EX、全仓、Win11、真实业务或模型验收；正式权限主体合同仍缺失。既有协作锁及可信管理员边界保持，不声称directory-at-COMMIT或外部原子性。资料包导出已完成且未重做，旧未推送Windows Job修复未迁移、未验收。
