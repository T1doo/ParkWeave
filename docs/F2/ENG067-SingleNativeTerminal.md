# ENG067 唯一标准 Windows CI：Start修复生效，整体FAIL

已按授权普通快进push `5146655 → 46648fb0ff3b13a4fc48ce2511a7ac07f85d2ded`，包含已审查代码649803f及报告46648fb；同HEAD只产生[run37504916551](https://github.com/T1doo/ParkWeave/actions/runs/37504916551)，attempt1、push event、**completed/failure**。Job112410995191实际1018秒（16分58秒），windows-2025、25分钟、contents:read及身份负例/Job预算/清理合同均不改，没有dispatch/rerun、第二CI或LIVE。

默认无凭据HEAD exit7（原代理8080不可连），已授权正式工具路径同身份HEAD HTTP200，远端只读/普通push/监测均成功。17:51:41断开通知后实际shell可读、快照更新、同身份gh查询成功，仍是同一run；没有认证拒绝、换身份绕过或回退旧迁移。终态后确认远端仍46648fb、同HEAD run总数1。

## 实际 Start、Stop 与生命周期

Start_native **PASS/exit0**：创建API/worker2，attempts2、responses1、timeout1、mismatch0、alive_refused0；API/worker RUNNING，last HEALTH_MATCH，mode/model/process匹配True，valid PID且server_relation **DIRECT_CHILD**。没有身份拒绝字段。这证明本轮首次启动在精确managed-to-base合同下完成绑定；不放宽argv0/path/尾部/ctime/父链/pins负例。代码和测试仍是已审查冻结版。

首次 Stop_native 可由**绑定当前源码的执行路径推断PASS/exit0**：已导出的Restart_native行只能在`assert script(Stop_native)`成功及`windows-processes.json`消失断言后出现；5个FAIL行全部公开且无Stop_native。它没有独立导出的PASS row，证据标SOURCE_BOUND_INFERENCE，不能冒充逐项直接输出。当前源还表明实际API/worker本地case阶段已通过才会走Stop/Restart；不代替浏览器或重启后读取的PASS记录。

Restart_native **FAIL/exit1**，lifecycle_exception phase=restart/category=AssertionError；Restart标签没有公开Start边界细码，原因 **UNKNOWN**，不猜成argv0、端口或权限失败。两个phase=final_stop/category=RuntimeError行是外层非零suite-command包装，不能据此判成独立Stop失败。

最后workflow Stop步骤SUCCESS；pg_status0/.016s、pg_stop0/.125s均timeoutFalse。没有app_stop phase annotation；源码条件是在processes record存在时才调用，当前缺该证据，不宣称独立最终app_stop oracle PASS。native_lifecycle63.735s/exit1/deadline300、native_validation909.906s/exit1/deadline1168，均timeoutFalse且 **OWNED_TREE_STOPPED**；这些outer cleanup不能替代专项Job断言。

## 四片实际成绩

合计 **1221 PASS／11 FAIL／51 SKIP = 1283**，每片statusFAIL/reasonCOMPLETE、coverageTrue、exit1、cleanupOWNED_TREE_STOPPED；不是超时或缺片。

| 片 | PASS | FAIL | SKIP | 片调用及解析耗时 |
| --- | ---: | ---: | ---: | ---: |
| S1 | 313 | 4 | 25 | 169.531s |
| S2 | 283 | 2 | 22 | 187.688s |
| S3 | 341 | 2 | 4 | 208.922s |
| S4 | 284 | 3 | 0 | 324.875s |

片耗时合计891.016秒，不等于global collection/外层启动/最终报告全部成本。source_binding AVAILABLE精确46648fb。历史ENG065为1160/42/51、1253项；净FAIL减少31但collection新增30，不称旧42项逐一关闭。此前两个regression_shards公开失败函数不再出现在本轮完整失败函数集合，不把所有旧S1失败都归给fixture。

## 全部失败白名单函数簇

11失败case完整聚合为10个去参数白名单函数；mapped_failed_cases11、unknown0、producer/annotation省略0、ids_truncatedFalse，逐片函数count之和精确为4/2/2/3。只公开无参数允许ID及数量，原始断言、异常文本、路径/签名/凭据均未读出。

| 完整白名单函数 ID | 失败case数 |
| --- | ---: |
| `test_ci_diagnostics::test_report_malformed_non_mapping_and_size_are_rejected` | 1 |
| `test_lifecycle_diagnostics::test_real_loopback_refusal_and_occupied_port_are_distinct` | 1 |
| `test_minimal_observations::test_acl_object_roundtrip_discards_private_or_multiple_output` | 1 |
| `test_owned_job::test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary` | 2 |
| `test_summary_publication::test_actual_bounded_private_wrapper_then_independent_publisher` | 1 |
| `test_summary_publication::test_invalid_non_utf8_duplicate_and_oversize_report_has_fixed_state` | 1 |
| `test_synthetic_config_file::test_native_config_first_creation_and_existing_bytes_protected` | 1 |
| `test_synthetic_session_file::test_native_session_owner_matches_current_user_and_existing_bytes_protected` | 1 |
| `test_utf8_sources::test_acceptance_old_default_cp1252_failure_and_current_utf8_specs_report` | 1 |
| `test_utf8_sources::test_actual_chinese_UI_http_under_non_utf8_path_default` | 1 |

按模块簇：report/summary边界3、ACL输出映射1、端口oracle1、native Job2、UTF8路径/HTTP2、native config/session owner2。函数归属已知不等于具体断言根因已知；没有用空JUnit failure标签猜AssertionError等类别。

## 原生 Job 专项及发布链

`test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary`仍 **2 FAIL**。源码有timeout False/True两个参数，但公共链不输出参数，不能还原每个具体失败断言。descendant停止、unrelated保留、primary结果及另外abrupt-coordinator专项四oracle整体保持 **OPEN**；没有逐项PASS导出。外层Lifecycle/Validation/各片OWNED_TREE_STOPPED都不是替代证据。

实际publisherSUCCESS/.062s，共33 annotations，其中8条固定安全notice，6case rows+header+case_ids续页；两条UTF8函数ID通过续页完整可见。case_counts10PASS/5FAIL/0NOT_RUN，case omission0；全部11失败case count公开且unknown/omission0。完整UTF8+LF notice字节[339, 545, 161, 2047, 165, 150, 113, 222]，总3742、最大2047≤2048；原8/2KiB/16KiB/25ID限制保持。重型末片计时observation为保留IDs被明确省略，4片counts/time/cleanup完整；未声称有末片fixture成本实测。check title/summary/text为null，没有下载原始私有logs。

剩余Restart原因、端口具体断言、原生Job专项、UTF8/文件owner/report-boundary断言及Server整体均未通过。本轮不追加修复或第二测量；报告仅本地提交。F1未签收、F2并行探索、Server非Win11、R4关闭、真实模型/预算0、不自动资格判断或外部履约。固定证据见[ENG067 JSON](evidence/eng067-single-native-terminal.json)。
