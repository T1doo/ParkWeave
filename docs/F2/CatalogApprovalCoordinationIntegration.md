# 合成目录 / Approval 协作正常整合

从实际已推 dev `2e77e408cb761e86e9f4808159569075fa600063` 建立独立候选 `candidate/catalog-approval-coordination-20261010`，没有在 main 开发。最初只读核验文件、实际HEAD/状态/默认网络、挂起操作与锁，读取现有README/运行说明/项目规则及原Approval/目录/临时PG权限合同。正常fetch核验已知88403af18b95b361114b303c3fae636f286d91b4为祖先，不假定旧实例或环境共享；原资料异议与资料包导出不重做。

0296d76b99b9442a11587efc309f9eb898bd89a8先冻结共同版本/锁及实际重启合同，ec05初次实现；a6acf4b5a7f8212e448052ed84224e3b2f99c108先补未绑定bridge失败关闭，2cc普通候选推送后独审实际激活死锁BLOCKED。bc3fd2c2a8341ecf831d1f55d4df0ee7feda93b7先补source-key→DDL顺序，07修后仍被不同原目录键首次安装DuplicateColumn实证BLOCKED。591ed3001fb666855aece22678fed22dc9d00935先冻结源键→owner关系安装锁→schema重读；对应最终源码 `20c0a568312e53c1c926927eda6d11c607c8e44e` 仅加该安装锁与真实同/不同键/重复setup回归及AST白名单1430。两个BLOCKED HEAD在当时均未单独整合；最终只以获审HEAD快进dev，普通推送最终候选后才重新交独审，未强推。

最终同一源码SHA：root先3个完整模块79PASS（JUnit33.025s，受控34.269520s），再其余15完整模块503PASS（584.543s，586.276273s）；18模块/582个唯一通过，两窗无重叠。独审3完整模块79PASS（48.806s，50.097374s）和其余15完整模块493PASS（595.665s，597.647948s）；18模块/572个唯一通过。独立额外API11、页面7、安装边界6、新API写关闭1，共25PASS。全部最终窗口自然exit0、0FAIL/ERROR/SKIP，业务边界通过真实HTTP/PostgreSQL/页面验证，完整诊断模块另有覆盖；不合并为同次测试、不声称全仓。独审原报告结论LIMITED_PASS，SHA256 `33d5d095951fb09e88daf273a2fdceb79c765885e58fb29a645d6e639ec871e1`；331源码零漂移，清单SHA256 `4c8710f177f372c096420c21791d2730a1476f5ed1f93bda1154372697fb3a70`。旧两次产品故障及观察器故障原始日志/XML私有保全，公共只发布安全故障报告/摘要/hash，最终通过窗口导出原日志/XML。

断联提醒期间实际命令通道可用、Git干净、331源零漂移，当前148份私有日志/XML/辅助记录做了带时点hash快照，不重启写入者或因通知重复挂起工作。root曾将“不重复长测试”误读成新源码不得补长窗；父任务随后澄清后，最终同20c先通过3个完整短模块，再分别由root/独审补齐各自其余15完整模块；明确分窗，不把旧07完整580/570成绩转签新源码、不伪称同次总PASS。

最终源码20c先普通推送候选，独审实际确认远端candidate20c/dev2e77/main31e7且源码331零漂移。随后仅文档/证据提交 `6fcc4e30ba7f86e88a541dd430fe761889bc3443` 普通推送候选。使用显式、无强制refspec正常fetch candidate/dev/main（原remote.fetch仅main，不改配置），ls-remote核验candidate为该证据SHA、dev仍2e77、main仍31e7；Git干净、无挂起操作、平台空且未持有的codex-index-refresh.lock保留原inode1310816。然后正常`--ff-only`整合及普通推送dev，实际ls-remote确认candidate/dev都为 `6fcc4e30ba7f86e88a541dd430fe761889bc3443`、main仍 `31e7acb7e53bb1ab6465b9daae59de28757f7583`。本整合记录和integration.json另作纯文档提交、正常推送；最终dev SHA由提交后的私有final-remote-verification.json与最终答复记载，避免文档递归记录自身SHA。main无本地分支、无改动；无强推、部署或安全网络/凭据配置修改。

受控测试/API/PG子进程均用minimal_environment，只对测试本身新建确证自有的临时PG实际stop/start。新API不同PID、PG不同PID与postmaster_start、同system identifier/database OID均实际记录；原消费账本/head/回执/关联保留，冷认证后原交付只GET、P2/goal验消费证明，负例损坏后409。newFactory批准入口403/关闭、旧issuedcap在PG重启DENIED，无nonce重签/复制。自有重启夹具teardown验证postmaster.pid消失；不凭主pytest退出声称所有PG目录删除或Windows通过。

协作窗口只封闭固定合成owner发布/INIT与原Approval消费者。32可达事件实际跑到明确WITHDRAW32，保留历史、不自动恢复。应用preparation_catalog仍SELECT only，候选setup两个JSONB列/固定不可变前缀触发器，只原服务@1合成来源revision；无生产迁移、发布API、新Grant/角色或生产开启。可信owner无协作篡改全部独立锚、默认其它资源路由、未消费Approval的新进程写或PG重启后重新启用不在保证内。正式ServiceRelease/独立业务审批主体/一般DAG/在途兼容/真实发布/政策审批/履约/预约/通知/分享/模型/Case完成未实现或未授权；全仓、完整原AT/EX/Windows未验收，Server CI未查询，旧a823a28未迁移。

入口：[范围与失败史](CatalogApprovalCoordination.md)、[合同](CatalogApprovalCoordinationContract.md)、[机器核验](evidence/catalog-approval-coordination/verification.json)、[最终独审](evidence/catalog-approval-coordination/independent-review/report.json)、[整合记录](evidence/catalog-approval-coordination/integration.json)、[工件hash](evidence/catalog-approval-coordination/artifact-hashes.json)。源码与公共证据全部普通推送；未推送仅忽略.runtime中的原失败/通过日志/XML、harness/probe/草稿、截图、状态与远端辅助记录。私有工件清单是生成时点快照，后续状态/辅助另记，不伪称全部文件永不变化。
