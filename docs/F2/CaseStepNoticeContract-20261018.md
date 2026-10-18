# 本 Case 受限步骤的站内通知

基线06186eef397a26bcf8ed8b6b3f07d6b1e9aa5cc5；接原V1§5.5的notice.create与F2-T04站内协同。复用CaseStep原同一显式依赖、原dispatch事件/outbox/inbox/分页及OPEN/MARK_READ时间戳，不新建身份、Grant、分派权限框架或外部消息通道。

1. 生产默认关闭、configured_app不变。原worker CLI不读取或发行CaseStep依赖。只有受信调度者显式把原精确CaseStep对象传给原consume，API同对象显式接入；原fixture数据库/短期依赖窗/唯一offer/固定300秒截止/当前权限代际等合同全部保留，普通SYNTHETIC不要求外部正式五证明。
2. 队列按所属preparation/dispatch首次OFFER是否含marker分隔，包含后续本身无marker的ACCEPT/DECLINE/WITHDRAW。旧consumer跳过marker意图并保持PENDING；显式consumer只处理本依赖原contract_id意图，不吞legacy/他issuer/无法分类意图。候选SQL在LIMIT前按lane过滤，FOR UPDATE后再次核分类与可交付条件。consume的False只表示本次有界扫描没有进展，不证明队列已排空；损坏/忙碌自有原件继续隔离，受信调度须按原cursor继续独立扫描，不自动循环至无界。marker仅用于分流，不是授权；原默认guard和列表隔离仍拒绝标记记录，不捕获旧拒绝后fallback。
3. consumer使用原outbox当前recipient行，不读取/生成登录token，不从事件创建身份。复用CaseStep当前principal/同域/父Case/Run/资料及原marker检查；完整事件证明包含OFFER、ACCEPT→CREATE、DECLINE/WITHDRAW精确字段/原指纹。API仍用原实际会话，并在最后锁等待后重核当前会话、权限、原件与数据库期限；失败回滚本次已读/送达修改。
4. executor只读本人当前有效OFFER/ACCEPTED lineage；权限/资料/目录换代、到期、DECLINE/WITHDRAW、Native/legacy污染后读取及命令拒绝。已送达通知不缓存权限。owner/负责reviewer可在依赖整体有效窗内按当前本Case权限读最小历史并OPEN/MARK_READ；不因此取得当前业务可办权。actionable仅本人执行者+当前live OFFER；历史/失效/已接单offer不显示可办理。撤权前未交付且本依赖确属对象的意图准确SUPPRESSED、不因恢复而复活；未知/损坏原件或他issuer意图保持隔离PENDING。所有行和时间戳保留。
5. 列表与正文只含原事件/Case步骤标识、动作/版本/时间/最小状态，不含原goal、材料、分派reason、会话或正文。分页绑定原模式与依赖contract_id，每页仍重核权限。普通新API/冷Store无依赖不继承通知权；过期通知不能借跳转绕过原业务guard。
6. 原协同页从“我的资料准备事项”/“查看此事项内部分派”发首次OFFER；executor从“刷新我的站内通知”→“查看通知”→“打开原事项”→“确认已读”。OPEN仅记录打开请求，MARK_READ须独立明确点击，跳转不自动接单、回执或完成Case。新模式说明步骤范围、期限与Run未授权；迟到GET/OPEN/MARK_READ/403不能覆盖新身份或新列表。
7. 只验实际loopback HTTP/ASGI/自有PG及完整原HTML NodeVM；不运行浏览器、Windows、正式AT35、真实来源/业务/模型或外部通知。不安装writer、不改roles/main、不强推、不新增费用/凭据/安全网络权限，不重试root/seal拒绝。旧129不重跑或转计；新片定向原通知回归与独验精确去重，全部失败保全。
