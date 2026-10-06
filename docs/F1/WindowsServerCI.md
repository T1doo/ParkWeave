# Windows Server CI

<a id="current-status"></a>
## 当前权威状态（ENG031已同步，Server FAIL，发布器PASS）

ENG030代码已普通快进同步，精确远端e9e962d4a5e2b42ea3750c83ee8d7145cc3f24f1；ENG030当轮冻结129份源码验证681PASS/0FAIL/1WindowsSKIP/2WARN（178.67s）。标准Server [run37420887816](https://github.com/T1doo/ParkWeave/actions/runs/37420887816)已completed/failure：PreparePASS，native_suite677.625秒exit1/外层timeoutFalse，独立安全发布器PASS，受绑定PG StopPASS。获准check title/summary/text仍为空，19条注释未给具体cases/counts，真实子项/报告阶段/根因仍UNKNOWN。发布器exit0结合已验证源码仅证明本次绑定报告SUMMARY_AVAILABLE且stdout/StepSummary写入成功，不能推定report_state=COMPLETED或回归通过。下一最小输入是此run“Windows Server safe engineering diagnostics”安全JSON的report_state/active_phase和FAIL/NOT_RUN行及已有有界计数；不需旧截图或私有日志。ENG031未作无证据CI修复或盲重跑；F2-T04后续ENG032内部分派切片仅本地完成，见[记录](../F2/ENG032-InternalDispatch.md)，其源码未同步到本次CI，F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。 见[ENG031记录](../F2/ENG031-SyncCI.md)。

## 历史ENG030本地诊断快照

ENG030的本地修复及681PASS验证见[记录](../F2/ENG030-SummaryPublication.md)；其中未push/新CI描述仅代表当轮安全保存点，现已被顶部实际同步结果取代。

## 历史ENG029同步与失败事实

ENG028代码已普通快进同步，精确远端ff00b6d8ad0880b24afaca49e33b9f8b982ceb87。标准Server [run37417713362](https://github.com/T1doo/ParkWeave/actions/runs/37417713362)已completed/failure：PreparePASS、native_suite623.032秒exit1/外层timeoutFalse、受绑定PG StopPASS。获准check summary/text为空，19条注释未给具体case/counts；仍UNKNOWN，不把时长推断成内部超时或根因。下一定位仅需此新run页面安全JSON，旧截图请求已过时。见[ENG029真实同步记录](../F2/ENG029-SyncCI.md)。下方ENG028“本地未push/待核对”等均为当时快照，现已被本节取代；F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。


## 历史ENG028本地待同步快照

ENG028增加仅固定test ID、阶段、异常类别和有界统计的诊断；明确UTF-8读取规格、页面、SQL及结果文本。本轮为本地工程修改，尚未push或触发CI，实际Windows码页及原生失败根因仍UNKNOWN。最新已同步代码1baa2cf、docs头aae63a5；标准Server run37414981257仍FAIL，Prepare/受绑定PG停止通过，native_suite79.235秒exit1/no timeout，具体case/counts未知。新样例仅模拟格式，不是该run结果。见[ENG028本地记录](../F2/ENG028-SafeDiagnostics.md)。F1未签收/F2正式准入NOT_PASSED，R4关闭、Win11/36AT6EX NOT_RUN，真实模型/预算0。

## 历史ENG019状态快照（2026-10-05）

以下是ENG019时的历史快照；其中“当前”等仅描述其记录时点，不覆盖顶部当前权威状态。

最近代码提交 `9a8cbc527503ab55978a4b50612207d3bf72de26`，已普通 push 到 `dev/f1-foundation`。最新 [run 37324704568](https://github.com/T1doo/ParkWeave/actions/runs/37324704568) 已 completed/failure，job 111812341430 用时约 1m56s：

- Checkout、显式 Python 3.12 x64 选择、Prepare：**通过**。原生 python_guard exit0/no timeout；postgres_version exit0；initdb exit0/2.172s；pg_start exit0/0.172s。
- Test：**失败**。native_suite exit1，78.094s，timeout=False。尚无具体 FAIL/NOT_RUN 子项及原生回归计数，不能推断生命周期、浏览器或 Server 文件 oracle 哪项通过/失败。
- Stop：**通过**。pg_status exit0/0.015s、pg_stop exit0/0.125s，无超时。这确认本次受绑定的 PG 停止步骤成功，不追认旧 run 清理成功，也不补造本次 API/worker 子项结果。
- **Server 整体未通过；F1 IN_PROGRESS/未签收。Windows Server 不是 Win11 验收；Win11 NOT_RUN，原 Win11 guard 未改，production R4 DISABLED；真实模型请求/预算0。** 完整36AT/6EX仍NOT_RUN；F2仅并行合成工程，正式准入NOT_PASSED；无资格自动判定或外部履约主张。

旧 [run 37318040507](https://github.com/T1doo/ParkWeave/actions/runs/37318040507) 的25分钟超时由允许注释确认，Prepare cancelled/Test skipped/Stop failure；**具体挂起命令及旧 Stop 失败根因仍UNKNOWN**。输出句柄继承只是待验证假设，不能因新 Prepare/Stop 通过就反推为旧根因。更早首轮 `37314450132` 的 Python 两路径拼接错误已由用户截图确认并修复；其截图不再是待输入项。

允许的 run/job/check 元数据与安全注释可读；此前标准日志下载跟随的签名存储地址返回Forbidden，数值HTTP状态/拒绝层未知，已停止该读取，没有重试或替代身份/镜像/日志路径。本次 check 输出的 title/summary/text 均null，注释数19；已取得信息为阶段/通用退出信息与Node版本告警，无法定位具体测试子项。native_suite 已设计写出页面上的 `Windows Server engineering (not Win11 acceptance)` JSON汇总，**现在只等待该汇总中的失败子项，不把旧超时日志作为必需输入**。

最小待输入字段：最新run页面 JSON 的 `cases` 中 `status=FAIL` 或 `NOT_RUN` 的记录（`case/status`，及已有 `exit_code/category/reason`），加 `full_engineering_regression.counts`（如有）。缺失字段保留缺失，不猜值；无需完整私有日志/会话/DSN/签名链接。收到后只针对命中子项定位修复；等待期间不取被拒日志、不执行原失败动作、不原样重跑CI。

已有安全产物能确认 Prepare/PG启停成功、native_suite非超时退出1及旧超时；不能再细分失败子项。静态源码能列出执行阶段/边界，不能把任一候选原因当真实诊断。当前文档收敛只改docs，普通push不命中此workflow的代码/测试路径过滤，不产生新CI或新测试成绩。

## 各轮可追溯结果

| 代码/run | 已观察的真实结果 | 后续处理/边界 |
| --- | --- | --- |
| 恢复51734906 / 37314450132 | Prepare失败、Test跳过、Stop成功 | 截图确认多个Python候选Source被拼成一个程序名；3.12.10实际存在。setup-python配置缺口与本次根因分开记录。 |
| 82ddaab、5a0987f / 37318040507 | 约25m10s超时取消；Prepare取消、Test跳过、Stop失败 | 多路径共享resolver和显式3.12/x64选择已发布；旧挂起命令UNKNOWN。 |
| 9a8cbc5 / 37324704568 | Prepare/PG启停通过；native_suite退出1；总结果failure | 有界等待/私有输出文件/阶段注释已发布；等待cases失败子项。 |

本地历史成绩均为Linux合成工程，不能替代Server/Win11：恢复后最终387 PASS/2 SKIP/2 WARN（便携PowerShell当时缺失）；Python解析修复定向42 PASS、全量394 PASS/1 Windows SKIP/2 WARN；有界诊断定向48 PASS、最终冻结源全量400 PASS/0 FAIL/1 Windows SKIP/2 WARN，AST13脚本零错误/4个CI Linux拒绝守卫。Python解析新增夹具首轮5 FAIL/37 PASS，修正夹具后通过，失败记录保留。原ENG012/ENG013/ENG014旧成绩与原始证据不改；所有本地计数不补作本次原生回归计数。

## 历史工程说明（按当时状态保留）

以下保留各轮真实计划、失败与实现说明；包括待审查、未发布、等待截图等当轮描述，均不作为当前待办。当前状态只以顶部为准。

### 历史：Server超时后的有界诊断（首次挂起命令仍UNKNOWN）

run37318040507/source5a0987f于约25m10s completed/cancelled；watch允许的注释明确maximum execution25m0s，Prepare cancelled/Test skipped/Stop failure。该证据确认任务超时与清理失败，不能确认是哪一条原生命令挂起。旧日志下载拒绝路线未重试、未换身份或接口读取同一日志。

静态可证：原Invoke-Checked对Python/initdb/psql/pip没有宿主侧时限，原pg_ctl通过PowerShell管道Out-Null消费输出；pg_ctl -t30不能证明宿主管道不会等待继承输出句柄的后台进程EOF。继承句柄只是待核实假设，不称本次真实根因。

诊断改为一个薄stdlib子进程执行器：shell=False/独立参数/DEVNULL stdin，stdout与stderr只写新私有trace目录普通文件；父程序只等待直接Popen子进程，按闭集阶段设时限，超时仅kill该直接命令并等待5秒，返回124及清理状态，不递归杀PostgreSQL/其它进程。pg_ctl status15/start60/stop60秒；其原生-w/-t30及原cluster UUID/data/bin/reparse/state绑定完全保留，未知status仍拒绝Stop。initdb120、psql30、venv60、pip锁依赖240/项目120、版本/端口15–30秒，suite900秒。suite超时可能跳过finally，因此always Stop在存在原自有状态记录时先复用lifecycle.stop的PID/cwd/命令/时间核验；失败仍尝试独立PG Stop，保持失败结论。该app_stop子进程复用原OS环境白名单，不继承owner/test-owner/model/GitHub配置。

公开notice/error只含闭集阶段名、START/END、deadline、exit、elapsed、timeout和直接子进程清理状态，不含参数/DSN/原始stdout/stderr。原始输出与JSON记录留本轮新私有trace，无artifact/cache上传。真实命令替身验证stdin EOF、空格参数、非零退出、超时不影响其它进程、私有输出不泄露、父退出后后代持有文件句柄仍及时返回、PowerShell桥接、原17个ownedcluster故障oracle；定向48 PASS。这些是Linux合成工程，不宣称Windows运行通过；用于下一次有实质变化的诊断run，不重复原样CI。

### 历史：迁移后显式Python配置与多路径解析修复

用户已提供首轮Prepare截图：Engineering.ps1行16调用的程序名包含hostedtoolcache的Python3.12.10路径及WindowsApps别名路径，两者被拼成一个字符串，exit1。这是已观察根因；Python3.12.10已存在，不能把此前显式setup-python配置缺口称此次根因。最小修复将Get-Command的多候选枚举逐个处理，只返回一个实际存在、非WindowsApps执行别名、非零长度的文件路径，保留完整空格且用调用运算符传独立参数；Prepare原3.12/x64/win32验证保持。Common.ps1相同解析缺陷同步使用该共享resolver。无硬编码runner个人路径、无空格删除/数组拼接、无版本守卫放宽。

本地PowerShell实测覆盖两个实际ApplicationInfo候选、WindowsApps别名优先/仅别名、带空格的可执行路径与独立参数、数组Source拒绝、缺失/零字节候选和错误版本拒绝；相关CI回归42 PASS。首轮测试夹具把单元素JSON数组解包成字符串后索引首字符，以及错误展开数组Source替身，导致5 FAIL/37 PASS；只修这两处夹具，未放宽产品断言。官方PowerShell7.6.6归档hash匹配，AST12脚本零错误/4个CI Linux拒绝守卫及原六Windows守卫PASS。这仍是Linux工程验证，原生Server需新run结果；Win11仍NOT_RUN。命令枚举语义参考[Microsoft Get-Command](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/get-command?view=powershell-7.5)。

恢复并普通push的精确51734906已触发首次Server run 37314450132，Prepare失败/Test跳过/Stop成功；详细日志下载在正式审批后仍Forbidden，数值HTTP状态及拒绝层未知，停止该下载且不换路线。当时步骤metadata没有错误注释，根因按UNKNOWN记录；后续截图已确认上述多路径拼接问题。原发布提交和旧证据不修改。

独立静态核查发现workflow原来依赖runner默认PATH的python，而Prepare明确要求3.12 x64。按新授权仅补官方setup-python显式选择3.12/x64，在Prepare之前设置PATH；v5官方ref于本任务只读核对为a26af69be951a213d495a4c3e4e4022e16d87065，workflow使用不可变SHA。3.12版本范围与pyproject的>=3.12,<3.13约束及既定Windows候选依赖一致，不宣称固定Python补丁版本或已有原生通过。未配置cache、artifact、secrets或新权限；单windows-2025/contents:read/25分钟/always Stop保持。

82ddaab当时只解决版本选择配置缺口，不称已解决首次Prepare失败；当时本地保存、不push并等待截图。后续截图、共享resolver修复及已发布运行结果见顶部当前状态。Win11 guard/R4保持原字节及关闭状态，LIVE/预算0，F1未签收。

**ENG012当时状态：LOCAL_ONLY / ACTIONS_BLOCKED / SERVER_NOT_RUN / WIN11_NOT_RUN（历史，非当前状态）。** 本轮没有访问Actions、推送workflow、启动runner或更改账号权限。Sim2Act的Windows CI结果不证明本项目执行环境有相同GitHub访问权限。完整AT/EX仍NOT_RUN，R4生产文件入口未启用。

### 历史：待审查配置和调用

`.github/workflows/windows-server-engineering.yml`只有dev/f1-foundation的窄push/代码及测试路径触发，单个标准windows-2025 job、25分钟上限、contents:read、单分支concurrency、checkout不持久化凭据；无larger runner、cache action、artifact上传、部署、repository secrets引用、workflow_dispatch-only对main的依赖。checkout使用v4版本tag，发布前仍应复核并锁定官方不可变SHA；本轮没有为此访问Park权限拒绝的API或切换路线。

在**新的标准Server runner**、fresh checkout及准备好的Python3.12 x64/PGBIN环境中：

```powershell
./scripts/windows_ci/Engineering.ps1 -Action Prepare
./scripts/windows_ci/Engineering.ps1 -Action Test
./scripts/windows_ci/Engineering.ps1 -Action Stop
```

Prepare只读CIM OS/product、Python位宽/版本、PG binary version、admin及EnableLUA；实际值写安全metadata，不更改UAC/权限策略。预期Server2025/admin/UACoff尚未实测，不伪填。官方[runner镜像清单](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md)曾核对包含Python3.12.10、PG17/PGBIN及Chrome/ChromeDriver；镜像会更新，版本以未来实际metadata为准，不能视清单为本项目实测。

在RUNNER_TEMP下新UUID目录设置**仅该新目录**的私有ACL，使用PGBIN initdb/pg_ctl建立UTF8新集群，trust仅用于无秘密的临时合成loopback测试，listen 127.0.0.1、空闲端口。不用runner预装PGDATA/service/password、不读取PGPASSWORD、不启动服务、WSL/pgserver/容器；专用park_ci_owner与低权限parkweave_app。只将本轮构造的临时无密码DSN/owned root发布到GITHUB_ENV，不发现/读模型key或repository secrets。环境/集群状态保留在新目录，无持续凭据。

准备独立.venv-windows并安装既有Windows候选pins（pip --no-cache-dir）。已有managed目录拒绝覆盖。Test调native_suite：六原有PowerShell候选生命周期；Setup重复拒绝且config/session hash不变；真实本地API/独立worker本地Case仍NEEDS_INPUT/NOT_SUBMITTED/NO_EVIDENCE；Stop/再启读回同Case；本地Chrome/预装ChromeDriver使用loopback W3C协议、新合成profile、headless且不关sandbox/web security，检查正常表单、三字段必要问题、补充仍UNKNOWN和取消。完整pytest使用fresh native PG的显式PARKWEAVE_TEST_OWNER_DSN及既有低权限role，全部模型mock，未知不默认通过。

生命周期失败会记FAIL/后续依赖NOT_RUN，独立回归/Win11 guard/Server候选检查仍执行。服务仅由原有可信PID/命令/时间/cwd识别的Stop关闭；PG Stop只接受本轮UUID root/状态数据/PGBIN binding，pg_ctl仅该data目录，失败保留不误停其它服务/进程，不宽泛删除路径。未来实际超时、权限、admin默认owner、NTFS/共享行为仍需Server运行证据；Linux不能确认这些语义。

### 历史：独立Server文件工程边界

ServerFileTest.ps1只新建server-file-engineering-UUID合成根/marker及自身ACL，server_candidate_probe.py以实际sys.getwindowsversion.product_type/build、Python3.12x64守卫，不spoof。复用仓库已发布的file_candidate_probe.run_probe**测试oracle helpers**，从不调用/修改其Win11 main；原文件release11 guard字节保持。先positive同handle读取成功才做坏ACL/ADS/硬链接/junction/共享拒绝等，失败/权限不足明确FAIL/NOT_RUN，不把全拒绝当PASS。独立Server summary明确NOT_WIN11、production R4 DISABLED；原API/files.py不调用candidate。未来即使Server全部PASS，Win11产品安装/ACL/reparse/竞态与完整AT仍未签收。

没有artifact上传，未来runner只输出安全步骤/计数/版本摘要与GITHUB_STEP_SUMMARY；private pytest/PG日志、合成session/token/profile不公开，临时cluster最后stop。ENG012记录时无runner，所有native步骤NOT_RUN；当前已有实际Server运行，见顶部。

### 历史：本地验证及准确阻塞

已有错误原文、目标API和CLI退出码保存在[evidence/eng012-actions-blocker.json](evidence/eng012-actions-blocker.json)，来源是上一轮已捕获输出，本轮未重新访问。CLI显示Forbidden；**数值HTTP状态、响应header/body/request ID和拒绝由GitHub还是执行访问层产生均缺失**，不凭文字声称HTTP403。workflow写入权限从未测试。当前需要原执行通道恢复/复核Actions状态与日志读取能力；本轮不尝试身份/令牌/路由更换或权限调整。

已安装系统PyYAML及缓存PowerShell作Linux YAML/policy/AST/拒Linux守卫；测试wire及故障编排只用明确mock。证据eng012-static-ci.json/eng012-acceptance-summary.json仅LOCAL_ENGINEERING，不称Server或Win11 PASS。初次PowerShell启动默认cache写/home只读导致exit134；仅对该子进程使用工作区XDG目录后恢复，无HOME/用户profile/全局配置修改。

权限恢复前仍可独立推进的最高优先项：对这一CI harness补充PG init/start失败、owned cluster状态篡改、浏览器超时/清理失败的独立故障oracle，确认保留失败/只清理自己对象/其它独立阶段仍运行。这是现有F1测试基础的审查，不新增R5/F2产品功能；随后再按授权恢复Actions并实测Server。R4仍等原生条件，真实API/预算始终0。

### 历史：ENG013本地有限加固（未发布）

CI辅助进程按阶段构建环境：Setup只接owner+app，Doctor/Start/Status只接校验为loopback/parkweave/parkweave_app的app DSN，回归协调器只接显式test-owner；Stop/文件probe/Win11守卫/浏览器只有OS白名单。service/options/owner角色/其它数据库或远端app绑定拒绝。原API/worker共用循环中的app_environment已过滤owner/test-owner/PGPASSWORD/token；本轮静态与合成Popen捕获及真实Linux子进程环境oracle确认此边界，没有读取真实凭据，也不将另项目风险直接归因本项目。

ClusterControl纯PS helper先验证UUID直接子目录、精确state字段/范围/路径/无reparse，再执行自身data的pg_ctl。start失败重新验证+status：未运行不stop、已运行只stop自己、未知状态拒绝，保留原start退出码；清理失败明确REFUSED_OR_FAILED，不猜成功。浏览器会话/自有driver退出先于profile清理；主超时不会被清理异常覆盖，清理错误保留分类注释。全部故障由明确SYNTHETIC命令替身/配置/临时目录验证，原生PG/Chrome/Server仍NOT_RUN。

访问恢复后的唯一最小验证计划：在原身份/原通道获准恢复后，先做一次只读Actions状态/日志访问验证；确认可读及workflow发布授权、复核checkout不可变SHA后，才推当前独立分支并运行一次标准windows-2025 mock任务，核对安全版本/低权限app身份、生命周期和故障检查/最终Stop摘要。失败按原输出记录，不自动换身份、改权限或反复启动job。Windows11门仍独立BLOCKED；现在不执行该计划。


## ENG040 最新标准Server实际结果

普通快进同步8ddf139后，唯一标准[run37439323047](https://github.com/T1doo/ParkWeave/actions/runs/37439323047)/attempt1 completed/failure。新安全annotations经正常API真实读取：Doctor_native FAIL exit1；Start_native FAIL exit1；API_browser_restart NOT_RUN START_FAILED；full_engineering_regression在regression_run TimeoutExpired，counts MISSING/无pytest ID。harness合计5PASS3FAIL1NOT_RUN，非pytest全量成绩。发布器成功、owned PG status/stop exit0无超时；Doctor/Start底层原因及单测试信息未知。细节见[ENG040](../F2/ENG040-SyncCI.md)。旧37420887816根因未知保持历史范围，不做同因推断；Server不是Win11，F1/F2未签收，R4关闭/36AT6EX NOT_RUN。结果docs-only同步不会另触发源码workflow。
