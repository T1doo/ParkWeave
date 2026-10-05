# ENG-008 Windows只读文件候选与可行性结论

基线d997ba9。有可审查的Microsoft官方接口实现路径，已建立代码与云端可运行单测；**没有Windows11原生调用证据**，不能承诺ACL/重解析或竞态已在真实系统安全通过。生产`files.py`/API/Windows生命周期不调用候选，Windows文件入口继续关闭。Linux已有descriptor文件边界不改为跨平台fallback；当前实际文件仍明确合成、<=16KiB text/plain、逻辑UUID、当前数据库授权及hash/UTF8核对。

候选只提供OS句柄/ACL文件读取原语，不代替园区/企业/角色/Grant授权。未来dispatcher必须保留Store.read_file的当前身份、scope、FILE_READ及Run授权检查；不能直接把候选函数注册成端用户或模型工具。

## 接口依据与候选算法

[Microsoft NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)明确允许RootDirectory句柄+相对名称，并提供FILE_OPEN已有文件、FILE_OPEN_REPARSE_POINT和同步句柄。选type-neutral元数据打开而不设置FILE_DIRECTORY_FILE：官方兼容表未列该flag与OPEN_REPARSE组合，因此不以未确认组合建立安全保证。目录/文件角色在返回句柄上核对。没有FILE_OPEN_FOR_BACKUP_INTENT、创建/覆盖/删除/写入或提权；未知NTSTATUS拒绝并关闭已返回handle，绝不换旗标重试。

[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)仅用于驱动盘根句柄，OPEN_EXISTING、只读访问与FILE_SHARE_READ、OPEN_REPARSE_POINT及目录必需的BACKUP_SEMANTICS；不传企业路径/外部文件名。该目录flag不等于本工程启用备份权限。根句柄用[GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)要求严格GUID卷根，再以[GetVolumeInformationByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew)/GetDriveTypeW限制固定本地NTFS；UNC/SMB、SUBST子目录、无GUID、ReFS/网络盘等拒绝。不是跨平台虚拟化方案。

从该句柄开始，NtCreateFile逐级打开单个经过校验的root component，后续固定files与canonical UUID.txt；持有所有祖先/目录/文件句柄直到读完，不按全路径重新打开。每级[GetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle)及GetFileType核对同卷/目录类型、拒绝任何REPARSE_POINT/DEVICE/OFFLINE/RECALL属性；文件须磁盘普通对象、单硬链接、大小<=16384。READ_CONTROL/READ_ATTRIBUTES/SYNCHRONIZE，只有最终文件请求READ_DATA；共享只读，不共享write/delete。共享冲突即拒绝，不能以放宽共享作为兼容fallback。实际共享模式是否如预期阻止持有文件的修改/替换，须原生探针验证。

名字只接受普通驱动盘绝对路径，禁止UNC/device/extended外部输入、drive-relative、斜杠混用、空组件、dot/dotdot、冒号ADS、控制字符/通配符、末尾空格点、短名`~`及DOS保留名；UUID与metadata严格canonical、整数大小/64位hexhash。单组件相对打开只跟随已核对祖先，重解析对象拒绝后不访问下一组件。这比一次完整路径加最终no-follow更有边界，但云端FakeAPI无法证明真实NTFS实现行为。

## ACL支持范围与威胁界限

[GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)在同一句柄上读owner/DACL，GetSecurityDescriptorControl/IsValidSecurityDescriptor/IsValidAcl/GetAce/IsValidSid做合法性及范围核对；LocalFree释放系统返回的descriptor/SID string。不调用任何SetSecurityInfo/Set-Acl，不修复既有目录。

私有root、files与文件均须owner是当前process TokenUser SID、DACL_PRESENT+SE_DACL_PROTECTED、非NULL/非空DACL、<=128 ACE。只支持简单ALLOW/DENY，未知object/callback/conditional ACE、继承标志/未知flags拒绝；ALLOW trustee仅当前用户、SYSTEM、Administrators。不模拟复杂Windows有效权限，也不忽略“貌似无害”的宽泛allow。OS打开权限检查仍必须通过，空DACL或DENY导致拒绝不放宽。NULL DACL的风险依据[Microsoft DACLs and ACEs](https://learn.microsoft.com/en-us/windows/win32/secauthz/dacls-and-aces)。该严格policy可能拒绝日常可用但超出候选范围的安全ACL，实机验证前不改变policy兼容它。

同一最终文件handle ReadFile<=16385字节，前后metadata、size/hash/UTF8核对；root/files/file ACL读前读后再核对。不防同一当前用户、SYSTEM/管理员、内核/恶意过滤驱动修改或提权；这些是可信OS安装主体，不能宣传管理员不可突破。ACL变更与文件内容并非一个跨对象原子快照，本方案不凭share flags保证ACL永不改变。非可信用户若从受限私有ACL不能取得修改权，持有祖先句柄和相对打开降低替换风险；这仍需要原生竞态试验而非云端安全认证。活跃存储过滤器/云文件/自定义文件系统均不在范围。

## 单测、原生专属探针及启用门

`tests/test_windows_file_candidate.py`在Linux验证FakeAPI流程/拒绝policy/句柄保留和关闭/固定ctypes Win64布局/相对NtCreateFile实参构造/异常handle回收。它不加载系统DLL，不证明syscall或真实安全语义。

在明确Windows11+Python3.12 x64环境，安装者可运行`powershell.exe -NoProfile -File scripts/windows/FileCandidateTest.ps1 -Python <本项目原生python>`。不使用ExecutionPolicy Bypass、不改全局策略、不请求管理员开关。要求已有.runtime，脚本只建立全新UUID候选目录/marker并给**刚创建的测试对象**保护ACL；Python先以句柄核对该私有root/marker，再只创建全新合成子fixtures。既有.runtime/root/用户文件ACL不改，不读取任意宿主路径，无真实资料、provider或PG连接。

原生probe记录正例读取（须先PASS，失败则其他拒绝oracle NOT_RUN）、三处不安全ACL、hash、UUID/ADS、硬链接、ancestor junction、持有handle期间写入与重命名拒绝、可选file symlink。symlink权限或junction创建缺失记录NOT_RUN，不提权，不删断言，不把“所有文件都拒绝”当安全通过。unique fixture/report保留供审查；输出仅计数/类别/安全数值错误，不含文件正文/账号token/真实路径。Linux Python与PS guards都拒绝且不建立fixture；PowerShell AST不代表原生运行。

全部上述原生结果、精确OS build/依赖/非管理员权限、受控替换并发试验、Windows安装与既有配置停止重启门通过并复核后，才能另行实现/审查产品dispatcher启用与owner合成文件注册适配。候选目前仅read-only，不写资源、不实现真实材料导入、危险文件转换或通用产物协议。不为“补齐”提前改`files.py`或设置开关。

## F1残余不是全部外部验证

| 类别 | 残余 | 当前判断 |
| --- | --- | --- |
| T01/AT01/05 | Windows native ctypes/NTFS/ACL/reparse/sharing/竞态、候选生命周期真实运行/精确版本 | 外部原生条件+实际验证NOT_RUN；本候选有代码/云端证据而非实际可用 |
| T01/AT05 | 候选read-only经过原生验证后产品dispatcher启用、owner合成注册/写入适配 | 仍有独立代码集成未做，当前必须关闭；不能写成“只缺实机验收” |
| T05/AT02/30 | 安全token/账号预算及两产品同协调库审批、真实书生与usage/计费 | 外部授权/预算0、LIVE实际验证BLOCKED；另一项目结果不继承 |
| T05/AT02 | 真正LIVE worker安全注入/配置接入、账号provider速率窗口轮转/实际限流接入、可核查计划修订artifact与完整before/after oracle | 尚未开放/完整oracle未实现；ENG007仅固定窗口总额度，不证明持续RPM限流，且只单case proposal与stop回填，不冒充计划修订验收 |
| T02/03/04/06及F1引用AT | 现有代码覆盖最小可信动作/权限/账本/来源与42定义的工程子集 | 原生/真实链外，AT05导入/危险渲染全流程、AT06完整事实候选/必要集中澄清等全oracle尚无；后续有界规格才实现，不以合成子集宣布完整PASS |
| 后续增强/阶段 | 窗口滚动/货币账单、完整服务办理/CaseStep/外部适配器/真实渠道/通用文件产物 | 保留未实现，按明确阶段处理；不是本轮F1最小候选范围，也不进入F2 |
| 来源/C0 | 真实目录/规则/材料许可、价值实测、模板/跨赛道/准确截止 | 授权与外部信息未核实；用户日期2026-11-05仅原样记录 |

F1仍IN_PROGRESS，完整36AT/6EX全部NOT_RUN；不是全部已实现后只剩外部门。下一步需父任务复核选择一个有界增量或等待明确实机/授权，不能在本轮扩完全部阶段。
