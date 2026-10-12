# 默认关闭的生产合同与独立受限事务 writer

基线 `9ea666620bdf9b88bca395e7ccf471ec7901a038`；开发分支 `dev/f2-native-run-access-writer-20261012`。用户已委托统筹决定下一步，统筹于 2026-10-12 明确选择方案 A。本片授权代码、文档及原允许自有合成 PostgreSQL 验证；不授权生产安装、实际生产赋权、凭据配置或技术权限扩大。根任务唯一源码/tests/docs/Git 写入，独审仅自己的运行时证据。

## 已选定业务政策

申请/激活仅当前企业 owner，READ/PREPARE/EXECUTE、原因、严格布尔确认、精确版本及原请求键继续生效。审批人是具名已有同租户 park_specialist，独立于 owner 和受益人；必须明确声明该 Run 的 APPROVE/REJECT/REVOKE 范围，资料 REVIEW_ASSIGNED 不推导此权。受益人仅一名已有同租户 service_executor 且已有 READ。

首批只允许一个具名普通 SYNTHETIC Run/Case，成功建单且操作 VERIFIED、来源精确；绑定 park/org/owner/Case/preparation/Run/当前资料与权限代际。READ 及原单独分派后的本人接单/人工回执路径可达，仍需各自业务守卫，不增加 CONTROL/EXECUTE/FILE_READ。拒绝覆盖 legacy、isolated 或未知 assignment。

每次明确 UTC 起止，最长 3600 秒，审批只缩短；不自动续期/续授。owner 或具名审批人可撤销。撤销/到期/资料或权限变化后不能复活旧租约；历史保留，取消 Case 不释放资源，原独立释放仍按原授权。合法 Case 进展、取消、对账、本地关闭保留有权历史 READ，业务写仍由原 Case 守卫拒绝。

每份外部 policy 最多一次 REQUEST；REJECT/CANCEL/REVOKE 后不得借新键再次申请实现续授，须另经明确政策决定。REVOKE 校验当前具名操作者/READ、原请求与当前 CAS，不要求受益人仍有 READ、旧资料仍 fresh 或原租约尚未到期；撤销不能被有效访问条件反锁。申请/激活 owner 的原三权限要求不放宽。 外部 policy 的 UTC 期限是 writer 新命令权限的截止时间；其自身到期后所有新命令（包括 REVOKE）关闭，当前 READ 也失效，原键和历史 GET 保留。旧 lease 到期而该外部 policy 尚有效时 REVOKE 仍允许；不承诺超出外部权限期限继续写撤销事件。

## 应用与 writer 分离

普通 configured_app 保持关闭，不读取环境布尔值或数据库 APPROVED/assignment 来创建权威。新 Policy 是业务合同，不能单凭其 JSON 启用；必须由 host 显式附加受信 writer 通道，核对当前数据库、声明 scope、独立 writer 身份及 policy SHA。旧 DecisionTestPermit/ActivationTestPermit 不转为该权威，不跨进程复制注册表。

API 仅持原低权限 app DSN 和明确 pinned endpoint/公开 scope，不能持 writer 数据库凭据或收据签发密钥。writer 在独立进程中只接收有类型 COMMAND/ACTIVATE、真实会话、原键和精确 Run；内部重新认证，不接受客户端 actor_id、SQL、DSN、任意对象 setter 或 SIGN。

writer 复用原 parent → native Run advisory → Run → assignment 锁序；原键按 actor/key 序列化。REQUEST/APPROVE/REJECT/CANCEL/REVOKE 与 ACTIVATE 的持久收据由 writer 独立签发。APPROVED JSON、客户端自造事件和未签发的旧 decision/activation 不能授权。全部当前权限、来源、区间、CAS 重核在同一事务内；activation event 与 assignment 原子提交，失败全回滚。

现 app 对 runs 的 table-level UPDATE 会覆盖新增 JSON 列，不能误称这些列已变为不可写。新 consumer 必须验证 writer 来源证明、完整不可变事件/head/lease 关系及当前 policy；原 SQL 不变，直接伪造 APPROVED 或旧签发回放不能取得 READ。原共享 Store exacttype predicate、guarded commit、executor/receipt/notices/collections 使用同一当前判断。验证接口仅验证既有证明，不提供签发 oracle。

## 当前合成 reference 与真实生产安装

本片 reference 使用 Python 标准库 Unix domain RPC，host 明确 pin 路径 inode/device、无 symlink 的父链、peer PID/UID/PID 实例、boot ID 和 policy SHA；不由服务器 HELLO 自采纳，没有 TCP/未知平台降级。VALIDATE/VERIFY 只读、短事务，不取 parent、principal/native advisory 或任何新共享/更新锁。命令与验证使用独立端点和独立有界并发，命令锁等待不能占满验证通道。RPC 有大小、超时和严格字段边界，不记录会话、MAC key 或 DSN。

reference controller 必须已有原 fresh owned fixture 创建证明，明确单 Run 和三主体、当前来源/权限及数据库 system identifier/OID/name。只有它可构造 OWNED_SYNTHETIC_REFERENCE bootstrap；writer 独占收据 MAC key，API 无 key，只经 pinned writer 验证。writer 使用原 fixture owner 的既有测试权；不新增角色、SQL GRANT、业务 Grant 或 registry。此测试 bootstrap 不是真实生产启用；同 UID Linux reference 也不证明生产 OS 隔离。

新的生产合同明确要求：具名已有受限 writer 服务身份、受保护启动/私有通道/政策及独立密钥来源、安装数据库与对象清单、最小精确 DML 或窄函数权限。生产 writer 不得采用 app 或数据库 owner/superuser 身份，不得持通用管理员权。生产部署 source/身份/技术权限的真实证明尚未提供，默认关闭。当前 reference 安装只使用原允许 UUID 自有数据库的现有 native storage，不调用生产安装，不更改 roles/白名单/迁移 32 或 setup 权限。正式安装 SQL 和权限方案须另列并获确认，本片不会执行。

## 跨进程与重启

API 新进程只能通过 host 明确重新绑定同一受信 writer 与原外部 policy；不由数据库记录自发行。新 writer 进程亦须同一受信 host policy/原独立签发 key，旧 endpoint pin 失效，host 明确 rebind 后才能恢复。数据库 restart 仅允许核对同一 physical cluster/system identifier、数据库 OID/name、来源与权限；bootstrap 与收据保持原期限，不续授。换库/换集群/dump-restore/不同 owner、来源变化、权限删建/撤授均拒绝。xmin 是该 physical fixture 的当前代际指纹，不被宣称跨逻辑恢复的永久权限版本。

无通道/无 policy 时普通冷 Store 只保持既有有权历史 metadata GET，native business READ 拒绝；GET 不修复或重新签发。 writer 元数据参与者由外部可信 scope 决定，未签 JSON 不新增读取身份。原键 GET 的 raw history 与 writer_receipt_verified 分开；通道不可用或证明无效时保留原收据但明确未认证，页面继续 UNKNOWN，只 GET 原键，不以未认证历史清除未知结果。 新签发收据包含经校验的 writer_command，签发证明覆盖其全部字段；页面还逐字段核对原正文（含版本、目标、确认和期限），异正文即保持 UNKNOWN。旧未启用 Native 的默认 null 确认字段不进入旧命令指纹；新增明确确认仍绑定新 writer 指纹。丢响应只 GET 原键核对 immutable receipt/current access，不自动重发 POST。跨进程证据必须由真实子进程及真实 owned PG stop/start取得，不能把同进程新 Store 算完整恢复。

## 实际验证门与交付

真实 PG/ASGI 与子进程：默认关闭/坏 host pin/异库/未知通道/伪造 policy/未签 ledger；1h、UTC、身份分离与 scope；全角色/跨租户/撤权/代际；原键并发/异参/跨协议碰撞；事件与 assignment 故障全回滚；parent 锁等待后的材料/撤销/到期以及业务 commit；旧通知、资源占用与独立释放；真正新 API、新 writer及 DB restart，显式 rebind与无权威拒绝，原 history/期限无改。复用原相关完整模块且另做独立 probe，原失败保全，窗口不累加冒称一个 pytest invocation。

不启动浏览器，历史 Chromium data: ERR_BLOCKED_BY_ADMINISTRATOR 不重试或换工具/URL。生产安装/赋权/安全权限、Win11/原生 IPC、真实模型/付费调用、完整 AT35 和正式 PR0 均 NOT RUN。结束时正常独立分支 push，核 remote SHA/保护分支/未提交未推差异，报告源码与交付完整 SHA。
