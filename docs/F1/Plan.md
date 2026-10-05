# F1 计划

F1-T01/T02/T03/T04/T06 IN_PROGRESS：首个有界增量为严格领域契约、合成身份、持久队列与本地case.create动作；不含预约、任意代码或外部受理。F1-T05 BLOCKED：未获模型安全注入、预算及共享总配额确认。

目标：API 202落库，独立worker领取，事务内本地Case/Receipt/outbox，重复键指纹核对，租约fencing及当前授权重验。Run成功仅表示本地建单，Case保持NEEDS_INPUT。

Windows AT-01/34 BLOCKED；AT其余完整门NOT_RUN，工程子集另记证据，不把局部覆盖计整个AT PASS。本轮结束于首个可测增量，供复核。

初始上限：请求目标2000字符、JSON 16 KiB、计划16步骤、目录100条；仅case.create/1可信动作。文件导入与其他动作仍禁用；真实模型额度为未配置/禁用。

## 首个增量复核状态

增量ENG-001 READY_FOR_REVIEW：21项工程pytest、实际Linux HTTP与Chromium三工作区流程通过，见evidence。阶段F1仍IN_PROGRESS，六任务仅部分实现，完整AT与Windows/模型门未通过；下一轮由父任务复核后派发。本輪不继续F2—F6。

## 第二有界增量ENG-002

READY_FOR_REVIEW：显式FAULT_INJECTION持久账本，独立模拟效果事务，丢响应/无结果查询/失联/旧worker/暂停取消/撤权/跨企业核对；补计划目标与引用边界。全量40工程测试PASS；完整AT仍NOT_RUN，F1整体IN_PROGRESS。

下一独立缺口（非外部阻塞）：V1完整ServiceSpec/Plan及事实冲突；字段级Grant、多角色作用域；正常worker长任务心跳和未知结果账本集成；outbox当前授权/消息撤回与并发回归；逐AT初态和oracle执行器。不要把这些未实现项写成环境BLOCKED。

真正外部阻塞：Windows11 x64实机/安装权限/精确依赖验证；真实书生安全配置、预算及跨产品总配额；真实园区目录/许可/用户流程证据。C0模板/规则/准确截止仍待核实。此次不进入F2业务实现。

## 第三有界增量ENG-003

READY_FOR_REVIEW：正常API/独立worker共用ExecutionGateway，持久DISPATCHED/OUTCOME_UNKNOWN、核对、撤权/控制与旧fence路径；Schema2保留历史；明确测试适配器默认关闭。实际HTTP/worker/PG工程回归和浏览器证据见ENG-003。F1整体IN_PROGRESS，完整AT/EX状态不变。

本轮不补完整V1最小契约/事实冲突/字段级Grant，以避免散开；这些是下一有界增量的独立工程缺口。仍未实现长任务心跳、outbox当前授权/消息撤回完整语义、逐AT全范围执行器。仅未知结果账本的正常worker接入从“未实现”改为“已有合成工程证据”，不声称真实外部连接已验证。

## 第四有界增量ENG-004

READY_FOR_REVIEW：当前闭环所需V1最小完整结构（校验不发布）、带来源事实冲突/缺证据、单企业经办角色字段READ/WRITE Grant、正常worker独立心跳及实际等待/撤权/取消/失联路径。78工程pytest PASS，browser与事实HTTP/worker证据见ENG-004。

配置命名：新增项目优先PARKWEAVE_INTERN_API_TOKEN、通用INTERN_API_TOKEN fallback的只读兼容助手，SecretStr不打印，仅虚构值单测；仓库原来无token读取实现，LIVE仍关闭，安全注入/预算尚未确认。

用户确认电脑Windows11系统家族；精确构建/架构/硬件/原生权限和测试仍BLOCKED，不能把自报系统视为AT-01/34通过。F1整体IN_PROGRESS，未进入F2，完整AT/EX NOT_RUN。

剩余独立F1工作：多角色/获派步骤权限与全部交集及审计、outbox当前授权/消息撤回、文件类型/路径/渲染边界执行器、原生生命周期脚本及固定AT全范围落地；当前仅三字段/一用途事实闭环、模型等待只mock。真实模型/Windows/真实园区资料依赖另列BLOCKED，不掩盖未实现部分。
