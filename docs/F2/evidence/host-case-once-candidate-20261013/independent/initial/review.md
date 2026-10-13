# 未提交 host→Case helper 只读独审：BLOCKED

当前reviewed-source-manifest.json固定三helper、workflow及关闭approval快照。没有导入/执行helper，没有测试、runner、权限、身份、随机凭据、SQL/PG/IPC或网络动作；沿用gpt-6.1-sol / medium。只能签静态检查。

四项仍需解决的阻断：

- **HC-01 Accounts removed before failure-retained secret tree**（scripts/host_case_once/controller.py:235）：cleanup deletes created users/groups, then removes T only when error==NONE. On any acceptance error the writer-owned bootstrap.json and PG-owned init-password/data stay while owning identities may be deleted. Secret-bearing orphan UID/GID paths remain. 修正要求：Preserve safe failure diagnostics under root-private ownership, then remove or root-protect all secret-bearing UID-owned new paths before deleting identities. Do not sign identities/files cleanup complete when that ordering is unresolved.

- **HC-02 Bootstrap controller timeout lacks retained-resource cleanup fallback**（scripts/host_case_once/bootstrap.py:149）：Timeout path terminates/kills only the controller; exception path logs failure and returns. Controller disables its alarm before cleanup, and inherited call uses select then blocking readline. A stalled cleanup/partial frame can exceed the grace and leave owned PG/API/writer children and newly created accounts/groups. Prepare/start failures also retain T without a defined safe fallback. 修正要求：Add bounded complete-frame I/O and an explicit retained-instance bootstrap/controller cleanup protocol with deadlines and fail/unknown reporting. Preserve diagnostics, refuse unknown deletion; never imply controller termination cleans descendants/accounts.

- **HC-03 Protected copy dereferences source symlinks before checking copied objects**（scripts/host_case_once/bootstrap.py:120）：shutil.copytree(...,symlinks=False) and copyfile read source/link targets first, while lstat protection only checks resulting target nodes. It cannot enforce approved refusal of source symlinks or original owner/mode/source provenance. 修正要求：Validate each original source and ancestor with lstat/root ownership/nonwritable/regular directory or file requirements; reject symlinks before copy and retain bounded complete protected-source checks.

- **HC-04 Fixed persistent claim outside approved new T**（scripts/host_case_once/bootstrap.py:24）：CLAIM is /tmp/parkweave-host-case-security-once-20261013.claim, written before creating T and never removed; current action checklist limits mutations to new T. O_EXCL/no-follow600 improve safety but do not extend user authorization. 修正要求：Move claim under approved new T or explicitly list this exact extra object and lifetime in the pending approval before execution.

早期确定缺陷“未保存owned store，导致SNAPSHOT/DROP失败”已由根侧在审查期间修复；保存快照包含owned['store']=owner，故它不冒充当前未修缺陷。未执行验证。

正向静态检查：默认approval false/null、单次repo/branch/push/number/attempt与25分钟门禁、closed公开输出、原SQL角色/Store分离、原proof复核、retainedPopen/start实例保护、故意丢弃单次POST响应后只GET原key均存在。CANCEL_DROP是在TestClient已经返回后丢弃响应；真正controller RPC超时/worker死亡会中止，不应签其恢复语义。当前结论BLOCKED，不具备最终源码冻结或执行资格；后续改动需新快照复审，原缺陷原件保留。
