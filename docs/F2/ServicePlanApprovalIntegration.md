# 原首次资源交付方案 Approval 正常整合

从已推dev `3406fd9c62bf1f28fd1e7ef62932d8acd1b3a386` 建立独立候选 candidate/service-plan-approval-20261010，未在main开发。普通fetch实际验证已知88403af18b95b361114b303c3fae636f286d91b4为祖先。8c52f07f2ddec7039d92be8d9794d1a393511bdc先冻结合同；318a4f103c7fc7560125c6a73381c4f22989090c先补独立head；05efd323c9762e7e6a29260c159552ab24114b0b先冻结原P2消费证明；1f32db63671fd21bb7912198d49d65b459dd6b8c先冻结来源PG row_version防ABA。对应实现冻结为 `11b756db4e164fafb7756ec63bffb286178e0a73`，普通推送后才交独审，未审没有合dev。

精确11b独审LIMITED_PASS。根14个完整相关模块524PASS/0FAIL/ERROR/SKIP，JUnit540.769秒、受控542.552443秒；独审11模块443PASS/415.815秒、受控417.424641秒，另API17PASS/33.576秒、受控34.890835秒，浏览器8PASS/27.655秒、受控28.961214秒，均exit0且无失败/跳过。328源首尾及整合零漂移，manifest SHA256 48c99bad9420ddd3976fa3498b7d4ef5d65fc40be2a5a14d3bbe428956d188ec；独审报告729592298b8f2e02b2baa056bdd09b90d5d71b3ced7f9a64eefb007cd1c5eb4b，公开副本与私有原件一致。开发46/14/55/6等窗口只保留各自未提交范围，不作最终验收。

安全证据文档提交 `d2d685a0a089d438d47204e18713dad4b8cb5265` 已普通推送；普通fetch/实际ls-remote确认候选d2、dev仍3406、main31e7acb7e53bb1ab6465b9daae59de28757f7583后才正常--ff-only快进dev至d2并普通push。实际ls-remote随后确认dev与候选均d2，main不变。本文与integration.json为其后纯文档提交，最终dev SHA以交付回复及私有final-remote-verification.json为准，避免递归自引用。无本地main分支、无强推/部署/凭据/安全网络配置改动。

末尾读取候选tracking ref曾报unknown revision：当前默认fetch仅追踪main，没有对应remote ref；原错误私有保全，用无force的显式refspec普通fetch补候选/dev/main，实际核对一致，未改fetch配置。无挂起merge/rebase/cherry/revert/普通index.lock，平台空未持有codex-index-refresh.lock inode1310816原样保留。此前测试与独审所有受控窗口自然结束，根观察到的两个控制进程身份已退出；该观察器没有捕获PG进程，不能据它声称PG重启验收。

真实HTTP/PostgreSQL/Chromium1200/390/320合成页面验证明确提案、批准、撤销、原效果消费、冷GET恢复、撤权/越权/跨企业/换版/并发/迟到/重复及隐私。8个已批对象1consume+7显式revoke共24合法事件，64为配置上限而非可达实测耗尽。新Store/新App同原签发fixture capability与冷浏览器覆盖，新的candidate API进程或PG重启不签收；目录publisher最后source读取至COMMIT非协作窗口仍OPEN。未防可信owner同时篡改全部独立锚。正式Release/独立业务审批角色/任意资源路由/在途兼容/fullrepo/fullAT/Windows未签收，Server CI未查询，旧a823a28未迁移。

候选真实能力默认关闭。仅合成setup增加两个候选列/固定不可变前缀触发器，不接生产迁移，无新Grant或角色，不执行真实业务、政策审批、真实资源预约、外部通知、模型调用、部署、Case完成或分享。原资料异议闭环和资料包导出已完成，不重做。

入口：[范围](ServicePlanApproval.md)、[合同](ServicePlanApprovalContract.md)、[机器核验](evidence/service-plan-approval/verification.json)、[独审](evidence/service-plan-approval/independent-review/report.json)、[整合记录](evidence/service-plan-approval/integration.json)、[100私有工件快照](evidence/service-plan-approval/private-artifacts.json)。公开仅安全报告、最终通过日志/XML、补充probe源码与三幅合成页面图；失败原件及其哈希私有保全。最终未推送文件仅忽略的.runtime原始日志/XML、harness/probe/草稿/截图/状态和后续远端辅助记录；源码与公共交付全部普通推送。后续辅助不伪装进入此前100文件快照。
