# 原已采用目标的当前本地交付证据

沿原产品§5.2/§5.5/§7.1与F2-T02/T04/T07继续，企业负责人现在可逐个核对原方案对应的实际合成本地产物、原本人核验事件和未满足原因。入口位于Case持久步骤计划的“本次明确目标的交付证据”。只读核对不会核验步骤；显式VERIFY仍由原企业按钮执行，返回链接进入原资料、资源、分派、回执和本地重验入口。资料包导出不重做，原资料异议与原专员回应/企业复核继续保留。

六个既有LOCAL_*目标复用原P1–P5：材料证据包括双槽当前UUID/version/hash及原REVIEW/CONFIRM；资源证据对应此Case组合和成员；接单对应原本人ACCEPT及receipt-step；回执对应最后连续版本/hash、原SUBMIT/企业ACK，并标明人工合成文字和实际启用本地报告的不同来源；本地事项对应REVALIDATE、cycle/revision。原owner VERIFY事件、当前来源、前置、当前请求/注册表/资料及权限均须满足；已有产物不自动核验，旧核验作为历史保留。

专用GET不写业务表，不调用原计划GET的观察失效写入，不增加Schema或Grant。只有原owner的当前READ/PREPARE范围可读；其它角色/企业和撤权拒绝。无法当前读取的产物不输出业务ID或SHA，保留本人历史计划/步骤核验引用及最小原因。专用结果不包含资料正文、事实值/摘录/假设/理由、回执正文或凭据。这些检查核对来源hash和原表事件关联，不是数据库全部记录被同步改写时的防篡改签名。当前不支持目标完整保留，旧采用目标单列为历史。

页面绑定身份、Case/Run、plan/request/preparation revision和草稿/结果代际；迟到200/403不覆盖新上下文。同Case原资料/异议写入已在途或UNKNOWN时，旧200保持未核验且保留未知操作/草稿；当前真实403优先清私有DOM/内存，不受原写锁阻止，无未处理页面错误，原不透明恢复句柄保留。

独立审查还复现了原材料句柄writer未保存reader要求的expires这一既有冷恢复缺口。本片沿原五字段v/id/key/revision/expires、400字节、8条和24小时合同修复：同请求重试保留原期限，错revision拒绝；过期、超期、损坏、额外字段和旧缺expires条目仍拒绝。实际材料提交已保存但回复丢失后，经旧200或撤权403、恢复原权限、冷刷新并重新认证，可以原key仅GET核对COMMITTED事件与当前v2，不重发材料。显式结束核对只清句柄，保留新手工草稿。这不补步骤计划未知动作冷恢复。

结果区分未知/未采用/等待实际产物或前置/待owner核验或重新核验；所有明确当前目标有实际当前证明及原核验才显示LOCAL_OUTPUTS_VERIFIED。case_goal_completed始终false，不代表自然语言诉求整体履约、资格、外部受理或线下完成。

最终候选984cbe95acdc51f42e4b67d9a6c06c780c44350b的精确测试与审查结果见机器证据；根14完整模块560项通过394.973秒，独审9完整模块393项通过及26个唯一额外独立探针分别通过；首窗25PASS/1观察器FAIL，观察器修正后的单例1PASS，原失败窗口保留。两次独立计数不加总成全仓或正式验收。321路径首尾零漂移，诊断白名单1334原函数ID。1200/390/320真实Linux Chromium无水平溢出；两个受控API进程在同PG恢复当前证据。首轮495b0eb与次轮e8c6c949独审BLOCKED和所有故障窗口分别保全，旧555/559PASS不冒充最终验收。

剩余关键路径仍包括正式ServiceRelease/Approval主体与发布/用途锁、真实服务承诺产物及独立核验、Case FULFILLED权限/判据、多用途分享精确授权和步骤计划未知动作冷恢复。没有模型调用、外部通知、真实业务、政策审批、新权限、Case完成、部署、main修改、强推、凭据/安全网络变化。Windows、全仓和原AT/EX未由本片签收，旧a823a28 Windows Job/accounting修复未迁移。

证据：[冻结合同](CaseGoalResultsContract.md)、[根测试](evidence/case-goal-results/verification.json)、[最终独立审查](evidence/case-goal-results/independent-review/review.json)、[首轮阻断](evidence/case-goal-results/first-independent-review/review.json)、[次轮阻断](evidence/case-goal-results/second-independent-review/review.json)、[完整窗口记录](evidence/case-goal-results/failure-history.json)、[页面及恢复](evidence/case-goal-results/browser-evidence.json)、[源码冻结](evidence/case-goal-results/frozen-source.json)、[私有故障保全清单](evidence/case-goal-results/private-artifacts.json)。
