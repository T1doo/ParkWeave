# 正常建单在途失联接管：实施前合同

基线 f585a34b23ac2d05994b3833363bdb86ef29fe03。完整读原分阶段计划、F1/TestSpecification及Store.claim/locked_execution/heartbeat、LeaseKeeper、ExecutionGateway、连续worker：本片覆盖AT17本地原子case.create的实际进程失联/旧fence回报，配套AT16/18/19；不签收完整AT17、真实模型/外部非原子动作、Windows实机或全仓。

原正常路径已实现：数据库时钟过期后claim以行锁/SKIP LOCKED换worker/fence；locked_execution核当前fence/state/DB租约，当前EXECUTE/动作授权重新核；LeaseKeeper独立线程/短连接续租。Case、Operation回执、Run终态、outbox同一事务；已提交终态不再领取，连续worker按原outbox去重消费。本轮首先直接实现该路径的真实进程故障验收，不另建预演运行器，不为了改源码新增协议；发现真实产品缺陷才修原路径，并冻结新源码重审。

测试仅自建Linux SYNTHETIC数据库及原fixture-a/b/c权限，正常configured_app、普通LOCAL模式与原连续worker，无fixture adapter/issued preview registry/复制proof/model-fixture/真实模型；原合法新库creation receipt只作初始化，之后不seed/migrate/新增或恢复Grant或手改Run/lease/Case/operation；仅第4切片按原owner路径撤EXECUTE。模型等待只用原已有CLI mock等待，纯本地不请求模型。租约用原CLI合法1秒边界；按DB clock真实过期，不UPDATE时间。

最小故障切片：
1. 旧worker实际领取并连续heartbeat；第二普通连续worker不能抢有效租约。按已知Popen PID+create_time暂停旧worker全进程（含heartbeat），原租约自然过期，新worker合法接管并唯一建单；恢复旧进程触发原Conflict，原cached fence的heartbeat/prepare_dispatch/finish均拒绝，不污染新结果。
2. 自有owner测试连接仅LOCK原outbox表，普通worker运行至INSERT outbox等待该锁，证明本地提交事务正在进行；终止已知worker，释放自有锁，等待其数据库连接退出、原未提交业务回滚。自然到期后新连续worker接管，唯一Case/Operation/回执/终态事件。不开触发器、fault-stage或故障旁账本。
3. 仅LOCK原deliveries表，普通worker建单已提交，原消费者在INSERT deliveries等待；worker退出后原消费事务回滚，新连续worker不重领终态Run，只消费原事件，Case/Operation/receipt原字节保持，event_id逻辑delivery唯一，旧fence仍拒绝。
4. 当前撤EXECUTE或正常HTTP取消：不恢复权，接管不产生Case/新动作；保持原FAILED_SAFE/CANCELLED与可见已知事实，旧fence拒写。

测试所有SQL观察/oracle取原正常库，PG blocker只能测试自己持有的锁，退出用同连接rollback/close。所有进程控制仅自己的已记录Popen PID+create_time，SIGSTOP/SIGCONT/terminate；不杀/清未知进程/锁。单窗一个PG/API，故障验证所需两个worker并发属于同一案例；窗口串行，不另起PG/browser并发。退出确认所有自有代际不存在，原事务已结束。原未知postgres/chromium僵尸只读记录，不操作。

每窗唯一短/tmp目录、独立pytest/API/worker日志、checkpoint JSON和截图；私有plugin将原模块OUT重定向本窗artifact，保全旧公共browser同名产物。公开只源码/合同/计数/安全结论/hash，无UUID/会话/DSN/SQL原正文/原日志。原所有失败保留。源码冻结、相关实际回归及独审精确故障路径通过后普通候选/dev快进推送；main/force/deploy/真实履约/网络安全权限不改。

P4/P5完整发行者退出的持久资格仍OPEN，本片普通身份/原子动作不依赖该缺口，不将普通Case NEEDS_INPUT、LOCAL_CASE_CREATED当P5关闭或外部履约。Windows/fullAT17/完整外部未知效果继续NOT_RUN；故障适配器相关回归单独明确FAULT_INJECTION而非本片正常路径证据。
