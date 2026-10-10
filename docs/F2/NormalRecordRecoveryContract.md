# 正常办理记录全进程停启只读找回：实施前合同

基线 `9f4aef7bea7000a102c1748ef0c70b69597087b7`。对照主方案 F1-T03/T04、F2-T05 和 AT-01/17/19/34/35：AT-17 要求新 worker 先核对既有效果、旧 fence/token 不可写新状态；AT-01/34 要求真实原生停启、保留数据、停止期间不声称执行、重开不重复操作。本文只实施 Linux 合成正常本地建单记录的只读发现与冷启读取，不称完整 AT 或 Windows 实机停启/关机验收。

## 已有合法资格与缺口

正常 `configured_app` 从显式应用 DSN 新建 Store；原 PostgreSQL principals 的 token_hash、active、role 和 capability_grants 已持久化。原会话须由本人重新输入，每次 GET 经原 auth/共享 principal 锁、当前 READ、park/org 和 owner 复核，不执行 seed 或恢复撤权。正常已有 `Store.read`/GET Run 不需要 fixture proof。已有资料准备目录要求其原 PREPARE/获派审核资格，不替代没有准备事项的本地建单目录。

P4/P5 组合影子历史和 managed Run access 要求原进程内签发对象/registry，并绑定原 PG 启动代际；P4 只读代理明确只接受原 issuer 存活。正常身份 READ 和已保存 SQLite 文档不能替代该证明。完整 issuer 退出后该组合历史没有已审核的持久重新取得资格流程。本次不序列化/搬运/重签旧 proof、不扩大长期凭据/Grant、不接续旧 socket，不保留代理冒充全进程恢复。P1/P2 独立预览读取有其原目录/数据库/source 与当前权限合同，不能笼统称全部依赖发行证明；其默认未 attach 的正常启动读取和 P3 不同类别资格也不纳入本片验收。

要另行闭合影子历史，须先单独决定并审核：由哪个已有合法主体重新核验，可信数据/namespace/源合同与当前租户/资格的绑定，撤权/到期/数据库替换后的拒绝，记录完整性及明确只读能力；是否允许建立该持久资格。单有既有数据库 owner 权限不构成这项许可。在该契约前影子历史继续拒绝；本片推进不依赖它的正常产品读取。

## 最小实现与写入边界

新增 GET `/api/runs`，仅 enterprise_operator 本人现有 SYNTHETIC `case.create` Run，当前 active READ 与原 principal/park/org/owner 交集；不列 facts.assess、fault.record 或任何非 owner 指派（managed 也不列）。只读事务，原表 SELECT，不新增 SQL 表/列/索引/迁移/Grant、会话种类或凭据。参数 limit 为 1–50，默认 20；after 为可选 UUID，按 Run UUID 稳定升序，不称按办理时间排序。最多读取 limit+1，响应仅 scope/read_only/automatically_replayed、items 的 run_id/state/revision/namespace 及最后已可读 ID 的 next_after；无 goal、input、request_key、fingerprint、Case/Operation/回执正文、身份值或 total。未知/他人游标只是本人集合中的排序界限，不读取游标所属记录。

原页面协同区增加明确的“找回我的本地办理记录”、下一页与只读选择。目录和会话只在内存，空身份不发请求，冷页面重新认证后显式 GET；不自动保存 token/正文、不自动提交/重放/控制/确认 P1–P5。身份、运行和 tab 切换立即清私有目录，独立请求 generation/token 防迟到跨身份显示；真实 403 清目录及原运行输出。选择只填原 run_id 并调用原 Run GET；原控制仍须用户明确操作和原权限。

## 实际验核要求

先有界工具/资源核验，所有 PG/API/worker/Chromium 窗口串行。全停启用测试自己新建的 `/tmp` 私有合成库，首次独立原进程按现有合法 creation receipt/migrate/roles/CLI seed 流程初始化，再由正常 configured_app/worker 建单；原 worker 自然 drain，确认无待处理 outbox/notice 后固定 canonical 业务/权限逻辑行基线。正常停止原 API/worker/browser/PG及初始化/发行父进程；逐个记录 PID+create_time 并确认原实例退出后才启动新一轮。

新轮只用同 PG data 及其原启动程序、显式原应用 DSN、同私有原会话文件，正常 configured_app/worker 与冷浏览器。不 migrate/seed/create role/Grant，内存 registry 必须空、没有原 issuer/provider。验证 PG PID/start 变化而 system_identifier/database OID/原会话文件 hash 保持；明确目录/选择 GET 找回原已提交 Run/Case/Operation，不产生重复 Case/operation/outbox/通知消费/权限变化。数据库物理 WAL/control 文件会正常改变，不宣称物理文件字节不变。拒绝沿原 Denied handler 记录脱敏 authorization_audit，允许且单独核对该原审计，不把它伪称业务写。

覆盖分页/边界、重复与并发 GET、当前撤权/错误会话/跨企业园区、同企业不同 owner、facts/FAULT 不列、非 owner 与 managed 不列；页面 320/390/1200、冷认证、身份/运行/tab/在途响应/403 清理、所有恢复请求为 GET、不存私密值。AT-17 相关原 worker/fence/未知效果工程测试另窗实际回归，不借目录冷启替代失联核对；完整 AT-17/Windows 原生关机仍 NOT_RUN。

源码冻结并普通候选推送后，精确 SHA 根相关回归及独立 API/页面/全停启审查通过才正常快进开发分支、普通推送并核完整 SHA/远端/未提交未推送差异。所有旧失败和新失败私有保全，公开仅安全分类/计数/hash。保持原合法项目临时缓存和锁定依赖；不使用旧实例、不重新供应、不碰未知资源/锁，不 main/force push/部署/模型/付费/真实批准履约/安全网络修改或新协议接受。真实资源/访问拒绝停止相关动作并报告。
