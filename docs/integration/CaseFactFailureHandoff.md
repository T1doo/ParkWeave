# 事实用途集成失败回传（未验收）

可 fetch 分支 `dev/case-fact-integration-checkpoint-20261007`，原集成检查点 `f0df6e04038d888762d18c6c8bb02ef19fc2d791`。外部原模块 `8d9e881f1d64042d6a7dfedf0d96c00e943c7a08` 的三个文件保持逐字相同。本线负责 API/Store/UI/P1–P5 适配，模块修订仍归外线。本文记录测试观察，不授权改变安全策略或扩大迁移目标。

## 四项真实失败

四个精确 pytest node IDs：

```text
tests/test_case_fact_clarifications_integration.py::test_restored_grant_revision_cannot_reactivate_the_old_fact_decision[field_read]
tests/test_case_fact_clarifications_integration.py::test_restored_grant_revision_cannot_reactivate_the_old_fact_decision[field_write]
tests/test_case_fact_clarifications_integration.py::test_restored_grant_revision_cannot_reactivate_the_old_fact_decision[capability_read]
tests/test_case_fact_clarifications_integration.py::test_restored_grant_revision_cannot_reactivate_the_old_fact_decision[capability_execute]
```

真实原 API 创建三项断言及竞争断言，DECLARE/CONFIRM，原 REVIEW/CONFIRM 后，GET CURRENT。分别使用既有 Store.revoke_field(region,READ|WRITE) 或 revoke_capability(READ|EXECUTE) 撤销原隔离 fixture 授权，原确认 key/body 重放返回403。仅在该测试 UUID 库恢复同一授权行 `active=true,revision=revision+1`（无新增授权行），随后 GET200；在测试约L500失败：

```text
assert current.json()['state'] == 'STALE' and not current.json()['satisfied']
AssertionError: assert ('CURRENT' == 'STALE')
- STALE
+ CURRENT
```

后续未执行的断言要求 source SHA 改变、历史不变、旧确认键返回 HISTORICAL_COMMITTED_EVENT/current_decision_restored=false、新 REVIEW409且无业务写。当前 core `_sources` 摘要只有 binding/sources，未包含原 Grant revision，导致授权撤销/恢复后旧选择复活。建议摘要稳定绑定当前同owner/park/org/purpose三字段READ/WRITE六行与capabilityREAD/EXECUTE两行的原 revision、active、有效期及精确范围；不引入clock动态摘要或新权限赋予，不承诺没有修订字段的任意管理员往返变更历史。

首轮20项15PASS/5FAIL（第五是NULL测试观察元数据断言，已单案修正通过），0ERROR/0SKIP/2WARN/15.57秒。首log SHA256 `7944defd622e1cdd9e1cd6f2b21051620b46d2b067df8b7dc1a335f35508c15a`；JUnit `dccac74b3b7dfe8fbdddc77c52d6135038672670959af73a36d8341561434ede`。四项恢复测试没有弱化或删去。

## schema24/25 起点

本线 Store.migrate 原事务执行001及002–024后，以最初读取的 version<25 条件调用025，并将 newer-version 上限升25；package-data包含025。于是原 preparation_fixture/link_fixture 的新 `fixture_<UUIDhex>` 在测试开始时已是25、已经存在fact_clarifications列与两个原生event action。

外部 `test_actual_migration_025_rolls_back_all_ddl` 在这个25起点重复执行025，然后人为RuntimeError回滚；回滚仍是25，测试却预期24/列不存在/两action不存在。因此不能直接改成预期25来假称证明DDL回滚。需外线为该测试明确建立新的24起点，再在真实owner事务应用025并中止，核对24原结构、原业务及权限完整保留。

三文件回归118项实际116PASS/2FAIL/33.34秒；第二失败仅原材料复用测试末尾旧现行24断言，业务断言全部通过。本线现行25断言及未来哨兵26已更新；legacy001新fixture_UUID升级两次、旧业务保留、拒绝未来26最终单案1PASS/0.86秒。专项复跑不拼算成118项整套通过。

## 固定 lifecycle 库的隔离合同与迁移触发

`tests/test_lifecycle_diagnostics.py::test_real_isolated_local_database_scope_schema_and_role` 原测试用 `tmp_path/data` 全新PG cluster，临时loopback端口，独立postgres维护连接，新建parkweave库与parkweave_app非特权角色；finally pg_ctl fast stop清理自己的cluster。它从原 Store(owner).migrate 初始化schema，之后应用原roles.sql，调用原lifecycle.check_dsn_scope(app,app=True)及拒绝owner角色。

`scripts/windows/lifecycle.py::check_dsn_scope` 原合同同时要求显式host127.0.0.1/localhost、无service/越界hostaddr、dbname严格parkweave，以及连接后current_database严格parkweave；app用户严格parkweave_app且非superuser/createdb/createrole。没有真实旧实例、现有目录或原身份/策略变更。

外部 migration025 DO block严格 `current_database() ~ '^fixture_[0-9a-f]{32}$'`，并要求schema_version已有24。原Store loader调用025时在这个已隔离但固定parkweave的库直接RaiseException `isolated UUID fixture database required`，尚未到诊断断言。不能为了通过而放宽guard、改lifecycle安全合同或更名绕过。需明确候选安装与既有生命周期兼容的接线合同后再实现；当前适配只在受支持UUID fixture可用，未申领一般生命周期集成通过。

旧升级测试最初创建upgrade_UUID也触发同一guard；本线把**创建新测试库时**名称规范为fixture_UUID，不触碰既有库或guard，该项已通过。原诊断固定库限制仍保留且明确失败。11项首次9PASS/2FAIL/4.90秒，log SHA256 `f7475077dbdd2bcec05a6fa40bf449cbaf2795e8b767bdfedfdc1fbfb1465f9d`；JUnit `9c1bbe1c02bfa7aa2be43feafa788949885b608406c2b100a8338ec393dc3c1c`。

## 支持线复用边界

支持原commit `b3669c79afde222283bb3209b915bdb238127499` 已本地cherry-pick；三文件只提供接线说明与黑盒断言。工具自测12项不是产品验收。真实分阶段门禁必须保存原可办理前态/path/CAS/Case与Run前驱绑定；已关闭Case天然409不是事实门证据。独立新增分阶段测试正在准备。

支持辅助当前 assert_observed_invalidation 对WRITE_REVOKED要求来源SHA不变；核心如绑定授权revision，该要求与新合同不兼容，待外线确认后必须更新。EXPIRED的纯观察仍不应把clock纳入稳定源摘要。真实浏览器及最终full Linux尚未运行，完整事实集成未签收。

## 独立已交付体验范围

正常主开发分支演示提交 `6d669b2d3567b9e36db4c42a4813115d5ca18b53`：指南+诊断class IDs支持107差异PASS/4.45秒；真实browser1PASS/82.39秒/24图（静态指南9+原预建合成Case恢复15）。file://管理员阻止，固定只读HTTP卡通过；未重跑可选材料复用、不是用户冷创建、无本修订完整Linux或事实UI验收。首次精确HEAD Server隔离job CI37634237108 attempt1 completed/success，8步骤成功；Server非Win11。R4关闭/预算0，F1未签收/F2并行，正式AT/EX未跑。


本环境支持自测12PASS/1WARN/0.08秒，只计工具自身；新增4真实可办理阶段与完整恢复/准备隐私共6项实际API选择测试6PASS/0FAIL/2WARN/11.02秒。四门在变化前各从原API保存允许动作、精确CAS/hash与同Case/Run前驱，再用原事实POST改变source；每项只报告对应阶段，并用包含prep/event/plan的独立oracle验证拒绝无业务效果（仅允许明确失效观察标记）。不使用闭合事项天然409证明门禁。支持独审另发现新确认辅助未比对末项choices与提交ID/rev/fingerprint，以及历史重放未核对原decision身份；本线正在真实API测试中强化，不把工具12项算产品或完整回归。机器范围与hash见 [CaseFactIntegrationCheckpointEvidence.json](CaseFactIntegrationCheckpointEvidence.json)。


精确选择与历史重放身份已在本线真实API测试补强：末项choices的三字段ID/revision/fingerprint与实际提交完全一致，sourceSHA、决定ID/hash与原event匹配；旧key重放action/decision_ref/decision_sha等于原event，仍需当前GET。最终两项专项2PASS/0FAIL/2WARN/6.58秒，测试源码SHA256 `30511d2dd5f75ed44a78eb7966f7c051f04664b1dee2a53dd888bac61ff66073`；不与前6项或工具12项拼算完整通过。当前检查点支持UUID fixture的真实UI验证正在执行，只证明当前源码已测行为；核心三处阻塞未解，最终验收不升级。


当前支持UUID fixture的真实UI最终检查点 **1PASS/2WARN/101.01秒/21图**，171冻结运行依赖跑后字节无差异；七项权限表hash不变，启动后setup业务写入0，模型0/预算0，测试服务与PG清理。原生DECLARE/三项选择、已提交答复丢失原key/body刷新后重试；原网页POST事实追加竞争来源令STALE/五步失效，再新明确用途、原人工REVIEW/CONFIRM、资源重绑、同执行者显式重新offer/本人新ACCEPT、独立新receipt UUID/v1 SUBMIT/ACK、本地REOPEN/cycle2及五步重验；历史只读、新加载与迟响应Case/token私密清理、专员/外企业403均真正完成。两个Case在浏览器前置通过原入口建立，不是普通用户冷创建。源事实变化不改原材料，旧/新材料reviewSHA相同是正确合同，独立事实决定/sourceSHA更新、prepRev提高、旧history保留另行验证。

三次尝试保留：启动前1.83秒PATH漏已安装Node（0UI）；首次原生84.49秒18图，在第二轮完成后沿用ENG099材料变更SHA必须不同的错误harness断言失败，迟响应等剩余场景未执行；核原材料SHA合同并强化独立事实决定/来源/版本断言后最终21图通过。产品API/UI/module未为此改动。证据范围为**CHECKPOINT_BROWSER_PASS_NOT_FINAL_INTEGRATION_ACCEPTANCE**，已知四项Grant恢复失败、回滚起点、lifecycle迁移不兼容均未解决，完整Linux/最终事实主分支推送/native/formalAT尚未验收。独立图/hash审阅正在完成。


独立只读审阅已完成：21图、4报告、三次尝试与171源码hash全部0差异，页面三种视口、STALE与重新明确选择、旧回执只读及材料SHA/事实SHA分开绑定均无检查点视觉或证据阻断。结论仅 **NO_VISUAL_OR_HASH_BLOCKER_CHECKPOINT_ONLY**；四项Grant恢复RED、schema24回滚起点和lifecycle固定库边界仍阻断最终集成签收。
