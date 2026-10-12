# 原生产安装与技术权限的待决方案

本页是可复核的后续设计输入，不是安装授权或已执行 SQL。当前代码仅提供默认关闭的合同和 OWNED_SYNTHETIC_REFERENCE 独立 writer；reference CLI 明确拒绝 PRODUCTION。生产服务启动器、密钥供给、受限身份及安装步骤未实现/未执行，不能将本片合成 PASS 当生产启用批准。

## 启用前必须给出的具体对象

须由后续委托指定真实数据库 host/port/name/OID/system_identifier、现有 app 与独立 writer 的角色名、安装操作者、受保护部署位置、单 Run/Case/preparation/park/org/owner、具名同租户审批与受益人、精确资料和权限版本、UTC 起止（不超过一小时）、收据密钥来源及 host pin 来源。当前没有这些真实生产对象，不能采用 fixture 名称、环境布尔值或数据库 APPROVED 来补齐。

app 必须仍为原非 owner、非 superuser、无 CREATEDB/CREATEROLE 的低权限连接；不得获得 writer DSN、签发密钥、pg_control_system 或 assignment 写权。writer 必须另用受限非 owner 身份；不得复用 reference 中的 fixture owner，也不接受原 DecisionTestPermit / ActivationTestPermit 为生产证明。

## 当前 Python 事务路径实际需要的数据库操作

此矩阵来自当前查询/写入路径，描述权限需求而非已审核最小 GRANT 方案。生产还须在直接 DML 与受保护窄函数之间另作选择并审查；不在本片执行任何 GRANT、角色建立或函数发布。

| 对象/动作 | 用途 | 当前状态 |
|---|---|---|
| principals、capability_grants、preparation_grants、action_grants SELECT | 真实会话、当前 READ/PREPARE/EXECUTE、case.create、角色/租户/权限代际 | reference 既有 owner 可读；生产未给出身份 |
| runs、operations、cases、preparations、preparation_evidence SELECT | 精确普通 SYNTHETIC 成功建单及当前资料证明 | 生产 scope/RLS/窄接口待决 |
| case_local_lifecycles SELECT | 新激活前本地关闭守卫 | 同上 |
| runs UPDATE(native_run_access_protocol,native_run_access_activation) | 追加事件/当前 head；列 UPDATE 同时满足 Run 行锁要求 | 未授予生产 writer |
| preparations 行 FOR UPDATE | parent → Run 顺序，串行材料/ACCEPT/取消/关联 | PostgreSQL 行锁仍需相应 UPDATE 技术权限；仅 SELECT 不足。直接授权某列或窄锁函数须单独审查 |
| run_assignments SELECT、INSERT、UPDATE(active,native_access) | 原子 assignment 与 marker、禁止覆盖 legacy/isolated | 原 app 无写权；生产 writer 未授权 |
| 原 API 的 authorization_audit INSERT | API 回滚后 Store.audit_denial 拒绝审计 | 当前 private writer 路径不执行此 INSERT；不得据此向 writer 自动授予多余写权 |
| 读取数据库 OID/name/current_user/host/port/start | 两端实际连接身份相符 | app 沿原可读范围 |
| 私有 writer 读取 pg_control_system().system_identifier | 固定 physical cluster，拒绝换库/集群 | 生产须明确只读函数授权方案，不给 app |
| 原 advisory lock 函数 | principal、原键与 native Run 串行化 | 不新建 registry，不改变锁序 |

直接 DML 会授予服务进程可写这些列的技术权限；业务合同和 Python 验证不能消除此技术能力。若采用 SECURITY DEFINER 窄函数，必须另实现且审核函数 owner、固定 search_path、schema/object ACL、类型参数、真实会话/来源/CAS/原键重核、事件签发与提交重核；当前没有此函数或其验收证据。不能把计划中的窄函数声称为已完成的生产安全边界。

## 存储安装与发行

native storage 两个 SQL 文件目前仅由原允许 UUID 合成 fixture controller 显式安装，不在 Store.migrate() 自动执行。真实安装需先只读核现有版本、列/trigger/function 是否缺失或冲突、对象 owner 与 ACL，并产出逐项变更及回退方案；不复用一次性 SQL 对未知生产库执行，不修改迁移 32 或旧 roles.sql。

## 已实现的安装前只读预检

[预检入口](../../src/parkweave/native_run_access_preflight.py)只比较公开安装清单与已取得的目录快照。`python -m parkweave.native_run_access_preflight --spec public-spec.json --snapshot catalog-snapshot.json` 不接收 DSN、密钥或连接选项，不发现环境凭据，不连接生产或启动服务。无输入也可运行，以明确列出缺配置与未连接项。JSON `status` 和进程退出码分别为 PASS/0、MISSING_CONFIG/2、NOT_CONNECTED/3、REFUSED/4、APPROVAL_REQUIRED/5；逐检查保留各自状态。缺失的附加对象和必要权限列入逐项待审批差异，同名错误对象、错误来源/版本与额外权限明确拒绝；不输出可执行安装 SQL，不覆盖冲突对象，不隐式回退历史列。

公开 `InstallationSpec` 复用完整 `WriterPolicy`（真实对象和精确资料/权限版本），另要求安装操作者、基线对象 owner 映射、DIRECT_DML 或 NARROW_FUNCTIONS 选择、明确的 parent 行锁技术 UPDATE 列、受保护位置、不同 API/writer UID、传输及 policy/key/host-pin 的来源引用。只填来源引用，不填凭据；引用和 UID 仅是声明，不能证明实际保护或 OS 隔离。Windows 原生传输及窄函数策略继续待实现/审批。生产实际 API/writer session_user/current_user、当前业务来源与授权、密钥/pin 保护及启用授权仍需独立可信核验。

原 issued UUID fixture 的 `collect_owned_catalog(connection, proof, spec)` 是独立只读采集器：仅接受原已签发创建证据及已连接的 idle owner 会话；不创建连接、migration ticket、数据库、角色或权限。独立 REPEATABLE READ READ ONLY 事务、固定 pg_catalog search_path 和超时，仅读目录及 schema_version，无业务/ledger读取、FOR UPDATE 或 advisory 锁。它实际检查 3 列、3 个零参数 trigger 函数的签名/原 SQL body SHA/语言/security/config/owner、3 个触发器的 relation/function OID 与完整语义、版本32、owner/ACL指纹和有效 table/column 权限（含继承、PUBLIC、owner）。还检查可 SET ROLE 的危险成员关系、额外 writer 写权、app assignment/身份写权、schema CREATE 与 pg_control_system 权限。采集错误原样向调用方传播，不重连、不补 GRANT。临时库 owner 明确被拒作生产 writer。

所有离线输入及 owned 快照均保持 `installation_authorized=false`、`activation_enabled=false`、`production_connected=false` 和 `installation_status=APPROVAL_REQUIRED`。PASS 仅表示本次快照比较无已检测差异；不能转为真实生产安装、Windows 或正式 AT35 验收。真正安装仍缺可信真实目录/会话/来源证明、受限身份与精确对象/ACL方案（含回退）、受保护 launcher/policy/key/pin，以及针对实际安装与启用的独立动作授权。

成员关系检查保守拒绝已知管理员、owner、writer 和所有 `pg_` 系统角色；任意自定义 NOINHERIT/SET ROLE 的额外权限链仍需独立核验，不宣称完整生产权限证明。预检源码 `d95cee3dc18052dc619e94f5826d79f7e5c76d3c` 实际根125 PASS、独审130 PASS（重叠125，另5独立探针），均0 FAIL/ERROR/SKIP；原834窗口的3 FAIL及同ID修复复验保留。详见[实际窗口与归档核验](evidence/native-writer-install-preflight-20261012/validation.json)及[独立限定审查](evidence/native-writer-install-preflight-20261012/independent/REVIEW.md)，不合并窗口或声称实际安装。

收据需维持 policy SHA 和 issuer/key_id。本片 HMAC 由私有 writer 验证，API 不持 key；生产尚未决定安全密钥存储/发行、旧 key 只读验证、轮换及灾难恢复。更换 key/policy 不得自动重新签历史或延长租约；当前换 key 的 reference 明确拒绝旧证明。旧 policy 一次 REQUEST 用尽后不能从本片自动新建或续授。

## OS 与重启边界

本片 Linux Unix socket reference 用 host 观察的 Popen PID/UID/实例、路径 inode/device、boot ID 和 policy SHA 验证。生产须另提供受保护启动者、socket 父链与 owner/mode、独立 UID/密钥隔离和不可被 API 改写的 pin 配置。相同 UID/root 的 fixture 并非生产 OS 隔离证据。Windows 原生 IPC 没有实现/验收，不降级到 TCP、自报 HELLO 或直接 owner 连接。

新 API/writer 只能由受信 host 以原外部 policy/key 明确 rebind；数据库仅同 physical cluster 正常 stop/start、实际身份及权限/资料相符时保留原截止时间。换集群/逻辑恢复/备份恢复/密钥轮换需后续独立方案，不依据 xmin 宣称永久恢复安全。

后续若要求生产启用，应先提交真实对象、受限身份及上述安装/权限/密钥方案的具体差异，独审后再获得该动作授权。本片仍保持生产默认关闭；未触生产部署、迁移、SQL 权限、业务 Grant 或真实 assignment。

## Linux 受限 DML 合成试运行准备

本轮选择 Linux 临时隔离目标与直接受限 DML；不使用用户 Windows。[公共计划入口](../../src/parkweave/native_run_access_trial_plan.py)可运行 `python -m parkweave.native_run_access_trial_plan --spec public-spec.json --snapshot catalog-snapshot.json --host-plan public-host.json`，复用上面的目录比较及精确权限矩阵，不重复 reference 整链。host-plan 仅声明 linux、`/tmp/parkweave-trial-<32位小写hex>`、已存在的不同身份及待固定源码完整 SHA。角色合同只供离线比较；没有生产/临时数据库连接或已签发创建证明。有效输入也只返回 APPROVAL_REQUIRED/5，列出精确单 Run/Case/资料版本/UTC、主体与完整来源摘要、目标路径、UID声明及权限需求；自由文本身份和资料状态不回显，摘要仍绑定其原值；无自动 GRANT，LOCK_UPDATE不被当成SQL授权动词。不能通过布尔值、计划文件、环境或方向选择授权执行。

5db离线计划交付阶段验证的是计划生成、输入拒绝、权限差异和无副作用控制。现 reference 保持原 owner/OWNED_SYNTHETIC_REFERENCE 边界，不能将其 argv 改名充当受限启动器；该阶段受限 private runtime/host adapter 尚未实现，历史计划明确 `writer_argv=null`、`writer_runtime=NOT_IMPLEMENTED`、`actual_run=NOT_RUN` 和全部授权为false。源码/解释器、独立UID、秘密交付、目录保护、当前权限与任意SET ROLE链、实际host pin均未验证；真实启动不在本轮执行。

当次最小批准须绑定审核后的计划digest与实际对象：只在其全新临时目录/原创建证明的UUID数据库内准备存储和缺失的精确writer权限，保留原app权限；明确既有API/writer UID和私有policy/key/凭据交付及必要目录/源码保护变更；由可信host使用另经审查的受限adapter启动/观察/绑定两通道，执行该唯一普通成功SYNTHETIC Run/Case的有限用例；最后停止原子进程并凭原证明删除本次新增临时资源，保留失败证据。新UID、新凭据或mode/owner变更需明确另列；不默认包含，不安装系统服务、不部署、不触生产、不调用付费模型、不扩业务Grant/registry、不续授。现阶段仅公开声明，不存在可立即批准并运行的已验证真实身份/目录/密钥；平台若无法提供隔离应停止，不降级为同UID证明。


本次冻结源码 `8ee3877fd3ebf4acd71ed8d49c4915cbf52f38ae` 根测试实际93 PASS（新计划34、CI诊断59），独审原探针复验99 PASS/2 FAIL，另按新摘要与CLI合同补测2 PASS；均0 ERROR/SKIP、源码首尾无漂移。两个FAIL是保留的旧状态/输出键断言，不能称原探针整窗PASS；初始1fed的路径越界与回显3 FAIL、原字节及修复复验见[本次实际窗口](evidence/native-writer-linux-trial-plan-20261012/validation.json)。既有5118证据与旧preflight/writer/SQL/roles/migrations保持不变；本次不重跑reference、PG或浏览器，不将离线成绩转签安装/实际受限进程验收。

## 默认关闭的受限 host/runtime 实现

新增 [Linux host](../../src/parkweave/native_run_access_restricted_host.py) 与 [restricted runtime](../../src/parkweave/native_run_access_restricted_runtime.py)，独立于 owner reference。`LinuxHost.start()` 默认在秘密读取、连接和Popen之前拒绝；真实启动须先验证固定位置的root私有32字节host审批key、当次完整spec/layout/UTC/动作的HMAC审批，以及原新建目标的受保护签名创建凭证。代码不发行审批、创建身份/凭据/角色或安装存储。合成签名比较不产生live capability；未由该host真实核验发行的token、未知host子类、未从root-owned sealed memfd发行的runtime authorization、DI store factory均不能进入真实监听/启动。

host核完整source-only bundle及每个目录/文件，拒未登记资源、现有__pycache__/pyc与扩展模块，验证既有pwd/grp API/writer及API/IPC组记录和成员，再核真实常规解释器与完整依赖目录的root owner/不可被API或writer改写/无symlink父链，核writer私有bootstrap原内容SHA。当次start-claim仅为全新目录内的host防重复动作标记，绝不写业务Grant/registry。实际Popen固定argv、shell=false、-I -S禁自动site/.pth、仅批准import_paths的精确Python入口、不同既有非rootwriter UID、明确IPC GID、空supplementary groups、close_fds与唯一sealed fd，DSN/key不进入argv/env/日志。两Unix socket由明确0117 umask创建为0660；host实际观察PID/start/UID/GID与双inode/device/owner/mode再以新文件O_EXCL发布root-owned0640 public binding。仅该新增binding FD会在当次批准内fchown/fchmod；不改旧文件、不覆盖旧pin、不重启或自动删除失败资源，stop仅接受本host真实拥有的child。

runtime先核实际isolated/no_site flags、精确sys.path与所有已加载module file/origin/namespace来源，再在两通道frame读取前校验SO_PEERCRED的API UID/GID，复用原canonical WriterContext/NativeRunAccess command、activation和原键路径。默认真实Engine/Store入口均须由sealed FD实际发行的精确host check；Connection与游标execute/executemany/stream/copy的首个非SET SQL、permit以及提交前重核当前session/current_user、非owner角色、物理数据库、完整安装目录及有效ACL；拒自定义或系统角色成员链、所有schema的CREATE/owner、TEMP、跨schema额外DML与ACL能力、grant option、可执行SECURITY DEFINER/untrusted例程、临时namespace与未知检查结果。原API不得有assignment/身份写或control-system权。连接固定pg_catalog/public/pg_temp并拒临时namespace；目录采集仅提取旧collector的原SQL，原issued-owner证明门保持。新增技术需求仅增加writer SELECT(schema_version)，必须另批实际ACL。

fresh source/generation/beneficiary条件仍由原REQUEST/APPROVE/ACTIVATE事务检查；全局guard不把它们施加给REVOKE。VERIFY保持纯MAC不连接/取业务锁，历史核对与新权限分开。显式`bind_api`只接受root保护的public binding及预期SHA；configured_app仍无新环境变量/隐式加载或私有Context。public计划现标记IMPLEMENTED_DEFAULT_CLOSED_UNVERIFIED，仍全部authority=false、writer_argv=null、actual_run=NOT_RUN。

真正待执行事项仍需独立审批和真实验收：绑定实际完整源码/解释器/依赖环境、原创建证明与UUID库对象/ACL；确认既有API/writer UID、API有效GID、既有IPC GID及API组成员；准备root host审批key/签名审批/创建凭证和writer私有DSN/key bootstrap；仅新目标内的目录保护、必要ACL（含新增schema_version SELECT、去除额外角色/TEMP/CREATE/grant option）及新claim/socket/public binding权限；批准当次sealed-fd交付、单次启动/观察/显式API绑定、真实owned PG锁/事务与丢响应验收；最后仅停止拥有的child并凭原证明处理本次新资源。新UID、新凭据、任何安全mode/owner/ACL改变及实际连接/启动本轮均未执行，不因代码实现或DI PASS自动获得授权。

## 受限 adapter 代码的实际验证与交付

冻结源码 `72f6b33ff3166f34dc12ae993cfcf50beefc811b` 已完成默认关闭的host/runtime实现及独审修复。主测实际245 PASS/0 FAIL/ERROR/SKIP；独审实际262 PASS/1旧SQL Oracle FAIL/0 ERROR/SKIP、exit1，结论LIMITED_PASS。两窗427源码与合同文件完全一致、首尾零漂移。精确重叠244项：主测另有原离线CLI1项，独审另有19项（18 PASS/1 Oracle FAIL），不能相加。真实窗口与逐项结果见[验证记录](evidence/native-writer-restricted-adapter-20261012/validation.json)和[独审报告](evidence/native-writer-restricted-adapter-20261012/independent/FINAL_REVIEW.md)。

独审原4 FAIL、追加default Engine 1 FAIL、import/ACL覆盖5 FAIL、default Store 1 FAIL均原样保留。11个原失败ID中10个最终同ID通过；剩余system_schema_create粗Oracle在整份SQL寻找系统schema排除项，误中了危险routine检查保留的系统内建例外。正确的ownership/table/routine逐子句控制通过；四项import正反控制均先接受合法观察，再拒绝坏path/file/namespace/origin。三项SQL Reader反例仅检验谓词覆盖，不冒充真实PG权限复现。另保留原SQL提取字面AST比对FAIL的精确报错转录及只规范多行SQL缩进后的实际PASS；它们不是pytest计数。

源码检查覆盖全部节点，拒未批准资源、缓存/扩展与可写/非root/symlink来源；连接首SQL覆盖Connection与游标四种入口。真实Engine与默认Store入口须接受实际sealed FD发行的精确bound check，Store另拒临时替代guard及实例方法覆盖；DI不能监听或自授物理权限。READ/REVOKE历史例外、原canonical业务路径和原请求键保持。

本轮未连接PG、启动writer/host服务、改UID/GID/凭据/ACL/安全owner/mode或部署。原7项实际owned PG用例及全部新受限物理验收均NOT_RUN；独审另因全局Popen禁止而未跑原CLI，主测已跑该离线CLI。浏览器0次，历史Chromium data: ERR_BLOCKED_BY_ADMINISTRATOR拒绝保留且未重试。先前5173份证据字节不变；本次仅按明确清单导出合成测试原件，普通开发分支为`dev/f2-native-writer-install-preflight-20261012`。真实隔离trial仍须上述独立动作授权与已有可信OS/PG/秘密环境，代码和纯DI结果不能替代该验收。

## 已批准的单次新 VM 验收结果

用户随后明确批准一次免费的 GitHub 标准 `ubuntu-24.04` 新 VM 隔离验收，冻结源码 `86bd07ef65135d749d6f0f9e9ae43039c4bd8fc8` 已在独立分支正常推送并只运行一次。实际结果 **FAIL：3 PASS / 1 FAIL / 13 NOT_RUN**，`PG_SETUP` / `CHECK_FAILED`，自有进程清理成功；失败标签 `ACTUAL_ROLE_ACL` 不等于已确认 ACL 缺陷，内部根因未知。其余受限物理合同未获得验收，未修代码或重跑。原始公开摘要、纯测试失败与独审签收见[单次实际验收记录](RestrictedLinuxTrialOnceAcceptance-20261012.md)。本段更新实际进展，保留前述各冻结阶段的历史资格范围；再次修订运行或试跑需用户下一明确决定。

父级随后明确授权准备最小无密 SETUP 诊断候选，禁止第二次 CI。冻结源码 `3617bd0cb67b2d667cfcbb4ba53d37c101d8df07` 主测 200 PASS、独审 208 PASS（精确重叠 200，不相加），均 0 FAIL/ERROR/SKIP、源码零漂移，结论仅代码/纯 DI LIMITED_PASS。补丁只公开固定 substage/check_id 和白名单整数 HTTP 状态，原 SQL、adapter、workflow 和双层首次运行门不变；旧失败根因仍 UNKNOWN。普通新分支不匹配任一 workflow，未真实再试。具体代码与下一批准范围见[诊断候选记录](NativeRunAccessSetupDiagnosticCandidate-20261012.md)。
