# 下一独立核心会话：按 Case 用途确认冲突事实（可执行分工合同，尚未实现）

冻结基线：`9ab3c06567ec4d3ff2bcd8152008ba46c39089a5`，已经普通推送；完整 Linux 2174 PASS，首次 Server 隔离 Job CI 37626906663/attempt1 success。与体验包会话 `01a1167d-6f45-75f9-999d-7ec1cde8701d` 的新预检工具/说明分工互不重叠。

现有 `/api/facts` 保留三字段原 owner 断言，`facts.assess` 保留冲突 UNKNOWN；旧集中澄清只追加 candidate child Run，尚未形成按当前 Case 用途选择来源、失效和恢复的实际业务门。新切片仅 SYNTHETIC、当前 owner、`synthetic-material-preparation@1`、固定 `LOCAL_SERVICE_PREPARATION_FACTS_V1` / `SERVICE_PREPARATION`，固定 region/employees/service_need。结果为 USER_SELECTED_FOR_CASE / USER_ASSERTED_UNVERIFIED；资格仍 NOT_EVALUATED，不改全局断言、不裁定冲突哪份真实、不调用模型。

独立会话拥有 `src/parkweave/case_fact_clarifications.py`、候选 `src/parkweave/migration-025.sql` 和 `tests/test_case_fact_clarifications.py`。迁移新增 preparations.fact_clarifications JSONB、版本25，并为原 preparation_events action CHECK 注册 DECLARE_FACT_PURPOSE / CONFIRM_FACT_PURPOSE 两个真实动作；仅全新 UUID 隔离 fixture，禁止生产启用或新增 GRANT。独立会话不得编辑 Store/package/schema/API/web/preparation/readiness/life/er/cp 或旧测试；主线后续统一集成共享触点。另一 checkout/worktree、独立 UUID 测试库，重型全量测试由主线调度。

模块 exports：Declare、Confirm、read、declare、confirm、gate、source_descriptor、public_status。

- Declare 输入 expected_preparation_revision、expected_clarification_revision=0、固定 profile/purpose、reason。
- Confirm 输入 expected_preparation_revision、expected_clarification_revision、expected_source_sha256、恰好三个不同字段 choices（field/assertion_id/expected_assertion_revision/expected_assertion_fingerprint）、reason。禁止 actor/org/case 覆盖、新值、任意字段或 verified 标记。
- 建议主线 API：GET `/api/preparations/{id}/fact-clarifications`、POST `.../declare`、POST `.../confirm`（原 Idempotency-Key）。只读显示全部竞争来源/有效期/版本；不按时间或文件名自动选值。
- owner 当前 READ/PREPARE/EXECUTE、精确 Case/Run/case.create，以及三个字段当前 SERVICE_PREPARATION 权限；授权先于历史 key replay。原 actor-key 锁、parent FOR UPDATE、与 Store.save_fact 同键的稳定字段锁；短事务双 CAS、source SHA 复核、账本 append、preparation revision+1、置 IN_PREPARATION、review_sha256=NULL、原 prep.event 真实动作与 P1 invalidation 同事务。来源每字段至多16，账本事件/版本上限64，超限拒绝。
- DB clock 校验 `[valid_from,valid_until)`；缺失/过期/冲突/待用途确认集中展示，未选择保持 UNKNOWN。来源 SHA 覆盖排序后的真实 ID/revision/value/unit/source_ref/excerpt/validity/fingerprint 和 profile/request binding，不含动态 clock/assessed_at。来源新增、到期、request 改变或撤权令当前门 STALE；历史 immutable snapshot 和原选择不改，显式再确认追加新事件。
- 精确旧 key/body 当前授权后返回 HISTORICAL_COMMITTED_EVENT，不回写当前 active；不同 body 409；并发确认仅一个 CAS 胜者。generic preparation 读投影对所有角色移除完整 fact_clarifications 私有账本；公开事件只包含 decision_ref/hash/public_status/所需字段/本Case理由，不含源值、ID或excerpt。owner 专用GET须当前字段 READ 后才展示完整历史。JSON历史逻辑不可变，不宣称数据库append-only。

主线必须把真实 `preparation.command REVIEW/CONFIRM`、readiness、`er.material_current`、`life._sources(MATERIAL_REVIEW)`、`cp.binding_p1` 和下游办理门绑定当前 decision/source descriptor。未声明 profile 的 legacy Case 不改变；开启后不能删 profile 或字段解锁。仅有模块/opt-in 标签不算实际产品切片，也不算完整 AT06（当前仍只有 USER_ASSERTED_SYNTHETIC 一类来源）。

已核定版本/恢复合同：每个新 DECLARE_FACT_PURPOSE / CONFIRM_FACT_PURPOSE 成功事务都增加 ledger revision 与 preparation revision、清 review_sha256、置 IN_PREPARATION、失效P1并沿原 prep.event 的 UNIQUE(actor,key)/UNIQUE(preparation,revision) 写真实动作。不得伪用 ADD_EVIDENCE/UPDATE_REQUEST。旧 key 历史重放不升版本；GET观察来源变化不升版本。旧材料/evidence/offer/receipt/lifecycle 不改。事实用途新确认即使材料字节相同，也必须产生新prep revision，使ENG099回执世代约束与当前accepted context一致。

必要原 API 恢复验收：DECLARE→选择当前真实事实→原材料REVIEW/CONFIRM→P1/P2→OFFER/ACCEPT→SUBMIT/ACK→P4→本地REVALIDATE/CLOSE；原POST facts追加有效竞争来源使当前decision STALE，旧SUBMIT/newOFFER/P1VERIFY/P5CLOSE拒绝并零业务效果；owner显式再确认产生新prep revision，不能直接资料CONFIRM跳专员REVIEW；原REVIEW/CONFIRM→资源重新绑定→P1/P2→sameexecutor recovery_offer(原旧receipt step ID)→本人新ACCEPT，生成currentPrepRev>oldPrepRev的新stepUUID/newreceipt v1→SUBMIT/ACK；原本地旧CLOSED须显式REOPEN/REVALIDATE/CLOSE及P5。旧事实/offer/step/receipt/cycle全部保持，旧step新keymutation409、旧key仅历史恢复；grants/assignments逐行不变，最终Case仍WAITING_CONFIRMATION而非FULFILLED。独立模块测试与主线实际原API集成回归分开报告，未集成前不称完成产品切片。


运行边界：预算0/R4关闭，无模型/真实资格判断/外部履约，不创建真实身份、Grant、assignment，不改 owner/ACL/security，不部署、不合并 main。正式 F1/F2/AT 状态不升级。
