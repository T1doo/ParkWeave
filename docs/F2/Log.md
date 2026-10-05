# F2并行工程日志

## ENG020 确认审查修复与前端可审阅版本完成（仅本地）

起始50f7c4b/干净工作树。同工作区独立6.1 sol medium reviewer固定da69..50f7发现1项P2：CONFIRM响应丢失、另一页取消、原key重试时后端历史回执+当前RELEASED正确，但旧UI提示已确认。真实Chromium合成响应先复现22/23 true/1 false（.runtime/eng020-review-repro.json），最小修复按当前hold.state反馈，回执与状态不一致则标历史回执；后端、不可变回执、锁/授权不变。review未独立重跑API，不将已有成绩冒充审查执行；范围与未测见ENG020-UIReview/CloseoutReview。

依据V1三工作区和用户美观要求，小范围纯HTML/CSS优化：绿色/暖白、统一字号间距与卡片/表单、明确当前导航、服务诉求/材料和资源步骤层级、主确认/次取消、当前状态色/空态/全页错误反馈、UTC可读时间。事实候选折叠但真实可展开办理，JSON工程记录默认收起；合成/未真实预约/未受理/未履约标签仍可见。无需框架/字体/CDN/安装。初轮真实截图可视审阅后改善时间，最终17张截图保留.runtime/eng020-ui-final，原初轮目录也保留；证据有各图hash。桌面1200/手机320与390实图检查正常确认、空态/权限错误、服务/协同/资料状态，未用DOM成绩代替美观；用户视觉签收仍PENDING。

实际低权限API/独立worker/PG浏览器：资源双企业预检/占位/确认/取消/TTL5过期、匿名容量、本人记录/reload、disabled重复click无重复、返回导航清旧form、script纯文本 PASS；资料双角色补正/补交/人工核对/确认/重开及事实区块展开/补充仍UNKNOWN/取消历史均PASS，自有fixture清理exit0，页面错误0。最终资源排序23/23、旧资料排序23/23 PASS。实际PG/API67 PASS/2既有WARN，新增不同key双确认仅一次提交和等待身份锁时撤权拒绝，既有版本/期限/tenant/取消竞争/幂等保留。

冻结最终全量 **486 passed, 1 skipped, 2 warnings in 146.07s (0:02:26)**，486 PASS/0 FAIL/1 Windows SKIP，所有测试源hash与冻结文件一致；25个Windows/R4/角色及roles SQL保护文件逐字相同，原V1来源字节未改。证据evidence/eng020-acceptance-summary.json；日志/会话只在.runtime，不公开明文会话或DSN。F1未签收/F2NOT_PASSED/R4DISABLED，Win11/原生picker/真实手机/完整36AT6EXNOT_RUN；Windows37324704568失败明细待用户。无push/新CI/备份/上传/新凭据/真实provider或外部预约，预算0。

## ENG019 单资源本地合成确认完成（本地并行工程，非阶段签收）

基线da69ea6。同工作区独立只读resource_hold_review审查5849..da69占位/过期/释放，未发现实质finding；具体边界见CloseoutReview，本次确认不继承独立审查结论。按实施前ENG019规格新增schema11状态/action约束、Confirm typed API与明确的本地确认/取消按钮，不增加应用数据库权限、不改原输入/TTL。有效HELD才可确认；锁后DB时钟、当前角色/tenant/core及资源Grant、固定/当前版本、开放/容量重验，排除本条占位避免双计数；确认保留区间容量，显式release兼作本地取消，TTL保留历史，状态/不可变回执同事务。

新PG/API首轮与旧资源共63 PASS（17新增+46旧），后补锁等待过期和双owner满容量确认2项，最终全量 484 passed, 1 skipped, 2 warnings in 141.49s (0:02:21)。首轮全量483 PASS/1 FAIL/1 SKIP：健康schema断言修改发生在运行期间，收集的10与DB11冲突；失败项目.runtime保留，不算通过。最终源码冻结重跑，484 PASS/0 FAIL/1 Windows SKIP；全部测试source hash与冻结文件一致。迁移10→11/重复迁移保留占位及原回执，回执写失败确认全回滚；版本/停用/窗口/容量/期限/撤权/跨owner/非法字段/同key指纹/并发确认取消负向已验证。25个Windows/R4/角色/roles SQL保护文件逐字相同，无新授权。

实际Chromium低权限PG/API双企业资源browser PASS：显式确认、历史TTL不变、另一企业匿名容量冲突、本人取消释放；TTL5真实DB过期、反复读取/reload、纯文本、320/390窄屏和页面错误0仍通过。既有双角色资料待办browser PASS；资源排序21/21与旧资料排序23/23 PASS，包括迟到确认草稿守卫和结果不明同key重试。自有fixture进程清理exit0。实际截图可视检查标签可读，非视觉设计签收；后续统一配色/字号/间距/信息层次/各状态/手机设计已入Plan，日期picker手势NOT_RUN。

证据evidence/eng019-acceptance-summary.json；运行日志/会话仅项目.runtime不公开。CONFIRMED只表示本地合成账本，真实预约NOT_CONFIRMED、外部NOT_SUBMITTED、线下NO_EVIDENCE；组合确认未实现。F1未签收、F2NOT_PASSED、R4DISABLED、Win11NOT_RUN、完整36AT6EXNOT_RUN，真实provider/预算0。无push/Actions日志/新CI/备份/上传/新凭据；Windows37324704568具体失败子项仍待用户，收到优先F1。

## ENG018本地纵向切片完成（非F2签收）

在5849基线按实施前规格新增schema10：版本化合成资源/显式READ-HOLD Grant/占位/不可变回执；只新增新业务表权限（登记/Grant只读，占位INSERT和UPDATE state，回执SELECT/INSERT），既有角色上限和旧表Grant字节不变。Store未来版本拒绝门相应改>10，原schema断言9→10/未来11，不删oracle；新SQL纳入package-data。一个合成资源具UTC开放/容量2/前后300秒缓冲，最小REST与资源UI可预检→短期占位→本人状态/释放/过期；无正式/组合确认、后台清理或外部作用。源目录合法合成工程与真实样例许可分类已纠正；原V1两文件字节/hash保持。

后端首轮43 PASS/2 WARN/6.51秒，补跨资源key/身份及资源锁有界冲突后46 PASS/6.82秒；冻结最终46 PASS/0 FAIL/2既有WARN/7.81秒。真实PG覆盖峰值（不误算不相交数量）、半开端点/双缓冲、并发只有2份成功、DB锁等待后时间/无清理过期、同key不重复/不延长、UTC等价指纹、新已确认意图使用新key、撤权前置/同org非owner/跨园区、规则停用/版本变化、输入/TTL约束、回执失败全回滚、应用不可改TTL/原始输入/历史、9→10与重复迁移保留旧资料历史。

实际浏览器首轮及补采均FAIL：preview422后resourcePreview readiness timeout。合成安全诊断证实读取默认日期有效，cached agent-browser fill之后两日期变空（无HOLD写入）；harness改成原生控件赋值+真实input event，而非放宽后端校验。资源响应排序首次FAIL为oracle把CSS选择器当id，修正后17/17 checks PASS；失败留项目.runtime与汇总，不计产品测试PASS。最终真实本地低权限API/独立worker/PG双企业资源browser PASS：预检/显式占位、匿名容量冲突、仅本人记录、主动释放、TTL5实际DB过期且释放容量、重复刷新/reload、脚本文字、320/390无横滚、页面错误0。原生日期选择器手势NOT_RUN。自有harness退出0；既有双角色资料待办browser和23/23排序回归也PASS。

最终冻结全量 **465 PASS/0 FAIL/1 Windows SKIP/2既有WARN，141.70秒**，所有回归源hash与当前文件一致；24个Windows/R4/角色上限保护文件逐字相同。src/roles.sql仅旧内容之后添加新业务表最小权限；未改全局角色权限、安全/网络策略、Win11guard或production R4。新17checks不加入pytest数，旧独立审查仅c285/3aa，不继承给本片。证据在evidence/eng018-acceptance-summary.json、eng018-browser.json；不公开会话/DSN/runtime日志。

本片到此停止扩展；Server37324704568 native_suite具体子项仍UNKNOWN，待用户后优先F1有界定位。F1未签收、F2NOT_PASSED、whole36AT6EXNOT_RUN、R4DISABLED、项目真实provider/预算0；无push/新CI/备份/上传/源代码外发。当前登记支持合成工程；真实资源/价值主张需对应真实来源许可，不把该许可缺失误称全部F1或合成F2硬阻塞。

## ENG018实施前记录：来源分类修正与资源最小纵向范围

基线5849c02。重新读V1：F1-T06要求开始获取来源许可/记录假设，缺许可停对应真实样例而保留显式合成测试；F2允许明确合成目录。更正CloseoutReview矩阵，不再把真实试点许可笼统作为全部F1或合成F2工程硬阻塞；原V1/Windows/真实模型/安全门不降。既有独立review仅c285/3aa，不能继承给资源新片。

用户新授权F2-T03最小资源预检/占位/过期/释放。缺时段容量与占位表，先冻结ENG018-ResourceHolds/Plan。补最小schema10与显式合成登记/最小新表授权；现有角色上限、原身份/授权锁及R4/Win11边界不变，不新增资源管理或真实预订。数据库时钟、短事务、半开/缓冲/峰值容量、当前权限及独立回执；组合确认/正式确认仍未实现。H01—H10初始NOT_RUN，之后真实输出另记。不push/CI/恢复包/上传/源码外发，LIVE/预算0，收到37324704568失败细项先回F1。

## ENG017：两个本地增量的独立只读收尾（文档only）

固定审查6ff160a..3aa99e4，保留c285竞态修复与3aa待办、本地/远端历史，不扩功能。用户明确授权同工作区独立reviewer，按指定6.1 sol / medium由 /root/local_f2_review只读审查case/session响应与草稿、个人待办role/tenant/owner/assignment、重复/跨case导航和未授权材料。结论未发现所审两增量的实质finding；Python AST/JS语法/diffcheck、ENG016六源码hash匹配。reviewer没有改源码、安装、外网、API/项目模型、私有会话、复制/导出/上传或新测试执行。

既有最终成绩保留419 PASS/0 FAIL/1 Windows SKIP/2 WARN、新19 PG/API PASS、23/23合成排序checks与真实本地双角色browser PASS，不冒充本轮重新执行。CloseoutReview.md记录功能/用例矩阵、未测同org第二enterprise owner专属用例、非全时序/非生产审计、100件/64限制和完整F2未实现范围。当前无新实现finding需修复，但正式F1/F2门不转PASS。

立即等待run37324704568失败cases/计数；允许元数据不足以细分native_suite exit1。正式F1另保留E1 Win11原生、E2安全模型配置/核实额度与预算、E3真实来源/许可；R4有条件集成代码仍未完成，不把它伪装成纯外部问题。收到JSON先核对run/source、按命中子项有界定位/修复/本地验证，再依据届时授权比较远端、普通push实质变化并统一一次CI监测到终态；不取被拒日志/无证据重复CI。此收尾只有必要项目内文档提交，未push/merge/deploy/上传/恢复包，项目真实provider请求与预算0。

## ENG016：个人资料准备待办（2026-10-05，本地开发与验证）

用户在Windows失败子项待补期间明确允许独立F2切片；本轮同时明确禁止恢复包/源码外发/Library/第三方/上传。基线 c285da8 正确恢复副本 dev/f1-foundation，先冻结 docs/F2/ENG016-PersonalTasks.md 与 Plan/TestSpecification，再实施V1产品§3/§5.5、F2-T04/T07的最小“本人需补交/确认、获派核对”子集。不处理未证实Windows失败，不扩大到跨服务规划/资源/真实资格或履约；原阶段门保持。

新增只读 /api/preparation-tasks，从同一PG语句快照读取当前state、资料槽存在性、补正理由；复用当前身份、READ/准备Grant、精确owner或reviewer与园区企业交集。无Schema/Grant/后台任务/通知/outbox修改。100件未本地确认事项的检查边界和更早记录提示可见；revision64显示既有写上限阻塞。待办只含必要目标/引用/状态/下一步，不含材料正文。企业缺材料/补正/确认，专员材料齐全后核对；确认从双方待办退出，重开返回专员待办。点击待办读取当前详情再执行原有CAS命令；队列既有revision不替代重新授权。界面复用ENG015代次/身份守卫，迟到待办不会恢复旧身份或覆盖新case草稿。

新增真实PG/API测试首轮 **19 PASS/0 FAIL/2 既有 WARN，3.54秒**：状态链/双case/缺少槽/说明/无材料正文、跨企业园区/未获派与错误角色/伪造角色、撤权、重复读/Store重建、并发提交快照、64上限和101有权记录的100件读取提示。实际Linux Chromium + 自有低权限本地API/独立worker/PG首次浏览器 **PASS**：双case企业与专员的补交→补正→核对→确认→reload→重开、待办打开当前详情、重复读无新历史、错误身份清UI/错误确认拒绝、脚本字面文本、320/390无横滚、页面错误0。自有harness正常停止退出0；不重置既有smoke记录，未读取/输出真实凭据。独立响应顺序浏览器 **23/23 checks PASS**（ENG015原20项保留，增加迟到待办、旧身份待办、范围限制）。各产物留本项目内，最终冻结全量 **419 PASS/0 FAIL/1 Windows SKIP/2 既有 WARN**（125.71s (0:02:05)），全部回归源码hash与当前文件匹配；详情见 evidence/eng016-acceptance-summary.json；不把checks增加到pytest数。

原V1两个原件 bytes/hash与manifest一致；R4/Win11 guard、Windows脚本/workflow、角色SQL、迁移不改。Windows37324704568仍native_suite具体FAIL子项UNKNOWN，F1 IN_PROGRESS未签收、F2正式准入NOT_PASSED、whole36AT6EX NOT_RUN、R4 DISABLED、真实模型与预算0。没有push、CI重跑、恢复包、上传或新外部连接。当前并行切片停止于独立本地结果，不宣称完整F2或真实业务效果。

## ENG015：资料准备 UI 延迟响应与草稿串事项修复（本地，待独立复核）

基线 `6ff160abe979f9d1c28d0e7804fda668daf72cf5`，正确恢复目录与 dev/f1-foundation 分支，不回退初始 work 树。合成 Chromium oracle 只读提供该 commit 原页面并控制 fetch 响应顺序，实际复现同身份 A 迟到 GET 覆盖 B、B draft 发往 A 的 commands（有效 revision 1）、切角色后旧响应恢复事项，以及跨 case 保留材料/来源/说明草稿。原页面还在迟到写响应后清空新编辑。这是合成响应证据，不宣称发生真实数据泄露；它也不替代后端 tenant/角色验收。

修复限于 preparation UI：请求冻结身份 token、代次与选择 id；成功/失败/JSON 完成后均检查是否仍为当前请求，旧错误不能清空新选择。载入保存 case/id/revision 快照，提交前核对；请求发送后导航不会撤销已发出的事务，但响应不再推进别的事项。切 case 清空材料、来源、人工说明，同 case 刷新保留草稿；成功写后仅当草稿未被修改才清空内容/说明。目录、列表、New、导航和 token 变更均使旧链失效，离开后不继续建单轮询或 preparation 创建。保留相同输入失败重试的幂等 key；后端权限、授权锁、CAS 和不可变历史无改动。

首轮 oracle 因 ABA 测试队列选错请求而 CDP evaluate timeout（harness FAIL，非产品计数）；修正队列从末尾选择新请求，保留原失败事实。原页面复现 PASS（即确认四项缺陷）；修复后冻结浏览器响应顺序 **20/20 checks PASS**：延迟 GET/写、身份、A→B→A、跨事项全部草稿、同事项编辑/刷新、409 草稿与幂等重试、提交 case/id/revision、旧目录/列表、导航/New、取消建单链。原有真实本地合成 API/独立 worker/PG 的双角色表单流程也通过，包括补正→补件→核对→确认→reload→重开、历史、失败确认拒绝、纯文本脚本和 320/390 无溢出。自有 fixture harness 正常停止，退出 0。首轮全量 **400 PASS/0 FAIL/1 Windows SKIP/2 既有 WARN**；补齐 case/revision 快照守卫后再对最终源码回归，最终冻结全量同样 **400 PASS/0 FAIL/1 Windows SKIP/2 既有 WARN**（详情见 evidence/eng015-ui-race.json）。没有用浏览器 checks 增加 pytest 数。

复现命令（依赖已批准缓存 agent-browser 0.38.2 和本地 Chromium）：`.venv/bin/python scripts/preparation_race_browser.py --expect-vulnerable --report .runtime/prep-race-before.json`；最终 oracle 去掉 `--expect-vulnerable`；全量 `.venv/bin/python scripts/run_acceptance.py --report .runtime/prep-race-acceptance.json`。原页面使用 git show，当前源码不回退。报告不含 token、DSN 或真实数据。保留既有 ENG014 与迁移失败记录，不触碰被拒日志、不单独 push、不触发 Windows CI。Server native_suite 具体失败仍 UNKNOWN，等待用户失败子项；F1 IN_PROGRESS/未签收，F2 NOT_PASSED，whole36AT6EX NOT_RUN，R4 DISABLED，真实模型调用/预算 0。

## ENG014进行中checkpoint（2026-10-05）

用户明确授权GitHub/Windows阻塞期间继续一个有界用户功能，不改F1准入/F1PASS。原F2前置真实模型/Windows与完整基础门仍未通过，切片对应F2-T01/T04/T05/T07工程子集，完整F2/36AT6EX NOT_RUN，R4关闭。基线1828653，dev/f1-foundation；无AGENTS/.agents新指令，无子agent/Sim修改/隐藏凭据读取/真实模型/预算/付费服务。

实现版本化合成企业资料整理服务，链接真实本地Case/Run，企业追加两个材料槽来源/版本，获派专员补正/人工核对当前hash，企业确认本地资料准备或重开；任何新材料使旧review失效、历史不删。qualification始终NOT_EVALUATED、资料真实性UNVERIFIED、external NOT_SUBMITTED/offline NO_EVIDENCE，原Case NEEDS_INPUT。无外部受理或线下成效。显式PREPARE/REVIEW_ASSIGNED Grant+固定角色/同园区企业/owner或精确assignment交集；应用无DDL/Grant修改或历史UPDATE/DELETE。当前API写与不可变事件同事务，版本/幂等/并发保护；GET短行共享锁防止半快照，保持当前授权锁协议。创建锁原Run避免不同key同Case竞态。Schema9为新增业务表；原schema版本断言升级9，未来版本拒绝测试改10，未删oracle。

Linux定向第一次30 PASS/6.22秒，补并发同Case与审核-补件竞态、Grant范围/不重激活等后34 PASS/4.93秒；原基础21 PASS/2.91秒。当前相关三组81 PASS/1 Windows SKIP/2既有WARN/58.86秒。TestClient+实际PG用例均只SYNTHETIC；浏览器用loopback实际API/独立worker/PG16.2 Python3.12.14，cached agent-browser0.38.2/Chromium，无下载/远端连接。

真实浏览器前两次成功走通创建/资料/双角色补正核对确认/重开/reload/字面脚本text，然后320px横向溢出断言失败。首次给select加border-box和button最大宽度尚未解决，继续定位；**browser完整证据仍FAIL、全量回归未冻结**，不把此checkpoint标READY或PASS。两Library原档完整字节/行/hash和files.py/windows_files.py/Win11probe/workflow逐字不变。

用户新提供另一环境GitHub读取恢复线索；本环境尚未证实。先安全保存本地checkpoint，再在原环境/原代理/原身份各一次Actions原target与远端分支状态复核。没有fetch/push/runner前，不声称网络/权限恢复；若Forbidden停依赖不绕过；成功才fetch/比较history，保留双方工作，不force或主分支合并。最终backup待阶段成果仅更新一次，此checkpoint不上传备份。

## ENG014阶段成果：READY_FOR_REVIEW（非F2签收）

修复后诊断确认320px viewport/scroll406且控件盒本身未越界：资料历史中脚本文本长单词溢出。section overflow-wrap:anywhere使完整文本换行，不以隐藏overflow裁切材料。第三次浏览器全链PASS（320/390均等宽）；追加单事项64事件上限后重启实际API/worker，并对冻结最终源重新验证浏览器PASS。原owned harness parent cwd只读检查遭psutil AccessDenied，未发送信号；用精确原argv/相同uid/已记录API+worker均直属父进程的安全交叉校验，再向自己的harness SIGTERM；它退出0/停止自身children，不发现或广泛杀进程，不改策略。

最终新增35项pytest PASS/5.26秒（真实PG/TestClient，包括事务失败rollback、历史权限、版本/并发/撤权）；冻结全量 `.venv/bin/python scripts/run_acceptance.py --report docs/F2/evidence/eng014-acceptance-summary.json`：**388 PASS/0 FAIL/1 Windows SKIP/2既有WARN，108.474秒**，84个src/test/script hash匹配，compileall/diffcheck通过。原schema期望8升级9、未来版本拒绝改10，只随新增迁移合理调整，没有移除旧oracle。

最终Linux Chromium用实际低权限API+独立worker+PG16.2 Python3.12.14、双角色真实表单，不修改数据库完成资料流程。创建→一个槽→专员要求补正→企业追加目录→专员核对当前hash→企业确认本地资料准备→reload→重开→追加版本→拒绝未重新核对的确认；三材料版本/所有人工事件保留。320/390模拟无横滚、页面错误0、脚本文本未执行、切身份清空旧资料。只SYNTHETIC，未收到真实目录/资格证据，不宣称客户或园区试点。实际重启前的Preparation在重启后仍IN_PREPARATION/3材料版本/8事件；最终API回读Run SUCCEEDED但Case NEEDS_INPUT/external NOT_SUBMITTED/offline NO_EVIDENCE，见独立restart-and-case-check证据。

用户新授权的本线程网络复核仅一次：安全checkpoint be5742e之后，原Actions target依旧Get ...: Forbidden/CLI exit1，数值HTTP状态/header/requestID/拒绝层UNKNOWN；Git原origin分支只读查询exit0，5185cf4与基线相同。由此不能称Actions/全部通道恢复；未fetch/push/runner，不新登录/换代理/读token/改权限。完整非敏感错误及结果见eng014-access-recheck.json，官方Work Mode状态调查同源未证实。其他环境/Sim分支线索不继承到Park。

本轮功能切片至此结束：企业资料准备/人工核对有可见可操作闭环，不只辅助测试；F2完整多服务计划/资源/执行者接单与真实回执/模板仍未做。F1 IN_PROGRESS、F2正式准入NOT_PASSED、whole36AT6EX NOT_RUN、R4 DISABLED、Windows/LIVE/真实数据门保留，provider请求及预算0。原V1来源字节/行/hash和R4/Win11 guard/workflow保护保持；低权限Grant与纯文本新API均本地可信代码，不执行任意生成代码，无外部业务写入。FirstUse说明显式合成入口/角色与限制，Plan标注新授权仅替代此前当轮不扩F2限制。

暂存前检查凭据模式无命中、无真实个人数据或private runtime/会话/DSN日志，安全本地commit保留checkpoint历史。阶段成果后仅更新一次用户私有Library恢复备份；不频繁上传，不把备份或恢复验证称Windows业务验收。最终本轮停止，交父任务复核派下一切片。
