# 连接诊断收尾验证

基线 `f26a09ecab71b6a277e9fee87f92f501ebf8e7a6`，原716输入冻结 `8ff6f34ad68c36c0c529957a6edaf2c25e5bbb38`。父线程已独审认可上批427项插桩回归，本批不再重复整批，不叠加业务功能或改产品/原测试源码。只执行一次关闭诊断的既定6项，再独立做一次自有pytest SIGINT清理冒烟；两项收尾校验通过，历史握手超时根因仍未知。

## 关闭诊断，原序六项一次通过

`six-no-diagnostics-invocation.json` 保存实际参数、帮助脚本hash、节点顺序及见证结果。没有传 `--owned-connection-diagnostics`，移除本子进程的writer/activation可选证据目录变量。只读见证在sessionstart、每个节点setup及sessionfinish确认配置为空、诊断current为空，`psycopg.Connection.connect/close`仍是原函数；见证不连接数据库、不包装连接、不执行SQL或开启PG日志。

六项按原顺序一次 **6PASS/0FAIL/ERROR/SKIP，JUnit17.702秒**；两项原失败用例的回执403、业务回滚快照相等、停writer后原键恢复未验证且不改历史及原清理断言均保留。没有放宽原2秒预算。这六项完全重叠于原427，不能累加为新全仓成绩。

1. `test_material_change_after_real_parent_lock_wait_refuses_activation`
2. `test_expiry_after_real_parent_lock_wait_refuses_activation[2]`
3. `test_real_expiry_during_receipt_endpoint_rolls_back_all_business_writes[3]`
4. `test_unsigned_json_cannot_add_metadata_participant[True]`
5. `test_unsigned_original_get_is_explicitly_unverified_and_never_repairs`
6. `test_verified_recovery_becomes_unverified_when_writer_offline_without_changing_history`

## 独立SIGINT清理校验

独立pytest只收集临时冒烟文件，显式复用原自有pg/fixture/preparation/receipt/writer夹具，开启原诊断插件以验证其收尾顺序。只使用合成资料和原reference writer，不创建真实身份、批准、分派或生产凭据。冒烟持有一条原app事务连接，完成 `SELECT 1` 后在主线程等待控制器SIGINT；没有锁住业务行或排队工作线程。

控制器只创建这个pytest子进程。在读取本轮ready记录后，核对pytest PID/cmdline、writer的直接父PID与启动tick，才单独向该pytest PID发送一次SIGINT，没有向进程组或未知PID发信号。writer由原夹具的SIGINT/wait逻辑回收；控制器没有直接操作writer或PG守护进程。

**pytest按预期退出2（KeyboardInterrupt），清理校验通过。** 原始JUnit含1个testcase元素、0failure/error，但测试在等待点中断，不能把它当作第7项pytest PASS。pytest原始日志无BadFD、无忽略的清理异常。记录证明以下单调时序：

| 事件 | monotonic_ns |
| --- | ---: |
| 持有连接close_end，closed=true | 9559147157719 |
| 测试finally确认连接已关闭 | 9559147468114 |
| sessionfinish外层进入，诊断仍在且fd有效 | 9559546501600 |
| 原writer退出并wait回收，退出码-2 | 9559719748068 |
| 原fixture到DONE后，diagnostic_finish | 9559753342889 |
| sessionfinish外层退出，current清空、fd已关闭 | 9559754428758 |

本窗29次受测连接全部观察到close；原fixture的DONE和writer退出均早于diagnostic_finish。控制器wait回收pytest后，pytest及writer两个 `/proc` 项均已消失。自有PG postmaster已退出，观察为Z态，等待其PID1父进程回收；它不是本控制器的直接子进程，不宣称已由本进程wait回收，也未为此改变权限或处理其他进程。PG日志由原夹具在清理前保存，不能保证含最终atexit关闭尾段。

该冒烟只证明这个主线程等待点的单次SIGINT清理，不能外推到握手/SQL阻塞中断、浏览器活跃请求、二次中断或崩溃。它不是一次自然ConnectionTimeout复现，也未验证失败单次pg_stat_activity采样路径；历史超时仍不作环境或产品根因归因。

## 封存与结束边界

新 `evidence/connection-diagnostics-closeout-20261017/` 封存原始六项日志/XML、SIGINT日志/XML、控制器及见证代码、单调事件/PG日志、验证结果及原件/公开副本hash配对。私有原件保留于本实例 `.runtime/runtime-diagnostic-closeout/`；公开文本仅脱敏源常量之外的43字符会话候选，JSON/JSONL/XML重解析，JUnit节点保持。原716输入无变化，旧证据按实际基线Git blob逐件核对；不改写上批日志或把此前失败改成通过。

已核对27692份继承证据，与基线实际Git blob逐件零差异。入口：[gate](evidence/connection-diagnostics-closeout-20261017/gate.json)、[六项JUnit](evidence/connection-diagnostics-closeout-20261017/six-no-diagnostics.xml)、[关闭诊断见证](evidence/connection-diagnostics-closeout-20261017/six-no-diagnostics-invocation.json)、[SIGINT原始日志](evidence/connection-diagnostics-closeout-20261017/sigint-smoke.log)、[中断清理验证](evidence/connection-diagnostics-closeout-20261017/sigint-verification.json)、[单调事件原件副本](evidence/connection-diagnostics-closeout-20261017/sigint-diagnostics/connections.jsonl)、[控制器信号与回收记录](evidence/connection-diagnostics-closeout-20261017/sigint-controller.json)、[原件/副本配对](evidence/connection-diagnostics-closeout-20261017/public-pairs.json)。

诊断至此停止，供独审后接回原产品主线。上批427插桩成绩仅引用父线程准入，本批没有再次执行；本批完成的pytest通过数仅6，预期中断单列。真实运行缺的合法身份/权限/记录、精确目录、原受保护binding/签名assignment及普通资源Approval契约保持；Windows/正式AT/真实业务/生产受保护host正向仍未验。无Actions查询、main/强推、部署、模型调用、新费用、真实凭据或安全网络权限变化，未知锁/进程/session未删除。
