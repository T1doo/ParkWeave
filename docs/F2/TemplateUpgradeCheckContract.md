# 实施前冻结：F2-T06 / §7.5 逐实例模板升级检查

首轮真实开发验证后的桥接合同补充（先于修复）：原 consumer 的计划采纳 stage key 为 `tc:<canonical实例UUID>:ADOPT_PLAN`，原计划历史证明却仅接受 `[A-Za-z0-9_-]`，导致已形成的真实旧实例检查和原LOCK拒绝。新建 stage 使用 `tc_<UUIDhex>_<注册stage>` 规范键；已有 stage/key/body不改写。原计划历史核验仅额外识别 revision1/actionADOPT 的精确旧键形状，仍核对原owner/Case/完整事件、原采纳参数与fingerprint。不是允许任意分隔键、复制fixture凭证或放宽新进程写门。首轮21FAIL/1PASS原日志/XML私有保全，不算最终验收。

基线 dev `b496f6a4da7022c10c906ff722fd3279f4536f71`，main `31e7acb7e53bb1ab6465b9daae59de28757f7583` 保持。唯一源码/Git写入者；候选分支独立开发。现代码已有默认关闭的合成模板审核/发布、不可变 SQLite Release、原 PG 新企业消费和不可变实例绑定；没有逐旧实例升级检查。旧版本不可用仍禁止继续消费，不能由检查重新开启。

最小有用切片是检查与明确选择的独立有界审计记录，不是迁移执行器。只显式组合到原隔离 consumer 工厂，精确同 consumer/engine/store、原 fixture 数据库和已有企业范围。默认生产 API 不挂载，没有新身份、Grant、fixture 凭证复制或新进程写门适配。

从本人原 consumer instance 找出旧 Release ID/hash/快照、原 Case/Preparation/Run 与输入绑定；旧 superseded/withdrawn Release 仅用于历史比较，必须核对原不可变库与实例快照。目标须同 park/template、当前可消费并经原独立审核的不可变 Release，核对 ID/hash/definition/registry/contract/source。对已形成的本人 Case 读取原授权、资料、请求、注册计划、手工锁证明和实际依赖来源，检查使用 observe=False，不写失效观察。尚无 Case 拒绝检查，未决 stage 不自动解决。

分类：移除旧目标/步骤、修改旧适配器/依赖/参数服务合同、降低内容版本或回退旧发布为 BREAKING_REJECTED；保留结构但增加目标/来源变更/当前业务依赖或未决阶段需核对为 NEEDS_RECHECK；需改动而旧步骤锁定或原 LOCK_CONFLICT 为 LOCK_CONFLICT；仅同来源、同结构的说明改动且当前旧实例无未决/失配为 COMPATIBLE。已有未完成但无变化步骤可保持待办理，不能把 COMPATIBLE 当完成。破坏性拒绝优先，其余锁冲突优先于需重验。

检查本身 GET 不落记录；明确 POST 选择 KEEP_CURRENT（全部分类）、REQUEST_RECHECK（兼容/需重验）或 ACK_COMPATIBLE（仅兼容）。人工锁冲突只能保留旧版，等待原入口明确解锁；破坏性只能保留旧版。所有选择只是确认检查结果/请求后续人工重验，原实例 Release 绑定和计划仍旧版；不会迁移、执行、预约、撤销、覆盖资料/决定或回滚回执/效果。不提供 APPLY/MIGRATE/ROLLBACK 指令。

独立新建非 symlink `.upgrade.candidate.sqlite3` schema v1，仅不可变事件表和固定拒绝 UPDATE/DELETE 触发器，不改原候选/consumer 文件或 PostgreSQL schema。每本人实例最多64事件；scope绑定 actor/park/org/database/instance/Case/Preparation/旧新 Release ID/hash、检查源hash、原请求key/body指纹、单调revision、前hash/事件hash、明确原因/选择。CAS要求检查hash与审计revision一致；同key同body返回原历史事件，变参或跨实例key拒绝。丢响应用 GET 原key只读恢复，撤权先于历史恢复，不靠盲重写推断结果。

新选择持当前 PG 身份共享锁和 parent FOR SHARE、重验现有 READ/PREPARE/EXECUTE/case.create 与本人Case范围；同候选 SQLite事务核对目标头/来源及历史并保持到独立事件提交，审计 BEGIN IMMEDIATE保证CAS。保证仅为检查观察和选择记录，不声称跨 PostgreSQL/候选/consumer SQLite 的迁移原子性、未来持续有效或非协作DBowner篡改全部锚的安全性。GET/历史查询不重新消费或调用普通产品写函数。

真实 HTTP/PostgreSQL 与页面核验兼容/增加目标/来源变化、人工锁/破坏性/回退、过期/撤回/换版、丢响应只读恢复、重复/并发CAS、撤权/越权/跨企业/跨模板、陈旧检查与历史恢复、SQL不可变/损坏负例，以及原Case/预约/回执/全部历史/权限不变。精确源码普通候选推送后独立审查，只有通过后的正常开发分支推送；main不动。完整F2/AT27迁移/正式ServiceRelease、真实业务/权限/通知/模型/履约/Case完成、全仓/Windows仍缺；已消费Approval实际重启GET范围与未消费新进程403边界保持。
