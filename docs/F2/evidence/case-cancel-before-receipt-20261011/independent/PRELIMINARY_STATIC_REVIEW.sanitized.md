# 接单后、首次回执前取消：初步独立静态审查

结论：**LIMITED_STATIC_REVIEW**。新片实现仍在进行；本记录不是冻结源码验收，未运行测试、访问 PostgreSQL、操作 Git 或启动浏览器。根任务是唯一源码、测试和 Git 写入者。

父任务报告基线 `396602aa4e4889cb32d6af89a2b32cc3e45b5029`、前片源码 `557528da70d905859d7fd09dc0b4ed8f5545af51`，本阶段未用 Git 核实。读取文件即时 SHA 及精确范围见同目录 JSON；不能作为最终清单。

ACCEPT 会同事务创建 `AWAITING_RECEIPT`、revision 1 的空步骤和 CREATE 事件。CREATE 不是回执提交；旧 legacy CREATE 没有实际 ACCEPT，不能取得新片资格。REOPEN 虽返回等待状态，却保留实际回执；材料换版和换人会保留旧步骤。因此必须按整个 Case/资料的全部世代查实际 receipt 和所有非 CREATE 事件，不能仅看当前指针、状态或空 current_receipt_id。

取消 parent UPDATE 与 SUBMIT 的 parent SHARE 串行。SUBMIT 已在 parent SHARE 下先检查 Case，再锁步骤；ACCEPT/换人也先锁 parent/dispatch 再检查 Case。维持 parent → dispatch → Case → local 顺序，后续必须真实 PG 验证两个胜出方向及其它材料、计划、资源竞争。静态阅读不能代替锁等待验收。

初版新模块已覆盖整段步骤、实际 receipt、非 CREATE 事件、初始状态与 ACCEPT/CREATE 基本字段证明。仍已提醒唯一写入者：扩展 handoff/new-material lineage 尚需逐字段核对及正确历史 predecessor 绑定；这是未执行的静态疑点。冷普通 Store 下持久 managed_access 也要拒绝，不能只看 provider 是否挂载或 receipt 是否有 adapter_execution；inactive 保留元数据仍属隔离来源。

旧片从不取消有步骤的 Case，所以回执页面此前无需取消投影。新片须令 GET/list/页面明确历史只读，人工提交、本地执行和企业回执动作均不可用；晚到响应不能重新激活动作。根已开始补 Case/can_submit 投影与页面护栏。新 schema31 还须保留29前置及受限普通手工交接支持，不能让旧 max29/30 门意外关闭现有功能。

取消保持原 ACCEPT/CREATE、资料、成功 Run、资源关联和容量，不伪造 WITHDRAW；独立资源释放按原授权办理。新旧入口的原键、action、scope 必须隔离；丢响应仅原键 GET 核对，事件失败与持久状态同事务回滚。

下一阶段：完成上述静态疑点修正与冻结合同/源清单后，按父任务另行授权，在独审自己的 owned PostgreSQL 验证历史损坏、隔离来源、授权与双向真实竞争。当前测试全部 **NOT RUN**，没有声明功能 PASS；前片独审报告、失败证据及浏览器明确拒绝均保持。
