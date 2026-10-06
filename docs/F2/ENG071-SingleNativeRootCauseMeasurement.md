# ENG071 唯一标准原生根因测量终态

普通FF已推送已审ENG070提交链（含1fe2a06b/ebd2b1ec）与独立审查通过的固定观测 `2339a4dc306950b2b06c92f283d528407c9d3f14`，远端从c10fef1前进到2339a4d。唯一[run37518589501](https://github.com/T1doo/ParkWeave/actions/runs/37518589501) attempt1 completed/failure，job112457807212耗时1249秒（20分49秒）。无第二CI/dispatch/rerun/预算扩展/LIVE。只读取固定check annotations与步骤元数据，不下载原始日志。证据：[安全终态JSON](evidence/eng071-single-native-root-cause.json)。

## 现在可决策的根因

| 项目 | 实际原生证据 | 可决策结论与边界 |
| --- | --- | --- |
| Restart | private_acl / ACL_OWNER_MISMATCH / **SERVICE_LOG** | 不再UNKNOWN。Start普通append首次产生log，Stop保留，Restart首次检查到该日志owner不等当前User SID。SESSION/CONFIG未发现replace；正常首次Stop强制确认STATE已不存在。日志首次owner事务超现有session/config范围，本轮未实现或执行。 |
| SESSION首次owner / CONFIG首次owner | 二者均 **PERMISSIONS_COMPARE / SESSION_PERMISSIONS_CHANGED**；owner_same=true，acl_equal=false，control_equal=false，owner_defaulted_changed=false | Owner设置与验证已成功，真正拒绝是owner操作前后DACL字节与非owner-defaulted控制位均改变。不是TOKEN_QUERY或owner仍不匹配，未到FD_TRANSFER/token流，也未测第二次existing refusal；不得删比较或把已有文件owner/ACL修复当解法。原Setup的受保护ROOT路径可用不证明普通TempPath继承场景。 |
| 最小Job正常退出 | primary=EXIT17；record=AVAILABLE；unrelated exactleaf=LIVE；cleanup=OWNED_TREE_STOPPED；**descendant=LIVE**，FAIL于DESCENDANT_EXACT_HANDLE | 同PID/有效创建时间、psutil身份与kernel句柄创建时间比较已通过，WaitForSingleObject(0)为unsignaled。这是具体反例：aggregate TreeStopped不能证明全部后代句柄已停止。stop_tree当前只看TerminateJobObject成功及Accounting.ActiveProcesses==0，没有逐后代signal gold。当前未测同句柄innerJob membership及signal序列，不能区分短暂终止/accounting竞态、managed链归属或其他内核语义；不宣称escape，不kill记录PID。 |
| 最小Job父timeout | primary=TIMEOUT；recordAVAILABLE；unrelated exactleafLIVE；descendantABSENT；cleanupTreeStopped；**PASS** | 三项独立gold实测通过，仅此受控场景。原两项Job fixture在独立测量也均PASS，但S4回归timeout且无有效count，不能将本次专项或旧两FAIL整体关闭。 |
| 真实端口 | occupied阶段已产生 **WSAEADDRINUSE /10048**；捕获数据库OperationalError家族后，FAIL于**DATABASE_GOLD** | 原生绑定没有把10013当占用，失败收敛到数据库诊断断言。该stage覆盖phase==database_connect、category==OperationalError及port不在安全command三条，实际失败哪条/子类型仍UNKNOWN。无网络构造已证明强fixture候选：ConnectionTimeout是OperationalError子类，pytest.raises接受，但固定精确typename白名单将其映射OTHER，硬编码base类断言失败。候选不能冒称实际native子类型。 |
| HTTP原失败 | 独立LF/CRLF×legacy500/current200四项 **PASS**，完整header/content/owned-thread-cleanup gold通过；S3全片345PASS/0FAIL/4SKIP | 原HTTP与新增CRLF的实际断言已通过，可确认ENG070完整canonical UTF8 fixture修复在本次Windows有效。生产API未改。 |
| 旧假errno98端口fixture | S2完整coverage，当前failed2只映射真实数据库分类与SESSIONowner，无未知失败；该fixture未再出现在FAIL | 不与真实产品端口问题混合。 |

## 四片与容量缺口：不能说7FAIL降为2FAIL

| shard | 实测counts | coverage / exit / cleanup | 耗时 |
| --- | --- | --- | --- |
| S1 | 317PASS /0FAIL /28SKIP =345 | true /0 /OWNED_TREE_STOPPED |187.843s|
| S2 |303PASS /2FAIL /22SKIP =327|true /1 /OWNED_TREE_STOPPED|223.828s|
| S3 |345PASS /0FAIL /4SKIP =349|true /0 /OWNED_TREE_STOPPED|283.734s|
| S4 |**NULL，未提供有效整片counts**（collect310）|**false /NULL /OWNED_TREE_STOPPED；TimeoutExpired/SHARD_ERROR**|381.047s|

965PASS/2FAIL/54SKIP、1021 seen只来自完整前三片，不能代表全1331或把旧7FAIL关为2。S4共享剩余预算被用尽，最后安全progress显示completed260/collected310/ordinal261、fixture CLIENT、call累计227907ms/setup119218ms等；这是progress而非有效JUnit counts，不反推出其余50PASS/FAIL/SKIP。source_bindingAVAILABLE与2339a4d一致。S4无Job/CONFIG逐项回归终态证明；二者有上述独立测量，分开记录。

Prepare34s SUCCESS；Lifecycle84s FAIL；固定观测17s FAIL；Validation1098s FAIL；Publish1s SUCCESS；Stop3s SUCCESS。native_lifecycle82.937s/exit1/timeoutFalse/TreeStopped；native_validation1096.562s/exit1/timeoutFalse/TreeStopped、原deadline1125s。外层未timeout，内层S4明确TimeoutExpired；不能以外层timeoutFalse否认预算缺口。

## 清理与停止边界

固定观测worker outer Job cleanup=OWNED_TREE_STOPPED、statusFAIL；生命周期/回归outer Job各TreeStopped，pg_status0、pg_stop0（1.703s）、summary_publish0，最后Stop步骤SUCCESS。**这些清理记录不能盖掉最小normal后代LIVE专项FAIL**。本轮无app_stop独立phase annotation，最终Stop SUCCESS不等同独立app_stop native PASS。首次Stop由Restart之前成功断言+STATE不存在路径推知（SOURCE_BOUND_INFERENCE）。

SERVICE_LOG新增owner事务已明确停在只读。完整同类最小对象/风险在[集中范围清单](ENG071-OwnerScopeDecisionInventory.md)：固定新log、STATE首次新建、STATE原子临时新inode；FILES只作为Windows未启用的独立候选。原ROOT保护与session/config首次创建授权保持，既有文件（含失败后空文件）不修复。本轮不夜间询问、不设置新增日志/STATE/FILES owner或既有ACL。

## 后续最小可实施方向（本轮未执行）

- owner：在SESSION/CONFIG首次创建范围内研究在CREATE_NEW时指定当前User owner的方案，避免事后owner变更使继承DACL/control重计算；仍需精确before/after验证，不能重写既有DACL或忽略变更。新增log/STATE/tmp需要集中明确额外对象授权。此为设计候选，未实现/执行。
- Job：在原5秒cleanup预算内持有本次创建及受控后代readonly精确句柄，固定观测innerJob membership与signal序列，区分归属与终止完成竞态；不用PID kill、breakaway、权限扩展、sleep放大或新deadline，不将ActiveProcesses0直接当全部kernel signal。
- PORT：固定输出三条gold分别bool和现有safe boundary_phase/category；若实际证明ConnectionTimeout，则只修明确子类型的fixture/固定安全映射，保持10013拒绝及10048占用。当前仅强候选；不放宽任意OTHER。
- 容量：本次新增观测消耗17秒，但S1/S2/S3本身亦较ENG069增加约8.6/25.3/41.3秒，不能把S4预算缺口全部归于观测。先实测fixture/阶段成本，原25min与共享截止保持，不自动优化重跑。

## 依据、审查与保留

本地85PASS/4nativeSKIP、真实loopback PORT+HTTP5PASS，projection poison拒绝；本地最小recipe为明确stub，不算native evidence。新增脚本及安全容量/异常捕获/阶段归因/cleanup独立NO_BLOCKERS，终态解读与对象清单再次独立复核。51测试+29实现共80个Git blob/raw/manifest SHA256一致，旧1323 stable keys保持、collection1331不是全量PASS。最后原始环境仍干净HEAD1aa81a2，原备份保留。

WinAPI仅用官方资料核对边界：正常job继承及终止覆盖层级见[Microsoft Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)和[TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)；[TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)区分异步请求与精确句柄等待，这使终止竞态成为候选，不能单凭它判定本例原因。owner flags规则见[SetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo)，未据文档执行额外DACL或privilege操作。

F1未签收/F2仅并行探索、Server非Win11，R4关闭，真实模型调用/预算0，无自动资格判断或外部履约。
