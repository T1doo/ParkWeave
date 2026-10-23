# 固定文件双槽实现与 exec EOF 语义

[`fixed_journal.py`](../../../../scripts/windows_portable/fixed_journal.py)实现固定8192字节/两个4096槽的版本化codec与存储；[`fixed_directories.py`](../../../../scripts/windows_portable/fixed_directories.py)显式连接原lease状态机。Linux真实pread/pwrite/fsync，checkpoint只写偏移0或4096，不rename/替换journal inode。两槽均须合法，核头尾/零填充/hash链/规范JSON及精确阶段、代际、根/锁/journal物理ID。短写不续写，读/身份/写入不确定均毒化本次lease，恢复原字节不能重新启用；坏槽不回退旧PENDING，新获取先flush/读回新代OWNED再返回。名称缺失不补建，旧v1不迁移、默认路径不变。

同一入口门与明确owner/depth覆盖公开操作及进程pin直接调用的`_verify()`。仅私有同线程内部嵌套复用所有权；所有公开重入和其他线程竞争均在IO前BUSY，不能中途release关闭句柄。公开并发拒绝本身无IO，不毒化正在正常工作的owner。

Linux进程空EOF现只记`NO_ERROR_RECEIVED`，另独立观察原目标映像；未观察/快速退出不补签exec成功，业务就绪始终`NOT_CHECKED`。真实自有fork反例覆盖GO后exec前SIGTERM，以及不exec直接exit0。实际收到exec错误另记`ERROR_RECEIVED`。

最终`final-tests-4.log`为**41P，0.685秒**：进程24项（17个Linux实际文件/进程方法、1个waitid替身、6个Windows替身）；固定日志17项（15个Linux真实文件方法、1个4095前缀纯codec检查、1个Windows准入拒绝替身）。不是41个原生Windows检查。整窗16个真实自有子进程，顺序执行、最多一个活子进程；一个有界竞争线程已join。所有文件只在本轮own TemporaryDirectory，最终fd数恢复、夹具清理。没有PG、浏览器、CI、真实凭据、用户电脑或全局权限变更。

实际文件覆盖初写部分文件、两槽方向短写、旧PENDING后的新OWNED撕裂、fsync/读取/最终读回失败、inode与symlink置换、重算checksum仍非法的状态/代际/版本/物理ID、缺名称与v1拒绝；真实独立进程先BUSY，release后另一进程取得gen2 OWNED并os._exit17，随后拒绝重开。close后抛错只能由新一次真实排他获取完成pending交接，不追认旧close成功。4095个部分前缀只在内存codec中检查，不能称4095次磁盘或断电实验。

保留所有原始窗口，不累计：`fixed-tests-1.log`为13P/1ERROR，原因是测试循环重复release，已修测试记账；`process-tests-1.log`、`final-tests-2.log`和`final-tests-3.log`均为中间版本。独审发现RLock无法排斥同线程公开重入，且进程pin的直接验证也须取得入口门；统一owner/depth已闭合，最终源码及41P日志获限定ACK。审查者全程只读，未运行测试或写文件。

[`fixed_windows_journal.py`](../../../../scripts/windows_portable/fixed_windows_journal.py)只有未准入的原生固定文件接口，沿原门在根open前拒绝；没有把Linux实测或文件flush当作Windows目录/断电耐久。Windows原生互斥/崩溃、初始名字持久性、秘密/SESSION/CONFIG、PG/应用就绪接线、运行时/DLL闭包及成品入口仍未闭合。原OWNER暂停与Windows持久化拒绝均保持。

`validation.json`提供源码/原日志hash、未改关键文件及边界。原405测试文件与380实现文件共785原始指纹核对；9521仅历史collection，本轮未重跑collection或全回归。文件接口依据：[SetFilePointerEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfilepointerex)、[WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)、[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)。
