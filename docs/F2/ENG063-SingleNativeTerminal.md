# ENG063 同一CI认证恢复后的只读终态

用户仅授权约半小时后以原身份/正常已授权路径读一次状态，成功后继续同一run。原gh/formal require_escalated读取已恢复；没有登录、创建凭据、切换身份/代理、扩大权限、push、dispatch或rerun，没有读取私有job logs。原401是历史阻塞，现已取得终态。

[唯一run37489722219](https://github.com/T1doo/ParkWeave/actions/runs/37489722219) attempt1、completed/failure，精确source `f5c8667f664a12325a86f474cec974d2608f1de6`。最终同头总run1，原origin dev仍精确此头。job112358948871从15:42:13Z至16:00:51Z，总1118秒（18分38秒）。Prepare36秒成功，Lifecycle82秒失败，Validation971秒失败，Publish1秒成功，最终Stop1秒成功。

实际native helper：Lifecycle80.594秒/exit1/timeoutFalse，deadline300；Validation970.219秒/exit1/timeoutFalse，deadline1132。两外层均OWNED_TREE_STOPPED，regression内树亦OWNED_TREE_STOPPED。最终appStop0/.093秒、PGstatus0/.016秒、PGStop0/.125秒。没有预算耗尽证据；不能把失败或最后片时长解释为容量不足。

## 实际字节核验与拒绝分支

fullreg source_binding AVAILABLE且精确同SHA，按冻结调用链表示实际HEAD与全部51 test HEAD blobs/manifest raw SHA256/工作树raw bytes的预检已通过；approved blobs为LF且tests固定LF检出，故关闭本次CRLF检出障碍。没有独立导出的逐文件EOL计数，不声明整个工作树无改动。

Start50 attempts/50 responses/50 mismatches，最近mode/model匹配、health PID正整数、process_matches false、server_relation REFUSED，具体固定码CHILD_POLICY/POLICY_REFUSED；Start最后cleanup和内部finalStop相同码。冻结源码这一stage有两处：child cwd/command快照与root不一致，或identify(child, child_record, repo)失败；当前enum未区分哪一处，不能猜成redirector路径、cwd或ctime差。最近Start已越过前面的root检查、root pin、child父关系/creation window；不推导全部50次相同。created2/cleanup_attempted2/stopped0/foreign2，两根清理后仍RUNNING；foreign是合同拒绝，不是已证明外来进程或实际terminate次数。最后appStop0可包含owned Job回收后的ABSENT，不能反推严格身份通过。

## 回归实际结果及公开缺口

实际JUnit诊断test_cases_seen1217，aggregate1117PASS/49FAIL/51SKIP，总1217，fullreg FAIL/exit1。回归内Job确认停止。frozen四片collection为314/275/342/286；最后progress collected/completed286、elapsed343828ms，与固定顺序末片S4相符（源码推断）。公开摘要未提升每片typed状态/计数/耗时/cleanup或精确coverage_complete，故这些仍UNAVAILABLE；不能拿本地collection片数分摊原生PASS/FAIL/SKIP，不能用最后片343.828秒当全部回归耗时。四个native owned-Job测试逐项结果也未公开，不能用实际树回收替代pytest逐项oracle。

失败case49，unknown_failed_cases3；公开11个固定去参数ID，ids_truncated true、annotation_ids_omitted14，不能把11个ID称完整失败清单或臆测49个断言原因。API/browser/restart仍NOT_RUN/START_FAILED。安全发布SUMMARY_AVAILABLE/COMPLETED，6PASS/5FAIL/1NOT_RUN，6非PASS全部有notice、case omitted0；34总annotations中7 safe notices，payload最大1987字节/总3453字节，原8条/2KiB/16KiB/25ID边界保持。check title/summary/text null。

取得实际49项失败和CHILD_POLICY分支后，后续本地修复需围绕child策略合同与原生失败oracle分别复现；本轮不改实现/权限/身份容差或触发第二CI。R4关闭、F1未签收/F2并行探索、Server非Win11、LIVE预算0、原25分钟/每片600/尾部200秒及原环境备份保持。

完整固定字段与实际安全notices见[证据](evidence/eng063-single-native-terminal.json)。报告只本地提交，不push。
