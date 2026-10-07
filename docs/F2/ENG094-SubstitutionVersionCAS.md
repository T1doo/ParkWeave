# ENG094：明确替代确认的版本 CAS 与持久影响记录

基线 32bb929ffe194c5ccfdffc01a35c5a4ccd752631。本片把已有 T03 只读比较接入明确替代确认：用户读当前候选、写说明后确认，服务器重验比较指纹及原有关联规则。未比较的旧 resource-link 合同仍按既有权限/材料 revision/关联 revision/资源检查支持直接关联；新增 strict 路径和产品比较确认 UI 必须带指纹，不能据此宣称所有历史 API 都新增了预览 CAS。

## 严格确认与持久记录

GET 候选比较增加 comparison SHA、材料/关联 revision、can_confirm 和 blockers；SHA 不含易变 server_time，但包含当前 Case/Run/owner/tenant、原诉求/全部保存目标、材料实际内容指纹、目录/模板、计划 ID/revision/checked SHA及快照/invalidated_from、原关联与候选组合/成员/规则/source/authority/当前 READ-HOLD 授权/Case 归属、时段与当前占用峰值/失效原因。

新增 POST `/api/preparations/{id}/resource-plan-binding/confirm`，strict schema 必需 comparison SHA、组合 ID、预期材料/关联 revision 和说明，Idempotency-Key 沿现有校验。它复用 case_resources.bind 同一事务，不新建真实 Approval、ServicePlan、Grant、身份或替代访问。当前 READ/PREPARE/EXECUTE、owner/tenant、精确 Case/Run、所有既有资源 READ 与目标资源 HOLD 都先校验。

按既有顺序取得父事项、资源授权/规则、组合/成员、Case、计划锁后重算指纹，旧比较或 revision 不符拒绝。保留原 gate(...,1) 的材料/目标/目录/计划前置，再重算全部来源、权限与时效。末次比较只使用锁定的 gate 前计划版本来排除本事务自己对已失效下游 checkpoint 的 invalidated_from 观察；并发计划 revision、checked、模板或源变化没有被忽略。插入前再取数据库时钟重验预约时段，原确认和一组合一 Case 规则不降低。

目录表只有 SELECT 权限。初轮测试准确暴露 FOR SHARE 需要更宽权限的错误；已移除此行锁，不新增 Grant。首/末完整目录 CAS 可发现比较期间已可见的变化，但没有受支持目录发布者/协作锁协议时，无法保证与管理员外部目录写入完全线性化。这是明确剩余限制；正式发布、不可变 Release 和 Approval 合同仍未实现，不使用应用 advisory lock 冒称阻止管理员写入。

新确认的 before P1/P2来源和计划、after新关联/组合/规则/已有授权、comparison SHA、说明、具体 changes、P2/P3/P4 重验步骤及“不取消原预约/不赋权/不执行”标记，保存为既有不可变 case_resource_links.snapshot.binding_impact，和新关联/归属同事务提交。没有新表、DDL、迁移或角色改动；失败回滚不残留新 claim/关联/影响记录。历史元数据从资源 snapshot 差异比较中单独分离，GET impact_history 可追溯，不改写旧事实。

同 actor/key 同完整指纹的已提交回执，在当前授权重验后、旧 SHA 新鲜度检查前恢复；目标、目录、候选撤回或时段/来源后来变化不制造第二条关联。不同 body/Case 复用 key 冲突。恢复的是不可变旧 event，当前 source_status 独立检查；目录或占位来源变化后明确 NEEDS_RECHECK，历史确认不能沿用。后续对 P2 的合法重核或本事务产生的新关联，不被误判为资源来源变化。当前权限撤回仍先拒绝读取/重放。

## 产品用户流程

比较可确认的候选后填写说明并明确确认，旧预约保留。提交期间锁定候选、说明、诉求草稿和重复提交；即使程序触发选择事件也不能覆盖在途 body/key。网络未取得回执时清掉旧“当前比较”卡片，只保留相同 body/key 的重试入口，说明结果可能已提交，允许刷新检查历史。只读刷新后不把旧比较恢复为可确认状态。

409/422 清比较并要求重新读取；403 清整个私有计划。Case/身份/资料版本/代际变化丢弃旧响应。页面独立显示历史替代记录的来源 CURRENT 或 NEEDS_RECHECK，旧关联、选择说明、比较摘要和重新核对步骤，不把历史记录当批准或执行权。

真实隔离产品 PG/API/web 同一 Case：读候选 → 通过原 UI 撤回候选 → 旧比较提交 409 → 重新读另一候选 → 受控延迟 POST/改变候选/重复事件被挡住 → 服务器提交成功后受控丢回执 → 原 body/key 重试恢复且仅一条影响记录 → 明确取消替代 → 改目标 → 刷新恢复失效来源及历史。业务确认/取消/目标修改都是实际 UI/API 动作；故障注入只影响浏览器响应交付，不用假成功代替数据库提交。

## 验证与下一片

最终完整 Linux 回归 1692 通过 / 0 失败 / 0 错误 / 9 原生跳过 / 2 警告，396.82 秒；236 份冻结源码差异 0。新增隔离回归 51 通过 / 0 失败 / 0 错误 / 0 跳过，浏览器 1 通过 / 0 失败 / 0 跳过。初轮权限锁错误导致 25 失败 / 21 通过，移除无权锁并完成末 CAS 后最终重跑通过。源码冻结、隔离回归/JUnit、真实浏览器与桌面/390/320截图、权限与历史证明、独立审查见[证据](evidence/eng094-substitution-version-cas.json)。实现、测试和只读审查分别负责，测试进程用各自 UUID 数据库；原演示 PG 未启动，自有 API 已停止。

剩余是正式目录发布/不可变 Release 与管理员并发写者协议、正式 Approval/有效期/授权 epoch、完整 ServicePlan dependency_lock 与更广的变更影响图。下一片建议补“变更后按当前来源显式重新核对的持久检查记录与旧影响引用”，沿用现有 P1–P4 权限和核对动作，不自动取消或批准。

本片单独本地提交，不新增 push/CI/deploy/owner、安全配置或实际身份权限修改。F1 未签收、F2 并行探索，Server 非 Win11，R4 关闭，模型调用/预算 0，真实生产激活关闭，原环境与备份保留。
