# 自有进程句柄候选：定向实际检查

[`processes.py`](../../../../scripts/windows_portable/processes.py)冻结私有可执行文件/参数目录，持有并复核原文件与目录身份；仅发行无资源属性的opaque token，真实状态留本次adapter私有登记。创建即登记、注册完成后才执行，停止只接受本实例原token。未知退出保留原观察句柄并把真实目录lease标UNKNOWN，既不重试信号/未知关闭，也不允许新adapter重开。进程句柄不授予数据库创建权限。

最终`tests-5.log`为22项原始输出，0.316秒：15项Linux真实文件/进程方法（12个真实fork子进程，另3项启动前拒绝/资源清理）、1项纯waitid结果替身、6项Windows替身。Linux只执行本环境已有sleep/true字节的私有副本，sleep最多5秒，同时最多一个活子进程；启动/停止各2/3秒，注入故障结束后的测试清理只用原保留cap，最多2秒。每项核fd总数恢复，own TemporaryDirectory结束清理。没有PG、浏览器、CI、Windows或用户电脑操作，没有真实凭据或全局权限变更。

实际覆盖gated fork→pidfd/birth→注册→fd-exec及真实映像、exec失败错误管道、自然退出WNOWAIT/reap、同一pidfd的TERM/KILL、pin失败GO EOF退出126/零信号、未知观察阻断重开、私有文件漂移/符号链接/注册后子目录置换、部分管道和环境失败资源保全。Windows替身覆盖创建后stdio关闭失败、AssignJob失败、未入Job子进程的原HANDLE终止/等待、未知等待保留、句柄只消费一次，以及Job配置与关闭双故障UNKNOWN。**替身不是Windows原生验收。**

初稿smoke及tests-1至4均保留，不累计通过数。独审发现两个确定P2：已发行cap的可变resources可改写清理目标；原create_job在配置异常叠加close失败时未登记句柄。已分别改为opaque token/私有state，以及CreateJob立即登记后才SetInfo，并补反例。另修创建中stop重入、环境构造异常收尾及waitid信号负码。最终源码和22项日志获得只读限定ACK；审查者未运行测试或进程、未写文件。`validation.json`列精确hash及所有未验边界。

[`fixed-journal-design.md`](../../../../scripts/windows_portable/fixed-journal-design.md)仅获设计ACK：固定inode双槽、任一坏槽拒绝，不回退旧PENDING；不从文件flush推定初始目录名称耐久，缺名拒绝且不自动fresh。未实现，不撤`WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED`或`OWNER_MUTATION_PAUSED`。

Windows实际句柄/Job、固定日志实施与崩溃/断电、PG/应用就绪及控制器高层接线、秘密/SESSION/CONFIG、私有DLL/安全运行时仍未闭合。当前未加入载荷/双击入口，不是可运行成品。源码指纹刷新为405个原测试文件+376个实现文件，9521仅历史collection，本轮未重复collection/全回归/巨大套件。
