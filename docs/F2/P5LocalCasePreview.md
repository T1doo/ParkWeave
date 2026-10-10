# P5 本地 Case 复核候选：环境阻塞，未签收

运行源码候选 `d52cfdbc0cfd98d34f172f72f56027ba861da8aa`，分支 `candidate/p5-local-case-preview-20261010`。基于已接受开发分支 `aac5489710b4364a78e83383c0ec9284a2b213fb`；没有合入开发分支。此次状态文档提交不改变运行源码。冻结合同提交 `c1c7a6bbd0967e5f38cdffa3e949aa2f7420af67` 先于实现；[写入与存储合同](P5LocalCasePreviewContract.md)和[124 条 SQL / 30 个影子表闭包](P5LocalCasePreviewSQLContract.json)是实现边界。

已实现原 `case_lifecycle.read/command` 的显式 REVALIDATE、CLOSE_LOCAL_RECORD、REOPEN 序列。模拟企业身份与执行者分离，绑定原 Case、请求版本、资料 revision、两槽 ID/version/hash、真实原资源及回执条件。关闭检查点为 WAITING_CONFIRMATION，重开 cycle=2、清当前校验并列四项复核；不把未决异议自动解决。保留原事件/账本、CAS、序列幂等与原 key 的未知结果 GET。全部原调用在 pg_temp 影子运行并回滚，正式 Case/Grant/通知写入为 0；默认关闭，不增加实际业务权限、政策审批、履约或模型调用。

**独审结论 ENVIRONMENT_BLOCKED / NOT_ACCEPTED。** [独立原报告](evidence/p5-local-case-preview/independent-report.json) SHA256 `f613fdeb149746df00917ca3c1a60ea5a7b6911b2ca9ad7a77f561ee7a05e3b7`。审查未证明产品阻断缺陷，但没有完成必要的精确源码运行验收，不能据此合并或签收。

| 精确源码窗口 | 实际结果 | JUnit / 受控秒数 |
| --- | --- | --- |
| 根 29 模块计划，实际仅 21 项后在 teardown 中受控停止 | 20 PASS、1 FAIL，exit 1 | 314.751 / 315.990567 |
| 根原页面失败项单独重跑 | 1 FAIL，exit 1 | 6.072 / 6.944460 |
| 根短原 HTTP 读取探针 | 1 PASS，exit 0 | 4.828 / 5.666094 |
| 根 Chromium 环境探针，启动/上下文阶段取消 | 0 项，未完成；wrapper exit 1，外层工具退出 130 | 228.394 / 229.200961 |
| 独立 29 模块，自然退出 | 96 PASS、1 FAIL、647 ERROR，exit 1 | 143.902 / 145.476040 |
| 独立自写 API 首窗，自然退出 | 11 ERROR，exit 1 | 0.224 / 1.189189 |

窗口各自保留，不累加 PASS。根原页面两次失败为读取 JSON `status` 时 KeyError；原窗口未记录 HTTP code/body，不能把具体成因改写为已证明的环境故障。短 HTTP 探针原已提交 key 返回 200 COMMITTED，原未知 key 返回 200 NOT_OBSERVED、发行者仍存活；Chromium 探针只记录启动前 200 NOT_OBSERVED，没有启动中/启动后实证。这些探针不是 P5 验收。

独立主窗实际记录 `sh: 1: Cannot fork`，随后 initdb 无法派生检测进程而退出 1；额外临时 PG 创建同样失败。工具另记录 bwrap namespace/fork 的 Resource temporarily unavailable；具体资源上限原因未查明，未改系统、凭据或安全网络配置。独立 API 首窗因私有探针漏显式 fixture import；已修私有探针，但纠正 API 11 项、独立 browser 9 项、纠正 29 模块均 **NOT_RUN**，不借根成绩覆盖错误。

开发阶段真实 PG/HTTP/Chromium 运行分别为 26P/4F、30P、41P/2F、87P/1F、53P/1F、7P；所有失败原件及观察器错误保全。开发中修正了夹具、回执 current hash 和错误页面选择器，并按静态审查修正 upstream 未执行阶段与唯一同历史文档回复关联。这些 mutable 窗口不能冒充 d52 精确冻结签收。见[开发故障分类/hash](evidence/p5-local-case-preview/development-fault-preservation.json)。

[367 路径源码清单](evidence/p5-local-case-preview/source-freeze.json) SHA256 `1567bac90e2acecd5ffdde5c2376d77ae9bab314ea3bd0af9c58b7ac0165008c`，根和独立末审零漂移，角色范围 SHA256 `604d084e12d84e9cad808ddd4a7e61289390faca49fd657d2ffe711b5a43afc3`。根结果与原故障文件 hash 见[根阻塞审计](evidence/p5-local-case-preview/root-blocked-audit.json)。原日志/XML/截图/合成连接与身份片段仅留私有 `.runtime/p5-local-case-preview` 和 `.runtime/independent-p5-local-case-preview-review`，不推送；公开文件只含安全报告、分类和 hash。

根准确识别并停止自身两个挂起 pytest wrapper；末尾递归自身日志来源审计未发现匹配的存活 wrapper 或 PG，不声称全环境进程归属均已证明。独审递归 child 日志发现初顶层扫描遗漏的独占 PG，验证 UID、原 -D 和 postmaster.pid 后经原 pg_ctl 正常关闭，末审自身剩余为空。没有关闭其他人的资源。

候选 d52 普通推送及实际远端核验完成；开发分支仍 `aac5489710b4364a78e83383c0ec9284a2b213fb`，main 仍 `31e7acb7e53bb1ab6465b9daae59de28757f7583`。没有强推、部署或改 main；平台锁保持原样。资料包导出未重做，旧 Windows a823a28 修复未迁移。

后续需要在可正常派生 PG/API/Chromium 的环境重新核验精确 SHA，完成根相关回归及独立 P5 API/页面验收后才可申请签收。完整原 issuer 退出恢复、完整 AT14、Windows 原生验收及真实履约仍未验证；仅沿用原 issuer 存活的已有证明范围。P4 旧错 key / 597 PASS 与 issuer 退出 500 故障窗口及旧报告保持不变。

## 原环境一次有界恢复诊断（仍阻塞）

父端授权仅在原实例诊断恢复；未创建替代环境。先只读核限额、进程和已有关闭记录，再做唯一一个 5 秒上限的单子进程探针，实际 0.014 秒 exit0 且自身 PID 消失。可见 pids.max=max、pids.events.max=0、内存约7.97/17.18GB、RLIMIT_NPROC=71955；具体限制未证明。这只能证明单进程当时可派生，不能证明 Chromium 所需线程容量。

随后仅串行原失败页面项及一次补证诊断，没有叠加 PG/浏览器窗口、改原断言或 Chromium 参数。两窗均自然 exit1、各1FAIL，JUnit/受控分别6.305/7.192023秒、6.208/7.041715秒。在 BrowserContext.new_page 阶段 TargetClosedError，尚未达到原 GET 断言。补证在浏览器前经原API实际 GET 原未知key：HTTP200、body.status=NOT_OBSERVED，issuer/API存活且socket存在。Chromium DEBUG 原日志随后明确多条 `pthread_create: Resource temporarily unavailable (11)`，实际 SIGABRT。公开[脱敏响应](evidence/p5-local-case-preview/bounded-recovery/root-status-browser-diagnostic-http-safe.json)、[夹具状态](evidence/p5-local-case-preview/bounded-recovery/root-status-browser-diagnostic-fixture-safe.json)、[错误签名](evidence/p5-local-case-preview/bounded-recovery/chromium-resource-signatures-safe.json)；原body/日志受私有身份与文档边界限制，历史和结果文档省略。

**停止后续所有测试，仍 ENVIRONMENT_BLOCKED。** 独立纠正API11、browser9、根/独审完整相关回归均未补跑，旧根 KeyError('status') 仍未解释；不能用启动前200或此次资源错误覆盖旧失败。源码 d52 的367路径再次零漂移、无产品修改、无 Grant/外部通知/真实履约。原两个 wrapper、补证 issuer/API/Chrome 已知 PID 均 /proc 不存在；自身日志路径匹配的存活 PG/runner 为空，原件仍保留。见[有界恢复结果与窗口hash](evidence/p5-local-case-preview/bounded-recovery/recovery-blocked-safe.json)。

末次只读可见19066个Z全部PPID1/tail，不能推定全部为本轮，更不能通过kill清掉未知进程。实际 uid_map 为 `1000 0 1`，cgroup视图 `0::/`，看不到宿主祖先预算。最小管理员动作：在**同一实例**核验该映射用户及祖先/宿主侧线程、进程预算，查明 Chromium errno11 的具体约束；由实例管理器核验 PID1 下孤儿的归属及原父进程回收路径，恢复正常线程创建。不盲目升限额，不新建实例绕过，不改项目权限、凭据、网络或 OOM 配置。没有 EPERM/EACCES 证据，因此不归因为策略拒绝；只读挂载下的 OOM score 日志不构成修改安全配置的授权。

独立仅只读核验本次原件，结论仍 ENVIRONMENT_BLOCKED；本轮 reviewer 未启动任何 PG/API/Chromium/pytest，不转借根成绩。见[独立诊断附录](evidence/p5-local-case-preview/bounded-recovery/independent-readonly-report.json)，SHA256 `cc08cde94f9455778f1247986424fb42826dfc22209a663054ab07ba21cdc4d7`。其初读 HEAD4401/Gitclean、末读本次docs-only待提交状态如实记录。旧 f613 P5报告及5b200 P4报告原字节不变；此后诊断附录提交仅docs，运行源码同d52，无新增运行验收。
