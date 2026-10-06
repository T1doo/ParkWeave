# ENG055：同Case导航候选与固定分片审查清单

本地页面增加当前下一步、责任角色、已有办理入口；企业且四步LOCAL_RECORDS_CHECKED时可进入同一Case本地依赖重验/关闭，Case页可回到同Case计划。P4提示回执纠正/重开后须执行者重新提交、企业核对当前版本。只复用已有GET，不自动授权、批准或关闭，不声称原Case目标完成或真实履约；assignment工程前置仅在首次体验文档说明。

Case迟到GET/POST在进入计划时失效；切到其它Case计划清空旧Case上下文。返回Case重新GET最新状态；首次Case→计划GET失败可重新读同Case，刷新失败保留计划ID和草稿，CHECK失败保留原计划视图/草稿，403清私有视图。原业务POST判定不变。两次独立审查补出的导航竞态已修正，最终审查hash与验证匹配。

最终冻结web SHA256 1c4073d4195d0fde3f2e0661bfd59736f4952cd7c84e4f5862c3d10bf0865e7c。原计划18个静态browser响应oracle全部通过；原Case23个加9个精确导航检查共32个全部通过（非pytest业务测试计数）。已有agent-browser0.38.2/Chromium复用、随机自有回环服务和唯一session，close/shutdown完成；未启动旧smoke PG。首次默认sandbox socket EPERM在browser启动前失败，正式工具审批无拒绝后执行，不换代理/身份。没有业务API/数据库/模型调用，不能代替真实整流程API/权限验收；此前ENG037已有三角色链路证据仍保留，本轮不扩称新冷启动完整V1通过。证据见[UI JSON](evidence/eng055-local-case-navigation.json)。该本地候选不在aa3dc55 Windows CI内，未额外push/CI。

回归分片仅审查候选，见[固定文件清单](evidence/eng055-review-only-shards.json)。当前collect-only为44文件/1027项，无测试执行；四片246/220/326/235项，文件互斥完整、原测试source hash记录。使用ENG049 Linux历史累计成本并以每例0.2秒作最低权重，四片权重约90.401/90.642/90.648/90.281秒，仅用于相对平衡，不是Windows耗时预测或每片600内保证。若实施须保留全部原断言、每片600及outer job900，任何缺片/重复/漏测/失败/超时使整体失败，全片齐备才可汇总完整工程计数。各片独立600/900预算的执行拓扑尚需审查；不能将四片串行塞进同一900秒外层便宣称解决。没有修改workflow/runner/并发权限或自动触发新CI。

下一可用整流程仍需把同一新Case的四步、通知、回执、关闭/重开/重载在实际三角色链路验证；新Run既有合法访问前置保留，不能靠自动赋权补全冷会话缺口。F1未签收/F2仅并行探索、R4关闭、Win11/36AT6EX NOT_RUN与预算0保持。
