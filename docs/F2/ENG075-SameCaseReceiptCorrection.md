# ENG075 同Case回执纠错与重新校验

本轮只使用ENG073保留的合成Case `0b76ab4c-e429-4313-ace2-25d3522ed09b` 与Run `e6c2bddf-8fb8-4848-b45e-8f4ffda6b8c6`，复用已有合法执行者assignment。没有seed/migrate/assign，全部run_assignments及capability_grants逐行前后相等，未创建或恢复任何授权。owner所有原生流程保持暂停，不做权限实验，不push/CI/部署/LIVE。

## 实际可体验的价值

企业可对同一个事项要求纠正回执，执行者提交新版本，企业重新核对；即使新回执已ACK，Case仍须按新的当前依赖显式重新校验才能关闭本地记录。更正不会静默沿用旧版回执的Case校验结果，不会把目标置为已履约。

实际从已有本地关闭记录开始：企业重开本地记录并先核验当前依赖，保存baseline；已ACK回执不能直接要求纠正，因此先重开回执→执行者提交待核对版本→企业要求纠正→执行者提交新版→企业核对当前新版→刷新同Case显示原校验失效、关闭禁用→显式重验→本地关闭→reload历史。回执未ACK期间重验及关闭均不可用；ACK后依赖检查通过但旧snapshot仍不匹配，关闭继续不可用。所有动作通过真实Chromium UI、当前源码API、worker及保留PostgreSQL完成，未用fixture owner直接写业务结果。

首轮实际走查通过，并在像素查看时发现READY顶栏静态映射仍写“当前一轮已显式校验”，与下方“本轮待重新校验”矛盾。仅修正renderLocalCase摘要：READY且verification_current=false明确“本轮原校验已失效，须重新校验”；true保持已校验；未提供有效性时仅说有校验记录。API/state/权限/关闭条件不变。浏览器脚本增加真实摘要断言，然后在同Case、同assignment完整重跑通过。

最终重跑回执revision8→13、版本3→5；本地记录cycle3→4、最终revision13，Case WAITING_CONFIRMATION、case_goal_completed=false。首轮产生版本1→3、cycle2→3，是同Case的历史验证，不伪装成回滚后的新测试。resource/dispatch/material依赖沿用既有记录，没有重新赋权或改变容量规则。

## 像素与验收证据

主线程实际打开纠正待办、执行者新版、ACK后旧校验失效、320及390最终态PNG；独立审查者也实际打开旧误导图、新失效图与390最终态。新摘要与待重验提示一致；320/390按钮卡片可读且换行，截图未见横向溢出，浏览器scrollWidth断言亦通过。截图hash用于文件绑定，**没有替代看图**。viewport截图不等于完整页面/真实设备或用户视觉签收。

8张最终截图及JSON绑定当前web/source，见[固定证据](evidence/eng075-same-case-receipt-correction.json)。[失效提示截图](/workspace/ParkWeave-targeted/.runtime/eng075-correction-screenshots/enterprise-rechecked-still-needs-case-revalidation.png)、[320最终态](/workspace/ParkWeave-targeted/.runtime/eng075-correction-screenshots/corrected-case-320.png)。截图和本机runner在.runtime保留；工作区重置后需重新准备，不能假设这些本机路径永久可用。

本地API/worker均由本轮拥有的Popen句柄发送SIGTERM后wait完成（返回-15），PostgreSQL STOPPED；未按PID宽杀其他进程。无真实模型调用/预算0，R4关闭、F1未签收/F2并行；Win11/原生Windows/完整36AT6EX NOT_RUN。

## 最短操作与下一片

企业在“协同”选原事项→回执“重开回执事项”；执行者选同事项提交待核对版本；企业“要求纠正回执”；执行者提交纠正新版；企业“核对当前合成回执”→进入同Case本地记录→“重新校验当前一轮”→“关闭本地记录”。若本地记录已关闭，应先“重开本地记录”。缺合法assignment时保持阻塞，不自动赋权。

本会话重放（只复用保留Case和授权）可运行：

```bash
PYTHONPATH=src /workspace/ParkWeave-restored/.venv/bin/python .runtime/eng075-existing-case-walk.py
```

再次重放会追加同Case版本/轮次历史；达到现有64事件边界会拒绝，不清空历史绕过限制。runner使用新的截图目录才能再次执行，先显式保留已有证据再选新目录。

仍缺接受后责任转移/handoff、通用Plan/Approval、真实来源和资格核验、真实受理履约及原设备验收。本次切片没有更改这些边界。下一最小产品片可审查同Case当前回执与旧历史在身份切换/迟到返回时的展示一致性，继续复用合法授权；不新增权限或Windows诊断量。
