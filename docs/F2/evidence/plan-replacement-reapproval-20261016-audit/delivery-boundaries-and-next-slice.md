# 最终交付文档建议与下一有界切片（仅建议，未实施）

依据：原产品 docs/平台产品设计.md §5.1–5.6、§6.2–6.3、§7.3–7.5、§8；原阶段计划 F3-T02/T03/T04/T05/T06、F5-T04；docs/F2/Plan.md、Log.md 与 DeliveryCriticalPath-20261010.md 当前置顶记录；当前产品源码 b7eec40f005ba5877ecea1a7165e99bd668d041c。此文不写最终回归计数；主140模块仍须等待实际最后回执。所有旧时点的“下一项/缺失”必须先对照已交付再使用。

## 六目标与五节点不可减少

| 原目标 | 原节点 | 本地证据边界 |
| --- | --- | --- |
| LOCAL_MATERIAL_PREPARATION | P1 | 实际材料人工核对及企业确认 |
| LOCAL_CASE_RESOURCE_ASSOCIATION | P2 | 本Case当前合成资源关联 |
| LOCAL_INTERNAL_ACCEPTANCE | P3 | 当前有权执行者本人接单 |
| LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT | P4 | 当前合成回执企业核对 |
| LOCAL_SYNTHETIC_COORDINATION_RECORDS | P4 | 当前合成本地协作记录 |
| LOCAL_CASE_RECORD_RECHECK | P5 | 当前本地事项重验 |

六目标并非六节点；P4承载两目标。本批新整计划采用产生新 plan_id 与五个新 step UUID，旧计划/旧UUID/事实/资源容量保存在历史中。不能沿用同计划局部修订的“当前step UUID不变”表述。LOCAL_OUTPUTS_VERIFIED与工作清单 recorded_states_only/evidence_verified=false/case_goal_completed=false 不等于现实履约或Case正式完成。

## 已交付部分不能再写成零实现

原 IMPORT/REFRESH/IGNORE/WITHDRAW、同计划来源明确局部 ADOPT/受影响 VERIFY、材料双槽/本人注记受控继续、同结构携注记升级、有限模板结构增强、V4 ServiceRelease/ParkInstance与第二园区冷输入、两类共享来源反查、有限多来源传播、同plan来源再批准、原完整旧链整计划替换后新明确批准与事务交付均有现成工程路径。本批只是最后一项的有限兼容扩展，不是新机会系统、任意DAG、通用迁移器或正式生产Approval。

当前替换 profile 明确要求旧六目标/P1–P5全部真实VERIFY、三项指定V4服务、同Case/owner/当前已知来源、有限非破坏合同、紧邻历史、新初始ADOPT与明确新Approval。当前缺失/撤回/到期/未知、破坏性、一般未完成旧链和不支持的人工/迁移组合仍拒绝。原批准、原资源占用与历史保留，不能改写成新资源已隐式替换并释放旧资源。

## 本批尚未覆盖的关键路径

1. 一般在途或部分办理链的版本适用性：P3已分派/已接单/有未决操作、旧链缺输出、手工决定/活跃锁、结构变化或迁移组合没有通用可继续协议。当前完整旧链许可不能推导这些状态可执行。UNKNOWN仍拒绝。
2. 定义/数据复杂迁移和回退责任：有限原模板兼容/前向增强已经存在；新replacement不能覆盖任意ServiceSpec/新节点、新目标、任意输入合同或业务数据迁移。破坏性拒绝是原PR0允许的首版行为，不必为了AT27实现破坏性执行。F5-T04备份恢复/复杂更新是增强阶段独立工作，不能倒写成此次F3-T03已完成，也不应将F5全量作为原首次提交必需。
3. 后继TEMPLATE_UPGRADE后的消费历史读取：实现具备保存历史边界，但本批未跑实际该业务探针；合法EDIT_NOTE已按精确资源CURRENT合同覆盖，不能将该成绩移植为模板升级证据。
4. 更广来源图：当前细粒度字段和有限聚合来源族不等于一般语义关系/任意动态图；shared_source_cases仅OWNER_RESOURCE_QUERY_SET与SERVICE_CATALOG_REFERENCE，MAX_CANDIDATES=32、跨页/溢出UNKNOWN和跨Case非原子边界保持。跨业务包不确定范围、更广字段/规则日期/地区与人工语义仍须独立答案。
5. 正式前提：生产发布/撤回/Approval主体、真实资料许可与来源维护责任、真实规则/日历/SLA、独立现实回执尚未落实。原测试fixture默认关闭能力不能冒充这些合同。真实模型/B0–B2、Windows/Win11原生及其浏览器、正式AT/EX、广覆盖浏览器、生产/部署和第二作品实际状态仍不能由本批限定Linux证据签收。
6. 专用PG27仍需原专用profile/role/hosted/branch/approval-only门。普通模块与有界Chrome模式不替代它，不创建role/增Grant或伪造host/branch绕门。

## 一周内立即接续的最小新产品片建议

优先建议：只支持一个**有原始“尚未开始”证明的执行前沿**，例如旧P1/P2已真实核验且已有资源，P3从未分派/接单，P4/P5从未产生业务效果；同原六目标/三个V4服务，在已知兼容变更后逐Case明确重新采用、新批准并续办。它与当前“旧五步全部完成”不同，不重复实现已有完整替换或同plan再批准。

先区分 KNOWN_NOT_STARTED 与 UNKNOWN：对没有创建过的后继动作，必须有原对象/事件/世代全集的有界查询、当前权限、来源版本和row epoch/fence证明；曾经有回执而现在缺失、查询不全、权限不足、迟到在途或来源未知绝不能包装成“尚未开始”。保持真实parent及原锁序，旧/新资源及历史保全；新profile/资格证明须明确隔离，不能仅删除现有五VERIFY门或把can_record当授权。若无法建立原始不存在证明，该状态仍安全拒绝并如实交付合同/阻断证据。

建议1–2天先冻结这个单一前沿的可继续/必须补正/必须拒绝字面答案及资格合同，随后2–3天实现唯一原命令路径与真实页面→HTTP/ASGI→自有PG正反链。验收至少区分：真实未开始、已存在/已删除回执、迟到旧P3分派、两计划ABA、撤权/目标撤回、容量事务回滚、同键异参、丢回执原key冷GET；P3–P5保持等待直至原动作和VERIFY真正完成。保留原六目标，不提前自动完成。

余下时间做冻结SHA完整受影响模块、隔离独测/独审、失败保全与普通开发分支同步；用完成条件推进，不再按月底慢排。可并行准备正式AT固定初态/oracle、Win11/模型/发布主体的既有许可与前提清单；没有这些前提就保留NOT_RUN，不以一周目标推导授权。更广执行前沿、人工注记/结构组合和备份恢复另分片，避免同一轮扩成通用迁移。

作为小型验证补项，可在独立窗口补“合法后继模板升级→原已消费receipt历史GET保持→当前需重验”的实际证据；这是补未执行路径，不是再开发已有模板升级功能。若希望先做更低风险的新查询功能，可选择“既有已选employees断言描述符→本人有权Case只读反查”的第三个明确来源族，复用已有采纳/批准/核验闭环；仍保留32候选与未知范围，不宣称一般图完成。

## 最终报告需核准的措辞

三轮必须并列：eaa的alias遮蔽29P/1F；06fd的资源状态oracle错误29P/1F；b7在产品七文件不变下修为精确CURRENT并增加实际注记/六目标/CONFIRMED断言后，全新重跑。只有最终同SHA完整窗口计分，原失败/中断保留。资源CURRENT仅资源交付当前性，不代表Case/整计划完成。

三套独审seal分别保全：最初eaa目录17files、v2目录13files、v3目录13files。不能简写为“旧17/新13”而遗漏中间冻结证据。

浏览器前置是混合路径：源/Release/实例/新V4采用由原Python产品函数，部分旧链/资料为进程内TestClient夹具；actual_http启动后的reoffer/receipt/P5使用loopback HTTP。页面实际完成明确PROPOSE/APPROVE/COMMIT、P2–P5 VERIFY、目标和清单。不要把全部前置都写作native HTTP或全部浏览器点击；Node机械DOM仍非浏览器。Windows/正式AT/真实模型/生产缺口保持。
