# AT-26 固定人工锁与历史事实：有界工程验收

基线：527afdccba9fdba2ec81b42a0141b4b152fc8c60。原规格为 V1 平台产品设计 §7.5/§8、分阶段开发计划 AT-26，以及 AT24-27FixedOracles-20261015.json 中 C26_KEEP_MANUAL、C26_DEFER、C26_ACCEPT_WHILE_LOCKED、C26_EDIT_WHILE_LOCKED、C26_ACCEPT_AND_REVERIFY。literal oracle 不从产品依赖算法生成。

隔离初态复用 two_cases：已有授权 Linux owned synthetic PostgreSQL、原 HTTP/ASGI、独立 SQLite 模板/消费者，两 Case 同园区同组织同 owner，各六个原目标、五个稳定步骤、真实本地输出 VERIFIED。随后 A/B 均原 EDIT_NOTE 保存 N0、原 P1 LOCK；M0 为当时真实 material_outline 的原锚点。N0 固定为 `SYNTHETIC AT26 人工原文第一行\n第二行：保留全部内容、标点与方法决定。\n`。记录完整 note/lock/events/verified_sources 与业务快照。

只对 A 经原 REOPEN、ADD_EVIDENCE 写 M1：`SYNTHETIC AT25 actual revised material outline version two`，B 不变。经原 IMPORT/REFRESH 获取新卡。A 字面期望受影响 P1–P5、B 全保留。A 当前 P1 必为 LOCK_CONFLICT，历史成功 VERIFY 与完整 N0、旧证据和锁仍在；B 当前 VERIFIED。

有界顺序：锁下 EDIT_NOTE、ACCEPT_SOURCE、VERIFY、proof-bound ADOPT、原 proofless ADOPT 均拒绝且无业务写入；KEEP_MANUAL 与 DEFER 分别经新读取显式发生，保留原文和锁，仍不得采纳。原 UNLOCK 单独发生且不验证；未解内容冲突仍拒绝采纳。原 ACCEPT_SOURCE 仅将完整实际 M1 复制到附注，仍是 ACCEPTED_AWAITING_RECHECK；新预览后显式 ADOPT，再原材料 REVIEW/CONFIRM、资源重关联、重发并接受、真实 synthetic report/ack、本地 REVALIDATE，各自 P1–P5 VERIFY。每个阶段保存当前状态与历史事件，最终六目标 LOCAL_OUTPUTS_VERIFIED、case_goal_completed=false。B 锁定初态逐字不变，A 原 UUID/目标/事件前缀/旧证据保留。

最多一个新增固定测试、一次开发窗口和修复有因失败后的冻结复验；实际请求由现成 fixture 记录。无新模型/浏览器/Windows执行，无生产库、owner/DACL 或原生026–032动作，不变更授权边界、协议、预算或上限。原正式 AT-26 仍 NOT_RUN；结果仅为 Linux synthetic HTTP/ASGI 工程证据，不能合并旧窗口或 collection 冒充完整产品验收。发布边界只核对旧 Release/consumer 无写，不声称 AT-27 发布验收。

独审设计结论：复用原固定 C26 语义；本片 N0 和真实每 Case M0 与 20261015 设计示例字面不同，不宣称旧设计示例逐字执行，不改旧 oracle。冻结状态在两 Case EDIT/LOCK 后，避免误用 fixture 更早 baseline。模板发布 SQLite 与消费者库一起保持原样，冲突状态当前 goal-results 不得冒充已验证；GET 的合法 invalidated 观察写与拒绝命令无写分开核对。原 runner AT26 原无 selector；本轮若接线，仅允许此工程 selector，whole_status 必须仍 NOT_RUN。
