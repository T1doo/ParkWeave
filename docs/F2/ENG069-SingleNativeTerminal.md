# ENG069 唯一标准 Windows CI 终态 FAIL；Restart 已定位到 owner 边界

已授权普通快进 push `46648fb → c10fef1`，只执行 push 自动触发的 [run37511398754](https://github.com/T1doo/ParkWeave/actions/runs/37511398754)，attempt1；终态 completed/failure，job112433171318，18分37秒。只读核验同HEAD唯一run、远端HEAD为c10fef15bd1196d0bac275754ef4e95599fa8ebe。原windows-2025／25分钟／共享预算未变；未dispatch或rerun、无LIVE、runner/权限/身份/代理扩展，真实模型调用/预算0。F1未签收、F2仅并行、Server非Win11、R4关闭，原环境及备份保留。

本次审查owner改动仅在首次创建前lstat拒绝既有file/link/directory；原首次新建session/config的CREATE_NEW与owner事务保留，没有修改既有文件owner或ACL。没有通过放宽严格合同使Restart通过。

## 精确最终源码的真实全套结果

CI source binding AVAILABLE且精确匹配c10fef1；1323项全部进入四片，每片coverage=true、reason=COMPLETE，没有NOT_RUN或timeout。CI执行源码78个测试/实现blob哈希与该提交manifest逐项一致。

| 片 | PASS | FAIL | SKIP | 总数 | 实际耗时ms | 终态 | 清理 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| S1 | 317 | 0 | 25 | 342 | 179250 | PASS/exit0 | OWNED_TREE_STOPPED |
| S2 | 299 | 3 | 22 | 324 | 198531 | FAIL/exit1 | OWNED_TREE_STOPPED |
| S3 | 342 | 1 | 4 | 347 | 242484 | FAIL/exit1 | OWNED_TREE_STOPPED |
| S4 | 307 | 3 | 0 | 310 | 350593 | FAIL/exit1 | OWNED_TREE_STOPPED |
| 全套 | 1265 | 7 | 51 | 1323 | — | FAIL/exit1 | OWNED_TREE_STOPPED |

native_lifecycle 72.203秒/exit1/timeoutFalse（deadline300），native_validation 992.078秒/exit1/timeoutFalse（可用deadline1151）；片计时之和970858ms不包括collection/协调/发布等开销，不与job时长混算。Prepare35秒SUCCESS，Lifecycle73秒FAIL，Validation993秒FAIL，Publish1秒SUCCESS，最终Stop步骤1秒SUCCESS，无预算耗尽证据。

[ENG068修前混合本地广跑](ENG068-TargetedRemainingRepairs.md)的1307项1297 PASS/1 FAIL/9 SKIP保持历史记录；随后该模块27 PASS不等于全仓全绿。它未被本次Windows结果覆盖或改写。

## Restart、正常路径 Stop 与原生 Job 分列

- Start_native实际PASS/exit0，API/worker RUNNING，2 attempts/1 response/1 timeout、0 mismatch/0 alive_refused；HEALTH_MATCH，mode/model/process=True，server_pid_valid=True，DIRECT_CHILD。
- Restart_native实际FAIL/exit1，category BoundaryError，boundary_phase private_acl，boundary_reason ACL_OWNER_MISMATCH。没有acl_object，具体ROOT/SESSIONS/CONFIG仍UNKNOWN；不能归因于TIME_WAIT，也不能从Start成功推出Restart通过。重启后读数/browser未到通过路径。
- 首次Stop为SOURCE_BOUND_INFERENCE：精确源码native_suite.py中只有Stop_native断言成功并确认process record消失后才能执行Restart row，本次真实Restart row已出现。没有独立公开Stop PASS row；此正常路径推知与Job专项无关。
- 原生Job `test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary`仍2 FAIL（两个参数均失败）；具体returncode/record/kernel/alive/unrelated断言点UNKNOWN。新增只读kernel oracle在本地的gold通过不能关闭实际专项。另两个native Job oracle没有单项PASS字段，不由外层树清理替代通过证据。
- 四片以及lifecycle/validation helper实际OWNED_TREE_STOPPED只证明其外层清理报告。PG status exit0/.015秒、PG stop exit0/.11秒，最终Stop owned cluster步骤SUCCESS；无独立app_stop phase annotation，不将两个final_stop RuntimeError wrapper行视作实际app Stop失败证据。

## 全部公开失败 ID 与实际 case 数

7失败case全部映射6个固定去参数函数；unknown=0、mapped/annotation省略=0、ids_truncated=false，7条安全notice完整发布。

| 片 | 去参数函数 ID | FAIL case数 |
| --- | --- | ---: |
| S2 | test_lifecycle_diagnostics::test_real_loopback_refusal_and_occupied_port_are_distinct | 1 |
| S2 | test_lifecycle_diagnostics::test_windows_port_probe_requires_exclusive_before_bind | 1 |
| S2 | test_synthetic_session_file::test_native_session_owner_matches_current_user_and_existing_bytes_protected | 1 |
| S3 | test_utf8_sources::test_actual_chinese_UI_http_under_non_utf8_path_default | 1 |
| S4 | test_owned_job::test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary | 2 |
| S4 | test_synthetic_config_file::test_native_config_first_creation_and_existing_bytes_protected | 1 |

与ENG067的11 FAIL相比净减少4，并非11项逐项全关闭；保留旧1283稳定case key并加40项。完整失败映射中不再出现原report malformed、ACL raw、bounded wrapper、summary invalid、acceptance CP1252五个函数；S1同342项由313/4/25变317/0/25。真实HTTP仍1FAIL，legacy/current参数及实际异常UNKNOWN；session/config各1FAIL，首次create或existing分支仍UNKNOWN；真实loopback仍1FAIL。

## 新增端口 fixture 失败的本地增量纠正

新增失败函数在ENG068把注入异常写成固定OSError(98)，在Windows errno.EADDRINUSE采用WSAEADDRINUSE=10048的政策下会被正确拒绝为PORT_CHECK_REFUSED，旧gold却要求PORT_OCCUPIED。[CPython3.12 errno实现](https://raw.githubusercontent.com/python/cpython/v3.12.0/Modules/errnomodule.c)明确Windows使用WSA对应值。这是源码可复现的fixture错误，不据此归因其余实际loopback失败。

仅本地提交 `281513905a83e3c3275ca1021338cbb30fa96b5e`：fixture分别注入98政策/98错误及10048政策/10048错误，两者固定gold PORT_OCCUPIED；保留10048政策拒绝旧98的固定负例PORT_CHECK_REFUSED。每分支仍精确exclusive→bind→close，生产port合同、owner/ACL和Job实现均未改动。8定点PASS，独立8 PASS/NO_BLOCKERS；lifecycle+分片相关90 PASS/7.56秒，manifest源指纹刷新。1323收集数量没有改变。该本地修复未push、未重新CI，不能改写本轮7FAIL或声称其余六个原失败已关闭。

[完整安全证据](evidence/eng069-single-native-terminal.json)保留精确源码、所有片级字段、固定Restart原因及公开失败映射。只读32条annotations中22条phase、7条safe notice、3条未解释；未下载原始私有日志，check summary/title/text均null。余下实际断言与具体ACL对象仍缺证据；本轮已结束，不扩权限、不修既有owner/ACL、不重复CI。
