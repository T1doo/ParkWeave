# ServiceRelease 单 Case 跨版本只读预检

已完成原页面预检、后端和独立私有证据记录；冻结源码 `0de44714499ff3ead538dd8dc1436e783ab8f944` 的67个完整相关模块2187项通过，另3独审探针通过。独立归档终门PASS；仅限定Linux合成范围，不签完整AT27或生产升级。

基线交付 `b2690b4316e2ca4e98c0b83ee2675db74239ccae`，开发分支 `dev/f3-service-release-preflight-20261015`。本批落实主方案 §7.5/§8、F3-T03 与 AT-27 的有界预检子集。只读 main，原六目标、P1–P5、历史、锁、授权和已有来源闭环保持。

## 实施前冻结合同

原页面入口按原 V4 已采用选择的冻结版本、实例和编译历史，比较本人当前有权的同服务、同 owner、同 template_scope 谱系的已审最新目标。普通 TemplateConsumer 或缺失旧绑定不能补造 ServiceRelease 历史，返回 UNKNOWN。旧版本的历史可验证与旧来源当前可用性分列；旧历史可读不能给目标授权。

目录、预览和恢复仅 GET。明确“记录预检证据”仅写全新专用 ConsumerRepository 私有 SQLite journal，沿用原严格 schema 与 immutable binding，不修改业务 PG、原 consumer/template/catalog journal、Case、计划、事件、锁、业务事实或权限。拒绝请求仍沿原 API 写入既有 authorization_audit，不将原拒绝审计计成业务变化。记录保留整份原预检、精确版本/hash、原计划/revision 和幂等原请求证明；丢回执只冷 GET，历史记录与当前可用性分列。拒绝证据可记录，UNKNOWN 或未知目标不可记录。

本片不发布、不迁移、不回滚、不执行、不自动 ADOPT/VERIFY；预检成功也不授权上述动作。不是 F5-T04、完整 AT-27 或生产升级验收。原共享来源反查仍只支持两种来源、最多32候选；跨页 UNKNOWN，跨 Case 非原子快照。

## 实际实现边界

源码已冻结于 `0de44714499ff3ead538dd8dc1436e783ab8f944`。原持久计划页增加明确入口：读取历史/当前目标目录→选择精确引用→只读预览→本人确认并记录证据→只 GET 原 key 恢复。丢回执不重发；完整核对 COMMITTED 后才能明确结束核对并重新预检，NOT_OBSERVED 或坏恢复引用继续拒绝新 key。localStorage 只保存原 Case/actor/key/plan/revision/摘要，不存 token、正文或输入副本。

目录没有按所选原service自动过滤目标，也未增加service_id专用标签；须人工核对Release/实例精确同谱系配对。错pair由后端拒绝并清当前私有视图，不改Case或记录预检；自动配对属于尚未实现的展示改进，不影响已验证的手动正向。

默认入口关闭，只接受与本自有合成 catalog/store 匹配的明确依赖；专用 journal 不得复用原 consumer、cold-input 或非空其它用途日志。目标目录最多16项、当前实例集合最多64项，日志全局最多64份；超界拒绝，不能按截断清单称完整。当前 PG 资料/Case/Run、目录和权限来源 epochs 与原冻结版本一同进入预检摘要，旧预览及 ABA 拒绝。mapping 等待之后及当前 Case 来源检查末尾有界复核目标期限、已审 head 和精确实例，变化转 UNKNOWN。

仅 READ 被撤回时，旧记录冷 GET 也拒绝；仅 PREPARE/EXECUTE 被撤回时，可在仍有 READ 且仍是原 owner 的范围读取历史，但 `current_available=false`，不能新记录。`current_available` 只表示旧预检在当前仍可重现/记录，不表示兼容、可迁移、可办理；BREAKING_REJECTED/LOCK_CONFLICT 的拒绝证据也可持久记录。历史证明不依赖当前编译器倒填，目标仍须通过当前已审来源和映射核对。专用 SQLite、原模板 SQLite 和 PG 不宣称分布式原子提交，最后读取后的受信管理员写入边界保留，记录不保证未来有效性。

## 字面样本及拒绝门

| 输入/变化 | 合同语义 | 实际 Case 判断及必须保留 |
| --- | --- | --- |
| 同 Release/config 无变化对照 | COMPATIBLE，NO_RELEASE_CHANGE | 无现有来源阻塞时全保留；不能算跨版本成功 |
| 同谱系已审新 head 仅标题变化 | COMPATIBLE，contract_affected=[] | 原 V4 目录绑定实变，NEEDS_RECHECK/THIS_CASE，实际P1–P5全受影响，旧正文UUID/六目标/历史不改 |
| 上项存在人工锁 | 合同语义仍单列 | LOCK_CONFLICT，原锁保持，不能以预检覆盖锁 |
| 原当前资源集合变化 | 注册传播合同决定受影响闭包 | P2–P5受影响、P1保留；未受影响锁保持；受影响锁拒绝 |
| 目标删除目标/步骤、角色/字段/资源映射不兼容或编译合同变化 | BREAKING_REJECTED 或 UNKNOWN | 不允许升级/迁移，记录明确拒绝原因不授权 |
| 目标跨 tenant/owner/park/family、撤权、撤回、失效、非最新 head、缺失、未知或坏历史证明 | 拒绝或 UNKNOWN | 不泄漏其它主体明细，不能称兼容，不能通过刷新复活 |
| 同 key 参数冲突、来源/权限/Case/计划版本变化、A→B→A | 拒旧参数/旧预检 | 幂等查原请求，当前权限重新核对；旧记录不替代当前资格 |
| 页面迟到成功/403、身份/Case/计划/选择变化、冷启动丢回执 | 世代隔离/只 GET | 不覆盖或清除新身份私有视图，不自动重发正文 |

以上为实施前冻结的验真预期；下文列出真实执行SHA、完整窗口和独立归档结果，不把设计本身当已通过。

Windows、真实浏览器、正式 AT、真实产品模型、生产、发布/迁移/回滚尚未执行；真实模型调用与新增费用均为零。

## 冻结实际结果

正式验证统一执行 SHA：**`0de44714499ff3ead538dd8dc1436e783ab8f944`**；599个受控源码路径与 Git blob 一致。四个互不重叠窗口合计 **67个完整相关模块、2187个唯一测试，0 FAIL/ERROR/SKIP**。不是一次全仓运行，不复用上批2074成绩。开始/结束原 UTC 与 JUnit 时间均保存在逐窗记录；本批实际窗口为北京时间2026-10-15 16:28–16:52，重叠窗口不能相加当墙钟耗时。

| 窗口 | 完整模块 | PASS | 实际耗时 |
| --- | ---: | ---: | --- |
| root-1-v1 | 27 | 900 | runner 1317.253s |
| root-2-v1 | 25 | 789 | runner 1418.505s |
| independent | 6 | 198 | JUnit 1298.792s |
| review extra-v2 | 9 | 300 | runner 341.165s / JUnit339.251s |

独审另列3个边界探针全部PASS，runner57.722s/JUnit55.652s，不并入2187。证明旧V4历史验真不调用当前编译器、bool图schema拒解释、schema1局部未知扩大本Case全部步骤并完整列受影响锁。独审无剩余本范围阻断；review/independent分别核对全部12078 tracked文件前后零漂移，review另核599源码+5 editable元数据路径。该旧tracked快照不声称包含随后新归档或文档提交。

本批预检字面oracle实际19例/82个受影响步骤对，其中已知15例/62对、intentional UNKNOWN4例/20对；锁交集3对单列。漏更、误改、误保留和误锁均0。原typed11例/38对和shared12例/24对在本轮六模块中重新执行，旧迹证仅复制本窗新增32文件，并核实际raw/hash/SHA，未冒充旧成绩。

本轮原HTML Node VM共29模式：原typed6/shared9，本批14。本批14明确分12条实际后端响应流，以及`pending`、`unknown_dto`两条DOM/transport负向：前者只证实发送前入口门及无phantom预检句柄，后者在真实200后注入未来DTO schema只验证页面拒绝；不能说后端接受/拒绝了原业务POST或后端生成未知DTO。其余丢回执、迟到、存储篡改也保留各自受控故障说明。HTTP/ASGI/自有PostgreSQL为实际服务，DOM由Node VM提供，真实浏览器NOT_RUN。记录5704个Python实际loopback请求、334个Node实际请求，不能据此称真实业务已履约。

每窗原始collection/JUnit精确相等且无重复；四窗模块与测试并集独立核对。仅另一次预收集的原`tests/test_template_candidate.py:136`导入期随机UUID参数不同：只在预收集比较中对该精确函数/参数形状归一，原始两ID、首次核验失败及修正脚本均保留。实际执行窗的原始节点从未归一、删减或补签。

## 失败原件与有限修正

后端首窗4PASS/16 setup ERROR：新夹具未先确认资料便P1 VERIFY，原409正确；focus首窗3 setup ERROR为原ready helper缺标准receipt fixture。只修新夹具及原办理顺序，不绕访问拒绝。完整开发21PASS后增加两项末尾expiry验证，最后3项目标窗PASS；两窗有重叠，正式证据采用本轮同SHA完整23项（含在independent六模块198中）。

独测开发API窗25PASS/1FAIL：目标模板WITHDRAW后当前源不可用沿Denied变HTTP403，尚未按预期形成UNKNOWN；精确分开当前owner/mapping权限Denied与目标source unavailable Conflict，后者返回UNKNOWN/不可记录。未改publisher权限，目标单项复验PASS；WIP运行时追加测试导致旧trace行偏移已单列说明，未据错位行号绕拒。早HTML4PASS使用未解析按钮tag的DOM，仅为旧开发证据；修DOM从完整markup解析后才强断言原安装wrapper，precision5PASS、最终开发15PASS均保留，正式14mode在当前SHA重跑。

独审两runner首次setup误读freeze键，pytest前KeyError；probe首窗3ERROR缺原conftest，且发现与首9模块窗的basetemp路径碰撞疑虑。只中断自有9模块进程，保全64PASS/exit2部分窗；换严格不同临时目录并显式原fixture加载，v2从头完整300PASS/3PASS，不拼首窗。未删未知锁或改产品。

冻结前尾部空行检查exit2被发现后，根以独立提交移除新JS尾部额外空行；功能提交`f2ff5e4`未冒充最终验真，全部正式窗口用后续`0de4471`。收口首窗因前述原import-time UUID预收集差异assert失败，保留失败JSON和原脚本，仅修runtime核验逻辑，产品及测试未改；修正后完整并集门PASS。

独立归档首个metadata前置检查因缺README停下，依赖该结果的gate也停下；根只补齐人读README，273组配对载荷/index/audit/.gitattributes未改。两停点原件保留，随后新v2独立重建；不以缺说明的初次窗口冒充通过。

## 交付与剩余关键路径

归档及独立重建门：**PASS**。主档273个raw/export配对、36,174,819字节；32处已登记合成值和72行截断fixture去敏，18673个指定合成值残留0。20XML/79JSON/57JSONL/25Python/2JS结构或原字节核对，原件/hash/大小及源码不改。独立重建不导入根producer/verifier；fast redactor有共享已验证来源，不声称算法多样性，本批另17项/200确定随机例差分验证。

[主档索引](evidence/service-release-preflight-20261015/index.json)、[主档人读说明](evidence/service-release-preflight-20261015/README.md)、[独立最终门](evidence/service-release-preflight-audit-20261015/final-gate.json)、[独立附件索引](evidence/service-release-preflight-audit-20261015/final-artifact-index.json)。独审51份公开附件3,918,047字节，另保留索引与.gitattributes；主档root audit保留当时PENDING独审的历史checkpoint，后续PASS在独立sibling，不覆盖初次日志或形成自引用。

独立审计另保留两次自身准备断言修正：旧收口脚本实际inline加载planned集合而非变量名假设；原HTTP迹证除method/path/status还含既有synthetic body/request_key/graph_sha256，按实际schema严格列白并递归拒绝凭据/header字段。仅修自己的审计脚本并保留失败原件，未改产品、测试、HTTP迹证或配对载荷。

本批只交付F3-T03/AT-27跨版本单Case预检子集；AT27规格状态保持NOT_RUN。下一关键路径是正式AT24–27固定初态/变化集与逐项覆盖、未覆盖兼容/人工内容合并和一般来源传播范围；既有同Case手动刷新→原明确ADOPT→受影响VERIFY→六目标证据/工作清单不重做。首版继续拒绝破坏性迁移；复杂在途升级/备份恢复与F5-T04、发布/迁移/回滚执行不在本片。

Windows/Win11、真实浏览器、正式AT、真实产品模型/B0–B2、正式来源治理与业务批准主体、现实产物/回执、生产均未执行或未具备前提，不能以合成记录代签。现有七个CI工作流只触发固定历史分支且无workflow_dispatch，本分支CI未执行，不改旧分支/工作流强行触发。模型调用0、无费用/凭据/权限扩展、无部署/强推/main变更；按10月15–22日一周目标继续，完成即接续。
