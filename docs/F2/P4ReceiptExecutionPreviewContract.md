# P4 原本地报告到模拟企业核对：实施前冻结

基线 `f505a8e8c075bdb6671b83624cb4bea24ceaff4d`，P3获审运行树 `345c95701851f16c71a3a36cb9548ee043a9c5b0`；root唯一源码/Git写入者，独立候选开发。依据原F2-T04/T05/T07、产品§5.5/§7.3、ENG106、原P4注册动作及PR0覆盖映射，不改原映射，不将报告说成原材料交付或真实履约。先冻结本合同及[SQL闭包](P4ReceiptPreviewSQLClosure.json)，后实现；任何扩大先修订冻结。

实际原P1/P2/P3 ACCEPT产物作为本轮P4前驱，同一隔离Case/Run/preparation、accepted offer及AWAITING_RECEIPT step逐字段复制到新影子事务。实际调用原IsolatedLocalExecutor.generate和executor_receipts.command(ExecuteLocal)生成结构化接单一致性报告、SUBMIT新回执和事件；企业角色的独立模拟token以当前step revision和实际receipt hash执行原ACKNOWLEDGE或REQUEST_CHANGES。不能手填text/source_label替代执行，不能自动纠错、重生成或ACK未决；REQUEST_CHANGES保留CHANGES_REQUESTED和历史。不得增加业务服务、模型、任意代码执行或外部效果。

原owner READ/EXECUTE/PREPARE、双资源READ/HOLD、原获派专员READ/REVIEW_ASSIGNED、精确Run唯一executor READ及原当前managed租约继续为外层交集。另须实际发行且实时匹配的原临时数据库proof、原附加IsolatedRunAccessBridge和已显式启用原IsolatedLocalExecutor；缺失、legacy、租约失效或多执行者均拒绝，运行时不安装正式schema/Grant/assignment。外层资格、generation、原Case/Run、资料revision/两槽ID/version/hash、请求revision、P1–P4精确动作/适配器和版本进入source绑定，当前授权先于历史和幂等。原正式数据库只作已有资格读取。

P4仅28个已声明影子表、112个精确SQL模板；连接search_path固定pg_temp且先建立全部影子表，代理拒绝未知/显式public业务SQL、commit、新连接和任意cursor操作。为原proof校验开放封闭cursor.execute/fetchone及只含host/port的info；不暴露DSN。原managed Store要求guarded connection，代理继承原guarded连接类型、保存待复核集合，但不允许commit；外层与影子当前资格在结束前再次核验。原proof的集群/数据库元数据读保留，不stub或伪造证明。

影子授权使用原IsolatedRunAccessBridge/RunAccessEngine，仅为本轮模拟原企业/专员/执行者、实际新Run签发模拟REQUEST/APPROVE，事件和lease存在专属临时0700 journal及pg_temp；不复制或修改正式权限，不表示真人审批。桥接构造和原本地适配器的两个精确ALTER仅作用于已存在pg_temp表；已有源schema的metadata只读取，其正式表不变。使用原发行proof匹配的owner连接仅建立/使用本轮临时表，所有公有业务写入被封闭。原适配器当前接单/材料/租约、回执和不可变事件重验不替换、不降级。临时journal与PG事务finally清理/rollback/close，安全产物含原模拟授权事件而无token/DSN。

新的独立scope、0700根/0600 SQLite、不可变文档/proof、128总记录/每Case16、正文与proof各64KiB、BEGIN EXCLUSIVE、当前权限优先、三源CAS、same-key幂等/异body409、并发/基础设施失败及提交后丢响应GET-only恢复沿用P3防护。旧P1/P2/P3格式、文件和产物不迁移、不更改。独立proof绑定完整P1–P4产物、receipt/metadata/报告hash、全目标及显式企业decision；单改正文并重hash不能省目标或冒充ACK。源变化保留STALE历史，仅明确新预演重绑定；source_atomicity=false，快照不是全来源原子保证。

原页面提供明确P4预演、ACK/REQUEST_CHANGES选择、历史/GET核对/结束恢复；仅独立五不透明字段恢复句柄，8条/24h，无token/正文，Case/身份/草稿变化、撤权403和迟到回复清私密视图；未知不自动POST。展示实际执行ID/hash/回执版本/模拟企业decision、CHANGES_REQUESTED未核对、完整目标/P5未执行、formal_writes=0/Case未完成。实际P3四个PENDING outbox保持未消费、notices空；无新通知消费者。

验证真实HTTP/PostgreSQL/SQLite/Chromium、原页面冷恢复和同一合法发行进程内的API/Store/预览对象冷重建：本地generate实际调用、原SUBMIT/ACK/REQUEST_CHANGES、历史hash/材料换版拒绝、当前租约/角色/跨企业/撤权、source CAS、迟到/重复/并发、丢响应前后只GET、篡改proof、原正式UUID消费403和隐私/窄屏。检查全部public业务表逐值（排除原authorization_audit诊断）、正式schema/权限集合及旧P1/P2/P3文件字节不变。保全每个失败窗口，不汇总成一轮PASS。

正常候选推送后精确runtime SHA独立审查，阻断先修；独审自然窗口/资源关闭后才普通ff-only整合dev并核验实际远端。完整AT14、全仓、Windows、P5、正式受理/服务目标/Case完成均未签收；原本地报告不等于材料服务。禁止改main、强推、部署、凭据/安全网络配置、真实业务或模型。旧Windows修复和资料包导出不重做。

开发闭包修订：原managed桥接使用ON CONFLICT(principal_id,run_id)，P3的仅DEFAULTS影子缺少对应唯一索引，原SQL明确拒绝。先补冻结：仅run_assignments的可信临时表建表复制原INDEXES（不复制FK/触发器），原112代理SQL不扩大；再实现。此影子临时journal的ProjectionPending不代表外层P4提交，转为503并只GET原key核对，finally销毁临时空间；不返回正式decision_committed含义。原注册adapter_ref必须精确executor-receipts，临时文件名遵守原.run-access.candidate.sqlite3门，既有拒绝不放宽。

恢复合同边界：原ENG106临时FixtureDatabaseEvidence是进程内实际发行对象，不能序列化后在新API进程伪造恢复。P4不重签该证明、不补正式Grant；真实新进程验证默认关闭/无发行proof时403且保留原SQLite字节。同一合法发行进程内重建Store/API/预览对象、原页面冷恢复和GET-only核对分别测试，不声称独立新PID下原managed链已恢复。完整跨进程发行proof/lifecycle恢复仍是未签收缺口。
