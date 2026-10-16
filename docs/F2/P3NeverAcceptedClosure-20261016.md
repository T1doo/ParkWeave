# P3 从未接单的明确收束合同（2026-10-16）

接续交付 `c6f0771f92b585829bda1e7496aee98945e6877d`，冻结源码 **`c91bbea1e996c6608665bb76dd65218f2ba542c2`**，开发分支 `dev/f3-p3-never-accepted-closure-20261016`。实际HEAD、default网络、远端main祖先和单一共享源码/Git集成者已核。文档提交及推送后HEAD以最终远端核验回执为准，文档不预测自身SHA。

冻结源码已先行正常推送供父级并行审查；另有独立开发证据分支 `dev/f3-p3-closure-review-evidence-20261016`，提交 `53eb320c8e838e6a7dacd506cbddd6b39f4aa491`，保留当时25完整窗口/1205项的原始XML和manifest。该快照是部分进度，不冒充最终范围成绩。

本片沿原F3-T02/T03增加独立资格 `P3_NEVER_ACCEPTED_CLOSED_V1`，兼容schema3；不是零前沿复用。有完整P3分派历史但从未ACCEPT，所有原OFFER/REOFFER须经原授权者明确DECLINE或WITHDRAW收束，两种终态保留各自决定。OFFERED、已接单、撤权和UNKNOWN分别拒绝；空行、PENDING、用户提示、删除再恢复或刷新均不能证明合法收束。epoch必须大于零且完整递增，ever_started保持true，不清零历史。

## 最小完整价值链

同Case原手动来源刷新、当前计划/版本绑定、受影响与保留步骤预览、用户明确完整ADOPT形成新计划并新P1，沿原PROPOSE/明确APPROVE/资源COMMIT；重新办理P2–P5原业务与VERIFY，最终读取六目标本地证据和工作清单。原六目标、P1–P5、原计划历史、UUID、资源占用和未受影响锁证据保留；不自动释放、撤回或解锁。目标读取仍为 `recorded_states_only`、`evidence_verified=false`、`case_goal_completed=false`，不声称现实目标完成。

旧P1/P2原VERIFY证据、八张业务表完整快照、原分派根/全部offers/events、每个原命令指纹/actor/payload/五元fence及xmin与不可逆marker序列相符才有资格。限定原revision偶数2–62，为后继原REOFFER/ACCEPT留出原64预算。预览、批准、提交绑定同一完整摘要与fence。原生追加consumption列与SQL触发器独立核对实际快照和事件序列，延迟约束要求同事务真实Approval、resource link与receipt；失败事务原样回滚。

后继真实P3–P5增加epoch后，原键冷GET从不可变consumption anchor只读重放，不用当前行数重构历史。资源交付与Approval已有原键GET；普通P3 OFFER/WITHDRAW没有通用原键GET，本片不创造该能力，也不误用只适用PENDING_MANUAL_RECEIPT的恢复入口。参数冲突继续拒绝，不确定回执保留opaque恢复句柄、不自动补POST。

父级要求先交付实际受影响范围，既有已完成26窗1487项均保留，暂停已知调度器让原3个子窗全部正常结束，再取消未启动旧队列；未中断有效测试或杀未知进程。补充9个批准/计划/锁/资源/目标/清单/采纳直接模块，最终79模块范围有逐项依据，原178计划与冻结清单原件保留，范围修订另列scope-amendment-v1。

默认关闭，仅在原已签发自有合成PostgreSQL fixture的任何preparation/业务出生前明确安装，沿原owner建本地DDL；不新增角色、GRANT、安全权限、迁移、回填或重签发。协议依赖原可信owner与连续catalog指纹，不抵抗任意超级用户、系统目录伪造或检查间不可见未注册DDL/restore。

## 实际验证

冻结同SHA **79个完整相关模块，1807个唯一pytest项PASS，0FAIL/ERROR/SKIP**；本轮按父级明确要求收敛：原170模块基线中71个完整模块本次执行，另99个未启动旧模块停止排队；原178模块全量回归未完成，不宣称整体通过。此前4303节点是历史基线，本轮重执行旧1648节点，另2655节点未执行；原一个精确函数导入期UUID参数仍仅做同一归一。新功能159项包含在主总数内。684源码、26204tracked文件和49runner输入无漂移。实际选窗、节点、JUnit与前后hash见[最终门](evidence/p3-never-accepted-closure-20261016/p3-closure-root/v1/final-gate.json)和[冻结清单](evidence/p3-never-accepted-closure-20261016/p3-closure-root/v1/freeze.json)，不代表全仓或生产验收。

原CI12完整模块另433PASS/14原平台SKIP；冻结独审完成后独占运行CI，最后原恢复30项以原2秒预算独占运行。独审与主测试若节点重叠分列，不重复相加。预声明同SHA相同完整模块至多一次有界重试；实际selection和失败原件决定是否采用重试，禁止迁移早期版本成绩。

新HTML/native HTTP→ASGI→自有PG四模式与已安装Linux Chromium四模式实际执行，含明确新资格、新批准与资源提交、丢COMMIT/PROPOSE/APPROVE回执后的原键GET、当前/迟到403、后继VERIFY及目标/清单读取。原Python命令前置旧历史、刷新/ADOPT/P1，后继业务由Python loopback HTTP控制；页面执行明确批准/交付和VERIFY/读取。有限八种模式不等于全面浏览器AT。

独立PG窗口35项和真实父锁竞争2项覆盖WITHDRAW/DECLINE及多轮REOFFER、完整原历史、owner/租户/身份、撤权、迟到意图、历史删除/UPDATE/恢复、原命令事务回滚、摘要错误、幂等参数冲突和冷GET。双向ACCEPT↔WITHDRAW竞争按原父锁排队，胜者真实提交、败者stale fence409；不靠超时或死锁作通过。实际可达顺序中，旧REOFFER提交后OFFERED拒绝新资格；明确再次WITHDRAW产生新摘要且epoch不归零。新ADOPT/P1到新COMMIT/P2期间旧REOFFER受原P2门拒绝，不关闭门制造虚假双胜；新提交后旧捕获ACCEPT/REOFFER/WITHDRAW意图拒绝，fresh新P2后正常新REOFFER/ACCEPT。

纯资格变异校验与原生PG拒绝分层记录，不以纯层代替PG。新增严格规范UUID拒绝uppercase/32hex/braces/URN及错误类型；此前异常已有原外层Conflict处理，并无正常Approval500实证。独测32行设计表是有限覆盖映射，不把未执行行或静态代码当作测试PASS。分析脚本曾混淆原件mode与终态action，失败诊断及修正保全，业务测试没有重跑或改分。

## 失败保全、封存与边界

开发阶段旧生命周期表排序字段错误、SQL CASE括号、页面测试夹具缺原常量/节点等失败与后续修正均保留。封存前辅助清单曾因Git默认转义中文路径而报FileNotFoundError，未生成freeze或测试成绩；改用与原运行器一致的NUL分隔枚举后成功，产品源码不变。暂停调度后的只读/proc children文件检查曾因环境未暴露该字段而失败，未执行终止；随后逐进程验证仅三个已完成子进程为zombie，才终止本任务已知暂停调度器，排队测试未启动。原始测试、断言和等待预算不放宽。未冻结开发预检、候选私有测试及早期版本不迁入本次正式成绩。

普通归档推送曾被GH013将两个由uuid4生成的测试文件名片段误判为Mailgun密钥。未使用解锁链接、未改保护规则；原件、原审计和被拒绝的本地文档提交完整保存。公开路径与元数据仅将这两个无业务含义的随机组件替换为不可逆SHA256显示标识，raw_path_sha256及原件哈希继续绑定实际私有路径；内容最小化后的首次复审脚本因局部变量遮蔽在旧封印复核处失败，日志与工具原版保留；修正工具后对同一公档完整重审，未重跑业务或放宽检查。重新独立审计后重新生成未发布文档提交，沿原远端源码正常快进推送，产品源码和测试成绩不变。

新五个primary证据根全部停止写入；seal SHA256 `a1dfb34e7ba07af719c5f5bfbb8c2c758271f5a360d972334e749b6609255c18`。此前18147份原件hash保持。公开主档1152对/353066274字节，另index与.gitattributes共1154文件，按全部确知合成值脱敏；私有登记、数据库、缓存、临时目录与截图不公开。独立归档审计PASS，receipt SHA256 `34a16ca0d7d66d9c0cd0bf30f9209e2b0ac6ef4f090fbb15dd6dc05fcc65f223`，见[独立审计](evidence/p3-never-accepted-closure-20261016-audit/final-archive-audit.json)。主档只含索引配对，审计sidecar独立索引。

原特殊PG27 profile/role前提仍未满足；schema33接单后before_receipt/reconciliation取消仍受原门拒绝。Windows/Win11及其浏览器、广覆盖浏览器、正式AT、真实模型B0–B2、现实履约/正式治理和生产NOT_RUN。原7个远端工作流分支过滤不覆盖新分支，未改工作流或手动调度，远端CI NOT_RUN。此前集合外浏览器Case设置诊断未在本片重测，已通过的具体模块以实际选窗清单为准，不因新页面通过而补分。通用既有DB迁移、跨进程重启/备份恢复、任意owner DDL ABA和更广已接单在途迁移仍无本片证明。模型调用0；无main修改、强推、部署、新费用、凭据、安全权限或绕访问拒绝。

下一最高价值产品片是已ACCEPT但尚无P4效果时，来源变更的明确收束/重批/继续履约合同；原取消门、回执与占用必须保留。已有P4/P5效果的更广在途合同、F5备份恢复与正式AT前提另列；须独立明确历史/占用/回执处理，不能清零或隐式复活。本片不声称整个F3完成。继续按一周目标推进。
