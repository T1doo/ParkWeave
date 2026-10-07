# ENG100 Windows 生命周期 generation / protected authority 候选

本轮完成独立、默认关闭的协议模型 `src/parkweave/windows/lifecycle_generation_candidate.py`。无 production factory、无 lifecycle 接线，无 Windows/native 创建、进程启动或终止、owner/DACL 修改、环境授权、workflow 恢复。`GenerationCandidate()` 的所有入口首先拒绝 `MISSING_PROTECTED_AUTHORITY`。显式 `for_protocol_tests` 只接受 `FAULT_INJECTION` 或 `ISOLATED_PROTOCOL_TEST`；这不是受保护服务部署证明。

## 现有生命周期与不变边界

现有 [`scripts/windows/lifecycle.py`](../../scripts/windows/lifecycle.py) 初次创建 `.runtime/windows-processes.json`，后续 execution binding 使用 `.process-binding-UUID.json` 和 `os.replace`（235–243、428–430、461–479），status/stop 从固定路径重读记录（533–557）。候选不覆盖此 identity 文件，不修改 paused helper，也不重试 ENG099 的非 CAS rename。现有 session 文件 `.runtime/synthetic-sessions.json` 和 config 仍由原代码创建/读取；候选只绑定它们的摘要，不重新生成凭据、不迁移它们、不宣称摘要本身证明读取来源可信。

原有 [`scripts/windows/server_identity.py`](../../scripts/windows/server_identity.py) 中的 `bind_server` 对 launcher/server 的 PID、创建时间、命令、根/直接子进程关系和借用句柄的校验应保持。候选事件中的 process 字段只是协议绑定值；真实 handle 授权、停止与退出证明没有实现。`process_actions` 始终拒绝，旧 PID、旧 STOP 或旧 session 不能由此触发进程动作。

## 为什么现有同 User 模型不能独立完成修复

Windows access check 使用 token 中的 SID/group 与对象 descriptor。同一 User 的攻击者不会因新 UUID 文件名而成为另一个安全主体；当前给该 User 的文件控制权限不能区分“此应用”和“同 User 的另一个进程”。本轮没有测量或更改现有 token、process descriptor 或目录 ACL。[Access tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-tokens)、[Access control model](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-model)

追加文件、CREATE_NEW 和哈希链可以检测与可信摘要不一致的内容，却不能阻止同权限者删除最新代、修改旧 inode 或重放完整旧链。DPAPI 通常允许相同登录凭据解密，它不能单独提供本应用专属的单调 current authority；本地 mutex、bool attestation、独占 UUID 或本进程私钥也未建立独立安全边界。[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

真实 authority 若在独立进程中，还必须证明攻击者不能读取/写入其内存或复制其关键句柄，并验证调用者及生命周期进程的实际身份。Windows process 权限包括 VM 和 DUP_HANDLE；本轮未证明这些隔离条件。[Process security and access rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)

## 文件布局与协议

测试 namespace 是全新 UUID 目录。平面布局为 `identity-root.json` 和 `gen-<epoch UUID>-<全局序号20位>-<SHA256>.json`。每个文件仅 CREATE_NEW，候选不覆盖、rename、删除或扫描目录选取“最新”文件。Linux `SyntheticFileStore` 是普通文件 fixture，既不设置私有权限，也不证明 Windows 文件保护。

RootBinding 钉住 root 的 volume/file identity、原始 canonical bytes 摘要，以及 config/session/source/permissions 摘要。每代绑定 root UUID、事件、epoch/session、API/WORKER 精确进程字段和上一代的文件名、identity、摘要。读取使用已授权 checkpoint 的精确引用，逐项验证 chain、序号和事件转移。当前代缺失/损坏或 authority 新鲜读取失败时直接拒绝；绝不退回旧 prefix。链上限 256，文档上限 32768 字节，超过即拒绝。

允许的生命周期为 `ROOT_CREATED → BIND_API → BIND_WORKER → STOP_INTENT → STOP_CONFIRMED`。绑定 server 只能保持 launcher 身份并添加同 PID/创建时间或精确直接子进程关系；STOP 两步必须携带完全相同的当前 RunIdentity。新 run 只能从 STOP_CONFIRMED 开始，epoch 和 session 都必须变化。真实停止完成证据是未来 authority 的责任；测试 authority 只模拟它，不产生该证据。

顺序：fresh nonce 读取 authority → 精确事件/进程授权 → CREATE_NEW generation 并核对 identity/bytes → 再核 root → authority `commit(PendingCommit)` CAS。**逻辑线性化点是受保护 authority 的原子提交，不是本地文件创建**。authority 应在同一原子事务中持久化单调 checkpoint 和 exact request key/body 结果，拒绝过期 expected checkpoint、重复 key 的不同 body 和重用证明。模块不提供这样的 production adapter。

`PendingCommit` 包含 key、完整 request digest、root、expected/proposed checkpoint 和绑定 nonce/proof 的 Authorization。模型也核对 proposed 的 predecessor/ref/revision 与 expected 一致。提交异常、未知结果或不匹配响应进入 sticky uncertainty；在确切 key/body 的 fresh-nonce `resolve` 确认结果前，禁止新 generation、新 nonce 和新 prepare。跨实例恢复依靠 authority 返回持久 pending；仅有本地 pending 不足以跨进程恢复。

提交前崩溃留下的未引用 generation 是 orphan，不能成为 current；候选保留它。提交后答复丢失须按原 key/body reconcile，不能猜测“未提交”。并发 fork 的失败 CAS 只留下 orphan，不改变 current。一次 CONFLICT 不自动重试；再次工作先读取新鲜 authority。拒绝旧 nonce、scope、root、checkpoint 和 local rollback；跨实例 anti-rollback 仍依赖真实受保护单调 authority，测试 harness 的 Python 状态不是安全实现。

## 必需但尚不存在的新信任边界

生产前至少需要安全 owner 明确设计和部署以下对象；本轮没有授权执行：

1. 与当前同 User 攻击者隔离的 authority 身份/存储，以及被保护的 IPC、进程/密钥/句柄边界；明确管理员/恢复/备份权限与威胁边界。
2. 持久单调 checkpoint 与 exact-key 结果账本的原子事务、认证新鲜 nonce 响应、崩溃恢复及抗回滚策略。不能用可由同 User 替换的 CURRENT 文件充当此 authority。
3. root/session/config/source/permissions 来源的可信初始登记，以及真实调用者和当前 launcher/server handle 身份证明；STOP_CONFIRMED 的真实终止证据。
4. Windows 文件 adapter 对原始句柄、reparse、identity、内容摘要和 pending I/O 生命周期的实际验证，以及明确的持久化边界。既有 ENG099 native candidate/mock 不等于这项实际验收。

这意味着新增 trust boundary 或主体隔离设计，不能在保持现有同 SID ACL 且没有外部 authority 的条件下从文件布局推导出来。必要部署、身份/权限配置、服务安装和实际 Windows 操作均未执行，也未申请。实际 protected-authority 集成为 **BLOCKED / MISSING_PROTECTED_AUTHORITY**；此候选完成后停止 A 线，不转向替代弱化路线。

## 验证范围

`tests/test_lifecycle_generation_candidate.py` 使用明确故障注入 authority 和 Linux UUID CREATE_NEW fixture；独立 `tests/test_generation_authority_invariants.py` 检查协议负例。最终当前两文件共 **63 PASS**（独立 57 + 本模块 6），0 fail/skip，1 既有 warning；日志和 JUnit 为 `/tmp/eng100-authority-gold-final.log`、`/tmp/eng100-authority-gold-final.xml`。测试仅证明逻辑顺序、拒绝路径、exact binding、synthetic file identity/hash 检测和恢复行为。没有 protected service、Windows native 安全操作、实际 PID 动作或持久化性能证据。冻结 source SHA 和证据 hash 另由最终报告绑定；collection 数不替代 PASS。
