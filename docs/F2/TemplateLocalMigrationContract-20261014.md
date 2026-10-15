# 在途合成模板修订实际采用合同

基线为已推送`adf867156fcf0b22d15a18007cf8fa3fc65f34a2`，原开发分支dev/f2-worklist-entry-isolation-20261013；root唯一共享源码/Git集成，实施/验收/页面/独审各自隔离私树。原V1§7.5/8、F3-T03/AT25–27/F2-T06定义与全局NOT_RUN不改。已有检查、选择、手工LOCK/UNLOCK、注册依赖局部ADOPT和VERIFY均复用；本批补检查选择之后的真实当前模板采用，不把审计ACK当迁移。

仅同park/template/service/version/parameter_schema/required_goals/registered steps/registry/contracts的合成修订。名称说明改变但source相同，保全部原检查；source改变且无精细来源边时扩大本Case全注册P1–P5检查失效，保旧verified快照/正文/事件。结构扩展明确UPGRADE_SCOPE_UNSUPPORTED，原checker可仍分类NEEDS_RECHECK；不偷改成通用破坏性判断或声称完整AT迁移。移除、旧Release回退、真实不兼容、非当前目标、未审、撤回或过期严格拒绝。

原/check和原选择REQUEST_RECHECK/ACK_COMPATIBLE保持原语义；新POST /api/template-upgrade/{instance_id}/apply才是真正采用。严格请求绑定expected_instance_id、target_release_id/expected_target_sha256、expected_check_sha256、expected_choice_revision/expected_choice_event_sha256、expected_plan_id/expected_plan_revision、expected_preparation_revision、expected_source_sha256和明确reason。最后一条原choice必须同scope/target/check且为上述选择；KEEP_CURRENT/旧choice不可绕过。server从原不可变consumer binding解析精确Case/Run/owner，不相信客户端自由授权。

新TEMPLATE_UPGRADE协调事件、完整新旧Release来源证明和effective binding在原PG plan JSON同事务保存，不改PG schema/Grant，不写第二个提交账本。原consumer SQLite binding/stages原字节不动；有效版本仅由PG采用链投影，旧resume不重开旧阶段。旧ADOPT指纹与事件不改，不伪造local_revision。原plan_proof/_recovery_proofs扩展严格验证新typed请求指纹、单调版本/前后链、affected/preserved及快照，损坏不能降级。source proof至少核原SAVE/REVIEW/PUBLISH列/payload/来源hash/当前头与原合同，非协作DBowner全锚重造不作安全承诺。

沿当前PG parent→dispatch→Case→engine/source lease顺序，写context一开始取原写锁，不从共享锁升级或反向engine→PG造成死锁。原owner READ/PREPARE/EXECUTE/case.create与fixture身份当前授权均保留。source lease持到PG真实commit，等待后提交前再核时钟、目标头/有效性和权限。受影响活动锁先原UNLOCK；说明零影响可保锁。取消、RECONCILING、隔离来源、LOCAL_RECORD_CLOSED与未决consumer stage拒新采用。原VERIFY逐项实际重核，不自动VERIFY/释放资源/重派/伪造接单或回执/完成Case；VERIFY检查有效target当前可用，未挂载或撤回/过期禁止当前执行但保历史读取。

GET /api/template-upgrade/{instance_id}/apply-requests/{key}仅核原PG事件与当前有权身份；同key同参原结果、异参冲突，当前目标后来不可用不抹历史。结果不明只原key GET，无证据NOT_OBSERVED不代表未提交，禁止自动重发。effective binding来自原子PG事件，避免跨SQLite-PG迁移原子性假承诺。代码回退读取未知事件可安全拒绝，不得删除既有计划/预约/接单/回执/资料/Run成功事实；不提供逆向业务效果回滚。

独立should-update/preserve：source变更→本Case全原步骤重验，说明变更→零失效，原资源集合变化仍走原local_revision P2–P5且留P1；无关Case/tenant历史保留。固定stable plan/step IDs与所有历史/资源业务效果；实际漏失效/误改/重验范围/人工介入/失败/模型调用0分别报告。必须真实owned Linux PG/ASGI，覆盖原锁等待/撤权与过期撤回、CAS同异key并发、事件失败全回滚、丢响应GET恢复、来源篡改与旧代码读取；页面用完整HTML离线NodeVM，不启动浏览器。

仅开发模拟，formal/business publication=false；不扩大正式治理/生产权限。真实模型、付费、Windows、浏览器、CI Forbidden路线、部署、生产迁移均不运行；无凭据/网络权限配置，不改main/F1/原F2受保护引用，不强推。保全部真实FAIL/ERROR与raw；导出仅独立核实的实际fixture session精确替换，独立语义扫漏。最终同SHA相关回归、全部package字节检查和归档独审后正常开发分支push，核远端/clean/未推差异。

实际独审红窗补充：旧goal-results未识别新协调事件而409，以及撤回/到期/未挂载时原plan仍静态VERIFIED，均不得签收。修复应对新事件核完整typed请求/来源/choice链，并仅在响应增加当前性投影，不在GET持久失效或删除旧核验。所有目标结果正例须读取原goal-results并核具体业务输出，不能只把计划状态VERIFIED当成果。页面热恢复必须核原typed请求全部字段及fingerprint，错误回执不解除pending。

实际事件额度边界：新来源采用前必须同时预留本次全部 affected 原步骤所需 VERIFY 事件及原人工锁 UNLOCK 额度，避免采用成功后在64上限内无法完成必需重验；不足时检查不可用、APPLY409且PG零写入。零 affected 说明修订不增加本次重验预算；已全核验63→64可用，原有其他待办仍受既有64事件上限约束。
