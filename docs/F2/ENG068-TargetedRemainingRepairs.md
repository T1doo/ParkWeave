# ENG068 定点本地修复；原生结果保持 OPEN

代码 `b1b50f2a2c54c1e27bc10b1d6e7865acbdfb964a` 与报告仅本地提交；未 push 或触发新 CI。原环境和恢复备份保留。当前 shell 与同身份本地测试入口可用，一次exec-server transport disconnected后同一默认入口复核恢复，保存修改与进行中的回归均保留；未切换环境/代理/身份。F1未签收、F2仅并行探索、Server非Win11、R4关闭；真实模型调用/预算0。

最新真实 Windows 结果仍是 ENG067 run37504916551：Start_native PASS；Restart_native FAIL且固定原因UNKNOWN；回归1221 PASS /11 FAIL /51 SKIP。此次 Linux/注入结果不改写该终态。

## 已映射失败的定点处理

| 公开失败函数簇 | 本地修复/证据 | 实际 Windows 结论 |
| --- | --- | --- |
| report malformed/ACL raw/summary invalid，3个超大参数 | 保留原始超大输入及全部拒绝断言，仅显示ID缩短。实际pytest环境更新helper在受控32767字符setter下旧3项拒绝（524384/65649/65649字符），新收集0拒绝。 | 证明平台fixture长度缺陷；新原生结果尚未取得。 |
| bounded private wrapper，1项 | 原始owned command保持；Windows gold要求OWNED_TREE_STOPPED，Linux要求DIRECT_CHILD_STOPPED，与production路由一致。 | 新原生结果尚未取得；不替代Job专项oracle。 |
| acceptance CP1252，1项 | 原默认编码仍拒绝；gold适配当前固定ACCEPTANCE_BINDINGS_INVALID/UnicodeDecodeError报告及exit1。显式UTF8成功用真实非空1caseJUnitfixture。 | 新原生结果尚未取得。 |
| Chinese UI HTTP，1项 | 仍执行实际API源码并真实HTTP验证旧500/当前200、精确UTF8响应字节；拥有uvicorn线程并显式停止/join，替换无法确认Windowsredirector后代退出的fixture root-only终止。 | 原生断言原因UNKNOWN，不声称原实际失败由启动时间造成。 |
| session/config first creation，2项 | 既有file/link/directory先lstat拒绝，不申请WRITE_OWNER、不改变字节/mode；首次缺失仍CREATE_NEW，80/183冲突与5/32拒绝各自gold保留。仅新文件owner事务保持原合同。 | 原2项失败的firstcreate/secondcreate分支UNKNOWN；不泛化权限或修改既有owner/ACL。 |
| owned descendant两个参数，2项 | 保留真实managed进程链、2s/5s预算、生产Job实现、exit17/Timeout主结果及unrelated存活断言。观察改为精确只读kernel handle PID/ctime+Wait0；保留PID不等于kernel活。record/process/kernel无效时间、未知/read/open/close均不能PASS。 | 两个真实native参数仍OPEN，本机SKIP；正常路径Stop与专项结果分开。 |
| actual occupied/refused loopback，1项 | 真实Linuxloopback与原独占gold保留；非busy/权限固定PORT_CHECK_REFUSED，busy仍PORT_OCCUPIED。 | 实际Windows失败断言UNKNOWN。 |

## Restart 的最小受控边界

此前Start成功不能推出Restart成功。现有Start调用固定最多1秒的独占rebind预检，计入既有outer预算；每次仍SO_EXCLUSIVEADDRUSE，仅明确busy+连接拒绝允许再bind。活listener、权限、超时/未知直接拒绝；已有bound-not-listening到期仍拒绝；deadline之后不再尝试bind。没有SO_REUSEADDR、PID发现/终止、权限变更或health/Job预算延长。

此候选不能证明旧Restart实际原因是TIME_WAIT。Restart_native仅复用现有Start安全boundary/observation到producer、project、annotations和完整publication_capture；ACL、primary/cleanup身份拒绝及端口固定原因贯通gold通过，私有输入不回显。未新增通用诊断追踪器。

## 本地验证与审查

最终相关14模块453 PASS /8 Windows native SKIP /21.70秒；包含同身份真实loopback、隔离临时数据库、严格身份、源字节、Job、ACL、publisher/capture及分片合同。独立只读审查NO_BLOCKERS：238 PASS（6nativeSKIP、2restricted-loopback deselected）及最终10 port/Restart gold PASS；曾误纳restricted loopback EPERM不作代码FAIL。更广的执行以1307项收集启动：1297 PASS /1 FAIL /9 SKIP，302.16秒，包含已有业务/双角色/worker-gateway流程。唯一FAIL为test_ci_cleanup::test_actual_api_and_worker_launch_arguments_have_no_owner_env的旧单参数port替身；最小适配后明确断言8765/1秒，owner-env/launch断言保持，模块27 PASS、独立该项1 PASS。最终相关回归再次通过。运行中审查另加16项gold，最终1323项未重新完整执行，不能声称1323项全仓PASS。代码提交b1b50f2的51测试+27实现文件blob/raw/manifest SHA256逐项一致，既有文件可执行mode无变更。四片收集1323项（342/324/347/310），51文件、614函数白名单；所有ENG066的1283 stable case keys保留，40新case，exact四片multiset等于global。收集不是PASS声明。

原生专项及Restart关闭仍需未来单独授权的真实Windows验证；本轮不请求或执行新CI。
