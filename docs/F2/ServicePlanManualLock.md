# 原注册步骤人工锁、来源影响与历史

从已推dev `9bc4ed59ed5156ee3a2a84c2023500eca355c426`继续，先d6ebf7ee冻结[有界合同](ServicePlanManualLockContract.md)、daff05e9冻结解锁额度，再实现。沿原§8/F3-T03，仅原P1→P2→P3→P4→P5注册Case链，不重做一般依赖图、已完成资料包导出或资料异议闭环。

原owner在当前权限、前置、来源和VERIFIED检查有效时，显式LOCK保存原核验内容及plan/step/owner/source SHA的事件引用。原业务来源仍可由原角色改变；改变后旧决定和来源快照保持，当前显示LOCK_CONFLICT，下游失效，不自动解除或重验。锁内只能显式UNLOCK；UNLOCK保留旧核验与失效状态，须原流程修复来源并VERIFY。任何活动锁阻止替换ADOPT，解锁后明确采用新计划，保留原计划及锁/解锁历史。

固定链影响报告区分直接变化、受影响和保持的步骤；未知request/catalog/registry绑定扩大到此Case全部采用步骤。独审独立预期P4真实回执REOPEN更新P4/P5、保持P1/P2/P3，实际核对旧快照、UUID、分配和事件不被覆盖。最多64追加事件、8代历史；每个活动锁保留一条UNLOCK额度，新LOCK同时预留自身额度，真实三锁及64边界不会留下无法解锁的锁。原CAS、actor/key指纹幂等与迟到请求保护保留。

LOCK/UNLOCK未知回包复用原11字段、8槽、640字节、24h无正文/hash/token句柄；热/冷、新页、实际同origin API进程重启只GET核对，不自动POST。当前撤权、来源换版、等待后期限和迟到200/403重新检查，跨企业/Case/角色不能读写。损坏锁或缺失/篡改事件拒绝，不能降级清锁。原目标结果接受合法锁事件，但只有原VERIFY证明当前检查；来源或依赖失效保留历史、提示先解锁，GET零SQL观察写。不同角色同字面key保留原(actor,key)身份。

最终精确运行源码 `1a8d95e8cf532affc8e5b8c8503866c63b29d4c7`，独审LIMITED_PASS。根7完整相关模块285PASS/0FAIL/ERROR/SKIP，JUnit452.467秒、受控454.075491秒；独审8完整相关模块353PASS/511.171秒、受控512.727002秒。独立分窗原15oracle15PASS/28.648秒、新11负例11PASS/23.710秒、加强实际源READ期限1PASS/7.391秒，共27唯一额外检查；初始同期限1PASS/6.854秒仅重复历史，不重复累计。325源首尾及交付零漂移，manifest SHA `4deb8f25a98bb265c9b990f76d0fdb33c7d112490c042fd69156d25d92e45046`，诊断AST1387。

首轮0c2e5fa根9模块363PASS/549.336秒及独审8模块345PASS/502.117秒不能抵消独立发现的五条产品失败：合法LOCK/UNLOCK使goal-results409（2条），缺失LOCK事件/错误owner/错误step却误报当前输出通过（3条）。先ef5e3735补合同，再1a8修原结构兼容与锁证明、补API/页面检查。五失败逐项独立复验通过；旧BLOCKED报告SHA `f5bd6aeb6fceebac4996eca043610558448637253e8610f33393eb9f4671cb5d`保持。开发窗口错误原P3角色、独审夹具未加载和在VERIFIED P4上BEGIN观察器均分窗保全并纠正；进度JSON非原子读取故障标为观察器，未重启测试。不同窗口不相加称全仓。

真实隔离PostgreSQL、loopback HTTP/Chromium实际覆盖丢响应、撤权、越权、跨企业、来源/原请求换版、并发、迟到响应、重复写、损坏证明与隐私。1200/390/320冲突卡无横向溢出，两动作分别实际API重启。独审实际executor源READ有效时owner目标GET200当前有效，等待最后lifecycle源行锁跨该期限后403、业务快照不变。owner本人managed期限在原合同不适用（租约只针对executor），没有自造owner租约或Grant，不标作PASS。

安全证据：[最终核验](evidence/service-plan-manual-lock/verification.json)、[最终独审](evidence/service-plan-manual-lock/independent-review/report.json)、[首次阻断](evidence/service-plan-manual-lock/first-independent-review/report.json)、[开发窗口](evidence/service-plan-manual-lock/developer-window-history.json)、[私有故障保全清单](evidence/service-plan-manual-lock/private-artifacts.json)、[实际窄屏冲突卡](evidence/service-plan-manual-lock/browser/lock-conflict-320.png)。只公开安全报告和通过窗口，失败XML/栈/原始日志私有；正常整合与远端另记[整合记录](ServicePlanManualLockIntegration.md)。

无新schema/迁移/Grant/角色/通知/政策审批/模型/部署/强推/main变更。仅原合成合同、有限注册Case链；未验收一般DAG、完整原AT25–27/EX、全仓或Windows，既有Server CI未查询，旧a823a28未迁移。人工步骤锁不是Approval；正式ServiceRelease/Approval、在途兼容/迁移/回退合同仍有缺口，见[只读盘点](ServiceReleaseApprovalInventory.md)。常规开发与合成测试已授权继续；真实发布、履约、Case完成和对外分享未由本片授权或实现。
