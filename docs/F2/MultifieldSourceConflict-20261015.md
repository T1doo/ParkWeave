# F3-T02/T03：双槽来源变更与本人修订确认

基线交付 `40092be0334a9891afcd478a9c0b1a1cfa54fe10`；最终冻结源码 `30e8a60f8bffeb5f0b41bd3abb222526127c5433`。本批为已有 Case 增加显式选择启用的双槽材料包确认，连接真实来源刷新、当前计划及版本、影响预览、本人 MANUAL 修订保全、原局部 ADOPT、必要 VERIFY、六目标本地输出核验及工作清单读取。既有 IMPORT/REFRESH/IGNORE/WITHDRAW 沿用，原六目标、P1–P5、UUID、历史及未受影响锁保持。

新材料包面板展示 B（捕获材料包）、S（当前材料包）和 M（本人正文）的实际对象与版本。GET 不启用；用户明确确认当前双槽和正文才启用。summary 变化只要求上下文确认，不复制摘要到正文；outline 变化或既有承载义务沿 exact-line 多重集规则，义务不能在后来 summary-only 确认中降级。KEEP_AND_CONTINUE 保全 M 字节，MERGE_NOTE 保全完整原 M 并满足必要目录承载。确认之后仍需原 ADOPT、办理与 VERIFY，不生成新的批准或发布权限。

新模式下任一材料槽变化或 EDIT 都要求 fresh 确认；旧 schema1 CONTINUE/MERGE、ACCEPT_SOURCE 无法隐式退出。原 v1/v2 事件解析、命令、指纹及旧模式行为保持。新 schema2/v3 封闭证明绑定实际材料全对象、来源行 epoch、当前 actor/tenant/owner/Case/Run/计划版本、最新卡片及原账本前缀，拒绝撤权、迟到/ABA、缺失 B、失效、撤回、UNKNOWN 和同 key 异参。提交失败事务回滚；丢 ACK 后只用原 key 冷 GET。合法后续办理不破坏历史证明。

## 正式验证

同一冻结 SHA 的 **97 个相关完整模块、2756 个去重有效项全部 PASS，0 FAIL/ERROR/SKIP**，不是全仓运行。

| 有效窗口 | 完整模块 | PASS |
| --- | ---: | ---: |
| root-1-v2 | 27 | 900 |
| root-2-v2 | 25 | 789 |
| common-v2 | 18 | 305 |
| backend-v2 | 8 | 254 |
| independent-prior-v2 | 1 | 33 |
| independent-new-v2 | 2 | 52 |
| review-v2 | 16 | 423 |

完整 collection/JUnit 身份唯一精确，选择按完整模块且互不重叠；617 源码路径、15418 tracked 和4个运行器辅助文件前后零漂移。此前3101份原始证据和79份原独审证据保持。[主并集核验](evidence/multifield-source-conflict-20261015/multifield-source-root/final-regression-verification.json)。

另同 SHA 的12个完整 CI 诊断消费者模块 **433PASS、14SKIP、0FAIL/ERROR**，447个完整唯一身份，单列于主97之外；14项依赖原PowerShell/原生Windows前提，保持NOT_RUN，不算已执行。补充含公开摘要、最长25个ID、分片、清理和原字节预算。主并集已有的 ci_diagnostics60项不重复计入此补充。

新独测24项、原carry28项在同一完整52项窗口全部通过。新4条完整HTML实际188次HTTP（59/71/16/42）；原carry2条实际24次HTTP，分列不合并为新样本。新闭环观察7项，要求当前六目标本地输出及完整分页工作清单，6项另逐字保持未影响Case的原计划。回执路径的P1/P2/P3及容量并集两Case的P1共5个完整锁步骤对象逐字保持。丢ACK后新VM仅用原key冷GET，当前403与迟到403/身份ABA分别测试。

known 字面矩阵18行：应影响42、应保留48，漏更/误更/误保留均0；另2行有意UNKNOWN按全5步/Case保守拒绝，不计入known精度。来源/行UNKNOWN DTO与无MANUAL不适用分别列示。40项设计映射为18限定scope PASS/15变体/7NOT_RUN，不宣称40全完成；Python API总调用数未由冻结采集器记录，不迁开发期计数。[新冻独测核验](evidence/multifield-source-conflict-20261015/multifield-source-final/independent-new-v2-analysis/validation.json)。

原MANUAL继续33项也在本SHA完整通过：8条原HTML本轮实际431请求（GET360/POST71），5次原计划机会证明采纳、25次VERIFY和5个六目标本地输出/原清单闭环。[本轮机械摘要](evidence/multifield-source-conflict-20261015/multifield-source-final/independent-prior-v2-analysis/mechanical-summary.json)。旧恢复GET的key由Idempotency-Key请求头传递，该trace未记录GET头；绑定依据原完整handler及执行observed断言，不能声称rawtrace展示了该请求头。统计分析器首次误判key位于URL的失败及修正保留，不改产品/测试或迁旧431计数。

原7个来源模块235项加新后端19项，组成独立的完整后端窗口254PASS。原41条完整HTML路径分为29条真实响应、7条真实提交后受控丢回执、5条受控客户端机械路径；不把受控客户端调用数当实际后端HTTP。分模式、known/UNKNOWN精度与锁边界见[后端分类](evidence/multifield-source-conflict-20261015/multifield-source-backend-formal/report-classification.json)。新后端19项使用旧五目标兼容夹具，六目标本地输出的主证明来自新独测fresh_chain。

补充独审另列：4 个 pytest、一个测试内的 37 个历史变异全部拒绝、29 个 VM/DTO/传输机械探针，以及一个测试内的 6 个预算分支 stub。它们不加入正式模块并集，也不冒充 37 次 HTTP 或真实 PostgreSQL 预算边界。最终同 basis UNKNOWN 使用受控 availability seam，实际 HTTP/PG POST409、冷 GET NOT_OBSERVED、计划/账本逐字不变；不冒充真实时间过期。v3→兼容 carry→EDIT→fresh 确认→再次 carry→旧 key 冷 GET 为原五目标兼容夹具补充，六目标闭环单独依据新独测。

六目标读取仅证明 `LOCAL_OUTPUTS_VERIFIED`：P1–P5 当前核验、六个本地输出及 Case/Run/preparation/回执引用一致。工作清单仍明确 `recorded_states_only=true`、`evidence_verified=false`、`case_goal_completed=false`，不把本地记录核验升格为现实证据或 Case 正式完成。

完整 HTML 使用 Node VM DOM→真实 HTTP/ASGI→自有 PostgreSQL；真实浏览器未执行。97 个相关完整模块的范围明确排除缺少原 .venv Playwright 的浏览器模块；未安装或替换解释器。Windows/Win11、正式业务 AT、真实产品模型/B0–B2、正式治理/批准主体、现实履约、生产以及无现有触发的本分支 CI 均未执行。真实产品模型调用 0。

## 失败与修正

开发阶段原件全部保留：首 smoke 的 PostgreSQL basetemp 路径错误仅修 runner；快照在旧 GET 观察失效前后不一致仅修新夹具；ADD 合法无 P1 review_sha 被新包误拒、图端点及 before_sources 可重哈希伪造、同 basis 最终 UNKNOWN 未复查是实际产品缺口，均在最终冻结前修正并验证。畸形 Unicode 由新端点返回通用 ASCII422，旧路由错误处理保持。独测旧 source-impact 超过既有 source_epochs 有界证明范围返回409，修新夹具改读原 plan.change_impact 的 UNKNOWN 并验证实际拒绝，不扩大产品上限。

UI 开发独审发现迟到403可能清除新 Case、B/S/M 不一致、Unicode codepoint/BOM、UNKNOWN 操作资格和自身刷新 busy 状态问题；最终 29 探针逐项验证。旧失败窗口、错误 runner/plugin 记录、scope 修正与有限安全重试均保留，不迁用 WIP 分数。

首冻结 `6187ed2` 的 root-1-v1 实际 899PASS/1FAIL：新增两模块共29个函数未同步原 CI 诊断白名单。仅补 `scripts/windows_ci/diagnostic-test-ids.json` 的29个实际ID，原2776个逐一保持，仍在原512KiB/3000项/256字符上限，loader、权限和断言不变。重新冻结 `30e8a60`，97完整模块全部从头；旧独测52PASS不迁。旧 backend 经一次精确自有SIGINT收口为190具名PASS/64未完成，另1无名中断占位不计有效PASS；旧 review 经一次自有SIGINT收口143具名PASS/280未运行。全部原collection/JUnit/log/before-after保持，不能将这两窗称为完整通过。最终冻结的主选择各窗均以完整窗口通过，无失败模块替代。

## 合同、归档和后续

[合同](MultifieldSourceConflictContract-20261015.md)及[40 项字面设计](MultifieldSourceConflictOracle-20261015.json)保持冻结设计输入，不用实际执行状态改写 oracle。主档1006个raw/export配对，原件114760126字节、导出114754212字节，逐项hash/大小及允许去敏转换核对。历史原件包含开发和首冻结，不以最终source_sha冒签旧执行。

[主档索引](evidence/multifield-source-conflict-20261015/index.json)、[归档说明](evidence/multifield-source-conflict-20261015/README.md)、[根checkpoint](evidence/multifield-source-conflict-20261015/audit.json)、[独立终门](evidence/multifield-source-conflict-audit-20261015/final-gate.json)。

本批仅已有 Case、P1 本人 MANUAL、双槽材料包和既有依赖图的有界确认；更一般语义冲突、任意多字段、动态图、正式替代 Approval、复杂在途升级/F5-T04、备份恢复及通用 ServiceRelease 跨版本执行/治理/回退责任仍需后续。按 10 月 15–22 日一周目标，先补更广来源变更的明确可验证路径，再补 Windows、正式 AT 与正式运行前提。main 与旧开发分支只读，无强推、部署、新费用/凭据/安全权限或访问拒绝绕过。
