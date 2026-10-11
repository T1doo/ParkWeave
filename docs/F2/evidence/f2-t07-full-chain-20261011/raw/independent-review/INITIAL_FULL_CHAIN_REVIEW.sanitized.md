独立静态结论：LIMITED_STATIC_REVIEW。本窗未运行PG、API、worker、Node或浏览器测试，没有新的PASS/FAIL计数，也不签F2-T07/AT35阶段通过。父任务声明续派基线为交付28f28328efb23f60cdfbbc51ae215cebd5261a08、源码796b41ad8939ba1d067f84f137a4d2a1861f06d4；本报告按实际读取文件SHA绑定，无独立Git操作。旧取消报告与原始证据未改。

原规格核对

已完整读取原分阶段计划§4及§10的AT01–35定义、原产品§5、§7、§8，并将docs/验收规格.json的35项原scenario/steps/oracle/initial/reset/status完整保存到机器映射。原F2准入仍要求F1真实模型、身份/Schema/账本和审核目录。原T07必须跨服务有可重放闭环、实际落库、刷新可读、权限正确、有效/错误新输入分开；不能靠手改数据库完成，不删必需目标。允许合成目录不推出真实园区或线下履约。

建议主fixture与真实路径

使用tests/conftest.py的自有UUID PostgreSQL，链式原preparation_fixture→receipt_fixture→link_fixture，在低权限parkweave_app的Store上启动生产create_app/uvicorn与独立python -m parkweave.worker。API新建Run/Case时先记录202/run_id，再读回真实SUCCEEDED/LOCAL_CASE_CREATED和唯一VERIFIED operation/Case；禁止直接调用store.finish/claim冒称实际CLI worker。每个新输入生成独立Run/Case/资料/计划/资源/接单/回执，不能复制已有成功成果。

A组零Run/Case初态只经普通API/CLI worker推进，记录新Run无assignment、executor catalog空、Run access默认403，保持权限阻断。B组使用原固定合成scope的显式测试owner setup为精确新Run准备原executor READ assignment；随后业务仅走生产API/worker。这条前提写入不算企业业务API或无setup新企业授权。禁止附加IsolatedRunAccessBridge/IsolatedPlanApproval/IsolatedLocalExecutor/模板消费桥来使普通路径通过。原fresh_chain虽有真实HTTP/PG，其模板/访问/Approval/软件报告仍为隔离合同且建单直接claim/finish，不能转签本片。

setup权限须单列

自有PG CREATE DATABASE/creation receipt、migrate、CREATE ROLE/表权限、seed假会话/企业READ/EXECUTE/actions、专员PREPARE/REVIEW_ASSIGNED、合成资源及READ/HOLD、假执行者READ均为测试环境准备。原link_fixture seed是真实假目录初始化，不是生产服务注册。B中新Run assignment属于owner-only synthetic setup，精确记录主体/Run/scope、前后权限快照和新增assignment，不能写“业务自动分派赋权”。不重激活撤权、不复用其他Run assignment、不改生产Grant/信任登记。当前普通api.access_bridge/approval_candidate都默认拒绝；无现成权限不扩大。

推荐B组业务顺序

1. 两已有合成企业scope分别提交全新目标，真实worker完成建单；重启worker读回无重复效果。
2. 创建资料、专员REQUEST_CHANGES、企业提交不同双槽新材料；明确保存5个LOCAL必需目标、重新REVIEW/CONFIRM，采用当前注册P1–P5计划。所有来源/修订/原key/CAS由API读回。
3. 明确VERIFY P1；分别预检并占位2个不同合成资源，原同事务组合确认并关联当前Case，再VERIFY P2。选用普通两资源路径，无Approval桥；3–8 resource-delivery的独立Approval未启用不是应绕过的缺陷。
4. 获派专员OFFER、本人执行者ACCEPT生成当前receipt step；真实worker消费站内通知，由原收件人OPEN/READ，核当前Case/offer，不将送达/已读计履约；VERIFY P3。
5. 执行者人工SUBMIT，企业REQUEST_CHANGES，执行者新的正文/版本SUBMIT，企业精确当前hash ACK；VERIFY P4。goal-results应显示MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT，execution_id=null；原SUBMIT权限禁止不能弱化。
6. owner明确REVALIDATE，VERIFY P5；goal-results当前5项LOCAL_OUTPUT_VERIFIED。CLOSE_LOCAL_RECORD后Case仍WAITING_CONFIRMATION，本地状态CLOSED；因为P5指纹包含整个ledger，旧P5必须失效，再明确VERIFY P5并核当前结果。REOPEN产生新cycle清旧验证，应先REVALIDATE→P5VERIFY，旧回执/资源/材料和历史核验保留。不能自动重绑/隐式VERIFY。
7. 新HTTP API进程/普通冷Store读取原Case/回执/计划/goal-results及原key恢复，不能重跑migrate/seed或把冷GET当业务修复。同scope第三份有效新输入完整重复，首Case全行与历史保留；错误输入和跨企业/园区拒绝独立核对。

P5与人工核验静态结论

case_lifecycle的REVALIDATE/CLOSE只gate through=4，所以P5依赖本地重验不构成必须先P5再重验的循环。source P5包含整个local_lifecycles记录，关闭改变state/revision，因此关闭前P5核验不会自动保持当前；需要真实反例确认关闭后原VERIFY可完成。原test_case_goal_results的完整五目标测试已明确manual ACK、2个receipt版本与冷Store只读核验合同；本窗只读其代码，未转报旧测试PASS。原goals仅承诺LOCAL产物，不应加入REAL_EXTERNAL_FULFILLMENT后删目标使通过。

必要独立反例

- A无assignment阶段禁止OFFER/legacy CREATE/跨Run授权复用，无任何权限修复副作用。
- B采用计划后再改assignment，应明确local_revision ADOPT/CAS而非自动rebind；或在adoption前单列setup并保持中途不写权限。
- 越序P2/dispatch/SUBMIT/关闭分别被实际gate拒绝；有文本未ACK不能VERIFY P4或关闭；owner/专员/执行者不能代对方操作。
- CLOSE后P5变陈旧→显式VERIFY，REOPEN后旧P5不得复活；当前goal-results GET保持全部业务行不变。active service-case-plan GET可能观察并持久失效元数据，不能把所有GET概称纯读；CANCELLED/RECONCILING观察写必须继续禁用。
- 换材料/目录/容量，未受影响P1正文/锁/ID保留；影响锁明确UNLOCK→局部ADOPT→重验，历史receipt/read保留，旧页面ACK/VERIFY/source SHA拒绝。
- 最后容量真实PG竞争，同key同参仅一效果、异参冲突；过期占位在worker停止仍拒绝，建议与确认之间被抢仍冲突，确认后TTL不自然释放。
- 原key丢响应先只GET核对，有/无观察均不能自动补POST；旧事件与当前状态分列，跨action/Case/key冲突。
- 普通取消前接单/接单未回执/已有人工回执核对三个旧边界作为不同Case有限负例，预约继续占容量直到独立受权释放；不延长新的取消状态。
- 专员/执行者最小返回，跨企业/园区guess ID、撤READ/PREPARE/EXECUTE/assignment、旧通知/迟到UI都按当前后端权限重核，不返私密正文。
- CLI worker exit0必须同时保存run/operation/case实际状态及完整stderr/stdout，默认足够lease，不复用1秒负载敏感窗口；旧Case0根因仍UNCONFIRMED。

AT01–35有限映射（原整项状态全部NOT_RUN）

| 原ID | 本片可核子条件 | 具体源码入口 | 范围及未完成 |
| --- | --- | --- | --- |
| AT-01 Windows原生启动 | F1前置；本片Linux不能签原生 | `scripts/windows/lifecycle.py`, `scripts/linux_fixture_server.py`, `tests/test_foundation.py` | 真实Win11安装/停启仍NOT_RUN |
| AT-02 书生真实工具闭环 | 模型前置；本片不调用模型 | `src/parkweave/model_chain.py`, `src/parkweave/bounded_planning.py` | 当前规划为确定性注册闭包，非书生真实理解/修订 |
| AT-03 恶意规格与注入拒绝 | 链上错误输入/越界动作负例 | `src/parkweave/domain.py`, `src/parkweave/bounded_planning.py`, `tests/test_v1_contracts.py` | 结构拒绝和零副作用；不加载新工具 |
| AT-04 跨企业/园区隔离 | 必测不同企业/园区各入口隔离 | `src/parkweave/store.py`, `src/parkweave/preparation.py`, `src/parkweave/executor_receipts.py` | Case/材料/资源用途/回执/通知/结果均不可泄露；固定合成主体范围 |
| AT-05 文件和凭证边界 | 文本和日志边界；浏览器不执行 | `src/parkweave/web.html`, `src/parkweave/store.py`, `tests/test_authorization_files.py` | 输出转义及日志脱敏；原生根/ACL/全部导入下载仍未验 |
| AT-06 事实冲突与必要澄清 | 保留来源/未知/用途核对 | `src/parkweave/case_fact_clarifications.py`, `src/parkweave/preparation.py` | 有限事实合同不能称通用事实抽取；缺值不是不符合 |
| AT-07 复合目标服务编排 | 五LOCAL目标明确保存/计划采用 | `src/parkweave/request_intents.py`, `src/parkweave/bounded_planning.py`, `src/parkweave/service_case_steps.py` | 必需目标不删除；UNKNOWN/UNSUPPORTED保持；未验证真实模型/任意服务DAG |
| AT-08 模板新输入与冷会话 | 同已有scope新输入/独立新Case与错误输入 | `tests/test_new_enterprise_local_chain.py`, `src/parkweave/template_consumer.py` | 隔离模板候选是另一合同；普通入口无正式模板挂载/发布权 |
| AT-09 本地组合资源确认 | 普通两资源全事务确认/Case关联 | `src/parkweave/resource_combinations.py`, `src/parkweave/case_resources.py` | 已确认占用与关联分开；失败不部分确认；3–8交付Approval普通入口未启用 |
| AT-10 并发最后名额 | 最后容量与同键/异参并发反例 | `src/parkweave/resource_holds.py`, `src/parkweave/resource_combinations.py`, `tests/test_resource_combinations.py` | 真实PG锁/容量；不从线程数推断效果数 |
| AT-11 陈旧批准与过期占位 | 清理停止仍拒过期占位/陈旧来源 | `src/parkweave/resource_holds.py`, `src/parkweave/resource_plan_binding.py`, `src/parkweave/service_plan_approval.py` | 数据库最后时点复读；普通无Approval桥，不能据旧隔离成绩称正式批准通过 |
| AT-12 多人协同最小权限 | 专员OFFER/执行者ACCEPT+SUBMIT/owner ACK | `src/parkweave/service_dispatches.py`, `src/parkweave/executor_receipts.py` | 固定READ assignment是setup前置；不得越级或读取企业全部材料 |
| AT-13 Case与Run成功分离 | 每阶段明确Run/Case/本地状态 | `src/parkweave/store.py`, `src/parkweave/case_lifecycle.py`, `src/parkweave/case_goal_results.py` | SUCCEEDED只LOCAL_CASE_CREATED；LOCAL_OUTPUTS_VERIFIED/LOCAL_RECORD_CLOSED不等于FULFILLED |
| AT-14 预览与真实数据隔离 | 预览与业务写快照对照 | `src/parkweave/bounded_planning.py`, `src/parkweave/isolated_execution_preview.py` | 普通planning-preview不执行，不能替代执行预览命名空间全量验收 |
| AT-15 履约核验与重开 | 缺ACK关闭拒绝/REVALIDATE/本地关闭重开 | `src/parkweave/case_lifecycle.py`, `tests/test_case_lifecycle.py` | 仅本地合成记录；真实履约证据/正式FULFILLED仍缺 |
| AT-16 outbox与消息去重 | 实际worker消费通知/outbox并重启 | `src/parkweave/store.py`, `src/parkweave/dispatch_notices.py`, `src/parkweave/worker.py` | 保存业务事件/通知意图及唯一收件事实；OPEN/READ与履约分开 |
| AT-17 worker失联与旧worker回报 | 建单worker独立进程/自然失联接管可分窗 | `src/parkweave/lease.py`, `src/parkweave/gateway.py`, `tests/test_worker_gateway.py` | 不从worker exit0推出Case创建；必须读operation/run/case，保留旧Case0未知根因 |
| AT-18 暂停取消在途动作 | 沿三片已有取消边界验证冻结与历史 | `src/parkweave/case_cancellation.py`, `src/parkweave/case_cancellation_before_receipt.py`, `src/parkweave/case_cancellation_reconciliation.py` | Run取消与Case取消不同；只覆盖已审有限普通人工片；资源独立释放 |
| AT-19 撤权与缓存 | 撤权/旧键/冷GET/通知重读负例 | `src/parkweave/store.py`, `src/parkweave/preparation.py`, `src/parkweave/dispatch_notices.py` | 当前权限先于回放，历史授权读取保留；缓存已取副本不能收回 |
| AT-20 外部结果不明工程测试 | 本地丢响应原key只读核对；故障适配器另标 | `src/parkweave/gateway.py`, `src/parkweave/receipt_history_recovery.py` | 无外部调用；FAULT_INJECTION不计真实接入；不盲重发未知效果 |
| AT-21 准备度三值 | 现有三值表/材料缺口 | `src/parkweave/readiness.py`, `tests/test_foundation.py` | 纯合成目录资格NOT_EVALUATED；不能给官方审批结论 |
| AT-22 地区日期与规则版本 | 来源版本改变/历史按原版本留存 | `src/parkweave/catalog_publication.py`, `src/parkweave/preparation.py` | 合成目录版本不证明真实地区/正式政策适用 |
| AT-23 材料清单与不伪造 | 独立双槽新材料/补正/REVIEW/CONFIRM | `src/parkweave/material_corrections.py`, `src/parkweave/material_preparation_drafts.py`, `src/parkweave/material_objections.py` | 来源未核实留UNVERIFIED；不造资质/签章；材料齐全不等批准 |
| AT-24 机会提示作用域和去重 | 同Case原机会/手动刷新/站内通知去重 | `src/parkweave/case_opportunities.py`, `src/parkweave/dispatch_notices.py` | 受控有权合成来源，不外发/不宣称关机仍后台在线 |
| AT-25 依赖失效与未知扩大重验 | 版本/材料/容量改变实际影响与明确局部修订 | `src/parkweave/registered_dependencies.py`, `src/parkweave/service_case_steps.py`, `tests/test_registered_local_revision.py` | 稳定ID/正文/未受影响项保留，未知扩本Case重验，不自动重绑定 |
| AT-26 人工锁与历史事实 | 人工锁冲突/历史回执保留 | `tests/test_service_plan_manual_lock.py`, `src/parkweave/service_case_steps.py` | 被影响锁须显式UNLOCK，核验无权覆盖原决定 |
| AT-27 定义升级与业务数据 | 既有模板升级/原业务不回滚 | `src/parkweave/template_upgrade.py`, `src/parkweave/store.py` | 无本片生产迁移/发布；逐实例选择不等正式Release已部署 |
| AT-28 资源状态新鲜度 | 资源来源/更新时间/容量与确认回读 | `src/parkweave/resource_holds.py`, `src/parkweave/resource_holds.py` | SYNTHETIC LOCAL_AUTHORITY仅本地容量，不称真实房间/设备预约 |
| AT-29 时间与办理期限 | UTC/[start,end)/双缓冲/DB过期 | `src/parkweave/resource_holds.py`, `src/parkweave/handling_deadline.py` | 正式日历/SLA/合法业务停表仍NOT_RUN；无源UNKNOWN/非法暂停拒绝 |
| AT-30 限流截断与全成本 | 模型0调用与既有预算门保留 | `src/parkweave/quota.py`, `src/parkweave/model_chain.py` | 不启用真实账号；本片不能签真实限流/usage成本验收 |
| AT-31 公平对照与验收不降低 | 失败原件/oracle版本/范围不降低 | `scripts/run_acceptance.py`, `docs/验收规格.json` | B0/B1/B2真实公平对照未运行；工程局部不转整项AT PASS |
| AT-32 数据来源与效果声明 | 数据源和效果声明贯穿机器报告 | `docs/sources/V1/平台产品设计 (2).md`, `docs/F2/PR0-CurrentGaps.md` | 仅合成/人工驱动；无真实园区试点/线下履约/AI代办声明 |
| AT-33 第二园区配置迁移 | fixture-c跨园区隔离负例 | `tests/conftest.py`, `tests/test_authorization_files.py` | 不等第二园区A/B/C配置迁移、成本及新授权验收 |
| AT-34 干净Windows复现与关机边界 | 普通API/worker进程冷启读回可验 | `tests/test_full_process_record_recovery.py`, `tests/normal_recovery_process.py` | 旧helper含browser，不能直接跑；Linux进程重启不替代干净Win11/关机边界 |
| AT-35 首个完整办理和重新使用 | A真实权限阻断+B已有setup普通生产API手工完整链/再次新输入 | `tests/test_service_case_steps.py`, `tests/test_case_goal_results.py`, `tests/test_case_lifecycle.py` | B只有限合成授权前提链；不能签无setup正式AT35或PR0-alpha/F2阶段门 |

证据与风险口径

新B链可以证明“明确合成主体既有权限前提下的普通本地人工闭环”；A实际权限缺口必须标BLOCKED，不包装为正式生产首用或AT35 PASS。原ATBindings多F2 selector仍为空，现run_acceptance保守保持whole_AT_EX NOT_RUN；建议另建本片有限ID/原AT引用/路径/真实mode/actor/setup/初态/hash/每步状态/操作key/独立oracle/重置清单，不将旧工程数量累加成本片PASS。模型0、浏览器0、无真实回执/园区上线/外部授权，不签完整F2/PR0-alpha/F1/Win11。现normal_recovery_process helper含Chromium launch，当前不运行该原helper；可单独复用普通API/worker冷启思路，禁止换URL/工具绕过历史浏览器拒绝。

本窗仅写本独审runtime三个新报告，未改任何产品、tests、docs、Git或旧取消原件。输入逐文件hash与原35项oracle见initial-full-chain-review.json及reviewed-inputs-manifest.json；未发现已实际复现的新产品缺陷。上述P5、冷GET、完整普通manual链均为后续真实验收点，不能从静态检查预签PASS。
