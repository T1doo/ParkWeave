# F1安全配置与已知边界

本轮默认LOCAL + SYNTHETIC + MODEL_MOCK，localhost单产品数据库/身份/端口/日志。普通应用角色无DDL/身份或Grant UPDATE；迁移owner只用于明确setup。运行CLI的LIVE激活关闭；HTTP代码须显式LIVE持久预算与owner授权证据，不通过env布尔值启用；模型密钥仍不持久保存。数据库持续凭据的产品设计已改为：仅在本机私有目录、由当前Windows用户保护后持久保存。当前只允许相应源码与隔离合成测试，未实际创建、保存或解密真实凭据；原权限、原生运行和安装门不因此解除。

## 私有实例封装候选：未接存储或原生保护

`scripts/windows_portable/credential_envelope.py`只编码/校验敏感**明文字节**，不加密、不落盘，也不取得OS身份。封闭用途为DATABASE、SESSION、CONFIG；规范JSON拒重复键、未知字段、非精确类型、超限、损坏摘要和绑定不匹配。绑定包含ParkWeave、格式版本、实例UUID、当前用户SID及稳定root/lock/journal身份；不含generation、sequence或postmaster_start。调用者传入这些数据不构成真实租约、Windows身份或数据库创建证明。

DATABASE只含现有postgres与parkweave_app秘密；SESSION沿现有fixture-a/b/c三身份映射与互异要求，不套用导览六身份、不增Grant或补token。CONFIG schema2只引用DATABASE、SESSION两对象的最终文件身份和**密文**摘要，不引用自身ciphertext hash；还承载稳定数据库身份、schema32和载荷指纹。这些只是严格的候选格式，真实数据须由后续有权持句柄适配器核验，不能由同一份JSON自证。

`windows_user_protection.py`只定义DATA_BLOB布局和显式FakeAPI隔离接口，无DLL加载、真实DPAPI调用、默认原生实例或路径接口。Fake输出不是加密或原生验收证据。参数固定为用户级用途、禁止机器级flags和交互提示；原生入口仍拒绝。未来原生实现遵循[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)/[CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata)：保留用户配置漫游例外，不承诺防同用户恶意进程或管理员；不能只凭API成功或特定错误码判完整性。原生明文缓冲清理与LocalFree尚未实现/验收，Python/DSN副本也不承诺完全擦除。当前Fake只验证有界复制、已识别输出的zero/free顺序、双故障私有保留及公开错误脱敏；未知指针不解引用、不猜测释放，失败进入本适配器内sticky UNKNOWN，不代表安装状态已持久化。

FixedDirectoryLease还没有三个secrets对象的能力；本片不使用任意Path/open，也不映射旧JSON名称或接controller。后续存储仍须固定私有路径、原owner/raw DACL/control保护、CONFIG最后发布完整引用、失败UNKNOWN poison及独立原生持久化准入。旧lifecycle schema1与原SESSION/CONFIG路径不改，不自动迁移、重签、覆盖或重新供应。现有initdb --pwfile的明文输入缺口仍未解决，不允许先落明文再删除作为替代；双击入口、OWNER暂停、固定文件和载荷加载门均不变。

## 文件私有根

Linux从根及files的已打开descriptor核对：目录属主须当前有效UID，group/other不得有权限；普通文件亦须同属主且group/other无权限、单硬链接、hash/大小/UTF8核对。既有目录0777/0755或不同属主拒绝，且不chmod/chown/修复。新建files0700、fixture文件0600；不访问配置根外文件，不导入宿主/企业真实材料。

不安全目录由安装者在明确授权后选择调整或改用新私有根，本实现拒绝不代表已经修复该目录。POSIX检查不适用于Windows ACL；当前Windows backend保持关闭。Doctor候选只读检查Windows根/已有files/会话/日志/配置ACL与属主、根继承保护，允许当前用户及OS系统管理员既有安全语义；既有ACL不改。新根才创建私有ACL。本轮Native ACL/重解析点/ADS/目录替换/安装和用户权限门NOT_RUN。

## 子进程与环境

process_env.py只读取/转发白名单OS执行必需项：PATH、Windows系统目录/COMSPEC/PATHEXT、临时目录、locale/TZ。调用者显式添加该进程的Park DSN/模式/私有路径。未知环境项、HOME、PYTHONPATH、代理、模型token、其他项目密钥、迁移owner及测试owner不传给API/worker。CLI迁移/隔离测试owner仅传给明确对应进程，不打印值；本轮测试用虚构哨兵验证未知键不读取/不转发。

官方PowerShell工具只安装在忽略的工作区缓存作LinuxAST检查，使用显式XDG缓存/配置/数据目录，不改HOME/全局策略。Windows脚本仅支持原生平台；签名/执行策略由既有授权流程处理，不用Bypass/Set-ExecutionPolicy。Stop核对稳定PID身份和可信命令，AccessDenied不会被误报“进程不存在”，不强杀/停止数据库服务。

固定AT汇总只输出分类/计数/源hash，完整pytest错误/JUnit留私有.runtime；不要提交含会话或配置的原始诊断日志。真实园区资料/来源许可/实际效果没有授权，本轮全部合成，未知资格不得默认通过。


ENG007 shared_model_quota由独立协调库owner显式安装及授权两函数；应用不可自行授权/增额/DDL。真实两个产品需同协调库、同provider account标识、各自DB角色与产品额度；本轮仅临时库第二合成产品，不改Sim2Act。只保存预留/usage/分类，不共享业务正文/密钥。未知计费不退额，只有已确认未发送可释放。窗口冻结，不允许在未决调用中重置计数；真实计费/滚动窗口尚需规格。具体状态与恢复见ModelChain.md。


ENG008 Windows只读候选独立于files.py/生命周期：stdio ctypes官方DLL从SYSTEM32加载、handle-relative单名称打开、每级reparse/对象属性检查、私有root/files/file的owner/protected DACL只读校验、单硬链接/hash/UTF8；既有ACL不改，云端只FakeAPI/ABI证据。候选仅手工原生probe可调用，产品入口继续关闭，不存在自动Windows fallback/env启用开关。新probe仅刚创建的UUID合成目录/子fixture设置测试ACL，已有runtime不改；native安全/竞态未经验证，不能宣传安全通过，详见WindowsFileCandidate。
