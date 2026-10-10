# 有界 Case 事实来源正常整合记录

从开发基线84af2948abc32415aaf6d7a4439e0596e0014405继续，冻结合同后独立候选开发。首轮3b5785b独审BLOCKED的空账本降级问题未合dev；保全证据，85b21ba先冻结SQL/JSON一致性补充，再由dded6b0e450dfcabda0baef0ace3cbfd386b7fa1修复。新精确候选282e0be4a0e4ae74139a642c7eb8e13a11197105获得独审LIMITED_PASS。

根最终12完整模块431PASS/0FAIL/ERROR/SKIP，270.782秒；独审9完整模块354PASS加11独立真实PG/HTTP探针11PASS，同次365项0FAIL/ERROR/SKIP，188.510秒（受控实际190.340秒）。两次独立计数，不加总成全仓或正式验收。318路径首尾及整合后哈希一致；review后只增加证据/计划/本整合文档，不再修改运行源码，因此未重跑相同测试。先前971项与424项仅各自旧字节窗口；所有故障私有保留，安全审查摘要可公开回读。

普通推候选及核远端后，重新fetch开发分支，仍为84af2948；核88403af18b95b361114b303c3fae636f286d91b4是祖先、main未变、worktree clean。将含独审证据的e7550cfdd14d38f6c1130be1ce7396b7c6e72b24正常--ff-only整合dev并普通推送。2026-10-10 03:48:36 UTC实际ls-remote确认dev与候选均e7550cf、main仍31e7acb7e53bb1ab6465b9daae59de28757f7583。本文及integration.json属于随后纯文档提交，最终dev文档SHA以交付回复与Git远端为准，不冒充递归自引用的提交SHA。

资料包导出与原资料异议闭环保留；本片固定OWNER_CASE_USE_ONLY和原合成角色/字段范围。JSON/SQL证明检测部分损坏，不是管理员同步改写全部记录的防篡改签名。无新Grant、模型、外部通知、真实业务、政策审批、Case完成、main修改、强推、部署或凭据/安全网络变化。未签收完整一般FactBundle/多用途分享、ServiceRelease/Approval、全仓/原AT/EX、Win11；旧a823a28 Windows Job/accounting未迁移。

机器证据：[integration.json](evidence/case-fact-bundle/integration.json)、[根测试](evidence/case-fact-bundle/verification.json)、[独立复审](evidence/case-fact-bundle/independent-review/review.json)、[首轮阻断](evidence/case-fact-bundle/first-independent-review/review.json)。未推送文件仅忽略的.runtime原故障日志、私有测试wrapper/probe及UI草稿；运行源码及公开交付文档普通推送，最终worktree/远端再核。
