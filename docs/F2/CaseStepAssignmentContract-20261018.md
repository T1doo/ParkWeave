# 本 Case 受限步骤分派合同

基线 a31cb8b551a8f335387e83174e94c789dbb2c165；原 V1 产品§3/§5.5/§6.4 case.assign、F2-T04/AT12/35的有限工程片。目标是新诉求不靠运行中owner补Run assignment，能经当前负责专员明确分派、本人接单、人工合成回执及企业核对。不是失败报告、预览、Run READ授予或正式AT签收。

1. 生产默认关闭。仅显式 `create_app(..., case_step_assignments=...)` 可绑定精确隔离服务；`configured_app`没有环境开关/模块loader/发行入口。原dispatch/receipt的全部旧guard、Store Run guard、Native/角色SQL与普通工厂保持原授权；旧分派/回执另增加marker隔离拒绝，防止其被旧解释器重解；新app明确路由到受限服务，绝不捕获旧拒绝后fallback。
2. 原发行的fresh owned临时PG证明必须有效、连接精确绑定；构造时Run/Case/准备事项/assignment/分派/回执为零。只配置已有同park/org企业owner、负责专员及1–8名已有READ执行者，不创建身份、Grant、技术权限、目录、批准、凭据或DDL。该依赖的短期运行窗最多3600秒，业务数据库与原发行证明都须当前匹配。仅原显式依赖可重读其记录；普通新Store/API不获得步骤或Run权。
3. 新事项由原API/worker创建，原双槽材料经独立REVIEW和owner CONFIRM；本片只分配固定的“合成人工办理回执”任务，不分享原诉求正文/材料/事实。负责专员必须恰为当前preparation.reviewer_id且有READ/REVIEW_ASSIGNED；owner有READ/PREPARE/EXECUTE；受益人是配置中已有同域service_executor且有当前READ。原当前service catalog必须合成且版本精确。原Case取消守卫及已有计划P1/P2前置仍检查；不冒充原P3–P5目标或履约通过。
4. OFFER复用原分派表/offer/不可变事件，保存独立合同marker、精确Case/Run/preparation/服务与资料revision/hash、全部参与者当前principal/授权代际、固定最小字段/动作及不可续期截至时刻。每offer最多300秒且不超过依赖窗。明确理由及原expected revision/key/CAS必需；同键重放不续期、不同指纹冲突。已有同Case旧非本合同业务记录拒绝。没有现有Run assignment不是降级理由，而是本独立合成步骤模式的初态要求。
5. 任意该Run的assignment行（含inactive）、native协议/激活历史或混入其它隔离/Native provider均拒绝；不会代替原授权、绕过原撤权/到期或将managed行降级。owner-only assign_status从不用于本链。未知或损坏marker/历史拒绝。
6. 本人读取仅自己的offer/必要服务与状态、本人回执及事件，不读取Run/企业档案/材料。不跨Case、不读他人offer/reason；专员只见自己的Case分派和状态，不取回执正文。ACCEPT/DECLINE必须本人、当前offer及版本；ACCEPT以原事务创建唯一原receipt-step和事件。SUBMIT只有当前已接单者，人工SYNTHETIC正文/来源；ACK只有原owner，核当前SHA。原REQUEST_CHANGES/REOPEN语义保留；execute-local、legacy CREATE与跨执行者交接在本模式不启用。原_event保留本地通知outbox意图；本片不授予通知读取或对外送达权，旧通知路径仍按原guard拒绝/抑制。
7. 每次操作和最后一次锁等待后的事务返回前重核当前权限/代际、资料/目录版本、同Case、原offer与数据库时间；等待跨期拒绝回滚；无提交触发器，不宣称物理COMMIT瞬间的原子到期。变版、撤权后恢复或过期不复活旧步骤。专员仅凭当前本人READ/REVIEW_ASSIGNED及本Case绑定，可在受益人撤权、材料失效或offer过期后明确WITHDRAW当前未接单或已接单责任，停止后续新操作，保留已有回执与全部事件；不释放资源或重写历史。首片每Case仅一个OFFER，DECLINE/WITHDRAW/到期后均不能换key续发；ACCEPT/SUBMIT/ACK等所有新动作共用首次固定5分钟截止，接单不延长。来源变化/撤权/到期后历史只对仍有本Case权限的owner/专员读，执行者不凭历史绕门。
8. 原GET恢复控件复用实际原key，只核既有ACCEPT/SUBMIT事件和真实正文SHA/版本/指纹，COMMITTED不等于当前可写，NOT_OBSERVED不证明请求失败；不自动重发、ACK或VERIFY。标识/精确字段不匹配拒绝，当前撤权优先。
9. 原页面重用分派、接单、回执控件，明确隔离步骤范围、期限与Run未授权，未知结果沿原只读恢复。不新增同义预览。完整原HTML NodeVM+实际ASGI/自有PG可验；没有真实浏览器/Windows/正式AT或真实业务、模型、部署结论。

必须验证：零业务初态的正常新Run到人工回执/核对且七类权限表不变；普通Run GET与原默认分派仍拒绝；当前角色/跨域/其他Case/未列执行者；固定最小视图无私有值；WITHDRAW、到期、资料/目录变版、授权代际变化；旧/Native/managed行无fallback；原CAS/并发/事件回滚/原键冷读；原正常legacy路径回归。测试fixture与真实来源/安装缺口严格分列。
