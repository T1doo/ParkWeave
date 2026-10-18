# AT32 无试点来源与披露执行回执

固定 AT-32 本次实例结论为 **PASS：无真实试点时的来源与披露完整性**。受测／受审冻结 `d74c7b4e22c648e125b5aa135d2506e94242f76e`，基线 `aaac5263f5694535758a11b5c38cce31e156cccf`，分支 `dev/f3-at32-source-disclosure-20261018`。本结论覆盖下列有限发布包，不推断其他 AT、真实效果或完整项目通过；项目仍 IN_PROGRESS。

[冻结用例包](AT32SourceDisclosureCase-20261018.json) SHA256 `0407407cfd36e9ac6319ac450eaec81a50253e2070be3b63120ce2e2913545c0`，绑定固定规格原 oracle、初态、预算、步骤、重置 N/A 理由及 24 件材料的来源／原执行类型／长度／SHA。审查类型为 **REPLAY + MANUAL_REVIEW_BY_CODEX**：回读冻结证据与助手文档核查，未重新执行业务。助手代码独审不是外部领域专家、园区专员或真实用户反馈。公开文献／协议 URL 仅作历史引用，本轮未联网验证现时规则、许可或服务。

## 固定四项 oracle 的实际核查

| 项目 | 实际观察与依据 | 结果 |
| --- | --- | --- |
| 输入 | 两份 V1 原件实核 size／lines／本地恢复 LF 后 SHA；无独立上游 hash。台账区分用户设计、自建合成、公开参考及未提供真实资料；demo 明示启动外合成身份／Grant／目录／分派初态，未推定真实授权或第三方再许可。 | PASS |
| 输出 | 历史 MODEL_MOCK 仅 LOCAL_CASE_CREATED，Case NEEDS_INPUT；FAULT 输出为 SIMULATED_RECORD。NO_MODEL 本地材料导出实际 SHA 等于原追踪记录，正文明确 SYNTHETIC／真实性未验／政策 UNKNOWN／外部 NOT_SUBMITTED／Case 目标未完成。旧403是另一 fixture 的运输注入，未当作当前执行者撤权。原执行类型与本次 REPLAY 分轴。 | PASS |
| 使用反馈 | 本包未提供真实试点、访谈、满意度、外部专家反馈、节时、完成率提升或收益数据；台账明确缺项。自动化 REVIEW／CONFIRM、代码独审及本次文档核查均未写作园区上线、用户反馈或真实性批准。 | PASS |
| 报告引用 | 24 件与冻结 Git blob 及清单 SHA／长度一致。原两主窗 JUnit 实核 43 与 6 唯一 PASS；独审另外读取明确列出的旧独测 XML 与实际 collection 列表，逐 ID 验证独4全部重叠主43、独2全部重叠主6，不加总。三份历史报告保留限定范围、失败与 UNKNOWN；不递归宣称核完其所有外链附件。 | PASS |

[主核查回执](evidence/at32-source-disclosure-20261018/runtime/case-receipt.json)逐项列观察、文件与限制。[独立报告](evidence/at32-source-disclosure-20261018/runtime/independent/pw-ind-at32-d74c7b4-qfrpef0m/independent-final-review.json)同冻结四项均 PASS，开放 P1／P2／阻断为0；独立读取原24件、包自身及明确列出的6件补充，共31输入，共享／镜像 PRE／POST 无漂移。补充仅为两独测 XML／实际节点列表和原 runner／测试源码，不暗改原24件范围。独立本次新 pytest 节点为 **0**，不增加测试数。

## 工程执行与拒绝分别保留

- 既有 `run_acceptance.py --ids AT-32 --source-head d74c7b4e22c648e125b5aa135d2506e94242f76e` 在 pytest 前拒绝：`SOURCE_BINDING / GIT_BLOB_UNAVAILABLE`，exit1，外层0.366235秒，实际执行 **0 tests**。[原拒绝报告](evidence/at32-source-disclosure-20261018/runtime/engineering-at32.json)、[调用记录](evidence/at32-source-disclosure-20261018/runtime/engineering-invocations.json)及 stdout／stderr 保留，未重试。
- [只读诊断](evidence/at32-source-disclosure-20261018/runtime/runner-refusal-diagnosis.json)：全部355个测试 Git blob 有效，合计 **4,435,221 bytes**，超过既有 `source_bytes` 固定 **4,194,304 bytes** 上限。没有修改上限、runner、源码绑定或删掉 source-head；此工程入口限制仍未解决。
- 单独的冻结 Git archive 静态窗口，直接运行原 `tests/test_acceptance_runner.py`：**3 唯一 PASS／0 FAIL／0 ERROR／0 SKIP**，外层2.150714秒，pytest0.15秒、1条原 FastAPI/Starlette 弃用 warning，exit0。[实际结果](evidence/at32-source-disclosure-20261018/runtime/static-mirror-result.json)、[JUnit](evidence/at32-source-disclosure-20261018/runtime/static-mirror.xml)、[输入绑定](evidence/at32-source-disclosure-20261018/runtime/static-mirror-inputs.json)保留；761个 Git 输入与共享／镜像前后字节相符。命令使用镜像 cwd／PYTHONPATH，未另加逐模块 imports 仪表，不扩大来源证明范围。

这3项是原件完整性、42项绑定安全及禁止推断 whole PASS 的现有测试，不是新产品场景，也不表示 runner 成功；原 archive selector 单独仍只覆盖部分工程条件。AT32 本实例 PASS 来自上表四项实际文档核查，不能只由 pytest 推导。固定规格模板、全部 `ATBindings.whole_status` 及通用 runner 的 `whole_AT_EX` 保持 `NOT_RUN`。本轮没有全仓回归、模型调用、数据库连接、浏览器运行或业务状态变更。

## 门表修正与仍缺的输入

[来源台账](../F1/DataLedger.md)保留 F1 原文并追加纠正，AT32 gate 只改解释文字，不改 selector／oracle。依据原方案 §4／§10／§15，合成目录、MOCK／FAULT／REPLAY 可用于各自适用技术验收；无试点可完成本次来源／披露门。[剩余门表](RemainingDeliveryGates-20261018.md)按用例依赖收窄，正式来源合同不再被列为全部 PR0 固定 AT 的前置。新增来源或效果主张须重核本包。

真正仍缺的范围分别为：正式 preparation 来源专用 backend／主体／原 ADOPT 接线及对应既有只读结构、版本／fingerprint／current-head、决定／撤销／回执语义、主体权限映射与公开信任验真合同；真实业务须已有合法记录、当前会话与 READ／PREPARE／REVIEW_ASSIGNED／精确目录及适用的 Run assignment，缺项准确拒绝。Windows 原生与干净重建、适用 LIVE 模型／公平 B0/B1/B2、真实规则／期限或第二园区主张、其他固定用例逐项实际回执、C0 官方模板／准确规则／视频和接收回执分别待验。可用合成完成的其他固定技术 AT 不等待这些无关输入，也未被本次自动判通过。

正式五证明仍 UNAVAILABLE，NativeRunAccess permit／writer 默认拒绝，资源批准只读仍不可消费，IsolatedPlanApproval 只属隔离测试。未恢复 Windows 创建／ACL 工作；无新增真实身份、Grant、分派、目录发布、批准、凭据、费用、安全网络权限或真实模型调用。Windows 正式 AT、真实来源业务、现实履约与效果均未验；F4–F6 仍非 PR0／C0 新前置。

[继承字节核查](evidence/at32-source-disclosure-20261018/runtime/inherited-evidence-proof.json)确认基线33,297个 evidence Git blob 实际字节零改动，未知锁保留。新执行原日志、拒绝、独审与 [raw/public 清单](evidence/at32-source-disclosure-20261018/manifest.json)一并保全；旧301／382等窗口失败、错误修补及启动／清理 UNKNOWN 没有被本次 PASS 解释或消除。实际普通分支推送 SHA 与远端差异在本地 `.runtime/at32-source-disclosure-20261018/delivery-and-remote-verification.json` 单列，最终回报给出，不在本报告预认网络动作。
