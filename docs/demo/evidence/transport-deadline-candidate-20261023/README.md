# 共享绝对截止传输候选

基线 aec90a90e591ed4cce0fabdbdfff3ccf1a12b56d。源码与本证据同提交；仅开发分支归档，不是发布、原生安装或可用成品。

最终唯一计数 **12P / 2.946s**（final-targeted.log）：新模块6方法，其中1方法含两个actual libpq + synthetic wire连接/查询黑洞子场景，5方法实际Linux冻结Python helper；另外2受影响就绪消费者/互斥测试、3旧Windows创建替身及1新增CRT关闭未知替身。7个实际Linux helper顺序创建，pidfd/birth/原精确能力TERM与reap，无业务子进程。根业务进程身份是明确替身。两黑洞约0.352秒客户端EOF，线程join、监听器关闭及fd数恢复；不是真实PostgreSQL或成功身份验证。Windows源码/ABI替身不能签原生Job/管道。

原时钟5秒不重置；辅助进程工作截止预留0.5秒收尾。非阻塞libpq只读启动配置、send/flush/consume/get_result均用当前socket及同一截止；结束finish原PGconn，不等同步cancel/COMMIT。管道阻塞只在冻结辅助进程内，根进程不再PeekNamedPipe或等活跃writer读结果。先确认helper及所有parent writer关闭，再有界读结果；清理未知保留cap并记lease UNKNOWN。GO可能已写出的超时、畸形结果、OS/解析错误均UNKNOWN、保cause且不重发。原worker业务自身同步DB调用仍在可精确停止的worker内，不能据此签Windows整启动硬实时保证。

历史窗不累加：targeted-1因私有Python副本缺测试stdlib定位而失败；targeted-2为早期4P；targeted-3的广域os.read注入后，测试末尾无界读取挂起，GO状态当时未知，不能推断产品根因。仅本次unittest的准确argv/PPID/birth与pidfd核验后SIGINT，退出已观察（test-harness-stop.json）；独立读取该进程/proc/cwd曾被内核PermissionError拒绝，未重试或提权，该读取不是后续停止依据。修后仅_decode注入且断言读前select有界。targeted-4与affected-1是中间窗，不加到最终12P。原stderr警告保留，未安装新依赖。

独审最终限定ACK见review.txt。OWNER_MUTATION_PAUSED、旧v1和固定文件Windows原生门逐字保留；双击入口仍关闭。未启动真实PG、业务、Windows、用户电脑、浏览器或CI，未生成秘密/凭据，未改ACL/系统权限。Windows DLL闭包、秘密SESSION/CONFIG、高层私有实例启动/真实身份验真、原生持久恢复仍待闭合。

依据：[libpq连接轮询](https://www.postgresql.org/docs/17/libpq-connect.html)、[异步命令](https://www.postgresql.org/docs/17/libpq-async.html)、[Windows匿名管道写入语义](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createpipe)。这些资料不是本环境原生验收。
