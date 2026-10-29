# Loader 目标输入与样例启动边界

## 仓库原目标

原始 `windows_handles.py` ABI、`file_candidate_probe.py` 和首次体验说明明确以 Windows 11 x64 为原生目标；Python 为 3.12 x64。没有已接受的精确最低 Windows build，也没有已签收 Windows 10。`payload.py` 的 Windows 10/11 DLL 分类文本和 PE 的较低 OS version 字段不是产品支持承诺。本轮只读取实际 build/架构，不自行扩展支持版本或设 READY。

## 从现有 9d 候选已取得的事实

完整 9d 包的清单及每个选定文件重新核 SHA256 后，`loader_inputs.inspect_payload` 已读取 82 个 AMD64 原生映像的 ordinary/delay import、named/ordinal symbol、导出、forwarder 和 PE header。原 PG/Python 域及固定 wheel 注册仍保留；EXE/launcher 另按各自目录建 desktop 域，不能借 Python、wheel 或其他 desktop 目录。

现有实际字节可静态闭合 6129 处私有符号引用，其中 6085 处为直接导出，44 处为 `python3.dll → python312.dll` 私有转发；没有私有缺 DLL、缺符号、非法 API-set 或未闭合私有转发。无需把这些包内信息再交 Windows 猜测。原 PG static consumer 已接入符号/转发检查：仅 DLL 文件名存在而缺所需导出会拒绝。原最后 native loader 门不变。

报告保留 476 条外部依赖边，归并成 28 个直接系统 DLL 名称及 17 个 API-set 合同。每条边都有 `importer`、`importer_basename`、`dependency`、精确 `symbols`（含 `#ordinal`）和未解析原因。不是要求用户采集整个 System32。

现有包还提供原资产 file/version/hash、各映像 SHA256、linker/OS/subsystem 字段及可读取的编译器字符串。PG 字符串为 `msvc-19.44.35229`；六个 wheel 映像的 linker 字段为 14.51，包括 psycopg 的两项 pyd、libpq/libssl/libcrypto 及 pydantic_core。linker 字段不是完整编译器或最低 CRT 版本，不据此判已兼容或直接替换原 Python 私有 CRT。先使用这些真实事实推进精确目标导出/加载核对；上游公开最低要求存在时再锁定，不把不存在的全生产者证明当成停止所有工程的理由。

在完整源码 checkout 下生成实际请求：

```bash
python -m scripts.windows_portable.loader_inputs --payload '/绝对路径/已解开的原9d payload'
```

这是纯静态读工具，不加载 PE，不签发 native witness。新增工具与检查在本轮新源码中；已保全的 9d EXE/ZIP 字节不因此包含新模块，不能把两个版本混称同包。

## 第一批 Windows 最小只读字段

原唯一协调任务可用 `scripts/windows/CollectLoaderTarget.ps1`，或正常内置查询取得下列字段；脚本只向 stdout 输出 JSON，报告文件若需保存由协调任务写到 `E:\Software`，外层使用原有有界预算。脚本执行策略拒绝则停止，不设 ExecutionPolicy bypass。当前云端没有 PowerShell，脚本仅源码独审，未 Windows 执行。

| JSON 字段 | 类型/内容 | 最小读取来源 |
|---|---|---|
| `schema` | 固定 `parkweave-windows-loader-target/1` | 本次格式 |
| `captured_utc` | UTC ISO8601 字符串 | 采集时间 |
| `os.nt_major/nt_minor/build/ubr` | 整数，无法读取则明确 null | HKLM CurrentVersion 对应字段 |
| `os.edition_id/installation_type` | 字符串；本产品目标为 Client | 同上，只读 |
| `architecture.os_64bit/process_64bit` | 布尔值 | 当前 .NET runtime 查询 |
| `architecture.os_architecture/process_architecture` | X64/Arm64 等原始值或 null | RuntimeInformation，禁止用环境字符串作权威 |
| `architecture.native_machine/process_machine` | 原 `IsWow64Process2` 结果；未查则 null | 最小脚本不新增 P/Invoke，不伪造 0/0x8664 |
| `system_directory` | 实际完整路径 | GetFolderPath(System)，不猜 C 盘、不搜 PATH |
| `system_files[]` | 首批仅 vcruntime140.dll、msvcp140.dll、ApiSetSchema.dll | 上述实际目录内原文件 |
| 每项 `name/path/size/sha256/pe_machine/file_version/status` | basename/路径/字节数/64位hex digest/如0x8664/原版本文本/状态 | 普通文件、同打开 stream 的 SHA 与 PE header；前后元数据复核 |
| `signature_status` | 默认 `NOT_COLLECTED_CACHE_ONLY_WITNESS_REQUIRED` | 最小脚本不调用可联网/写缓存的 Get-AuthenticodeSignature；原 cache-only witness 另验 |
| `identity` | `NOT_COLLECTED` | 此快照不冒充原 HANDLE/file ID/SD 证明 |

原生目录/file ID、ACL、微软签名链和实际进程身份仍由已有受保护能力核验，不能让这些普通 JSON 字段代替。所有响应固定 `response_is_native_witness=false`、`activation_allowed=false`、`usable_product=false`；未知项目保持 null/NOT_COLLECTED，不填示例成功值。

## 第二批精确目标解析输入

第一批先确认实际平台。随后只针对请求 JSON 中的 28 个 `direct_system_dll_names` 和 17 个 `api_set_contract_names` 补：

第一批实际平台元数据已在本次私有交接记录收到；下一批 version 6 文件映射解析及只读选取工具已实现，具体命令和未采边界见[API-set 目标映射](ApiSetTargetMapping-20261029.md)。原始条目尚未回传，不将字段定义或受控 fixture 当成实际映射。

1. 对每个系统目标：绑定同一文件的名称、SHA256、Machine、版本、原签名事实，以及 exact named/ordinal export → direct RVA 或原始 forwarder 字符串。缺文件、缺导出与签名未知分别记录。不是从 PATH 选同名文件。
2. API-set：绑定实际 ApiSetSchema 文件 hash/格式版本，提供每个合同在该系统、该 importer 下的 `present`、`mapped`、`host` 及 alias/default 规则。普通格式可为 `api_set_mapping:[{contract, importer_basename, present, mapped, host}]`；不能以有同名文件、name 前缀或单个 schema hash 冒充已解析。宿主补齐第1项，原始 forwarder 再逐层解析，循环/缺件/未知保持拒绝。
3. 原进程实际加载来源属于后续原生阶段：固定原 HANDLE/birth/image/Job、所加载模块原路径和文件身份、系统/各私有域及动态加载/Job 后代。静态 JSON、一次成功 LoadLibrary 或已存在 WebView2 不能替代。

[微软 loader 文档](https://learn.microsoft.com/en-us/windows/win32/apiindex/api-set-loader-operation)明确合同不是文件，schema 映射随设备变化，宿主可加载及所需导出还必须分别满足。本轮不预设 KernelBase/ucrtbase，不调用 LoadLibrary 获取假证明。WebView2 的已有机器级版本/签名信息继续使用原范围记录，并在真正宿主验收时重新通过原检查，不自动安装 runtime。

## 可独立交付的本地样例

`scripts/local_product.py` 是非 root Linux 的真实本地样例安装/启动入口，采用原私有目录、加密双角色、PG/API/worker 与持久回读；没有导入 Windows native 门。源码齐备时可按原 `install`/`start --state-dir` 办理提交、补正、审核、确认、重开，不能因 Windows loader 等待而宣称 Linux 功能 BLOCKED。此前实际业务/持久回读证据仍按原提交保留，本轮 Windows-only 变化不重复跑同组业务。

该 Linux 安全合同依赖 POSIX 私有权限、Unix socket peer 和原 Linux PG 过程，不能在 Windows 强行改平台判断、改用明文身份或系统 PG 来复用。当前 Windows 独立 EXE 即使只用合成资料，仍要创建/读取 Windows 私有运行时与身份，故必须经过 OWNER/fixed journal/loader；这是运行平台安全前提，不是要求真实园区来源。Linux 样例可用、Windows native 未签收、正式来源/真实试点未接入是三个不同状态。
