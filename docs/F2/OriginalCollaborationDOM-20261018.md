# 既有人工补证与关闭／重开普通页面链

基线 `e3be7e4de10fce1ff4fc988ffb878ec12694c660`，正常分支 `dev/f2-collaboration-dom-20261018`。先核原方案、状态机、普通页面与测试后，复用已有实现；本片不改 `src`，不新增算法、provider或批准包装。验收目标是两个完整同对象的普通 Chromium DOM 路径与跨普通 API 进程持久回读。实际冻结及分窗成绩另记验证报告，不能由本合同预认通过。

## 人工补证协作

`test_manual_goal_collaboration_browser` 在显式 SYNTHETIC 身份／权限／目录初态中，先核 Run、Case、preparation、材料与 Run assignment 均为空。普通 configured_app 及独立 LOCAL worker 从原页面创建新事项，原控件保存双目标诉求、两份 USER_STATEMENT 材料、专员 REVIEW、企业 CONFIRM；保留未支持目标，明确采纳 partial 计划并核验 P1。

同一 preparation／Case／Run／plan 经原个人任务队列交接：REQUEST → TAKE → REQUEST_EVIDENCE → SUPPLY_EVIDENCE → TAKE → REPLY(INFORMATION) → ACKNOWLEDGE_REPLY。补证与答复显式选择当前两份材料 ID／version／SHA；知悉前按钮禁用，企业明确勾选原答复事件与 fingerprint 后提交。逐阶段同对象、当前来源 SHA、材料完整性、七事件顺序与原答复绑定均核验。最终 COORDINATION_ENDED 仍 PARTIAL／UNSUPPORTED，未证明真实性、阅读、外部批准、线下履约或 Case 目标完成。

停止首个 API／worker／浏览器后，新普通 API 进程及两个全新角色上下文只经 GET 和原页面冷读。核完整 Case 表记录、人工账本、来源、材料、同对象、权限快照不变；无运行时 Run assignment 或权限创建。业务写入均经原 DOM，page.evaluate 仅观察值，不替代业务动作或导航。

## 同一事项回执反馈、关闭与重开

`test_case_feedback_cycle_browser` 复用 `test_assigned_demo_chain_browser` 的完整原 DOM P1–P5／六本地产物链。准备资料与精确 Run executor assignment 明确为普通进程启动**之前**的既有 SYNTHETIC fixture；不能称零设置新 Run 全链或普通自动分派。原两参数测试节点保持，提取共同执行函数只为在同一浏览器和业务对象上继续。

企业对已 ACK 回执不能直接 REQUEST_CHANGES：先原控件 REOPEN，P4 失效；原 executor 对同 step 提交 v2；企业 REQUEST_CHANGES，原 executor 提交 v3，企业 ACK。当前 P4、cycle1 REVALIDATE／P5 后，企业明确 CLOSE_LOCAL_RECORD，P5 需重验；明确 REOPEN 到 cycle2，旧 verified SHA 清空且不能关闭；再显式 REVALIDATE／P5。最终六产物本地核验，不代表 Case 目标完成。

核 P4 精确 v3 ID／SHA／SUBMIT 与 ACK 事件及 actor／revision 顺序；核 P5 精确 cycle2 REVALIDATE actor／事件与持久 verified_snapshot，独立按既有 canonical JSON 规则重算 SHA。旧材料、准备、派工、回执和生命周期事件保留，资源 hold／claim／link／offer 不自动释放。新普通 API 进程、全新浏览器通过原列表冷读最终 DTO 和完整同 Case 历史，仅 GET，无权限变化。

## 观测与预算

按父级要求，下一次相关执行前增加自有 ordinary child 的 spawn、逐次 health、ready／deadline、stop 时序及 `/proc` CPU／RSS 状态；失败时既有自有 PG observer 增采精确失败数据库的连接、锁／blocking PID 和数据库资源计数。首次 spawn 日志也在 child 清理 try/finally 内，日志失败仍进入自有 child 回收。日志不记录 DSN、会话 token、环境正文、SQL 正文或真实资料。测试外层启既有 owned-connection-diagnostics，保留节点阶段、连接尝试与 PG 日志。

原连接 2 秒、DROP DATABASE statement_timeout 5000ms、ordinary 启动循环 15 秒、health HTTP timeout 15 秒预算不变；失败后额外诊断不是新的业务重试机会，也不把整段启动／清理说成硬 15 秒。无自动重跑。先前连接／清理／启动超时底因仍 UNKNOWN；后来 PASS 不解释或抹除原失败。

POST 记录仅枚举浏览器收到的 response，不能等同所有发出的请求。新链没有运输注入。前片旧 403 是另一 fixture 身份拒绝的运输注入；其 overlap 两分支均旧回复先交付，80ms 等待不是 settled 屏障；本片未触及该并发代码／场景，不扩大其结论。

首冻结 a54add455c41e81bd91df481e70cbc377826354c 的14完整模块301唯一窗实际282PASS／19FAIL／0ERROR／0SKIP，四个新增DOM节点及四个原DOM节点均PASS。19个旧Node页面失败涉及六个既有Element替身，缺少原清理入口调用的classList；原JUnit保留null读取、等待未达与直接classList.remove栈，离线同字节诊断在零API调用下复现真实beginCaseWorklistEntry→clearPreparation→clearCaseCancellation的TypeError。它与此前连接／启动UNKNOWN分开。

仅就地复用既有multi_goal_overview_actual.js的className同步、stateful add／remove／contains及小probe，补六个替身能力，保留原生产清理、所有业务／负例断言和预算。修后另冻结并有限复验19个实际失败节点及8个完整DOM节点，不把两冻结／分窗成绩写成301单窗全绿。旧Node回归含显式隔离template／approval测试fixture，不进入普通批准；新增四个普通DOM节点不依靠这些批准桥。

第一次修补e1d9502d8f1b3d176cc33f0676e7efbc26aad3ca由根代理复制片段错误，六constructor截断为499字符，缺remove／contains及闭合；独审拦下，六项node --check均失败。该27节点窗自然结束8PASS／19FAIL／0ES，759输入零漂移，原件保留，不能视为已修。一项只读/proc cwd核验遭PermissionError，未发送SIGINT或扩大权限。随后复制现有完整634字符constructor，六个文件node --check全部通过后才冻结最终版本；完整业务实跑成绩以独立后续窗口记录，不把语法检查当业务节点。旧连接／启动UNKNOWN不由此解释。

## 运行输入与未验范围

本片只验证显式 SYNTHETIC、LOCAL、Linux PG／Chromium（1200／320）环境。无真实模型、身份、Grant、目录发布、分派、批准、凭据、费用、安全网络权限、main 修改、强推或部署。普通合法运行仍需已有会话／READ、PREPARE、REVIEW_ASSIGNED、精确 preparation_catalog、现有记录及执行者的当前精确 Run assignment。缺项准确拒绝，不让测试安装 fixture 或 IsolatedPlanApproval 进入普通批准。

正式来源专用 backend、主体映射及原采纳证明尚需合同和专用代码。最小可转交字段保持 [来源合同原文](ReceiptSubmitRecovery-20261018.md)：既有来源域／ID／版本／只读结构与获准样本；preparation／Case／Run／已采纳计划的关系、版本、hash 和 current-head；原采纳决定／actor／状态及 Run 回执语义；既有主体映射、权限／用途／有效期／撤销；公开 trust／签名覆盖与独立验真协议。不要发送 token、私钥、密码或 DSN。正式五证明 UNAVAILABLE，NativeRunAccess permit／writer 默认拒绝，资源批准只读仍不可消费。

Windows11 原生、正式 AT／AT35、真实来源／批准／业务／模型、生产受保护宿主、真实履约与完整项目交付均未验。原方案其他剩余项沿 [前片剩余清单](ReceiptSubmitRefreshFixValidation-20261018.md) 保留；本片实际完成后仅更新上述两条普通 DOM 缺口，项目仍 IN_PROGRESS。
