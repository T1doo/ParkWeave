# 默认关闭的单次 host→Case→取消候选交付

冻结源码 **8ea7060509e6e91aacaf06a2bce7f14997225000**，基于既有交付 `48907ab27969d7c095f1944571b1372ef420cac0`；独立候选分支 `dev/f2-host-case-once-candidate-20261013`。后续交付提交仅增加本文和公开证据，不修改受审源码、测试、清单或 pending approval。最终候选完整 HEAD 由交付响应及远端核对给出，该 HEAD 才是未来审批父提交。

本轮完成有限的单次 bootstrap/controller/SETUP/API/BUSINESS helper 与独立 workflow，复用原 LinuxHost、issued owned database proof、native app/writer、原 Case API，业务取消使用独立 pwci_case Store。没有扩通用权限平台。新入口 `scripts/host_case_once/approval.json` 仍严格 **false/null/null**，候选分支不匹配执行 workflow。未启动 runner、PG/IPC/真实 helper，未执行 useradd/groupadd/chown/chmod/SQL权限或随机凭据配置；未生成真实密钥，未重跑已消耗的旧入口。

门禁要求公开原仓库、固定新执行分支、push、run_number/attempt=1、标准 ubuntu-24.04、root入口、干净 exact HEAD、单一受审父提交、唯一 approval 文件差异。通过后才排他创建精确新 claim/T。固定 helper 操作、封闭公开摘要与私有密封FD/pipe/log；owner原证明保留到DROP，native与业务DSN分离；取消后单一原事件和持久状态、原Run/资料/assignment历史核对，迟到修改拒绝。750秒业务和独立120秒清理，不把强杀、未知资源或残留签PASS。失败保留T时保留身份所有者，成功删身份前收回新秘密到root0600，避免T删除失败留下可复用UID秘密。

| 本轮证据窗口 | PASS | FAIL | ERROR | SKIP | 限定 |
| --- | ---: | ---: | ---: | ---: | --- |
| 根最终相关纯合成测试 | 239 | 0 | 0 | 0 | 新candidate 62、binding 34、旧contract 84、diagnostics 59；真实副作用由DI guard禁止 |
| 独审修后candidate DI | 62 | 0 | 0 | 0 | 与根窗口重叠，不相加 |
| 独审期限反例修后 | 1 | 0 | 0 | 0 | 专用CleanupTimeout穿透逐资源handler |
| 根注册遗漏历史窗口 | 233 | 1 | 0 | 0 | 追加2测试后漏注册，原件保留；同ID最终PASS |
| 独审期限反例历史窗口 | 0 | 1 | 0 | 0 | CLOSE阻塞/期限被吞，原件保留；修后PASS |
| 本轮真实host/ACL/Case组合 | 0 | 0 | 0 | 0 | 固定21项全部 **NOT_RUN**，不是SKIP或模拟PASS |

独审结论 **LIMITED_PASS_CORRECTED_CANDIDATE_PURE_STATIC_ONLY**，8个受审源码/测试/清单路径与冻结提交的Git blob bytes/hash全等，无剩余阻断发现。首次BLOCKED及源码快照未覆盖；修复owner Store丢失、失败孤儿UID秘密、来源symlink先解引用、CLOSE与清理期限、claim审批范围，并补app/case实际42501→rollback→SELECT1的固定观察与DI反例。原PASS窗口47、173及独审57也原样保留，不能合并成最终覆盖数。

公开原件在 [证据 manifest](evidence/host-case-once-candidate-20261013/manifest.json)，包括日志、JUnit、两次独审与hash快照，复制前后逐项bytes/SHA256核对。源码差异检查PASS；完整归档staged差异检查FAIL（原pytest失败traceback的两行尾空白），原失败字节不修剪，原检查输出保留于本地runtime。[最终独审](evidence/host-case-once-candidate-20261013/independent/followup/followup-review.md) 和 [审批动作清单](HostCaseCancelTrialApproval-20261013.md) 分别限定代码可审和未来安全动作，不能互相替代。

当前唯一待批准激活差异：未来从最终候选HEAD创建 `dev/f2-host-case-security-once-20261013`，只把 `scripts/host_case_once/approval.json` 三字段改为 `approved: true`、`source_sha: <最终候选完整HEAD>`、`approval_ref: USER_CONFIRMED_HOST_CASE_SECURITY_ONCE_20261013`。不得加源码变化、额外父提交、复用旧审批或rerun。**本轮未创建该执行分支，也未写入激活值。** 父任务后续须就具体新身份、组、T/claim保护、仅新库ACL、临时私有随机值和清理范围取得用户明确确认，再决定是否执行唯一一次。

范围限制：丢响应是TestClient已返回后主动丢弃→只GET原key，不签真实transport断线/worker死亡恢复；外部SIGKILL、解释器不可恢复挂死及runner强制结束不签全清理/VM擦除。原27项真实PG验收只沿用既有交付，不在本轮重签；完整Case/host端到端签收仍未完成。main/F1/F2原主线不变，无部署、生产迁移、新业务Grant/registry、模型/付费调用、凭据或网络配置、安全权限扩大、浏览器重试或强推。
