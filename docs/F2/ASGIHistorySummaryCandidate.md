# 独立 ASGI 本人历史摘要候选

本候选从已推 dev `b58cf201de3d6ca4e249bec3e8544ea53163807a` 重新实现，独立分支 `acceptance/asgi-history-summary-20261011`。main/dev 不集成。旧任务保留候选 `6002be735e8fe5c05443cd8499bd5f8858556891`（旧源码 `8538c77ccf92d554351c7d1eae93153341984108`）；本实例没有假定共享其文件，也不声称恢复或还原该提交。

新增只读 GET `/api/cases/{case_id}/preparations/{preparation_id}/history-summary/{stage}`，stage 仅 P4/P5。`create_app(store, *, summary_reader=None)` 必须由服务端显式注入精确 `MemoryHistorySummaryReader`，且 stage 匹配。None、子类、鸭子类型、错 stage 均拒绝；请求参数、Store 属性和环境不能登记 reader。`configured_app` 保持默认 None；没有生产、文件、持久化或自动登记入口。

`read_case` 要求实际 UUID Case。当前 auth/READ/企业本人/park/org 筛出 preparation 后，立即核对路径 Case，早于历史行读取、解码和事实私有来源读取。复用原 `current_context` 的 Run/Case/来源、三字段 READ、显式事实用途选择、当前来源完整性/版本/期限/撤回检查；来源与基线、行在投影后再核。精确 Case 和 reader stage 在最后观察中再核。原 `read` 接口保留。

返回原固定摘要，加 `case_id`、`stage`。不返回正文、标签、proof、来源快照、事实选择或授权租约。不重放、恢复执行或批准权；`execution_available=false`、`NOT_EVALUATED`、`formal_writes=0`、`new_grants=false`。原 P4/P5 GET/POST provider 精确类型和执行门不变，网页不接入。已知合法未声明来源版本变化仍按原合同 STALE；已声明事实用途的被选来源变更、过期或撤回按现有事实 READ 合同拒绝。协作锁与两次快照不是全来源原子性承诺。

本次测试只使用合成历史行、服务端显式内存 fixture baseline、仓库现有隔离 PG fixture 和进程内 ASGI TestClient。没有 listener、浏览器或替代 URL。成功读取与 reader 拒绝事务不写业务、权限、outbox；ASGI Denied 沿用原处理器，对已知 token 的 `authorization_audit` 可追加一条 API_AUTHORIZATION/DENIED。fixture 管理员撤权、篡改和过期安排是测试布置，不是生产授权修改。

本实例测试日志、JUnit 和独立审查结论见 `evidence/asgi-history-summary/`。旧 76 项结果不计为本次通过。独立审查只读源码/Git，允许写私有 `/tmp` 证据，不写仓库、不 push。

保留未解决限制：原浏览器 `data: ERR_BLOCKED_BY_ADMINISTRATOR`、Windows/整页验收、持久登记和完整发行者退出/PG 重启恢复。ASGI 内存候选通过不构成这些验收。本实例默认 origin 可读或候选 push 成功也不证明旧容器认证恢复。
