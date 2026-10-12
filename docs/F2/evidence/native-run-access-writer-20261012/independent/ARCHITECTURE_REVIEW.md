# 受限 native writer 架构审查

结论为 STATIC_ADVISORY_ONLY，审查基线是 `9ea666620bdf9b88bca395e7ccf471ec7901a038`。新 writer 尚未冻结，本轮没有测试、PG、浏览器、部署、凭据配置、Grant/registry/SQL 权限或源码/Git 写入；旧 4384/201 成绩及签署不转签新功能。

建议采用独立 Unix domain RPC writer。API 只持 app DSN 和精确受信 client/context；writer 私有连接在同一 PG 事务内验证真实 session、当前权限、明确政策、版本、原键和原因，再提交签名事件及精确 assignment。controller 只用原已发行的 fresh owned fixture 证明建立 reference，并始终标为 OWNED_SYNTHETIC_REFERENCE。生产受限身份、私钥、受保护 endpoint、启动绑定和安装需要后续单独批准；本轮 configured_app 默认关闭，不执行安装或实际赋权。

最重要的既有边界是 `roles.sql` 对 runs 的表级 UPDATE：新 JSON 列继承该写权限，结构合法及 append-only 不等于审批人已认证。writer 必须验证所有 REQUEST/APPROVE/REVOKE/ACTIVATE，不能信任 app 自造的 APPROVED。MAC 应绑定明确的用途、policy、数据库、主体、Run/Case/tenant、来源版本、原请求和有序历史头；必须拒绝改写、重哈希、复制或未签发数据。保留原 APPROVE 的 NON_EFFECTIVE 事实，ACTIVATE 是另一个明确动作。

资料 REVIEW_ASSIGNED 与 park_specialist READ 不构成 Run 审批权。政策须指定同租户的已有具名审批/撤销人，并验证其独立于 owner 和 beneficiary。目标只允许已有 service_executor 的单 Run READ；业务 ACCEPT/manual SUBMIT 仍受独立分派、当前责任世代和原业务守卫约束。没有新 Grant 或信任 registry。

VERIFY 需要同时满足两项条件：SQL 不获取任何新的 principal/native advisory 锁或行锁；RPC 调度不被等待 parent 的 COMMAND 占满。否则 API 持有 parent/身份锁等待 VERIFY，而 writer 命令等待该 API 的 parent，可能形成跨 RPC 等待环。验证应有独立只读连接及受限并发容量，不能共享命令事务或全局命令 mutex。这是静态风险分析，尚未实测死锁；冻结后须用真实 PG 排队反例验证。

启动信任必须来自独立 controller 或受保护配置，不能采纳 HELLO 自报身份。校验真实 SO_PEERCRED、socket inode/类型/owner/父目录、进程实例、boot nonce 和 policy SHA；超时、换 endpoint 或断线均明确拒绝，无 TCP 或直连 owner 降级。合成进程共用 UID 不证明生产 OS 隔离。有效 provider 也要坚持精确 client/provider 类型、同 Store 和可信类方法，拒绝实例覆写。

真实 API Store 的数据库身份必须本地核对；正确 DB1 writer/MAC 不能放行 DB2 Store。生产 app 不需要新增读取 pg_control 的权限：由私有 writer/controller 核系统身份，结合 app 现有可读端点、数据库 OID/name 与 schema 绑定。API、PG 或 writer 重启后须独立明确 rebind；APPROVED、assignment 和旧 test permit 不得自行生成权威。必须定义 issuer/key epoch 和轮换规则，保留旧 receipt 与 GET 恢复。xmin 是当前 MVCC 指纹，不能单独充当跨恢复或新集群的持久授权代际。

有效期须明确 UTC、最长 1h、审批只能缩短；owner 当前权限、精确 CAS、原因和严格 true 确认由 writer 重核。无 4/8h 或 fixture TTL 默认，不覆写 legacy、同 lease 不续期。合同需写清是否允许撤销后的新独立 REQUEST，避免变相延长。REVOKE 只依操作者的当前明确权力及 CAS，不能要求受益人仍有 READ、材料仍 fresh 或 lease 未过期；owner 自身三权限要求按合同明确，不自行放宽。

MAC 历史真实性与当前可用性分开返回。原键 GET 不重发 POST，不修表、不隐式失效计划、不释放预约。Case 进展、取消/对账/关闭时保留仍有权的历史 READ；新激活和业务写继续受服务端守卫。保留 native marker 不可降级、guarded commit 重核、列表 post-filter、执行者 parent、收据 base、通知 OPEN/outbox 和依赖读取的真实消费者覆盖。

ARCHITECTURE_REVIEW.json 给出 12 项源码位置风险及后续独立反例计划。这些是实施前条件和建议，不是新功能 PASS 或生产启用批准。
