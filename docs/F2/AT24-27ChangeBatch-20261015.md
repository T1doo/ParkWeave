# AT24–27 固定双 Case 变化批

验证源码 `5a7eee826564426a4c36607ac038bd61e00665d7`；开发分支 `dev/f3-at24-27-change-batch-20261015`。基线交付 `f9834d44e5ec7600848784bfaf07f88ff4cf8691`。本轮把来源变化、人工说明冲突和原办理链放进同一个固定双 Case 变化批，不另造预检入口。仅限定 Linux 合成工程证据，正式业务 AT 未签收。

## 实现和固定初态

先冻结[合同](AT24-27ChangeBatchContract-20261015.md)及独立[字面答案](AT24-27FixedOracles-20261015.json)。两个 Case 均用原六目标 TemplateConsumer 和 P1–P5，原资料审核确认、资源关联、接单、回执核对、本地记录重核及本人 VERIFY 实际完成；再结清第二 Case 带来的 owner 集合差异。各场景从相同构造规则重建原始当前有效状态。固定答案为独审写定的 20 场景、8 去重规则和 8 安全规则，与 37 个新 pytest 项单位不同，不由产品闭包算法生成答案。

原机会卡 IMPORT/REFRESH/IGNORE/WITHDRAW 沿用。实际材料 A 变化影响 A 的 P1–P5，B 全保留；原资源集合中预置未选容量变化影响双方 P2–P5、保留 P1；真实已选容量变化须重新比较、明确确认并再绑定；目录合同变化影响双方全部步骤，原绑定变化拒绝局部 ADOPT；目录 UNKNOWN 和真实查询行界溢出均单列 UNKNOWN、扩大重验并拒绝 ADOPT。

新增有界 P1 本人协调说明：编辑时服务器捕获实际两槽材料包及来源引用。后续实际来源变化形成冲突。KEEP_MANUAL 保留原说明、记录保留决定并继续待办；DEFER 同样继续待办；ACCEPT_SOURCE 由服务端复制当前实际来源全文。编辑或接受先按原规则 UNLOCK；各选择均不代替原 ADOPT、逐受影响 VERIFY 和业务办理。说明是协调注记，不是材料事实、编译合同或一般文档合并。旧聚合 VERIFY 不倒填不存在的逐槽历史。

说明事件与原机会账本同一 PG 事务，双向重建验证原请求、前缀、actor/Case/Run/plan/step/version/epochs 和精确预览。旧事件、旧缺省字段指纹和原历史不改。未解决冲突拦原所有 ADOPT 入口；携说明的非局部替换和模板应用拒绝，直到受控保全合同实施；同计划局部采纳保留原 UUID、说明与步骤。动作预算实际走到第64事件完整核验，不放宽原上限。

原 HTML 内显示实际前后正文和来源槽，显式三选项。localStorage 仅留原 key/主体摘要/对象 ID/动作/指纹/卡 ID，无 token、正文或原因。发送前存引用；丢回执后只 GET 原 key，NOT_OBSERVED 不解锁新写。精确 COMMITTED 证明加当前原计划/机会/说明重读后收口；只有后端明确、完整绑定且无业务写的拒绝证明才能释放精确本请求引用。迟到成功/403/JSON/传输失败与身份、Case、计划 ABA 隔离。

修复原六目标资源比较错误落到旧单目标摘要门的问题：仅对已采用、非新增 partial 的受支持注册计划复用原严格 P1 证明分支；原比较、权限、当前绑定、原 ADOPT/VERIFY 证明及最终确认复核保留。旧部分交付路径不改。真实已选容量场景仍使用原比较摘要和明确再绑定；原再绑定正式 Approval 尚未实现，不将本地重新关联伪称正式批准交付。

## 原 AT 条款逐项证据

| 原条款 | 固定变化与实际行为 | 实际场景/证据 | 本轮限制 |
| --- | --- | --- | --- |
| AT-24：有权企业、重复/乱序导入刷新，不外发 | 相同 key 原事件、同源新 key 不增卡、旧代重复不替换 head、未见旧代/同代异参拒绝；终止不复活；同 owner 两 Case 定位 | C00/C24，原 typed/shared 模块及新 `test_at24_fixed_two_case_duplicate_and_out_of_order_events`，真实页面手动刷新 | 无定时在线/消息外发；反查仍两来源、32候选/跨页 UNKNOWN、跨 Case 非原子 |
| AT-25：真实源规则/资料/容量变化、确定传播/未知重验，分别报告误差 | A 资料/双方可选容量/实际已选容量/目录合同/目录实际 UNKNOWN/真实行界超界；原局部 ADOPT、原办理与受影响 VERIFY；未影响 P1 锁保持 | C25五场景、另列目录UNKNOWN变体及C26混合；独立字面集合、目标/证据/清单和旧业务事实对照 | 不新增共享材料反查类型；目录绑定改变拒绝同 UUID 合同替换 |
| AT-26：LOCK_CONFLICT 原内容、未解不发布、历史保留/当前有效性单列 | 实际手动说明后源变；KEEP/DEFER/锁下 EDIT/ACCEPT 拒绝；原 UNLOCK→接受→原 ADOPT→真实 P1–P5 办理/VERIFY；替换绕过拒绝 | C26 七场景，原 API 和完整原 HTML accept/capacity 流；15 说明组件项含64事件预算 | 仅 P1 协调注记；携注记非局部替换/模板 apply 拒绝；不声称一般内容合并 |
| AT-27：不兼容定义/迁移/回退阻止、业务事实不回滚、有预检证据 | 同双 Case 原 TemplateUpgradeChecker：非法注册依赖 SAVE_DRAFT422、未审发布409；合法独立已审新版本不迁移旧 Case；删除必需目标 BREAKING_REJECTED；原 REQUEST_RECHECK409、KEEP_CURRENT 原审计后完整 APPLY409；旧 ref403且事实不回滚 | C27六场景及完整原升级页真实拒绝；旧 ServiceRelease 预检完整模块重跑 | MIGRATE422 仅 typed choice 拒绝；没有迁移执行成功证据；不新增 ServiceRelease 发布/迁移/回滚执行 |

正式统一冻结 SHA：**`5a7eee826564426a4c36607ac038bd61e00665d7`**。五个不重叠窗口合计 **90个完整相关模块、2617个唯一测试，0 FAIL/ERROR/SKIP**，不是全仓运行。原72模块完整重跑，并依据首轮失败揭示的公共入口消费者清单补充18完整模块；不延用77059旧窗成绩。

| 窗口 | 完整模块 | PASS | runner耗时 |
| --- | ---: | ---: | ---: |
| root-1-v2 | 27 | 900 | 1074.823s |
| root-2-v2 | 25 | 789 | 1184.858s |
| independent-v3 | 7 | 235 | 2043.384s |
| freeze-5a7eee8-extra | 13 | 388 | 418.264s |
| common-clear-v1 | 18 | 305 | 557.920s |

各窗实际原始collection/JUnit精确一致且唯一，五窗模块/节点并集不重叠；605个受控源码路径及原12417 tracked文件在文档/新证据提交前与冻结清单一致。根同时复核上一批归档273个私有原件hash/大小均无变化。原始命令、开始/结束UTC、before/after、源码与完整文件清单见[五窗并集](evidence/at24-27-change-batch-20261015/at24-27-root/final-regression-verification.json)，没有对本轮原始nodeid归一或删项。独审[精确新SHA报告](evidence/at24-27-change-batch-20261015/at24-27-review-v2/freeze-5a7eee8-review.md)无阻断；另20项实际页面函数NodeVM探针重新通过，0.119404s，与2617完整模块项及完整HTML流分开。

[逐AT结果与20场景映射](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-per-at.json)、[完整独测交接](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-handoff.json)、[原始精度统计](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-oracle-statistics.json)。20固定设计场景全部对应通过节点；设计场景、pytest项、观测记录、步骤对分别统计，不混为同一分母。新批35条传播记录：known27条/100应影响步骤对，保守UNKNOWN8条/40对，漏更/误更/误保留均0，无额外未声明UNKNOWN。35条记录没有locked字段，不能把0锁字段说成35条锁测试：实际已选容量两Case各自P1锁逐字保持、原预约/历史保全、原比较与明确重绑后六目标均核验，单列2例。原preflight本窗重跑known15/62对、UNKNOWN4/20对，受影响锁交集3/3、错锁0；typed8known/23对、2声明UNKNOWN/10对及另1实际UNKNOWN/5对分列；shared8known/14对和4UNKNOWN/10对分列。各组漏更/误更/误保留均0。

[41条完整HTML轨迹](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-html-summary.json)：typed6/shared9/preflight14/new12，均在本轮实际执行并核原件hash。新12严格分9真实后端响应模式与3受控客户端异常/坏DTO模式（late JSON、transport、bad UNKNOWN）；全41含5条DOM/transport负向，不称41条都为真实后端拒绝。Node捕获957个实际HTTP请求，Python test-body捕获6109个loopback HTTP请求，不声称包含全部fixture setup。原完整HTML由NodeVM/DOM替身执行，服务为真实HTTP/ASGI/自有PostgreSQL，真实浏览器仍NOT_RUN。

真实说明GET403直接before/after无业务写另列2例；5条读取前后差异观测单列，其中late_403一条有3项原invalidated字段观察差异，其余4条无变化；其他业务/历史表无变化，既有authorization_audit拒绝审计不算业务事实变化。实际已选容量的原比较/新hold/明确rebind没有省略；原第一次交付Approval保留，替代正式批准仍NOT_IMPLEMENTED。MIGRATE422仅证明封闭类型拒绝；BREAKING完整apply409有当前完整proof，superseded403不声称执行业务回滚。UNKNOWN真实行界由实际130新资源触原256 joined-row界，扩大重验且拒绝采纳；不是成功完整反向遍历。schema1实际投影/原页面parser与旧v1管理员夹具分别列证，不倒填新业务历史。


## 失败原件和有限修正

首个后端候选交接在写共享文件前被 hash 门阻止：候选写者更新过 WIP，清单与实际不同，未集成；改用不可变快照后继续。开发说明夹具原计划 GET 会持久当前 invalidated 并推进 parent xmin，旧预览正确409；仅修夹具顺序重新读预览。预算场景旧资源关联没有走原明确重绑而被原 P2 拒绝，修测试走完整原业务顺序，未绕门。

独测初次合法模板版本夹具字符串不符原格式，说明 driver 未先读机会便刷新、未读新计划便核验，替换 driver 引用不存在 revision 字段，均修新夹具；页面撤权恢复后原 GET 合法持久 invalidated 位，PG 差异断言只明确容许该原观察字段，其他原事实/历史严格相等。真实六目标已选容量新比较确实误拒绝，按上文限定原 P1 严格分支修复并在最终 SHA 复验。

新再绑定5项首窗因夹具把3个成员传给原最多2项确认而 setup ERROR，仅修新夹具不改旧上限。独审资源拒绝首窗把原 authorization_audit 写入误算业务变化，收窄断言只容许该原拒绝审计。首个正式独测启动前 runner 输出路径与 shell launch 文件冲突，未运行 testcase；保留失败启动，使用唯一新 v2 窗口从头执行。冻结前 `git diff --check` 发现新 JS 额外 EOF 空行，仅删该空行后冻结；最终 SHA 下无源码修改。所有 WIP 成败窗单列，不与正式计数相加。

首轮正式冻结 `77059b4`：root900完整896PASS/4FAIL，root789完整767PASS/22FAIL；26项集中于新增公共清理路径读取 firstChild，而34个既有DOM驱动未模拟该标准属性。原真实DOM合法，未把这些失败当业务授权失败。新实现仅把新option.value在插入前赋值，移除该公共路径多余的DOM反查，真实页面行为等价；未改任何旧测试、驱动、断言或业务门。原26精确节点实际新代码复验全部PASS，7原API/ASGI/自有PG桥接和19DOM/transport分列。随后冻结 `5a7eee8`，原72模块全部从头重跑，不延用首窗成绩；另按34个旧DOM驱动的精确消费者清单补充18完整模块305项，同一冻结SHA，五窗并集90模块，最终总项以实际collection/JUnit核验为准。

旧独测在208PASS后自有pytest一次SIGINT优雅中断，27未完成，原235 collection和部分JUnit完整保留，不称235PASS；旧独审388PASS仍仅属于77059。独审曾试验标准getter的私有候选，前2项PASS后因改选单行产品等价初始化而中断；中断JUnit的无classname合成记录导致其旧normal-only后处理停止，原件与解释保全，不计3项通过。root准备中断root2时精确PID检查为空（已自然退出），未发signal，检查失败记录保留。

## 验证与交付界限

Windows/Win11、真实浏览器、正式业务 AT、真实产品模型/B0–B2、正式来源治理与批准主体、现实产物/回执、生产未执行。完整 HTML 使用 Node VM DOM 和真实 loopback HTTP/ASGI/自有 PostgreSQL，浏览器与 DOM shim 明确区分。现有 CI 仅固定历史分支，无本分支触发则 NOT_RUN，不改旧分支或工作流强触发。模型调用0；新增费用/真实凭据/安全权限0；部署0；main只读。

下一关键路径按10月15–22日一周目标立即接续：补充保留人工内容后的受控继续采纳（本批 KEEP_MANUAL/DEFER 均继续待办，完成闭环使用明确 ACCEPT_SOURCE），在受控注记保全合同下扩展兼容升级/更一般人工内容冲突；再补一般来源传播/动态图覆盖及正式环境验收前提。破坏性迁移继续拒绝；复杂在途升级/F5-T04、备份恢复与 ServiceRelease 发布/迁移/回滚执行留待后续受控合同与实现验证，不由本批合成通过替代。

## 证据归档

主档775个raw/export配对，公开载荷50,568,287字节；原件共50,580,116字节，hash/大小全部保全。仅20处已登记合成会话精确替换、52行pytest截断fixture repr去敏；38362个登记合成值残留0。298 JSON、164 JSONL、41 XML和70 Python结构解析通过；源代码类文件未触fixture repr行掩码。根检查通过并保留待独审checkpoint，后续独立结论以链接终门为准。私有集合/数据库/cache/完整工作副本不导出；.gitattributes只在新证据目录保留原字节与日志空白，不放宽产品源码检查。

[主档索引](evidence/at24-27-change-batch-20261015/index.json)、[主档说明](evidence/at24-27-change-batch-20261015/README.md)、[根checkpoint](evidence/at24-27-change-batch-20261015/audit.json)、[独立最终门](evidence/at24-27-change-batch-audit-20261015/final-gate.json)、[独立附件索引](evidence/at24-27-change-batch-audit-20261015/final-artifact-index.json)。根checkpoint保留当时PENDING独审状态，后续结论见独立sibling，不覆盖原始失败或制造自引用。独立重构不导入根producer/verifier；known-token matcher有明确共享来源，不声称算法来源多样性。
