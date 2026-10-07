# Case事实用途模块接线核对

原冻结模块提交：`8d9e881f1d64042d6a7dfedf0d96c00e943c7a08`（保持不变）；模块修复顺序：`f3a90a6999bb8d75f509b7c91ea5f0e60ea49f3e`→`bcb9a2fb8ef6edd6844db1910f3800f7c507f2c6`；原合同：`686f3e1f93eed03a31915df5eac6b99da3ad7f0a`。本支持分支不修改模块、Store、API、UI、迁移或旧测试。本支持包原轮次探测基线未挂载路由；主线集成检查点`5f11ae96007f2e9f07e0c571b7e0da90f6aa6dab`已包含适配和失败回传。本文及工具不表示主线新迁移接线已经通过。

## 具体调用与锁顺序

1. API校验UUID、Declare/Confirm及原Idempotency-Key，取当前Bearer后调用 `read/declare/confirm(store, token, preparation_id, ...)`。模块自身有事务，禁止外层先打开另一事务并持有parent再调用它们。READ字段撤回时专用GET拒绝；WRITE字段撤回但READ仍在时可读历史且当前门STALE。整体owner READ/PREPARE/EXECUTE和精确Case/Run/action范围仍要成立。
2. 原业务命令在**同一事务**完成当前角色授权、锁完整当前preparation，再调用 `gate(store,c,parent)`；此parent必须是DB完整行，不能是移除了私有字段的HTTP投影。检查 `satisfied` 后才进行新业务写入。parent至少持有FOR SHARE（新业务通常FOR UPDATE）；owner共享授权锁和稳定字段锁一直保留到该事务结束，不能拿第一次GET检查替代COMMIT所在事务检查。
3. `source_descriptor(store,c,parent)`也调用gate。返回的hash只表示当前来源描述，并不表示条件通过。将enabled Case的descriptor加入材料快照/审核、readiness、`er.material_current`、`life._sources(MATERIAL_REVIEW)`、`cp.binding_p1`及下游源绑定。未声明legacy Case不要加入新绑定或改变旧hash。
4. 模块新声明/确认的锁顺序为：当前actor共享授权锁→原actor-key锁→parent行锁→稳定排序的三个field锁→原plan失效→原prep.event。主线不得先持有plan行锁再反向取parent；授权等待后重验时效，事务中来源锁须与原Store.save_fact使用同一命名空间。
5. 主线升级Store版本门至25并注册package-data/迁移；025仅允许有本次集群/数据库创建证据的候选fixture；新UUID和固定parkweave名称均须真实owner、集群、OID及同事务票据匹配。无票据拒绝，不能按库名/环境/GUC自动启用。generic preparation的单项、列表、待办、计划源投影及事件对所有角色移除私有事实账本/源值。只能owner专用GET在当前字段READ下提供完整历史。

## 错误与历史映射

| 场景 | 必须观察的结果 |
| --- | --- |
| 无Bearer | 401 |
| 当前主体/Case/字段READ或写授权不满足 | 403，私有账本不回显 |
| 非法字段、重复choices、actor/org/verified伪造、请求键不合法 | 422 |
| 双CAS/来源SHA变更、结果不满足的当前事实业务门 | 409，无新业务效果 |
| 锁等待超时 | 确定非2xx；建议按既有bounded映射409，可保留原键重试；不要让成功响应掩盖超时 |
| 旧合法key/body | `HISTORICAL_COMMITTED_EVENT`与`current_decision_restored=false`；其public_status是历史快照，不是当前权威 |
| 模块路由不存在 | BLOCKED/404，不算权限拒绝或集成通过 |

合同没固定declare/confirm成功码，工具接受200或201；主线应统一API/前端期待。历史回复需要重新GET当前状态，不能把其中旧CURRENT喂回新UI。确认响应的顶层revision/state是**preparation**；用途revision/state在public_status；专用GET的revision是**用途账本**，preparation_revision单列。不要混用两个CAS。

source_sha256不含动态clock：源新增/真实内容漂移/request变化、实际依赖的授权行修订变化都会改变SHA。三字段READ/WRITE六行及capability READ/EXECUTE两行以稳定范围、active、revision、有效期绑定；恢复同一行的新revision不能复活旧CURRENT。仅时间到期可在SHA不变时令门STALE。无revision的action/preparation授权不承诺不可观测的管理员往返世代。观察GET不增加版本、不改旧事件。旧历史恢复也不增加版本；新显式确认同时增加用途及preparation版本，清review_sha256，置IN_PREPARATION。

## 黑盒验收与假阳性

[`scripts/case_fact_integration_contract.py`](../../scripts/case_fact_integration_contract.py)直接使用主线现有TestClient和已授权合成会话；没有DB/DSN、身份setup、Grant或路由注入。默认CLI只打印**待执行清单**：

```bash
.venv/bin/python scripts/case_fact_integration_contract.py
.venv/bin/python -m pytest -q tests/test_case_fact_integration_contract_support.py
```

第二条验证工具自身的漏检防护。模拟HTTP数据只测试断言器，不计为产品集成PASS。

主线pytest可直接导入`FactAPI`、`Request`、`capture_eligibility`、`verify_refusals`、`assert_observed_invalidation`、`assert_recovery_generation`。会话和完整HTTP响应只保存在测试内存，不打印；错误消息只有检查名及状态码。私有marker须使用唯一合成事实正文/断言UUID，应覆盖所有竞争来源，不能只覆盖已选择来源；不能用“地区”、数字等公共短值。工具同时拒绝sources/choices/source_ref/source_excerpt/evidence_id等私有结构键。

- `FactAPI.mount_probe()`只读，404返回BLOCKED；200仅表示路由已响应，绝不直接给集成PASS。
- `exercise_fact_roundtrip(...)`走原事实/用途HTTP，并借主线回调完成已有原流程。当前Case必须未声明，selected_ids是三份已有真实合成断言，回调`add_competitor()`必须调用原POST `/api/facts`，不是直接改模块/数据库。`prepare_before_change(api,event)`由主线复用已有原审核/办理API操作。工具检验generic owner/专员/列表/待办脱敏、源变化STALE、历史重试零写、新确认双版本、原CONFIRM不能跳REVIEW。返回明确标注完整恢复仍须调用方执行。
- `capture_eligibility(client,request,get_path,predecessor_path)`须在变化**之前**读取原API；工具强制绑定原GET/POST路径、同preparation及Case/Run前驱，保存当前允许动作、精确版本/hash及已核验前驱；变化后`verify_refusals`检验409和独立business oracle无变化。oracle须包含实际受影响业务行/事件、资源占用、receipt与cycle；可单独允许拒绝审计及明确的失效观察元数据，不可仅比较总行数或排除所有plan/parent字段。
- `verify_refusals`默认要求四个不同原门：P1_VERIFY、NEW_OFFER、OLD_SUBMIT、P5_CLOSE。可以为明确的单阶段测试传`expected_checks=('P1_VERIFY',)`；不能将子集报告为四门通过。工具先校验全部前态，缺证据则不发新写请求。

四个可办理前态**不能同时存在于一个已关闭Case**：普通OFFER在已有接单回执时可能本来就409；旧SUBMIT在LOCAL_ACKNOWLEDGED后本来就409；CLOSE在已关闭时也本来不允许。不能把这些天然409当作事实门的证据。为每个门使用其真实可办理阶段或独立新UUID负例，逐项标明Case/阶段；完整恢复闭环另用同一Case验证，不把多Case负例拼成新闭环。

| 原门 | 变化前必须保存的真实GET证据 | 变化后的原命令 |
| --- | --- | --- |
| P1_VERIFY | service-case-plan当前P1含VERIFY、step/revision/source SHA匹配 | `/api/preparations/{id}/service-case-plan/commands`，VERIFY |
| NEW_OFFER | dispatch catalog.ready、合法executor与prep/dispatch revision；P1/P2 VERIFIED；恢复OFFER还须精确旧step | `/api/preparations/{id}/dispatch` |
| OLD_SUBMIT | 原当前step为AWAITING_RECEIPT或CHANGES_REQUESTED，dependency CURRENT、revision匹配；P1/P2/P3 VERIFIED | `/api/executor-receipts/{step}/commands`，SUBMIT |
| P5_CLOSE | local-case.can_close_local_record，cycle/revision/current snapshot SHA匹配；P1–P4 VERIFIED | `/api/preparations/{id}/local-case/commands`，CLOSE_LOCAL_RECORD |

`assert_observed_invalidation`可供主线的原API source/request变化、已批准fixture到期/撤权测试复用。READ撤回后GET应403，不能继续拿私有GET读取STALE；WRITE撤回且READ保留才可读STALE历史。撤权只在主线现有合成fixture中操作，不为本工具创建或恢复授权。再确认后用原REVIEW/CONFIRM、资源重绑、P1/P2、同原执行者recovery offer（旧step ID）、本人ACCEPT、P3、新receipt v1 SUBMIT/ACK、P4及本地REOPEN/REVALIDATE/CLOSE/P5；`assert_recovery_generation`核对原GET的新旧世代、相同Case/Run/执行者、receipt.step_id以及最终原Case/Run的WAITING_CONFIRMATION，旧资料/offer/receipt/cycle/authority由主线独立oracle比对保留。

未运行主线已接线产品、完整恢复、浏览器、全量工程或Windows；模板/资格/外部履约及正式AT状态不升级。原8d9e881三文件在本支持分支保持逐字不变；修订由独立模块分支提供。

本支持交付自测：12项通过（工具自身、含假阳性负例），1条现有TestClient依赖弃用警告。冻结8d9e881应用的真实TestClient只读探测得到404/BLOCKED；connect哨兵禁止DB调用，未创建会话或权限。证据为环境内`/tmp/parkweave-integration-support-final.log`、对应JUnit XML及`/tmp/parkweave-integration-baseline-probe.json`。独立只读审查发现的四项假阳性缺口已修正并复审通过。

## 新迁移接线顺序（由主线执行）

在已有fixture本次initdb/start之后、第一次CREATE DATABASE之前，调用并保留`capture_fixture_cluster(maintenance_dsn, actual_owned_data_directory)`。成功创建新数据库后，在目标owner连接调用`cluster.record_created_database(connection)`并保留receipt。主线将receipt通过显式参数/context交给原Store loader，在它**同一owner连接、同一非autocommit事务**执行025之前调用`receipt.authorize_migration(connection)`。票据提交/回滚即消失，重复迁移须重新发票据；不可在另一连接预先发票据。

此入口核对新空本地临时集群实际system identifier/data directory/start/owner、目标创建前不存在/创建后OID、真实表owner及backend/transaction。仅库名、owner、pytest环境变量或自填GUC均不足以启用。它防误用，不宣称抵抗可直接执行DDL的owner。原生已安装集群没有本次新临时集群证据时拒绝；如需支持另须受审的创建凭据适配，禁止补Grant或绕过。

同步自测仍12项通过；WRITE_REVOKED/AUTHORITY_REVISION现在要求稳定SHA改变，EXPIRED保持不变。模块修复全套66项通过；主线20项API验证使用授权修复和主线原UUID迁移入口，新票据Store接线与完整工程尚待主线验证，不拼成完整验收通过。
