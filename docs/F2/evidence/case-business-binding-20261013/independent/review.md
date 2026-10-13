# Case cancellation business binding 独立审查：限定 PASS

冻结 `b15e23d2b9808394ba1fe21942bd289288a9a3ac`，沿用 gpt-6.1-sol / medium。本审查只读源码，仅在独审运行目录写证据；无 PG、IPC、网络、OS身份、凭据或ACL动作，未改代码。

独立纯反例 **11 PASS / 0 FAIL / 0 ERROR / 0 SKIP**。根已有 XML **35 PASS / 0 FAIL / 0 ERROR / 0 SKIP** 单列核对，没有重跑或相加；原27/114也未重复。3文件冻结hash前后及当前源码一致。

22行表/列权限完整覆盖精确原 `cc.read/recover/cancel` 路径：八表SELECT*对应原查询与ledger RETURNING*；七项列级SELECT含过滤/排序/join所需列；四项UPDATE含preparations.revision、service_dispatches.revision技术锁权限及cases.state、local ledger四列原写；三项INSERT完全对应原提交和API拒绝审计。principals权限保持只读正确：Store.auth使用shared advisory锁，不取identity行FOR SHARE。详尽映射见static-checks.json。

绑定强制businessrole与nativeapp、writer、installer/owner四者不同；固定完整spec digest、DB endpoint/OID/system_identifier与Source，check_spec重建比较不接受变更。private DSN仅校验精确五字段，拒绝discovery overrides，既不保存也不返回密码/DSN。原Case/preparation/revision和恢复key精确校验，不合成source/lifecycle/hash/reason，原API继续负责current auth、owner、材料、显式确认及事务。观察永远DECLARATION_VALIDATED_ONLY/NOT_RUN，授权布尔均false；src下没有新增模块的自动API/Store挂接，也没有发放live authority。

**无阻断代码发现；限定PASS仅签纯声明接口及静态最小权限映射。** CONNECT、schema USAGE、builtin EXECUTE、实际SQL grant/inheritance/ownership、应用连接身份和原Case事务仍需未来真实验收。技术锁UPDATE列也是真实SQL写能力，不能将列清单称为SQL逐Case权限隔离或RLS证明。实际host/IPC与businessrole/ACL **NOT_RUN**，审批授权未发行。

此审查未涵盖尚未出现的HostCaseCancelTrialApproval草稿，不授权任何runner、用户/组创建、凭据或ACL动作。自有反例及完整结果原件保留在test_review_probes.py、results.xml、stdout.log。
