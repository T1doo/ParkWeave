# ENG098 CREATE_NEW readonly 校验候选

新增独立模块 [create_new_readonly_candidate.py](../../src/parkweave/windows/create_new_readonly_candidate.py) 与 [测试](../../tests/test_create_new_readonly_candidate.py)。生产 `synthetic_session_file.py` 未改、owner mutation仍暂停；本模块没有production调用。**原生adapter未实现**，默认调用返回 `NATIVE_ADAPTER_NOT_IMPLEMENTED`，不因Windows平台自动选择backend。不存在pathname fallback、owner/ACL setter、privilege或security descriptor安装；没有运行Windows或网络。

## 创建与只读合同

候选是显式backend协议及可测试的决策流程。调用者先提供已持有的私有目录handle、显式预期parent OWNER/rawDACL/control以及独立预期child OWNER/rawDACL/control。`verify_private_directory`在同一parent handle复核metadata、当前User SID、受保护私有ACL和原始descriptor精确相等；返回绑定parent身份/descriptor/User的不可变合同。caller仍须证明固定仓库`.runtime`范围、本地文件系统、handle获取/祖先重解析保护及存续；该合同不是sealed provenance witness，fake不能提供真实路径安全证明。未来适配器必须补可信范围证明才可接入任何生产调用。

`Request`强制ObjectKind、Operation、basename。创建仅以下白名单：SESSION=`synthetic-sessions.json`，CONFIG=`windows-config.json`，SERVICE_LOG=`windows-services.log`，PROCESS_RECORD_INITIAL=`windows-processes.json`，BINDING_TEMP=`.process-binding-<32位小写hex>.json`。类型与文件名错误在backend调用前拒绝；不接受任意路径、ADS或目录分隔符。协议创建必须相对**原parent handle**原子独占CREATE_NEW，share=0，security_attributes=None，已有对象/竞争拒绝，不以预先exists检查替代原子创建。`CREATE_NEW=1`只表示Win32语义，不能直接当NtCreateFile disposition使用。

最小请求权限精确为 **FILE_WRITE_DATA(0x2)|READ_CONTROL(0x20000)=0x20002**。独审指出GENERIC_WRITE会映射到SYNCHRONIZE、写EA/属性等额外权限，故候选不使用generic access bits，也不显式增加SYNCHRONIZE、WRITE_OWNER或WRITE_DAC。fake/static证明本协议mask精确，不证明Windows实际创建或CRT流可在此mask工作。若原生同步/CRT适配需要额外权利，必须另行审查；本轮不选择悄增权限或较弱路径校验。

成功取得新child handle后，在同一handle读取两次metadata与OWNER/rawDACL/control；owner必须等于当前**TokenUser** SID，不能默认TokenOwner group等于User，也不为group mismatch设置owner。raw DACL与显式child合同完全相等，包括ACE顺序、mask、slack；control全值完全相等（候选没有OWNER_DEFAULTED豁免）。NULL/空ACL、未知ACE/control保留位、无DACL_PRESENT、public allow SID、reparse/nonregular/多链接/非零内容/volume差异拒绝。parent在创建前、两次child读之间和转流前复读，parent身份/权限/User变化拒绝。

child允许经过合同明确验证的简单继承ACE，不能从parent raw bytes直接推导child raw bytes。parent私有ACL检查复用现有readonly policy；SYSTEM/Administrators属于该既有策略的可信SID，这不构成抵抗管理员修改证明。backend descriptor读取只OWNER|DACL，必须原生validate/copy/free，SACL内容不查询、不声称保持；当前fake仅证明流程，无法证明LocalFree和ABI。

通过检查才转移原handle到FD、FD到stream，不重新按路径打开。协议规定transfer失败保留handle所有权、wrap失败保留FD所有权；失败关闭对应资源一次，新失败对象保留，正文未写，不unlink、不修ACL、不重试owner。cleanup失败保留原主要拒绝并标记固定boolean，不公开私有错误文本；不是cleanup已成功。caller保留parent handle至少至stream关闭。只读快照不提供管理员对抗、token原子性或转流后descriptor永不变化证明。

backend仅可返回fresh child handle。候选先校验有效handle并拒绝与借用parent同值，再登记child所有权；别名拒绝不关闭caller的parent。该负例有独立fake gold；未来native adapter仍须证明真实返回handle归属。

## 对象范围与未实现部分

| 路径/对象 | 现有生产行为 | 本候选覆盖与边界 |
|---|---|---|
| SESSION/CONFIG | 固定新对象owner helper CREATE_NEW；native暂停 | 仅独立新建协议，既有失败文件拒绝；未替换helper、未恢复seed/setup。 |
| SERVICE_LOG `.runtime/windows-services.log` | [lifecycle第421行](../../scripts/windows/lifecycle.py#L421)普通append，可已有文件 | 新SERVICE_LOG类型可测试首次CREATE_NEW+检查；没有实现既有log append兼容或生产接线，不能设置已有owner/ACL。 |
| 初始STATE `.runtime/windows-processes.json` | [第415/428行](../../scripts/windows/lifecycle.py#L415)拒已有记录后普通`open('x')` | PROCESS_RECORD_INITIAL可测试首次CREATE_NEW；真实private PID/ctime/command正文写入在stream核验后，候选本身不生成/记录这些内容。 |
| `.process-binding-UUID.json`与替换后最终STATE | [第235–243行](../../scripts/windows/lifecycle.py#L235)exclusive temp后`os.replace`换inode | BINDING_TEMP仅验证临时新对象；最终对象发布/目标身份/竞态/descriptor合同**未实现**。PROCESS_RECORD_REPLACEMENT/ATOMIC_REPLACEMENT及独立replace入口固定 `ATOMIC_REPLACEMENT_NOT_IMPLEMENTED`，零backend动作。不得将temp通过升级为安全replacement覆盖。 |
| ROOT `.runtime` | [第128–141行](../../scripts/windows/lifecycle.py#L128)新目录SetOwner/Set-Acl，既有目录只读ACL检查 | 不创建目录或设置保护；候选需要已验证parent。原有SetACL未改，普通mkdir不是私有contract证明。 |
| TraceRoot `$RUNNER_TEMP/parkweave-native-trace-GUID` | [Engineering第53–69行](../../scripts/windows_ci/Engineering.ps1#L53)每Action新建后SetOwner/Set-Acl | 不在文件kind白名单；未覆盖这些新目录和其trace子对象保护。 |
| PGRoot `$RUNNER_TEMP/parkweave-server-ci-GUID` | [第78–84行](../../scripts/windows_ci/Engineering.ps1#L78)Prepare新建后同SetOwner/Set-Acl | 不覆盖PG目录、cluster-state/data或owned cluster合同。 |
| ServerFile fixture `.runtime/server-file-engineering-GUID`及marker | [ServerFileTest第8–24行](../../scripts/windows_ci/ServerFileTest.ps1#L8)目录与marker分别SetOwner/Set-Acl；实际不在RUNNER_TEMP | 不覆盖目录/marker保护，不接通生产FILES，不删除旧保护或失败fixture。 |

普通synthetic fixture创建与安全设置分开：三项测试使用Linux `O_CREAT|O_EXCL`和真实FD证明已有bytes保护、失败空文件保留/FD关闭、stream最终关闭；descriptor和parent identity仍为fake。这不是Windows owner/DACL、reparse或handle-relative创建证据，也不能让该fixture成为默认backend。

## 验证与后续门槛

最终Linux定向结果：本候选76 PASS，加既有session/config兼容46 PASS/2 native SKIP，合计122 PASS/2 SKIP，1项现有Starlette弃用warning。未执行native；源码/test/docs freeze需独审完成后由root记录实际指纹。

候选测试覆盖typed角色/错basename、创建竞争、unsafe parent及创建后变化、TokenOwner group mismatch、rawDACL/control变化、未知/非法descriptor、reparse/硬链接、转流/wrap/cleanup拒绝及最终replacement关闭。已有session/config测试同时验证暂停路径保持；Linux结果只代表协议/fixture回归，native原创建测试仍SKIP，不声称原生完成。

ENG097 manifest当前69文件来源已提交核验PASS、Linux1817PASS/9nativeSKIP；这是已修工程项，不再列作Windows阻塞。新增本片测试进入后续collection须重新冻结manifest/allowlist，原预算不改。最新CI37613345338仅隔离Job成功，非full验收。后续仍需独立确认严格mask的native/CRT可行性、可信parent provenance、samehandle descriptor/free、creation与replacement分别的安全验证，再按原完整预算验证Job normal EXIT17/精确handles、S1–S4真实终态/coverage及cleanup。**本轮零安全setter调用；原生全链“zero security writes”未测且旧目录保护仍存在**，不把源码候选升级为实测承诺。不改YAML、暂停生产或native预算。
