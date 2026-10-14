# 原人工协调申请再核对与本人明确接续

从父审有限签收08afd6e93ff975b9046be889d22f1cf2821c145e接续原产品§5.5。冻结源码 `4be0ae897229e83477d805c402da9eccc9f5a094`；企业可对当前原答复继续核对，或在本次责任结束后申请再次核对。只追加人工ledger事件，不重写旧答复、旧知悉或原key，不自动恢复责任，不是Case重开。

## 有限实施合同

原owner从WAITING_OWNER_ACKNOWLEDGEMENT或COORDINATION_ENDED明确REQUEST_RECHECK，须绑定该目标最新原答复ID、fingerprint、同一当前Case/Run/plan、ledger revision/source SHA和原因；进入RECHECK_REQUESTED。此时responsible_actor_id为空，只有待原专员另行接续的申请，原REPLY/旧TAKE不能越过接续。

原资料专员再只读核对原申请，另行TAKE_RECHECK绑定该申请ID/fingerprint及原答复ID/fingerprint、相同当前来源，才进入UNDER_MANUAL_RECHECK并承担此次责任。此有限状态只支持原本人REPLY或企业WITHDRAW；需要变更资料/诉求/计划时走原资料/计划入口，旧答复不能用于新的来源或计划。再答复产生新不可变ID，企业须对新答复再明确知悉才结束本次责任；旧答复ID不能知悉新轮次。

申请前旧ENDED仍没有责任人，仅新增明确申请入口。再次申请、接续或知悉都不证明实际阅读、答复真实性、服务履约或目标完成；始终UNSUPPORTED/PARTIAL、Case未完成、Grant/资源/原计划步骤不推进。未请求目标的隐私投影、旧计划历史和当前待办继续分开。

当前计划合法共享ledger投影原专员MANUAL_ACCEPT_RECHECK待本人接续，之后MANUAL_REVIEW_REQUEST待再核对；申请不会给原owner或专员自动接责。页面分别显示精确旧答复和新申请ID/指纹/原因，各次需明确勾选用途才保存opaque原key并提交。待办点击继续在mgRender前核代次、Case/Run/plan/revision/source/state；刷新/身份变化/迟到不能覆盖新草稿、句柄或责任。

沿原parent锁、actor key锁及等待后当前权限重核，原同key同参结果、异参409；缓存结果亦守当前权限，换计划后原key只GET核对旧事件，当前新ledger不复活旧任务。事件与状态同JSON事务，异常全rollback。取消/核对中/关闭、撤权、资料变版或换计划后拒绝新动作，有权历史保留。未引入迁移、Grant、registry、模型、通知、权限扩大或安全配置。

原32条ledger以当前权重保留收尾容量：等待知悉1、申请待接续3、再核对中2。REQUEST_RECHECK耗1并将原权重0/1替为3，需要remaining>=pending+4-oldWeight；明确接续及再REPLY均耗1、减权1；ACK/明确WITHDRAW释放本状态额度，其它目标不能占保留槽。额度不足拒绝申请，不扩大账本。其它老状态的原有限边界不宣称可自动结束全部目标。

## 原件与开发窗

两起始状态先行红窗2FAIL（新动作schema422），原log/XML/exit保留。第一次核心/旧reply绿窗30PASS/2FAIL：两旧ENDED断言仍要求allowed_actions=[]，与已授权显式再核对入口不符；只改为['REQUEST_RECHECK']，原responsible_actor_id为空、Case未完成等断言保留，不删除旧测试ID或改旧产品历史。新API36PASS、原页6+PG锁等待2专项8PASS、加权第32事件收尾实测1PASS；开发窗不与冻结成绩加总。

真实PG parent锁等待分别证明材料变版先提交时申请或接续409，保持原待知悉或申请状态，不自动接责。重复/异参、同异key并发、伪ID/指纹/版本/主体/角色、取消、读写撤权、源变化、实际换计划、事件失败回滚和旧key冷热恢复均在原API测试中验证。

实测原合成身份为template-new-enterprise-a owner及template-new-reviewer-a专员；拒绝矩阵使用对应b身份。fixture原种子权限仅为原隔离测试前提，feature全过程Grant snapshot不变。完整原HTML在NodeVM调用真实ASGI/ownedPG；六窗waiting/ended/lost_request/lost_take/cancel/late，丢响应实际POST已提交后丢弃，只GET原key、不自动重发。

根正向链及页面另比较资源九表的当前夹具行（可以为空），不宣称已有预约占用／释放容量全矩阵验收；11业务表仅独立manual ledger变化，原步骤/Run/Case字段保留。完整冻结模块/独审数量、页HTTP计数与原始证据将在下方最终验收列明。

浏览器历史ERR_BLOCKED_BY_ADMINISTRATOR与prepare Forbidden持续停止；浏览器、prepare、部署、生产迁移、真实/付费模型、全仓及Windows/native NOT RUN。原两approval与保护分支不变。

冻结根14模块 **351PASS、0FAIL/ERROR/SKIP、2WARN、297.576秒、exit0**；独立核心真实PG/API **12PASS、0FAIL/ERROR/SKIP、2WARN、13.269秒、exit0**；补充人工撤回API **2PASS、0FAIL/ERROR/SKIP、2WARN、6.246秒**，原完整HTML撤回 **1PASS、0FAIL/ERROR/SKIP、2WARN、2.136秒**。各窗分别统计，不加总旧成绩。507文件前后hash零漂移，两原approval保持同SHA256。

根模块及实际用例数：

- `tests.test_manual_goal_recheck`：45
- `tests.test_manual_goal_reply`：36
- `tests.test_manual_goal_tasks_late`：4
- `tests.test_manual_goal_tasks`：15
- `tests.test_preparation_tasks`：19
- `tests.test_manual_goal_requests`：25
- `tests.test_manual_goal_privacy`：11
- `tests.test_case_worklist`：17
- `tests.test_case_worklist_offline`：21
- `tests.test_template_full_chain`：4
- `tests.test_service_case_steps`：68
- `tests.test_template_consumer_planning`：25
- `tests.test_template_partial`：17
- `tests.test_case_goal_results`：44

新原HTML6窗均包含根45项新模块内：

- `waiting`：17断言/18HTTP/4POST，PASS。
- `ended`：17断言/18HTTP/4POST，PASS。
- `lost_request`：19断言/18HTTP/4POST，PASS。
- `lost_take`：19断言/18HTTP/4POST，PASS。
- `cancel`：13断言/8HTTP/1POST，PASS。
- `late`：13断言/8HTTP/1POST，PASS。

cancel窗为明确原Case取消的单列API测试驱动桥，不算manual页面POST。另独立人工撤回页19断言/10HTTP/1WITHDRAW POST属于补充1项，不是Case取消，不加进根页面6窗。近32容量实测证明撤回释放预留槽后另一合法目标接责可继续；旧申请GET/cache与冷opaque恢复只显示WITHDRAWN历史，不恢复任务，迟到TAKE/REPLY409。

[证据索引](evidence/manual-goal-recheck-20261014/export-index.json)，[精确统计](evidence/manual-goal-recheck-20261014/validation.json)，[核心独审](evidence/manual-goal-recheck-20261014/independent/review.json)，[人工撤回补充](evidence/manual-goal-recheck-20261014/independent/withdraw-review.json)。原件保留.runtime；导出仅fixture会话repr脱敏，失败空白和统计保留。源码到证据交付仅文档，不修改已验src/tests/scripts。

源码／报告空白检查PASS；证据归档空白检查exit2，仅保全原pytest失败log/XML尾空格，未修剪原失败原件。

最终只读归档独审PASS：51件raw/export的SHA256、字节数、唯一脱敏范围与报告统计一致；字段措辞已精确为responsible_actor_id为空；507冻结无漂移。记录保留 `.runtime/manual-goal-recheck-20261014/independent/archive-review.json`。
