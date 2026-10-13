# 原页面工作队列入口隔离修复

后续状态：父级核实本报告的两个原阻塞已修，但随后发现真实人工回执、资源关联未决写和原历史面板遗漏，因此本交付当时未整体签收。补修与实际新复验见 [真实未决写操作收口](ReceiptCommandNavigation-20261013.md)。本报告独立23模式/115断言为最终catch之前的窗口，1模式/8断言为随后补审，不是24模式对最终源码整套重跑。

本片从 `53958532b97eca3b92e0a30bb3cb045e65d43519` 创建正常独立分支 `dev/f2-worklist-entry-isolation-20261013`，解决父级在真实原入口链发现的两项阻塞。原交付的365项相关测试及导航double不能证明这两项已经通过；本报告以新的完整原HTML脚本测试和实际PG窗口为依据，不追认旧集成验收。

真实Run `apiCall` 的当前403现在在解析正文前处理：清除资料、回执、Case、计划及资源私有视图，推进各原上下文世代，显示权限失效；旧上下文响应不能清理新身份视图。原资料、分派、回执和Case调用的JSON异常保留已知HTTP状态，导航链仍能执行403清理。读取工作队列的403也在正文解析前处理。

工作队列进入原办理入口前，先检查现有写操作、恢复核对和明确提交中的状态。有未决状态就留在原入口，不清pending、正文或句柄，不另发请求；纯读取则通过真实原clearers使旧读取在render之前失效。资料A迟到不能覆盖当前回执B或Case B。沿用原GET入口和各服务端守卫，不新增业务POST。

强制撤权清理前保留memory-only原操作的opaque kind/id/key，并保留原持久句柄，页面内Map不淘汰未知请求引用；清除敏感正文、原因和token，既有持久恢复句柄不删除。这些引用不授权重放、不自动发送，也不构成新的冷恢复协议；memory-only引用的存续范围仍为当前页面。

后端只读事务显式设置 `READ COMMITTED, READ ONLY`，避免连接默认RR/SERIALIZABLE使授权锁等待后继续使用旧快照。业务元数据仍来自同一条SELECT。UUID分页是每次GET的有界状态视图，各页之间不是固定快照；插入较小UUID需显式刷新第一页，不声称完整实时总览。

源码冻结 **0ef58b3bb0c260a698185aeb55648df190d332b6**。根最终相关 **395 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，107.05秒**。精确统计与冻结hash见 `evidence/worklist-entry-isolation-20261013/freeze.json` 与 `results.json`。根最终相关窗口包括原9个模块和新30个完整脚本模式；前置51PASS窗口及历史窗口不累加。完整脚本执行真实apiCall、loadPreparation、loadReceipt、loadLocalCase、render和clear函数，仅DOM/HTTP/存储/定时器是离线double。25个pending模式对真实全局状态作合成设置，不能当作实际POST全链验收；两个迟到资料模式使用成功的B响应并确认B继续显示。

独立审查分列：23完整原HTML Node模式/115断言PASS，补充异常JSON Case入口1模式/8断言PASS；4真实owned PG PASS，覆盖默认RR/SERIALIZABLE×身份/PREPARE撤权，观察实际pg_stat_activity Lock等待及有效read committed。旧窗口不重跑，不将独立断言与根pytest用例相加。独审有限通过，无剩余本片blocking。

根修复前有效红窗 `red-confirmed` 为3FAIL，覆盖原Run403和两个迟到材料render。更早两个红窗含DOM脚手架缺项，原件保留并明确区分；独审JSON403、遗漏pending、真实runId和memory-only事实key反例也原样保留。补充Case解析异常的负控是移除该catch补丁的内存counterfactual，明确不是历史源码实跑。所有归档原件按字节与SHA核对；不裁剪失败输出或改写FAIL为PASS。源码diff检查PASS；归档暂存diff检查实际FAIL/rc2，仅六份原pytest失败日志/XML的48处尾空白，检查原输出随证据保留。

两份安全approval仍false/null/null，未运行准备探针、未创建新安全执行分支。原安全实测1PASS/1FAIL/19NOT_RUN及未知根因不变。历史Chromium data导航ERR_BLOCKED_BY_ADMINISTRATOR保留，本片不启动浏览器或换工具重试；真实浏览器、Windows、部署、生产迁移、模型/付费调用、现实履约及完整AT签收均NOT RUN。main、F1、原F2及上一交付分支不修改。

下一步由父级复核本次两个集成阻塞的修复，再推进原F2-T06/T07 AT08/35冷全链；本片不宣称完整Case生命周期或解除独立安全/浏览器门。
