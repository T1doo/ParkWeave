# Native Run access / restricted ACTIVATE 验收

本片交付可信 native Run READ provider 与显式、原子 ACTIVATE；生产默认关闭。实现沿用已交付的普通合成 Case 取消、人工交接、收据和资源链，不扩大平台生命周期声明。正式生产启用政策、审批主体和受信 writer 尚未采纳；4/8 小时建议没有成为默认 TTL。

## 源码与边界

- 最终测试源码：`1a4ac06cc1e5af580c003da4c0c0ac51b028b7b2`。
- 414 文件清单 SHA256：`6dd7360657dc915f39731b7c29022c650ad6da848dd23068326b126be1361c53`；实际测试首尾、源码提交与工作区一致。
- 生产源码与独审修复提交 `13029ed5e19fd3ffbf8c8dba01a3afcfe7215893` 字节一致；最终源码提交只修复四处旧测试/诊断夹具。
- [ACTIVATE 合同](NativeRunAccessActivationContract.md) SHA256：`0b2cada854812b3672cd6c6b36572349606150a5237dcb6e9b263f91f4317548`。
- [decision 合同](NativeRunAccessContract.md) SHA256：`6fbc10b549e65d901db97ad9a93e295220d878edfb294e2dd3988fd6de0c234f`。
- 开发分支：`dev/f2-native-run-access-activation-20261011`，从既有 native decision 交付 `f37c93a50600e9afe32c18b31351ee09bddb52a8` 接续。最终证据提交是交付 SHA，与上述测试源码 SHA 分别核验。

受限发行器只接受原有 fresh owned synthetic PG 证明、原集群/数据库、原 owner writer。不可变 permit 绑定已有批准 lease、明确 UTC 区间、精确 approver/既有 executor/owner/Run/Case/tenant/material/权限版本及权限行代际。原 owner 当前 READ/PREPARE/EXECUTE、原键、原因、严格布尔确认和当前版本均必须匹配。parent → Run → assignment 锁内将 immutable activation receipt 与精确 native assignment 同事务提交；不覆盖 legacy/isolated assignment，不新增 SQL GRANT、业务 Grant、身份或信任 registry。

有效 READ 还必须满足实时 permit、原 activation、实际 assignment、未撤销的 APPROVED lease、当前来源/权限及数据库 UTC。普通冷 Store、未知或覆写 provider、跨数据库借用 writer、临时/影子 schema、autocommit、缺失可信 enablement 均拒绝。冷重绑只接受原明确发行 permit，GET 不激活或修复记录。业务访问在 guarded commit 重核，锁等待中撤销/到期会拒绝或回滚。原键恢复返回原 immutable receipt，并单独返回当前可用性；不自动重发 POST。

READ 范围不赋予新的业务角色。已有 executor 仅在自己的当前责任范围执行 ACCEPT/DECLINE/manual SUBMIT，收据和分派业务守卫继续生效。合法进展、RECONCILING/CANCELLED、local close 保留有权历史读取；取消/对账/关闭阻止新激活与受限业务写。取消不自动释放预约容量，原独立释放/组合取消依其当前权限继续操作。原建单成功、资料、分派、资源与预约历史保留。工作台分开呈现当前 fixture READ 和 NON_EFFECTIVE 审批历史；真实到期 callback 清除有效展示，保留 UNKNOWN/原键并只 GET 恢复。该片无生产 ACTIVATE 按钮。

## 实际验证

真实 owned PostgreSQL、进程内 ASGI 与离线 NodeVM 的结果如下，未使用 SQLite 替代锁竞争。两个广基线进程使用不同 owned fixture，模块互斥；不是一次 pytest invocation。

| 最终冻结窗口 | PASS | FAIL | ERROR | SKIP | 唯一 JUnit ID | 实际收集测试项 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| root delivery lane a | 2299 | 0 | 0 | 20 | 2319 | 2318 |
| root delivery lane b | 2085 | 0 | 0 | 20 | 2105 | 2105 |
| 两线合计 | **4384** | **0** | **0** | **40** | **4424** | **4423** |
| 独立 delivery-frozen-full | **201** | **0** | **0** | **13** | **214** | **214** |

root 调用全部 135 个允许模块参数，2026-10-11 20:48:06.299923–21:15:57.852714 UTC，实际两进程均 exit0。414 源码及两个合同零漂移；执行进程实际 collection 与完成 JUnit 身份逐一对应，无遗漏/重复。额外 1 条 JUnit 是 `tests.test_material_objection_authority_edges` 的整模块 collection SKIP，该模块没有收集测试项。其余 39 条 SKIP 为 30 条 PowerShell 环境相关和 9 条 Windows 原生相关测试，均不计 PASS。

独立进程另实际运行完整 47 activation + 35 decision + 8 offline NodeVM + 16 自写 PG 反例，以及完整四个维护模块（95 PASS / 13 SKIP）。它与 root 重叠 198 个 ID，另有 16 个独立 ID；两个窗口的 PASS/SKIP 不相加冒充独立覆盖。额外独立 `delivery-vm-expiry-callback` 是 Node exit0、8 checks，无新增 JUnit testcase。独审结论 [LIMITED_PASS](evidence/native-run-access-activation-20261011/independent/DELIVERY_REVIEW.md) 在 root 广窗结束前签署，报告原文中的 RUNNING 保持不变；root 完成结果由[实际执行记录](evidence/native-run-access-activation-20261011/root/delivery-baseline-run.json.gz)及[结果汇总](evidence/native-run-access-activation-20261011/root/delivery-result-summary.json)证明。

动态覆盖包括实际建单 worker、P1–P5、资源关联/占用、人工 ACK/local close；有效 assignment 后分派/ACCEPT/legacy receipt CREATE/manual SUBMIT/通知/依赖读取；同异键并发、事件或 assignment 失败全回滚、丢响应原键冷 GET；撤权重授/删建权限行/跨租户/跨 Run/跨 DB；持久 native 标记不能降级 legacy；真实 parent 锁等待后的材料变化、到期、ACCEPT 与 REVOKE 两种顺序、SUBMIT 与 REVOKE 两种顺序及提交前到期回滚。取消三阶段保留有权历史 READ，新激活/业务写拒绝；旧通知重核可用性，不伪造 WITHDRAW。计划来源变化仍要求原 API 显式 ADOPT，不自动重绑。

[独立消费者审查](evidence/native-run-access-activation-20261011/independent/static-consumer-review.json)核查 central Store、executor parent/receipt base、列表 post-filter、通知 OPEN/outbox 与 guarded commit。七份既有 SQL 白名单及 role bounds 与 f37 基线字节一致。静态消费者覆盖不代表每个 API 都被独立动态运行。

## 原失败与修复证据

所有窗口原件留在本地 runtime，发布副本按既有规则脱敏并标记。原失败没有改成通过；修后另有实际窗口和同 ID 映射。

| 原窗口 | 原结果 | 修复及最终关联 |
| --- | --- | --- |
| root initial | 70 PASS / 2 FAIL | 错误测试 URL；metadata REVOKE 被自身 tracked commit 回滚的实现缺陷。独立重跑修复，最终全范围通过。 |
| root second | 85 PASS / 1 FAIL | 旧测试错误期待未持久化 legacy 行可授权；实际 legacy 正/负例保留，最终同 ID 通过。 |
| independent initial-provider-counterexample | 1 FAIL | HIGH：未知 provider 返回 True 导致真实 GET200；限定 exact native 类型、同 Store 与可信类方法后，同 ID 实际 PASS。 |
| independent initial-cross-db-counterexample | 1 FAIL | HIGH：DB2 Store 借 DB1 issued writer 完成 ACTIVATE；先核业务 Store 实际 endpoint/database 后，同 ID 实际 PASS。 |
| 原 root 135 模块 full-baseline | 4357 PASS / **27 FAIL** / 40 SKIP，exit1 | ACL oracle1、旧诊断名清单1、离线 handoff 夹具9、目录 snapshot 间接 Playwright import16。四处测试/夹具维护；冻结源码两线最终同 27 ID 全 PASS。 |
| 初始 collection | exit2 / 2 collection ERROR | 两个间接 browser 模块缺 Playwright；保留原错误，整个模块 NOT RUN。未安装、替代或启动浏览器。 |

四处维护保留 `OWNER_MUTATION_PAUSED` 前置关闭守卫，将安全诊断名清单更新为当前 1886 个 AST 函数名，仅给 handoff NodeVM 补实际初值 `preparationView:null`，将 browser 专用 import 移到实际 browser child_environment 内。实际 PG snapshot 函数字节不变。维护窗原 95 PASS / 13 SKIP 的未提交状态记录保留，随后冻结 1a4ac06 并重新运行广基线及独审。

[独立 29 个同 ID 映射](evidence/native-run-access-activation-20261011/independent/delivery-failure-map.json)关联两项 HIGH 与 27 项维护失败；[root 最终汇总](evidence/native-run-access-activation-20261011/root/delivery-result-summary.json)也核对最终广窗同 27 ID。初始第一独立 probe 的整份输入未在后续追加前另存，捕获限制保留在原 [REVIEW](evidence/native-run-access-activation-20261011/independent/REVIEW.md)；其完整原 stdout/JUnit 和产品源快照仍在。

归档过程中另有纯 metadata identity 检查：旧 checker 因 JSON 对象键顺序误判，修正 path-keyed 比较后实际 probe PASS。独审捕获时已是修后代码，外围 inline wrapper 仍期待旧 exit1 而产生 AssertionError；其 stdin 明确 NOT_CAPTURED。旧 helper 由先前工具读取重建并匹配旧 SHA，仅提取函数 probe 实际 exit1，未宣称整份旧 helper/归档窗口失败。完整原诊断及限制见 [ARCHIVAL_STATIC_NOTE](evidence/native-run-access-activation-20261011/independent/archival-static-note/ARCHIVAL_STATIC_NOTE.md)，这不是产品/JUnit 失败。随后 root 实际执行完整 exporter/validator，对 416 输入、16 个 exact static、17 个 JUnit 窗及 349 个 JSON metadata 检查通过。

[完成归档独审](evidence/native-run-access-activation-20261011/independent/ARCHIVE_REVIEW.md)对原 416 闭包实际 exit0，独立重算 accepted-policy 字节、redaction counts 与 25 个 deterministic gzip，核对全部实际基线/同 ID/重复计数、旧 2590 个 tracked evidence 和旧 117 个独审原件。只追加 14 份明确列出的 root 检查和独审签署/支持记录，原 416 导出字节不动；最终 manifest 430 项，root 再实际 validator PASS：16 static、17 JUnit、358 JSON。最终 manifest SHA256：`cac0d5b98ea70a60b86fa98c8c6a1841f52af109d31afc64388c8f308beedf48`。

整份暂存 `git diff --check` 实际 exit2，27 条尾随空白诊断全部在原失败日志/JUnit 导出；源码与新写说明各自检查 exit0。原[检查输出](evidence/native-run-access-activation-20261011/root/delivery-staged-whitespace-check.sanitized.log)和[实际结果](evidence/native-run-access-activation-20261011/root/source-and-authored-doc-whitespace-check.json)保留。完成归档独审另有辅助 inline summarizer 将 list 当 dict 的 exit1，其 stderr/provenance 保留在支持闭包，主 416 核查已先通过；没有新增业务 testcase 失败或修改原输入。

## 未运行与后续

[最终范围](evidence/native-run-access-activation-20261011/root/delivery-baseline-scope.json)列明 24 个直接 browser 模块及 2 个间接 browser 模块 NOT RUN；上述混合模块另为实际 collection SKIP。browser attempts=0，既有 Chromium `data:` 导航 `ERR_BLOCKED_BY_ADMINISTRATOR` 未重试、未换 URL/工具。生产部署/生产迁移/真实权限或 assignment 改动/付费模型、Windows 原生验收与完整正式 AT35 均 NOT RUN。

本限定片无剩余阻断。下一片须明确并采纳生产 enablement/审批/TTL 政策及受信 writer，再另行验收生产启用和完整 AT35；本次不将 owned-fixture 发行器解释为生产授权。交付只正常推送独立分支，protected main/dev 基线保持不变。

完整归档与脱敏/哈希规则见 [evidence README](evidence/native-run-access-activation-20261011/README.md)。
