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

严格原生REOPEN仍未实现：现`IsolatedFixedSecretStore`只接受FakeSecretAPI和隔离保护器，读取事实不是Windows原生认证来源；因此schema4不能走其schema3的endpoint/authentication恢复口，更不能给native目录签发恢复能力。还缺真实三对象原生存储/CurrentUser解封到“全部关闭并最终核lease”的一次消费来源接线；这是源码依赖缺口，不以再次泛授权代替。旧/缺失/损坏profile不迁移、不认领，旧实例不能借NEW能力重开。源码检查不授权实际TokenOwner/DACL变更、原生进程、凭据传送或数据库启动，也不防恶意同用户/管理员并发或撤回已打开句柄。普通原子创建并不构成断电目录持久性证明。

process_env.py只读取/转发白名单OS执行必需项：PATH、Windows系统目录/COMSPEC/PATHEXT、临时目录、locale/TZ。调用者显式添加该进程的Park DSN/模式/私有路径。未知环境项、HOME、PYTHONPATH、代理、模型token、其他项目密钥、迁移owner及测试owner不传给API/worker。CLI迁移/隔离测试owner仅传给明确对应进程，不打印值；本轮测试用虚构哨兵验证未知键不读取/不转发。

官方PowerShell工具只安装在忽略的工作区缓存作LinuxAST检查，使用显式XDG缓存/配置/数据目录，不改HOME/全局策略。Windows脚本仅支持原生平台；签名/执行策略由既有授权流程处理，不用Bypass/Set-ExecutionPolicy。Stop核对稳定PID身份和可信命令，AccessDenied不会被误报“进程不存在”，不强杀/停止数据库服务。

固定AT汇总只输出分类/计数/源hash，完整pytest错误/JUnit留私有.runtime；不要提交含会话或配置的原始诊断日志。真实园区资料/来源许可/实际效果没有授权，本轮全部合成，未知资格不得默认通过。


ENG007 shared_model_quota由独立协调库owner显式安装及授权两函数；应用不可自行授权/增额/DDL。真实两个产品需同协调库、同provider account标识、各自DB角色与产品额度；本轮仅临时库第二合成产品，不改Sim2Act。只保存预留/usage/分类，不共享业务正文/密钥。未知计费不退额，只有已确认未发送可释放。窗口冻结，不允许在未决调用中重置计数；真实计费/滚动窗口尚需规格。具体状态与恢复见ModelChain.md。


ENG008 Windows只读候选独立于files.py/生命周期：stdio ctypes官方DLL从SYSTEM32加载、handle-relative单名称打开、每级reparse/对象属性检查、私有root/files/file的owner/protected DACL只读校验、单硬链接/hash/UTF8；既有ACL不改，云端只FakeAPI/ABI证据。候选仅手工原生probe可调用，产品入口继续关闭，不存在自动Windows fallback/env启用开关。新probe仅刚创建的UUID合成目录/子fixture设置测试ACL，已有runtime不改；native安全/竞态未经验证，不能宣传安全通过，详见WindowsFileCandidate。
