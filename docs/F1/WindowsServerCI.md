# Windows Server CI本地候选（ENG012）

## 迁移后显式Python配置与多路径解析修复

用户已提供首轮Prepare截图：Engineering.ps1行16调用的程序名包含hostedtoolcache的Python3.12.10路径及WindowsApps别名路径，两者被拼成一个字符串，exit1。这是已观察根因；Python3.12.10已存在，不能把此前显式setup-python配置缺口称此次根因。最小修复将Get-Command的多候选枚举逐个处理，只返回一个实际存在、非WindowsApps执行别名、非零长度的文件路径，保留完整空格且用调用运算符传独立参数；Prepare原3.12/x64/win32验证保持。Common.ps1相同解析缺陷同步使用该共享resolver。无硬编码runner个人路径、无空格删除/数组拼接、无版本守卫放宽。

本地PowerShell实测覆盖两个实际ApplicationInfo候选、WindowsApps别名优先/仅别名、带空格的可执行路径与独立参数、数组Source拒绝、缺失/零字节候选和错误版本拒绝；相关CI回归42 PASS。首轮测试夹具把单元素JSON数组解包成字符串后索引首字符，以及错误展开数组Source替身，导致5 FAIL/37 PASS；只修这两处夹具，未放宽产品断言。官方PowerShell7.6.6归档hash匹配，AST12脚本零错误/4个CI Linux拒绝守卫及原六Windows守卫PASS。这仍是Linux工程验证，原生Server需新run结果；Win11仍NOT_RUN。命令枚举语义参考[Microsoft Get-Command](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/get-command?view=powershell-7.5)。

恢复并普通push的精确51734906已触发首次Server run 37314450132，Prepare失败/Test跳过/Stop成功；详细日志下载在正式审批后仍Forbidden，数值HTTP状态及拒绝层未知，停止该下载且不换路线。已有步骤metadata没有错误注释，具体根因仍UNKNOWN。原发布提交和旧证据不修改。

独立静态核查发现workflow原来依赖runner默认PATH的python，而Prepare明确要求3.12 x64。按新授权仅补官方setup-python显式选择3.12/x64，在Prepare之前设置PATH；v5官方ref于本任务只读核对为a26af69be951a213d495a4c3e4e4022e16d87065，workflow使用不可变SHA。3.12版本范围与pyproject的>=3.12,<3.13约束及既定Windows候选依赖一致，不宣称固定Python补丁版本或已有原生通过。未配置cache、artifact、secrets或新权限；单windows-2025/contents:read/25分钟/always Stop保持。

该修复只解决明确的版本选择配置缺口，不等于已解决首次Prepare失败。同步现有静态policy/范围检查；本地保存，不push、不重跑CI，等待用户提供首次Prepare错误段后再联合核对。Win11 guard/R4保持原字节及关闭状态，LIVE/预算0，F1未签收。

**LOCAL_ONLY / ACTIONS_BLOCKED / SERVER_NOT_RUN / WIN11_NOT_RUN。** 本轮没有访问Actions、推送workflow、启动runner或更改账号权限。Sim2Act的Windows CI结果不证明本项目执行环境有相同GitHub访问权限。完整AT/EX仍NOT_RUN，R4生产文件入口未启用。

## 待审查配置和调用

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

## 独立Server文件工程边界

ServerFileTest.ps1只新建server-file-engineering-UUID合成根/marker及自身ACL，server_candidate_probe.py以实际sys.getwindowsversion.product_type/build、Python3.12x64守卫，不spoof。复用仓库已发布的file_candidate_probe.run_probe**测试oracle helpers**，从不调用/修改其Win11 main；原文件release11 guard字节保持。先positive同handle读取成功才做坏ACL/ADS/硬链接/junction/共享拒绝等，失败/权限不足明确FAIL/NOT_RUN，不把全拒绝当PASS。独立Server summary明确NOT_WIN11、production R4 DISABLED；原API/files.py不调用candidate。未来即使Server全部PASS，Win11产品安装/ACL/reparse/竞态与完整AT仍未签收。

没有artifact上传，未来runner只输出安全步骤/计数/版本摘要与GITHUB_STEP_SUMMARY；private pytest/PG日志、合成session/token/profile不公开，临时cluster最后stop。当前无runner，所有native步骤NOT_RUN。

## 本地验证及准确阻塞

已有错误原文、目标API和CLI退出码保存在[evidence/eng012-actions-blocker.json](evidence/eng012-actions-blocker.json)，来源是上一轮已捕获输出，本轮未重新访问。CLI显示Forbidden；**数值HTTP状态、响应header/body/request ID和拒绝由GitHub还是执行访问层产生均缺失**，不凭文字声称HTTP403。workflow写入权限从未测试。当前需要原执行通道恢复/复核Actions状态与日志读取能力；本轮不尝试身份/令牌/路由更换或权限调整。

已安装系统PyYAML及缓存PowerShell作Linux YAML/policy/AST/拒Linux守卫；测试wire及故障编排只用明确mock。证据eng012-static-ci.json/eng012-acceptance-summary.json仅LOCAL_ENGINEERING，不称Server或Win11 PASS。初次PowerShell启动默认cache写/home只读导致exit134；仅对该子进程使用工作区XDG目录后恢复，无HOME/用户profile/全局配置修改。

权限恢复前仍可独立推进的最高优先项：对这一CI harness补充PG init/start失败、owned cluster状态篡改、浏览器超时/清理失败的独立故障oracle，确认保留失败/只清理自己对象/其它独立阶段仍运行。这是现有F1测试基础的审查，不新增R5/F2产品功能；随后再按授权恢复Actions并实测Server。R4仍等原生条件，真实API/预算始终0。

## ENG013本地有限加固（未发布）

CI辅助进程按阶段构建环境：Setup只接owner+app，Doctor/Start/Status只接校验为loopback/parkweave/parkweave_app的app DSN，回归协调器只接显式test-owner；Stop/文件probe/Win11守卫/浏览器只有OS白名单。service/options/owner角色/其它数据库或远端app绑定拒绝。原API/worker共用循环中的app_environment已过滤owner/test-owner/PGPASSWORD/token；本轮静态与合成Popen捕获及真实Linux子进程环境oracle确认此边界，没有读取真实凭据，也不将另项目风险直接归因本项目。

ClusterControl纯PS helper先验证UUID直接子目录、精确state字段/范围/路径/无reparse，再执行自身data的pg_ctl。start失败重新验证+status：未运行不stop、已运行只stop自己、未知状态拒绝，保留原start退出码；清理失败明确REFUSED_OR_FAILED，不猜成功。浏览器会话/自有driver退出先于profile清理；主超时不会被清理异常覆盖，清理错误保留分类注释。全部故障由明确SYNTHETIC命令替身/配置/临时目录验证，原生PG/Chrome/Server仍NOT_RUN。

访问恢复后的唯一最小验证计划：在原身份/原通道获准恢复后，先做一次只读Actions状态/日志访问验证；确认可读及workflow发布授权、复核checkout不可变SHA后，才推当前独立分支并运行一次标准windows-2025 mock任务，核对安全版本/低权限app身份、生命周期和故障检查/最终Stop摘要。失败按原输出记录，不自动换身份、改权限或反复启动job。Windows11门仍独立BLOCKED；现在不执行该计划。
