# 人工待办迟到GET在渲染前丢弃

父审发现9f0da39中openPersonalTask先await mgRead、内部已设置mgView/allowed_actions并打开表单，之后才检查列表代次。刷新或翻页造成旧列表失效时，旧响应仍会渲染并跳过外层Case/Run/plan/revision/source核验。无越权写证据；后端CAS不能替代前端原事项核对。

冻结源码 `89a423bd0b27af134bc38627c1b7042b8c64d1e6`。mgRead携带调用方列表代次，统一mgCurrent在响应正文后、渲染前以及catch/finally重核；原Case/Run/plan/ledger revision/source/目标责任绑定也移到mgRender之前。失效响应不会设置mgView、打开表单、显示旧错误或更新控件，不会清新草稿或opaque恢复句柄。

列表刷新同步只取消其精确当前task read的busy锁，保留新独立读取／写入的锁及全部草稿／句柄；旧finally不能解锁新操作。未改后端、授权、业务写、schema、Grant、registry或正常原key恢复合同。

## 真实红绿与验收

初红4FAIL：refresh及replace_refresh真实迟到渲染；page的测试误以为点击事项后旧翻页按钮仍存在（原入口会清列表）；replace_live误要求已取到旧快照的响应凭空发现之后服务器变化。两oracle分别修为刷新重建真实列表后翻页，以及在实际GET取快照前通过原API更换计划。修正红窗仍4FAIL：三项迟到渲染与一项绑定核验发生在渲染后。失败log/XML/exit及两个红窗逐项链原样保全。

首绿4PASS；增加精确busy取消及断言后4PASS。最终冻结根6模块 **80PASS、0FAIL/ERROR/SKIP、2WARN、70.648秒、exit0**：late4、tasks15、requests25、privacy11、case_worklist_offline21、template_full_chain4。原页面4迟到专项已包含根80，不加总。仅翻页100空legacy行是压力夹具，人工请求/REVIEW/CONFIRM/实际换计划均原API+ownedPG。

独立原完整HTML→ASGI→ownedPG **3PASS、0FAIL/ERROR/SKIP、2WARN、4.089秒、exit0**：刷新12断言/3GET、翻页14断言/4GET、新面板14断言/4GET，均0POST。旧响应零额外mgRender，新mgView/草稿/勾选/控件锁/错误/opaque句柄保留，业务/audit/Grant零变化。503份tracked源码／测试／脚本前后hash零漂移，原两approval未变。

独立第一次启动前exec-server transport disconnected，pytest未启动，该窗口NOT RUN，完整原错误保全。root在原同一环境实际成功exec_command读pwd/Git和根80PASS完整日志，确认恢复后才续同一服务独立原探针一次成功；无切换模型/环境/工具/配置，无权限拒绝重试。

浏览器历史ERR_BLOCKED_BY_ADMINISTRATOR与prepare元数据Forbidden继续停止；浏览器、prepare、部署、生产迁移、真实/付费模型与全仓测试 **NOT RUN**。只签本次列明范围，不将前片222或旧365成绩转签本冻结源码。

[证据索引](evidence/manual-goal-task-late-20261014/export-index.json)，[统计与恢复证明](evidence/manual-goal-task-late-20261014/validation.json)，[独审](evidence/manual-goal-task-late-20261014/independent/review.json)。导出仅夹具会话repr脱敏；失败尾空格保留，源码/报告空白检查PASS。源码到证据交付不再改src/tests/scripts。

已重读原产品§5.5、§7.1、§7.3/7.4及F2现有人工/待办链，选定[下一片合同](ManualGoalReplyNextSlice-20261014.md)：原人工答复后企业明确知悉并结束本次协作责任，继续UNSUPPORTED/PARTIAL、Case未完成、Grant不变。合同尚未实现／验收。

归档空白检查 exit2，仅保全原pytest失败log/XML尾空格；未修剪原件。未提交代码0，冻结修复提交89a423已保全，交付前正常分支尚领先远端1提交；最终推送和远端差异在handoff另核。

只读归档独审PASS：42件原件／导出hash、字节数和唯一脱敏变换一致，根80/独立3及逐窗失败保全准确，503冻结零漂移；下一片仅合同。记录保留 `.runtime/manual-goal-task-late-20261014/independent/archive-review.json`。
