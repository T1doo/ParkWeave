## ENG080 当前本地核对（以下旧条目为历史快照）

当前源码完整Linux回归 **1454PASS/0FAIL/9原生WindowsSKIP**，299.57秒；首轮三项旧workflow断言失败已修正后全量复验，用例未删/未增skip。实际同Case回执失败恢复、提交后丢响应的相同输入幂等重试、身份切换迟到响应、纠错新版重核/Case显式重验、收起计划返回及1200/390/320视图通过；原资源时段结束先正确阻塞，再经正常UI关联新有效组合v2，规则与授权不变。最终cycle5/本地revision17、回执revision18/v7，Case等待真实确认、目标未完成。

F1未签收/F2仅并行、R4关闭/模型预算0；完整工程Windows仍有ENG071失败与S4缺口，ENG078独立success缺直接JSON，owner保持暂停、完整CI未恢复、Win11未验。无新增GitHub请求/push/run；最后已核实远端381a20a，后续本地提交未推送，不当作实时远端。快速体验命令、前置与实际证据见[ENG080](ENG080-FullLinuxAndQuickExperience.md)；旧新Case/seed/赋权入口属于历史演示，不用于本轮只复用Case的复验。

> 当前只读复用入口与已修复的回执失败反馈见[ENG079](ENG079-ReceiptReadFeedbackAndEvidenceLimits.md)。本轮保留原Case和授权；下方ENG073新建场景入口仅是历史说明，不用于当前复验。

> ENG075补充同一个保留Case的纠错与新版本重核/显式重验，无新增assignment；实际短步骤及不清空历史的重放条件见[同Case体验](ENG075-SameCaseReceiptCorrection.md)。下方ENG073隔离新Case自动runner属于当轮演示，当前只复用授权的切片不调用它。

# 当前最短合成体验（ENG073）

这是本机合成演示：材料准备、资源、本地分派及回执能操作；资格未评估、外部未受理、没有真实履约证据。当前服务已在走查后停止，截图和报告保留；Win11未验。

## 本会话最短自动体验

使用当前已安装环境，一条命令重放两个独立合成Case并保留报告/截图，完成后自动停止服务：

```bash
PYTHONPATH=src /workspace/ParkWeave-restored/.venv/bin/python .runtime/eng073-product-walk.py
```

这个本机runner保存在当前工作区.runtime中，使用现有缓存浏览器并将API/worker包入口绑定当前源码；不下载依赖。临时数据库只用于本次合成演示。脚本本身不在发布交付包内，环境重置后须重新准备，不能假设旧绝对路径继续可用。

## 本地启动与身份前置

在已有依赖和本地Chromium的Linux环境、项目目录运行既有入口：

```bash
PYTHONPATH=src /workspace/ParkWeave-restored/.venv/bin/python scripts/linux_fixture_server.py --preparation-fixtures --resource-fixtures --combination-fixtures --receipt-fixtures
```

打开 `http://127.0.0.1:8765`。本机私有`.runtime/synthetic-sessions.json`中的fixture-a是企业会话；对应专员及执行者分别来自preparation-sessions.json与receipt-sessions.json。在页面会话框切换，切换会清空旧身份视图。勿把会话值写入截图、文档或提交。

该入口会显式准备合成数据库/schema/角色/资源；不代表真实身份部署。执行者还须具有这个新Run的合法assignment，当前产品不提供自动赋权入口。最短**完整自动重放**可按既有 `scripts/case_lifecycle_browser_smoke.py`（同Case生命周期）或 `scripts/controlled_plan_browser_smoke.py`（另Case四步计划）进行，需本机fixture owner DSN在进程环境内与缓存agent-browser；不把DSN打印或粘贴进本文。ENG073的实际运行已由隔离harness完成，无需以授权真实数据替代fixture。

## 按同一个事项操作

1. 企业在“服务”查看可选服务与专员，开始资料准备，填写两类材料及来源版本。记住同一事项名称。
2. 专员在“协同”读取该事项并核对；企业切回同事项确认当前资料。
3. 企业去“资源”分别预检、占位两个资源并确认组合；回该事项，明确选择组合并确认此Case资源关联。
4. 已有合法新Run访问前置准备好后，专员在同事项分派，执行者本人接受并提交合成回执；企业核对回执。没有企业ACK，本地关闭按钮应不可用。
5. 企业从回执进入该Case本地记录，显式重验当前材料、资源、接单与回执，再关闭本地记录。重开后先重验才能再次关闭；reload保留两轮历史。
6. 有固定计划的事项可从资料/分派/回执进入“查看此事项四步计划”，逐步核对；P4后进入同Case本地状态。计划核对和本地关闭均不代表目标履约。ENG073计划与生命周期实际测的是两个独立Case。

本輪生命周期实际截图：[390宽本地状态](/workspace/ParkWeave-targeted/.runtime/eng073-case-screenshots/local-case-390.png)、[重开需重验](/workspace/ParkWeave-targeted/.runtime/eng073-case-screenshots/owner-reopened-recheck-required.png)。独立计划截图：[390宽四步计划](/workspace/ParkWeave-targeted/.runtime/eng073-plan-screenshots/plan-390.png)。固定结果与截图指纹见[走查证据](evidence/eng073-decision-product-walk.json)。

## 仍未完成

- 新Run合法执行者访问仍有fixture owner前置；通用业务授权、接受后责任转移和handoff尚缺。
- 只有当前固定四步合成模板，通用ServicePlan/DAG、完整Approval、参数化模板发布与真正冷会话未完整交付。
- 跨材料真实来源/资格核验、真实园区资源、外部受理及履约凭据尚未接入；不得将Run SUCCEEDED或本地记录关闭标作FULFILLED。
- 当前场景未重跑回执纠错/新版本重提、分派拒绝/撤回/重派、站内通知和所有故障/并发链；历史证据保持原轮范围。
- 原生日期picker、真实设备、Win11、完整36AT6EX和用户视觉签收未完成。Windows owner暂停、精确后代结束及S4缺口单独保持OPEN；不阻塞上述本地合成体验。

完整原V1对照见[V1Status](V1Status.md)，当前权限和Job决策边界见[ENG073](ENG073-DecisionPackageAndProductWalk.md)。本轮仅本地commit，无push/CI/部署/LIVE，F1未签收/F2并行、R4关闭、预算0。
