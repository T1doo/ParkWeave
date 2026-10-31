# 已有官方系统 CRT 先决条件 · 2026-10-28

当前已确认采用此方案：不随 ParkWeave 复制新 CRT，不要求所有 CRT 私有化；只检查目标机已有的合法官方运行库。缺失或无法验证时退出，提供微软官方说明，不自动下载、安装、修 ACL、写注册表或接受条款。不把 VCRUNTIME/MSVCP 加入 OS_DLLS；其他 PG/Python 私有依赖合同不变。

## 源码实现与接线

`NativeSystemCRT` 只在 native Windows x64、原始实例 lease 和 constructor 发行的 runtime capability 下构造。PG 冻结文件按名称、ordinal 和 delay imports 提取实际符号，当前锁定字节有 VCRUNTIME 26 个、MSVCP 18 个不同导入；initdb/postgres 的静态依赖图分别确定必须观察的 CRT 集合。

系统目录来自 GetSystemDirectoryW，拒绝 WOW64/ARM 仿真与不匹配架构；不从 PATH、环境路径或注册表取得权威。逐级持有固定本地 NTFS 路径，拒绝 reparse，保存目录/文件 ID、原 descriptor、最终路径与 SHA256。OS ACL 使用单独合同：owner 为 SYSTEM、Administrators 或 TrustedInstaller，普通主体不得对实际对象有写、删除、改权限/owner 等权限；祖先仅创建其他子对象的权限与 INHERIT_ONLY 单独处理，不修 ACL。

签名使用同一 held file 的 WinVerifyTrust，UI_NONE、缓存限定的链吊销检查，只有 LONG 0 成功。缓存不足或未知不降级；取同一 WinTrust state 的 primary signer 链，核对每证书状态、微软组织及链末 Microsoft Root Certificate Authority 2011 DER SHA256 `847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61`。锚点来自 [微软 PKI 目录](https://www.microsoft.com/pkiops/docs/repository.htm) 的 [官方证书](https://www.microsoft.com/pki/certs/MicRooCerAut2011_2011_03_22.crt)；没有把证书装入系统。其他链当前保守拒绝，不能仅凭 Subject 字符串称微软签名。所有 state VERIFY 都 CLOSE；未知关闭保留原结构和原句柄，不重试。

PE 读取不加载 DLL：要求 AMD64、14.x DLL 版本、满足原 PG 精确名称/ordinal 导出，未解析的 forwarder 拒绝。14.x/符号齐备只是受限兼容前置，不证明构建工具链最低版本已满足；报告保留 `minimum_toolset_compatibility=NOT_ESTABLISHED`，不能签收 loader。

直接导出可指向代码或数据；零初始化数据允许位于节的 VirtualSize 超过 SizeOfRawData 的尾部。解析器单独核对映像内唯一节范围，不把此类 RVA 伪装成文件偏移。导出表、名称、forwarder 和资源元数据仍必须有真实文件字节；映像外、节间空洞、落入重叠节范围或越过 SizeOfImage 的目标均拒绝。依据为[微软 PE 节和导出地址表格式](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)。

新建在 runtime staging 后、凭据/身份/数据库创建前检查；重开在读取受保护凭据前检查。初始化及服务器启动入口复用同一 witness，不因重开而省略。原 loader 最终拒绝仍存在，所以本轮没有运行初始化或 Windows 进程。

## 实际加载来源要求

源码观察只借用原 Job 创建的 process HANDLE、birth、image 和 Job 身份，不按 PID 猜进程。模块清单要求容量完整、路径完整、句柄不重复，两次样本稳定；所需 CRT basename 唯一且路径匹配原 System32 pins。系统文件保持原身份/hash，借用的 HMODULE 不关闭。initdb 与主 postgres 都接此检查；SQL peer 在 libpq 首次认证前，使用原 TCP owner、birth、image、Job 已验证的只读 backend HANDLE 再核 CRT。增加的访问仅 QUERY_INFORMATION/VM_READ，不启用 DebugPrivilege 或修改 DACL。

每次观察有绝对预算并串行使用文件指针。系统文件 pins 保持至本次拥有进程全部停止后；这可能阻止运行期间替换这些 CRT 文件，系统维护应先正常停止本次实例。原生调用预算为合作式检查，不声称可强制中断 WinTrust。源码记录预检时签名政策结果，后续复核字节与模块；不自动联网刷新吊销缓存。

该证据仅覆盖被观察的原进程及 SQL backend 的稳定采样时点，不证明所有 Job 后代或未来动态模块均已安全加载。目标平台原生调用、完整 Job/PG/API/worker/业务重开和主工作台像素仍 NOT_RUN；OWNER、fixed journal、native loader 的独立验收门全部保留。

## 缺失与许可边界

入口给出固定 `SYSTEM_CRT_PREREQUISITE_UNVERIFIED` 和 [微软官方安装说明](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)，由安装者自行核对已有运行库及平台证据，不运行安装器。使用已经合法安装的系统 runtime 与本项目复制/再分发微软二进制不同；本方案不要求普通使用者持有 Visual Studio 再分发资格。先前 installer 的整包哈希仅作检查记录，不是随包 CRT 或 DLL 级锁。

本轮仅云端源码与受支持的负向/协议、真实 PE 字节检查。没有操作用户电脑、执行安全 setter、接受新法律条款或公开上传。
