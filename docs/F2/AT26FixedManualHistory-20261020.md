# AT-26 人工锁与历史事实：当前固定工程切片

源码 `5f28e77ed4415f6d3d468635195eda26f381d5e8`，接续 `527afdccba9fdba2ec81b42a0141b4b152fc8c60`。原 V1 AT-26、原固定 oracle 与正式规格字节保留，正式 `whole_AT_EX/AT-26 = NOT_RUN`。本片复用既有实现；产品运行代码无改动，没有新增第三种组合协议。

## 实际完成

同一次隔离 synthetic Linux owned PostgreSQL、真实本地 HTTP/ASGI 执行中，A/B 同时有完整中文换行人工原文和 P1 LOCK。只修改 A 的真实资料版本；A 当前 P1 为 `LOCK_CONFLICT`，旧成功事件、完整原文、旧证据仍在，B 全程 VERIFIED。KEEP_MANUAL、DEFER 保留原文和锁，未解决冲突不能经带 proof 或旧无 proof 入口采纳；锁下覆盖、接受源、VERIFY 都拒绝。

随后原 UNLOCK、ACCEPT_SOURCE、ADOPT 分别显式执行，任何一步都未冒充业务验证。原材料 REVIEW/CONFIRM、资源重关联、重发并接单、synthetic 回报/确认、本地 REVALIDATE 各自发生，再逐一 P1–P5 VERIFY，直到最后才恢复六目标本地输出 VERIFIED；业务 Case 没有自动完成。18 个阶段将历史与当前状态分别保存。8 张不可变表中原 38 行始终是当前表逐字子集，包括真实 synthetic 履约回执行；当前业务指针可由原动作改变。模板发布库和消费者库从冻结初态起未改变，179 条变更窗口 HTTP 记录没有模板发布写操作。

## 实际执行窗口

| 窗口 | 实际结果 | 范围 |
|---|---:|---|
| 最终原 `run_acceptance.py --ids AT-26 --source-head 5f28…` | 1 PASS / 0 FAIL / 0 SKIP，80.05 秒 | 单一固定场景，source_binding AVAILABLE，engineering_subset PARTIAL_PASS，full_regression=false |
| 绑定约束独立窗口 | 2 PASS / 0 FAIL / 0 SKIP，0.07 秒 | 固定 42 ID、selector/whole 状态安全约束；不计入上行 |
| 新目录 publisher 窗口 | 2 PASS / 0 FAIL / 0 SKIP，3.78 秒 | 原实际 CLI 安全输出与 Class::method 身份；不计入上行 |
| 较早开发窗口 | 1 PASS，83.15 秒 | 未冻结开发版，没有最终实体子集/HTTP补证；不合并 |
| 首个冻结 runner，`980df315c511a2539a74b86d18d2efbaad700839` | 0 PASS / 1 FAIL，18.09 秒 | 我新增测试读取 trace 的键写错，进入场景前失败；修复后重跑。失败原件保留，不算产品运行缺陷 |

898 个代码、工作流及原规格/绑定输入与源码 Git blob 一致，运行后零漂移。最终 10 个拒绝命令均返回 409 且无业务写。原最终日志、JUnit、逐阶段原件、拒绝正文和 HTTP 原件分别归档；gzip 保留完整原件字节，另有未压缩阶段摘要和 SHA256。

当前精确 Linux collection：9366 项 / 395 文件，四片为 2352 / 2309 / 2368 / 2337；比前 9365 项移除 0、新增 1，文件分配不变、四片稳定身份多重集合等于 global。这只是 collect-only。active AST 目录 3544 ID、454500 字节、missing/extra=0；4096 ID / 524288 字节上限不变。维护时产生的早期代保留；active generation 为 `20298420f25df9ffd1e302818911b86e45aa0b33882e8812619a81ab18d7178f`。

## 证据与边界

[有界合同](AT26FixedManualHistoryContract-20261020.md)、[原 runner 回执](evidence/at26-fixed-manual-history-20261020/acceptance-report.json)、[结果](evidence/at26-fixed-manual-history-20261020/result.json)、[18 阶段摘要](evidence/at26-fixed-manual-history-20261020/stage-summary.json)、[原件 SHA256](evidence/at26-fixed-manual-history-20261020/artifact-provenance.json)。独立审查原件在同目录 `independent/`，审查不重复执行此大场景。

本片沿 C26 语义使用明确冻结的 N0 与每 Case 实际 M0/M1；不宣称旧设计示例文本逐字执行。MANUAL 附注不是已验证业务事实。没有实际浏览器、原生 Windows、真实模型或正式来源执行，不能签正式 AT-26/全产品 PASS。主机 Windows 安装整体验收、OWNER_MUTATION_PAUSED、owner/DACL 和原生迁移026–032/roles/seed限制保持；未新增费用、凭据或权限，main 和旧分支不改。下一条按原 AT-25 复用现成场景，分别计算漏影响与误影响，未知保守扩大单列；不得把误影响计为实际正文误改。

最终独立只读审计 `LIMITED_PASS`、无开放 P1/P2，本侧动态测试 0，不重复计数。审计 SHA256：`4088cd7fe79c301c39ab8b5aef94a646f917b7d41183be0ffda7be37d952ba56`；核对上述当前原件及原规格/其他绑定行字节。
