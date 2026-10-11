# ASGI 有界原键核对：独立候选合同

父候选 `8a8a0321d63abd05de36b71e0b51a56593bb2e8f` 获限定放行，不入 dev/main。本片在独立分支 `acceptance/asgi-history-key-20261011` 补原只读历史计划的原键查询；不修改旧回执或受限执行链。

GET `/api/cases/{case_id}/preparations/{preparation_id}/history-summary/{stage}` 可附单个 `request_key` 查询参数。不提供时保持原全历史 envelope；提供时原样传给现有 `read_case(..., key, stage=stage)`，复用既有内存基线、完整历史校验和纯摘要投影。原 `_key` 合同为精确 Python str 和 ASCII `[A-Za-z0-9._:-]{1,128}`，不 trim、大小写折叠、扩展语法、二次 URL 解码或截断。空串、129字符、空白、斜杠、非ASCII等拒绝；重复 request_key 参数也拒绝，不隐式选择最后一个。

可信完整历史中只有精确原键匹配时，返回既有 `status=COMMITTED` 及 `result=固定摘要`，其中摘要的过去 state 保持原值；COMMITTED 表示观察到该原记录，不表示执行成功或当前可执行。未观察到仅 `status=NOT_OBSERVED, result=null`，仍保留原完整 history、只读和不重放限制。不得推断 FAILED、生成替代原键、自动重发或恢复执行。请求 key 只用于核对，不登记 baseline、记录或授权。

默认未注入、非精确 reader、错 stage/Case、当前本人/tenant/READ/三字段权限失效、来源版本/期限/撤回失效和基线过期/撤销仍拒绝，即使请求不存在的键也不能跳过这些检查。投影后重核当前上下文、基线、所有历史行和 pinned stage。若历史在本次读取中途增删/改动，即使新增历史被独立服务端 baseline 同步锚定，本次读取仍拒绝；后续全新读取只有重新通过当前完整检查才可观察到新的原键状态。不存在状态是该次快照观察，不是永久不存在或可重发的证明。

非法键通过原 Denied 通路返回统一 403 `record unavailable or authorization denied`，不采用会回显输入键的 Query pattern/max_length 验证错误。不存在合法键正常结果中的 request_key 是调用方自己的精确查询键；拒绝结果不回显该键、历史键、语法详情或原记录。成功读取不写任何数据库表；已知 token 的拒绝可沿原处理器追加 authorization_audit，业务、权限与 outbox 另行保持不变。

验收限本实例合成历史、显式 fixture baseline、现有隔离 PG、纯投影与进程内 ASGI。覆盖原键边界/已存在/不存在、全历史兼容、迟到历史与中途变更、当前权限二次核验、Case/stage/来源拒绝及错误无泄露；独审仅写私有 /tmp 证据，不写仓库/Git。没有浏览器、替代导航、真实模型、生产或持久登记、新 Grant、凭据或网络权限修改。保留原 data: 管理员拒绝、Windows/整页、持久登记及完整发行者/PG重启未验限制。
