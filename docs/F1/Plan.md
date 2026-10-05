# F1 计划

F1-T01/T02/T03/T04/T06 IN_PROGRESS：首个有界增量为严格领域契约、合成身份、持久队列与本地case.create动作；不含预约、任意代码或外部受理。F1-T05 BLOCKED：未获模型安全注入、预算及共享总配额确认。

目标：API 202落库，独立worker领取，事务内本地Case/Receipt/outbox，重复键指纹核对，租约fencing及当前授权重验。Run成功仅表示本地建单，Case保持NEEDS_INPUT。

Windows AT-01/34 BLOCKED；AT其余完整门NOT_RUN，工程子集另记证据，不把局部覆盖计整个AT PASS。本轮结束于首个可测增量，供复核。

初始上限：请求目标2000字符、JSON 16 KiB、计划16步骤、目录100条；仅case.create/1可信动作。文件导入与其他动作仍禁用；真实模型额度为未配置/禁用。

## 首个增量复核状态

增量ENG-001 READY_FOR_REVIEW：21项工程pytest、实际Linux HTTP与Chromium三工作区流程通过，见evidence。阶段F1仍IN_PROGRESS，六任务仅部分实现，完整AT与Windows/模型门未通过；下一轮由父任务复核后派发。本輪不继续F2—F6。
