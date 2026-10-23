# 真实目录租约与有界文件/并发检查

[`directories.py`](../../../../scripts/windows_portable/directories.py)实现独占新根、保持不替换的锁inode、dir_fd相对读写与祖先/根/lock身份复核、有界原子journal、持锁RELEASE_PENDING及新获取先落盘OWNED代际。目录记录不是数据库出生或权限证明。锁从不删除，未知fd不重试，失锁后不回写。

最终`tests-6.log`为21项原输出：16项真实Linux文件/锁/受控子进程检查，5项Windows ABI/替身检查。其中控制器接线使用真实lease，其他PG/安全/应用端口仍为fake。两个真实竞争进程先在READY屏障均存活，parent持续持锁再放行，两者BUSY；parent close后另一进程ACQUIRED/STOPPED_RELEASED。最终一轮最多5个自有Python子进程，等待/清理和reader2048条均有界。所有测试文件仅在本轮自建TemporaryDirectory，已清理；没有PG/浏览器/CI/用户电脑操作或全局权限变化。

tests-1至6全部保留，不把各轮相加：tests-1的替身反例暴露重复关闭已消费未知锁句柄，两后端已修；tests-4为新加保留设备名测试发现异常类型未统一，已在IO前转为LeaseRefused。发布末尾绑定复核的独审P2已修，并由sync后换lock/final-read后换root的真实文件反例覆盖。最终增量独审限定ACK。`validation.json`含全部日志/源码hash和精确范围。

Linux flock只证明当前文件系统合作进程的实测互斥，不是对抗同UID恶意改名、管理员或断电的保证。原生Windows具体API源码在[`windows_directory_handles.py`](../../../../scripts/windows_portable/windows_directory_handles.py)，owner/control/raw DACL只读比对不等于整个SD全字段；新建仍受OWNER_MUTATION_PAUSED，真实根open/写入前因WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED拒绝。不能把Linux或替身通过当Windows互斥/崩溃恢复或安装成品。

查阅的官方API原件：[NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)、[FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)、[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)。目前未闭合所需目录元数据持久化合同，不以文件flush推定目录rename耐久，不请求管理员卷flush、不增加权限或放宽旧门。未接双击入口/包。
