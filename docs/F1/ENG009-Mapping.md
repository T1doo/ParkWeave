# ENG-009 F1收敛与单项修订artifact

基线4ac2d2e3767491d997356f0eaf1e5613a1f35cc7。逐条按原V1 F1-T01—06及12个F1首次AT断言核对，阶段不改/标准不降；有限清单见Convergence。只实现无外部依赖的R1：正常worker动作前计划与模型接收真实本地receipt后的结构化修订artifact，独立oracle/持久恢复/当前授权读取。

范围仍一goal/可信case.create。revision1 PENDING_ACTION→revision2 LOCAL_RECORD_CREATED/WAITING_INPUT；goal保留，Case NEEDS_INPUT，外部NOT_SUBMITTED/线下NO_EVIDENCE，绑定前artifact SHA、op/Case/receipt/tool/provider调用ID。模型不得虚报资格/履约、添tool/改goal；失败保留已知Case，无隐式重发。版本为独立local plan projection，不冒充F2复合ServicePlan。

AT30逐字要求共享或明确划分总额、非流式完整校验、步骤上限、未知usage非零、注入不冒充上游。固定窗口总额+产品上限与持久usage覆盖总预算子集；产品设计第10节另明确默认每用户30RPM，长窗口会允许31个即时发送标记，须纯合成复现并列R2账号发送速率门有限待办。本轮只修R1、不同时实施第二项；真实provider速率/总额未知，LIVE预算0/请求0，不以固定窗口宣称限流合规。金额高级功能不移入F1。

Windows候选和原入口完全不改，不执行Windows；真实API/预算、安全配置继续BLOCKED。新增规格来源V1与本次委派；工程mock不可当真实AT02通过。一个有界实现回归commit/push后停止。
