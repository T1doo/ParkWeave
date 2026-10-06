# ENG065 唯一标准 Windows CI 终态与剩余失败

按用户新授权，普通快进推送已审查 `68e5306`／`5146655` 到既有 `dev/f1-foundation`，远端从 `f5c8667f664a12325a86f474cec974d2608f1de6` 到精确 source **`5146655a2ab56e842924eba93d4d39971394c7a3`**。没有重启旧恢复包任务。正常正式网络路径与原身份成功；未改变代理、身份、权限或策略，未读取原日志。workflow、Engineering、BudgetControl、owned_job 和配置owner实现与原远端字节一致，保留windows-2025／Python3.12x64／nativePG17、25分钟、共享wall/uptime截止与cleanup预算。

[唯一 run37498631767](https://github.com/T1doo/ParkWeave/actions/runs/37498631767) attempt1，completed/**failure**；终态后同头run总数1，原origin dev仍精确同SHA。job112389566941从16:48:46Z至17:05:16Z，**990秒／16分30秒**。Prepare34秒success，Lifecycle95秒failure，Validation844秒failure，Publish0秒success，最后Stop2秒success（步骤时刻精度为秒）。实际helper Lifecycle94.141秒／exit1／timeoutFalse／deadline300，Validation842.703秒／exit1／timeoutFalse／deadline1128；均OWNED_TREE_STOPPED。没有job预算耗尽证据，不能泛化为timeout或扩容理由。

## 实际 Windows 回归

**1160 PASS／42 FAIL／51 SKIP，共1253项**；fullreg FAIL／exit1，JUnit test_cases_seen1253，source_binding AVAILABLE且精确上述SHA。冻结调用链已实际核验51 test HEAD blobs／manifest SHA256／工作树raw bytes，不代表整个工作树无改动。

| 片 | PASS | FAIL | SKIP | 总数 | 调用及解析耗时 | coverage | exit | cleanup |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| S1 | 281 | 35 | 25 | 341 | 157.344秒 | true | 1 | OWNED_TREE_STOPPED |
| S2 | 256 | 2 | 22 | 280 | 180.578秒 | true | 1 | OWNED_TREE_STOPPED |
| S3 | 339 | 2 | 4 | 345 | 195.125秒 | true | 1 | OWNED_TREE_STOPPED |
| S4 | 284 | 3 | 0 | 287 | 288.891秒 | true | 1 | OWNED_TREE_STOPPED |

四片均statusFAIL／reasonCOMPLETE，表示其覆盖检查完整但存在实际失败，不是片执行通过。逐片计数相加精确等于实际aggregate，片总数与当前冻结collection一致。各片ms合计821.938秒；它们不含global collection及最终report写入，也不能把Validation与片合计间差值全部归因于某一个阶段。公共数据没有单独给出global collection_state／coverage_complete，仍不提升为全量通过。

末片progress collected/completed287、elapsed286921ms，setup95713／call175480／teardown14714ms，与本片288891ms调用区间不同；不是整个回归耗时。数据库采样只表示那个checkpoint：client_connections1、fixture_connections0、idle_txn/lock_waiters/blocked/fixture_databases均0，不推断整个run从未等待。

上次实际1117／49／51、1217项，本次1160／42／51、1253项：FAIL净少7，新增collection36。旧orchestration参数维度也改变，因此不是原49项逐一关闭证明；[ENG064本地501 PASS及角色140 PASS](ENG064-LocalNativeFailures.md)与本次Windows实测分开保留。

## 原生身份细码与清理

Start50 attempts、49 responses／49 mismatches、1 transport timeout，refused/http_errors/other_errors均0。最近mode/model匹配、health PID有效，process_matchesFalse、server_relationREFUSED，固定码 **CHILD_POLICY／ARGV0_MISMATCH**；Start cleanup和内部final_Stop_owned_services均相同细码。当前源码该分支确认child snapshot argv0与root snapshot argv0不一致，并已越过先行cwd、父关系与creation-window检查；没有导出原始路径或确认命令尾部单独匹配，不能把base-python路径或“只有argv0不同”当实测。

[Python3.12 venv redirector说明](https://docs.python.org/3.12/library/venv.html)与[官方launcher源码](https://github.com/python/cpython/blob/v3.12.0/PC/launcher.c)仍支持redirector argv0变化的解释，但具体exe值没有公开。本轮没有放宽身份或改启动命令。health READINESS_TIMEOUT是未取得严格匹配结果的边界；一次transport timeout也不能解释最后的具体argv0拒绝或推成job deadline耗尽。

Start created2／cleanup_attempted2／stopped0／absent0／foreign2；两根清理后仍RUNNING。foreign是严格合同拒绝标签，不是已证明恶意外来进程。内层final Stop FAIL／exit1／BoundaryError；外层Lifecycle/Validation和regression内树、全部四片均确认OWNED_TREE_STOPPED。最终app Stop0/.079秒、PGstatus0/.016秒、PGStop0/.109秒。最后app Stop可在Job回收后观察ABSENT，不能反推严格身份验证通过。API/browser/restart仍NOT_RUN／START_FAILED。

## 实际剩余失败簇与信息缺口

安全摘要仅公开4个去参数白名单ID：

- `test_lifecycle_diagnostics::test_real_loopback_refusal_and_occupied_port_are_distinct`：Windows端口占用／DSN拒绝oracle仍FAIL。该项本地Linux修补后1 PASS不能替代Windows；未公开哪个断言或异常类别。
- `test_owned_job::test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary`：原生owned descendant／unrelated／primary oracle有FAIL。实际helper/片确认tree回收不能代替该pytest逐项断言；未公开timeout参数或失败位置。
- `test_regression_shards::test_actual_expired_coordinator_persists_all_not_run_without_launch`。
- `test_regression_shards::test_each_shard_exports_actual_counts_invocation_cost_and_cleanup`。

后两项共同使用candidate fixture。源码 `str(path.relative_to(root))` 在Windows生成反斜杠路径，而production固定manifest合同要求正斜杠。仅本地临时合成数据的对照已证明forward-slash manifest接受、Windows格式manifest拒绝／MANIFEST_SCHEMA_REFUSED；没有改源码或生产合同。这是源码可证的共同候选缺陷，不能冒充实际逐项trace，尤其不能把全部S1的35 FAIL自动归为此因。该fixture当前collection涉及37项，另有本来期望拒绝或不调用manifest验证的测试，数量不是native失败归因。

实际42 failed_cases，unknown_failed_cases3，ids_truncatedTrue、annotation_ids_omitted16；公开4 ID不能当完整42项清单。逐项JUnit异常类别在聚合时未保留，安全check title/summary/text均null；其余失败的测试ID／断言类别仍UNAVAILABLE。按片实测的剩余失败簇规模为S1=35、S2=2、S3=2、S4=3，不能臆测每片中未公开失败的业务类别。

安全发布SUMMARY_AVAILABLE／COMPLETED、6 PASS／5 FAIL／1 NOT_RUN，annotation_cases_omitted0。34 annotations中7 safe notices，最大完整UTF8 command2021字节（含prefix和LF），整批3751字节；原8条／2048字节／16KiB／25 ID边界保持，全4片未省略。公开5个FAIL为Start、internal finalStop、lifecycle_exception、suite_exception、fullreg；两个RuntimeError wrapper是保留失败状态，不当独立native断言根因。

本轮一次普通push与一次标准CI完成，报告仅本地提交，不再push/dispatch/rerun。F1未签收、F2仅并行探索、Server不是Win11，R4关闭，无自动资格判断／外部履约／LIVE，真实模型与预算0。原环境与备份保留。实际安全JSON、完整步骤/时刻、前后计数、约束字节hash与本地候选对照见[ENG065证据](evidence/eng065-single-native-terminal.json)。
