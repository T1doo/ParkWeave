# 原注册步骤局部修订正常整合

原dev基线 `ee646825b2bb9a00418b7a708e6b638187f61da2`，先行合同 `da1a89ee21c89a0fbf0ae8f3b9c749c1eb409f7e`。精确运行源码 `d12afaa6258dd89a539e3a859b965ca9441e2111` 先普通候选推送后独审LIMITED_PASS，报告SHA-256 `449785c57cf290763d17c0e9cb91b449285efe58909743952ec5ee12b8f17bda`。根104PASS、独审45/5/24/4/1五窗各自自然exit0，343源首尾零漂移；旧ecf5/3cda/5bc5 BLOCKED原证据与限制保留。

候选证据/文档HEAD `bcc608e1d463d8abd19007a4422166eec9ba5ebe` 普通push成功，343源与获审d12字节完全一致，后续变化仅docs。正常显式fetch核验dev仍ee646、main仍 `31e7acb7e53bb1ab6465b9daae59de28757f7583`、候选bcc608；已知 `88403af18b95b361114b303c3fae636f286d91b4` 为dev祖先。Gitclean，无index/merge/rebase/cherry-pick挂起；平台空锁inode1310816在/proc/locks不持有且未触碰，原main-only fetch config未改。

独审解除冻结后切原dev，仅git merge --ff-only获审候选并正常git push origin dev/f1-foundation。实际远端FF时点dev与候选同为bcc608、main31e7acb不变；源码343路径零漂移，Gitclean。见[实际快进时点核验](evidence/registered-local-revision/integration-ff-verification.json)。本整合记录与公开hash更新随后仅docs提交/普通dev推送；最终实际HEAD见私有 `.runtime/registered-local-revision/final-remote-verification.json` 与交付回复，避免自包含提交SHA循环。没有获审后的源码改动或重复无必要测试。

[功能范围与失败史](RegisteredLocalRevision.md)、[机器证据](evidence/registered-local-revision/verification.json)说明原页面显式局部采用、原锁/CAS/幂等、冷热只GET、实际自有PG/API重启及隐私边界。完整AT25/一般动态图/全仓/Windows/真实履约/正式Release/Case完成仍未签收；新PID默认关闭探针不冒充未消费Approval账本生命周期验收。原资料导出/异议不重做，旧a823a28未迁移。无新Grant/角色/Schema/政策审批、自动停表或资源释放、模型/真实业务/外部通知；未改main、强推、部署、凭据或安全网络配置。

所有失败原始XML/log及旧BLOCKED报告留忽略0700运行目录，未覆盖。公开封存证据63份/62hash锚，加入本实际FF核验后为64份/63hash锚；仅安全结构报告、通过日志/测试源码/原页截图公开。最终未推送内容仅忽略的私有运行日志/探针，不遗留未推送源码或非忽略交付文件。
