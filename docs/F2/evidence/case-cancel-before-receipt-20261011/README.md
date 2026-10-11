# 接单后、首次回执前取消：可读原始证据

**LIMITED_PASS**。最终根完整窗口已实际完成 **1390 PASS/0 FAIL/0 ERROR/1 Windows SKIP，进程0**：37完整模块、1391唯一标识，旧1271全部保留，新增120；不是全仓/AT或完整Case生命周期。范围与全部窗口说明见 [交付证据](../../CaseCancellationBeforeReceiptEvidence.md)，有限合同见 [合同](../../CaseCancellationBeforeReceiptContract.md)。源码/测试最终冻结 `3fc6fa712f14820d88fcf8cd94fa70fcf6120e0c`，401路径清单 SHA256 `cb236fe42b8acf4c6cf2748d781106844bffd1b1201094d63827d3f6350309c7`，前后零漂移。

## 如何复核

`root/` 和 `independent/` 保存64件实际窗口、JUnit XML、完整 stdout和冻结/审查记录，包括原 FAIL、中断和漂移窗口。它们是明确标记的脱敏副本；私有输入仍在本环境 `.runtime/case-cancel-before-receipt/`，没有改写原字节。`archive-manifest.json` 逐项给出原文件 SHA/大小、导出 SHA/大小、脱敏类别及次数，清单 SHA256 `b042b947c119656bd2ee40c4196f78a861070a80ecb7580ced73d144c9b10526`。超512KB内容采用无损 gzip 政策，并附解压 payload SHA；本次64件无需压缩。独审静态 helper/probe/修前源码快照不含运行时凭据，按原字节复制。

`build_archive.py` 复用前片已签收的 stdout/JUnit 脱敏政策，只替换执行路径、fixture 认证值、Bearer/password/PG URI 及主机名。所有 testcase classname/name、时间、PASS/FAIL/ERROR/SKIP 和 suite 计数逐项断言不变。JSON 的哈希、测试标识和业务证明长字符串保持字面值，只处理执行路径及 URI/Bearer。原与导出哈希不同不代表原件被改；清单明确区分两者。

`build_failure_map.py` 把每个实际失败标识映射到另一个实际通过窗口，保留原失败状态及其证据等级。独审两条产品缺陷通过相同独立测试 ID 复验；根窗口失败通过最终完整窗同 ID 复验，不能把多窗汇总当单次结果。

## 关键文件索引

- 最终根完整窗：[JUnit](root/full-final.sanitized.xml)、[stdout](root/full-final.sanitized.log)、[真实命令/退出/时间/冻结记录](full-final-run.json)、[401路径](final-source-manifest.json)。
- 最终独审：[限定签收报告](independent/REVIEW.sanitized.md)、[机器记录](independent/review.sanitized.json)、[132项 JUnit](independent/final-frozen-review.sanitized.xml)、[stdout](independent/final-frozen-review.sanitized.log)。其签署时根完整窗尚在运行，保留这个时间边界。
- 独审真实 HIGH 反例：[原 BLOCKED 报告](independent/BLOCKING_LINEAGE_COUNTEREXAMPLE.sanitized.md)、[9PASS/2FAIL JUnit](independent/pre-fix-extra-probes.sanitized.xml)、[stdout](independent/pre-fix-extra-probes.sanitized.log)、[修前模块原字节](independent/pre-fix-case-cancellation-before-receipt.py.sanitized.txt)。修后 [11PASS JUnit](independent/proof-corrected-extra-probes.sanitized.xml)、[stdout](independent/proof-corrected-extra-probes.sanitized.log) 同源清单；原观察和修后观察分目录，原文件未覆盖。
- 根原初失败：[73PASS/8FAIL](root/first.sanitized.xml)、[完整异常](root/first.sanitized.log)；旧029夹具 [304PASS/1FAIL](root/second.sanitized.xml)；修后5模块 [314PASS](root/third.sanitized.xml)。
- 根中断完整窗：[67PASS/2FAIL/1SKIP](root/full-attempt-1.sanitized.xml)、[完整 stdout](root/full-attempt-1.sanitized.log)、[实际退出2/70ID/零漂移](full-attempt-1-run.json)、[核实自身进程后 SIGINT 记录](full-attempt-1-stop.json)。它是不完整窗，其余标识不能计为 PASS。
- 版本集成 [138PASS/1FAIL/1SKIP](root/schema-integration.sanitized.xml) 保留 wheel 缺031的原 KeyError；修正后的 [164PASS](root/proof-and-wheel-fix.sanitized.xml) 包含107新后端、35机会、22离线页面与实际 wheel 安装迁移。
- [逐项失败映射](failure-map.json)、[全部原件/导出清单](archive-manifest.json)、[环境及生产 JS 语法](environment-and-node-syntax.json)。
- 完整根窗结束后的独立归档签收：[ARCHIVE_AUDIT.md](ARCHIVE_AUDIT.md)、[逐件机器记录](ARCHIVE_AUDIT.json)。另见根任务的 [源码/归档核验](delivery-source-and-archive-verification.json)。这些是64件冻结清单外的后续支持文档，原签署 REVIEW 和64件清单没有改写或递归重建。
- 审计自身诊断：旧目录仅新增的 ignored pyc 已按 [清理记录](evidence-cache-cleanup.json) 删除，73原文件字节未改；导出器禁止生成字节码。粗扫描误把原静态 probe 的复现路径当运行值，保留 [原断言输出](coarse-export-scan-diagnostic.json)，按已声明静态代码原字节政策的 [修正核验](corrected-export-policy-scan.json) 无运行时敏感值发现。独审1ms时间断言过严也在归档签收中原样披露，均不是 testcase FAIL。
- [暂存差异空白检查](cached-diff-check.json)：完整归档检查实际退出2，仅原 pytest 失败正文的6行 `E ` 末尾空白；原导出哈希和失败正文保留。排除这些原日志/XML后的源码、metadata、helper和文档检查实际退出0；未改变 Git 空白配置。

## 保留限制

历史跨租户 fixture-b 原失败只直接证明 CLI 返回0后 Case_count0；原 worker stdout/持久状态没记录，根因仍 **UNCONFIRMED**。独立两轮 b/c 为 SUCCEEDED/VERIFIED、Case1，不恢复原缺口或确认短租约假说。原一秒租约、Case1 和跨租户403要求没有放宽，仅补未来失败诊断。

前片61个证据文件保持原样：[前片索引](../case-cancel-before-accept-20261011/README.md)。其中旧39个API stderr 缺失及推断根因、旧清理异常保留原披露；本片不声称恢复旧原件。

浏览器 **NOT RUN，0次启动/替代重试**，历史 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 保留。Windows/native 未在本环境执行。生产迁移/部署、真实模型/付费调用 **NOT RUN**。无凭据/网络配置、生产权限扩大、强推或 protected 分支写入。本片不支持任何提交回执后取消、恢复或完整生命周期。
