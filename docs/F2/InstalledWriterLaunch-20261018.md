# 已有安装的单 Run writer 显式启动

本片核对实际实现后补上原缺口：旧 LinuxHost/RestrictedEngine 只接受新 fixture_UUID 库、临时 trial_root 与新建库签名；普通工厂虽然已有消费接口，却没有承载已有普通库的新进程与新 pin 通路。现新增独立的已有安装 profile，复用原 host/runtime，不再实现 SQL 安装器、政策发行器或业务算法。本片没有执行安装、发行、启动、赋权或激活。

## 已有安装 profile

`InstalledRuntimeLayout` 的严格公开 JSON 使用 `schema_version=parkweave-installed-writer-layout/1`、`runtime_root=/var/lib/parkweave/runtimes/<32位小写hex>`、`installation_receipt_sha256`，以及原源码/解释器/依赖、既有 API/writer UID/GID、boot_id、私有 bootstrap SHA 等字段。内部复用旧路径和源检查；公开 JSON 不接受旧 trial_root/creation_receipt_sha256 别名、未知 schema 或额外字段。旧 RuntimeLayout 与 trial launch_request 保留原新 fixture 门，并明确拒绝把新的安装模型当作旧 trial 模型。

仅支持明确的本机 loopback 或规范绝对 Unix 目录、非系统且非 fixture_ 前缀的单个数据库，PRODUCTION policy、LINUX_UNIX、DIRECT_DML、完整 owner 映射、既有分离非 root 身份及精确公开来源引用。普通配置仍只消费最终 root public binding，不调用 LinuxHost，不生成签名或 sealed FD。解析模型、policy 的枚举或离线 PASS 均不产生授权。

`LinuxHost(spec, layout).start(layout.approval_path)` 消费固定 root 私有审批 key、签名启动审批和受保护安装收据。启动动作是独立的 START_BIND_INSTALLED_SINGLE_RUN，绑定完整 spec/layout 摘要、安装收据摘要、本次新 root/boot 和原 policy UTC 区间。`installed_receipt_payload` 仅生成预期公开数据，不签名、不发布、不证明安装：签名收据须独立绑定物理数据库 host/port/name/OID/system_identifier、安装主体、完整 spec/policy/源码文件摘要、私有 bootstrap SHA 和 UID/GID。原新建库凭证不能代替它，普通收据也不能进入旧 trial 分支。

原 protected reader、身份/源码/解释器/依赖检查、一次 claim、固定 -I -S argv、分离 UID、空 supplementary groups、sealed memfd、真实进程/双 socket 观察、O_EXCL 公开 pin 发布、owned child 清理均复用。父进程只用提取的 `validated_private_input` 做纯输入校验；普通 engine 仅在原 load_host_ticket 核验 root-owned sealed FD、真实父进程与源码/身份后，才能以精确绑定方法和已发行授权对象构造。任意回调、DI store factory、未发行或被覆盖的实例方法不能放行普通 engine。

真实首次连接、首个非 SET SQL、私有 permit 及每次提交仍由原 RuntimeGuard/WriterContext 核当前物理库、session/current_user、非 owner 与有效最小 ACL、存储合同。root 签名数据不替代这些实时检查。REQUEST/APPROVE/ACTIVATE 的当前来源、权限代际、租约、原 key 及事务算法不变；原 SYNTHETIC 本地 Case 来源门不放宽，不据此宣称正式来源或真实业务可用。

## 重新启动与失败边界

每次显式启动需要新的受保护 runtime_root、boot_id、claim、socket 和 pin；原有文件/未知 socket 不采纳、不覆盖、不删除。同一 host 实例已消费即拒绝再次启动。失败保留 claim 和原异常，仅停止本次确切拥有的 child；目录、数据库、凭据及历史保留。部署者负责先确认原拥有进程已停止，再独立批准新启动；这里不发现、接管或停止旧/未知进程。

重启只重新装载原 policy 和私有 key，保持原 policy SHA、原 UTC 截止、来源与权限代际；不生成新 policy/key、不续授、不重签历史。过期后的写启动仍拒绝。新 pin 需要独立显式更新原受保护内外两层绑定并重建 API；旧 client 仍按原 PID/start/inode/device/boot 检查拒绝。没有热切换、自动重试、自动接管或“撤回 pin 即原子追回在途命令”的保证。仅限原物理库的正常停启；逻辑恢复、换集群、备份回滚、轮换及灾难恢复不在本片实现或验收范围。

## 定向离线证据

直接 unittest `tests/test_installed_writer_launch.py`：19 个新增方法与 7 个调用原断言的 legacy 方法；另运行普通工厂原 24 方法，合计 50 个唯一方法。legacy 包装中一个方法含两项原参数反例，不额外累计唯一方法。没有运行 pytest/conftest、PG fixture、浏览器或旧整套 69 项 UI；UI 源码与原断言不改。最终冻结 SHA、实际结果及独测重叠见本片 evidence/validation。

正向路径显式 DI root 保护读取、身份/源码观察、fcntl 常量、FD、Popen 与 socket 观察，原 host 控制流和原封包/类型检查执行，但不产生真实启动资格。测试全局禁止实际连接、进程、socket、memfd 和权限修改。首次开发 24 方法出现 8 个 ERROR 实例（6 个方法，含 subtest）：本环境 Python 缺少 F_*SEAL 常量；原日志保留。补齐测试替身、规范模拟 FD payload 后第二窗 24 PASS；补缺能力拒绝及旧门反例后第三窗 26 PASS，普通工厂 24 PASS。开发窗不与最终冻结窗相加。

产品在受支持能力检查中要求 memfd、SO_PEERCRED 及全部 seal 常量；缺一即在私密读取或 FD IO 前准确拒绝，没有数字常量 fallback。本环境属性只读观察实际为 unsupported，未尝试真实启动，也未修系统 Python 或权限。

首冻结 5683796d 的主/独 50 方法均通过；独测指出过期子段会先遇本环境能力门，该窗如实保留此覆盖限制。最终只修正该子段的能力/root DI，并断言命中原 UTC 拒绝信息、仍不允许私密读取；产品代码不变，最终在新固定提交上重新结算同批 50 方法，不将旧窗口累计为新增覆盖。

## 后续实际执行条件

本片只消费已有合法安装；缺少安装或合法政策时仍停止。首次普通库的存储/ACL 安装与真实政策/密钥发行尚无可自动执行的普通工具，不能说实现层已齐、只差随便填配置，更不能用旧 trial worker 补造授权。实际执行前必须提供并独立批准以下**同一组已存在对象**：

- 受支持 Linux/Python 的真实 sealed FD 环境；已受保护的冻结源码、常规解释器及完整依赖路径/摘要；现有不同 API/writer UID、API GID 和 IPC GID/成员关系。
- 同一实际普通库的 host/port/name/OID/system_identifier；原低权限 app、独立非 owner writer、安装 owner 映射、原最小有效 ACL 和已安装 native 存储。工具不创建角色或补 GRANT，任何差异应拒绝并单独处理。
- 原合法 policy 的单 Run/Case/preparation、现有 owner/独立批准者/受益人、READ 与来源/权限代际、最多一小时的原 UTC 区间、原签名 key 和私有连接；合法 PREPARE/REVIEW_ASSIGNED、精确 preparation_catalog 和普通来源条件仍须在原流程满足。
- 本次全新 root 下已准备的保护目录与私有 bootstrap、root 审批 key、上述安装收据及签名启动审批；批准只涵盖本次 sealed FD 交付、该一个 writer child、两条新 socket 和一个新 public binding，随后显式两层绑定/API 重建与有界核对。没有新身份、业务 Grant、目录发布、政策续期或实际激活的隐含许可。

恢复和停止只针对可证明属于该次启动的 child，保留失败日志、数据库、历史、key/policy 与未知锁/文件；新一次尝试须新 root 和独立批准，不删旧 claim 解锁。本片当前没有这些真实对象值，因此不提交可立即执行的真实批准包。

未执行真实安装、迁移、policy/key/身份/Grant/目录/批准发行、服务、IPC、模型或浏览器动作，未修改系统/SQL/网络权限。Windows 正式 AT、无夹具 AT35、实际普通安装/恢复及真实业务场景均 NOT_RUN，完整 F2/项目尚未完成。
