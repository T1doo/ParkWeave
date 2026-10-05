# F1安全配置与已知边界

本轮默认LOCAL + SYNTHETIC + MODEL_MOCK，localhost单产品数据库/身份/端口/日志。普通应用角色无DDL/身份或Grant UPDATE；迁移owner只用于明确setup。运行CLI的LIVE激活关闭；HTTP代码须显式LIVE持久预算与owner授权证据，不通过env布尔值启用；不保存模型/数据库持续凭据。

## 文件私有根

Linux从根及files的已打开descriptor核对：目录属主须当前有效UID，group/other不得有权限；普通文件亦须同属主且group/other无权限、单硬链接、hash/大小/UTF8核对。既有目录0777/0755或不同属主拒绝，且不chmod/chown/修复。新建files0700、fixture文件0600；不访问配置根外文件，不导入宿主/企业真实材料。

不安全目录由安装者在明确授权后选择调整或改用新私有根，本实现拒绝不代表已经修复该目录。POSIX检查不适用于Windows ACL；当前Windows backend保持关闭。Doctor候选只读检查Windows根/已有files/会话/日志/配置ACL与属主、根继承保护，允许当前用户及OS系统管理员既有安全语义；既有ACL不改。新根才创建私有ACL。本轮Native ACL/重解析点/ADS/目录替换/安装和用户权限门NOT_RUN。

## 子进程与环境

process_env.py只读取/转发白名单OS执行必需项：PATH、Windows系统目录/COMSPEC/PATHEXT、临时目录、locale/TZ。调用者显式添加该进程的Park DSN/模式/私有路径。未知环境项、HOME、PYTHONPATH、代理、模型token、其他项目密钥、迁移owner及测试owner不传给API/worker。CLI迁移/隔离测试owner仅传给明确对应进程，不打印值；本轮测试用虚构哨兵验证未知键不读取/不转发。

官方PowerShell工具只安装在忽略的工作区缓存作LinuxAST检查，使用显式XDG缓存/配置/数据目录，不改HOME/全局策略。Windows脚本仅支持原生平台；签名/执行策略由既有授权流程处理，不用Bypass/Set-ExecutionPolicy。Stop核对稳定PID身份和可信命令，AccessDenied不会被误报“进程不存在”，不强杀/停止数据库服务。

固定AT汇总只输出分类/计数/源hash，完整pytest错误/JUnit留私有.runtime；不要提交含会话或配置的原始诊断日志。真实园区资料/来源许可/实际效果没有授权，本轮全部合成，未知资格不得默认通过。


ENG007 shared_model_quota由独立协调库owner显式安装及授权两函数；应用不可自行授权/增额/DDL。真实两个产品需同协调库、同provider account标识、各自DB角色与产品额度；本轮仅临时库第二合成产品，不改Sim2Act。只保存预留/usage/分类，不共享业务正文/密钥。未知计费不退额，只有已确认未发送可释放。窗口冻结，不允许在未决调用中重置计数；真实计费/滚动窗口尚需规格。具体状态与恢复见ModelChain.md。


ENG008 Windows只读候选独立于files.py/生命周期：stdio ctypes官方DLL从SYSTEM32加载、handle-relative单名称打开、每级reparse/对象属性检查、私有root/files/file的owner/protected DACL只读校验、单硬链接/hash/UTF8；既有ACL不改，云端只FakeAPI/ABI证据。候选仅手工原生probe可调用，产品入口继续关闭，不存在自动Windows fallback/env启用开关。新probe仅刚创建的UUID合成目录/子fixture设置测试ACL，已有runtime不改；native安全/竞态未经验证，不能宣传安全通过，详见WindowsFileCandidate。
