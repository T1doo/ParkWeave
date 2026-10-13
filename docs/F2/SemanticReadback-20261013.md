# 原写入语义读回、普通拒绝与表单未决保护

本片接续交付 `83717e3e0342c0f4a083a75d50c2186209e49813`。父级复核确认上一版尚有三处缺口：资源关联POST成功后，两次GET虽均200但资料版本不一致，内部catch吞错后登记提前释放；普通回执旧版本409和空理由422长期成为未知结果；receipt-submit表单未返回原Promise，普通receipt-list可清未决草稿和请求键。上一版未整体签收，本片没有扩展Case业务范围或后端权限。

冻结源码 **054d693efe173870da14eff6ed7c6177401734ce**，由root唯一源码/Git写入者在 `dev/f2-worklist-entry-isolation-20261013` 正常提交。写登记在原await链中完成语义读回才释放：业务域、身份、绑定ID及原版本/原事件历史证明都须匹配；原内部读回throw或被原错误处理器catch时flow仍失败，原请求键与草稿保留。成功响应本身不替代核对。独立读取被拒绝时不会污染正在正常完成的原flow。现有持久恢复协议继续负责其原写操作；本片共享内存登记没有引入冷恢复或自动重发协议。

普通人工回执仅对 `/api/executor-receipts/{id}/commands` 的闭合拒绝契约解除登记：409的六个明确字符串均位于原same-key replay检查之后、回执业务修改之前；422仅接受FastAPI结构化body校验错误。原opaque请求引用、输入和Retries仍保留，刷新/改正后由用户明确提交新key。没有泛化为所有409/422可释放；Case守卫、异参冲突、未知500、丢响应及不匹配422仍保留未知保护。两个真实owned PG用例分别证明旧版本409、空理由422未产生回执事件，回执业务行计数不变，随后明确新key纠正成功；不宣称所有后端拒绝都没有其他metadata观察写。

receipt-submit及同类原表单返回其原Promise，保护覆盖实际POST挂起和未知结果。普通列表、跳转和其他会清状态的独立入口在登记存在时拒绝执行；原receipt-refresh、对应业务域的原刷新/恢复及非破坏性历史读取按允许范围继续。未知POST不因普通GET读到新版本而释放；已知成功POST可由原一致GET核对后释放。没有永久禁用所有导航。

最终冻结相关 **415 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，112.59秒**，见 [results.json](evidence/semantic-readback-20261013/results.json) 与原JUnit。十个模块包含Case取消、队列、资料、分派、回执、目录、离线页面和诊断；新增2真实PG用例包含在415内。根48个完整原HTML模式使用原handlers/loaders/renderers/clearers，仅DOM、HTTP、存储和定时器为离线double；其中旧25个pending模式仍手工设置状态，不替代真实写验证。21个队列单元/ASGI模式也不等于完整浏览器或冷业务链。

独审在同一冻结源码hash重跑 **13模式/98断言 PASS，0 FAIL/ERROR/SKIP**：12真实原页面模式77断言，1纯函数闭合拒绝契约21断言。覆盖link两次200但版本不一致、ACK旧step、intent错绑定、readiness内部catch、真实executor表单pending/unknown→普通列表、明确409/422纠正、Case守卫409/未知500/非body422继续保护及独立读拒绝不污染ACK。较早core6/38和拒绝7/60不累加；上一交付20/117、动态1/6、旧23/115与catch1/8以及旧PG4不作为本片新增验证。

原失败证据保留。根最初红窗口为2有效FAIL、1脚手架时序假PASS；补上macrotask tick后，对精确83717 Git blob的实际receipt-form-pending反例FAIL。独审另4实际语义反例对精确83717 FAIL。中间修复窗口66、71、71 PASS均不与最终415累加。执行连接曾报 `exec_command failed: CreateProcess { message: "Rejected(\"Failed to create unified exec process: exec-server transport disconnected\")" }`；该次动作NOT_EXECUTED，原工具恢复后才重新执行，没有换环境或绕过。归档逐文件保留hash/字节，本片已识别fixture会话repr导出数为0，原件不修改；归档hash检查属于证据完整性检查。源码diff检查PASS；归档暂存diff检查实际FAIL/rc2，根原红日志/XML共12处pytest尾空白原样保留，检查输出也归档，不裁剪原件。

两安全approval保持false/null/null；main/F1/原F2及既有交付/安全分支不修改，不创建新安全执行分支。浏览器、安全探针、Windows、新冷AT08/35、真实模型/付费、生产迁移及部署均NOT RUN。历史浏览器拒绝不重试，原安全1PASS/1FAIL/19NOT_RUN和未知根因不变。本片修复范围可复核交付，下一步由父级复核；完整Case生命周期和冷全链未因本片通过而签收。
