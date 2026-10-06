# ENG072 owner 暂停、只读差异审查及 Job/端口候选

本轮仅本地候选与独立review，不push/CI/LIVE，不执行任何原生owner流程，不改变新增日志、STATE、FILES或既有对象owner/ACL。不扩大授权来掩盖原SESSION/CONFIG保留权限合同的失败。实际Windows仍ENG071唯一run37518589501：normal最小Job FAIL/descendantLIVE、timeout与unrelated exactgold PASS、S4 timeout/countNULL/coverageFalse。

## owner：先停止，再区分已证明与未知

默认SESSION/CONFIG入口现在直接OWNER_MUTATION_PAUSED，在构造backend、请求token/创建文件之前拒绝。注入WindowsSessionFile实例或子类同样拒绝；native setter也无条件拒绝。没有ENV恢复开关、替代API、扩大target或失败后existing文件修复。mock backend仍可验证原严格事务，但不是原生恢复开关；本地暂停尚未push，不能称远端代码已部署暂停。

ENG071前调用的真实参数是 `SetSecurityInfo(handle,SE_FILE_OBJECT=1,OWNER_SECURITY_INFORMATION=1,sid,NULL,NULL,NULL)`，没有DACL/SACL flags；NULL参数在未指定相应flag时不会表示设置NULL DACL。这已经是文件对象支持API的最小owner-only请求，但请求最小不代表实际其他权限已保持。[Microsoft SetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo)

TOKEN_USER backing buffer在当前_user返回后由事务局部变量保留直到verify，token句柄关闭不会释放调用方buffer。before/after owner/DACL指针分别依附两份GetSecurityInfo返回SD，verify/compare结束才LocalFree，未找到生命周期悬空或可证明ABI错误。官方要求释放返回副本，而指针有效范围取决于查询flags。[GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)

当前已证明的原生事实仅是：目标owner匹配；两份ACL完整存储块不等；两份**返回副本**control除owner-defaulted外不等；流转交前拒绝。原生有效ACE、具体delta bits和真实权限语义变化仍UNKNOWN，既不能称无害规范化，也不能将完整存储不等直接升级为访问语义变化。

当前inspect复制AclSize整个块。AclSize包含潜在unused memory，AclBytesInUse可能小于分配容量，保留/容量/slack差异可触发原比较。本轮直接调用当前inspect实现配纯ctypes fake读API，复现零有序ACE相同/slack不同/fullbytes不等/control相同；另设control0400变化时能单独固定报告DACL_AUTO_INHERITED。**该mock不证明ENG071实际仅slack差异，尤其不能解释实际control同时不等。** [ACL规范](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-acl)，[ACL_SIZE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-acl_size_information)

新owner_descriptor_observation仅在已有复制bytes上分开raw equality、revision/capacity/reserved/slack及有序ACE完整bytes，control差异输出固定bit名；SID/ACE内容/mask/opaque payload不公开。semantic_permission_change始终UNKNOWN，strict_contract仍全bytes/control保持才UNCHANGED，没有裁剪slack来让真实事务通过。NULL与empty区分，非法长度/边界/ACE size拒绝。未来native读取应使用IsValidAcl/GetAclInformation/GetAce等官方读取函数验证，不将本结构观察器当作完整AccessCheck证明。

查询只有OWNER|DACL；此前“All DACL/SACL ... stays”注释过强，已改为返回OWNER/DACL descriptor control并明确SACL内容未查询。不为观测加ACCESS_SYSTEM_SECURITY或特权，不能声称全部SACL已验证。[GetSecurityDescriptorControl](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptorcontrol)

独立审查排除把SetKernelObjectSecurity当文件owner修复路线：官方明确文件系统对象不应使用该函数。因此本轮没有激活替代setter，也没有在CREATE_NEW descriptor里指定owner来绕过原合同；这些都尚缺权限保持证据。[SetKernelObjectSecurity](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-setkernelobjectsecurity)

## Job：独立复现逻辑缺口，原生机械原因不冒判

独立agent通过fake kernel调用**当前**stop_tree、server_identity.identity与run实现：TerminateJob成功/class1 Accounting size48/ActiveProcesses0使cleanup立即TreeStopped；同一精确mock对象WaitForSingleObject0=258仍LIVE；主退出17保持，close顺序thread→parent→job。Accounting48及offset0/8/16/24/32/36/40/44无错位证据。这是可控逻辑复现，不是新的Windows运行。

ENG071原生normal的primary17/unrelatedexactLIVE均已过，后代同identity未signal，不能被cleanup盖PASS。原最小recipe在run返回、Job关闭后才open后代query handle，因此无法判断其inner Job归属或终止→accounting→kernel signal时序。不能直接称escape；timeout PASS和无关gold保持，S4仍未验。

新job_stop_observation是未接线readonly候选：调用方先持有并确认本次精确readonly process handle及未关闭innerJob，再在stop_tree内close(job)之前观察membership/accounting/signal。使用同一cleanup_started+5秒截止，不刷新或扩预算，最多8采样，逐读取gate；仅IsProcessInJob/QueryInformationJobObject/WaitForSingleObject，不OpenPID/kill/Terminate/close/调整权限。ReturnLength必须48，超指针宽度handle/bool/0/负值在任何backend读前拒绝。读不是原子快照，UNKNOWN/nonmember不升级为停止；EXACT_PROCESS_SIGNALED仅代表该已核对进程，不代表整棵树。

独立9个mock gold覆盖LIVE→SIGNALED、NON_MEMBER、未知读取、已有截止/未来start/采样上限/读跨截止/长度错误；主线程又加入5个非法handle参数gold分别验证process/job零读取。没有修改production Job stop算法、延长timeout、自动接CI或宽杀进程。实际Windowsmembership与signal序列仍待可用且获授权的定点只读测量，不能以本地mock替代。

## 端口：用固定枚举拆开三个数据库断言

原DATABASE_GOLD共同覆盖phase、category及安全command不含port三条。新增database_refusal_observation分别输出database_error（OPERATIONAL_ERROR/CONNECTION_TIMEOUT/OTHER）、OperationalError family bool与三gold bool，native候选trace可保留它们，仍没有放宽原base类别断言。

本地构造base OperationalError：三gold PASS；ConnectionTimeout：family=true、phase/redaction PASS、category=false（精确typename白名单OTHER）；未知RuntimeError：family/category false，不接受任意OTHER。所有输出只有固定枚举/bool，poison/DSN/port/错误文本不输出，没有网络调用。本例证实fixture候选具体失败机制，**实际ENG071 native subtype/三条中的具体FAIL仍UNKNOWN**，没有声称端口问题已修复或再执行原生测量。之前WSAEADDRINUSE来自occupied检查，不是10013或数据库错误码。

## 集中权限清单与验收边界

[集中owner对象及风险清单](ENG071-OwnerScopeDecisionInventory.md)保留新SERVICE_LOG、初始STATE、受限原子STATE临时inode；FILES仅为Windows未启用候选。用户醒来后的对象范围确认不能替代SESSION/CONFIG其他权限保持证明，更不能授权既有文件ACL修复。本轮不提问或执行新增权限动作。

最终本地8模块312PASS/6nativeSKIP/14.05s；独立34PASS/1nativeSKIP及5非法handle gold PASS，NO_BLOCKERS。初次默认sandbox记录2个loopback/PG测试FAIL（未导出完整trace）；按既有同身份正式流程验证97PASS/2nativeSKIP，最终312/6记录保持；不把它们计作原生。

fresh collection1354，四片345/345/349/315 Counter精确相等；旧ENG0711331 stablekeys全保留+23、623函数、51测试+31实现82 raw指纹一致。collect不是全量PASS，历史S4实际collect310/countNULL/timeout不改写为候选315已验。

固定证据：[ENG072 JSON](evidence/eng072-owner-pause-readonly-candidates.json)。原环境与备份保留；F1未签收/F2仅并行，Server非Win11、R4关闭、真实模型/预算0、不自动资格判断或外部履约。
