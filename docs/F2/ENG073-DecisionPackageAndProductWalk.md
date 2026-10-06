# ENG073 权限决策包与实际本地产品走查

基线 `5de3294be8c5d703ff251c0f744a907dc897d254`（精确HEAD以证据JSON为准）。本轮只做本地：原生owner入口保持暂停，不询问夜间确认，不修改任何Windows owner/ACL，不push/CI/部署/LIVE。现有源码没有新增产品功能；转向原V1产品§3、§5.5与F2-T03/T04/T06/T07的实际可用子集验证。

## 可决策的权限包：先区分观测与授权

最小只读方案只使用已存在且经过路径/对象身份核对的句柄；只请求读取现有OWNER/DACL所需访问，不请求WRITE_OWNER、WRITE_DAC、ACCESS_SYSTEM_SECURITY或提权。不创建目标、不调用setter、不调整继承、不递归修复、不更换API绕过暂停。

1. 在同一精确对象句柄上读取两次独立OWNER/DACL副本，验证读取可重复；复制有效数据后才释放各自SD，避免指针生命周期混用。这是无修改的baseline A/B，不能称owner修改前后验收。
2. 未来获准且已满足原严格合同的单次事务才有真实before/after；分别保留owner是否相同、NULL/empty DACL、有序完整ACE是否相同、ACL revision/容量/保留/slack差异及control XOR固定bit名。原始SID、ACE、mask、路径和异常文本留私有，不出报告。native读取使用官方IsValidAcl/GetAclInformation/GetAce等；结构比较不等于AccessCheck语义证明。
3. 原完整ACL字节及control（仅既有owner-defaulted例外）的保留断言不放宽。SACL内容未查询，报告NOT_QUERIED。实际ENG071的ACE/control具体差异与访问语义仍UNKNOWN；旧before/after私有数据未导出，本地mock不能还原它们。
4. 只读拒绝、无效对象、重解析/竞争或身份变化立即停止该对象的观测，结果UNAVAILABLE/UNKNOWN。审批对象范围也不能把未知权限语义改成PASS。

日后一次范围确认应列明以下对象及各自边界；本轮仅准备清单，**没有提出确认问题或自行批准**：

| 候选对象 | 精确范围 | 必須保持/未知风险 |
| --- | --- | --- |
| SERVICE_LOG | 首次独占创建的固定 `.runtime/windows-services.log` | 现有日志不得修复或覆盖；私有诊断、append共享与创建竞态需证明安全。ENG071实际该对象owner mismatch；授权范围不证明权限保持。 |
| PROCESS_RECORD初始 | 本次Start独占新建的固定 `.runtime/windows-processes.json` | 绑定数据在权限验收前不得写入；已有记录拒绝，不能借此修改其他身份数据。 |
| PROCESS_RECORD原子临时对象 | 本次自有记录使用的受限 `.process-binding-UUID.json`，核对原记录字节后原子替换 | 临时inode同样需验证，不能只改初始inode；目标竞态、遗留临时文件与替换后的合同均需验收，不授权任意path。 |
| FILES（独立未启用候选） | 首次创建的固定 `.runtime/files` 目录 | Windows当前未启用；目录继承/重解析与文件不同，需独立需求及授权，不含子树递归修复或文件生产派发。 |

SESSION/CONFIG原流程也保持暂停；失败残留文件不自动修复。ROOT原首次创建边界不扩张。完整源码路径盘点见[集中清单](ENG071-OwnerScopeDecisionInventory.md)。未知项仍未知，额外对象授权与原SESSION/CONFIG权限保持证明是不同决策。

## Job生产接线独立审查

新增未接线 `StopObservationAdapter` 只读候选按BEFORE_TERMINATE→AFTER_TERMINATE→ACCOUNTING_ZERO捕获membership/accounting/精确process signal，finish在关闭process/job之前。ACCOUNTING_ZERO实际读到非零拒绝；最后即使已signal也复查原截止。沿调用方原cleanup_started+5秒、最多8样本，逐读取gate；UNKNOWN/nonmember/缺stage/截止/采样耗尽均FAIL。成功只为EXACT_PROCESS_ONLY，不能投射TreeStopped。

独立审查指出两个生产阻断，均保留：当前`owned_job.py`的stop_tree在Terminate之后才局部建立5秒clock，且没有三个hook；run保留的是parent句柄，不能代替特定descendant。直接包裹原stop_tree会错过beforeTerm或引入第二budget。因此生产owned_job.py、CI均未改。将来若接线，需在唯一清理起点固定时钟并共享到原停止循环，显式传入事先合法持有且身份已核对的目标descendant句柄，无OpenPID/新权限/宽杀流程；读取调用自身若阻塞，Python gate不能抢占，整体耗时仍需原生验证。

测试通过实际pytest：owned_job模块65PASS/4nativeSKIP；相关shard/安全诊断/暂停SESSION模块133PASS/1nativeSKIP。fresh collection1371，四片345/345/349/332精确相等、ENG072旧keys全保留+17；collect不是全量PASS，原native S4缺口不改写。候选测试用注入Candidate.stop_tree替身模拟未来hook，覆盖primary0/17/timeout、signalLater/live/unknown/nonmember、原截止过期零读取、缺stage、zero-stage不等于零及finish超截止；记录close顺序thread→parent→job。它们不证明当前生产stop_tree接线或任何Windows进程已结束。原native descendantLIVE与S4未完整问题仍OPEN。

## 本轮实际产品走查

使用独立 `/tmp/parkweave-eng073-product-ytp_zhmu` 合成PostgreSQL/API/worker及本地Chromium/缓存agent-browser；运行既有脚本，不下载依赖、不访问外部业务或模型。API/worker正常停止，PostgreSQL STOPPED。

- 同一个Case `0b76ab4c-e429-4313-ace2-25d3522ed09b`：服务资料入口→两槽材料版本→专员人工核对→企业确认→资源页两资源预检/占位/组合确认→回同Case显式关联→专员内部offer→执行者本人accept及合成回执→企业ACK→本地重验关闭→重开→第二轮重验关闭→reload。三角色实际UI、未ACK禁止关闭、专员/执行者最小只读、跨企业隔离、脚本文本不执行和320/390无横向溢出断言通过。最后本地记录revision5/cycle2；真实Case WAITING_CONFIRMATION、目标仍未完成。
- **另一个独立Case** `33a8ff0e-27cc-4620-a881-c398405f7619`：固定四步计划P1-P4、缺assignment初始BLOCKED、观测撤权后的失效与恢复显式重验、reload、最小只读及320/390断言通过。计划revision8/8events，Case NEEDS_INPUT、目标仍未完成。不能拼成前一个Case全部经过计划测试。

首轮服务子进程过滤PYTHONPATH，已将其标为源码绑定不确定的历史观察；最终重跑通过临时工作目录包symlink明确绑定当前源码，最小子进程环境实际resolve api.py为当前targeted源码。两个脚本均重新exit0，证据以重跑Case及截图指纹为准。

两场景执行者的Run assignment均由fixture owner在UI外为本次新合成Run显式准备。产品UI不自动赋权；这是最短演示的实际前置/现有缺口。日期控件通过值和input事件填入，未测原生picker手势。主线程查看两张390截图：同Case返回四步计划入口可见、本地关闭仍明确目标未完成；计划说明不自动赋权及原目标未验。未做完整视觉签收。

[最短体验与未完清单](ENG073-QuickExperience.md)。固定证据：[JSON](evidence/eng073-decision-product-walk.json)。模型调用0/预算0；F1未签收、F2仅并行、R4关闭；Win11/native/完整36AT6EX NOT_RUN。本地通过不关闭Windows专项，也不证明资格、真实受理或履约。
