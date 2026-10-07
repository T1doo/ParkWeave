# ENG105：同 Case 的精确 Run 访问申请与决定

本轮接入 ENG089 原单 Run 申请、独立审批、拒绝、取消、撤销、期限与不可变审计合同。新增认证 API 与用户界面，只能在实际创建证明仍匹配的全新本地临时合成数据库中显式启用。正常 `configured_app()` 不启用；生产角色、既有 GRANT、SQL 迁移及持久权限不变。资料 REVIEW 权限不推导审批权；隔离演示另显式声明原资料专员夹具的单 Run APPROVE permit。

企业所有者提出指定现有同租户 service_executor 的 READ 请求。审批者须独立于申请人和受益人，明确核对对象及 UTC 时段，只能缩小请求期限；合同上限为 8 小时，当前桥接默认 4 小时。隔离审批会话从构造时起固定 8 小时，不滑动续期；单次租约到期仍可在会话内撤销和重新申请，会话结束须另启动新的全新演示。申请本身不写 assignment。批准后仅投影到该执行者/Run；不增加 EXECUTE、CONTROL、FILE_READ、其他 Run、资格判定或外部办理权限。原分派、本人接单、合成回执、企业核对仍分别执行。撤销及到期阻止后续访问，保留既有历史和回执，不删除已获得的副本。

## 接口与默认拒绝

认证 `GET /api/run-access/status` 明确返回 enabled。未显式附加桥接时为 false，所有决定接口拒绝。
`GET /api/runs/{run_id}/access` 返回精确对象、当前决定版本、Run/授权摘要、历史、当前角色允许的动作与实际投影状态。`POST /api/runs/{run_id}/access/commands` 复用原 RunCommand 和幂等键，拒绝跨租户、跨 Run、旧版本、审批者资格失效、旧批准重放及扩大时间范围。

独立 SQLite 为原审批/审计来源；PostgreSQL 是受约束的投影。二者没有共同原子提交：决定先提交，投影后提交。投影失败不会给出可访问状态；明确原请求重试还须匹配当前决定。撤销先使来源失效，即使 PG 清理失败，也不能继续访问。界面区分候选批准和实际访问，不把二者合成成功。

只在精确 FixtureDatabaseEvidence 通过原发行注册表及 live cluster/database/start/owner 核对后，隔离库增加 nullable managed_access JSONB。NativeReceipt、伪造/复制证明、未知库及默认部署不进入此安装入口。不接管 NULL legacy assignment，不修复旧身份，不新增通用权限系统。

所有实际 assignment 判断覆盖 Store、执行者目录、分派和回执列表、Case 路径、受控方案和规划来源。managed 行必须同时匹配审批来源、期限、Run 与当前主体 READ/版本；缺 provider、元数据异常、来源不可用或变化均拒绝，不退回 legacy。事务持有共享精确 Run 锁，决定持有独占锁；Store 在提交/返回前重验期限，等待跨到期会回滚。原 NULL legacy 行沿用原合同。列表仍只扫描原最近 101 条，过滤后保留原 has_older_records 并报告 access_filtered；不承诺返回所有更早合法项。

## 隔离演示与验证记录

启动说明见 [隔离演示](ENG105-IsolatedAccessDemo.md)。其 API 与实际证明留在同一进程；原 LOCAL worker 单独运行。原企业、专员和执行者身份/目录是显式合成初始化，Run/Case/assignment/分派/回执初始为零，批准由网页动作写入。

验证结果、精确源摘要、失败历史及最终单次浏览器证据见 [机器证据](../integration/ENG105-RunAccessEvidence.json)。最终桥接33PASS；原候选30PASS、原相关PG170PASS及metadata101PASS各保留原冻结范围。真实新Case的申请→独立批准→原分派/接单/提交/企业核对→撤销与原Run403/列表移除通过，21项三宽度检查和独立复核无实质阻断。上一轮双流程报告不用于fresh结论；最终driver写入前实时空列表与事后唯一事项一致，临时API/worker/PG目录已确认清理。历史全量证据仍仅代表其原冻结源；本轮专项不拼成新的全量或正式验收。首次默认受限网络运行卡在原未改 TestClient 的 asyncio portal，并保存调用栈及中止记录；随后仅通过工具的单次附加本地网络权限重跑，无代理、身份或环境策略变更。

F1 未签收，F2 仅并行探索，PR0 全目标与正式 AT/EX 未由本轮自动签收；Case 资格未知、本地回执不代表外部履约。R4 关闭，真实模型调用/预算为 0。Linux 与 Server 工程测量不能替代 Win11 或 installed Windows 实测；本轮不运行 Windows owner/ACL/security 操作。原环境和备份保留。
