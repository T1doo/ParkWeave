# ENG099：材料变化后的本人重新接单与回执恢复

基线为 `0979f0d7975e622eb2fa19f62acc6817279e0300`。沿原 V1 §5.5、§7.2–7.5 处理来源变化、显式重新确认、事务事件和未知结果恢复。ENG098 的隔离候选模板仍没有正式生产发布主体或启用权限；本片不改变 T06 / AT-08 / AT-35 的 NOT_RUN。

## 实际问题与持久恢复

旧接单把回执步骤绑定到固定资料 revision / SHA256。企业重开资料、补充新版本并重新人工 REVIEW / CONFIRM 后，旧回执新提交正确返回 409，但原分派又因已有回执拒绝重新分派；原 Case 没有可完成的新回执路径。独立旧版本实际测试已复现，原失败不通过修改状态标签掩盖。

当前资料已人工确认、原 P1 / P2 来源门禁通过且原执行者仍具有此 Run 的现有合法访问时，获派专员可明确说明原因，请**同一原执行者**重新确认新版材料。请求绑定旧接单回执步骤 ID、新资料 revision / SHA256 和分派 revision；缺少旧步骤 ID、错执行者、错 Case、旧来源或失去当前权限均拒绝。新 OFFER 不改变旧 ACCEPT 或旧回执；执行者本人新 ACCEPT 才创建新的回执步骤，并在同一事务保存接单、来源绑定、事件和原通知 outbox。

`migration-024.sql` 将单一 `UNIQUE(preparation_id)` 替换为 `UNIQUE(preparation_id, preparation_revision)`。这是约束替换，不是纯新增迁移；仅在 UUID 隔离测试数据库应用，生产未部署。旧行、编号、来源、正文和事件保持，角色/Grant/Run assignment 不新增。当前回执由当前已 ACCEPT 分派的 `receipt_step_id` 唯一选择，待重新接受时没有当前回执；无分派的兼容历史仅允许唯一旧步骤，多个无权威指针的旧步骤不任意选择。

当前合法企业/原执行者可查看旧代历史。旧代不接受新变更；已经提交的原键可在当前授权核验后恢复历史事件，响应明确 HISTORICAL_GENERATION / HISTORICAL_COMMITTED_EVENT，不把它当当前确认。新版必须重新实际 SUBMIT、企业 ACKNOWLEDGE，再重新核对 P3 / P4 / P5；关闭过的本地账本须显式 REOPEN / REVALIDATE / CLOSE。原 Case 关闭本地账本后仍是 WAITING_CONFIRMATION（重开恢复为 NEEDS_INPUT），本地账本关闭不表示真实目标完成、资格裁定或外部履约。

实际材料正文重新计算 SHA256、槽位及 review 快照；仅匹配数据库中存储的 review_sha256 不足以允许新 ACCEPT / SUBMIT。当前权限、材料、资料状态及 gate 在新业务写入时重验，原键恢复不再次执行旧业务。

## 页面与结果未知

原分派页显示“请原执行者重新确认新版材料”，仅列此 Run 当前合法的原执行者。历史回执原文可读，变更按钮禁用；同 Case 计划和分派导航仅进入权威当前回执。

POST 网络失败或 5xx 时保留原 path、body、幂等键及当前身份/Case，禁用编辑，使用“使用原操作重试”。同 Case 刷新不生成新意图；身份或 Case 切换清除私有状态，迟到响应不覆盖新上下文。收到确定 4xx 或提交回应后清除未知意图。页面键仅存内存，完整浏览器重载后不宣称能恢复未知键；已提交业务和历史可通过当前授权 GET 重读。

## 工程边界与验证

真实浏览器使用两个新 UUID Case；Run / Case / Preparation 与既有合法分配在浏览器启动前通过原 API/core 和隔离 setup 准备，不能称为浏览器从零创建 Case。资源组合通过原资源 API 确认，不能用测试 owner INSERT 业务持有或确认状态。启动后资料、审核、本人接单、回执核对和五步恢复由实际界面执行；不修改身份、Grant 或 assignment。

专项、完整回归、浏览器、源码冻结和远端提交证据记录于 [eng099-recovery-native.json](evidence/eng099-recovery-native.json)。Windows 原生候选代码及不可保证目标 file-ID CAS 的限制见 [ENG099-WindowsNativeAdapter.md](ENG099-WindowsNativeAdapter.md)。代码候选、Linux ABI mock、Server 隔离 CI 均不替代真实 native normal/S4、完整 Windows 或 Win11 验收。F1 未签收，F2 仅并行工程；原 42 项 AT/EX 保持 NOT_RUN，R4 关闭，模型调用和预算均为 0。

## 已完成的专项与浏览器证据

独立旧版本死路复现为 1 PASS，实际旧 SUBMIT / reoffer 均 409、业务记录不变。最终恢复专项 **46 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，28.99 秒**，覆盖真实五步恢复、同一执行者与新回执世代、旧键历史恢复、三世代未知 ACCEPT 回复、当前授权撤回、并发 CAS、四类事务回滚、实际材料正文/哈希漂移以及坏前驱/指针/Case 绑定拒绝。已有分派/回执/owner 路径专项 108 PASS；这些专项不重复加到全量计数。

最终同源真实浏览器 **1 PASS / 80.91 秒**。两个浏览器前原 API 创建的新 Case 中，一个实际走完初次五步核对、显式本地关闭和重开、四个真实材料版本、原组合重新关联、明确同一执行者 reoffer / 本人 ACCEPT、新合成回执 v1 / 企业 ACK、第二次 P1–P5 核对与本地关闭。五个 CaseStep UUID 不变，旧回执不被重绑，两个世代各有独立步骤/真实回执，13 个计划事件；最终 Case 是 WAITING_CONFIRMATION、目标仍未完成。另一个新 Case 用于晚到读取与上下文隔离，不能计为第二个已完成全流程。

实际验证提交后丢回复：原分派 body / key 精确重试，不能创建第三 offer；前置未核对时原生提交按钮触发 409，历史回执按钮禁用；刷新/重载保持已提交步骤历史，晚到 Case / 身份响应忽略。七张权限相关表摘要前后不变，无浏览器启动后的 setup 写入、模型调用或新授权，自有 API 已停止。全部 15 张 1200 / 390 / 320 截图由独立审阅者实读核对；17 项产物 hash 对应本轮最终目录 `.runtime/eng099-product-18e6b5eb1f8c`。两次先前浏览器 PASS 因后续真实源码守卫修正保留为非最终证据，不累计为最终通过次数。

初轮 core 为 229 PASS / 2 FAIL：owner 只读路径将错误 Case 绑定改成 403 而非原合同的缺省记录投影，以及旧 schema23 断言；均已修正为完整当前指针绑定、错绑定不显示，schema24 断言。初轮 native mock 为 31 PASS / 2 FAIL：句柄指针归一化及未知异步完成的生命周期保留缺陷；已修复并增加独立金标准。原日志/JUnit 保留，未删用例、增加跳过或用标签替代业务操作。

当前收集 **2088 项 / 75 文件**，四片 **529 / 517 / 534 / 508**，953 个 AST 诊断 ID；全局与四片实际稳定 keys 多重集精确一致，ENG098 的全部 1968 项保留。268 个源码文件已冻结，manifest 与当前文件 hash 一致，原 25 分钟 / 1500 秒工程预算及各子预算不变。此处 collect-only 尚不表示完整运行或原生 Windows 已通过。


ENG099 最终本地验证：完整 Linux **2079 PASS / 0 FAIL / 0 ERROR / 9 既有 native SKIP / 2 WARN，500.87 秒**，2088 项 JUnit 对应当前 collection；268 个冻结源码文件零差异。恢复专项46PASS，当前原生候选 Linux fake/ABI专项150PASS，最终实际浏览器1PASS/80.91秒，15图与17产物hash已独立核对。专项不重复计入全量。当前75文件/四片529/517/534/508/953诊断ID与1968旧keys保留，预算不变。完整回归只证明该Linux源码，原生Windows、目标file-ID CAS、全量workflow/Win11、正式业务发布及外部履约仍未验收。普通推送及首次精确HEAD的CI终态由本任务最终同步运行时证据记录，不在提交前预写成功。

完整回归日志 SHA256 `1a9cb45e7b3fd11a848e7b68a43d76a1b8d276063134c7b6919b209acbe866e2`，JUnit SHA256 `f3e4c836bbd85e644b53623a27e5e5da0d9569b5eef363ac011aa132ff08f059`；冻结文件清单 SHA256 `232ecb8a518e196f3d02843eac06733367da74899b29510b80f28a154858704b`。
