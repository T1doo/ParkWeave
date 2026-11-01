# 待批：原生吊销资料获取后原严格 WinTrust 复验

状态：只完成源码/离线协议准备，没有批准或执行网络获取、Cryptnet 缓存写入或新 Windows CI。旧的“禁止任何重定向且只写 URL 缓存”方案已撤回；本方案明确允许系统原生重定向与临时账号缓存副作用，不能沿用旧方案许可。

## 推荐的最小路径

一次全新的标准 GitHub-hosted Windows2025 AMD64 runner，job 总上限 3 分钟，无付费备用；120 秒原工作截止及其后最多 15 秒自有对象清理，均不得突破 job 上限。只执行 `scripts/windows_ci/crt_cryptnet_cache_trial.py --inspect-native-cache-once`，不运行产品/数据库/身份工厂。

1. 原 read-only receiver 持有两个固定 System32 CRT 文件，核固定身份、字节和所选三证书链。先调用**原共享严格文件验证器**，保留其真实结果；无法取得原已知、可绑定证据时，网络前停止。两者本已严格通过时不取证、不写缓存。
2. 对已知缺失的叶证书 CRL 初始官方 CDP，仅调用一次 `CryptRetrieveObjectByUrlW`：

   `http://www.microsoft.com/pkiops/crl/Microsoft%20Windows%20Third%20Party%20Component%20CA%202013.crl`

   参数固定 `CONTEXT_OID_CRL=2`，flags 为 `WIRE_ONLY(0x4) | VERIFY_CONTEXT_SIGNATURE(0x20) | NO_AUTH(0x20000) = 0x20024`，`dwTimeout=15000`（不足原截止则截短），`hAsyncRetrieve=NULL`，`pCredentials=NULL`，`pvVerify` 指向自有、与原选定链 DER pin 一致的 issuer context。aux 全零初始化并设 size、last-sync 输出和 `dwMaxUrlRetrievalByteCount=16777216`；不申请额外响应/错误缓冲，不设置缓存前缀、刷新时间或任何策略。
3. 不设置 `DONT_CACHE_RESULT`，因此系统可能写当前临时 runner 账号的 Cryptnet URL 缓存。成功返回的 CRL context 先登记所有权，再在原截止内独立检查 MD2/MD4 禁用的签名、issuer/AKI、适用性、完整列表、序列号和有效期。失败非空输出或调用未知时，不猜所有权、不释放或重试，保留原参数图。
4. 持有原文件时，用**完全相同的原严格验证实现和 flags**重新检查两个 CRT；核前后文件身份、字节和选定证书一致。只有原检查本身严格通过才记录该组件通过。原拒绝仍拒绝，UNKNOWN 仍 UNKNOWN；不修改任何原记录或生产字段。
5. 有界逆序清理本次拥有的 context 和文件句柄。不清空/修补系统缓存，不以失败为由更改 flags、换 URL 或重试。结束后关闭唯一 workflow 窗口。

[`CryptRetrieveObjectByUrlW`](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-cryptretrieveobjectbyurlw) 的 flag、签名 context 与缓存语义及 [`CRYPT_RETRIEVE_AUX_INFO`](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/ns-wincrypt-crypt_retrieve_aux_info) 的响应字节上限均有官方合同。本方案没有手写 Cryptnet 内部格式，也没有用 WinINet cache 冒充它。

## 批准必须覆盖的真实限制与副作用

- 一次指**一次应用层原生 API 调用**。内部可能跟随 HTTP 重定向、使用已有代理或做原生内部通信；没有逐跳拒绝或完整最终 URL 回执，不能保证只联系原主机、只发一个 HTTP 请求或一定直达源站。若必须维持单目的端/禁重定向，就不能执行这个方案。
- `NO_AUTH` 抑制自动认证，不提供应用/账户凭据；不修改代理、网络或信任设置。它不是禁止重定向或逐跳目的端审计。HTTP 传输的内容完整性依赖 CRL 签名和原严格验证，不执行响应中的软件。
- 非零超时和响应字节限额由 API 请求，不承诺即时取消、总内存、协议开销或所有内部网络流量均在相同上限内。原生卡住可能由 job 上限终止，结果/对象清理只能记 UNKNOWN。
- URL 缓存写入可能发生在应用的完整适用性检查前；即使验签/后续检查失败，也不能承诺没有缓存或元数据写入。最坏会留下未被应用认可、部分或有效的缓存项，以及 DNS/HTTP、原生预取/审计记录；它们随该一次性 VM 生命周期结束，不手动删除系统缓存或密钥。
- 不导入系统或用户证书库，不改根信任、吊销政策、注册表、服务、代理或防火墙；不做 token/ACL setter、DPAPI、初始化数据库、调试附加或用户电脑操作。只用预装 Python，无新账号、凭据、安装器或付费备用。
- 日志仅保存公开证书/CRL 摘要、固定阶段/返回码和清理结论，不打印凭据、响应头、原生指针、私有路径或异常参数。不上传 cache、证书私钥或原始敏感日志；不发 Release、不改 main。

## 原调用与可得结论

`authenticode_signature.py` 的 GENERIC_VERIFY_V2 FILE 验证、cache-only、吊销、Publisher、root pin 和 CLOSE 均不修改。新工具使用同一共享实现，原前测拒绝记录保留；资料获取后另作一次原样复验。没有把独立 CRL 结论插进原谓词。

这一次可以组合“获取 + 原严格复验”，不必再运行业务工厂来判断是否取得原调用可用的资料。即使两 CRT 严格通过，也仅闭合这个组件：OWNER、fixed journal、loader、完整业务/重开与独立窗口/Windows11 验收仍分别保留，不发行生产能力或将 usable_product 设为 true。

执行前仍需：冻结确切工具源码和一次 source-bound workflow 补丁，独审确认上述边界，然后取得**本次原生重定向和临时 Cryptnet 缓存副作用**的具体执行批准。当前 workflow 没有该 job，不会因普通源码推送执行。
