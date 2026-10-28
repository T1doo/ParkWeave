# Windows 静态闭包与 CRT 来源 · 2026-10-28

CRT 部分记录此前 app-local 方案的来源核对。用户现已确认采用已有官方系统 CRT 先决条件；当前合同以 [系统 CRT 只读 witness](ExistingSystemCRT-20261028.md) 为准，不要求把 CRT 复制到 PG 域。

当前可以在云端完成真实依赖归档读取、固定字节核验、PE import/delay import 检查及完整源码封装；这不执行 DLL，不观察目标 Windows 的实际加载，也不解除 native loader 门。

## CRT 的具体条件

既有 24 份软件锁包含 Python 域的 VCRUNTIME140，但 PostgreSQL 私有域没有该文件，也没有 MSVCP140。不能把其他域或机器上偶然存在的 DLL 当成 PG 的合法封装闭包。

微软 [再分发说明](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170) 和 [当前下载说明](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) 均要求核对 Visual Studio 许可资格和适用的 Microsoft 条款。当前任务没有提供已有适用再分发权的依据，也禁止接受需单独同意的新法律条款，因此没有授权把新 CRT 二进制加入产品分发。

仅为公开来源和字节检查，已读取官方 x64 下载链接的微软域重定向结果：18731856 字节，SHA256 `843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c`。不可变下载 URL、大小及哈希记录于 runtime-assets.json 的 `external_prerequisites.msvc_x64.inspection_only`。该项不是 `assets` 中的可分发资产：没有执行安装器、没有提取或复制 CRT 到 PG、没有接受许可，也没有把检查文件加入候选 ZIP。此 SHA 是官方读取字节的完整性记录，不是签名验证或再分发授权。

解除这一依赖缺口需要先确认已有适用再分发权，再为实际 DLL、版本、架构、依赖与许可证建立可分发锁及私有 PG 域封装；不能用“等待用户测试”代替这些依赖工程。

## wheel DLL 目录

psycopg-binary 3.3.6 的原始 wheel 已包含 hashed libpq，目录为 `psycopg_binary.libs`，其初始化代码先声明 `os.add_dll_directory`。旧静态模型仅搜索导入文件目录和 Python 可执行目录，漏识别了这个已存在的路径。

新模型只识别现有锁定 wheel 的完整初始化文件 SHA256 `712ff217ff67595f391b6dd2a0e148c78a6e74f3e8f4a66116f873c0e49395b4`。对应 package 和 .libs 的依赖可关联到确切的包内文件，同时记录初始化来源、哈希及 `native_loading=NOT_RUN`。未知代码、字节漂移、其他同名 .libs 目录均不能发行该模型；路径不会传给独立的 PG 域。

这修复的是打包字节与加载声明的静态模型，不是 DLL 已经加载的证明。Python [add_dll_directory 文档](https://docs.python.org/3.12/library/os.html#os.add_dll_directory) 说明其搜索作用；真实目录注册、cookie 生命周期、转发导出和所有模块实际来源仍须目标平台核验。

## 系统 DLL 与 API-set

微软 [API-set 说明](https://learn.microsoft.com/en-us/windows/win32/apiindex/windows-apisets) 区分合同名称和实际 DLL 文件。静态名字形状不证明目标 OS 具备该合同；新审计将其保留为 `API_SET_REQUIRES_TARGET_SCHEMA`，记录语法和 `observed=false`。形状错误也不会被放行。

cabinet/msi/propsys/pdh/powrprof 被单独标为待目标核对的系统库候选，仍在 unresolved 中。原 OS_DLLS 没有扩大；原已声明系统项也新增 `observed=false` 平台需求记录。微软 [搜索顺序说明](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order) 中的 API-set、KnownDLL、已加载模块、SxS 和目录顺序均不能用静态名字或云端 POSIX 检查冒充。

因此审计分别输出私有依赖缺失、平台需求、固定 wheel 目录及其文件关联。全局仍可为 UNRESOLVED；`activation_allowed=false`、`symbols_and_forwarders=NOT_CHECKED`、Windows NOT_RUN 及所有原准入门保持不变。
