# ENG099 Windows 无安全 setter 原生候选

[原生适配器](../../src/parkweave/windows/create_new_readonly_native.py)新增实际ctypes创建、读取descriptor、OVERLAPPED写入及rooted rename代码；[配套测试](../../tests/test_create_new_readonly_native.py)只注入fake API/DLL函数。默认 `NativeAdapter(enabled=False, ...)` 在加载DLL前拒绝；非Windows/x64亦拒绝。显式候选调用不等于操作授权，生产helper仍暂停、没有生产caller、没有YAML或预算修改。本轮不执行Windows创建/rename/owner/ACL操作；仅授权的Microsoft公开只读文档查询及Linux mocks。

## 精确访问权与内核依据

| 对象/操作合同 | 实际DesiredAccess | 依据与限制 |
|---|---|---|
| 普通新文件 `NativeCreationContract` | `0x20082` = FILE_WRITE_DATA + READ_CONTROL + FILE_READ_ATTRIBUTES | 数据写入与OWNER/DACL及同handle属性/reparse查询。与ENG098 fake-only `0x20002`分开；不将旧mask称原生可用。 |
| replacement临时文件 | `0x30082` = 普通新建 + DELETE | 从原始CREATE_NEW handle写入再rename，不reopen获取DELETE。只有显式ReplacementContract才可请求。 |
| readonly祖先/parent pin | `0x1200a0` = READ_CONTROL + FILE_READ_ATTRIBUTES + FILE_TRAVERSE + SYNCHRONIZE | 现有目录读取及同步open；不启用traverse privilege。此mask仅目录。 |
| old/final target file query | `0x20080` = READ_CONTROL + FILE_READ_ATTRIBUTES | 仅file metadata/descriptor；无FILE_READ_DATA、FILE_EXECUTE或SYNCHRONIZE，与目录合同分开。 |
| replacement目标parent操作handle | `0x1200e2` = 上项 + FILE_ADD_FILE + FILE_DELETE_CHILD | 显式独立操作capability，用已pin ancestor相对再开同parent并匹配身份/descriptor；不是普通创建悄增权限或环境授予。 |

普通file/temp均无generic映射、WRITE_OWNER、WRITE_DAC、WRITE_ATTRIBUTES、FILE_WRITE_EA、FILE_READ_DATA或SYNCHRONIZE。EVENT独立句柄支持等待，不等待新file。请求capability并不保证权限被系统允许；所有拒绝保持失败，不提权或降级重试。

Microsoft [NtCreateFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile)明确FILE_CREATE在目标存在时拒绝、支持RootDirectory相对名称，且同步IO flags需要SYNCHRONIZE；本实现使用FILE_CREATE=2、FILE_NON_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT、NULL descriptor/EA、share=0，**不设置同步IO flags**。GENERIC_WRITE会映射额外权限，故不使用。Nt状态必须SUCCESS且IOStatus.Information=FILE_CREATED；collision保持FileExistsError，异常状态不当成功。

Microsoft [ZwQueryInformationFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-zwqueryinformationfile)要求属性/tag查询有FILE_READ_ATTRIBUTES，故显式加入这项只读权，而不是假设READ_CONTROL能覆盖metadata。实际GetFileInformationByHandle等ABI/文件系统返回仍需未来native实测，不以fake证明平台可用。

Microsoft [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)要求source DELETE及目标目录对应创建权限，并说明RootDirectory可请求traverse/read-attribute；rooted rename还涉及目标目录同步打开。当前明确声明上表parent合同。用 [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle) + [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info) class3实现普通ReplaceIfExists rooted rename：x64 buffer包含BOOLEAN、对齐RootDirectory、UTF16字节长度和相对简单名称。不用ReplaceFileW/generic fallback、POSIX-ignore-open/read-only flags或security setter。

## 固定私有root与同handle读取

正常候选root固定由源码仓库位置得到 `.runtime`；实验替换root为其下已有私有 `eng099-noncas-<canonical UUID>`。适配器不mkdir、不建立/修复ACL，不接收native任意root路径；`_runtime_for_tests`只在显式fake API seam可用。按drive→所有组件逐层打开existing目录，使用原parent handle相对open，OPEN_REPARSE且每层检查directory/attributes/volume/identity。仅固定本地NTFS volume GUID，拒UNC/network/非本地卷；所有祖先保留handle至关闭，不shareDELETE，避免普通rename祖先。每层final_path必须匹配由volumeGUID和已验证组件构造的预期路径；后续创建/写入前后重复ancestor identity/path及parent OWNER/rawDACL/control检查，不能仅靠Path.resolve或末端字符串称race-safe。

当前User每次来自process TokenUser，未使用TokenOwner或privilege。新对象默认owner可能为group，因此只读检测owner不等User时拒绝并保留空文件，不设置owner。GetSecurityInfo仅OWNER|DACL；读取IsValidSecurityDescriptor/IsValidAcl、GetAclInformation/GetAce边界，copy完整raw DACL（含slack），严格支持基本ACE policy和精确control/raw equality。descriptor和SID字符串原生allocation经LocalFree释放，失败也拒绝；SACL内容未查询，不声明完整SACL保持。

普通新建支持SESSION、CONFIG、SERVICE_LOG、初始PROCESS_RECORD和UUID binding temp，沿用ENG098 typed ObjectKind/Operation与basename白名单。仅atomic FILE_CREATE，不预先exists后覆盖、不开existing failed files修owner/ACL。新file原handle两次校验metadata/owner/完整descriptor稳定后才提供custom TextIO stream；新file不CRT转FD，任何创建后拒绝保留对象并关闭所拥有handle一次。caller借用ancestor handle别名拒绝，不接管borrowed handle。

## 显式异步写入与pending生命周期

stream对同一原始file handle调用 [WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)，每次唯一OVERLAPPED、独立manual-reset EVENT、明确offset、异步count参数NULL，用GetOverlappedResult获取实际字节数，处理UTF8及short writes。使用caller提供的同一绝对deadline，不刷新截止或修改native预算；等待EVENT，不向file请求SYNCHRONIZE。完成前后同handle校验descriptor/identity/size、parent和ancestor，失败不发OwnedRecord。没有内容readback或FlushFileBuffers持久化证明。

[Microsoft取消说明](https://learn.microsoft.com/en-us/windows/win32/fileio/canceling-pending-i-o-operations)明确CancelIoEx不是完成保证。超时或未知completion error先强引用保留file handle/buffer/OVERLAPPED/EVENT，再请求取消；模块级retention跨adapter关闭/GC继续持有，pending file的CloseHandle被拒绝。后续创建/写入拒绝，关闭报告cleanup未证实，不发成功record；晚到IO仍可能写入，不能承诺失败文件一直为空或已停止。显式 `poll_pending()`非阻塞只读检查，仅成功终态或ERROR_OPERATION_ABORTED才释放；未知状态/异常NtCreate pending保留。terminal cleanup失败保留固定拒绝且不重复close。保留可能泄漏资源至进程结束，这是不冒称cleanup完成的保守候选，未来native收敛证据尚缺。

## 原子rename代码与CAS限制

`replace_record`是实际可调用native primitive代码，**默认安全替换仍拒绝**。默认ReplacementContract.require_target_cas=True；[MS-FSA FileRenameInformation](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/87f86c9b-6c2a-4803-84b7-131a74a434fa)及所用rename结构没有expected-target-fileID比较参数。本适配器不把pre-read identity→pathname replace→post-read升级为线性CAS；普通target handle不shareDELETE会阻碍自己的replace，释放或shareDELETE不能排除末刻同User替换。默认在任何temp创建/写capability请求前返回TARGET_ID_CAS_UNAVAILABLE。

仅调用者同时明确 `require_target_cas=False`、`explicit_noncas_exclusive_candidate_namespace=True`，且adapter使用新UUID实验namespace、精确replacement mask时才允许实验路径。该“exclusive namespace”是调用者实验范围声明，**不是内核排除所有同User/admin竞争的证明**；不得用于生产固定actual STATE或自动fallback。

实验路径只接受本adapter首次成功关闭后签发、仍保存的exact OwnedRecord对象作为target，且kind为初始PROCESS_RECORD；复制/伪造ticket、既有失败文件、任意target路径拒绝。沿已pin parent readonly打开并匹配old target的identity/raw descriptor/size；独占创建特定UUID temp、同原始handle核验→异步写入→再次核验old target与parent；释放old query handle后，使用明确replacement parent capability和原始temp handle rooted rename。rename后检同原temp handle的owner/raw/metadata/final name，关闭再相对打开最终target核对同identity/descriptor/size。任何postrename失败标记 `publication_may_have_occurred=True`，撤销ticket，不能把已发布对象回滚/删除来假装未发生。

成功receipt限定为 `PUBLISHED_FINAL_VERIFIED_NONCAS`，并强制 `target_cas=False`、`same_user_namespace_race_unresolved=True`、`content_readback_verified=False`、`durability_verified=False`。它只表示该实验候选的最终metadata/name核验，不是安全替换验收、正文readback、crash durability或cleanup证明。旧target可能在最后窗口被其他同User inode代替；此未关闭risk不能靠fake PASS关闭。

## 逐路径audit与工程边界

| 路径 | 旧实际保护/创建 | 本轮处理 |
|---|---|---|
| SESSION/CONFIG | 暂停owner helper固定CREATE_NEW | 独立ordinary adapter可调用代码，不接线、不恢复seed/setup；group owner仍拒绝。 |
| SERVICE_LOG | lifecycle普通append，既有log保留 | 候选仅首次CREATE_NEW；没有existing log append/owner修复。 |
| 初始STATE/temp/最终STATE | exclusive初始/临时bytes后os.replace | 新普通STATE、binding temp代码；最终实验primitive与默认CAS拒绝边界如上，未替代生产save_execution_bindings。 |
| ROOT `.runtime` | [lifecycle128–141](../../scripts/windows/lifecycle.py#L128)新目录SetOwner/Set-Acl；既有只读检查 | 原样保留。新experimental子目录需要另行明确私有新目录前置；适配器不创建/赋权。 |
| TraceRoot `$RUNNER_TEMP/parkweave-native-trace-GUID` | [Engineering53–69](../../scripts/windows_ci/Engineering.ps1#L53)各Action新建保护 | 未改，仍有旧SetOwner/Set-Acl调用，不能说全链无安全写。 |
| PGRoot `$RUNNER_TEMP/parkweave-server-ci-GUID` | [Engineering78–80](../../scripts/windows_ci/Engineering.ps1#L78)Prepare保护 | 未改，不涵盖PG data/cluster-state/root权限操作。 |
| ServerFile fixture `.runtime/server-file-engineering-GUID`及marker | [ServerFileTest8–24](../../scripts/windows_ci/ServerFileTest.ps1#L8)分别设置owner/DACL；不在RUNNER_TEMP | 未改，不启用FILES、不删fixture保护或已有失败对象。 |

ENG097历史69文件manifest/HEAD来源已修并核验，不再当作当前阻塞；root本轮ENG099冻结collection为75文件/2088 cases、953 AST diagnostic IDs，四片529/517/534/508，原预算不变。collection不是PASS；完整Linux执行由root另记。ENG098协议0x20002保留为历史fake seam，未暗改。原生code本轮NOT_RUN，最新isolated Job CI不是full，Job normal EXIT17/精确handles、S1–S4完整counts/coverage、原完整预算及全链zero-security-write均未测。此候选的mock ABI/流程结果不取代这些门槛。

最终定向Linux结果：本模块16项配套gold、独立 `test_native_creation_invariants.py` 的58项gold及既有ENG098协议76项，共150 PASS，1项现有Starlette弃用warning。覆盖精确mask/ABI、两次query、TokenUser、raw descriptor/free、short write、pending未知终态/取消/保留与失败close、ancestor reparse/path、角色/所有权、默认CAS前置拒绝、显式UUID非CAS及最终rooted identity查询。全部fake-only，无native skip冒充native通过；独立gold文件由其owner维护，本任务仅修改本模块、配套测试与本文。

## 最终候选专项

冻结源码 SHA256 `da5e29826527f7c86e7e1905b91d9b7620f9ab4a434d33cfa7e8460ad8b46fad` 的真实 Linux fake/ABI 专项为 **150 PASS / 0 FAIL / 0 SKIP / 1 既有警告，0.20 秒**：58 项独立 handle/DLL 生命周期金标准、16 项适配器候选与76项既有 ENG098 协议测试。精确文件查询mask、原parent/ancestor provenance、同创建handle、raw DACL、pending关闭拒绝、终态poll、UTF8 short write、default CAS拒绝与显式非CAS rooted rename均有可执行回归。测试仅注入API/DLL函数；Windows真实返回、原生创建/写入/rename、normal/S4和原完整workflow均 **NOT_RUN**。

最终专项独立证据为 `/tmp/eng099-native-da5-final.log` 与 `.xml`；先前 `eng099-native-gold-final` 只绑定此前 `bc0dced5…` 版本，不能作为当前源码结论。源码后续补充固定仓库形状检查以及创建/rename前后的同一绝对deadline检查，最终专项在这些修正后的同一源码运行，不声明逐分支覆盖或原生系统调用可被期限强制中断；工程预算不变。完整回归及远端同步见 [ENG099业务恢复记录](ENG099-DispatchMaterialRecovery.md)与[机器证据](evidence/eng099-recovery-native.json)。
