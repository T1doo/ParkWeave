# 逐实例模板升级检查正常整合

从实际已推 dev `b496f6a4da7022c10c906ff722fd3279f4536f71` 建立独立候选 `candidate/template-upgrade-check-20261010`，未在main开发。先只读核文件、HEAD/状态、默认网络、挂起操作和锁，读取现有运行说明与原产品§7.5/F2-T06/冻结需求映射，核已知 `88403af18b95b361114b303c3fae636f286d91b4` 为祖先，不假定旧环境共享。原资料包导出、资料异议闭环不重做，旧a823a28 Windows修复未迁移。

4b82672先冻结检查/选择的有界存储合同；首开发窗21FAIL/1PASS发现原consumer历史键不能被原计划证明接受，先7cc83a7补合同再修，新键改规范形式、旧首ADOPT仅精确历史兼容，旧event字节不改。e83021dd02292061332b3e50c0264c35da340e2e虽根/独审完整相关模块各314PASS，仍被真实末事件reason/choice与payload/hash改写、原body锚保留的两项FAIL阻断。私有探针初窗13ERROR是缺原fixture的观察器故障，另窗修正13PASS不能抵消产品FAIL；报告BLOCKED保留、不覆盖。1542ec5先冻结原Selection正文重建合同，最终源码 `076625a357fe9631cccb923132dad3cd224db48e` 核对重建fp与两个原body锚、严格revision/FLAGS类型，拒绝损坏历史，不修写正常旧历史。旧BLOCKED HEAD当时未单独整合，最后只快进已修复且获审的后代。

最终同076源码，根完整10相关模块318PASS，JUnit256.680秒、受控258.567393秒，自然exit0。独审10完整模块318PASS/253.948秒（受控255.493853秒）；额外API15PASS/26.948秒（28.295560秒）及页面7PASS/26.829秒（27.951830秒）。三独审窗全部自然exit0、0FAIL/ERROR/SKIP，本SHA无观察器故障；分窗记录，不合称一次总分、全仓或正式AT。独审原报告LIMITED_PASS，SHA256 `b56dba7dd1a98cf69f1072b303d46babc79298b6da684ad8289848126738e732`；335源码首尾零漂移，manifest SHA256 `da4de8663fe847f132a9e4b48c780bd32dd3a5ee98221688906306aad774e018`。1448诊断AST白名单只为安全标识，不能称Windows验收。

真实HTTP/PostgreSQL/Chromium包括：四分类、原资料/请求/锁变化、原合成占用/接单/回执全行保留、当前撤权/跨企业和角色隐私、精确legacy边界、真实64最后槽双HTTP CAS与幂等、事件/body锚损坏拒绝、真实Case行等待跨目标期限403且零事件。320/1200页面实际原POST在途但显示未知，热/冷GET NOT_OBSERVED零重写，只有原POST迟到单次提交后GET COMMITTED；旧GET/POST不能覆盖新Case/身份，撤权恢复清私有视图。原数据库业务/权限行（独立authorization_audit除外）、原consumer和template字节均保留，不把选择记录解释为升级执行或完成Case。

076源码先普通推送候选，独审实际ls-remote核candidate076/devb496/main31e7。获审后只文档/安全证据提交 `dbe04b3588917b5c67615d0d79b5229fb729a388`，普通推送候选；显式无强制refspec正常fetch candidate/dev/main，原remote.origin.fetch仅main不改配置。整合前实际ls-remote核candidate为dbe04b3、dev仍b496、main仍 `31e7acb7e53bb1ab6465b9daae59de28757f7583`；Git干净，无挂起merge/rebase或Git锁，平台空且未持有的codex-index-refresh.lock保持inode1310816未动，335源码无漂移，076后只有docs变化。随后正常`--ff-only`整合并普通push dev，实际远端核candidate/dev都为dbe04b3、main仍31e7。本记录与integration.json另作纯文档提交普通推送，最终dev SHA由提交后的私有final-remote-verification.json及最终答复给出，避免文档递归记录自身SHA。

只在原默认关闭的显式隔离组合、原合成主体/企业/fixture DB范围提供逐原实例检查与独立SQLite最多64不可变明确选择。KEEP_CURRENT保留旧版；REQUEST_RECHECK是提出重验意向；ACK_COMPATIBLE是确认检查结论。它们均不迁移、不重绑、不改原Case/资料/计划/预约/回执，也不回滚已发生业务效果。没有生产路由、生产迁移、新Grant/角色、凭证复制或真实发布。旧superseded/withdrawn修订只作精确历史依据，目标必须为同模板有效当前发布头；提交前实际PG等待后再查期限，未决仍未决。

受控测试/API/PG子进程使用minimal_environment。原目录/Approval真实不同API PID和自有PG重启模块在本SHA相关窗再次通过，范围仍为已消费证明只GET冷恢复；未消费Approval新进程写仍403，旧cap在PG重启后DENIED，不重新签发或复制fixture凭证。新升级选择的跨PG/模板SQLite/consumerSQLite迁移原子性、未来持续有效和可信非协作owner改全部独立锚均不在保证内。正式ServiceRelease/ParkInstance、生产主体/独立审批/维护/安装权限、升级迁移执行/在途回退责任、完整新企业F2和AT27迁移仍缺；真实业务/政策审批/履约/通知/分享/模型/Case完成未实现或未授权；全仓、完整原AT/EX/Windows未验收，ServerCI未查询。

入口：[范围与失败史](TemplateUpgradeCheck.md)、[实施前合同](TemplateUpgradeCheckContract.md)、[机器核验](evidence/template-upgrade/verification.json)、[精确独审](evidence/template-upgrade/independent-review/report.json)、[正常整合记录](evidence/template-upgrade/integration.json)、[工件hash](evidence/template-upgrade/artifact-hashes.json)。源码和公共安全证据均普通推送，无main修改/强推/部署/安全网络或凭据配置修改。未推送仅忽略.runtime里的原失败/通过日志/XML、harness/probe/截图、草稿和辅助状态；公开私有工件清单为生成时点hash快照，不声称后续辅助状态永久不变。
