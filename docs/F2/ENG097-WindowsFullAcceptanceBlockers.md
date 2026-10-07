# ENG097 Windows 全量验收阻塞与最小前置

审查基线 HEAD `cc4a46b0823fc1dfa8e5af5adf5d08d9700d780b`，以当前工作树源码和既有公开证据为准。本轮未请求日志、网络、原生 Windows 或新 CI，未恢复全量 workflow，未修改 owner、ACL、安全实现或预算。本文记录确认前置，不是权限申请或执行授权。F1 未签收、F2 仅并行探索、Server 不是 Win11，R4 关闭、真实模型预算 0。

## 当前可直接确认的工程阻塞

1. **当前 workflow 不运行全量验收。** [workflow 第49行](../../.github/workflows/windows-server-engineering.yml#L49)至文件末尾只有两分钟 controlled Job measurement，没有 Prepare、Lifecycle、Validation、四片回归、Publish 或 Stop。ENG078 的实际 success 仅属于该隔离测量；[安全结果 JSON 第42行](evidence/eng078-independent-job-native.json#L42)明确逐项 receipt、membership/signal、unrelated cleanup 不可用，第62行 full regression 为 NOT_RUN。不能用此绿色 job 替代全量。
2. **当前 full-regression manifest 与当前测试源码集合不一致。** `eng057-job-shards.json` 当前记录 53 文件、1463 历史 collection，当前工作树有 68 个 `tests/test_*.py`。15 个新文件不在四片；[regression_shards.py 第74行](../../scripts/windows_ci/regression_shards.py#L74)会首先报 `MANIFEST_SOURCE_SET_MISMATCH`。8 个旧文件 raw SHA256 已不等 manifest，补齐集合后还会在第81–83行报 `MANIFEST_HASH_MISMATCH`；独立 HEAD/blob/worktree 三方检查保持于 [source_bytes.py 第44行](../../scripts/windows_ci/source_bytes.py#L44)。这是工程冻结记录过期，不能删 integrity guard。
3. **恢复旧阶段不能绕开安全调用。** [Engineering.ps1 第53行](../../scripts/windows_ci/Engineering.ps1#L53)的 Protect-NewDirectory 使用 SetOwner/Set-Acl；所有 Action（包括 Publish、Stop）在第67–69行先创建并保护 TraceRoot，Prepare 在第78–80行再保护 PGRoot。因此只把原 YAML 阶段粘回并不形成 owner-free 全量链。Validation 还会调用 [native_suite.py 第209行](../../scripts/windows_ci/native_suite.py#L209)的 ServerFileTest，该脚本[第13行](../../scripts/windows_ci/ServerFileTest.ps1#L13)至第24行保护新 fixture directory 和 marker。本文不删除、替换或绕过这些保护。

初次只读指纹核对：53 个 test hash 中 8 个不一致；33 个 implementation hash 均匹配。diagnostic allowlist 当前有 816 个顶层测试函数，AST 对照未发现当前函数缺项，但 manifest 内 `diagnostic_allowlist_sha256` 已过期；该字段过期属于冻结证据问题，不据此声称现 pipeline 有独立 allowlist-hash 拒绝分支。

8 个旧测试指纹过期：`test_authorization_files.py`、`test_case_lifecycle.py`、`test_controlled_plans.py`、`test_executor_receipts.py`、`test_lifecycle_diagnostics.py`、`test_resource_combinations.py`、`test_resource_holds.py`、`test_worker_gateway.py`。

15 个未分片文件：`test_bounded_planning.py`、`test_case_path.py`、`test_catalog_decision_validity.py`、`test_plan_handoff_chain.py`、`test_plan_preview.py`、`test_readiness.py`、`test_request_intents.py`、`test_resource_catalog_concurrency.py`、`test_resource_plan_binding.py`、`test_resource_substitution_confirm.py`、`test_review_demo.py`、`test_rule_publication_boundary.py`、`test_rule_publication_candidate.py`、`test_run_access_candidate.py`、`test_service_case_steps.py`。ENG097 新测试冻结后须一并纳入；上述数字是初次审查快照，不是最终 collection。

## 既有 Windows 证据：已知失败与未完成不能混计

| 证据 | 实际结论 | 本轮解释边界 |
|---|---|---|
| [ENG063 第17行](ENG063-SingleNativeTerminal.md#L17) | 1117 PASS /49 FAIL /51 SKIP；Start CHILD_POLICY/POLICY_REFUSED | 当时具体 child 子检查和完整失败原因未公开，不把49项整体归因于一种缺陷。 |
| [ENG064](ENG064-LocalNativeFailures.md)、[ENG066](ENG066-TargetedLocalRepairs.md)、[ENG068](ENG068-TargetedRemainingRepairs.md) | portable strict fixture、真实 Windows mock 入口、CRLF、安全 failure-ID 映射、参数显示长度、精确 argv0 authority 等有本地定点修复 | Linux/mock PASS 不能自行关闭当时原生失败。ENG068 第5行记录后续真实 Start PASS，Restart 仍 FAIL。 |
| [ENG069 第9行](ENG069-SingleNativeTerminal.md#L9)至第19行 | 四片 coverage 全 true，1265 PASS /7 FAIL /51 SKIP | 是完整1323用例的历史失败结果，不是当前 HEAD 全量。7失败已完整映射；正常 Stop 的源码推知不替代专项 Job oracle。 |
| [ENG071 第9行](ENG071-SingleNativeRootCauseMeasurement.md#L9)至第15行 | Restart SERVICE_LOG owner mismatch；SESSION/CONFIG 权限比较失败；normal descendant LIVE；timeout专项 PASS；HTTP四项 PASS | HTTP canonical UTF8/LF/CRLF fixture修复有真实原生证明；旧假errno98 fixture不再出现在完整S2失败映射。owner与正常后代失败不能因此关闭。 |
| [ENG071 第19行](ENG071-SingleNativeRootCauseMeasurement.md#L19)至第28行 | S1/S2/S3 完整；S4 count NULL、coverage false、TimeoutExpired | 965 PASS /2 FAIL /54 SKIP仅属于前三片。不能称7 FAIL降为2，不能从260 completed progress推断剩余50用例成绩。外层 timeoutFalse不消除内层S4预算缺口。 |
| [ENG078 第17行](ENG078-IndependentNativeJobMeasurement.md#L17)至第23行 | 独立隔离 Job success，直接安全 JSON 不可用，日志路线明确 Forbidden 后停止 | 是有限的源码退出规则推断，不是四片、原生S4、任意整树或Win11证明；本轮不重试任何被拒日志路径。 |

原25分钟、work cutoff1300秒、Python cutoff1290秒、每片600秒和尾部200秒保留于 [BudgetControl.psm1 第13行](../../scripts/windows_ci/BudgetControl.psm1#L13)及 manifest limits。原生S4缺口先需要完整collection与fixture/阶段成本证据；不得凭历史Linux相对权重预测当前 Windows 必定完成，也不得扩预算或删用例使结果变绿。

## owner/ACL：实际阻塞与最小确认对象

**SESSION/CONFIG原生创建目前明确暂停。** [synthetic_session_file.py 第116行](../../src/parkweave/synthetic_session_file.py#L116)在构造 native backend、创建文件前拒绝 `OWNER_MUTATION_PAUSED`，native实例同样拒绝；第77–80行的 setter 也暂停，没有环境恢复开关。Lifecycle setup 第383–387行需要真实 session seed/config first creation，[native_suite.py 第156行](../../scripts/windows_ci/native_suite.py#L156)又要求 Setup→Start→Stop→Restart→browser 完整链。因此当前源码不能仅靠恢复 YAML 完成这条链。原生创建验收测试仍在 Windows 要求实际创建（`test_synthetic_session_file.py:49`、`test_synthetic_config_file.py:40`），不会因新增“暂停正确拒绝”测试通过而自动变成原创建 PASS；不擅自跳过或重写原验收目标。

ENG071 实测 owner_same=true，但 acl_equal=false、control_equal=false，owner_defaulted_changed=false，失败在 PERMISSIONS_COMPARE、未到 FD_TRANSFER。[ENG072 第13行](ENG072-OwnerPauseReadonlyCandidates.md#L13)至第21行明确有效ACE、control delta和有效访问语义仍未知；slack规范化的mock不能解释实际control同时变化。需要 security owner 确认权限保持合同及可用的持权精确对象只读观测目标；不得以对象范围授权豁免权限保持，不得换setter、裁剪比较、增privilege或修已有文件。

| 对象/动作前置 | 最小范围 | 风险与仍需确认 |
|---|---|---|
| 固定 SESSION、CONFIG 首次新建 | 原固定路径及 CREATE_NEW，先确认其他权限保持证据和恢复方案 | 原生owner变更后DACL/control不等已实测；失败后既有空文件仍保护，不自动删/修owner或ACL。 |
| SERVICE_LOG 首次新建 | 仅固定 `.runtime/windows-services.log`；当前 [lifecycle.py 第421行](../../scripts/windows/lifecycle.py#L421)普通append创建，Stop保留 | Restart owner mismatch已定位此对象。私有诊断、重解析/竞争/共享句柄及DACL/control保持必须确认；既有失败log的处理由明确范围决定，不能自动修复或覆写。 |
| PROCESS_RECORD 初始新建 | 仅本次 Start 独占创建的 `.runtime/windows-processes.json` | 包含私有PID/ctime/命令绑定，不能提前暴露或接管既有记录。尚未实测该对象owner失败，不标为已失败。 |
| PROCESS_RECORD 原子临时inode | 仅本次记录的 `.process-binding-UUID.json` 新对象及受限替换，[lifecycle.py 第235行](../../scripts/windows/lifecycle.py#L235)至第242行 | `os.replace`会换inode，只处理初始记录不能保障替换后的owner合同；临时泄漏、目标内容竞态、继承metadata均要评估，不赋予任意路径修复权限。 |
| FILES | 默认不纳入本次修复 | 当前Windows功能failclosed，LOCAL app不传file_root；仅未来独立实测/阶段确有需要时另行确认首次目录范围，不递归修ACL。 |
| ROOT / TraceRoot / PGRoot / ServerFileTest fixture | 分别列出现有新建保护调用及已有授权边界 | 不是SESSION/CONFIG同一事务；不能把普通mkdir当ACL保护，也不能因要求owner-free观测而移除保护。restore评审必须逐路径审计，既有ROOT不修复。 |

完整生产对象清单与风险保持 [ENG071 inventory 第9行](ENG071-OwnerScopeDecisionInventory.md#L9)至第16行；额外新对象的范围确认与SESSION/CONFIG权限保持证明是两个独立前置。当前任务不发权限申请或执行任何动作。

## Job与数据库诊断：不是owner确认的替代问题

ENG071 normal 的 exact descendant LIVE 是真实专项反例，timeout/unrelated gold PASS不能覆盖它。当前 [owned_job.py 第232行](../../scripts/windows_ci/owned_job.py#L232)至第241行在提供精确 observation_target 时会采样并拒绝非PASS观测；没有target的普通路径仍以Accounting.ActiveProcesses==0返回TreeStopped。只证明已核对进程的signal不能升级为任意整树证明。ENG078缺少直接receipt，现无足够证据关闭历史normal或原生S4；不按PID kill、不breakaway、不放宽身份、不加timeout。

真实端口occupied已实测10048，失败收敛到 DATABASE_GOLD 三项之一。ConnectionTimeout→OTHER与硬编码OperationalError gold冲突是已复现候选，不是ENG071实际异常子类已证明。[ENG072 第35行](ENG072-OwnerPauseReadonlyCandidates.md#L35)至第37行已有固定三gold/异常枚举只读观察；仅在实际子类型证据可用且工程范围明确后修相应fixture/白名单映射，不能接受任意OTHER或把10013当busy。本轮不修改此安全诊断代码。

## 本轮允许准备的最小工程修复

仅更新现有四片 manifest 的当前完整测试文件集、raw指纹、allowlist指纹及collection冻结证据。不删除原测试文件，不改变稳定ID规则；保留历史记录、原预算和原安全拒绝。当前global与四片的stable multiset精确验证；旧private 1463 keys逐项继承未核验。HEAD blob三方检查须在包含这些源码改动的提交形成后绑定实际HEAD，不能把未提交工作树hash冒称HEAD blob。

全量workflow恢复是另一个需评审的动作，当前不改；[ENG078 第13行](ENG078-IndependentNativeJobMeasurement.md#L13)要求恢复链先确认不调用暂停owner路径，再取得独立全回归运行授权。owner保持、额外对象范围、Job原生专项和S4有效整片终态未关闭前，不宣称 Windows全量通过。

## 冻结后的工程预检结果

在tests、backend与root维护的diagnostic allowlist冻结后，使用Linux Python执行一次global及四次独立分片 `pytest --collect-only`，全部exit 0。global实际69文件、1826 cases；四片分别453/459/458/456 cases及17/17/17/18文件。每片stable case multiset精确等于global中该片文件的投影，四片合并精确等于global，无缺失或重复。未使用旧private inventory，未证明历史1463个key的逐项继承，也没有以collection代替测试通过。

当前 [manifest](evidence/eng057-job-shards.json) 已冻结，SHA256 `9e884187d64515cd2fbc7d636a78a18a52a659989d1bb8aa1345c444f0ae6d9e`。69个测试文件raw hash与33个implementation raw hash均一致；diagnostic allowlist的834个ID与当前AST精确相等，其raw SHA256为 `331a4a52c84198e72e3ab4b6ded6b090bad8fe2a3e4b47ff787e6ead72fe8f14`。新material-corrections测试hash为 `697dac07810c01796451d7b99428973a35d296ead12b7e5333293bca19d6204d`。原四片预算未变，旧权重明确仅对应原文件，不能预测本轮Windows片耗时。

私有本地collection记录位于 `/tmp/eng097-global-collection.json` 与 `/tmp/eng097-S1-collection.json` 至 `/tmp/eng097-S4-collection.json`；各raw指纹已记入manifest。global inventory SHA256为 `8d0a41c935dab4d2564cc5ce3578bc1a2925f04c1de805d8c92e680fa46648f5`，这里不复制private stable key列表。工程fixture `tests/test_regression_shards.py` 与 `tests/test_source_bytes.py` 合计53 PASS，1项现有Starlette弃用warning，日志 `/tmp/eng097-manifest-checks.txt`。这些只证明Linux工程预检；不构成Windows owner/ACL、原生Job、数据库gold、四片终态或全量验收证据。

本轮未执行Windows、CI、网络、日志取回、owner/ACL修改或workflow恢复。manifest当前worktree raw bytes检查可执行；新源码尚须由包含本轮修改的实际提交建立HEAD/blob/worktree同源证明，再绑定后续运行。后续全量Linux执行结果由root另行记录。

首轮完整Linux1816PASS/1FAIL/9nativeSKIP（461.74秒）：唯一失败为既有迁移保留测试的health schema预期22未同步到23，产品源码未变。已修正该预期并定点1PASS（0.90秒），manifest对应rawhash刷新；保留首轮证据；最终完整Linux已通过，Windows范围仍按本文件限定。

最终manifest SHA256 `9e884187d64515cd2fbc7d636a78a18a52a659989d1bb8aa1345c444f0ae6d9e`；health期待23的单行修正未改69文件/1826个collection身份。完整Linux1817PASS/9nativeSKIP仅本地回归，Windows全量仍受以上阻塞。实际包含提交的HEAD/blob/worktree三方检查及远端/现有CI终态见 `.runtime/eng097-final-sync.json`，不能把父提交当新源码。
