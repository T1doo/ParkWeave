# ENG098 Windows 最小动作统筹包

代码核对基线 `f34b28b2199f3c112219c99f2bfeb63b8dae9d8c`。本包只整理对象、责任和依赖，不申请权限，不授权执行owner/ACL操作，也不激活安全代码或恢复workflow。Server探索不构成Win11/F1签收；R4关闭、真实模型预算0，原native预算和当前默认workflow保持。

## 已完成的工程项与证据边界

ENG097过期manifest已修复：69测试文件、1826 collected cases，四片453/459/458/456，当前global↔四片stable multiset精确相等；不删除原测试文件或改变稳定ID规则，旧private1463 keys逐项继承未核验。最终manifest SHA256 `9e884187d64515cd2fbc7d636a78a18a52a659989d1bb8aa1345c444f0ae6d9e`。工程fixture53 PASS；root最终Linux1817 PASS/9 native SKIP。[ENG097最终记录](ENG097-WindowsFullAcceptanceBlockers.md#L69)及本地 `.runtime/eng097-final-sync.json` 记录提交后 `PASS_69_TEST_FILES`、249冻结文件零mismatch，已闭合本次HEAD/blob/worktree来源前置。不是Windows原生通过。

本地既有同步记录确认最新CI run **37613345338**、attempt1、source上述HEAD、completed/success，仅 `EXISTING_SERVER_ISOLATED_JOB_ONLY`；不补取网络或日志。[当前workflow第49行](../../.github/workflows/windows-server-engineering.yml#L49)至末尾只执行独立controlled Job，未执行Prepare/Lifecycle/Validation/四片/Publish/Stop。ENG078旧run成功且直接receipt不可用的历史边界仍保留；最新isolated success同样不替代全量。原生Job normal历史反例、DB实际gold子型、S4完整终态尚未关闭。

## 精确对象与当前创建语义

| 对象组 | 当前具体对象及入口 | 现有保护/限制 | 最小需确认的动作边界 |
|---|---|---|---|
| SESSION | CLI固定相对路径 `.runtime/synthetic-sessions.json`，调用方须固定仓库cwd；[session helper第100行](../../src/parkweave/synthetic_session_file.py#L100) | `lstat`拒绝既有对象；`CreateFileW` disposition=1即CREATE_NEW、share=0，只向新对象请求WRITE_OWNER，不启用privilege，[第47–58行](../../src/parkweave/synthetic_session_file.py#L47) | 仅固定首次新建事务、owner设置及原合同验证；不得接管既有空文件/链接/目录。路径范围确认不等于权限保持确认。 |
| CONFIG | 仓库绝对 `.runtime/windows-config.json`，[第108–113行](../../src/parkweave/synthetic_session_file.py#L108)；lifecycle `write_exclusive(CONFIG)` | 同一CREATE_NEW helper；当前native构造/创建前就拒绝OWNER_MUTATION_PAUSED | 与SESSION逐项确认；不是任意JSON文件接口。 |
| SERVICE_LOG | 仓库 `.runtime/windows-services.log`，[lifecycle第421行](../../scripts/windows/lifecycle.py#L421) | 普通 `.open('a')`，可复用既有文件；当前没有该对象独立CREATE_NEW owner事务；Stop保留log | 若需新增首次创建保护，确认固定新对象/句柄、继承及DACL/control合同、重解析/竞态/共享风险；既有log继续只读检查，不自动修复或覆盖。ENG071 owner mismatch已定位此对象。 |
| PROCESS_RECORD初始 | 仓库 `.runtime/windows-processes.json`；Start先拒绝已有STATE，[第415行](../../scripts/windows/lifecycle.py#L415)，第428行写入 | `write_exclusive`为普通`open('x')`（CONFIG除外），[第58–61行](../../scripts/windows/lifecycle.py#L58)；包含私有PID/ctime/命令绑定 | 仅本次Start独占新对象，不扩至已有记录；未实测该对象owner mismatch，不能列为已失败。 |
| PROCESS_RECORD替换 | 同目录 `.process-binding-<uuidhex>.json`，[第235–243行](../../scripts/windows/lifecycle.py#L235) | 独占临时文件；两次比较原STATE bytes，`os.replace`换inode；finally清临时路径 | 确认新临时inode保护、发布前验证、目标竞态和替换后metadata合同；只修初始STATE不能覆盖替换。现有bytes检查不能冒称完整重解析/句柄竞态证明。 |
| 生命周期ROOT | 仓库 `.runtime`，[第128–141行](../../scripts/windows/lifecycle.py#L128) | 既有root只做native ACL检查；新root `mkdir()`后SetOwner/受保护DACL/current-user FullControl再检查 | 单独确认首次新目录保护边界；既有ROOT不重写。 |
| TraceRoot | `$RUNNER_TEMP/parkweave-native-trace-<GUID>`，[Engineering第66–69行](../../scripts/windows_ci/Engineering.ps1#L66) | 每个Action都New-Item后Protect-NewDirectory，包含Publish/Stop；SetOwner/Set-Acl见第53–58行 | 新目录及其诊断子对象独立范围；不是SESSION/CONFIG合同，也不是不调用owner的阶段。不得删保护来构造owner-free路径。 |
| PGRoot | `$RUNNER_TEMP/parkweave-server-ci-<GUID>`，[第78–84行](../../scripts/windows_ci/Engineering.ps1#L78) | Prepare新建后同样Protect-NewDirectory；后写`cluster-state.json`、data等 | 新PG根与后续子对象/本次owned cluster的创建、验证、清理另列；不发现/接管/停止其他PG实例。 |
| ServerFile fixture | **不在RUNNER_TEMP**：仓库 `.runtime/server-file-engineering-<GUID>`，其`SERVER-ENGINEERING-ONLY.txt`，[ServerFileTest第8–24行](../../scripts/windows_ci/ServerFileTest.ps1#L8) | 要求既有private runtime；目录New-Item后保护，marker WriteAllText后保护；均SetOwner/受保护DACL | 专项一次性fixture目录/marker，分别列首次创建窗口与失败处置；不是生产FILES启用授权。脚本没有finally删除fixture，不能预先承诺现有自动清理。 |
| FILES | `.runtime/files`在native ACL检查对象集中 | 生产Windows file功能默认关闭 | 本轮排除；将来确需实测另行确认，不递归修ACL。 |

## Owner/DACL/control保持与失败策略

当前native helper与setter都明确暂停，[第77–80行](../../src/parkweave/synthetic_session_file.py#L77)、[第116–121行](../../src/parkweave/synthetic_session_file.py#L116)，无环境恢复开关。不得换setter、在CREATE_NEW descriptor预设owner绕过原事务、启用privilege或接受较弱DACL比较。

原合同在同一新对象句柄上读取前后OWNER|DACL，验证owner SID相等，再要求**raw DACL bytes全等及descriptor control除OWNER_DEFAULTED位外全等**，之后才FD_TRANSFER/写正文，[第127–142行](../../src/parkweave/synthetic_session_file.py#L127)。SACL内容未查询，不声明完整SACL保持。ENG071 owner_same=true而acl_equal=false、control_equal=false，owner_defaulted_changed=false，失败在PERMISSIONS_COMPARE；仅证明owner成功不足以继续。

`owner_descriptor_observation`只读候选仅分解raw ACL、ordered ACE、slack和control固定bit名；semantic_permission_change始终UNKNOWN，[第22–36行](../../scripts/windows/owner_descriptor_observation.py#L22)。有序ACE相等/slack变化不能替代原合同，未知control差异必须拒绝。可观察对象、允许输出的固定枚举与持权精确句柄先由security owner确认；不公开SID、ACE正文、mask或私有descriptor。

失败不向新文件写正文，描述符和handle按原finally关闭；若历史失败已留下新空文件，保留为既有受保护对象，不重试owner、不重写ACL、不自动unlink。当前暂停在创建前拒绝，不产生该新文件。验证与清理需分别记录：验证失败保持拒绝；清理仅本次明确归属对象，保留失败证据，不能把清理成功覆盖主失败。SERVICE_LOG/新目录/fixture的失败处置必须逐对象确认，不能套用helper自动删除或扩大到已有用户文件。

## 最小动作分组、RACI及顺序

R=实施责任，A=决定/签收责任，C=必须咨询，I=知会。这里的角色是统筹分工，不是已取得执行授权。

| 顺序/动作包 | R | A | C / I | 当前可推进程度与完成门槛 |
|---|---|---|---|---|
| 1 工程冻结与保真 | 工程维护者 | root统筹 | 独立review / security owner知会 | ENG097 manifest与提交来源已完成。现权限可维护准确证据、collection/fixture与固定枚举诊断的非安全工程修复；保留完整集合、raw-byte guard、预算和失败gold。每次源码变更重新冻结实际HEAD。 |
| 2 精确对象确认包 | 工程维护者列清单 | security owner | runtime/CI维护者 / root | 先确认上表每组固定路径/新对象/句柄、既有对象拒绝、失败保留与可用只读观测目标。可现在完成静态方案/fixture审查；owner/ACL动作实施需明确范围，不能用一次笼统确认覆盖所有组。 |
| 3 SESSION/CONFIG权限保持 | 获授权的Windows安全实施者 | security owner | 独立安全review / root | 首先解释实际raw DACL和control差异、证明原合同可保持；先验证读观测设计，再决定是否及如何恢复原新对象事务。范围确认与保持证明分别满足后才实施，不改guard取得PASS。 |
| 4 补充新私有对象保护 | 工程实现者与安全实施者 | security owner | runtime维护者、独立review / root | SERVICE_LOG首建、STATE首建/替换、ROOT、TraceRoot、PGRoot、ServerFile fixture分别形成最小补丁和失败/清理契约。属于新安全实现，当前不做；不修既有对象。可并行准备方案，依赖包2且不能借包3绕过其各自合同。 |
| 5 原生诊断闭合 | 定点Windows验证执行者 | root确认运行范围；security owner确认安全边界 | CI/数据库维护者、独立review | Job exact handle/membership/accounting/signal、DB三gold实际异常子型及完整S4终态逐项取有效证据；不用isolated success/模拟替代。保留同一截止、进程身份、unrelated gold，不宽杀、不加预算、不接受任意OTHER或10013 busy。实际取证路线需获允许；不重试被拒日志。 |
| 6 恢复全量链与验收 | CI维护者 | root统筹/授权执行者 | security owner、独立review /相关验收方 | 包2–5必要前置关闭、源码实际HEAD冻结后再审查Prepare→Lifecycle→Validation→四片→Publish→Stop调用与失败清理，取得独立全量运行授权后执行。当前默认workflow保持；验收要求每片终态及coverage，不以三片累加或Job绿灯替代。 |

现权限下的安全工程修复限于不会改变安全决策或动作范围的collection/manifest/源字节核验、fixture准确断言、文档和既有固定枚举证据整理。DB ConnectionTimeout映射虽是候选工程项，实际原生子型尚未知且诊断安全代码本轮不改；恢复owner、扩owner对象、修改ACL策略/比较、fixture保护和workflow均不纳入此“可现在实施”分组。

顺序不是要求先全量试跑来找安全问题：先对象范围与保持合同，再最小实现/定点验证，最后全量。失败后只汇报对应门槛和已完成清理；保持当前default workflow、原native截止/预算、真实模型0及既有拒绝。本文仅新增文档，未运行Windows、网络、CI或任何owner/ACL操作。
