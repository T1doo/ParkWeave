# P4历史跨API进程只读恢复：实施前合同

基线28f7a4f659626c4e2d2c0736bd7827b1ffe41381，获审原P4运行fa80309a9cc728bd6e43a5f9c47d1cb317791df5。root唯一源码/Git写入者，独立候选；原资料包和P1–P4执行树不重做，先本合同后实现。原FixtureDatabaseEvidence仅进程内发行，现有机制不支持原发行进程退出后的重签或反序列化；本片不得增加这类入口或放宽旧接口403。

本片限同一个仍存活、最初实际创建并发行原临时夹具证明的权威进程。该进程保留原bridge、当前RunAccessEngine/租约、原本地适配器及P4对象，提供显式启用的本地Unix socket只读历史代理。原证明绝不传给API客户端、写文件或重新发行；代理不是新Grant或独立政策批准。新API进程通过独立仅GET端点读取原已提交P4历史，每次代理实际调用原ReceiptExecutionPreview.read及完整当前owner/角色/项目/双资源/原专员/精确executor/managed租约/原live proof与本地provider校验，不缓存验权或历史。原P4GET/POST、正式Run/receipt/批准接口保持原资格门；新客户端没有原bridge或local provider，不能执行或回退。

仅新GET /api/preparations/{id}/receipt-execution-history及/recovery/{key}，没有POST/自动重放/generate/SUBMIT/ACK。客户端只接受代码级显式附加、精确类型和LOCAL Store，默认关闭。Unix目录必须绝对、临时、自有0700，无symlink；socket0600、自有UID，客户端校验SO_PEERCRED的当前服务PID/UID及Linux /proc启动代际，文件inode前后保持，服务身份/namespace/原P4合同与数据库身份逐次匹配。权威失联、代际改变或socket替换全部拒绝，不重新绑定、启动或补权限。仅Linux隔离合成环境，Windows关闭，不部署、不更改网络/凭据配置、不开放外部listener。

封闭协议只允许固定字段的READ操作及UUID/有界key/token/期望身份；没有任意方法、路径、SQL、DSN、pickle、报告输入或权限指令。长度前缀JSON，单请求最大4096字节，单回复最大2MiB、3秒socket timeout、单处理线程及最多8等待连接，未知操作/超界/错误编码拒绝，连接always关闭；不打印token、证明、报文正文或原异常。错误仅403/409/503安全分类。代理使用原P4封闭存储读取，不新增SQLite/PG迁移，不改变source/body/proof/fingerprint/事件/授权日志字节；原来源换版仍保留旧历史和STALE，未决不自动解决。原authorization_audit诊断表可由原验权路径产生，其他全部正式业务逐值和schema/权限不变。

测试必须两个真正不同API PID：旧只读API读取既有已提交历史、确认退出/不存在后启动新API读取，原issuer PID明确仍存活且与两个API均不同。单独报告这一范围，不将同进程重建对象或403拒绝称为跨PID恢复成功。合法ACK及REQUEST_CHANGES历史、重复GET/并发、来源换版、原key未知、撤权/到期/缺provider/proof/错误身份/跨企业、篡改正文proof/socket/issuer死亡、禁POST、无自动执行、原P4/RunAccess及旧P1–P3字节和正式业务零写；真实HTTP/PG及原页面冷GET另有窗口。原完整P4相关模块回归、精确源码冻结/独立审查、故障窗口保全；获审后普通dev推送和实际远端核验。

原发行/权威进程终止后的完整冷启动、PG重启/WAL、真实材料服务交付、P5/Case完成、真人许可、正式Grant或新权限、通知消费/外部效果、模型调用、完整AT14/全仓/Windows均不在本片。遇真实权限/安全拒绝停相关动作，不模拟证明或绕过；代理不可用保持拒绝。main不改、无强推/部署；旧Windows修复延后。本方案是新API客户端在原合法存活权威下的历史只读恢复，不是原证明跨进程迁移。

独审首候选2c964296488e42f2b162589b12e919647c96c13f实际发现浏览器可把另一原key的合法已提交历史响应显示为当前未知key的结果，候选阻断且故障保全；597项回归通过不能抵消。修复前明确回复相关性：客户端和页面均仅接受COMMITTED或NOT_OBSERVED；COMMITTED必须有精确当前原key、同namespace/scope/preparation绑定、正式写入0的原文档，且在回复history中唯一逐值相等；NOT_OBSERVED必须result=null。页面只接受只读transport标识及automatically_replayed=false，未知状态/跨key/绑定失配均保持空私密视图与明确错误；客户端失配503，不回退、重新执行或放宽原资格。测试用原权威对另一实际原key执行合法GET的完整真实回复模拟响应错配，不伪造报告正文/hash/proof。首SHA独审BLOCK及原自然窗口永久保留，新SHA须重新冻结与独立复审。
