# AT-27 定义升级与业务数据：当前固定工程切片

源码 **`9a2a9d5a778e58661f9cc7269827823146830667`**，接续 `ff67d40b205140faf1d15d7112b20cc9bbaf9f49`。原 V1 §7.5、AT-27 与旧 literal oracle 字节保留；本片冻结[实际 oracle](AT27FixedDefinitionDataOracle-20261020.json)和[有界合同](AT27FixedDefinitionDataContract-20261020.md)，复用既有两 Case 后端场景。产品运行代码没有变动，没有新测试 ID、协议或兼容矩阵。正式 AT-27/whole_AT_EX 仍为 NOT_RUN。

## 当前实质结果

初态两 Case 使用原六目标与 P1–P5，原审核确认、资源预订/关联、接单、回执核对、本地重核和逐步 VERIFY 已完成。初态归档原 UUID、计划、诉求/材料/回执全文、预订和历史实体以及 consumer 原行。核心21类记录实际64行保留全文；全部45张 public PG业务表（只排 authorization_audit）和完整 consumer 由执行中直接全等断言保全，另存逐行/逐表 hash。不是只核引用。

| 原固定变化 | 本轮实际结果 | 证据范围 |
|---|---|---|
| 完整非法注册定义 SAVE_DRAFT | 422，发布库和业务未变 | 请求和定义 validator 响应全文，不是缺请求体 |
| 有效 publisher 未经独立 REVIEW 发布 | 409，未新增 release，业务未变 | 实际 publication business guard；不是仅角色403 |
| 独立 REVIEW 后合法发布新定义 | 200，新目标少一个原必需协调目标 | 允许独立新定义，不自动迁移旧 Case |
| A/B 原兼容预检 | 两次200、BREAKING_REJECTED，仅允许 KEEP_CURRENT | 原 UUID、全文、预订/回执、consumer和历史不变 |
| A/B REQUEST_RECHECK | 两次409 | 不兼容分类下拒绝；无 checker journal/业务写 |
| A/B KEEP_CURRENT | 两次200，各一个revision1原审计事件 | 仅保留选择，不是迁移采纳 |
| A/B 完整 POST /apply | 两次409，实际正文含 UPGRADE_SCOPE_UNSUPPORTED 和 CURRENT_EXPLICIT_CHOICE_REQUIRED | 原11字段 DTO、fresh check/计划/parent/KEEP proof匹配、原model验证通过；不是404/body422 |
| A/B 旧 superseded ref /check | 两次403 | 仅当前目标可用性预检拒绝；没有实际 rollback执行 |

MIGRATE 的两次422单列为封闭 choice 类型拒绝，不能作迁移执行门证据。完整 Apply 同时有“不支持此升级范围”和“KEEP不是执行选择”两阻断，不宣称单独 scope 门的反事实执行。两Case KEEP事件的check hash、新check hash、Apply预期check hash均相同，11个请求字段对应当前 proof，避免把陈旧CAS说成兼容拒绝。

原发布过程 RETURN_DRAFT 将旧 release 的外部 state 从 PUBLISHED 改为 SUPERSEDED；其 id/scope/payload/sha逐字保留，新release是唯一新增条目。后续原发布库不再变化。历史已完成业务仍完整存在，不因此宣称旧模板当前仍可用或重新通过验证。八个保全点全PG/consumer/两完整stored plan均与初态相等；checker恰两条 KEEP_CURRENT，没有迁移事件。变更窗口实际31条本地HTTP请求，完整原件保留。

## 实际执行与收集

| 窗口 | 实际结果 | 边界 |
|---|---:|---|
| 原 runner `--ids AT-27 --source-head 9a2a…` | 1 PASS / 0 FAIL / 0 SKIP，18.21秒 | source_binding AVAILABLE，engineering_subset PARTIAL_PASS，full_regression=false |
| 固定绑定/whole状态约束 | 2 PASS / 0 FAIL / 0 SKIP，0.06秒 | 独立小窗，不加到上行 |
| 更新目录后的原 CLI publisher | 2 PASS / 0 FAIL / 0 SKIP，3.50秒 | Class::method/安全输出，独立小窗 |

本片无失败测试窗口。907个实际代码/工作流/原规格及新oracle/合同输入与冻结Git blob一致，运行后零漂移。AT27原绑定的两个legacy schema/grant迁移测试仍保留在 historical_engineering_selectors 和历史来源SHA中，本轮不执行，不累计数字；其他AT绑定行不改。

精确collection在同源码刷新为9366项/395文件，四片2352/2309/2368/2337；四片稳定身份多重集合等于global，和上轮9366相比增加0、删除0，文件分配不变。580个manifest绑定输入零漂移。此为collect-only，不是9366 PASS。active AST目录仍3544 ID/454500字节，missing/extra=0，4096 ID/524288字节上限不改，active generation为 `c02c777a627d3a53b8c201318e525e4a762f1dc8d9b627865ae0d0e578eb523c`。

## 证据与原计划剩余项

[原 runner 回执](evidence/at27-fixed-definition-data-20261020/acceptance-report.json)、[结果](evidence/at27-fixed-definition-data-20261020/result.json)、[阶段摘要](evidence/at27-fixed-definition-data-20261020/stage-summary.json)、[原件SHA256](evidence/at27-fixed-definition-data-20261020/artifact-provenance.json)及同目录 baseline、实际template请求、完整执行拒绝、保全点和HTTP JSONL原件。大baseline用gzip原字节归档；私有原件未改，没有已知synthetic token或前缀进入公开原件。

本轮没有重复原HTML/NodeVM场景，UI与真实浏览器均NOT_RUN。原生Windows/Win11安装整体验收、正式来源/真实业务及模型场景、正式AT与全回归仍未完成；实际迁移、版本回退执行与撤销预约/线下/外部动作没有验收，不能用本片拒绝结果代签。Windows OWNER_MUTATION_PAUSED、owner/DACL及原生迁移026–032/roles/seed授权门保持；未尝试改变权限或绕拒绝。没有新费用/凭据/真实模型/部署/用户电脑动作。原方案项目仍IN_PROGRESS，后续在原授权边界继续固定验收及正式环境前提，不扩展兼容矩阵或把后续阶段抬为新前置。

最终只读独审 LIMITED_PASS、无开放 P1/P2，不重复 PG/pytest。审计 SHA256：`b1d5afaeec6cb7cd4b6ba38732062632c6a79c96036b83bb3b12ea5337011940`；审计原件见同目录 independent/review.json，独立核当前原件和归档、907代码输入、580collection输入、完整CAS及实际拒绝/保全边界。
