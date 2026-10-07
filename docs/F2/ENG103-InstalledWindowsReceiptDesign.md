# ENG103 Installed Windows 创建回执历史设计

最新状态：ENG104已实现并离线测试显式adapter候选，默认installed入口仍关闭；见[代码与验证](ENG104-CreationReceiptAdapter.md)。下文保持ENG103当轮设计和未实施状态，不作当前代码状态。

基线 `81ff445`。本轮仅在原离线合成边界内设计代码接口与测试，不实现或启用 native adapter，不修改 lifecycle、Store、migration025、测试、角色或权限。没有运行 PostgreSQL、Windows installed/native、浏览器或真实模型，没有执行 owner/ACL/security 写入，也没有创建凭据、身份、Grant 或数据库。本文不是部署批准、真实安装通过证据或可使用票据。

## 已确认阻塞

`scripts/windows/lifecycle.py:setup` 先要求目标 `parkweave` 的 owner/app DSN 可连接，然后直接 `owner.migrate()`。它没有维护连接、创建前观测、实际 CREATE DATABASE 或创建后回执。目标不存在时，目标连接检查先失败；目标已存在且 schema<25 时，Store 缺少发行回执而拒绝。这两条拒绝均应保留。

`case_fact_clarifications.capture_fixture_cluster` 只用于调用方实际新建的空临时集群；它验证临时目录、POSIX 所有权、live cluster 和初始数据库集合，并明确排除 installed cluster。不得添加 Windows 平台例外、跳过所有权/空集群条件、用名称或环境标志代替证明。

Store 对 migration025 要求 `FixtureDatabaseEvidence`；该类型又要求两个进程内发行 registry 中的精确对象身份。手工构造、复制或继承对象不构成合法发行。独立新 helper 无法直接接入当前 loader。SQL025 也明确没有 implicit production/native opt-in。因此接线候选需要共同协议、native issuer、loader 与 SQL 合同的独立工程评审，不能通过伪造 fixture 对象解决；离线代码/测试候选可在现有授权内推进，真实 native 发行与 owner 创建动作另需明确范围。

## 独立且默认关闭的未来入口

未来设计一个明确命名的 fresh synthetic database creation 入口，与默认 setup 分离。默认 setup 不猜测用户希望新建数据库，不补证、不覆盖已有配置，不自动调用该入口。新入口只处理显式批准的本地新合成目标；初始设计目标名称为精确 `parkweave`，不得扩大成任意数据库名。现有同名数据库无论是否空、schema24、UUID 外观或当前用户所有，均不符合 fresh 创建条件。

维护 DSN 必须由已授权会话显式提供，并包含明确本地 host、port、maintenance database 与主体。不得从目标 owner/app DSN 隐式改写 database 或猜测维护凭据，不读取密码缓存、探测其他主体或自动建立角色。缺来源、权限或查询能力时立即拒绝，不请求更高数据库权限作为自动恢复。维护身份是否具有创建权限是未来批准的前置条件，本轮没有批准实际使用这些权限。

显式创建入口必须在目标 DSN 连接检查之前执行，随后仅验证预先明确的目标 owner/app 连接范围；不得因为目标连接失败改用维护身份启动应用。新数据库所有者必须是预先批准且已存在的主体，CREATE 不伴随任何 CREATE ROLE、GRANT、ALTER OWNER、ACL 或安全描述符动作。

## 创建证据与共同协议的审批范围

Native issuer 的可信输入来自同次实际数据库操作，不来自 JSON、路径名称、schema_version、配置文件、CLI 布尔值或用户提供的 SQL GUC。它读取并绑定维护连接的 system_identifier、data_directory、postmaster_start、current_user/session_user 与初始目标不存在事实。目录字符串是 live SQL 身份绑定字段，不单独证明 Windows 文件所有权或 ephemeral 集群；不得把它宣传为 owner/ACL 或受保护 authority 证明。

Issuer 自己执行精确、正确引用的 CREATE DATABASE，只有数据库命令返回明确成功后才继续。CREATE DATABASE 在独立 autocommit maintenance connection 上执行，不能放进普通迁移事务。创建成功后，从明确目标 owner connection 验证相同 cluster/start、预期 database_name、实际 database_oid、实际 database owner、current/session owner，再发行进程内精确对象。只读观察“之前不存在、现在存在”而没有 issuer 自己成功 CREATE，不足以发行 native 回执。

发行回执不是针对 DDL owner 的安全沙箱；DDL owner 本来能够绕过 SQL。创建前观测和成功 CREATE 不保证抵御其他特权管理员在随后改名、删除或重建目标，所有可观察绑定变化都必须拒绝。不声称完整并发线性化或新增受保护 authority。

未来共同协议应允许已评审的 fixture issuer 与独立 native issuer 提供同一个迁移授权能力，保持现有 fixture 路径验证不变。审批须覆盖：精确发行对象来源、进程内 registry 与生命周期、native fresh 范围、Store 接收类型/接口、loader 调用顺序、SQL025 合同文字及全部拒绝测试。不能仅将 isinstance 改成 duck typing 或接受任意具有 authorize_migration 方法的对象；也不能开放“直接传入票据字段”接口。接口实现前不能宣称已与原 Store 兼容。

## 接口伪代码（描述，不可执行）

```text
default_setup(existing_target_owner_dsn, existing_app_dsn):
    preserve_existing_configuration_and_authorization_checks()
    use_existing_loader_without_native_receipt()
    # schema<25 的现有拒绝保持；没有自动 fresh fallback。

explicit_fresh_synthetic_creation(approved_request, explicit_maintenance_dsn,
                                 explicit_target_owner_dsn, explicit_app_dsn):
    require_future_enablement_and_exact_approved_local_target(approved_request)
    validate_explicit_connection_sources_without_credential_discovery()
    maintenance = open_explicit_maintenance_connection(autocommit=True)
    before = read_live_cluster_and_current_session_identity(maintenance)
    require_exact_authorized_existing_subject(before)
    require_target_absent(maintenance, approved_request.target)
    execute_exact_create_database(maintenance, approved_request.target)
    # 异常、超时、连接丢失或成功不确定 => 不发行；禁止重试补证。
    target = open_explicit_target_owner_connection()
    after = read_live_cluster_database_and_owner_identity(target)
    require_same_cluster_start_and_exact_target_owner(before, after)
    receipt = reviewed_native_issuer.issue_live_object_from_completed_create(after)
    store = construct_existing_store(explicit_target_owner_dsn)
    attach_via_future_reviewed_common_receipt_interface(store, receipt)
    store.migrate()
    # 未来 loader 在其原连接/事务内调用 receipt.authorize_migration(c)。
    # 不执行角色/Grant/session/security setup；应用启动另属原批准流程。

receipt.authorize_migration(migration_connection):
    require_exact_issued_live_object_in_same_process_registry()
    require_explicit_non_autocommit_transaction()
    require_current_cluster_start_name_oid_and_owner_match()
    issue_original_single_row_temp_ticket_on_this_connection_and_transaction()
    preserve_original_SQL025_checks()
```

伪代码中的 enablement、approved_request、issuer 和共同接口均未实现，不是环境变量、凭据或新增权限定义。实际 SQL 参数/Identifier 使用、维护连接资源关闭和拒绝错误脱敏须在未来实现评审中核对。

## 同事务强绑定与失败保留

迁移票据继续只在 loader 实际 migration025 的 owner connection/transaction 内发行，保留 database OID/name/owner、system_identifier、data_directory、postmaster_start、backend_pid、transaction_id、发行 nonce 全部绑定和精确一行要求。实际 current_user 与 session_user 均须匹配当前 database owner。COMMIT/ROLLBACK 后临时票据消失；autocommit、另一连接或另一事务不能沿用已发行 SQL 行。

活 receipt 可以在同进程原 cluster/start/OID 不变时重新核验并为新事务发行新票据；这不是保存 SQL 票据或重启补证。进程重启、cluster 重启、目标 DROP/recreate 后 receipt 失效，不从磁盘重建。未来若要求崩溃后恢复，需要独立新信任与保留协议，不在本设计中添加。

CREATE 成功但 migration 失败时，事务内迁移回滚；已创建数据库不自动 DROP、不覆盖、不重新归属、不补 Grant。记录固定、不含 DSN/路径/凭据的拒绝类别与“新数据库可能已存在，需独立复核”的结果。创建结果未知时同样保留，不将连接失败当成未创建或成功。后续默认 setup、重新运行 fresh 入口或 schema24 检查不能为它补造 receipt。

## 拒绝与测试矩阵（设计，NOT_RUN）

| 输入/变化 | 必需结果与证据 |
|---|---|
| 默认 setup、缺明确 fresh enablement/批准范围 | 保持原行为，不打开 maintenance connection、不 CREATE、不发行回执。 |
| 维护 DSN 缺失、远端、service/多 host/范围不明、凭据未提供 | 固定类别拒绝；不猜测/探测凭据，不 fallback。 |
| 目标已有，包括现有 schema24 或同 owner 空库 | CREATE 前拒绝；不补证，不迁移，不删除。 |
| 创建竞争导致 duplicate database | 不发行；不把竞争者创建的库认作自己的成功。 |
| CREATE 明确失败、超时、断线、结果未知 | 不发行、不自动重试 CREATE、不 DROP；明确未知结果。 |
| 仅 before/after 观察存在变化，无 issuer CREATE 成功 | 拒绝；不能经手工对象字段获得票据。 |
| foreign cluster/system_identifier、不同目录、不同 postmaster start | 创建后或迁移前拒绝，不进入 SQL025。 |
| database name/OID 不同，目标 DROP/recreate | 拒绝旧 receipt，不向新对象授权。 |
| owner/current/session 身份不匹配，SET ROLE | 拒绝，不恢复或修改角色。 |
| 手工构造、复制、序列化/反序列化或其他进程 receipt | 发行身份检查拒绝，未调用 migration SQL。 |
| 程序重启/cluster 重启、只剩 schema24 与磁盘配置 | 拒绝补证；不接受名称/nonce 文件作为权威。 |
| autocommit migration、其他连接/backend/事务 SQL 票据 | 保留 Python 与 SQL 的拒绝，所有写入回滚。 |
| 临时票据零行/多行、字段 NULL/篡改、未来 schema version | 原 SQL025 严格拒绝。 |
| migration 回滚/提交 | temp ticket 消失；仅仍存活的精确 receipt 可重新核验发行新事务票据。 |
| migration 失败或 CREATE 未知 | 无自动 DROP、角色、Grant、owner、ACL、security 或凭据操作。 |
| 任一拒绝/成功的候选单元测试 | 断言权限相关调用为零、错误输出无 DSN/密码；成功只指纯协议 seam 顺序。 |

第一层可在未来新增独立 helper 与 fake seam tests 中检查顺序、对象身份、错误和零额外副作用；fake seam 不能发行生产有效票据或证明 NT/PostgreSQL 行为。第二层需要明确协调的隔离真实 PG 对 SQL 强绑定、事务与失败原子性做集成验证。第三层才是另行授权的实际 installed Windows 同进程 CREATE/loader 验证，不能用 Linux、Mock、Server CI 绿灯或 native SKIP 替代。

## 本轮状态与剩余门

本轮完成源码/Plan/Log只读定位与设计文档，设计没有宽松补证路径；本轮没有实施或运行 adapter 候选。后续离线代码/测试候选可在现有授权内推进，共同协议与 SQL guard 改动需独立工程评审；真实 native 发行、owner CREATE、实际安装、owner/ACL/security 操作与部署仍待明确执行范围。F1 未签收、F2 并行；原 AT/EX、完整 Windows/Win11 与受保护 authority 缺口不因本文改变；R4 关闭、真实模型预算为 0。未来实施必须先具体审查上列入口/issuer/共同协议变更，不解除原 owner/ACL/security 暂停边界。
