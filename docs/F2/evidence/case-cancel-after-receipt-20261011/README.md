# 已有人工回执后的取消核对：原始证据索引

有限合同及实际范围见 [合同](../../CaseCancellationReconciliationContract.md)、[交付证据](../../CaseCancellationReconciliationEvidence.md)。源码冻结 `796b41ad8939ba1d067f84f137a4d2a1861f06d4`；405文件清单 SHA256 `cb47c652372f4aad3076c7adc995e77f505800f4aa1e28d39a94617b0a9d96b5`。最终单窗38完整模块实际1560PASS/0FAIL/0ERROR/1既有WindowsSKIP、exit0，1561唯一ID、旧1391全部保留+170；405源零漂移。不能把下面的窗口相加成一次通过。

## 复核方式

`root/` 与 `independent/` 为明确标记的脱敏副本。私有原件在本环境 `.runtime/case-cancel-after-receipt/`；导出不改原件。`archive-manifest.json` 按每件列原SHA/字节数、导出SHA/字节数、处理类别、解压payload SHA以及JUnit结果摘要。超512KB用固定mtime=0的无损gzip。全部JUnit classname/name、时间、PASS/FAIL/ERROR/SKIP及suite计数在导出前后逐项断言一致。

`build_archive.py` 复用前片签收的stdout/JUnit脱敏政策：执行路径、fixture认证值、Bearer/password/PG URI及hostname。JSON保留字面hash、测试ID及业务证明长字符串，只处理执行路径和URI/Bearer。静态 `.py/.js/.diff`、修前 `.py/.js/.sql/.html.txt` 源码snapshot经精确路径与SHA白名单才按原字节复制；它们不含运行时凭据。每件记classification，JSON非空credential key拒绝导出。不把源码scope或源哈希当token删改。读取旧policy前禁生成pyc，旧两片149已签收文件保持原字节。

输入清单第一次导出后冻结；后来审计文件单独保存于该清单之外，不递归重建或覆盖既签署报告。`build_failure_map.py` 逐实际FAIL/ERROR映射到另一实际窗口同ID PASS，原窗口仍失败。根失败由最终38完整窗同ID复验；独立失败由实际第六226窗同ID复验，精确注明该窗e103cb清单与最终cb47的静态差异绑定。

## 关键文件

- 最终根完整窗：[JUnit](root/full-final.sanitized.xml)、[完整stdout](root/full-final.sanitized.log)、[实际命令/进程/退出/漂移记录](full-final-run.json)、[405路径](final-source-manifest.json)。
- 独立签署报告：[REVIEW](independent/REVIEW.sanitized.md)、[机器记录](independent/review.sanitized.json)、[实际226 JUnit](independent/sixth-complete-backend-ui-and-probes.sanitized.xml)、[stdout](independent/sixth-complete-backend-ui-and-probes.sanitized.log)。报告签署时根38窗口仍RUNNING，保持该时间边界。
- 独立真实产品失败：[冷UNKNOWN表单1FAIL](independent/fourth-cold-hydrate-failure.sanitized.xml)、[当前local投影3FAIL](independent/fourth-prefix-projection.sanitized.xml)、[初始cycle/state重哈希2FAIL](independent/fourth-rehashed-initial.sanitized.xml)、[Case动作上下文4FAIL](independent/fifth-cross-case-capture.sanitized.xml)。配对stdout、source manifests、修前源码/VM快照都在同目录。
- 独立两个自身oracle原FAIL：[22PASS/2FAIL](independent/fourth-extra-probes.sanitized.xml)、[同ID修后2PASS](independent/fourth-oracle-retest.sanitized.xml)。第五30PASS及第六226PASS另窗保留。
- 原standalone Node：[exit1 stdout](independent/unknown-handle-capture.sanitized.log)、[run](independent/unknown-handle-capture-run.sanitized.json)，原probe字节/原argv修后[exit0 stdout](independent/final-unknown-handle-capture.sanitized.log)、[run](independent/final-unknown-handle-capture-run.sanitized.json)。这不是JUnit测试ID，也不计入226。
- 根原失败：[12ERROR](root/first.sanitized.xml)、[164PASS/6FAIL](root/third.sanitized.xml)、[404PASS/1FAIL](root/fourth.sanitized.xml)、[83PASS/1FAIL](root/sixth.sanitized.xml)。所有配对完整异常stdout未覆盖。
- 版本oracle：[11PASS/2ERROR](root/schema-oracles.sanitized.xml)、[修后3PASS](root/schema-oracles-corrected.sanitized.xml)，[旧十文件精确快照](root/schema-oracle-before/manifest.sanitized.json)、[最终逐处diff](independent/schema-oracle-final-static.sanitized.diff)。原创建票据和历史/权限/rollback断言保留。
- [全部逐件原件/导出manifest](archive-manifest.json)、[全部失败同ID映射](failure-map.json)、[源码冻结时AST/Node检查](source-freeze-node-and-ast.json)、[同源码字节绑定](source-freeze-node-and-ast-source-binding.json)、[原环境版本记录](final-node-and-ast.json)。
- `verify_delivery.py` 只读核对405源在工作区/源码commit/交付commit、原/导出/交付的archive字节、旧149归档字节和实际原origin/protected/当前独立branch/HEAD远端差异。正常push后的运行记录另见本环境 `.runtime/case-cancel-after-receipt/delivery-after-push-verification.json`。

## 有限边界

只实现纯本地人工合成流程 REQUEST_CANCEL→RECONCILING、独立RECONCILE、另行明确CONFIRM_CANCEL。UNRESOLVED保持RECONCILING。原事实和原取消限制保留，资源仍占容量，独立释放按原当前权限。不支持取消恢复、外部/隔离效果、关闭历史或完整Case生命周期。

历史worker Case_count0根因仍UNCONFIRMED；没有补回缺失原stdout/Run状态或放宽lease。旧39API stderr缺失和既有atexit诊断保留前片披露。浏览器NOT RUN、0次启动/替代重试；原 `Chromium data: navigation ERR_BLOCKED_BY_ADMINISTRATOR` 拒绝保持。Windows/native、全仓/全AT、生产迁移/部署、真实模型/付费调用NOT RUN；无凭据/网络配置、生产Grant扩大、force push或protected分支写入。

249件冻结导出，原3465991字节/导出3461260字节、0gzip；archive-manifest SHA256 `6c24677c7a2b27c330d4da2b714f66561ec68ef44ecb962bccec42b413137096`。精确55静态白名单SHA256 `902d0e18361454d70f7d925b441e5b04d800917f7cd986ed28a66d1326435a96`；failure-map SHA256 `3a7c38d7e1fc68ea24b5d183486d532b1655d67138f93f7da918aabdab371a25`，34原FAIL/ERROR occurrences、34唯一ID，每个另窗同ID PASS，原件不改写。最终38进程1562.358秒、JUnit suite1560.155秒、pytest1560.20秒，两个原警告保留，无atexit诊断；唯一SKIP原native Windows gate。

原signed REVIEW签时RUNNING字段保留。后续独立归档审计另附 [ARCHIVE_AUDIT.md](ARCHIVE_AUDIT.md)、[机器记录](ARCHIVE_AUDIT.json)，它们在249件冻结输入外，不递归纳入原manifest。正常push实测结果以运行核验为准；源码/授权范围不因归档签收扩大。

新增18件审计支持另见 [support manifest](audit-support-manifest.json)，不计入249：三个独立扫描程序/日志/run的实际exit1、1、0，以及结果、签署报告和组装诊断均保留。`build_audit_support.py` 只导出精确清单，三个程序按独审批准的原SHA逐字节复制；其余沿已签收日志/JSON政策处理。交付核验另外比较全部18件原/导出/commit字节。报告内 documentation hashes 是签署时的快照；签署后父任务仅新增此支持索引/导出helper及交付核验支持文件比较，不改变405源码、249归档或独审原报告。

组装stdin的 [库存说明](audit/archive-audit-signoff-assembly-inventory.sanitized.log) 是解释性记录；[原工具stderr转录](audit/archive-audit-signoff-assembly-original-stderr-transcription.sanitized.log) 明确是事后按会话原输出准确转录，非进程直接捕获、非重新运行。[来源](audit/archive-audit-signoff-assembly-original-stderr-provenance.sanitized.json) 和 [capture status](audit/archive-audit-signoff-original-stdin-capture-status.sanitized.json) 明确原stdin文件NOT_CAPTURED，原命令/结果保留在工具会话。没有把该缺口改写成完整原始捕获或JUnit测试。


归档暂存完整 `git diff --cached --check` 实际退出2，66行保留证据空白（36行原pytest失败正文、30行原独审静态diff空上下文）；原日志/XML字节与hash保留，没有修剪或修改Git whitespace配置。排除原root/independent证据正文后的所有新写文档/helper/metadata检查实际退出0。完整原输出见 [cached-diff-check.json](cached-diff-check.json)，不把该失败检查称为PASS。
