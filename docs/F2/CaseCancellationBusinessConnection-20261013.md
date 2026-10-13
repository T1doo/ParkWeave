# 首次接单前取消的独立业务连接

选择 **独立业务连接 + 独立最小 SQL 角色 `pwci_case`**：原 native app `pwci_app` 和受限 writer `pwci_writer` 的 DSN/权限不变，owner `pwci_owner` 仅用于本轮新库 setup/核验/清理。另一方案是给原 app 增加同样的最小 DML；它不必获得 assignment/identity/control-system 权，但会把业务状态写权并入原 native 读取连接，扩大现有职责。因此不选该方案。新角色也无 identity/assignment/Run 写权、control-system EXECUTE、membership、owner、CREATE、TEMP 或 grant option。

源码 `b15e23d2b9808394ba1fe21942bd289288a9a3ac` 新增 [BusinessBinding](../../src/parkweave/case_cancellation_business_binding.py)：`from_spec` 绑定完整安装声明摘要、精确新 fixture 数据库及 Unix socket、Run/Case/资料来源、四个不同 SQL 角色；`check_spec` 拒绝来源/角色/数据库/期限变更；`check_private_dsn` 仅比较显式私有输入，不存储/回传/发现凭据；`read_path/recovery_path/check_cancel_request` 保留原 API 路径、原 key 和明确请求。生命周期/hash/reason/确认仍由原 GET 与 owner 输入产生，再由原取消事务验证，接口不自动重绑/重发/补签。

这是可离线验证的有限连接绑定接口，**没有挂载 API、构造 Store 或连接数据库，没有 live authority**。全部匹配也仅 DECLARATION_VALIDATED_ONLY、connection_authorized=false、actual_run=NOT_RUN。后续批准的 helper 使用另一个普通 Store/ASGI 客户端承载业务连接；原 native Store 继续持有原 app DSN、原 pinned writer，两者不互换。真实业务会话身份/OID/物理集群、有效 ACL、原授权/事务与 host 链仍待验证。

下表是当前原 `case_cancellation.read/recover/cancel` 调用链的完整表需求；机器行由 `required_privileges()` 返回，共 22 行。`SELECT *` 保持当前 SQL 所要求的全部列，不额外改写业务查询。

| 对象（public schema） | SELECT | UPDATE | INSERT | 原代码用途 |
| --- | --- | --- | --- | --- |
| principals | 全列 | 无 | 无 | Store.auth 两次核验；共享 advisory 主体锁；拒绝审计找 id |
| capability_grants | principal_id,capability,park_id,org_id,active | 无 | 无 | 当前 READ/EXECUTE |
| preparation_grants | principal_id,capability,park_id,org_id,active | 无 | 无 | 当前 PREPARE |
| preparations | 全列 | revision（仅满足行锁技术需求） | 无 | prep.scoped，GET FOR SHARE / POST FOR UPDATE |
| service_dispatches | 全列 | revision（仅满足行锁技术需求） | 无 | sd._root，parent→dispatch 锁 |
| cases | 全列 | state | 无 | Case 行锁、原来源与取消状态 |
| case_local_lifecycles | 全列 | revision,state,verified_snapshot,verified_sha256 | preparation_id,case_id,revision,cycle,state | local 行锁；已有行 UPDATE 或新行 INSERT，RETURNING * |
| case_local_events | 全列 | 无 | id,preparation_id,actor_id,request_key,fingerprint,revision,cycle,action,payload,snapshot | 原 key/关闭历史/证明；同事务事件 RETURNING * |
| runs | 全列 | 无 | 无 | 原建单成功与来源指纹 |
| operations | 全列 | 无 | 无 | 原 VERIFIED receipt |
| schema_version | version | 无 | 无 | 增量 30 存在 |
| service_dispatch_events | dispatch_id,action | 无 | 无 | 任意历史 ACCEPT 拒绝 |
| service_dispatch_offers | dispatch_id,state,receipt_step_id | 无 | 无 | 任意历史实际接单/步骤关联拒绝 |
| service_receipt_steps | preparation_id,case_id | 无 | 无 | 任意 receipt 步骤拒绝 |
| preparation_evidence | preparation_id,id,slot,version,text,source_kind,source_label,source_sha256,authenticity | 无 | 无 | prep.latest 原资料 hash 与快照 |
| authorization_audit | 无 | 无 | id,principal_id,category,outcome | API Denied 回滚后独立拒绝审计 |

另外仅需 CONNECT 本轮 fixture 库、USAGE public/pg_catalog 和既有相关内置函数的有效 EXECUTE（hashtextextended、pg_advisory_xact_lock/shared、clock_timestamp 等）；不新增 control-system EXECUTE、不需序列、REFERENCES、TRIGGER、DELETE/TRUNCATE 或资源释放权限。外键检查沿已有约束，不需给业务角色 REFERENCES。[PG16 SELECT 文档](https://www.postgresql.org/docs/16/sql-select.html)明确 FOR SHARE/UPDATE 至少需要一个列的 UPDATE 权；[INSERT 文档](https://www.postgresql.org/docs/16/sql-insert.html)明确 RETURNING 读取列需 SELECT。因此冷 GET 也不能仅授 SELECT。revision 授权是真实 SQL UPDATE 能力，数据库不能把它限制为“只加锁”；原 API 路径不修改这些列，业务修改仍需原明确动作和授权。表/列 GRANT 也不是逐 Case/RLS 隔离，有限绑定声明不能替代当前 API owner/tenant/source 校验或受保护执行进程。

拒绝路径 `er.bounded` 的原观察 context 在本链为空，不另开 controlled_plan 持久失效写；API Denied 仅需上表审计。没有 run_assignments、field_grants/action_grants、材料/分派事件写、资源关联/预约或 outbox 写。原授权、parent→dispatch→Case→local 锁序、事件事务、历史冷读和资源保留语义均不改。

根离线窗口 **35 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，3 受改路径首尾 hash 一致。独审自有纯反例 **11 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，与根窗不能相加；原 27/114 未重跑。最小 SQL 权的真实安装/有效权与新绑定执行、host/IPC 均 NOT_RUN，本轮未创建身份/组/凭据或改 ACL。代码及[清单独审](evidence/case-business-binding-20261013/independent/approval-checklist-review.md)均限定 PASS；原 app 权限歧义修文保留单独记录，未改签此前代码审查。后续动作范围见[精确审批清单](HostCaseCancelTrialApproval-20261013.md)。
