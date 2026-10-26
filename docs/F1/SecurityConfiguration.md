# F1安全配置与已知边界

本轮默认LOCAL + SYNTHETIC + MODEL_MOCK，localhost单产品数据库/身份/端口/日志。普通应用角色无DDL/身份或Grant UPDATE；迁移owner只用于明确setup。运行CLI的LIVE激活关闭；HTTP代码须显式LIVE持久预算与owner授权证据，不通过env布尔值启用；模型密钥仍不持久保存。数据库持续凭据的产品设计已改为：仅在本机私有目录、由当前Windows用户保护后持久保存。当前只允许相应源码与隔离合成测试，未实际创建、保存或解密真实凭据；原权限、原生运行和安装门不因此解除。

## 私有实例封装候选：未接存储或原生保护

`scripts/windows_portable/credential_envelope.py`只编码/校验敏感**明文字节**，不加密、不落盘，也不取得OS身份。封闭用途为DATABASE、SESSION、CONFIG；规范JSON拒重复键、未知字段、非精确类型、超限、损坏摘要和绑定不匹配。绑定包含ParkWeave、格式版本、实例UUID、当前用户SID及稳定root/lock/journal身份；不含generation、sequence或postmaster_start。调用者传入这些数据不构成真实租约、Windows身份或数据库创建证明。

DATABASE只含现有postgres与parkweave_app秘密；SESSION沿现有fixture-a/b/c三身份映射与互异要求，不套用导览六身份、不增Grant或补token。CONFIG schema2只引用DATABASE、SESSION两对象的最终文件身份和**密文**摘要，不引用自身ciphertext hash；还承载稳定数据库身份、schema32和载荷指纹。这些只是严格的候选格式，真实数据须由后续有权持句柄适配器核验，不能由同一份JSON自证。

`windows_user_protection.py`只定义DATA_BLOB布局和显式FakeAPI隔离接口，无DLL加载、真实DPAPI调用、默认原生实例或路径接口。Fake输出不是加密或原生验收证据。参数固定为用户级用途、禁止机器级flags和交互提示；原生入口仍拒绝。未来原生实现遵循[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)/[CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata)：保留用户配置漫游例外，不承诺防同用户恶意进程或管理员；不能只凭API成功或特定错误码判完整性。原生明文缓冲清理与LocalFree尚未实现/验收，Python/DSN副本也不承诺完全擦除。当前Fake只验证有界复制、已识别输出的zero/free顺序、双故障私有保留及公开错误脱敏；未知指针不解引用、不猜测释放，失败进入本适配器内sticky UNKNOWN，不代表安装状态已持久化。

生产FixedDirectoryLease路径仍没有三个secrets对象的原生能力。新增`fixed_secret_store.py`只接受显式FakeSecretAPI、原FixedDirectoryLease对象与Fake保护器，使用原租约排他entry门覆盖整个校验、独占创建、单次写入、flush、精确密文读回、解封校验与关闭；没有Path/open、旧JSON映射或controller接线。三种Purpose仅映射已有secrets下database.dpapi、synthetic-sessions.dpapi、instance-config.dpapi。Fake观测核稳定root/lock/journal、对象/父身份、当前owner、raw DACL/control、private-ACL检查结果、链接/reparse及内容版本；private-ACL结果仍是假能力事实，不是Windows ACE解析证明。

DATABASE与SESSION先核实，再从两者最终身份及密文摘要构造CONFIG并独占创建；不覆盖既有对象或重试不明结果。新建phase限定CREDENTIALS/SESSIONS/CONFIG；原对象读取仅VERIFY_FILES或READY_STOPPED对应的精确initialized状态，重开不create/write/flush，不迁移、换钥、补session或增Grant。CONFIG不是跨文件原子事务：只有全部写入、同步、读回及关闭成功，调用者后续才可提交READY。短写、同步/关闭未知、身份或内容变化均失败；持租约时尝试原journal UNKNOWN，随后poison。原验证失败或UNKNOWN落盘失败时保留原错误、原件和OWNED状态，不能假称UNKNOWN已耐久，也不继续重开。未知能力不猜关闭，已尝试关闭不重试，原始失败/清理错误私有保留；普通公开错误不含秘密。所有文件系统和保护操作目前只有内存替身，未写凭据文件、未调用安全API；原生存储工厂继续拒绝。Windows互斥/ACL/目录名称与文件持久性都未验，Linux线程只能核原Python操作门。

旧lifecycle schema1与原SESSION/CONFIG路径不改，不自动迁移、重签、覆盖或重新供应。现有initdb --pwfile的明文输入缺口仍未解决，不允许先落明文再删除作为替代；双击入口、OWNER暂停、固定文件和载荷加载门均不变。

## 文件私有根

Linux从根及files的已打开descriptor核对：目录属主须当前有效UID，group/other不得有权限；普通文件亦须同属主且group/other无权限、单硬链接、hash/大小/UTF8核对。既有目录0777/0755或不同属主拒绝，且不chmod/chown/修复。新建files0700、fixture文件0600；不访问配置根外文件，不导入宿主/企业真实材料。

不安全目录由安装者在明确授权后选择调整或改用新私有根，本实现拒绝不代表已经修复该目录。POSIX检查不适用于Windows ACL；当前Windows backend保持关闭。Doctor候选只读检查Windows根/已有files/会话/日志/配置ACL与属主、根继承保护，允许当前用户及OS系统管理员既有安全语义；既有ACL不改。新根才创建私有ACL。本轮Native ACL/重解析点/ADS/目录替换/安装和用户权限门NOT_RUN。

## 子进程与环境

PGDATA专用源码候选`pgdata_candidate.py`仅限同一V2租约、generation=1且CLUSTER未初始化状态下的全新`data/postgresql`。已有私有`data`父目录保持原owner/raw DACL/control；以held父句柄相对NtCreateFile的FILE_CREATE独占新建PGDATA根，显式当前用户owner、PROTECTED DACL及唯一当前用户FILE_ALL_ACCESS的OI/CI ACE。不增加SYSTEM/Administrators等allow，其他目录和原`windows_files.private_acl`完全不改。后代仅接纳该具体SID/具体权限的精确继承投影：目录flags=0x13、文件flags=0x10；不接受generic rights、CREATOR_OWNER、额外/未知ACE、空DACL或后代私自PROTECTED。原始ACL字节也核对，不能仅凭解析后的INHERITED标志自证来源。这是批准的新专用规则，后代对父ACL变化的隔离弱于逐对象PROTECTED，不宣传完全等价。

根能力仅登记于本次原租约，绑定实例UUID、root/lock/journal身份与generation、data/PGDATA物理身份、冻结描述符及规则版本`parkweave-pgdata-current-user-inheritance/1`；不按路径认领，不接旧目录/迁移或持久JSON恢复。initdb冻结命令及每次创建前freshcheck须消费同一精确目录能力。源中提供有界held-parent枚举/相对打开/owner/raw ACL/文件身份/单硬链接/reparse/同卷核验及两轮所选元数据一致性检查，文件大小不套用资源TXT预算；不读取业务内容、不宣称全DB不变或原子树快照。外部tablespace/WAL重解析逃逸拒绝。漂移或未知关闭在内存标记UNKNOWN并poison租约；保留原件和已尝试关闭的未知句柄记录，不删目录、不修ACL、不重试未知关闭；不宣称journal UNKNOWN已耐久。

该候选未接生产工厂/打包入口，`launch_ready=False`，NO_RESUME/NO_SECRET保留。原生NtCreateFile/目录枚举/继承结果、TokenOwner当前用户设置与实际child读回均未执行或验收；仅检查owner不能保证未来创建者默认owner。`prepare_owner`源码只对自有derived token显式设置fresh TokenUser为TokenOwner，读回并核原其他令牌观测不变；pipe fresh与真实child token查询代码均要求相同owner。失败不重试setter，仍关闭自有句柄并保留UNKNOWN。该方法没有默认工厂调用，不代表实际权限调整已获准。

PG命令路径源码通过同一held PGDATA根的VOLUME_NAME_DOS观测，仅接纳精确扩展盘符前缀，剥前缀后转换为`C:/...`式普通路径。逐组件拒绝ADS、设备名、短名别名、尾点/空格及相对段；根长度最多240个UTF-16单元。代码独立打开并保留drive与每级目录句柄，核同卷、无reparse、描述符和最终根物理身份，使用前再核DOS映射与原VolumeGUID根绑定；字符串不单独授能力。中文窄API/PG17规范化和动态后缀长度仍未获Windows兼容验收，根长度通过不能外推整树可用。没有换盘、重解析或任意路径回退。

CONFIG新增显式`PGDATA_SCHEMA4`：保留schema3端点，增加封闭profile版本、实例UUID、当前SID、data父及PGDATA根物理身份、冻结root control与精确私有ACL摘要；根须与database.data_identity相同，同卷且不与root/lock/journal/secret引用/父对象冲突。schema2默认与schema3字节合同不改，也不自动探测升级。NEW发布仅从当前精确PGDATA能力在原lease门内读回profile，DATABASE/SESSION核实后CONFIG最后写，写后再次检查profile；不把CONFIG阶段当PG已停止，不据此调用scan_stopped。

`native_secret_store_candidate.py`现提供未接入口的真实三文件来源源码：原`IsolatedFixedSecretStore`仍只接受FakeSecretAPI和隔离保护器；新NativeStore只复用其已审读写/关闭算法，构造、Operation、原句柄capability及恢复票据域分离。NativeFiles不继承Fake API，不接受外部ObjectInfo/已验证字典；仅持同一V2租约的NativeFixedLeaseAPI，从真实成功返回的原HANDLE登记能力。既有`secrets`目录必须已私有保护，缺失拒绝；Purpose仅映射三个固定文件。NEW文件以FILE_CREATE和显式当前用户PROTECTED/单U-only ACE原子占名；REOPEN仅FILE_OPEN/read，零create/write/flush，不补文件、不修权限或自动迁移。缺少首次私有布局创建接线时仍拒绝，不能把该存储源码说成完整安装器。

Native Operation核owner/control/raw DACL、同卷父链与对象身份、reparse/单硬链接、内容长度及元数据变化；单次write、flush、原句柄精确密文读回、解封后规范payload一致才成功。短写、未知flush/close拒绝，未知关闭记录原件并只尝试一次；清理不依赖仍有效的租约/当前SID，防止poison后漏关。SID字符串和安全描述符的LocalFree也核NULL成功，读取主因及清理错误同时保留；DPAPI失败out没有成功所有权转移，不据它LocalSize/read/erase/free，进入UNKNOWN。不会把文件flush或三文件依次发布称目录断电耐久或跨文件原子事务。

CurrentUser保护包装仅内部持精确`_NativeDPAPI`，不接受隔离保护器；DPAPI前后都读有效线程身份和fresh进程TokenUser。OpenThreadToken只允许FALSE+ERROR_NO_TOKEN，无impersonation；成功取得的原thread token关闭一次后拒绝，其他错误拒绝，不Revert/Impersonate或启用权限。进程SID须与V2租约封装绑定相同，DPAPI保持flags=UI_FORBIDDEN、NULL描述/保留/提示及原purpose entropy。用户配置漫游、同用户/管理员和不可完全擦除的Python明文副本边界不变。

严格重开的来源接线现有候选源码：实际三文件读取/DPAPI解封/规范绑定和CONFIG引用全部核实，capability全部关闭且最终核lease后，原Operation只消费一次read事实；期望runtime指纹不匹配拒绝。独立native票据先只准PGDATA恢复：核schema4、UUID/当前SID/父与根物理身份/冻结ACL摘要、held DOS链及两轮协作观察，缺/坏/旧profile拒绝。随后用另一明确阶段消费注册端点，终末核验后才签发opaque恢复结果；替身闭后proof和任意JSON不能进入此域。恢复结果在确认属于本store后先消费，任何后续失败sticky UNKNOWN、poison并关闭自有目录能力，不能恢复状态后重试；他人结果不销毁。原journal STOPPED只是生命周期前置，不独立证明OS零进程；恢复元数据也不证明数据库/socket/角色/SESSION当前权威。NEW与REOPEN分流，恢复根禁止再冻结initdb。

以上均仅源码、离线字节/ABI/拒绝与故障注入审查，真实三文件/DPAPI/Windows恢复未执行。原生存储、保护、目录和启动工厂及控制器/打包入口继续关闭，NO_RESUME/NO_SECRET与`launch_ready=False`不变，不授权实际TokenOwner/DACL变更、凭据传送或PG启动。首次布局的原生验收、真实互斥/持久性/加载验收与后续独立物理库/身份验证仍未闭合；不以模拟成功代签。

首次布局与准备阶段总装新增未接入口源码：`native_layout_candidate.py`仅NEW、generation1、同一V2租约，固定独占创建data/secrets/files/logs/tmp五个目录，显式当前用户单U-only PROTECTED/noinherit权限。逐次创建前后核原root物理身份/rawSD，失败保已有原件并poison，不接纳任何既有叶目录，不删/修权限。exact布局cap冻结五叶原HANDLE/物理ID/rawSD，NEW NativeStore消费secrets叶、PGDATA消费data叶，重复/BUSY创建不得覆盖原绑定。布局只证明五目录本身，不将PGDATA继承规则外推到未来temp/log/files动态子项。REOPEN的三文件reader仍从原heldroot独立只读secrets，避免“先需CONFIG认证layout才能读CONFIG”的循环。

`native_preparation_candidate.py`组合真实准备路径而非伪造完整运行Controller：NEW按原OWNER门→NEW布局/typed端点→CREDENTIALS保护数据库凭据→CLUSTER目录/TokenOwner/私有pipe/冻结restricted backend；标准随机秘密的生产代码仅在未来显式调用时执行，本轮未生成秘密。资源在有副作用的方法前登记，partial constructor先保引用；外register前登记原token，返回后在原private-held门回核，不重入public entry。旧明文pwfile与会Resume的普通cluster路线不调用。原runtime preflight继续拒绝，挂起候选结果仅ready=false/resumed=false/secret_transmitted=false，不能报告业务就绪。REOPEN只消费真实闭后恢复票据形成私有typed DSN/原目录，零进程、零补写、无initdb/schema/seed。退出逐资源及逐cap继续清理，首个close失败不漏后续，已attempted不重试；候选未READY只记UNKNOWN/poison，外层原持有者负责租约释放，不伪造READY_STOPPED。

`initdb_client_candidate.py`提供未来运行中的原initdb客户端只读验真源码。本轮不Resume且group.started=false，因此正常挂起候选不会产clientticket。源码只接exact restricted backend及其原claimed group，在原lease→group→owner→server锁序中，以原process HANDLE、birth、image、TokenOwner、Job绑定和当前存活核验关联GetNamedPipeClientProcessId，前后重核；没有OpenProcess或接受任意Job子进程，不传密码、不WriteFile/Disconnect/Impersonate。GetNamedPipeInfo仍NOT_OBSERVED，不为读回增加访问位或假称创建参数已实测。

异步Connect使用原owned手工复位event与实际OVERLAPPED，提交前挂入server及全局强登记。一次总截止最多5秒且预留0.5秒清理；CancelIoEx仅请求取消，GetOverlappedResult对Connect的字节数未定义，不能作为证据。取消后未确认completion则UNKNOWN，原OV/event/pipe HANDLE保留，不释放或报告cleanup完成；server.close对任何未退役记录拒绝，明确cleanup-only观察也不能自动重新Connect。event关闭FALSE或异常都保留UNKNOWN且只尝试一次。此为有截止的合作式等待与未知隔离，不承诺所有同步元数据/关闭调用的硬实时上限。

下一实际验证仅为待审方案，未创建workflow/触发运行：先选择明确授权的隔离Windows x64环境，固定源码/已锁载荷，仅自建私有临时子目录、单次最多6分钟/512MiB、无模型/业务网络/PG/传秘/用户电脑。先核真实固定租约/目录保护与互斥准入；原门未闭合时必须按真实拒绝记录，不绕门构造“已接受”lease。实际创建私有DACL目录、派生Token/默认DACL/TokenOwner、DPAPI合成哨兵等安全动作须逐项另批。当前NO_RESUME窗口不能验证真实initdb客户端成功；若后续验证客户端，须另外明确原自有测试进程创建/恢复范围与清理合同。任何窗都不能代签完整安装、数据库/actor权威或产品可用。

process_env.py只读取/转发白名单OS执行必需项：PATH、Windows系统目录/COMSPEC/PATHEXT、临时目录、locale/TZ。调用者显式添加该进程的Park DSN/模式/私有路径。未知环境项、HOME、PYTHONPATH、代理、模型token、其他项目密钥、迁移owner及测试owner不传给API/worker。CLI迁移/隔离测试owner仅传给明确对应进程，不打印值；本轮测试用虚构哨兵验证未知键不读取/不转发。

官方PowerShell工具只安装在忽略的工作区缓存作LinuxAST检查，使用显式XDG缓存/配置/数据目录，不改HOME/全局策略。Windows脚本仅支持原生平台；签名/执行策略由既有授权流程处理，不用Bypass/Set-ExecutionPolicy。Stop核对稳定PID身份和可信命令，AccessDenied不会被误报“进程不存在”，不强杀/停止数据库服务。

固定AT汇总只输出分类/计数/源hash，完整pytest错误/JUnit留私有.runtime；不要提交含会话或配置的原始诊断日志。真实园区资料/来源许可/实际效果没有授权，本轮全部合成，未知资格不得默认通过。


ENG007 shared_model_quota由独立协调库owner显式安装及授权两函数；应用不可自行授权/增额/DDL。真实两个产品需同协调库、同provider account标识、各自DB角色与产品额度；本轮仅临时库第二合成产品，不改Sim2Act。只保存预留/usage/分类，不共享业务正文/密钥。未知计费不退额，只有已确认未发送可释放。窗口冻结，不允许在未决调用中重置计数；真实计费/滚动窗口尚需规格。具体状态与恢复见ModelChain.md。


ENG008 Windows只读候选独立于files.py/生命周期：stdio ctypes官方DLL从SYSTEM32加载、handle-relative单名称打开、每级reparse/对象属性检查、私有root/files/file的owner/protected DACL只读校验、单硬链接/hash/UTF8；既有ACL不改，云端只FakeAPI/ABI证据。候选仅手工原生probe可调用，产品入口继续关闭，不存在自动Windows fallback/env启用开关。新probe仅刚创建的UUID合成目录/子fixture设置测试ACL，已有runtime不改；native安全/竞态未经验证，不能宣传安全通过，详见WindowsFileCandidate。
