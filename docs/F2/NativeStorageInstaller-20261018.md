# 普通已有库的显式 native 存储与精确 ACL 安装代码

本片接续已有安装启动 profile，新增 `native_run_access_installer`，把原 InstallationSpec、目录预检、三份固定 SQL 和 RuntimeGuard 的权限合同接到一个显式安装入口。原 host、普通配置工厂、业务算法、SQL 文件及旧 owned fixture 发行门均不修改。本片没有运行安装或发行任何真实政策、批准、身份、凭据或业务 Grant。

## 最小调用闭环

调用者先提供同一实际普通库的严格 InstallationSpec、InstalledRuntimeLayout，以及已存在、空闲、autocommit 的精确 plain psycopg.Connection；连接主体必须是原 installer，host/port/dbname/user 与 spec 相符，函数不打开连接、不发现目标、不改变 caller 的 row_factory。

`inspect(controller, connection)` 在明确 READ COMMITTED READ ONLY 事务中核实际 session/current_user、物理库 OID/system_identifier。读取原 schema_version 数据前，仅用 pg_catalog 拒绝非原 owner 的普通整数表、view、RLS、规则、分区或继承结构；先验通过才获取 ACCESS SHARE ONLY 锁，再复核。原目录读取器及现有有效权限检测复用，自有 dict_row cursor 补上 schema_version SELECT、CONNECT/public USAGE 和适用函数默认 ACL 观察。只读事务以 rollback 结束。输出 snapshot 与纯 `prepare(spec, layout, snapshot)` 计划，授权及激活标记仍为 false，不读取私钥或审批文件。

计划绑定精确 spec、layout、完整目录快照与原 SQL 文件 SHA。仅允许缺失的三列、三函数、三 trigger，以及原 runtime.required_privileges(revision) 缺少的精确 writer SELECT/INSERT/UPDATE/EXECUTE；LOCK_UPDATE 不生成权限语句。固定 SQL 按完整 grammar 消费 dollar body，拒绝未知、重复或未消费语句，不按分号拆分，不使用 IF NOT EXISTS 或 OR REPLACE。已有正确对象不重放；冲突、未知版本/owner/函数重载/ACL/缺失观察拒绝。

部署者通过原外部批准机制签署 `installation_request(controller, plan)` 的 INSTALL_NATIVE_STORAGE_AND_EXACT_ACL 动作，放在本次既有受保护 root 的 `host/install-approval.json`。代码只用原 `host/approval.key` 核验，不提供签署批准、创建 key 或发行 policy 的工具。启动批准不能代替安装批准。计划和 controller 在 install 入口作私有规范 JSON 快照，调用者验签后或锁等待时修改原 dict 不能扩展批准差异。

`install(controller, connection, plan, authorization)` 默认拒绝；只有显式固定批准路径、受支持 Linux/root、原 UTC 区间、原受保护身份/源码/依赖观察及精确 HMAC 批准全部通过，才能建立一次 O_EXCL、NOFOLLOW、0600 的 install-claim。原安装收据字节 SHA 须预先与 layout 相符。既有 claim、收据或未知文件不采纳、不覆盖、不删除。

执行在 READ COMMITTED 事务中，设置本事务搜索路径及 5 秒 statement/1 秒 lock timeout，核实际 installer/物理库，取得计划相关 advisory 锁及原 14 表 ACCESS EXCLUSIVE 锁，然后重读目录并重建完整计划；与已批计划不同则在任何 DDL/GRANT 前回滚。逐项执行期间与提交前均核原 policy 截止；提交前再检查原存储和 runtime 全部权限合同。提交确认后才用既有 root key 生成并发布原 host 已支持的安装收据；没有自动启动、绑定更新、API 重建、激活或模型调用。

## 支持范围与失败边界

仅支持已预先硬化、已具备原 baseline32 和现有 installer/app/writer 角色、完整 installer owner 映射、revision 锁列的 DIRECT_DML 普通安装。CONNECT/public USAGE 必须已有；未知默认函数 ACL、额外权限、危险角色/成员关系、PUBLIC 带来的额外 TEMP/CREATE/系统函数权限等拒绝。不会以 REVOKE 修复已有权限，不创建角色，不修改已有未知目录/ACL，不把 fixture 发行器作为普通批准依据。精确新增 writer SQL GRANT 仅在将来该动作获独立批准时才执行；本片测试未执行 SQL。

表锁防止本次表结构变更交错，不能冻结并发管理员的角色、数据库权限或其他目录变更；部署者仍须安排独占维护窗口，原运行时每次实际连接/写入的实时检查保留。只读 inspect 是待批快照，不能承诺在批准等待期间维持不变。

提交前错误尝试 rollback 并保留原异常；rollback 响应丢失报告 ROLLBACK_UNCONFIRMED。COMMIT 抛错报告 COMMIT_UNKNOWN，即使服务器可能已提交也不重试、不补偿 DROP/REVOKE。提交后收据发布失败或响应丢失报告 COMMITTED_OUTPUT_UNCONFIRMED；数据库与文件不是跨系统原子事务，不保证断电后的目录持久性。所有失败保留 claim、未知输出和异常链，无自动重启或清理。只读结束不确定性单独报告 READ_ONLY_END_UNCONFIRMED。

## 定向离线验证及下一真实前置

直接 unittest 的 28 个唯一方法覆盖固定 SQL、首次/部分/已齐差异、原批准拒绝、计划替换、默认 tuple 连接、自有 cursor、未知基线先验、只读采集、目录漂移、DDL/GRANT 中途失败、后验/过期回滚、commit/rollback/文件响应丢失及不覆盖。正向均为显式 DI；实际连接、socket、process、memfd 与权限修改在测试内被禁止。没有使用 pytest/conftest 或 PG fixture。最终冻结提交、独测重叠及输入摘要见同名 evidence/validation。

开发 v1：23 方法，1 个失败为断言在原 trigger 字符串中误匹配 REVOKE，改为检查语句前缀；v2：23 PASS。独审识别计划可变引用、默认 tuple cursor 和 schema_version 先读后验问题后修复；v3：28 方法，1 个失败为测试类上 tuple_row 函数被 Python descriptor 绑定；改用 staticmethod 后 v4：28 PASS。原失败日志保留，不与最终冻结批次累计。所有这些观察均不证明真实 SQL/锁/ACL/文件权限或安装行为。

下一真实执行需要同一目标的现有物理库/角色/owner、已安全的基线与外围权限、既有空闲 installer 连接、原合法单 Run/Case/preparation policy 及原 UTC 区间、完整精确 spec/layout/源码/依赖/私有 bootstrap 摘要、本次既有受保护 root 和原 root approval key、由原机制独立签署的精确安装批准、匹配原安装收据 SHA，以及独占维护窗口。本模块不发行 policy/key/批准，也不硬化已存在的未知权限；若这些原始输入不存在则准确停止，不能用合成测试补齐。

安装后仍需原独立启动批准、受支持 sealed FD 的 Linux/Python、本次新 boot/root、最终受保护内外绑定/API 重建，再由原流程提供合法 PREPARE/REVIEW_ASSIGNED、preparation_catalog、当前身份/来源代际等真实业务输入。本环境此前属性观察缺少 F_*SEAL 常量，真实 protected host 继续拒绝，没有数字 fallback 或权限修复。

真实普通安装、政策/批准发行、服务/IPC、Windows 正式 AT、无夹具 AT35 与真实业务场景均 NOT_RUN；完整 F2/项目尚未完成。本片只新增三个文件，不修改 main 或旧交付证据。
