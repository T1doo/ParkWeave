# ENG064 本地修复：原生失败 oracle 与固定观测

代码提交 `68e5306`，基于 `e893137`；仅本地提交，无 push、新 CI、LIVE、权限/身份/代理修改。新附件恢复 ZIP SHA256 `d6e17408f0ba2c53a877e3c4dd6d19543e7ef75a83f5533ff3a22abe31d4da96` 实际核验一致，既有恢复树与备份保留。

## 实际失败证据及局限

沿已成功原身份正式工具路径，只读查询[同一 run37489722219](https://github.com/T1doo/ParkWeave/actions/runs/37489722219)的安全 annotations；没有读取被拒原日志，也没有新测量。实际1117 PASS／49 FAIL／51 SKIP，Lifecycle/Validation外层均 timeoutFalse、owned tree停止确认，不能改称泛化预算超时。公开11个去参数白名单 ID，另14个注释长度省略、unknown_failed_cases3；49项异常类别未公开，聚合JUnit源码只写空failure标签，无法事后还原每项category。[ENG063原生终态](ENG063-SingleNativeTerminal.md)保持原成绩。

| 公开失败 ID／本地共同原因分组 | 本地处理及证据范围 |
| --- | --- |
| bounded_observation 的 valid_health_response、successful_start、safe_projection；launcher_lifecycle relation_projection | portable fake child仅pid/create_time/poll，却在Windows进入真实strict绑定。fixture明确portable绑定关闭；另有独立strict正反oracle。独立before注入strict路径1 FAIL READINESS_TIMEOUT/.12s；after同注入1 PASS/.06s。 |
| ci_cleanup actual_launch_arguments | 同类portable fixture明确隔离strict绑定，继续断言子进程无owner/model/CI凭据环境。 |
| ci_cleanup browser_timeout；ci_diagnostics suite_publishes（6参数）；job_schedule extended_budget | Windows实际入口run_owned_job未被subprocess.run mock覆盖。补实际入口mock；相关orchestration增加nt/posix module proxy参数，不修改全局os.name。扫描并补preparation、minimal_observations、lifecycle_diagnostics、summary_publication同类double。 |
| acl_readonly setup_checks | 最终ACL边界测试误进真实Windows配置owner factory；仅fixture mock该factory，保留exclusive创建/配置内容/session字节/final read-only ACL断言；生产owner创建与检查保持。 |
| job_budget bounded_safe_stdout | 合成子进程text输出在Windows转CRLF，改用与真实publisher相同binary UTF8 LF。production capture严格比对原始annotation批次LF，前置JSON分隔符可LF/CRLF。 |
| lifecycle_diagnostics loopback_refusal/occupied | 绑定但未listen不能可靠表示Windows已占用listener；测试先持有listener验证占用，关闭自身listener后验证拒绝连接。正式同身份本地测试1 PASS/.04s；这是测试条件修正，不是实际49项异常已还原。 |

另发现原preparation status fixture已有source binding合同却缺相应合成字段，Linux本地可复现失败；补当前绑定及同头报告，保留status exit0身份不匹配仍FAIL的原oracle。以上是本地源码/测试复现分组，不是49项原生断言的完整归因。

## CHILD_POLICY 一次区分且保持严格合同

保留原identify_process的trusted command→ctime<.01→cwd→完整argv短路顺序及异常拒绝；固定原因TRUSTED_COMMAND_REFUSED／CTIME_MISMATCH／CWD_MISMATCH／COMMAND_MISMATCH／READ_FAILED。child snapshot仍要求与root工作目录、完整命令相等，拒绝码区分CWD_MISMATCH／ARGV0_MISMATCH／COMMAND_TAIL_MISMATCH／空命令COMMAND_MISMATCH。没有采集路径、PID、命令原文或时间差到公共输出。kernel10µs、direct parent、60秒creation window、held handles、borrowed不关闭、重检、只停止owned过程均保持。

实际上次CHILD_POLICY/POLICY_REFUSED仍不能指明具体子检查。官方[Python3.12 venv](https://docs.python.org/3.12/library/venv.html)与[CPython3.12 launcher源码](https://github.com/python/cpython/blob/v3.12.0/PC/launcher.c)支持Windows venv redirector重新组装base executable argv0且继承cwd/命令尾部的假设；不是该run已测证明。本轮没有放宽可接受exe路径或修改启动命令来迎合此假设。

## 四片证据沿现有结构保留

regression_shards原来已有private逐片status/counts/cleanup，native_suite/publisher丢弃；原来没记录逐片耗时。本轮在现有调用/结果解析区间记录elapsed_ms，不含global collection或最终report写入；经固定4行typed投影进入原fullreg notice，compact字段id/status/reason/counts/ms/cleanup/coverage/exit/category。未启动确知0与null耗时；执行后坏/missing JUnit为null counts，missing cleanup为UNAVAILABLE。late report failure保留有效观测，坏context为执行证据不可用，不能伪称PRECHECK/NOT_STARTED；坏aggregate counts的schema零占位标counts_scope UNAVAILABLE，native不公开假零。

整体native PASS还需全部四片PASS、counts有效且FAIL0、coverageTrue、exit0、cleanup OWNED_TREE_STOPPED；缺/坏summary强制FAIL。原8 notices、2KiB完整command（含LF）、16KiB batch、25 IDs不变。最长合法字段+25最长白名单ID+active ID+完整regression observation边界测试保留全4片；先省略整ID并计数，必要时只省略重型末片observation且明确标记。没有新增追踪器或修改预算。

## 冻结验证

- 最终相关19文件：501 PASS／2原生Windows SKIP／2隔离用例deselected／1既有warning，28.37秒。最后missing-observation小修的两个模块77 PASS／4.27秒；不累加重叠用例当唯一总数。
- 现有Case/资源关联/组合/回执/关闭重开与合法对手角色流程140 PASS／51.44秒，临时本地PostgreSQL并正常回收。默认沙箱先有140 setup ERROR（Unix socket EPERM），该失败记录保留；正式同身份本地测试成功后才记PASS。
- 独立只读审查NO_BLOCKERS：296 PASS／7.08秒，修补后11 PASS/.11秒，再4 PASS/.10秒；未修改文件或网络写。
- 当前全量collection1253，51文件，四片341/280/345/287；595白名单函数。四片独立stable multiset与global精确相同，旧函数全部保留；给旧orchestration新增平台参数会改变其旧exact case key，未声称全部旧1217 exact keys原样。collection不是1253 PASS。
- 提交后实际HEAD的51 test blobs SHA256 == manifest raw SHA256 == 工作树raw bytes；compileall与diffcheck通过。不是整个仓库无改动证明。

原生49 FAIL完整关闭、实际child子原因、新版四片原生计数与Windows逐项Job oracle仍待将来获准测量；本轮无push/newCI。F1未签收、F2仅并行探索、Server不是Win11、R4关闭、不自动资格判断或外部履约、模型调用/预算0。完整hash、前后证据及测试统计见[ENG064证据](evidence/eng064-local-native-failures.json)。
