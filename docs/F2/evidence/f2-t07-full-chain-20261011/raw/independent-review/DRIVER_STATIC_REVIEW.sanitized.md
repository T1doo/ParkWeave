新驱动静态审查：LIMITED_STATIC_REVIEW_DRIVER_COVERAGE_GAPS。未独立运行任何PG/API/worker/Node/浏览器测试，无新产品缺陷复現。合同A普通新Run真实权限阻断与B既有owner-only合成assignment前提分开，保留正式AT35/F2准入NOT_RUN，符合原规格和当前授权。根第一窗实际0PASS/10FAIL/0ERROR/0SKIP、exit1、406源零漂移，本报告只读其run记录和原JUnit；未将其签作独立运行，也不覆盖旧失败。

已确认生产路径与界限

新Chain使用原create_app(Store)实际HTTP、低权限Store与独立python -m parkweave.worker --once，读取真正Run SUCCEEDED/LOCAL_CASE_CREATED、VERIFIED operation和NEEDS_INPUT Case；无隔离桥或mock业务结果。assignment使用原owner.assign_status且其他权限表一致，属于setup前提，不属于业务API赋权。双槽材料补正、专员REVIEW、企业CONFIRM、明确注册计划/资源关联/本人ACCEPT、人工SUBMIT与企业反馈/ACK、local REVALIDATE/P5均调用原生产接口。记录人工动作为合成驱动，不称自然人试点或模型完成线下工作。

第一窗恢复断言

service_case_steps.recover原精简event是既有合同，字段为id/plan_id/revision/action/step_id/expected_revision/previous_plan_id/actor_ref/request_key/historical_only/current_plan，没有sources/source_sha256/fingerprint/reason/actor_id。外层还有scope/Case/Run/preparation/actor_ref/read_only/automatically_replayed。原VERIFY正文source SHA应在原提交与当前步骤核验，不通过扩大恢复投影来满足测试。根第一窗10项真实失败属于驱动对原投影整对象相等的错误oracle，原raw/trace应保持，修正后另窗同ID复验。

需补齐的有限证据

- E01_CURRENT_CHAIN_OUTPUT_PROOFS（HIGH_EVIDENCE_GAP，tests/test_f2_t07_full_chain.py:238）：Global LOCAL_OUTPUTS_VERIFIED plus count5 cannot independently detect wrong-Case/current-version output mixing. Assert outer preparation/case/run/request/plan identity; match exact goal->adapter set and each evidence UUID/version/SHA, combination/link/offer/step/executor/current receipt/version/SHA/SUBMIT+ACK IDs, current-cycle REVALIDATE event against API+owned PG reads. Assert no stale actual_output before reverify.

- E02_NOTICE_PATH（MEDIUM_EVIDENCE_GAP，tests/test_f2_t07_full_chain.py:343）：Contract T07-F old notice OPEN is absent. worker drain alone does not verify delivery/read/current actionability. GET original /api/dispatch-notices with recipient; bind exact OFFER event_id/preparation_id/dispatch_id/revision; OPEN then MARK_READ and monotonic timestamps. After Case cancellation GET/OPEN original authorized notice and assert case_cancelled=true/actionable=false, no offer state WITHDRAWN fabrication and late ACCEPT409. Include outbox/notices/projection counts or scoped PG oracle.

- E03_PREMATURE_CLOSE（MEDIUM_EVIDENCE_GAP，tests/test_f2_t07_full_chain.py:300）：T07-G promises no receipt/ACK no close; actual new full-chain test closes only after complete acknowledged business records. On same chain after ACCEPT and again after SUBMIT-before-ACK, submit original local REVALIDATE/CLOSE with current CAS/SHA and expect409/no local event/business mutation. Preserve need for P4 verification. After CLOSE assert Case WAITING_CONFIRMATION, old P5 NEEDS_RECHECK before fresh explicit VERIFY; after REOPEN assert cleared verification/current cycle2 and no current result until explicit REVALIDATE/P5VERIFY.

- E04_SETUP_ACTOR_AND_EXACT_DELTA（MEDIUM_EVIDENCE_GAP，tests/test_f2_t07_full_chain.py:108）：setup.actor='executor-a' misidentifies the assignment target as the setup authority; actual invoker is owner Store. Use setup_actor=OWNED_SYNTHETIC_FIXTURE_DATABASE_OWNER and target_executor_id=executor-a. Assert exactly one intended new assignment with exact Run/scope/active/managed_access=None and all earlier assignment rows unchanged, plus current existing role/READ. Keep all other authority tables byte/logically unchanged.

- E05_CURRENT_VERSION_AND_REVOCATION（MEDIUM_EVIDENCE_GAP，tests/test_f2_t07_full_chain.py:320）：New matrix covers cross-scope and ownerREAD only; it lacks same-chain stale preparation/resource/receipt revision plus own-role EXECUTE/PREPARE/assignment boundaries promised in contract. Either add compact same-chain cases or explicitly map exact existing regression testIDs in final38+new module scope. Own executor ACK403/owner SUBMIT403, PREPARE/EXECUTE revocation current writes403 and correct authorized historical GET; assignment revocation lateACCEPT/SUBMIT/ACK403. Old material/source/hash or receipt revision409; no admin regrant.

- E06_COLD_BOUNDARY（MEDIUM_SCOPE_LIMIT，tests/test_f2_t07_full_chain.py:290）：actual_http starts a new API object/thread in the same host process; current cold check reads only goal-results. Label API-object/Store replacement accurately. For process-cold claim start ordinary uvicorn configured_app factory in own child with same low-privilege DSN and no bridges, preserve PID/argv/exit/stdout/stderr and GET original Run/material/receipt/plan/recovery/local/goals. Do not run existing Chromium helper. At minimum read exact same IDs/version/SHA after fresh Store and assert no business writes.

- E07_CAPACITY_VERSION_ORACLE（MEDIUM_EVIDENCE_GAP，tests/test_f2_t07_full_chain.py:171）：Fixed quantity2/current revision1 holds plus occupied_peak assertions cover one resource cancellation capacity but not declared broad final-slot/version/TTL integration. Bind preview.resource_revision/current source and authoritative synthetic source. Assert both resource members CONFIRMED/current claims and exact capacity; after cancel both remainoccupied and independent whole release freesboth. Add same-chain expired hold/stale expected_revision or map precise existing owned PG concurrency/window/TTL tests; no SQLite stand-in.

- E08_RECOVERY_ORACLE（KNOWN_TEST_ORACLE_FAILURE，tests/test_f2_t07_full_chain.py:165）：Whole original command event differs intentionally from read-only recovery event projection; first10 failures must remain actual FAIL. Match exact projection id,plan_id,revision,action,step_id,expected_revision,previous_plan_id,actor_ref,request_key,historical_only,current_plan plus outerCase/Run/preparation/read_only/automatically_replayed=false. Do not demand absent source/SHA/fingerprint/actor_id/reason. Current recovery steps have no allowed_actions/source/verified_sources and must not persist observation writes.

- E09_DECLARED_CASE_SCOPE（LOW_SCOPE_LIMIT，tests/test_f2_t07_full_chain.py:89）：All valid complete cases use existing fixture-a; foreign tenants are negative actors. This is not two valid enterprise full chains. Keep scope statement precise; if two successful tenant chains desired parameterize original existing fixture-b with its own specialist/executor/material/holds and exact assignment setup, no new grant. Current AT35 once-again same-scope new inputs remains a valid finite reuse test, not broad tenant success proof.

实际通知接口建议

GET /api/dispatch-notices按原收件人读取，选择同本Case/dispatch/offer对应event_id，POST /api/dispatch-notices/{event_id}/commands，正文{action:OPEN或MARK_READ,expected_revision:原item.revision}。送达/打开/已读与履约单列。取消后有权历史OPEN仍可200，但case_cancelled=true/actionable=false，并且实际ACCEPT409；不误设OPEN本身应拒绝，不伪造WITHDRAW。

独立同链核验应读取的原表

preparations/evidence/events、runs/operations/cases、resource_case_claims/case_resource_links、组合成员/holds/组合、dispatch root/current_offer及ACCEPT event、receipt step/current_receipt/全部版本/SUBMIT+ACK event、local ledger/current cycle/REVALIDATE event、嵌入service_case_plan的当前plan/step/VERIFY event与明确request_intent，全部按Run/Case/准备事项精确连接。goal-results输出对照这些PG事实而非仅重复后端状态字面值。容量/版本/撤权负例可绑定本次完整相关模块的精确现有testID，不能从历史成绩推断本窗。

本窗限制

现冷HTTP为同进程新uvicorn线程/新Store，不是原API进程真正退出重启；如果不新增进程验证，文案须准确。跨企业仅拒绝矩阵，不是两个企业各完整成功。正式模型/模板发布/Approval生产启用/新Run访问仍缺，不建议新增权限或新产品能力。禁止browser0仍保持，不运行含Chromium的原full-process helper。未改src/tests/docs/Git、旧取消报告或证据；只写本runtime两份新静态文件。
