# API-set 目标映射实现与下一次只读输入

已收到的 OS/架构及三份系统文件元数据只保存在本次私有交接记录；签名和原 HANDLE/file ID 未采，不将这些字段当成生产准入。原桌面 9d 候选保留，新源码尚不等于它的字节。source/工程验证正常推进，安装包 Release 仍须等完整验收。

## 已实现

`api_set_map.py` 对原文件 SHA256 绑定的 AMD64 PE 查找唯一 `.apiset` 节，读取 version 6 元数据。namespace 大小、offset、UTF16 长度、条目/值数量、hash factor、排序 hash/index 全排列和 hashed-name 校验均有界；未知格式不自动选其他版本。不读取 live PEB、不加载 DLL。

二进制布局来自 [phnt 的主头 ntpebteb.h](https://github.com/winsiderss/phnt/blob/master/ntpebteb.h)，是私有格式的版本受限解析，不冒充微软公开 ABI 保证。语义依据[微软 API-set loader 文档](https://learn.microsoft.com/en-us/windows/win32/apiindex/api-set-loader-operation)：合同名不是物理文件，目标 schema、宿主可用和精确导出需分别验证。

metadata resolver 优先 exact importer basename alias，再选择唯一空 alias 的默认宿主。遇到可能匹配但未验的 extensionless alias，不误用默认宿主；缺合同、无宿主、未采集、未知 alias 风格分别保留。Python/wheel 多点 pyd basename 可表达；不把 schema 中未知 host 自动加入系统白名单。

collector 回传的普通 JSON 经 `selected_metadata` 校验 requested/entries/missing 的精确覆盖、文件 hash、类型和路径形状，来源仍标 `COLLECTOR_REPORTED`。原始 bytes parser 才标 `VALIDATED_FROM_BYTES`。两种结果都不是 native witness；不会设 READY、启动产品或消费安全操作许可。

## 下一批最小 Windows 数据

只读取上轮相同 SHA256 的 System32 `ApiSetSchema.dll`。用原唯一协调任务、原 E:\Software 输出边界和有界预算；脚本策略拒绝则停止。新源码中的 `scripts/windows/CollectApiSetMapping.ps1` 参数：

```powershell
& '.\scripts\windows\CollectApiSetMapping.ps1' -ExpectedSha256 '<上轮实际文件SHA256>' -Contracts $contracts
```

`$contracts` 仅为已生成请求中的 17 个 `api_set_contract_names`。不必采整个 System32，不按合同名尝试找同名文件，不新建测试身份。collector 将完整文件作为数据读取，核 hash/PE 和全部 namespace 结构/hash index，仅向 stdout 输出请求条目；没有签名查询、LoadLibrary、Add-Type、子进程、目录写入或安全 setter。签名和原句柄身份仍是 NOT_COLLECTED。真实 PS5.1 执行尚待协调任务，云端仅做源码独审。

需回传格式 `parkweave-api-set-selected-v6/1`：

- `captured_utc`；`file.path/size/sha256/machine`，identity/signature 均明确未采。
- `namespace.version/size/flags/count/hash_factor`。
- 原请求 `requested`、每个选中 `entries[].contract/flags/hashed_length/values[]`；values 包含原 `flags/alias/host`，空 host 不填假值。
- `missing_contracts` 显式区分不存在与未请求；`hash_index_validated` 仅是该 collector 的元数据检查陈述。
- `response_is_native_witness=false`、`activation_allowed=false`、`usable_product=false`。

schema 文件若已变化，固定 hash 检查会拒绝，应先回报新的只读元数据，不能暗中采用新 hash。本次仍未收到这些实际条目，不称 17 项已解析。

## 收到实际行后的命令与输出

在标准 Python3.12 的源码环境中运行，不修改旧候选 embedded `_pth` 或向其 immutable payload 加文件：

```bash
python -m scripts.windows_portable.api_set_map --selected api-set-selected.json --expected-sha256 '<同一实际文件SHA256>' --requirements loader-inputs-9d124b9.json
```

输出只包含实际选择结果与各宿主的精确 named/ordinal 导出读取请求；未知宿主需策略审查，不扩 `OS_DLLS`。再读取这些实际宿主的原文件/导出/forwarder 与签名证据，不预先猜 KernelBase/ucrtbase。单独的文件 schema 不是 active PEB namespace，也不覆盖系统扩展、实际原进程加载或所有 Job 后代；原 OWNER/fixed journal/loader 门均保持关闭。

本轮的受控 byte fixtures 验证字段边界与保守状态选择，不是目标 Windows 数据。Linux 合成样例与这些原生门的区别仍见[Loader 输入及样例边界](LoaderTargetInputs-20261029.md)。
