# 共享来源到本人有权 Case 的有界反向定位

基线交付 `9e8080920d906613bf61f47dd9be4218b8075856`，新开发分支 `dev/f3-shared-source-cases-20261015`。产品源码冻结于 `bc4f384fa32817ddf3b332f898d59b5b994bfe2f`；最终验证提交 **`731529bc409041f255742e11756ebc4084bb9319`** 仅修 HTML 测试驱动沿原工作清单翻页。随后交付只增文档和归档，`src/tests/scripts/pyproject.toml` 相对最终验证提交零差异。

## 完成范围

原工作清单逐 Case 来源图下可手动选择“本人当前可选资源集合”或“此园区服务目录引用”，反向定位本人当前有权合成 Case；每一项明确所选源的受影响/保留分区、未知或不依赖状态，再回原逐 Case 图和办理入口。反向查询只 GET，不创建机会、刷新来源、采纳、核验或改历史。实际办理继续原手动导入/刷新→当前计划与版本预览→本人明确 ADOPT→受影响 VERIFY→原六目标证据及工作清单；原锁须原 UNLOCK，未受影响锁、UUID/正文/事件与证据保持。

新 GET `/api/preparations/{id}/shared-source-cases` 严格复用当前 READ/PREPARE、原 owner/企业/园区和合成 Case/Run 绑定。候选 LEFT JOIN 保留尚无准备/计划的 Case 为 UNKNOWN，不从已有计划反推所有 Case。资源来源身份是本人/园区/企业/固定查询语义，目录身份包括园区/原 service_id/service_version；内容 hash 和 xmin epoch 分开，不以 plan 内节点 ID 充当共享实体，不补造材料/事实旧细历史。

所选共享源传播单列 `affected/preserved`，Case 整体来源变化和阻塞另列；材料或回执独有变化不归因于未变化的资源集合。投影与游标共用 `PROJECTION_SCHEMA=1`，每项列当前图 schema/hash；只按已知 schema1 facet 比较，其它版本保守 UNKNOWN。旧 v1/v2 历史编译、采纳和恢复合同未改。

每次最多 32 个候选，每页 1–20 条（页面每页 10 条），cursor 最大 4096 字节、版本 manifest 最大 4 MiB，原各来源行版本上限保持。超过候选、manifest 或原 epoch 上限返回空明细/无 cursor/候选数未知及原因；不以截断前 32 项宣称全覆盖。页绑定起点/身份/来源范围、修订和 epoch、权限、完整候选及每 Case/Run/preparation xmin与原来源版本；变化或 ABA 拒旧页。首尾重新核对，Case 分别使用原事务/锁序，不跨多个 parent 长期持锁。不是跨 Case 原子快照；受信管理员在最后读取至 COMMIT 的既有边界保留。

候选枚举完整不等于影响全部核对；有后续页或当前为非首页均显式 `CASE_PAGES_NOT_CHECKED` / UNKNOWN。cursor checksum 非签名、授权或已读历史证明。仅起点页一次涵盖全部候选且无未知才 `all_cases_checked=true`；这只表示本次来源比较，不表示资格、事实、六目标或现实履约已通过。

页面隔离身份/起点/来源选择和世代，当前 403 清私有列表和原图，迟到响应或身份 ABA 不覆盖/清除新视图；页内旧来源、候选和 Case hash 不匹配拒绝。没有新增浏览器持久存储、后台扫描、新权限、schema 或业务写命令。原 opaque 幂等恢复、参数冲突、失效/撤回/未知来源拒绝保持。

## 冻结验证

| 实际执行 SHA | 完整模块 | 实际结果 | 时间 |
| --- | ---: | --- | --- |
| `bc4f384f` root-1-v1 | 27 | 900 PASS /0 FAIL/ERROR/SKIP | 958.756s（runner） |
| `bc4f384f` root-2-v1 | 25 | 789 PASS /0 FAIL/ERROR/SKIP | 1088.298s（runner） |
| `731529bc` independent | 4 | 123 PASS /0 FAIL/ERROR/SKIP | 451.654s（JUnit） |
| `bc4f384f` review | 8 | 262 PASS /0 FAIL/ERROR/SKIP | 197.708s（runner） |

四窗共有 **64 个完整模块、2074 个唯一测试项**，逐窗 collection/JUnit 精确匹配且窗口间无重叠；每窗受控源码零漂移。bc4 的 60 模块 1951 项与 731 的 4 模块 123 项通过逐文件证明关联，不声称相同执行 SHA。独审另列 bc4 的未来图头 schema 探针 3PASS/17.335s，实际 HTTP/ASGI/自有PG返回UNKNOWN、扩大原五步骤且保留空，未写业务/历史。

64 个完整受影响模块分为根 27、根 25、独测 4、独审补充 8；旧根 52 与独审 8 的真实执行 SHA 为 bc4，新独测 4 的执行 SHA 为 731，不能称四窗同 SHA。这不是一次全仓回归或正式 AT。独测四模块包含本批 47 项、后端 23 项和旧类型化 53 项；新完整原 HTML driver 有 9 个模式，原类型化还有 6 个模式。Node VM 提供 DOM/传输表面，HTTP/ASGI/自有 PostgreSQL 为实际服务，不代表真实浏览器。

## 失败原件与修复

初始 root UI 验证误用不存在测试路径，pytest exit4/无用例；修正路径后原两个完整 UI 模块 74PASS/6.82s。目录静态 60PASS/1.12s 是开发窗口，不重复计入冻结结果。

后端首窗 16PASS/2FAIL/75.68s：新夹具误期待 runs POST 201（实际原合同 202）、读取原 setup 回执不存在 goal。次窗 22PASS/1FAIL/82.98s：坏计划测试写 JSON 标量先被原 DB object CHECK 拒绝，未到 reader；仅改用原约束允许的缺头对象，不修改或绕过 CHECK，目标单项 1PASS/3.07s。最终完整后端开发窗 23PASS/98.36s，运行期间发生源码冻结，故仍作为开发补充，正式证据采用后续同 SHA 完整四模块窗。

独测首窗 9PASS/1FAIL/70.15s：noPrep 夹具 UUID 与字符串直接比较，仅修类型接线。分页未遍历范围原返回 AVAILABLE/null，字面合同 RED 保留，产品改为显式 UNKNOWN，目标 GREEN1PASS/3.42s。Case 与 preparation ABA 夹具后来严格还原真实 A，目标分别 1PASS/2.62s 和 1PASS/2.96s；早窗不冒充严格 ABA 证据。全部日志和 JUnit 原件保留，开发分窗不合计充当正式通过。

独审另保留受信管理员直接 SQL 破坏原计划结构的观察：保留合法 id/revision 但删除 steps 时，继承的原 typed reader 返回 generic HTTP500，无明细泄露、无业务/历史写，owner 恢复原对象后可读。受支持业务命令无法产生此形状；本片只承诺坏计划头或原校验 Conflict 的 UNKNOWN，不宣称任意 DB 结构破坏都逐 Case 容错。该单项观察只验证此边界，不计入产品 PASS 或正式模块并集。

正式 bc4 四模块首窗 122PASS/1FAIL/486.889s：HTML overflow 驱动假设起点在原工作清单首页；33 个随机 UUID Case 时起点落第二页，仅发原清单 GET，尚未调用新反向接口。只修测试驱动，通过原下一页 handler 至多 3 页查找，不改 UUID、产品或预期。确定性起点第33位、真实 HTML/HTTP/PG 临时验证 1PASS/5.257s（4GET/0POST）；其首次临时用例未载入既有 conftest 导致 fixture-not-found，原件另保留。731 正式四模块从头重跑，不覆盖首窗或拼接首窗122项。独审证明594/595路径相同，唯一改动JS只被新独测调用；旧60完整模块按原bc4窗口逐文件延续，明确执行SHA。

## 剩余关键路径与未执行门

本片只实现两类共享来源的有界、本人当前范围反向定位；不覆盖任意共享实体、一般动态/语义图、跨业务包未知传播或批量自动采纳。多页始终保留未遍历/未证明已读 UNKNOWN，超 32 候选或源版本不可界定须后续更广的有界索引/覆盖证明。下一片优先已有受审 ServiceRelease 跨版本的单 Case 只读合同差异/适用性预检，固定应改/应留/应拒答案；更广来源身份与破坏性拒绝和正式 AT24–27 变化比较分别推进；已有有限 Release/ParkInstance、第二园区冷输入、有限模板结构增强不重做。

Windows 原生、真实浏览器、正式 AT、真实模型、生产和远端 CI 均未执行；原浏览器拒绝不绕过。产品真实模型调用 0，没有部署、付费、新凭据/安全权限或 main/强推。当前精确模型不可核实仍 UNKNOWN，未传/改 model 或 thinking。既有真实资料许可/治理发布与 Approval 主体、现实产物/回执、参赛模板/视频/提交授权及第二作品状态仍需各自真实前提。按 10月15–22日一周目标继续，工程 PASS 不代外部门签收。

## 独立答案与证据入口

731 同窗共享来源字面 oracle 12 条、expected/actual affected 24 对，漏更/误更/误保留均 0，4 条未知单列；原来源图 oracle 11 条、38 对同样零漏误，3 条未知单列（其中 2 条故意扩大）。未知扩大不计作精细影响准确率。15 条原 HTML 模式为新反向 9 条、旧来源图 6 条，正向及丢回执仍只有本人明确的原 POST，冷恢复只 GET，不因反向提示自动采纳。实际 Node 请求记录与 Python HTTP 记录分开，不冒充独立测试数。

主证据含全部成功/失败日志与JUnit、原件/导出 hash 和大小、源码清单、595文件逐项证明、字面答案及HTML轨迹，私有合成会话值集、PG/缓存排除。见[证据索引](evidence/shared-source-cases-20261015/index.json)、[分窗覆盖](evidence/shared-source-cases-20261015/shared-source-cases/final-coverage.json)、[源码延续](evidence/shared-source-cases-20261015/shared-source-cases/source-continuity.json)、[最终源独审](evidence/shared-source-cases-20261015/shared-source-cases-review/final-source-review-731529bc.json)和[最终独测](evidence/shared-source-cases-20261015/shared-source-cases-independent/freeze-731529b-formal-result.json)。最终归档审计见下方独立附件。

## 最终归档门

主归档 **259 对原件/公开导出、25,396,224 字节**独立重建一致；8 次指定合成会话值精确替换、18 行夹具展示去敏，原始文件未改。16,164 个指定合成值残留为 0；25XML/71JSON/48JSONL/18Python/2JavaScript 的结构、测试身份/状态与语法均通过。最终独审 PASS，限定范围内无剩余阻断；原失败和受信管理员500边界未隐藏。

独立审计在单独 sibling 归档，见[附件索引](evidence/shared-source-cases-audit-20261015/index.json)、[最终门报告](evidence/shared-source-cases-audit-20261015/final-gate.md)及[详细审计](evidence/shared-source-cases-audit-20261015/archive-independent-audit.json)。主归档 audit.json 的“等待独立重建”是根侧历史检查点，最终结论由上述独立附件给出，不修改主 index 以自证。源私有注册表、PG/缓存不导出；重建算法的快匹配辅助函数共享来源明确披露，独立结构重建不导入根 producer/verifier，慢参考17项差分与200随机案例另列，不算产品测试。
