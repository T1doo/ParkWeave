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
