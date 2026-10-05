# Windows Server CI本地候选（ENG012）

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
