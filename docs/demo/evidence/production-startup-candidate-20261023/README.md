# 固定文件独立前置与 API/worker 就绪候选

`fixed_windows_journal.py`不再借用旧rename acquire：独立检查真实Win x64、现有本地NTFS drive句柄、既有SD与固定文件API必要事实，然后仍由模块级`WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED`拒绝实例root获取。env/布尔或替身事实不签原生接受。旧v1的`WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED`及新建OWNER暂停不变；只共享原句柄获取机械代码，后续固定file flush与首次名称缺失拒绝分开，不补建、不转fresh。此路径未在Windows执行。

`runtime_readiness.py`已接API只读`GET /api/runtime/readiness`：使用原active Bearer，返回当前主体、app-role/safe/schema与DB观测；拒绝不调用普通audit写入。worker显式stdio模式在首次claim前通过本次私有管道报告WAITING_GO，原业务循环仅精确GO后进入。`controller.py`要求API/worker两个原token、出生身份、challenge及当前主体/DB匹配，探针后独立重核物理库绑定，再持久RUNNING，最后一次GO/use。注册、EOF、同名DB/OID或自报PID都不能单独代签就绪。

独审发现Bearer原先在端点归属验证前发送的P2，已修：连接后、零应用字节时先用原hProcess前后出生身份与GetExtendedTcpTable的实际反向四元组ESTABLISHED唯一PID行核对，再send；缺native支持时HTTP函数零调用，错归属时sendall零调用。后两项由离线spy确认，不是本轮真实Windows网络捕获。系统表有界读取且不输出，不OpenProcess、不提升权限。帧增加精确数字/布尔类型检查，避免dict相等接受浮点/0/1。

最终`targeted-tests-2.log`为**98P，1.649秒**，分组25＋17＋21＋26＋9：进程25项、固定日志17项、目录21项、控制器26项、就绪9项。各组真实文件与替身范围见`validation.json`，不累加较早33P窗口。就绪9项包含真实ASGI＋FakeDB、3项真实Linux管道（DB/身份或业务端口明确fake）、严格DTO/逻辑配对/发凭据前拒绝及Windows表ABI替身。实际worker.main的首次claim/consume只在GO后调用fake端口，没有真实业务效果。Windows stdio检查为**真实Linux管道fd＋Windows CreateProcess/CRT句柄替身**，绝不是Windows CRT/原生通过。

整窗有界自有子进程为14个fork及7个Python子进程，最多2个同时存活；线程和临时目录按各测试收尾。没有PG、真实HTTP监听端口、Windows、CI、用户电脑、真实凭据或安全权限变化。控制器旧例及目录集成例显式替换ready seams，只验证控制流；不拿其正向当真实探针成功。日志保留原有Starlette/Pydantic警告，未为此安装或升级依赖。

最终源码及原日志获只读限定ACK，未见剩余确定源码P1/P2；审查者未执行或写入。同步libpq只有连接/语句超时及迟到拒签，**没有5秒传输硬抢占证明**；同步Windows PeekNamedPipe在多线程句柄上的阻塞、单帧write及空管道容量未实测。5秒消费者/10秒worker只是共享准入时钟，不冒充网络黑洞可抢占。

剩余最小实门：Windows固定前置/元数据/互斥/崩溃、端点与管道继承/容量/传输原生验证；受保护现有主体探针、秘密/SESSION-CONFIG与物理绑定安全适配器；私有PG/API/worker高层命令接线；安全嵌入运行时与私有DLL闭包及重包。默认双击入口仍明确关闭，本轮不是端用户成品验收。原405测试文件＋384实现文件共789原始指纹匹配；9521仅历史collection，本轮没有collection或全回归。

API依据：[GetExtendedTcpTable](https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable)、[TCP行](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcprow_owner_pid)、[TCP表及padding](https://learn.microsoft.com/en-us/windows/win32/api/tcpmib/ns-tcpmib-mib_tcptable_owner_pid)、[PeekNamedPipe及同步阻塞限制](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe)。
