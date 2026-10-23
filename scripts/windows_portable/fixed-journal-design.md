# 固定 journal inode 的 Windows 交接候选合同

格式已有`fixed_journal.py`、`fixed_directories.py`实现候选及真实Linux文件检查；`fixed_windows_journal.py`仅提供未准入的原生文件IO接口。未做断电/Windows验收，不解除旧v1的`WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED`、固定文件独立`WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED`或OWNER暂停。目标是保守拒绝下的交接安全；不保证首次建目录后断电仍可恢复使用。目录记录不授予DDL或身份权限。

使用既有私有根、独立永久lock和**同一个固定8192字节journal文件**。在原句柄相对路径、根/祖先/reparse/既有owner-control-raw-DACL检查下打开；持锁期间没有合法并发writer。journal持有读写句柄且禁止write/delete共享，不rename、不替换、不增删文件名；不请求管理员卷flush。文件ID与根/lock ID均进入记录，并与真实持有句柄复核。

两个4096字节slot，索引固定0/1。每slot布局：

| 字节 | 内容 |
| --- | --- |
| 0–7 | magic `PWLJv001` |
| 8–15 | little-endian uint32版本1、slot索引 |
| 16–31 | uint64 generation、sequence，正数且不得溢出 |
| 32–35 | uint32规范JSON正文长度，1–3072 |
| 36–67 | 正文SHA256 |
| 68–99 | 前一个完整slot的SHA256 |
| 100–127 | 必须为零的保留区 |
| 128–3967 | 正文及零填充 |
| 3968–4095 | 与首128字节逐字相同的footer |

正文只有schema、根/lock/journal物理ID、generation/sequence、phase、initialized、runtime、handoff；不含秘密/凭据/PID授权。header与正文计数必须相同。两槽各单次读取完整4096字节，检查全长、索引、双头尾、hash、零填充/无未知字段，并在读前后复核同一journal inode与原目录/锁绑定。两槽**都必须有效**，sequence严格相邻，较新slot的前向hash必须等于较旧slot全4096字节hash，generation变化仅可为新获取时精确+1。沿用原journal精确phase/initialized/runtime/handoff组合与代际转移校验；规范JSON拒绝重复键、未知字段与非规范编码，不凭hash或相邻sequence推定状态合法。hash是完整性检测，不是授权签名。

初次独占创建后，写入完整8192字节：gen1/seq1/NEW/OWNED的前hash全零，seq2/NEW/OWNED指向seq1。调用原文件句柄`FlushFileBuffers`并全量读回验证后才允许后续动作。**不由此推断文件名或父目录在断电后必然存在**；reopen遇缺根、缺lock、缺journal、文件长度/ID不符或缺坏槽必须拒绝，不补建、不转`claim_fresh`、不签发新数据库创建凭据。用户若未拿到可恢复名称，结果是保留数据供检查而非可用性保证。

检查点只覆盖较旧slot，固定偏移写完整新记录，sequence=旧最高+1，prevHash指向旧最高完整slot；文件长度不变。每次完整写、文件flush、两槽全量读回及身份复核成功后才向调用者确认；此前不得开始该阶段业务副作用。任一短写、读取异常、坏槽、错代/错链均UNKNOWN。禁止“选一个仍有效的旧slot”回退：新代OWNED半写留下坏槽时，旧RELEASE_PENDING不能重放。若失败发生于任何字节改变之前，两槽仍是旧合法相邻状态，则该次获取没有获确认、更没有执行业务动作。

新获取必须先真实取得原lock的内核排他，验证最高slot为READY_STOPPED+RELEASE_PENDING、初始化完成且所有自有进程已确认停止；然后持锁写入并flush/读回新代OWNED，成功后才返回lease。崩溃在返回前留下完整OWNED或任一坏槽时，下次拒绝；不能信任旧handoff。读取两个有效旧槽本身不代表新代获取已提交。

release先在仍持锁/根句柄时确认进程退出与清理，再写最高RELEASE_PENDING并flush/读回复核。随后单向冻结lease，只关闭本次原句柄；未知关闭不重试、不失锁回写。只有新一次真实排他获取才可独立完成该pending交接，不冒称旧close返回成功。UNKNOWN、部分初始化或未确认退出不得靠此方案修复。

Linux候选已检查实际两方向短写、两槽读取/flush失败、新代OWNED崩溃/撕裂、名称缺失与inode置换；4095个部分前缀仅为纯codec检查，不称4095个实际文件实验。真实Windows互斥/进程崩溃及断电/硬件持久性另验。调用者须显式选择`FixedPrivateDirectories`，默认v1路径不变、不自动迁移或补建；同lease并发操作在IO前拒绝，只有内部嵌套可重入。此候选仅消除**后续检查点对目录rename屏障的依赖**，不填补SESSION/CONFIG、受限秘密、DLL闭包、初始化或端用户成品验收。

官方依据：[FlushFileBuffers的文件句柄合同](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)、[NtCreateFile相对句柄与共享规则](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)。这里没有把文件flush等同目录flush。
