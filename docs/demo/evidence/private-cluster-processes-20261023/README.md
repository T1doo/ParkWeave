# 固定集群进程编排候选

基线`522d0a376f652e8e5a0ff37023af837eeb970586`，源码与本证据同一正常审查分支提交；未接双击入口/构建器，不是发布或自包含成品。

[`FixedClusterProcesses`](../../../../scripts/windows_portable/cluster_processes.py)只固定编排包内initdb.exe/postgres.exe与原`PrivateProcessAdapter`。NEW仍先在配置/文件/进程端口前拒绝OWNER暂停；受控测试显式替换此门，仅证明分流控制流。将来前置另通过时才允许initdb读取根下固定`secrets/postgres-bootstrap.password`、初始化`data/postgresql`；不得覆盖已有/部分目录。确切int退出0后还须同原token确认整个Job退出，才能启动postgres。REOPEN命令表只有postgres，不调用initdb，不读取/传递密码文件，不迁移、seed、补session或自动修复。

三份原DatabaseInputs仅接受同一个回环127.0.0.1/端口，maintenance为postgres库/postgres角色，owner为parkweave库/postgres，应用为parkweave_app；此对象不是NativeDatabaseCreationEvidence或任何权限证明。命令不含密码/DSN，只传固定路径、SCRAM选项及端口；无trust、禁fsync、单用户SQL、系统服务或shell动作，子进程不继承项目/PG/provider环境。官方参数依据为[initdb](https://www.postgresql.org/docs/17/app-initdb.html)和[postgres](https://www.postgresql.org/docs/17/app-postgres.html)，未下载运行时或DLL。

四项必需`ClusterPrerequisites`目前都是未实现的生产依赖，没有默认成功实现：

- 读取并绑定原受保护配置输入，不生成秘密。
- 持有/验真密码文件、祖先及新数据目标，保障initdb后续路径打开的owner/DACL/reparse/名称边界。
- 验真新初始化或既有PG树/配置/物理身份，拒绝UNKNOWN交接或未确认的旧进程退出，不修文件。
- 真实维护库认证及物理集群验真，发送凭据前核连接与原进程出生身份；exec/端口打开/pg_isready不算证明。

还有原应用角色前置未解决：原issuer在CREATE DATABASE前检查parkweave_app安全存在，原roles.sql只GRANT。此provider不创建该角色，不把initdb/服务就绪冒充完整安装。进程Job全退不等于干净数据库停机；正常PG WAL恢复仍需真实ready等待，不代替schema/session恢复。OWNER及Windows固定文件原生门保持，安全SESSION/CONFIG、角色认证、runtime/DLL和端用户首建/退出/重开都未验。

原token在创建时沿cluster→InstanceProcesses→Controller即时传递；NEW四token、REOPEN三token由原控制器逆序收尾。部分启动、owner拒绝、出生身份变化、迟到、退出未知均保原错误，失败调用不重试；清理False/raise只尝试本次capability一次，原主因与清理错误链同时保留。未猜PID、删除锁或调用pg_ctl。

30秒协作式启动时钟传给全部检查，initdb每片观察≤5秒，ready预留原3秒清理；调用返回后再核截止。不承诺未实现回调/全部内核IO已被强制限时或中断。原adapter创建2秒/停止3秒未扩，未改监督器或CI预算。

最终唯一计数为`final-targeted.log`的**11P/0.145s**，准确argv/退出码/墙钟见`final-targeted-invocation.json`。全部为受控逻辑/进程API/文件检查/ready替身，包含原Controller+上片应用桥的NEW/REOPEN及owner拒绝叠加清理失败；没有文件/网络操作、子进程、PG、Windows API、凭据/session创建或CI。原11P中间窗保留，不累加。校验hash与原安全/入口文件零差异见validation.json；不能据本片签生产运行。
