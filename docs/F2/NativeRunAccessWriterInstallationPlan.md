# 原生产安装与技术权限的待决方案

本页是可复核的后续设计输入，不是安装授权或已执行 SQL。当前代码仅提供默认关闭的合同和 OWNED_SYNTHETIC_REFERENCE 独立 writer；reference CLI 明确拒绝 PRODUCTION。生产服务启动器、密钥供给、受限身份及安装步骤未实现/未执行，不能将本片合成 PASS 当生产启用批准。

## 启用前必须给出的具体对象

须由后续委托指定真实数据库 host/port/name/OID/system_identifier、现有 app 与独立 writer 的角色名、安装操作者、受保护部署位置、单 Run/Case/preparation/park/org/owner、具名同租户审批与受益人、精确资料和权限版本、UTC 起止（不超过一小时）、收据密钥来源及 host pin 来源。当前没有这些真实生产对象，不能采用 fixture 名称、环境布尔值或数据库 APPROVED 来补齐。

app 必须仍为原非 owner、非 superuser、无 CREATEDB/CREATEROLE 的低权限连接；不得获得 writer DSN、签发密钥、pg_control_system 或 assignment 写权。writer 必须另用受限非 owner 身份；不得复用 reference 中的 fixture owner，也不接受原 DecisionTestPermit / ActivationTestPermit 为生产证明。

## 当前 Python 事务路径实际需要的数据库操作

此矩阵来自当前查询/写入路径，描述权限需求而非已审核最小 GRANT 方案。生产还须在直接 DML 与受保护窄函数之间另作选择并审查；不在本片执行任何 GRANT、角色建立或函数发布。

| 对象/动作 | 用途 | 当前状态 |
|---|---|---|
| principals、capability_grants、preparation_grants SELECT | 真实会话、当前 READ/PREPARE/EXECUTE、角色/租户/权限代际 | reference 既有 owner 可读；生产未给出身份 |
| runs、operations、cases、preparations、preparation_evidence SELECT | 精确普通 SYNTHETIC 成功建单及当前资料证明 | 生产 scope/RLS/窄接口待决 |
| case_local_lifecycles SELECT | 新激活前本地关闭守卫 | 同上 |
| runs UPDATE(native_run_access_protocol,native_run_access_activation) | 追加事件/当前 head；列 UPDATE 同时满足 Run 行锁要求 | 未授予生产 writer |
| preparations 行 FOR UPDATE | parent → Run 顺序，串行材料/ACCEPT/取消/关联 | PostgreSQL 行锁仍需相应 UPDATE 技术权限；仅 SELECT 不足。直接授权某列或窄锁函数须单独审查 |
| run_assignments SELECT、INSERT、UPDATE(active,native_access) | 原子 assignment 与 marker、禁止覆盖 legacy/isolated | 原 app 无写权；生产 writer 未授权 |
| authorization_audit INSERT | 原权限检查的拒绝审计 | 不触 principals/Grant/材料/Case/资源/通知业务写 |
| 读取数据库 OID/name/current_user/host/port/start | 两端实际连接身份相符 | app 沿原可读范围 |
| 私有 writer 读取 pg_control_system().system_identifier | 固定 physical cluster，拒绝换库/集群 | 生产须明确只读函数授权方案，不给 app |
| 原 advisory lock 函数 | principal、原键与 native Run 串行化 | 不新建 registry，不改变锁序 |

直接 DML 会授予服务进程可写这些列的技术权限；业务合同和 Python 验证不能消除此技术能力。若采用 SECURITY DEFINER 窄函数，必须另实现且审核函数 owner、固定 search_path、schema/object ACL、类型参数、真实会话/来源/CAS/原键重核、事件签发与提交重核；当前没有此函数或其验收证据。不能把计划中的窄函数声称为已完成的生产安全边界。

## 存储安装与发行

native storage 两个 SQL 文件目前仅由原允许 UUID 合成 fixture controller 显式安装，不在 Store.migrate() 自动执行。真实安装需先只读核现有版本、列/trigger/function 是否缺失或冲突、对象 owner 与 ACL，并产出逐项变更及回退方案；不复用一次性 SQL 对未知生产库执行，不修改迁移 32 或旧 roles.sql。

收据需维持 policy SHA 和 issuer/key_id。本片 HMAC 由私有 writer 验证，API 不持 key；生产尚未决定安全密钥存储/发行、旧 key 只读验证、轮换及灾难恢复。更换 key/policy 不得自动重新签历史或延长租约；当前换 key 的 reference 明确拒绝旧证明。旧 policy 一次 REQUEST 用尽后不能从本片自动新建或续授。

## OS 与重启边界

本片 Linux Unix socket reference 用 host 观察的 Popen PID/UID/实例、路径 inode/device、boot ID 和 policy SHA 验证。生产须另提供受保护启动者、socket 父链与 owner/mode、独立 UID/密钥隔离和不可被 API 改写的 pin 配置。相同 UID/root 的 fixture 并非生产 OS 隔离证据。Windows 原生 IPC 没有实现/验收，不降级到 TCP、自报 HELLO 或直接 owner 连接。

新 API/writer 只能由受信 host 以原外部 policy/key 明确 rebind；数据库仅同 physical cluster 正常 stop/start、实际身份及权限/资料相符时保留原截止时间。换集群/逻辑恢复/备份恢复/密钥轮换需后续独立方案，不依据 xmin 宣称永久恢复安全。

后续若要求生产启用，应先提交真实对象、受限身份及上述安装/权限/密钥方案的具体差异，独审后再获得该动作授权。本片仍保持生产默认关闭；未触生产部署、迁移、SQL 权限、业务 Grant 或真实 assignment。

