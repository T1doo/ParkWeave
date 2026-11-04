# 原生验收 harness 源码与审批范围 · 2026-10-28

本片补实现，不执行 Windows。原产品/界面候选仍为 `5a048dbef9da4e82a1cb0eb51b4813d75dda54e1`，原 ZIP 51637700 字节、SHA256 `58486d0c92833d2358a9c0198c082065ebf3bd91cd1b76364132555ff7dbbbaf`，manifest SHA256 `2ab9b9ef3ad24cdeecca7775f5e6dae9dbbd5cb9c252838304f0096d5a55e8d2`。本片 harness 的新提交与上述产品字节分别记录，不以旧包冒充包含新 harness 的包。

## 已实现的真实原生调用链

`native_acceptance_storage.OwnedNativeObjects` 在未来获准窗口内，先只读 current primary user、拒绝 thread impersonation、固定本地 NTFS 和无 reparse 祖先，再用带当前用户 protected descriptor 的 `NtCreateFile(FILE_CREATE)` 独占创建一个测试目录。新目录名由仓库、精确 workflow/ref、批准 run ordinal 和 job 派生；不接受已存在目录，不用随机新名绕过一次窗口。最多创建 `lock.bin`、`journal.bin`、`torn.bin`、`identities.dpapi` 四个固定新文件，无现存文件权限修复。

`NativeSlotIO` 是独立原 HANDLE adapter，直接供原 `FixedJournal(INSTANCE_V2)` 写入、FlushFileBuffers、回读、原 ID/descriptor 文件重开、第二次打开排他拒绝和破损槽拒绝。测试 journal 仅走 NEW→CREDENTIALS，不写 READY，不发行或伪造 `FixedDirectoryLease`。完整 API 输出缓冲在 syscall 前登记；pending、部分写入、flush 或 close 未知不重试、不补写。

`NativeBackend.derived_token` 调用原 `_RestrictedPrimaryCandidate` 创建本次拥有的 derived token，再仅对该 token 调用 `SetTokenInformation(TokenDefaultDacl=6)` 和 `SetTokenInformation(TokenOwner=4)`；前后读取比较原进程 primary token 的 user/groups/privileges/Owner/DefaultDacl/type。原 token 从不 setter，不 impersonate、不提升 privilege、不创建系统账户或子进程。

`dpapi_identities` 临时生成三企业、三专员应用 token，不注册 OS 用户、数据库主体或真实 API 身份。每个 token 使用 window/root/source/actor/role 独立 entropy，经原 CURRENT_USER `_NativeDPAPI` 加密后仅保存密文容器；重开同一原文件解密比较，并用企业密文+专员 entropy 验证 ERROR_INVALID_DATA=13 的干净拒绝。UNKNOWN DPAPI allocation/free 会保留原对象、mutable storage 及所有文件句柄，不换对象重试未知操作。Python 不可变 plaintext 内存不承诺安全擦除；值不进 argv、环境、报告或明文文件。跨不同 OS 账户 DPAPI 隔离没有本轮证据。

所有 query token HANDLE 先登记原输出、owned/close-attempted/closed；关闭未知保留原记录、API owner 和 backend 强引用。底层 `WinAPI._user_sid` 的同类查询关闭也补了保留。最终 cleanup 只用本次 FILE_CREATED、原 ID/SD/namespace 未变化文件的原 HANDLE 执行 FileDisposition，不按路径递归删除。成功删四文件后保留空测试目录作为单次窗口标记；任何未知整体保留至一次性 runner 销毁，不删现存文件、DPAPI 系统 key、源代码或其他实例。

## 执行绑定与现状

正式入口为 `native_acceptance_entry.py`。无执行参数仅输出计划；审批记录 `native_acceptance_window.json` 当前为 `null`，正式 `--execute` 只读取该固定源审批数据即拒绝，在 native imports、候选读取、RNG、目录或安全操作之前停止。旧 harness 直接执行入口也固定拒绝，不能靠 CLI/env 参数发放批准。

审批记录是有限 JSON 数据，不是会在加载时执行的 Python 赋值或表达式。未来明确批准的 enabling commit 只能改该 JSON 和工作流，全部可执行 harness 源保持与已独审 parent Git blob 一致；消费记录还须与当次实际 Git blob 语义一致。数据发行 weak-registry 中的单次原对象，环境变化或消费失败后不可重用。只冻结必要 context 和禁止 PG 变量的名称集合，不复制秘密环境值。

绑定本 public 仓库、精确 `GITHUB_WORKFLOW_REF`、workflow SHA/GITHUB_SHA、ref、job、run number、attempt=1、GitHub-hosted Windows x64、private Python 3.12 `-I -B`、到期时间与固定操作集合。若派发前不知道实际 run ID，记录可用明确批准的 workflow ordinal，实际 ID 只在运行后记录，不能声称预知/批准过该 ID；如已知则必须精确匹配。起始时需保留超过六分钟有效期；禁继承任何 PG 配置，只用 pinned binary psycopg。

`native-local-acceptance-once.yml` 是 manual-only、标准 Windows2025、job 六分钟/step 五分钟、contents:read、无持久 checkout credential、cache、artifact upload 的准备工作流，目前 job 条件仍为 false。没有触发 CI、public push、Release、PR 更新或费用。

`native_acceptance_driver.ps1` 仅接受本仓 Release 路径、原候选文件名和外部 ZIP SHA；先审源记录和只读窗口检查，再允许最多 60 秒、51,637,700 字节下载与三个官方 HTTPS redirect。401/403/429、hash/size/来源异常立即停止，不换凭据或路线。持有同一 ZIP stream 校验后在 RUNNER_TEMP 新 staging 根按最多 192MiB 解包，最后启动固定私有解释器和正式入口。当前没有已获准公开的候选 URI；脚本不会自行发布候选或把 Library 私有文件变成公开 URL。

未来最小命令（仅在上述绑定、原包暂存或明确获准发布路径具备后）：

```powershell
pwsh -NoProfile -NonInteractive -File scripts/windows_ci/native_acceptance_driver.ps1 -CandidateUri '<另行明确批准的原候选公开地址>'
```

## 合同接入与未覆盖边界

`native_acceptance_contract` 统一 OWNER/fixed journal/loader 必要观察名、缺口和固定拒绝码；fixed journal、runtime loader 原拒绝入口读取该合同，仍无条件拒绝。legacy lifecycle 文件入口保持原固定 OWNER 暂停，避免对完整 `scripts` 包路径新增依赖；协议检查核它与 OWNER 合同一致。即使向 coverage 提供全部观察名称，也只输出 NOT_ACCEPTED、activation_allowed=false、usable_product=false，普通 JSON 或一轮测量不能签发产品许可。

仍未覆盖/未验：Windows API 实跑；跨 OS 用户 DPAPI；进程中断/断电与目标文件系统持久性；实际 initdb 原管道、Job/SQL backend 加载来源、API-set、PG 工具链最低兼容；完整 Windows PG/API/worker 双角色业务和重开。上述必须分项提供真实证据后独审生产合同，不能因获一次测试许可直接删除三个门或改 READY。已通过的 Linux 三项完整业务回归本轮不重复跑，UI 不改。

## 供一次确认的完整范围

仅在 T1doo/ParkWeave 的一次性标准 GitHub-hosted Windows2025 x64 上执行一次上述固定源码/原包验收，最长六分钟；新建一个 protected 临时测试目录及四个固定新文件，只对本次新派生 token 设置 TokenOwner/TokenDefaultDacl，CURRENT_USER DPAPI 临时保护六个企业/专员应用 token。不会创建 OS/数据库账号，不启动 PG/API/worker，不改原账号 token、现存目录 ACL 或系统安全设置，不授予产品 READY。DPAPI 可能由 Windows 在该临时 runner 用户配置中使用/生成保护 key，不自行删除这些 OS 文件；随 VM 回收。仅用原句柄/ID 删除本次创建的四文件，保留空单次标记目录；未知则保留全部现场。用户 PC 不在范围。新版源码、非敏感测试记录及原候选若要公开以供 CI 取用，仍需逐项明确该仓库、分支/Release 文件与精确哈希，不能沿用此前被拒的泛化上传或截图许可。
