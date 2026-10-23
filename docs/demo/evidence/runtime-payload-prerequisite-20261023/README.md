# 租约绑定的固定PG载荷静态前置候选

基线`fcbd2610ca0e994fd97b2a54d1b3ae6ae3cd880e`，源码与原件同一正常审查分支提交。没有下载运行时/DLL、安装、PG/Windows进程、真实凭据或新CI；未激活entry或cluster provider。

[`RuntimePayloadPrerequisite`](../../../../scripts/windows_portable/runtime_payload.py)绑定精确FixedDirectoryLease原对象及snapshot/root/lock、外部冻结manifest摘要和source SHA。manifest本身使用原根的相对句柄pin读取，原解析器提取成共用parse_manifest并严格检查完整行集合、重复/casefold键、单文件/总字节及数量。外部摘要须来自受审交接，内部manifest不能证明发布者身份或授予运行权限。

只检查manifest列出的完整`runtime/postgresql/`载荷子树，包括bin/lib/share及可能存在的许可文件。根下data/files/secrets不遍历。沿原pin保留祖先与文件句柄、owner/private mode/nlink/物理身份/名称/hash，held-fd前后两次枚举拒绝缺项、额外文件或空目录、链接与别名，复用原PE普通/延迟导入解析和builder有限bootstrap动态模块集合；不以manifest自报static状态代替重算。POSIX实际文件测试不证明同UID恶意并发防护、原子快照或未来加载期间不可变化。

新增的PayloadFileSpec不能进入原PrivateProcessAdapter的精确Command目录；默认可执行pin仍要求原exec位/ELF或MZ，只读数据pin允许空文件和0600。独审定位首个postgres.exe先于目录扫描被阻塞打开的FIFO风险，修复末级open加O_NONBLOCK后立刻按原fstat拒非普通对象。新增真实无writer FIFO场景在打开前断言该标志，验证修后拒绝及FD恢复；没有让旧实现实际挂起，也没有用线程或子进程制造超时。

Windows尚缺已接受的held-directory枚举，快照入口在文件读取前拒绝，不按路径回退；模拟platform分支检查不是Windows API执行。`inspect`只返回`activation_allowed=false/native_loading=NOT_ACCEPTED`静态观察。`require_for_cluster`即便静态通过仍硬拒`NATIVE_RUNTIME_LOADING_NOT_ACCEPTED`，没有env/布尔开关或合成receipt解禁。

本片不证明Python/实际OS DLL与API-set、符号/转发、动态加载或initdb内部行为。前片“无shell/单用户SQL”现明确仅指高层argv：initdb本身运行bootstrap/standalone backend及管道命令，pin initdb.exe不等于这些闭包已验。旧集群README与其SHA256SUMS只更新这一说明；旧validation/source hash和所有旧运行日志仍属历史`fcbd2610…`，没有刷新或冒充新受测源码。

最终唯一计数**23P/0.231s**：9项新真实Linux自有合成文件/固定租约检查，加14项受影响的原payload模块检查。原22P中间窗保留，不累加。所有PE都是不可执行合成结构，真实合成目录与FD已清理；没有业务DB、模型、会话或权限动作。准确argv/退出码/墙钟见final-targeted-invocation.json；读取错误叠加关闭错误保原两因且不重试，夹具close故障为实际close后注入未知。

该组件是静态预检，不是已完成的四个Security前置端口；受保护输入/密码文件、实际PG树与维护库端点/物理集群、应用角色认证、SESSION/CONFIG、Windows原生准入及端用户首建/停启仍缺。原OWNER暂停、旧v1和fixed Windows门均未解除。
