# 整计划替换后的明确新批准与同 Case 资源续办

基线 `f1161454fd746806fccef7ec7ac848a7bf618d25`；最终验证源码 `2dd98b67d52746dcdc3f358d2d60042cbea93909`；开发分支 `dev/f3-plan-replacement-reapproval-20261016`。本批是原产品 §7.4/§8、F3-T03 的有限工程增量。root 为唯一共享源码及 Git 集成者，候选、独测和独审隔离；正常开发分支最终交付 SHA 和同步状态以最后回执为准。

原同稳定计划来源再批准守卫与十字段协议保留。本批支持**原完整五步已核验、六目标 V4 三服务计划，经原整计划 ADOPT 产生新 plan_id 后**，用户在同 Case 明确提出并批准新用途，再走原资源交付事务和后续核验。只读预检、来源提示、can_record、旧批准及普通 rebind 都不能代替新批准；机会 IMPORT/REFRESH/IGNORE/WITHDRAW 与原局部 ADOPT 不重复实现。

## 实际办理与有限合同

实际正向链为原完整旧 P1–P5/六目标及旧资源交付 → 原当前受审新 Release/实例及逐项有限兼容预检 → 原 REOPEN/专员 REVIEW/负责人 CONFIRM → 原明确整计划 ADOPT 新 UUID → 新 P1 VERIFY → 明确 PROPOSE/APPROVE `CASE_RESOURCE_PLAN_REPLACEMENT` → 原 COMMIT、组合资源、递增 link 与 CONSUME 同一自有 PostgreSQL 事务 → 原 P2–P5 业务动作和 VERIFY → 六目标与工作清单读取。新计划重新核验五步；旧链作为历史保留。旧容量不自动释放，释放仍须原独立权限与明确动作。

新可选 `expected_previous_plan_id` 必须与 `expected_link_revision` 一起提供。独立14字段 `plan_replacement` 证明绑定紧邻旧/新计划、原 link/snapshot/旧交付上下文、两份定义、新计划初始整 ADOPT 事件与候选、明确批准 revision 和兼容性 SHA。严格嵌套类型/键集合、不可变原 link/receipt 递增历史和消费证明在写入与 GET/P2/目标读取共同核验，不能去掉 profile 或重哈希伪装成首次交付。

能力默认关闭，只有原签发的自有合成 PG fixture 显式启用 `enabled_for_plan_replacement_tests`，并要求同 Store/catalog 的原 `ServiceReleasePreflight`。它复用原 `_historical_source`、`_target`、`compare_v1`，逐一核验原 V4 所选三个服务的同 service/owner/来源族和固定 registry；在原来源租约与 PG 锁内重复读取当前目标。没有将完整只读 `_build`/can_record 的观察结论变成授权。

有限范围要求旧五步实际 VERIFIED、真实来源 SHA、原目标 verification 与恢复证明；当前原 current_sources/dependency/evidence/typed graph 必须已知且精确分区。目录绑定变化和普通业务重验可为 NEEDS_RECHECK；缺 authority、撤回/到期/取消、UNKNOWN、破坏性合同、缺失或替换服务、部分计划、未完成旧链、活跃人工锁/注记或不支持迁移均拒绝，不能靠刷新复活。原全量替换守卫不放宽，也不擦除旧人工决定以通过它。

历史已消费交付与当前可继续状态分开。后来合法 EDIT_NOTE 的原事件在批准 revision 之后，已完成交付仍可冷读；这不授权该注记直接进入新 replacement。实现亦为后来 TEMPLATE_UPGRADE 原事件保留历史读取边界，但本批未执行该实际业务探针，不转写为已覆盖。

## 同一最终 SHA 的完整相关回归

最终选择 **140 个完整相关模块、3690 个唯一 pytest 节点全部 PASS，0 FAIL/ERROR/SKIP**，新增6模块45项已计入；不是全仓。647 个源码/测试/脚本、19,446 个原 tracked 路径与 37 个 runner/selection 文件在各最终窗口前后完全一致；10,885 个前批原件字节保留。 原 3642 个实际测试标识全部保留，仅原 test_template_candidate 的一个导入期 uuid4 参数在精确函数内归一；原始两组 UUID 另存[核验](evidence/plan-replacement-reapproval-20261016/plan-replacement-root/v4/prior-node-preservation.json)。

所有133个上批完整模块原测试字节相对基线保持，并全新执行；另加6个新模块及原预检支持完整模块。窗口的 collection 与 JUnit 精确一致、节点唯一；不逐节点挑选成绩，也不将 eaa 首轮、私有候选或前批成绩迁入。原2秒恢复预算、解锁和访问规则保持。

|最终窗口|完整模块|PASS|
|---|---:|---:|
|ci-diagnostics-early|1|60|
|replacement-core|2|7|
|replacement-independent|2|30|
|replacement-http|1|4|
|replacement-chromium|1|4|
|legacy-source-core|2|18|
|legacy-source-independent|1|32|
|legacy-source-chromium|1|4|
|extra-browser|4|55|
|long-01|1|37|
|long-02|1|24|
|long-03|1|33|
|long-04|1|52|
|long-05|1|28|
|long-06|1|23|
|long-07|1|22|
|related-01|9|282|
|related-02|8|193|
|related-03|10|269|
|related-04|9|291|
|related-05|9|209|
|related-06|11|225|
|related-07|9|213|
|related-08|12|508|
|related-09|12|339|
|related-10|9|273|
|related-11|9|204|
|related-12|9|218|
|original-preflight|1|3|
|recovery-solo|1|30|


前置原诊断模块60项已计入主集合；原CI12早期预检433PASS/14原平台SKIP单列，不迁为最后检查。最终并行窗口全部结束后，原 CI 元数据12完整模块独占运行：433 PASS/14 原平台前提 SKIP、0 FAIL/ERROR；随后原完整30项恢复模块按原2秒预算独占运行。两者不与重叠集合重复相加。新冻结独审 **15纯协议 +11客户端** 各一次通过、无阻断项，与主集合重叠部分不相加。见[实际终门](evidence/plan-replacement-reapproval-20261016/plan-replacement-root/v4/final-gate.json)、[独审](evidence/plan-replacement-reapproval-20261016/plan-replacement-root/v4/frozen-review/review.md)及[完整选择](evidence/plan-replacement-reapproval-20261016/plan-replacement-root/v4/final-selection.json)。

## 原 HTML、真实 HTTP/PG 与 Chromium 边界

最终原 HTML 的 Node 机械 DOM 四模式经 native fetch→真实 HTTP/ASGI→自有 PostgreSQL，覆盖正向、资源 COMMIT 丢回执、当前403与迟到403。Node 不是浏览器。当前模式/Case/身份/选择 ABA 的受控客户端探针与真实 HTTP 分列，不将它们移植为真实浏览器负向。

|Node页面模式|native fetch|POST总数（含预览）|实际403|Python真实HTTP尾部请求|
|---|---:|---:|---:|---:|
|current_403|10|0|1|0|
|late_403|17|0|1|0|
|lost_ack|54|8|0|9|
|positive|50|8|0|9|

合计 131 次页面 native fetch；Python 控制请求单列，不混入页面计数。

已安装 Chromium 的四个有限模式为正向、COMMIT/PROPOSE/APPROVE 分别丢回执；每次原写动作一次，未知响应使用原 key 冷 GET，不自动重发。浏览器实际操作明确新批准、资源交付、P2–P5 VERIFY、六目标及工作清单；旧链、原新 Release/资料重新确认、V4/new ADOPT 和新 P1 由 Python 原产品函数与进程内 ASGI 夹具建立；页面启动后的原 reoffer/receipt/P5 REVALIDATE 才使用 Python loopback HTTP 控制。不声称全部由页面点击或全部前置经过真实网络。网络数含 assets，不能当作纯 API 数。

|Chromium模式|实际页面网络请求（含assets）|PROPOSE/APPROVE/COMMIT|P2–P5 VERIFY|页面错误|
|---|---:|---|---:|---:|
|lost_approve|63|1/1/1|4|0|
|lost_commit|59|1/1/1|4|0|
|lost_propose|63|1/1/1|4|0|
|positive|53|1/1/1|4|0|

实际 Chromium 151.0.7922.173，总网络观测 238 次。[逐请求分层与原件映射](evidence/plan-replacement-reapproval-20261016/plan-replacement-oracle/page-evidence-v4.json)。Chrome autouse helper 把 OUT 路由到外部辅助目录，窗口 manifest 所列路径未实际写入；原4份结果按窗口时间、原路径/mtime/SHA 原样复制并核对，不补写已完成窗口、不重造原件。[复制证明](evidence/plan-replacement-reapproval-20261016/plan-replacement-oracle/chromium-originals-v4-manifest.json)。

六目标只证明 `LOCAL_OUTPUTS_VERIFIED`；工作清单仍 `recorded_states_only=true/evidence_verified=false/case_goal_completed=false`，不是现实履约或 Case 正式完成。未拍本批新截图；原旧浏览器回归的本地截图保留，二进制不导出。

## 独立覆盖与失败保全

原20行设计仍保持 DESIGN_ONLY_NOT_EXECUTED；实际30节点另有[逐行有限映射](evidence/plan-replacement-reapproval-20261016/plan-replacement-oracle/formal-v4-result.json)。设计分类为 EXECUTED=3, EXECUTED_LIMITED=4, NOT_RUN=1, NOT_RUN_HERE=3, VARIANT=9；这些设计行可共享同一节点，不能相加为测试数或声称20/20完成。真实两次事务 Grant false→true ABA、目标撤回后重复目录/预检/quote/批准读取不复活、旧P1/P2完整但后续未完成的UNKNOWN拒绝均有实际节点。机会 REFRESH 命令、材料ABA、来源到期、replacement持久profile重哈希四读和更多Case组合未在这30项执行；纯合同/客户端/其他回归分列，不移植成相同变体的实际HTTP证据。

开发候选原件保留：最初缺六目标/P1–P5 边界；历史 profile/消费读取和精确嵌套 schema 补强；旧 P1/P2 不完整链曾可能被误认已知，现加真实旧五步证明及当前已知图门。夹具最初在所有目录动作之前审核材料，实际最后目标严格拒绝；改为所有目录动作后原 REOPEN/REVIEW/CONFIRM，并沿原 REOFFER/ACCEPT/新回执 SUBMIT/ACK 再 VERIFY，未弱化产品守卫、目标断言或容量规则。旧资源始终占用，新夹具使用独立时段。

首冻结 eaa2b9e 的独立完整30项为29PASS/1FAIL。最后注记历史测试的动作函数别名覆盖待比较的 `receipt` 字典，实际 API 操作成功但最终严格比较失败；仅修3行别名，七份产品文件逐字不变。仍提交新 SHA。06fd9a7 的第二完整30项仍29PASS/1FAIL：回执字典已完全相同，唯一剩余失败为纯后继注记错误期望资源交付 NEEDS_RECHECK。独立合同复核原产品与既有资源当前性测试确认精确 CURRENT 正确；修正该预期并新增实际注记全文、六目标、组合/三资源 CONFIRMED 保持断言，产品七文件仍逐字不变。b7eec40 的独测30PASS及多组长回归保留，但原 related01 完整342项为341PASS/1FAIL：原诊断白名单遗漏新18个受信任AST函数。仅登记2876→2894 IDs、旧ID零删除、schema/512KiB预算及产品/测试原样；最终2dd98b6再完整重跑140模块，最终冻结时将原诊断完整模块明确安排为前置窗口以先核元数据。上述旧分均不迁入。首轮 root 的 HTML/Chrome 各4 setupERROR，原因是 artifact mkdir 重定向与私有会话登记 os.open 使用父目录不一致；只创建新的私有父目录后重跑，源码/断言/原预算不改。首轮协调器安全停止，所有完成/中断/失败原件保留，不给 partial 窗口记完整通过。

原专用 `test_case_pg_vertical_integration.py` 的27项需原专用 profile/`pwci_writer` 与 hosted/branch/approval-only 门；前批普通 profile 的实际缺 role 失败不改写。本批在冻结前明确排除整个专用模块，不创建 role、扩 Grant 或绕门。普通140模块通过不替代专用27项，本批整体为 `LIMITED_PASS_WITH_PROFILE_GAP`。

## 原件、脱敏与归档

主档实际 2200 对 raw/export，原件 607,308,865 bytes，公开导出 607,300,358 bytes。独立最终审计 PASS：完整枚举/逐对重建/结构与残留扫描/四个独审封印/主seal和终门独立重算均通过，无漏项、额外文件或原件漂移。见[配对索引](evidence/plan-replacement-reapproval-20261016/index.json)、[主seal](evidence/plan-replacement-reapproval-20261016/plan-replacement-root/seal.json)、[独立归档终审](evidence/plan-replacement-reapproval-20261016-audit/final-archive-audit.json)。

私有会话 registry、PG/cache/tmp、截图及继承 clone 的无关资料不导出；精确候选源码白名单与全部实际尝试日志保留。XML/JSON/JSONL 先解析再仅替换已知合成会话值和 fixture repr 文本，未变文件保留原字节；每对记录 raw/export SHA、长度与替换数。独立审计自行重建相同结果、解析结构、扫描残留、核对主 seal 及 eaa17、06fd13、b7 13及最终2dd新版13项四套独审 seal；原件和私有 registry 始终不改。

## 后续关键路径

优先按10月15–22日一周目标补一个**有原始“尚未开始”证明的执行前沿**，例如旧 P1/P2 已实际核验，P3 从未分派/接单、P4/P5 从未产生业务效果。先固定 KNOWN_NOT_STARTED 与 UNKNOWN、曾有回执缺失、迟到在途的不同答案和资格证明，再以原明确新批准、资源事务、各步业务命令及 VERIFY 闭环；不能直接删除当前五步已完成门，也不能擦除旧人工决定。未知或破坏性继续拒绝。后继合法模板升级后的历史 GET 是另一个未执行验证补项；更广迁移/回退、一般语义或动态图、正式来源治理及生产批准主体仍为独立缺口。F5-T04 备份恢复属于增强阶段独立工作，不把它倒写成本批 F3-T03 完成或原首次提交的必需项。

Windows 原生及其浏览器、广覆盖浏览器、正式 AT、真实产品模型/B0–B2、现实履约与生产均未执行；远端 workflow 若不匹配本开发分支则不新增 dispatch，也不能称已运行 CI。main 与旧开发分支只读，不强推、不部署、不新增费用、凭据或安全权限、不绕访问拒绝、不调用真实模型。正常推送与最终工作树/远端差异另留实际回执。

归档审计失败史：final-v1 实际 FAIL，唯一错误为审计 helper 仍比较旧轮次 oracle cessation 状态字面；V4 原声明的状态为 `ORACLE_V4_WRITERS_STOPPED_READY_FOR_PARENT_SEAL`，source/0 active/support hash 均一致。原 helper、stdout/stderr 和[失败结果](evidence/plan-replacement-reapproval-20261016-audit/final-v1/final-archive-audit.json)保全；仅改为精确 V4 字面，不扩大状态集合。final-v2 重新完整核验所有配对及终门后 PASS，主原件与公开导出不改。[最终结果](evidence/plan-replacement-reapproval-20261016-audit/final-archive-audit.json)。
