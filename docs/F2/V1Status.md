# F2 与原V1计划的真实对照

## ENG029 当前同步与Server CI结果

ENG028代码已普通快进同步，精确远端ff00b6d8ad0880b24afaca49e33b9f8b982ceb87。标准Server [run37417713362](https://github.com/T1doo/ParkWeave/actions/runs/37417713362)已completed/failure：PreparePASS、native_suite623.032秒exit1/外层timeoutFalse、受绑定PG StopPASS。获准check summary/text为空，19条注释未给具体case/counts；仍UNKNOWN，不把时长推断成内部超时或根因。下一定位仅需此新run页面安全JSON，旧截图请求已过时。见[ENG029真实同步记录](ENG029-SyncCI.md)。下方ENG028“本地未push/待核对”等均为当时快照，现已被本节取代；F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。


## ENG028 本地诊断与UTF-8读取修复（待同步核对）

ENG028增加仅固定test ID、阶段、异常类别和有界统计的诊断；明确UTF-8读取规格、页面、SQL及结果文本。本轮为本地工程修改，尚未push或触发CI，实际Windows码页及原生失败根因仍UNKNOWN。最新已同步代码1baa2cf、docs头aae63a5；标准Server run37414981257仍FAIL，Prepare/受绑定PG停止通过，native_suite79.235秒exit1/no timeout，具体case/counts未知。新样例仅模拟格式，不是该run结果。见[ENG028本地记录](ENG028-SafeDiagnostics.md)。F1未签收/F2正式准入NOT_PASSED，R4关闭、Win11/36AT6EX NOT_RUN，真实模型/预算0。


## ENG027 当前同步授权

普通同步已完成：精确代码push头1baa2cf93f795dbf3036245b8f2ea2ec2ce15e56（含已验证54fad8c）。标准Server CI37414981257终态FAIL：Prepare成功、native_suite79.235秒exit1、owned cluster停止成功；具体case仍UNKNOWN。实际证据见[同步记录](ENG027-SyncCI.md)。旧ENG026未推送/暂停说明属于当时快照，不能当当前状态。未经精确远端验证不声称GitHub已更新，CI结果取得后据实记录；不force/merge main/deploy/LIVE，不重试被拒日志或换身份。F1F2/Win11/R4门槛保持。

当前收敛基线：本地 `2fddccae02a27818e3632cfca7676104e6eb3569`（ENG025）。原V1《分阶段开发计划》F2-T01—T07及产品§3、5.2—5.5是来源；原文/验收规格未改。下表是实际子集，不是阶段或整项AT签收：F1未签收、F2准入NOT_PASSED、R4关闭，PR0-alpha未完成。

## 当前已能复现的合成链

新的合成诉求→Case/Run/独立worker建单→两槽资料版本/专员补正→企业追加资料→获派专员核对→企业本地确认→本人两资源预检/占位/短事务组合确认→企业明确选择并保存此资料Case的资源关联→资料重开显示需重验且不释放预约→重新人工核对确认后显式关联v2→合法获派执行者合成回执/企业纠错核对重开→reload历史→显式整组取消释放两条容量并保留关联失效原因。ENG025实际三角色UI/PG/API链及320/390记录见[证据](evidence/eng025-acceptance-summary.json)。

关联已是产品API/UI持久记录，不能继续称为ENG024时的纯测试手动ID关联。但仅当前资料服务Case与本人已确认的两资源组合；没有一般ServicePlan/DAG/Approval，跨模块不构成一个总事务。一组合永久归一个Case，换组合保留旧归属/旧占用，取消是显式独立操作。资料REOPEN不是Case生命周期重开；实际Case仍NEEDS_INPUT，资格NOT_EVALUATED、外部NOT_SUBMITTED、线下NO_EVIDENCE。

执行者assignment由本次测试owner显式准备已有合法分配；产品没有运营分派写入口，不是新建真实身份/通用接单。回执仅SYNTHETIC来源，不能证明真实办理或关闭Case目标。角色上限/当前授权交集不变，执行者无企业资料正文或资源操作权。

| 原项 | 已有真实工程成果/提交证据 | 尚未完成的原始项 |
|---|---|---|
| T01 服务入口与企业事实 | 合成建单、带来源候选事实/必要澄清、资料两槽/版本/补正/核对、个人待办；`5173490`、`3aa99e4`、`c285da8`，ENG024修复通用身份/迟到回填。 | 完整锁定约束/事实冲突、三类来源真实性核验、按用途授权复用。新资料/自述仍可UNKNOWN；真实样例需对应授权。 |
| T02 ServicePlan生成与目标覆盖 | 已有类型契约/结构校验；无自动资格或外部办理。 | 书生从注册服务编排有限DAG、必需目标覆盖、责任/前置/输出/补正/不支持项及预览闭环，均未完整交付。真实模型/额度和安全门未通过。 |
| T03 资源预检与组合确认 | `da69ea6`预检/占位/期限；`50f7c4b`单资源确认；`c2f3465`两资源同事务确认/整组取消；`2fddcca`增加当前资料Case持久关联/明确重验/失效原因。真实PG故障/并发/撤权/幂等及浏览器证据见[ENG021](evidence/eng021-acceptance-summary.json)、[ENG025](evidence/eng025-acceptance-summary.json)。 | 任意数量组合、一般Approval/ServicePlan绑定、多Case共享/归属转移、替代/完整变更影响。局部验证不能给全部AT09—11/28—29 PASS；真实资源/外部系统未接入。 |
| T04 角色协同与本地办理 | 企业补件/获派专员核对/确认/资料重开；`8e2195a`有来源/version/hash的获派执行者合成回执、企业核对/纠错/重开；`2fddcca`实际串联资料、Case资源关联及回执。 | 通用CaseStep、运营分派、执行者接单完整语义、站内通知/送达/已读、Case生命周期关闭/重开、真实核验履约。此前Operation receipt不是办理回执。 |
| T05 事件及可靠执行回归 | F1操作账本/租约/fencing/核对/取消/outbox；资料/资源/回执局部事务、幂等/CAS/当前撤权/失败回滚；ENG025不可变关联及归属事务。 | 所有F2办理/通知与业务Outbox贯通、全流程幂等消费、失联/未知结果/变化核对/陈旧批准回归；局部PASS不等于AT16—20整体完成。 |
| T06 办理模板与新输入 | 新Case/输入及资料/资源/回执合成样例，不复制旧材料/真实身份；多企业隔离回归。 | 审核后参数化服务包模板、完整新企业冷会话/新材料样本、版本发布和全部AT08/35。现有SYNTHETIC fixture不是授权真实样例。 |
| T07 三工作区及端到端验收 | 服务/协同/资源局部真实UI、当前有边界三角色链、桌面/320/390截图；55张登记图hash匹配，历史3覆盖/3恢复缺图见[ScreenshotEvidence](ScreenshotEvidence.md)。 | 新诉求→规划→确认→办理→核验→反馈完整原V1链、用户视觉签收、真实设备/Win11和全阶段端到端验收。当前有边界链不等于PR0-alpha。 |

## 实测入口与同步边界

[FirstUse](FirstUse.md)给出当前产品UI步骤；[ENG026同步前收敛说明](ENG026-SyncReadiness.md)列出仓库实际CLI入口、所需本地fixture/合法分配、提交链及检查限制。ENG025冻结源全量584PASS/0FAIL/1WindowsSKIP、95页面时序检查；本轮Windows验收脚本窄修复的独立结果见ENG026，不复用旧数字当新测试。

截至ENG026结束，本地缓存origin/dev/f1-foundation为6ff160a，积累11个本地提交尚未推送；该历史缓存不是实时GitHub状态。ENG027已恢复授权，并正常读取实时远端仍6ff160a，确认快进关系；普通同步精确验证1baa2cf，标准ServerCI37414981257FAIL，具体case待用户，详见同步记录。仍不force/reset丢代码、不备份/导出/上传/LIVE。

旧Windows事实：源码9a8cbc527503ab55978a4b50612207d3bf72de26的CI37324704568 Prepare通过，native_suite78.094秒退出1，失败case/日志未取得。新标准Server CI37414981257已对同步1baa2cf执行并FAIL：Prepare通过、native_suite79.235秒exit1未超时、owned cluster停止通过；case与根因仍UNKNOWN，不能用Linux模拟/AST替代。Server不是Win11。F1/F2未签收、R4关闭、36AT/6EX NOT_RUN；Windows失败明细仍待用户，不能用猜测替代。
