# AT24–27 固定双 Case 变化集：独立预期与缺口

基线 `f9834d44e5ec7600848784bfaf07f88ff4cf8691`。本文件为实施前独立设计，**NOT_RUN**，不签正式 AT 或复用旧成绩。只读参考原 `docs/分阶段开发计划.md:296–299`、`docs/平台产品设计.md §7.5/§8`。无仓库 AGENTS.md，`/workspace/.agents`为空；本任务仅新 runtime 目录写入，根唯一产品/Git集成。

## 固定初态与观测

每个变化场景从新建的共同 fixture 重建 A/B 双 Case，不把上场景变更带入下一场景。相同 owner/park/org、相同当前已审服务版本与源规则、相同六必需目标、相同 P1–P5 合同及依赖，分别通过原资料 REVIEW/CONFIRM、资源关联、接单、回执 ACK、local REVALIDATE 和本人 VERIFY 完成。两 Case 的对象/事件/材料/回执 ID 保持各自独立。原六目标字面见 fixed-oracles.json；legacy `test_case_goal_results.complete(local=True)`只有5目标，不能据它宣称原六目标初态。

优先使用同一 V4 已采用选择来源构造两 Case，以便 AT27 真正 ServiceRelease 预检沿同一初态。若用原 TemplateConsumer 六目标链，则 AT27 V4 预检必须另建明确标记 fixture，不能声称两 Case 均有 V4 消费证明。不得伪造旧候选/consumeproof。

先创建并完成两 Case，再核对双方当前 source-impact 为零受影响，全部五节点 VERIFIED，六目标结果 CURRENT/LOCAL_OUTPUT_VERIFIED、Case 仍未完成。两者共同资源集合/目录当前来源摘要必须相等；字段身份差异不删除，只在独立初态等价报告中把 A/B UUID 映射到固定标签。共享资源占用采用预先固定的互不冲突时段；真实产生的占用、接单、回执和人工决定均留历史。不能把第一 Case 完成时的快照当第二 Case 完成后的共同基线。

每次记录完整原 plan/step UUID、六目标顺序、合同正文、events/history 前缀、verified_sources、锁事件及锁快照；另独立 SQL 保存业务、权限和原 consumer/template/catalog 日志快照。UUID只从原 plan 建 `P1..P5 -> UUID` 映射。**不得调用产品 closure/impact/build/compiler 生成 expected**。实际 affected/preserved/locked 分别对字面集合比较，漏更 `expected-actual`、误改 `actual-expected`、误保留对称差、误锁对称差分列。UNKNOWN扩大不能算已知依赖精度。

读取、提示导入、刷新、预览、选择记录、局部 ADOPT 各自允许写集分列；原服务计划 GET 可能持久化失效观察，不能概称所有 GET 零 PG 写。新只读图/shared/预检 GET 按原零业务写合同核对；所有拒绝路径保留既有 authorization_audit 例外。只有原对应业务入口可修复资料/预约/接单/回执，不让采纳或决定记录代替它们。

## 原能力与本轮真正缺口

已交付：IMPORT/REFRESH/IGNORE/WITHDRAW、稳定代次/作用域去重、逐 Case actual typed 图、RESOURCE_RULE_COLLECTION/SERVICE_CATALOG_REFERENCE 两来源 shared 反查、原局部 ADOPT/VERIFY/LOCK/UNLOCK/冷 GET、有限模板升级与结构增强、有限 ServiceRelease/ParkInstance/第二园区，以及单 Case ServiceRelease 跨版本预检日志。不要重做或重列不存在。

仍缺：统一冻结的两 Case 初态、变化集和逐项独立分母；把重复乱序机会、实际影响、人工冲突处置、原采纳重验与最终历史串成新验证链；“保留人工/接受来源/暂不处理”的三选项持久处置合同。现 P3人工锁绑定既有 VERIFY 来源与协调内容，但没有任意计划正文编辑/自动合并能力；不得把仅新增标签或提示 note 宣称一般正文合并。

材料只属于其当前 Case，shared 只支持资源集合和精确目录引用。材料变化可从有权工作清单/原 Case 入口定位，但不能假称已有跨 Case MATERIAL 反查。其它类型、一般动态图/自动扫描/真实来源治理仍是范围缺口。

## 冲突三选项合同建议

固定容量集合变化，A/B 两 Case 均 P2–P5受影响，P1保留；在两 Case P1 与 P3预先显式锁定。P1为未受影响锁对照，P3为真实受影响锁。原手工 executor/offer/acceptance、锁理由与已核验来源均保留，来源只改变集合，不自动重分派。

- **保留人工**：记录“保留旧人工决定”，保留 P3锁、原核验内容和实际分配。当前来源仍不匹配，继续 LOCK_CONFLICT/未通过；不可把记录当 VERIFY，不清已失效事实，不自动 IGNORE/WITHDRAW 机会。
- **接受来源**：先明确记录意图也不能自动解锁。本人另走原 UNLOCK；解锁使 plan revision变化，旧 preview/旧选择不能直接复用。重新读取当前 proof，原明确 local ADOPT，然后 P2–P5分别原 VERIFY（且原业务前提真实满足）。原 P1及锁字节相同；所有旧人工/来源事件完整留历史。来源接受不等于授权改派或改写任意正文。
- **暂不处理**：记录当前准确冲突的延后处理，仍显示未解决/锁冲突；不得把它实现为不可恢复的 IGNORE/WITHDRAW，不得暗中ADOPT/UNLOCK/VERIFY，不得刷新复活终止卡。可随后本人重新读取最新冲突，明确新决定。

三选项应绑定 actor、Case/Run/owner范围、plan UUID/revision、step/lock事件、机会 ledger/card/generation/basis、before/current来源和epoch、preview摘要、原因、幂等key和原请求指纹。不是所有字段都必须复制正文，可保存不可变精确证明。读取历史与当前可用性分列；旧成功不是当前授权。未知/已撤回/非当前卡/跨Case/撤权/ABA/冲突指纹拒绝新选择，丢回执只原key冷 GET。

不能把新选择事件加入原 plan actions 后漏改历史白名单/指纹/goal-results/冷恢复，也不能消耗原64事件锁解锁/受影响VERIFY预留空间。若独立 journal，须专用且默认关闭/明确组合，不能复用原 consumer、cold或其它日志；若PG扩展，则迁移/源安装/严格shape兼容必须完整受测。选择记录不应自己绕过原pending门，更不能重复上片save入口包裹自拒问题。

## 服务合同和AT27边界

实际 preparation_catalog 当前source变会触发 CATALOG_CHANGED；原 local_revision 在该绑定变化下拒绝，必须原显式replacement。V4新ServiceRelease head也会失效旧capability binding。字面oracle仍可判两 Case全P需重验，但不能要求同plan/step UUID的局部ADOPT成功。显式replacement允许新plan/step UUID，旧计划完整保存在history，不是删除历史；是否执行此正向分支应先单独冻结合同。

AT27固定源合同删除原必需目标/步骤、硬映射变化或回退，预检 BREAKING_REJECTED/UNKNOWN，不发布迁移回滚。允许明确记录拒绝证据且仅新私有预检日志变化；不能把缺少MIGRATE/ROLLBACK端点的404本身当完整不兼容执行验收。使用原严格命令schema验证伪动作被拒，并与原实际checker的确定拒绝组合；所有原Case/预约/回执/consumer绑定均不变。定义回退不撤销业务事实。正式AT27和F5执行门依然分列。

## 必需负向和回归

重复同key/异参/跨Casekey、乱序旧未知代拒绝和已存在旧代DUPLICATE、无实际源变化、失效/withdraw/UNKNOWN不可采纳，刷新不复活。current READ/PREPARE/EXECUTE、owner/tenant/park/Run重验；撤权再恢复的旧proof仍拒，冷历史按各原endpoint权限合同读取，不能把全局owner撤权误当仅A受影响。

来源capacity A→B→A内容恢复但实际行epoch变化拒旧preview/cursor；plan/锁/决定变更拒旧revision。页面当前403清当前私有视图，迟到403/成功和Case或身份ABA不能清/回填新视图；所有未知结果仅GET原key，NOT_OBSERVED不证明未提交。

完整相关模块建议：保留本轮原67模块新执行，新增本片API/历史/HTML测试模块；重点补 `test_case_opportunities.py`, `test_case_opportunities_browser.py`, `test_source_change_adoption.py`, `test_opportunity_plan_adoption_independent.py`, `test_registered_local_revision.py`, `test_registered_local_revision_browser.py`, `test_service_plan_manual_lock.py`, `test_service_plan_manual_lock_browser.py`, `test_service_plan_recovery.py`, `test_case_goal_results.py`, `test_case_worklist.py`, `test_typed_source_impact*.py`, `test_shared_source_cases*.py`, `test_service_release_preflight*.py`, `test_template_upgrade*.py`、模板migration/consumer/历史以及diagnostics。按实际diff/加载依赖增减，不把摘要测试替代完整受影响模块。

冻结后独审需独立source manifest/原collection/JUnit同窗精确去重、固定字面oracle、实际完整HTML→loopbackHTTP→ASGI→自有PG，日志和失败保全；Linux合成范围与原AT状态分开。Windows/真实浏览器/正式来源治理/真实模型/业务履约/生产/本分支CI未执行缺口持续列出。


## 父级实施合同对齐补充（此前提案历史保留）

以 `fixed-oracles-v2.json` 为当前独立固定答案。新正文冲突采用 P1 owner 可编辑“人工协调说明”，非资料事实/编译合同；候选正文仅当前实际 `material_outline` 的完整 text/id/version/sha/kind/label。新增严格 plan `EDIT_NOTE|KEEP_MANUAL|ACCEPT_SOURCE|DEFER` 和精确匹配的机会 `RESOLVE_PLAN_NOTE`，同PG事务。EDIT/ACCEPT拒P1锁，KEEP/DEFER保留锁与失效并继续阻止采纳；ACCEPT需原UNLOCK后再显式原ADOPT/VERIFY。上文P3锁是旧锁/分配保留的补充对照，不是替代本轮P1正文功能。

同双Case使用原 TemplateConsumer 六目标实例，AT27接原 TemplateUpgradeChecker。合法独审发布新定义与能否用于旧Case必须分开：新定义可合法发布，删原必需目标对旧A/B仍BREAKING_REJECTED；未独审发布409、非法注册依赖422、REQUEST_RECHECK409、MIGRATE typedchoice422、旧supersededref403及完整原APPLY409分别注明真实验证层。不能把typed拒绝、404/405或前置字段错误说成执行迁移验收。原 ServiceRelease V4新head预检控制另列可选已交付profile，不能在无V4证明的TemplateConsumer里制造history。

新note审查须统一原adopt/migration gate，防无机会proof局部ADOPT或显式replacement绕过；双向note/机会事件证明防单边损坏且避免递归validator；全文超note上限明确拒绝而非截断；KEEP/DEFER仅记录决定，不能称当前来源冲突已解决。原历史无新字段的fingerprint、历史compiler dispatch和原64事件/解锁预留保持。
