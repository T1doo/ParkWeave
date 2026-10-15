# F3-T03 / AT-26：保留人工正文后的受控继续

基线交付 `7cfb1336bbfbf856c37808a66ec6f00067b6f966`；本批验证源码 `14bc83f241149bd03907bd088a35eb6df53ba0a2`。原六目标、P1–P5、UUID、历史、业务事实与未影响锁保持。同 Case 原手动来源刷新和原计划 ADOPT 保持，新增的是人工协调正文冲突后的明确继续决定。

原页面同时展示历史真实来源 B、当前人工正文 M、当前真实来源 S，逐条展示缺失的当前来源原文行与次数。KEEP_AND_CONTINUE 仅保留现有 M，MERGE_NOTE 需用户给出完整稿且连续逐字保留 M。缺当前来源条件时必须先沿原合法 EDIT_NOTE 编辑，再重新预览并明确继续；原 P1 锁需沿原 UNLOCK。KEEP_MANUAL 与 DEFER 均继续待办。当前来源为 UNKNOWN、失效、撤回，B 无法从实际历史复证或相关权限失效时拒绝；刷新不能恢复已失效的来源。

原文承载采用精确非空行多重集（1–128 行），不推断语义、业务义务、事实、资格、履约或目标满足。继续正文仍为 MANUAL，不签成 SOURCE 或新证据；继续之后的任何 EDIT_NOTE 都必须重新预览和确认。随后沿原同计划局部 ADOPT、实际业务操作、全部受影响 VERIFY，到六目标证据及工作清单读取。

绑定当前 actor/Case/Run/plan/说明修订、B/M/S、机会账本、版本与 epochs；跨租户/owner/撤权/迟到/ABA/同键异参拒绝。未知 POST 沿原 opaque handle 冷 GET，不自动重发，不在恢复引用存正文、原因或 token；页代次与身份变化隔离旧响应。

## 验证范围与边界

同一冻结 SHA 的 **92 个完整相关模块、2666 个唯一项全部 PASS，0 FAIL/ERROR/SKIP**，不是全仓运行。六窗模块及节点并集不重叠，实际 collection/JUnit 精确一致；608 个源码路径和13,252个受控文件零漂移，上一交付1,048份原始证据保持。

| 完整窗口 | 模块 | PASS |
| --- | ---: | ---: |
| root-1-v2 | 27 | 900 |
| root-2-v2 | 25 | 789 |
| common-v3 | 18 | 305 |
| formal | 7 | 235 |
| manual-independent-v2 | 1 | 33 |
| freeze-14bc83f-extra-v2 | 14 | 404 |

[最终六窗并集](evidence/manual-content-continuation-20261015/manual-continuation-root/final-regression-verification.json)、[新独测验证](evidence/manual-content-continuation-20261015/manual-continuation-independent-formal-v2/manual-independent-v2-validation.json)、[冻结独审](evidence/manual-content-continuation-20261015/manual-continuation-review-formal-v2/frozen-source-independent-review.md)。首次冻结、开发焦点和失败窗口不迁入本轮分数；设计、测试、传播记录、步骤对、HTTP请求和闭环分别计数。

原完整 HTML 经 Node VM DOM 驱动，连接真实 HTTP/ASGI/自有 PostgreSQL。不是实际浏览器、Windows 或正式业务 AT。真实模型/B0–B2、正式治理与批准主体、现实履约、生产和本分支 CI 均未执行；模型调用0。未部署、未改 main、未强推、未扩费用/真实凭据/安全权限。

## 剩余关键路径

本批新增范围限 P1 协调正文受控继续。既有两类共享反查、有限合成 Release/ParkInstance、第二园区冷输入及有限模板前向增强已交付，继续保留。剩余为携注记兼容升级保全、更一般的语义/多字段冲突、一般来源传播与动态图、正式替代 Approval、复杂在途升级/F5-T04、备份恢复，以及通用 ServiceRelease 跨版本发布/迁移执行、正式治理和回退责任闭环；这些通用/正式范围仍是缺口。共享反查仍有两来源/32候选/跨页 UNKNOWN/跨 Case 非原子边界。按10月15–22日一周目标，先补兼容升级时正文保全及更广来源传播的可验证闭环，再推进正式运行前提。

## 失败保全与有限修正

最初文件清单读取没有使用 NUL 分隔，中文路径被 Git 引号编码；改用 `git ls-files -z`，发生在业务源码变更前。候选集成按不可变路径和逐文件哈希门进行，原候选、开发窗口和收据保留。

开发阶段 API 夹具曾对 READY 材料错误执行原 REOPEN，且把原 PreparationCommand 的外层空白规范化误当本模块逐行条件行为；仅修新夹具，保留失败。完整 HTML 首次运行暴露误加在原机会计划预览中的 `renderPlanSourceContinuation(v,box)`，该作用域没有 box；移除误调用，原函数恢复逐字旧实现，原失败 HTML 输入和修复哈希保留。独审实际来源最终重读发现 basis 变成 UNKNOWN 后 TypeError/500；产品修复为原 Conflict 拒绝，冷 GET 为 NOT_OBSERVED，实际目录 UNKNOWN 和受控 reader Conflict 均重跑且业务零写。

首个正式冻结 ef16：根900与789全部通过；公共18模块首轮282PASS/23FAIL，均是历史硬编码测试输出目录未准备导致 FileNotFoundError，未变产品或断言，以审查过的16测试输出前缀重定向后305全过。新33独测29PASS/4FAIL，均为新夹具对 UNKNOWN nullable 投影或已失效P1合法LOCK的错误前提；修为真实 owned-PG 行变化再恢复、精确旧请求409与业务零写，未放宽拒绝。旧7模块在214PASS后仅对自有pytest发一次SIGINT，21未执行；原日志/JUnit与完整前后hash保留，并标记被测试修正版替代。

仅两个新增独测文件构成 ef16→最终冻结的 Git 差异，产品源码全部字节相同；最终92模块全部从头重跑，历史成功不迁入新成绩。输出重定向只作用测试 OUT 和16个固定测试证据目录，不改断言、原业务调用、身份、权限或 PostgreSQL 状态。计划 ABA 的 owned-PG 故障注入不冒充合法业务编辑；临时变化期间不执行业务命令，恢复完整行后再验证原请求拒绝。

新增33项独测的实际设计映射为23命名场景、8变体覆盖、1仅夹具路径和14本模块未执行；46设计数不是46完成，也不能用别窗测试数量补齐。独审另有逐项PARTIAL/NOT_RUN表。新8完整HTML捕获431次真实HTTP，Python test-body另捕获498次（不声称包含fixture setup）；5个六目标闭环中4保持MANUAL、1明确ACCEPT_SOURCE。lost_choice/lost_adopt均实际提交后由客户端丢响应再冷GET，2次真实说明GET403有直接无业务写快照；整个授权流程的原观察读取可能持久invalidated字段，因此不声称全流零写。

新known影响观测14条/35受影响步骤对，漏更/误更/误保留0。没有新UNKNOWN影响传播样本，故该精度NOT_MEASURED；另有4个继续资格UNKNOWN拒绝node，分母不同。P1锁下新动作拒绝及原UNLOCK后成功、P3锁下原ADOPT拒绝的直接证据，与无锁字段的传播观测分列。补充独审10个pytest项中2个成功回执夹具承载48项内存篡改检查，48不是HTTP测试数；另4项新冻结页面函数VM探针不混进完整模块计数。

原7完整模块235项本冻结重新通过，41条原HTML=typed6/shared9/preflight14/固定双Case12，957条页面test-body fetch记录（不含Python fixture/setup与control请求，fixture总数未计）；29真实后端响应、7真实提交后受控丢回执、5受控客户端负向分列。加本批8条共49条完整HTML轨迹，不能称全部是真实后端拒绝或真实浏览器。

原77条传播观测按记录/受影响步对：typed known8/23、声明UNKNOWN2/10、额外UNKNOWN1/5；shared known8/14、UNKNOWN4/10；preflight known15/62、UNKNOWN4/20；固定双Case批 known27/100、UNKNOWN8/40。各类漏影响/错影响/错保留/漏保留0，UNKNOWN不并入known精度。preflight19条含锁字段、期望锁交集3对/错0；选中容量A/B两Case原P1锁逐字保留及六目标闭环另列。其他传播行没有锁字段，不能宣称其有锁精度。详见最终[原来源窗口摘要](evidence/manual-content-continuation-20261015/manual-continuation-backend-formal-v2/report-summary.json)。


## 合同与归档

[受控合同](ManualContentContinuationContract-20261015.md)与[46项设计输入](ManualContentContinuationOracles-20261015.json)逐字保留；输入仍是NOT_RUN_DESIGN_ONLY，实际逐项执行映射见独测/独审证据，未统签46完成。

主档1079个raw/export配对，原件91,500,437字节，导出91,483,152字节；hash/大小精确，原件未变。登记合成值残留0，结构解析通过。根checkpoint不替代独立终门；精确去敏计数、共享matcher来源及排除范围见索引和audit。

[主档索引](evidence/manual-content-continuation-20261015/index.json)、[说明](evidence/manual-content-continuation-20261015/README.md)、[根checkpoint](evidence/manual-content-continuation-20261015/audit.json)、[独立最终门](evidence/manual-content-continuation-audit-20261015/final-gate.json)。
