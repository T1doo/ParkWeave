# ENG097 逐项材料补正与新 Case 办理

基线 `cc4a46b0823fc1dfa8e5af5adf5d08d9700d780b`。对照原 V1 和验收的当前能力矩阵见 [范围核对](ENG097-V1ScopeAndNextSlice.md)；Windows 原生全量的实际失败、可修工程项和最小权限前置见 [Windows 阻塞](ENG097-WindowsFullAcceptanceBlockers.md)。原42项验收状态仍为 NOT_RUN，工程回归数量不是 F1/F2 或 AT08/AT35 的签收。

本片选择 F2-T01/T04 的逐项资料补正闭环。已审核参数模板复用仍缺正式模板发布合同与新 Run 协作访问准备；本片不启用发布、审批、Grant 或 assignment，也不将固定工程模板称正式审核模板。两个企业在冷会话中创建各自的新 Case，只验证现有合成资料合同的新输入与隔离，不声称企业入驻、模板复用或完整跨服务履约。

## 持久合同与真实门禁

`migration-023.sql` 在原 preparations 表增加 `material_corrections` JSONB。schema23 和包清单已更新；迁移仅在隔离测试数据库应用，生产部署尚未确认。roles.sql、schema.sql 基础权限与 workflow 不变，无新增 GRANT/ACL/身份/凭据。

原 `POST /api/preparations/{id}/commands` 的 `REQUEST_CHANGES` 可选 `correction_slots`，仅接受已有诉求摘要与材料目录两个槽位的非空去重选择，其他命令携带此字段拒绝。旧命令无此字段时保留原 fingerprint/幂等合同，不推断历史文本对应哪个槽位。每个请求和目标有稳定 UUID，保存要求时的材料版本、来源字节 hash、请求者和理由，最多16组；提交历史和当时人工核对来源保留。应用合同保存历史，不是数据库 INSERT-only 不可变账本。

企业必须通过原 ADD_EVIDENCE 提交属于此 Case 的实际新版本。来源 actor、version、digest 与实际记录精确匹配，才表示已提交待核对；理由或按钮点击不能完成补正。原 REVIEW 检查全部尚未解决目标的新材料，同事务保存人工核对与原资料状态。未解决目标继续阻止 CONFIRM，包括 row state/hash 被错误标记为已核对的反例。重新要求同槽补正会保留旧请求并明确 supersede；另一槽的尚未解决要求仍保留，不能靠改选槽位消失。

`GET /api/preparations/{id}/material-corrections` 只给此 Case 企业 owner 和获派专员；企业执行者、其他企业/园区/项目均拒绝。通用 preparation GET 剥离内部 ledger。GET 只读，不持久化失效标记。新版材料或资料重开使旧 resolution 不适用：区分实际目标来源变化与核对状态变化，显示历史而不是当前通过；当时的来源版本和人工决定不改写。

## 产品界面与未知结果

专员在原人工决定入口选择具体槽位、说明理由；企业看见待补槽位及旧/当前版本、来源、稳定编号和历史，提交自己的新版资料。随后专员核对、企业确认，真实 Case 仍 NEEDS_INPUT，资格未判定、外部未受理、线下履约无证据。

提交中禁用原命令与刷新；响应丢失时保留本页面同 Case 的原 body/key，未知结果按钮只重放原请求。同 Case 刷新不替换原参数；切身份/Case/工作区清私有上下文，不跨身份恢复旧请求键。409/422 清当前核验来源，必须刷新；403 清私有事项。迟到响应按身份、Case 和 generation 拒绝。独立审查发现提交来源展示使用错误 hash 字段，已改为实际 `source_sha256`，不保留 `undefined` 展示。

## 验证与剩余范围

最终专项为33项新补正测试加35项既有资料兼容测试，共68PASS/0FAIL，20.25秒；隔离 UUID PostgreSQL 和实际 API 验证。包括两企业独立新 Case/材料、同企业两项目、双槽部分补交门禁、单槽替代仍保留另一槽、旧键恢复/不同 body 冲突、当前权限与撤权、并发和事务故障回滚；来源与核对状态失效反例保留。

实际浏览器、最终完整回归、源码冻结和同步终态在 [机器证据](evidence/eng097-material-corrections.json)。浏览器准备过程失败及修复按各次输入/源码范围保留，不把失败的尝试改写成通过。

Windows 全量工程修复仅更新原四片 manifest 的完整文件集合、实际 collection、raw hashes 和 diagnostic allowlist 引用；保留预算、历史结果、安全拒绝和现有 isolated Job workflow。原生 owner/DACL/control 保持、日志/进程记录首次新建对象范围、历史 normal 后代和 S4 有效整片仍阻塞；不重试被拒日志、不启用暂停 owner、不恢复全量 workflow。本片普通 push 的首次现有 Server CI 成功也不能签收完整 Windows/Win11。

F1未签收、F2并行探索、R4关闭、真实模型调用/预算0；正式 ServiceRelease/Approval、任意 ServiceSpec/DAG、审核参数模板冷启动和真实目标交付继续按原标准保留缺口。

首轮完整Linux1816PASS/1FAIL/9nativeSKIP（461.74秒）：唯一失败为既有迁移保留测试的health schema预期22未同步到23，产品源码未变。已修正该预期并定点1PASS（0.90秒），manifest对应rawhash刷新；保留首轮证据；最终完整回归已通过，结果见下方及机器证据。

ENG097最终：完整Linux1817PASS/0FAIL/0ERROR/9nativeSKIP/2WARN（459.89秒），249冻结文件零差异。专项33新补正+35既有兼容=68PASS，工程fixture53PASS；最终两冷会话三新Case浏览器1PASS/6图/9产物哈希独审通过。前述专项不重复计入全量，初轮失败证据保留。
