# ENG045：SESSIONS owner 方案与定点恢复等待

仅本地工程收敛，基线 e0bdf84；最后已验证远端为 8da8e4a。没有新 CI、push、全量回归、SetOwner/chmod/ACL 执行、真实模型请求或预算消耗。原环境、恢复包和历史保留。

## Windows 所有者：观测与创建路径

ENG044 唯一 Server run [37450539320](https://github.com/T1doo/ParkWeave/actions/runs/37450539320) 报 Setup `SESSIONS/ACL_OWNER_MISMATCH`。严格只读检查要求文件 owner SID 等于当前用户 SID；实际 owner SID 没有观测，不能指定为 Administrators、SYSTEM 或任何账户。检查在 owner 比较处拒绝，因此本次 SESSIONS DACL、后续 CONFIG 均未验证。

`scripts/windows/lifecycle.py` 对新 ROOT 显式设置当前用户 owner 并配置继承 ACE；`src/parkweave/cli.py` 对 session 文件使用 `open("x")` 排他创建，随后已有 `os.chmod(0o600)`，没有显式 Windows owner。当前轮未执行这些权限操作。

新对象的默认 owner 来自访问令牌 TOKEN_OWNER，可为用户或组 SID，并不保证等于 TOKEN_USER；父目录 ACE 继承与 owner 选择是不同机制。Runner 的管理员/UAC 元数据读取不改变令牌默认 owner。本轮未读取实际 TOKEN_OWNER，因此这一机制解释可能路径，不是本次具体身份的证明。来源：[TOKEN_OWNER](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_owner)、[Windows 文件安全与访问权](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)。Python 在 Windows 上的 chmod 仅支持只读标志，不能落实 SID 所有权合同，见 [Python os.chmod](https://docs.python.org/3.12/library/os.html#os.chmod)。

## 最小候选与用户审批文案

候选仅在 Windows 首次排他创建 `.runtime/synthetic-sessions.json` 时，把**该新文件** owner 设为当前创建用户 SID，成功只读验证后才写 token 正文。优先使用创建时安全描述符；若采用创建后 owner 设置，应使用已打开的新文件句柄，防止路径替换。已有文件继续拒绝覆盖，不处理 ROOT、CONFIG、其他对象或递归权限。

只改变 owner，不改变 DACL/SACL、继承或其他主体权限；需要该对象的 WRITE_OWNER，不启用额外特权。Windows 的 owner 设置权限条件参见 [SetNamedSecurityInfoW](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setnamedsecurityinfow)；候选实现应使用句柄接口，而不是可被替换的路径。风险是句柄指错、权限不足以及 owner 元数据变化本身；失败须在 token 写入前拒绝。当前没有足够证据要求放宽 DACL 或变更 CONFIG。

可供用户确认的授权范围：

> 授权仅在 Windows 首次排他创建 `.runtime/synthetic-sessions.json` 时，将该新文件 owner 设为当前创建用户 SID 并只读验证；保留 DACL/SACL、继承及其他主体权限，不启用额外特权，不修改已有文件、ROOT、CONFIG 或其他对象。设置失败即拒绝写入 session 正文；不自动 push 或运行 CI。

这是待确认方案，本轮未实现或执行安全变更。

## 精确目标与受控等待

最后原子记录为 `pytest_call` / `test_plan_revision::test_after_artifact_and_terminal_run_outbox_atomic_recovery_no_new_call`，仅表示最后成功记录，不定位具体挂点。原测试定点运行 1 PASS（0.98 秒）；同步 MockTransport、PG 事务与恢复路径没有自身的子进程、线程池或重试等待循环，也未发现必然锁环。TestClient 有 portal 线程。Store/配额连接原先仅有连接超时，外部 SQL 持锁可无限等待；这不是实际 Windows 600 秒原因的证明。

目标模拟 revision2 artifact 写入后的异常，验证连接已关闭、事务回滚，Run RUNNING、op VERIFIED、只有前置 artifact、两份配额 reservation、无成功 outbox。过期 lease 后重新 claim，恢复使用已验证的 PLAN/FEEDBACK，不重复 provider/配额请求，最终两个 revision 和恰好一个 SUCCEEDED outbox。

新增显式测试 fixture 为该目标及新受控探针的 app/owner DSN 追加 1 秒 lock_timeout、5 秒 statement_timeout；API 和直接配额连接继承相同 DSN，monkeypatch 在测试后还原。不 ALTER ROLE/DATABASE，不改变产品超时或所有测试。重新生成现有诊断 ID 白名单包含四个新增函数，参数仍不公开。

受控真实 PG 探针持有自有 run 行锁，通过自有 application_name 的 pg_locks 观察子进程等待：旧 DSN 等待直到锁释放后成功；有界 DSN 在 4 秒内以 LOCK_TIMEOUT/exit3 失败，保留恢复状态，释放锁后使用同 claim 恢复成功。另验证 principal 锁下 API 在 3 秒内拒绝且释放后 GET200；配额账户锁在 3 秒内 QUOTA_DENIED、零发送/预留，释放后可 reserve；自有 pg_sleep20 在 7 秒内取消，后续新连接可查询。

仅探针启动一个直接自有 Python 子进程，用 MockTransport/FAKE_TOKEN；所有完成或 finally 清理等待均先释放自有 blocker，只对该 Popen terminate，3 秒仍存活则 kill，再有界等待。没有全局进程扫描、产品 JobObject 或清理权限变化。

## 验证与保留结论

初始目标加探针 6 PASS/11.11 秒；最终整个 plan_revision 模块、新等待探针和可信 ID 精确匹配检查共 **26 PASS、0 FAIL、2 既有 warning，17.56 秒**。这不是全量成绩。XML 与三份最终源 SHA256 见 [证据](evidence/eng045-targeted-recovery.json)，本地原始 XML 在 `.runtime/eng045-*`。独立只读复核无实质阻断，建议的仅自有 child kill fallback 已补入最终验证。

600/900 秒、Windows 权限/身份、产品模型链和 workflow 未改。Windows 实际挂点仍 UNKNOWN；SESSIONS owner 候选待用户确认及后续专门验证。OWNED_REGRESSION_DESCENDANTS 仍 OPEN，PGStop 成功不代表所有后代清理。F1/F2 未签收，Server≠Win11、36AT6EX NOT_RUN，R4 关闭。
