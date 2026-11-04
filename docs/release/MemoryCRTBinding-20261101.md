# CRT 内存证据绑定与生产等价性审查 · 2026-11-01

范围：只审现有系统 CRT 的证据组合，不改变信任标准、生产验证器或准入。隔离运行 [41321508465](https://github.com/T1doo/ParkWeave/actions/runs/41321508465) 的源码没有请求 `pCrlInfo`，因此其两个 native GOOD **没有所用 CRL 内容证据**。本片的新绑定尚未在 Windows 执行，不能把旧成功结果套给它。

## 已查明的官方合同及源码修复

[`CERT_REVOCATION_PARA`](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/ns-wincrypt-cert_revocation_para) 中 `hCrlStore` 是可搜索的来源，不是排他来源；`pftTimeToUse` 也不是实际验证时间的回执。仅传 MEMORY store 或读取 freshness 不能证明用了哪份 CRL。

[微软 SDK 头文件](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/wincrypt.h) 对 `pCrlInfo` 明确说明：handler 更新所用 base/delta；输入中的非空 context 会被释放；输出 context 由调用者释放；结果只对应最后一个被查证书。因此每个目标单独调用，`cContext=1`，每次独立全零输出结构并设 `cbSize`。

`scripts/windows_ci/crt_memory_revocation.py` 现已实现：

- 保持原单证书 cache-only 调用及已持有 target/issuer context；一个共同 FILETIME 同时用于两次请求，输出十进制字符串。
- 已知返回后，立即登记 base/delta 两个独立拥有引用，再做 BOOL、状态、期限或内容检查。相同指针值不合并引用；不释放借用的 entry。
- 要求返回 base 的完整 DER 等于该 target/issuer pair 之前签名和适用性校验的确切字节；缺失、不同的有效缓存 CRL、delta 或 entry 都拒绝。并独立检查两份 CRL 覆盖共同请求时间及最终返回时刻。
- 输出内容匹配为 `USED_BASE_DER_EQUALS_EXPECTED_PAIR_CRL`，存储来源仍为 `NOT_OBSERVED`，时间语义仍为 `REQUESTED_NOT_ATTESTED`。内容相同不等于来自 MEMORY store。
- 已知失败也清理返回引用；未知调用保留输出结构和整个参数图，不检查猜测输出、不释放或重试。逆序先释放返回引用，再 CHECK-close MEMORY store，再释放原 context。

原共享 `authenticode_signature.py`、`native_system_crt.py`、工厂、OWNER/fixed-journal/loader 门和工作流不变。

## 组合谓词和不能证明的部分

设 `H` 为原路径/ACL/架构/导出兼容、持有文件身份/字节及 runtime/lease 绑定；`O` 为原完整严格文件验证；`B` 为下表证据绑定；`C` 为独立当前时间 CRL 和 native 检查；`K` 为期限与已知清理。

| 绑定 | 已有或本片实现 | 仍不能据此声称 |
| --- | --- | --- |
| 文件 → 原选定签名链 | 原 held HANDLE WVT、同一 live state 拷贝、固定文件/三个证书 DER pin，前后文件和证书字节一致 | 普通 JSON、mutable internal record 是生产能力 |
| target → issuer | 每次单一 target、显式 issuer context、DER/名称/AKI/SKI 和证书签名校验 | 证书 Subject 字符串足以建立可信链 |
| issuer → CRL → target | CRL 签名、issuer/AKI、完整适用性及序列号检查，返回 base DER 逐字节等于该 pair 的已验 CRL | native GOOD、freshness 或 store HANDLE 自身证明来源 |
| 时刻 | 一个共同请求时间，独立 current-validity/CRL 窗口检查，末尾再次检查，不接受历史时间戳例外 | handler 实际按请求时间裁决，或当前 CRL 等于历史 Authenticode 时间语义 |
| 生命周期 | 原文件持有至复查，输出引用完整登记、逆序清理、UNKNOWN 保留 | 关闭后的 dict/hash 可重新发行或跨运行使用 |

**本片若保留原 `O` 并叠加独立补证，可写为 `P0 = H ∧ O ∧ B ∧ C ∧ K`。** 它蕴含 `O`，但当原 `O` 因 `80092013` 拒绝时仍拒绝，不解决当前生产启动。这不是新的准入要求：已经满足原生产合同者不因此被额外要求执行 `B/C`。

候选 `P1 = H ∧ F ∧ Publisher ∧ RootPin ∧ B ∧ C ∧ K` 中，`F` 表示从同一文件 WVT 提取的完整非吊销要求。它可能实现单独审定的组合策略，但当前不能证明 `P1 ⇒ O`：`O` 还要求原 provider 每个证书吊销状态为零；独立调用无法修改或证明那个事实。原 WVT 使用 provider/timestamp 时间，独立路径只确认当前有效性，不能把两者当成相同判据。生产路径也尚未分离和完成 `F`，原检查遇到离线状态即停止，后续 Publisher/RootPin 没有执行。

此外，当前 `OriginalCopies`/结果 dict 是可变的内部记录，并非原生产 receiver 发行的能力。即使内容绑定在未来实机通过，生产接入前仍须在原 receiver/lease 内完成检查，发行不可序列化、绑定原文件/链/CRL/时间/绝对期限的内部能力，并由消费方在文件仍持有时复核、过期/关闭/UNKNOWN 即失效；不能接受调用者 JSON 或把哈希当授权。此处仅给设计，没有增设产品门或实现假 issuer。

**生产接入继续否决。** 新反例只能补足独立调用的内容绑定，不能修复这个逻辑蕴含缺口。最小选择为：

1. 保持原生产合同，要求已有系统资料使原 cache-only WVT 本身严格通过；程序不取证写缓存、不更改信任设置。现内存诊断不能代替该前提。
2. 若确要采用内存证据，需要明确审定组合策略变更，先证明完整 `F`、时间语义与能力生命周期，再考虑接线。不能只跳过 `80092013`、复用旧 UNKNOWN 或放宽 Publisher/RootPin。当前没有批准或实施这项变更。

[`WINTRUST_DATA`](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_data) 的 FILE 路径没有公开的 CRL-store 输入字段。本次未找到让现有 GENERIC_VERIFY_V2 FILE 调用只用这份内存 CRL 的受支持合同；不把 CERT 对象验证、policy/SIP callback 或自建链当成原文件策略等价品。

## 独立桌面下一可执行验收顺序

本片没有重复打包。已有新宿主 AMD64 GUI EXE 为 825344 B、SHA256 `16ec2b8d72b141d7dd2699448b746be118c12784c574cb729f07238b5bcb54cf`，只是独立宿主构建，未替换冻结 ZIP，不能称完整新版安装包。

| 顺序 | 实际操作与通过证据 | 当前边界 |
| --- | --- | --- |
| 1 | 正式准入需审定 CRT 组合或满足原严格前提；核最低工具链版本、平台 API-set 和加载来源策略 | 内存诊断只完成一部分。原 `minimum_toolset_compatibility=NOT_ESTABLISHED` 及正式 loader 门保留；不把未知版本 floor 新增为已批准 TRIAL 的当然前置 |
| 2 | 冻结完整 app/bootstrap/EXE/依赖，冷构建 ZIP，核 manifest、成员、大小与哈希 | 受限源码/候选构建可与前项并行，无新增构建次数限制；旧 ZIP/单独新 EXE 不能混报，最终交付绑定完整源码与字节 |
| 3 | 在新临时原生环境完成原准入范围的初始化、原句柄和 fixed journal、身份隔离及加载来源观察 | 需另行安排原生执行；本轮不运行。正式 new 仍先拒绝 OWNER，已有安装 reopen 仍受 journal/loader 门约束 |
| 4 | 从包根 `ParkWeave.exe` 打开独立窗口；明确 new/reopen，核输入错误可恢复、私有桥、受保护 profile、Runtime 来源和真实 RUNNING | 不能用浏览器预览或 API health 代替；初始化/profile/DPAPI 有真实副作用，必须列入那次执行范围 |
| 5 | 窗口内申请人登录提交→审核员要求补料→申请人补料→审核确认→申请人确认；核越权拒绝、UNKNOWN 精确只读恢复、分页 | 使用合成样例及两角色，保存事件 ID/状态。1366×768、1440×900 同入口真实像素，局部滚动、按钮可达 |
| 6 | 关闭窗口，核原 browser/controller/Job 有界停止及 API/worker/PG 停机；再次 EXE 重开同安装，登录回读同事件 | 不能只重读未退出的进程；未知关闭保留 UNKNOWN，不自动重启或新建 |
| 7 | 审核安装/退出/移除方式，仅移除本次拥有的应用目录，保留独立资料和别的实例；形成限制说明和最终包清单 | 当前是便携 ZIP，没有本片新增的卸载器；若将来有安装器再验其卸载。Windows11、正式园区来源与 Server 样例分别记录，不提升 usable_product |

当前桌面路径为 `EXE → desktop_bridge.run → entry.main → native_invocation → create/reopen → workspace.check → NativeDesktopProfile → RUNNING`。关闭经 WebView2/原 UI Job 结束后发正常停止字节，再由原 Controller 停止服务；异常归 UNKNOWN。源码已有实现和协议证据，完整原生业务及窗口验收仍未完成。没有自动启动第九轮。
