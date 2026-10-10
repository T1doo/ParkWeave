# P4 原本地报告到模拟企业核对：有限验收

运行候选 `fa80309a9cc728bd6e43a5f9c47d1cb317791df5`，开发基线 `f505a8e8c075bdb6671b83624cb4bea24ceaff4d`。先提交[有界写入与存储合同](P4ReceiptExecutionPreviewContract.md)及[112模板闭包](P4ReceiptPreviewSQLClosure.json)（a72a1131c70a148c3b190a19985631a6e0390793），再先冻结原ON CONFLICT所需临时唯一索引（4a2606550a5ffb62a926192a04e2347e9f23d18c）及进程发行证明恢复边界（ad4e68ae3b995182cff6ee8c4e67dfde6a04ebfc），后实现。冻结360个源码路径，manifest SHA256 `2fa97a17c06dd1b3965d4d2365b84cb3f670a4f47ee39bedc5f01392b51435d2`，1588个实际AST测试函数诊断ID；roles.sql保持SHA256 `604d084e12d84e9cad808ddd4a7e61289390faca49fd657d2ffe711b5a43afc3`。原F2/PR0产品映射、旧P1/P2/P3代码及证据不修改。

本轮实际原P1/P2/P3 ACCEPT留下AWAITING_RECEIPT前驱，P4实际调用原IsolatedLocalExecutor.generate及executor_receipts.command(ExecuteLocal)：生成原结构化接单一致性报告，再SUBMIT回执版本1。企业角色使用独立模拟身份、当前step revision和实际receipt hash，明确调用原ACKNOWLEDGE或REQUEST_CHANGES。实际事件为CREATE→SUBMIT→企业决定，revision为1/2/3，完整绑定同一隔离Case/Run/preparation、accepted offer/step、当前managed executor、执行ID、报告及回执hash；P3前驱快照保留。ACK为LOCAL_ACKNOWLEDGED；REQUEST_CHANGES保持CHANGES_REQUESTED、尚未核对，无自动重生成或ACK。输出是[ENG106](ENG106-LocalExecutionReceipt.md)定义的接单一致性元数据报告，不是材料服务交付、真实履约或真人批准；没有手填正文替代实际适配器。

28个专属pg_temp影子表，封闭代理仅允许112个精确SQL；run_assignments仅复制原临时唯一索引，不复制外键/触发器。原proof的数据库身份读取与原managed连接类型保留，封闭cursor/info不暴露DSN；未知SQL、public业务回退、commit、新连接及任意cursor操作均拒绝。原IsolatedRunAccessBridge在本轮临时0700 journal及影子表内实际执行模拟REQUEST/APPROVE，生成两条授权事件；原人没有批准，正式Grant或指派没有增加。使用已合法发行proof的原owner连接，两个原ALTER只作用于已有临时表，自有事务finally rollback/close，临时journal清理。运行时不安装正式schema，不补源权限、资格或适配器。

原owner READ/EXECUTE/PREPARE、双资源READ/HOLD、原获派专员READ/REVIEW_ASSIGNED、精确Run唯一executor READ、原当前managed租约及已显式启用原本地适配器仍共同限定本轮；当前资格先于历史和幂等。独立scope及不可变SQLite正文/proof绑定Case、资料revision、两槽ID/version/hash、请求revision、参与者资格generation、原动作/适配器版本、全部目标及企业决定。沿用0700根/0600库、128总记录/每Case16、正文与proof各64KiB、BEGIN EXCLUSIVE、三源CAS、同key幂等/异body409、并发及提交前重验。单改正文并重hash不能改变报告、回执关联、授权事件、actor、企业决定、outbox或全目标。旧P1/P2/P3文件整库字节不变，预演UUID不能由正式回执入口消费。源换版保留旧STALE历史，仅明确新预演重绑定；source_atomicity=false，不承诺全来源原子一致。

实际P3四条PENDING outbox保持未消费，notices为空；正式Case/分派/报告/回执/通知业务写入为零。独立HTTP/PG探针逐值比较全部public业务表（排除原authorization_audit诊断表），并验证正式public列、索引及权限集合不变、旧三库字节不变。影子ProjectionPending只意味着将被清理的私有journal局部提交，返回503而不冒充外层decision_committed；生成前失败原key为NOT_OBSERVED，外层提交后失响应原key为COMMITTED，均只GET核对，不再执行。

原页面增加本轮ACK/REQUEST_CHANGES选择、读取历史、原key只读核对与结束恢复。独立storage key仅五个不透明字段、8条/24小时，不保存token或材料正文；Case/身份/草稿变化及撤权403清私密视图并拒绝迟到回复。真实HTTP/PostgreSQL/SQLite/Chromium验证提交后失响应、页面reload仅GET、旧CHANGES_REQUESTED换版后仍精确保留且STALE、never-sent为NOT_OBSERVED/无自动POST、1200/390/320无横向溢出及隐私负例；完整必需/unsupported目标与P5未执行、Case未完成均展示。窄屏ACK及CHANGES截图实际视觉检查。

恢复范围明确有界：同一合法发行进程内重建Store/API/预览对象，重新附加原实际bridge及本地适配器，仅GET原key，已验证精确原产物与字节。真实独立新API PID没有原进程实际发行的FixtureDatabaseEvidence，当前GET返回403且保留旧字节，不重签/序列化proof、不补Grant；[根实际新PID证据](evidence/p4-receipt-execution-preview/root/new-process-proof-refusal.json)与独立复验均记录子PID已关闭。这是拒绝边界通过，完整跨新PID证明/lifecycle恢复仍未实现、未签收，不能将其描述为成功新进程恢复。

| 窗口 | 实际结果 | JUnit / 受控秒数 |
| --- | --- | --- |
| 根冻结22完整相关模块 | 576 PASS，0FAIL/ERROR/SKIP，自然0 | 410.030 / 411.926440 |
| 独立22完整相关模块 | 576 PASS，0FAIL/ERROR/SKIP，自然0 | 399.252 / 401.142164 |
| 独立自写真实HTTP/PG | 10 PASS，0FAIL/ERROR/SKIP，自然0 | 23.535 / 25.230063 |
| 独立自写原页面Chromium | 2 PASS，0FAIL/ERROR/SKIP，自然0 | 12.548 / 14.162310 |

22模块包含新增29个P4 API案例/7个页面案例及原P1/P2/P3、提交保护、规划/资料/权限/managed Run、资源、dispatch/notice/receipt及原isolated_local_execution回归。原本地模块REQUEST_CHANGES/REOPEN、明确新输出、旧hash/失效租约、手动降级拒绝等既有回归不表示本轮增加P5或签收完整AT14。独立探针自己运行实际HTTP/PG关系oracle、4类nested正文单改重hash409、原proof/provider撤销403、提交前后503、只GET冷对象/冷页面、正式schema/权限/旧字节，未借根结果。四个窗口分别保留，不将两次576相加或把独立三个窗口合成一次588。2条既有运行环境warning（anyio预导入与XDG_RUNTIME_DIR临时fallback）不算失败；未更改环境/网络配置来消除。

开发过程按[逐窗hash与分类](evidence/p4-receipt-execution-preview/development-windows.json)保全：dev01原adapter_ref缩写不匹配1FAIL；dev02临时journal文件名不符合原门1FAIL；dev03/05/06临时表缺原ON CONFLICT唯一索引各1FAIL；dev07/08/09混淆原资源receipt与新增P4 receipt的proof校验各1FAIL。8次产品失败观察对应4个原因，均先修复后冻结；dev04私有观察器漏conftest导入1ERROR。另一次编辑期py_compile语法失败修复后保留记录。dev10/11/12/13/14分别2/27/7/29/95PASS，全部是后续修改前的开发窗口，不转成冻结验收。失败原XML/log留私有.runtime并提供原hash，未公开token片段、未删除、改名或合并进最终PASS。

本次独审LIMITED_PASS仅签收合成P1–P4元数据预演；所有企业/专员/执行者与影子授权均模拟。完整跨新PIDproof恢复、P5、完整AT14、全仓、native Windows、真实材料服务交付、正式受理/可用容量/履约/Case完成均未签收，未新增PG重启或WAL验收。source_atomicity=false，SNAPSHOT_MATCH/STALE仅为快照比较；同权限管理员联改正文/proof/锚或截断数据库不在本轮防护声明内。不增加模型调用、真实业务、正式政策审批或外部通知消费者。旧Windows Job/accounting未推送修复留待以后重做，资料包导出不重做。

root唯一源码/Git写入者。候选普通推送后独立审查精确运行SHA，360路径前后零漂移、各自然窗口及自有资源关闭后才解除冻结，仅追加本安全证据文档，再普通推送候选、ff-only整合开发分支并核验实际远端。main、凭据/安全网络配置未改，未部署、未强推。

[独审原报告](evidence/p4-receipt-execution-preview/independent-report.json) SHA256 `fdbe784753d7e6fb3ecf3d99fa0b6518ef7b2abdf54068be4fc60cd112033c0b`；[根冻结结果](evidence/p4-receipt-execution-preview/root-frozen-audit.json)、[独立HTTP/PG探针](evidence/p4-receipt-execution-preview/independent/test_independent_api.py)、[独立原页面探针](evidence/p4-receipt-execution-preview/independent/test_independent_browser.py)、[320px旧CHANGES_REQUESTED/STALE画面](evidence/p4-receipt-execution-preview/independent/changes-stale-320.png)、[逐文件hash](evidence/p4-receipt-execution-preview/artifact-hashes.json)。报告原private路径与文件hash保留，公开副本通过逐字节比较并由最后的artifact-hashes重新锚定公开相对路径。
