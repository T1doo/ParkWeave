# 固定AT判据下的原服务冷输入与反馈重放

基线交付3bc1e96ccc6b6d73a5f1488bee644f92a15ddd97。root是共享源码和Git唯一集成者，开发、实际PG验收及独审在独立目录并行。原docs/验收规格.json与V1产品/计划AT-07/08/14/33/35的steps/oracle逐字冻结；不降低或重命名A/B/C，不修改既有全AT NOT_RUN状态。

本批实质缺口：ParkInstance只有API/facade，无需既存Case的当前实例发现和原页面新输入入口。增加默认关闭的本人有限配置发现GET、按配置映射的新材料表单，以及每阶段明确提交原业务命令和原key只GET恢复；进入既有V4受信服务选择、明确采用和原P1–P5入口，不自动规划/采用/办理。原确定性补件/回执反馈已经存在，不为验收新增不必要模型循环。

目录接口固定GET /api/service-instance-configurations，复用可选精确ParkInstanceConsumer，未配置403。返回scope=SYNTHETIC_PARK_INSTANCE_COLD_INPUT_DIRECTORY、actor_ref、park_id、read_only=true、automatically_replayed=false、provider_enabled=false、execution_enabled=false、new_grants=false、automatic_adoption=false、instances最多16。每项仅instance_id/config_revision/config_sha256/release_id/release_revision/release_sha256/service_id/title/supported_goals/fields，fields为两个原slot到input_field的映射；不带原材料、会话、其他企业或未获权资源。只收当前本人现有READ/PREPARE/EXECUTE/case.create、当前审核来源/角色/资源映射有效实例。allowed_goals是当前本人可用实例supported_goals的有限并集，额外未支持必需目标仍明确输入并保留。GET不写PG业务/consumer journal、不占模板源写租约，准入/阶段描述再核配置；实际原业务请求各按自身权限/资料版本合同核验，不承诺跨独立HTTP事务原子性。

页面先显式读目录，再选精确版本配置、填写诉求/必需目标和两项新材料，确认只准备原请求；不存材料/会话到localStorage，只保存本人opaque actor/key。准备facade POST的响应丢失只GET原cold key，NOT_OBSERVED/未知不自动重发。每个原业务阶段先明确prepare-stage，再分别确认提交其原请求体和原key；发送前持久写已发送标记（准入1、描述4、原业务5，最多10项），丢响应只GET facade recovery。实际Run由原worker处理，页面只读状态，不能finish/赋权或冒充成功。只有原key COMMITTED且body指纹可核对后才开启下阶段；已发送NOT_OBSERVED保持未知。中断/刷新可只GET恢复，不能连发剩余阶段。最后只打开实际新preparation原页；撤权/跨scope/迟到响应清私有视图但留opaque核对句柄。

实际验收新增：两次不同新输入/新Case/材料/候选/结果不混淆；V4映射下原P4 REQUEST_CHANGES、v2 ACK、REOPEN/v3造成P4/P5当前失效并明确重核；错误cold inputs公开API拒绝、业务与authority无变。AT33的业务B是真实三值准备度、C是真实原变化处理；未实现/未运行的门明确保留，不把映射unknown或两个园区名称替代完整A/B/C。AT14另记实际隔离写范围，不把只读候选当隔离执行签收。

518归档旧NOT RUN和本次首次FAIL保留；修复仅精确替换两导出中的8个临时fixture会话、共16处，原runtime不变，修后新独审另记PASS。GitHub免费CI资格只读核实gh repo view首次返回Post "https://api.github.com/graphql": Forbidden，停止该API动作，不走替代端点/新workflow绕过；本地开发/正常Git推送继续，CI未运行。

不启动浏览器，不真实模型/付费调用，不Windows、生产迁移/部署、新Grant/registry或权限扩大，不改凭据/网络配置、不强推或改main/F1/原F2。测试使用真实owned Linux PG票据与原fixture，初始fixture种子和runtime写分列，原始FAIL/ERROR/log/XML/exit保留；相关完整模块冻结复验后正常分支推送并核远端/未推差异。
