# 固定应用对高层接线候选

基线`7d71853a01d07b156c87dc115baa627f6f58dbaf`。源码和原件随同一普通开发提交封存；未启动新CI，不是发布、安装或成品验收。

本片实现[`InstanceProcesses`](../../../../scripts/windows_portable/instance_processes.py)的应用对接线。首次创建与重开只选择各自独立cluster端口；一次尝试即消费该调用实例，未知不自动重试。原OWNER门仍在首次创建前拒绝。租约及原DatabaseInputs必须精确同对象，固定新布局为根下`data/postgresql`与`files`，不查找或移动旧安装。集群端口的真实初始化/启动仍未实现，不能把Protocol或替身称为生产PG接线完成。

应用固定调用包内`runtime/python/python.exe`的隔离解释器、原`configured_app`及stdio worker。不接受外部argv/env或可选业务开关；仅显式app-role、IPv4回环DSN、LOCAL模式及同根文件目录进入冻结环境。既有无环境Command仍保持原默认行为。秘密不打印、不写参数或本证据；本测试DSN是无密码的合成字符串，不连接任何监听器。

原创建登记回调即时把能力交给控制器，先登记再继续创建；只保留本次token及所属adapter，不按PID猜目标。应用对返回时不自称READY、不发GO，原控制器仍先真实ready核验、复核物理库、RUNNING落盘再唯一GO。未知清理只记False/错误，不对cluster端口重复发送；原错误与controller清理错误链仍保留。

最终唯一计数见`final-targeted.log`与`final-targeted-invocation.json`：**13P**，包括新模块9项（其中一项沿原Controller控制流验证NEW和REOPEN）、旧Controller2项、就绪消费者1项、Windows stdio替身1项。均是受控替身/逻辑检查，不创建子进程，不连接PG，不创建凭据/SESSION/CONFIG或目录，不调用真实Windows API。首次8P中间窗保存在`targeted-1.log`，不加到13P。原依赖deprecation警告保留，没有为本片安装或升级依赖。

`validation.json`记录原入口/构建器/安全创建/控制器/就绪及三页面逐字不变的hash。OWNER暂停、Windows原生固定文件门、旧v1拒绝均未解除。真实集群、安全文件与物理库证明、运行时DLL闭包、打包接入和Windows首建/退出/重开仍未完成；不能把本片签成自包含成品可用。亦未改变正式来源、LIVE或AT31暂存边界。
