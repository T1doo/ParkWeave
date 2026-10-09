# 资料交付异议合同（实现前冻结）

基线 88403af18b95b361114b303c3fae636f286d91b4；原 V1 F2-T07、产品 §5.5/§7、PR0-CoverageAt-a1e6022。仅 SYNTHETIC 当前双槽资料交付；材料文本包已经完成，本片不重做。

企业在已人工核对的双槽资料上 RAISE；原获派专员 RESPOND；企业明确 ACCEPT_RESPONSE 或 KEEP_OPEN。回应不自动解决；KEEP_OPEN 后须专员新回应。来源变化时显示 STALE，企业须在重新人工核对后 REBIND；保留全部原绑定、回应和决定，旧回应不能解决新来源。ACCEPT_RESPONSE 只表示当前资料异议已明确复核，不代表 Case 完成、资格批准或现实履约。

绑定包含 preparation/Case/Run、原 owner/reviewer、服务 ID/version、资料 revision、双槽 evidence ID/version/真实正文 SHA256、原请求 revision/内容 hash（未明确原请求时 revision 0 和 Case 原目标 hash）。写入同时要求资料 revision CAS、异议 version CAS、绑定 hash CAS；企业决定另绑定当前 response event UUID。当前来源、材料人工核对状态和当前身份/原准备权限在事务内重验。来源 revision 的历史不因后续反馈事件推进而失效；任何实际来源变化不得自动重绑定。

存储只使用现有 preparations 的 revision 更新与 preparation_events 的 INSERT（同事务）；无新增角色/Grant/通知/模型/外部副作用。schema26 仅扩展事件 action CHECK，沿用 schema25 的已验证新建隔离数据库 receipt，普通已有数据库不得自动安装。应用角色没有事件 UPDATE/DELETE 权限；以事件折叠读回异议，禁止覆写历史。每事项最多8个异议、32个异议事件，且沿用总64资料 revision上限；说明1–1000字符。不可变指事件在应用角色下不可改，owner 仍为数据库信任边界。

幂等键使用现有 actor/key 排他锁和事件唯一约束，原键/原body重试返回原事件；同键异body冲突；权限先于重放。只读 recovery 仅查当前有权原 actor 的原 key，不重放、不提交；NOT_OBSERVED 不代表未提交。页面仅持久保存原 Case/key/actor 编号句柄，不保存 token/说明/body；冷刷新后重新输入本人会话只读核对。403清私有视图，迟到身份/Case/generation响应丢弃；未知时禁新写，未核实 absence 保持未知。

未决或失效异议阻止原 CONFIRM 和本地 Case关闭；回应、其他材料命令或来源更新不消除未决。Case实际状态仍沿原合同。验证使用隔离新建 PostgreSQL、当前普通API与原页面真实HTTP/Chromium，包含冷恢复、撤权、越权、跨企业、换版、并发、迟到、重复、隐私负例。Windows/LIVE/完整42 AT/EX仍未签收；不修改main/强推/部署/网络凭据配置。

实现细化：绑定另保留原人工 REVIEW 事件 UUID/revision、目录来源 hash 与事实用途 descriptor hash；资料重开再审核不会复活旧回应。schema26只由既有 Linux 新建隔离库 receipt 安装；原 native receipt 路径仍止于25，原25读者兼容，异议写入关闭。目录只有既有owner合成初始化来源，应用角色仅SELECT；没有为了读锁新增UPDATE权限，owner来源变更仍须与事项/主体锁协作，越过锁的DB owner为信任边界。
