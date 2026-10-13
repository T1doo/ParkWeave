# 真实未决写操作与原历史面板收口

本片接续上一交付 `02fa63e3959647d28baec477c86b41c53f042bf6`，仍由根单一源码/Git写入者在 `dev/f2-worklist-entry-isolation-20261013` 正常开发。上一两个导航阻塞已由父级核实修复，但当时没有整体签收：真实人工回执和资源关联POST只有Retries，未决时总览仍能清请求键和草稿；原回执历史面板也未加入拒绝清理链。新增修复没有扩展Case业务功能或后端权限。

源码冻结 **e7ede1b41f6310cbc9bc237d584d9307b9d70797**。共享登记覆盖实际原HTTP写调用，并在原写函数/原inline handler的await链中持有操作，涵盖命令、成功后的读回挂起以及未知结果。总览导航在实际登记存在时拒绝切换，不清原Retries、草稿或句柄；登记保留原path/token/key/body的内存signature，不自动发送。已存在的memory pending和持久恢复句柄按原协议继续持有未知操作，不用新登记替代原key恢复。GET（包括FOR UPDATE）不登记；已核的资源预检/替代时段、受控计划预览、资源交付预检POST为纯预检，明确排除，不误称业务写。没有eval或新的动态代码执行。

独立新操作不能被并入正在提交的await链；仅静态原函数引用中可达的内部调用可加入原flow。写flow活跃时独立读取按钮明确临时拒绝，原命令内部读回继续，总览仍可只读展示但不能打开其他入口；这样独立历史读取的500不会锁死另一命令。未知结果结束后历史读取仍可使用。原请求已收到成功响应、但随后读取失败的情况，允许用户通过原GET入口核对后退出保护，不另发POST。

退出保护按实际行分别核对：人工回执、分派、资源关联、资料、技术Run、受控计划、诉求、规划metadata与材料评估不混用版本。原GET函数必须完成其现有权限/绑定/上下文验证，身份和业务域匹配；有原事件版本时当前同一行版本至少达到该版本。诉求只用request_intent版本，不能借同Case受控计划较大版本。规划metadata核原POST返回history的id/revision/document；评估必须核原request_key与完整canonical原record出现在新history。未知POST始终不因普通GET或新版本而释放。该内存保护不是新的冷恢复协议，也不证明现实服务完成。

原dispatchPending的顶层preparationId现在纳入opaque引用提取。当前403按已有上下文守卫清私有请求signature并保留opaque引用和既有持久句柄；HTTP403正文解析失败仍保留403状态。原receipt-history-result接入真实clearReceipts链，已渲染内容清除、在途GET世代失效；历史入口自身403也在解析正文前走统一拒绝。各原私有clear链和18组真实写入口做了有界静态核对；静态核对不计为产品测试。

根最终冻结相关 **407 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，100.91秒**；统计见 `evidence/receipt-command-navigation-20261013/results.json`。最新63项入口窗口包含42个完整原HTML模式及21个原工作队列单元/ASGI模式，属于最终相关窗口，不累加。新增12模式实际驱动4类receiptCommand、资源关联form POST的挂起/丢响应和原历史读取；未mock原导航、command、render或clear函数，只有DOM/HTTP/存储/定时器为离线double。较早的25个pending模式仍是手工状态单元，不替代真实命令验证，也不声称服务器授权或完整浏览器签收。

独立本片主审 **20原HTML模式 / 117断言 PASS，0 FAIL/ERROR/SKIP**（af5b577、capture之前），覆盖ACK/link/dispatch三阶段、未知GET不释放、原dispatch同key重试、并发和独立读取隔离、历史清理、预检可离开、intent跨row反例及readiness原record核对。随后动态capture在最终e7ede1b补审 **1模式/6断言 PASS**，20模式未整套重跑；动态通知按钮fixture先取得原GET快照、真实加载通知，再用原render形成共存面板，明确是防御fixture，不是自然冷UI全链。此前23模式/115断言发生在上一最终catch之前，随后1模式/8断言为catch补审，不能称为24模式对最终源码整套重跑；旧4 PG与这些旧窗口本片均未重跑，不加总。本片后端未改。

根有效红例12FAIL及独立新增反例原件保留。更早8/4窗口是Node等待未决导航后空退出的脚手架失败，明确区别于tick后即时断言的有效红例；部分旧单元窗口缺新entryFetch抽取double alias，原FAIL也保留。含随机合成fixture会话repr的失败日志/XML仅公开标记SANITIZED_EXPORT的导出，原件私有runtime不改。源码diff检查PASS；归档暂存diff检查实际FAIL/rc2，17份原失败日志/XML共785处pytest尾空白，原检查输出也归档，不裁剪原件。连接曾报告完整 `CreateProcess Rejected("Failed to create unified exec process: exec-server transport disconnected")`；同原exec恢复后继续，没有另开实例、换安全工具或绕过拒绝。

两安全approval仍false/null/null，不运行安全探针、不新建安全执行分支；浏览器继续NOT RUN，历史Chromium data导航ERR_BLOCKED_BY_ADMINISTRATOR不重试。原安全1PASS/1FAIL/19NOT_RUN和未知根因不变。main/F1/原F2及上一原工作队列交付分支不改；不部署、生产迁移、模型/付费调用、凭据/网络配置或扩权限。完整AT08/35冷全链及真实履约仍待后续复核，不因本片通过而签收。

后续状态：父级复核发现成功POST后语义读回失败可提前释放、普通409/422长期锁定及回执form未等待Promise三处缺口，83717交付未整体签收。已由 [SemanticReadback-20261013.md](SemanticReadback-20261013.md) 接续修复；本报告原窗口、失败证据与计数保持原样，不作为后续冻结源码的最终验证。
