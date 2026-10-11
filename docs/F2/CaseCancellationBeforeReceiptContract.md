# 接单后且从未提交人工回执的有限取消合同

本片从已签收 `396602aa4e4889cb32d6af89a2b32cc3e45b5029`（源码/测试 `557528da70d905859d7fd09dc0b4ed8f5545af51`）继续原产品 §5.5、§7.1、§7.4。开发分支为 `dev/f2-case-cancel-before-receipt-20261011`。根任务唯一写源码、测试与 Git；独审独立只读、自己的运行时证据另存。下述是实施前冻结，不代表测试已通过。

## 有限对象及拒绝条件

仅已有资料、已核实成功建单的普通 SYNTHETIC Case，历史至少一次真实本人 ACCEPT，全部历史 receipt generation 均为有精确 ACCEPT/CREATE 证明的本地人工 AWAITING_RECEIPT 步骤；未提交过任何回执。允许合法换人未决、拒绝/撤回后及新材料重接单历史，但核查全世代，不能只查当前指针。

任何历史 service_step_receipts、非 CREATE receipt event、非初始步骤 revision/state/current_receipt_id、遗留直建步骤、接单/CREATE 证明失配、外部受理/履约、本地关闭历史、不支持 Case 状态、隔离访问/执行 provider 或来源一律拒绝。取消后恢复、任何提交/确认/关闭之后取消和完整生命周期均不在本片。

保留原 `/case-cancellation` 的首次接单前语义；另设 `/case-cancellation-before-receipt` GET/POST/recovery。新 action/scope 与旧事件清楚区分。企业原 owner 当前 READ/PREPARE，POST 另需 EXECUTE；精确 Case、资料/生命周期版本及完整接单/步骤/计划/资源关联来源 SHA、明确布尔确认与非空原因。原键同参只返回原提交，异参冲突，两个入口不能互换键；丢响应仅 GET 原入口原键，不自动重发。

## 事务与保留历史

沿 parent → dispatch → Case → local ledger 顺序，取消持有 parent UPDATE 至提交；SUBMIT、ACCEPT/换人、材料、计划采用、资源关联均先持有同一 parent SHARE/UPDATE，再检查 Case。取消先提交则所有晚写（包括原写键 replay）拒绝；SUBMIT 先提交则取消重读完整历史并拒绝。其它先写若改变预览来源则要求刷新并重新明确确认。

取消事件和 Case/local CANCELLED 同事务；事件失败全部回滚。原 Run 成功、资料、实际接单/CREATE 历史、步骤、claim/link/预约及容量原样保留，不伪造 WITHDRAW，不自动释放。独立资源释放/组合取消沿当前原授权继续。历史有权 GET 保留，不触计划隐式失效；旧 outbox/通知/回执 UI 重核 Case，历史可读且无可提交/接单动作。

新 schema 31 仅扩原不可变 local event action CHECK，在具有原创建票据的自有 Linux 临时 PG 安装；无新表、Grant、registry、角色或生产迁移。原 Windows/native 默认拒绝边界保留。

## 验证门

1. 真实 owned PostgreSQL 双方向锁等待：取消/SUBMIT、再次 ACCEPT、换人、材料、计划采用与资源关联；不得用 SQLite 代替。
2. 新旧全部写入口与内部旁路、所有 receipt action、legacy CREATE、授权冷读/撤权/跨租户/非 owner；完整历史无隐式写、资源仍占容量与独立释放。
3. 同/异原键并发、事件故障回滚、两入口原键隔离、丢响应原键冷热 GET、历史提交/证明损坏与隔离来源反例。
4. 原页面离线 NodeVM：新范围说明、UNKNOWN 不重发、冷恢复选原入口、迟到 POST/GET/回执/分派回复不能复活已取消动作。
5. 复用上一36完整模块回归范围，在最终冻结源码单次实际完成；同一新旧模块测试标识对比，旧失败不覆盖；原始 JUnit/stdout 脱敏公开，原与导出 SHA、独审、远端与未提交/未推差异明确。

历史 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 保留，不启动浏览器或换 URL/工具重试。无部署、真实模型/付费调用、凭据/网络配置、生产迁移、权限扩大、强推或受保护分支修改。
