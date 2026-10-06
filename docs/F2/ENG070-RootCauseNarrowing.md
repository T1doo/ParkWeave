# ENG070 剩余七 case 根因收敛与最小原生方案

仅本地代码 `1fe2a06b1973d522fe1f0968287c338cb1f0da7b`，独立NO_BLOCKERS；不push/CI/LIVE，不改既有owner/ACL、不增加runner/权限/预算。最后实际Windows仍[ENG069 run37511398754](https://github.com/T1doo/ParkWeave/actions/runs/37511398754)的精确c10fef1：1265 PASS/7 FAIL/51 SKIP；Restart private_acl/ACL_OWNER_MISMATCH，具体对象UNKNOWN。以下区分源码可证缺陷、受控复现及需要原生测量的分支，不能把本地结果改写为原生通过。

## 为什么 Restart 没有 ACL 对象

原acl_check_command实际读取ROOT、files、SESSION、CONFIG、windows-processes.json、windows-services.log六路径。只为ROOT/SESSIONS/CONFIG设置枚举，其他三个把AclObject设null；Refuse-Acl只输出三个已知枚举。故附属对象owner不符会exit2/ACL_OWNER_MISMATCH但不打印对象，现有安全parse也无法保留它。这是确定的报告覆盖缺陷；真实本轮对象仍可能受其他输出错误影响，不能仅由缺字段断定具体文件。

本轮仅复用既有acl_object字段，补原已检查对象FILES、PROCESS_RECORD、SERVICE_LOG固定枚举。全部路径、owner/SID比较、Allow规则及Root继承拒绝条件保持，未知/多行/非ASCII/poison拒绝保持；无新通用追踪字段。受控PowerShell分别让三个对象owner不符，均exit2并准确输出一个枚举，经native_acl_check→start marker→Restart project→annotation→完整publication_capture保留；3 gold PASS，既有字节/inode/mode不变，没有Set-Acl或SetOwner。

## Restart 文件写入路径只读核对

| 对象 | 当前源码写入路径 | 对本次Restart的收敛 |
| --- | --- | --- |
| SESSIONS | CLI seed第一次固定路径create_synthetic_session_file；已有则拒绝 | 未发现原子替换/覆写session；原生Setup链进入Start说明项目root场景首次事务已通过（源码绑定推知），隔离owner test失败仍另列。 |
| CONFIG | setup固定repo路径create_synthetic_config_file；已有Setup立即拒绝 | 未发现临时替换配置；不改既有文件owner/ACL。 |
| PROCESS_RECORD | 首次x创建；保存绑定写新.process-binding临时文件并os.replace STATE | 会换inode，临时对象由普通创建得到metadata；不是config/session的owner事务。首Stop后已有强制不存在断言，Start前置STATE.exists拒绝；在本次正常控制流中STATE不是Restart ACL阶段的首要候选，外来竞态未实测。 |
| SERVICE_LOG | Start在private_root检查后普通open('a',UTF8)；Stop保留log | 首Start后新出现且持久，是优先核验候选。普通创建得到的默认owner不保证等于TokenUser，不能从Root继承Allow规则推出owner相同。真实owner/SID及该对象尚未原生输出。 |
| FILES | files功能create=True才mkdir；当前LOCAL app环境不传file_root，fixture目录另属validation | 仍补其实际检查对象，不能仅凭缺字段断定本次files被创建或owner不符。 |

当前事实不支持将Restart归因于端口TIME_WAIT、session原子替换或状态文件未被ACL检查：STATE此前是已检查但没有枚举。仅元数据替换本身就可能带来不同owner；本轮不改状态保存设计以猜测解实际日志owner问题，也不取消附属对象检查。

**权限边界与具体候选风险：** 若原生枚举确认SERVICE_LOG首次创建owner不符，需要的目标会是`.runtime/windows-services.log`首次新建的verified-owner句柄事务；这超出当前session/config首次范围，本轮未写该实现或执行任何owner更改。日志可能含私有诊断，必须保持原DACL/control和严格拒绝；既有log仍不得自动修owner/ACL。PROCESS_RECORD及其新临时文件、FILES目录若确需owner事务也各是额外目标，不能复用session/config内部helper绕过路径授权。现有对象保护、拒绝与外来进程无signal合同保留。

## 七 case 逐项状态

| ENG069实际函数/数量 | 已收敛证据/本轮处理 | 尚缺原生证据 |
| --- | --- | --- |
| windows_port_probe_requires_exclusive_before_bind /1 | ENG069已本地2815139修正Linux98与Windows10048注入政策；occupied与unknown/permission独立gold不变。本轮不把该fixture错误当作真实产品端口原因。 | 未再次原生执行，该CI历史FAIL保留。 |
| real_loopback_refusal_and_occupied_port_are_distinct /1 | 实际监听占用与已关闭自己listener的database_connect是两个阶段。Linux真实gold通过；Windowserror10013仍拒绝，10048才busy，不放宽独占bind。 | 原FAIL是哪段、errno/winerror或psycopg category未公开；最小原生方案分段观察既有固定拒绝字段，不杀外来listener/不改SO_REUSEADDR。 |
| actual_chinese_UI_http_under_non_utf8_path_default /1 | 源码read_text进行universal newline规范化，原response==rawwebbytes把checkout换行字节当API文本gold。受控真实CRLF HTTP前例在status200/UTF8 header已通过后确切失败于旧rawbytes断言，owned thread清理正常。仅fixture使用独立完整UTF8 canonical bytes，LF/CRLF各保留legacy500/current200，5 HTTP/acceptance gold PASS；生产API未改。 | 真实Windows失败参数/断言点仍UNKNOWN；不得宣称实际HTTP已关闭。 |
| native_session_owner_matches_current_user_and_existing_bytes_protected /1 | 未找到源码可证ABI bug；首次TOKEN_USER backing、CREATE_NEW、OWNER_ONLY、owner验证、DACL/控制位一致、CRT转移顺序保留。existing lstat/80/183与5/32各自gold已通过。 | FIRST_CREATE或SECOND_REFUSAL/bytes分支未公开；原Setup实际项目root路径能通过不证明独立TempPath场景。用固定owner阶段及三个bool取得缺口，不扩大owner范围。 |
| native_config_first_creation_and_existing_bytes_protected /1 | 共享同一事务，repo-bound固定路径保持；未发现配置替换。新控制位负例证明verified owner与相同DACL也不能接受其他控制位变化，3 gold PASS、不转移token流。 | SessionOwnerError已有固定reason或哪次阶段未知；不删DACL/control guard或把owner仍不同当PASS。 |
| native_job_stops_owned_descendant_and_preserves_unrelated_and_primary /2 | 已有readonly精确PID/ctime/kernel signal oracle，不可拿psutil retainedPID为活或unknown为dead。原记录直接write_text有partial读窗口，但normal退出17前完成写，不能把此候选归为两例共同根因。unrelated.poll目前只观察managed launcher，也不能证明真正leaf。 | 两个参数均实际FAIL，但primary/记录/无关leaf/descendant kernel哪项失败未知。提供可直接运行的受控最小原生方案，保留5/2秒及原Job5秒清理，atomic记录、经过当前runtime authority绑定的无关base leaf+持query handle、primary/leaf/descendant三项独立gold；缺记录/拒绝/unknown均FAIL。 |

## 最小原生测量已具体化；本轮未执行

[受控原生验收方案](ENG070-MinimalNativeOraclePlan.md)含可作为指定managed Python stdin直接运行的两场景代码，仅原production Job、管理进程链及本次Popen leaf；不按记录PID kill、不创建新身份/runner/权限、不访问模型。只输出固定stage/category/reason与状态枚举，不输出SID/PID/path/命令/错误文本；normal5秒、父timeout2秒、Job清理5秒保持。leaf清理与query handle close独立finally，setup/authority拒绝固定字段；任何unknown不形成PASS，也不因TreeStopped形成PASS。

owner和真实port/HTTP分开测量，owner阶段固定CURRENT_USER→CREATE_NEW→INSPECT_BEFORE→SET_OWNER→INSPECT_AFTER→VERIFY_OWNER→DACL_COMPARE/CONTROL_COMPARE→FD_TRANSFER/TEXT_WRAP→FIRST_BYTES/SECOND_REFUSAL/EXISTING_BYTES；仅已有SessionOwnerError固定reason/category和owner_same/acl_equal/control_equal bool。当前可用环境是Linux，本轮不触发新Windows CI或改变runner，因此没有实际原生执行；方案仅语法/静态审查及Linux平台guard固定NATIVE_PLATFORM_REQUIRED无副作用验证，不能称native验收通过。

## 本地验证与交付

- 最终10模块318 PASS /6 native SKIP /22.32秒，包含真实HTTP/loopback、临时PG、PS metadata doubles、完整发布与manifest；没有执行native方案。
- 独立NO_BLOCKERS；独立56 PASS（2deselect）及控制位3 PASS，native方案闭角/语法检查通过。
- fresh collection1331、pieces345/327/349/310精确multiset等于global；旧1323 exact stable keys全保留、8新增，51测试文件/617函数白名单。旧HTTP两case保留原参数轴，CRLF使用独立测试，最终旧key全部保留。
- 代码commit的51测试+27实现文件blob/raw/manifest SHA256逐项一致（78），native方案及报告仅本地。此前完整native1323结果与历史本地1297/1/9均保留，不把收集1331称全量PASS。

F1未签收/F2仅并行，Server非Win11，R4关闭，真实模型调用/预算0；原环境及恢复备份保留。剩余原生根因缺口已写为具体对象/阶段验收，等待测量，未自动执行owner权限变更或第二CI。
