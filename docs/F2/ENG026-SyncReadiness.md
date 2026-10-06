# ENG026 本地积累提交的同步前收敛

审查基线2fddccae02a27818e3632cfca7676104e6eb3569；本轮只收敛文档及修正代码可证的Windows验收弱点，不新增产品功能。当前授权明确不push/新CI/备份/导出/上传/LIVE，模型/真实预算0。

## 提交链与可见性

起始工作树干净。git fsck --full通过；原恢复51734906aaa3469a5e3cfeb9f97696db5f29cb06、旧远端5185cf4b0a3973f1b7b486bc6adf43f478742db2、旧CI9a8cbc527503ab55978a4b50612207d3bf72de26及本地缓存origin/dev/f1-foundation6ff160abe979f9d1c28d0e7804fda668daf72cf5均为ENG025的祖先。相对缓存有以下10个连续单父提交，无reset/丢码。它们按任务记录均未推送；不称当前GitHub可见，不把缓存当实时远端。

| 本地提交完整SHA | 内容 |
|---|---|
| c285da844fcf86f397e052826743e4fe7360a9e8 | fix(f2): bind preparation requests and drafts to selected case |
| 3aa99e45e82517a80a5197d140a92ebce8c92ff2 | feat(f2): show scoped personal material preparation tasks |
| 5849c02244680ae84e924380053669720e213ba1 | docs(f2): record independent review and remaining validation gates |
| da69ea6d74f0279051e6d0cbe4b70dfb9695db95 | feat(f2): add synthetic resource preview holds and expiry |
| 50f7c4bd7fe6704e61bd2dc3c9a96d26f3e31f90 | feat(f2): confirm single synthetic resource holds locally |
| 3e146a56e596d9c07e36c6ca49138be468fb5cad | feat(ui): polish service and resource views with current-state feedback |
| c2f3465f478175ec62b477d77a06c2a13a70acf5 | feat(f2): confirm and cancel two synthetic resources atomically |
| 8e2195ad63dd19d0b7c8e3ef94f47e0c04044a6a | Add assigned executor synthetic receipt workflow |
| 18f9f5670960a3affdf6d11455a89fc4aaaebb16 | Verify bounded cross-module flow and guard generic UI sessions |
| 2fddccae02a27818e3632cfca7676104e6eb3569 | Bind confirmed synthetic resources to preparation Cases with history |

本轮本地收敛提交还会增加1个。后续同步需新的明确授权及实时远端只读比较；若远端变更/冲突未知，先报告，不force、不回退覆盖。当前不请求或执行发布。

## Windows证据与确定修复

唯一已知旧CI37324704568事实：旧源码9a8cbc Prepare通过，native_suite78.094秒exit1；具体失败case未取得。当前源码的原生Server结果NOT_RUN，原生Win11/全36AT6EX NOT_RUN，旧CI根因UNKNOWN。未重试被拒的日志下载、改身份/代理/访问路线，也没有推测哪一个case失败。

独立同工作区windows_native_review（用户指定6.1sol medium）只读源码，未执行测试/API/DB/browser、读私有runtime或访问外网。审查发现三处可以代码证明的验收弱点：

- Status脚本读到身份不匹配仍exit0，suite仅据退出码记PASS。仅修suite判定：解析安全Status JSON，要求ParkWeave/模型关闭/8765及两个不同正整数PID的identity_matches明确true；不成立记FAIL，保留其他独立phase，不改变生命周期终止授权。
- 浏览器清理失败只有异常notes，suite只记类型而丢类别。owned_browser主失败或仅清理失败均附结构化类别，suite只保留限长类别名，不复制原异常message/notes、凭据或路径。
- 注入oracle直接写DOM textContent后验无script，不能证明应用渲染。改为SYNTHETIC诉求包含script文本，经实际建单/worker/API结果渲染后检验原Case.goal/页面文本及无script节点/执行；取消旧直接写结果节点的伪证据。

这些是确定的验收/诊断修复，不是已定位旧Windows失败或已修复原生平台故障。独立最终静态复审未发现剩余实质问题或新增应用跨平台同步阻塞；它未独立复跑主代理测试。相对旧9a8cbc，应用Windows文件候选/句柄/生产dispatch、生命周期脚本、OS环境白名单、workflow/ClusterControl/ACL与Win11/Server守卫保持原字节，只改browser_smoke/native_suite及相关测试。

## 可复现实测入口

在仓库根目录，使用已准备的Python3.12本地工程环境及测试依赖。命令内输出路径用新的唯一标识，避免覆盖历史证据；不要把Linux结果算Windows通过。

```text
.venv/bin/python scripts/run_acceptance.py --report .runtime/<唯一标识>-acceptance.json
.venv/bin/python -m pytest tests/test_windows_ci_preparation.py tests/test_ci_cleanup.py tests/test_native_command.py tests/test_lifecycle.py tests/test_python_command.py tests/test_windows_file_candidate.py -q
.venv/bin/python -m pytest tests/test_case_resources.py -q
```

已准备Linux pgserver/Chromium及缓存agent-browser0.38.2时，实际产品UI由以下显式合成fixture入口提供；它仅127.0.0.1:8765启动自有API/独立worker，按[FirstUse](FirstUse.md)的三角色步骤操作，正常停止该harness由其停止自己的children。原会话/撤权/历史保留，不找凭据或改身份。

```text
.venv/bin/python scripts/linux_fixture_server.py --preparation-fixtures --resource-fixtures --combination-fixtures --receipt-fixtures
.venv/bin/python scripts/candidate_browser_smoke.py --report .runtime/<唯一标识>-candidate.json
.venv/bin/python scripts/case_resources_browser_smoke.py --report .runtime/<唯一标识>-case-resources.json --screenshots .runtime/<唯一新目录>
```

完整Case/回执自动browser要求调用者明确授权并提供同一本机SYNTHETIC cluster的PARKWEAVE_RECEIPT_FIXTURE_OWNER_DSN，用于只给本次新Run准备合法assignment；它不是应用自动分派能力。不能把私有.runtime临时runner、已有旧assignment或旧路径当干净环境的一条自动复现命令。CLI脚本、前置fixture和真实步骤才是仓库入口；环境/依赖未准备则NOT_RUN，不自动联网安装。

五个页面时序oracle是scripts/generic_session_race_browser.py、preparation_race_browser.py、resource_race_browser.py、executor_receipt_race_browser.py、case_resource_race_browser.py，均需--report独立路径，使用真实页面及合成fetch，不访问业务API或验证后端授权；应逐个执行以避免共用浏览器session竞争。PG授权/事务由对应真实测试提供。

Windows静态检查入口是scripts/check_windows_ci.py --pwsh <已有PowerShell路径> --report <独立路径>，需要已有PyYAML解释器。本机.venv缺PyYAML，改用系统已有解释器运行，不安装依赖；脚本使用工作区XDG隔离。一次直接版本探针未指定隔离缓存而被只读默认目录拒绝，不能算PowerShell/应用失败。AST与Linux拒绝守卫仍不算原生Windows执行。

原生Windows工程入口仍是scripts/windows_ci/Engineering.ps1 Prepare/Test/Stop，但需要原生Server2025/Python3.12x64/显式runner PG17与全新自有cluster/配置。当前未执行，未改安全门/策略，不把这些列为已通过，也不建议在已有私有环境直接覆盖运行。

## 同步前验收判断

最终本轮实测结果在下方及evidence/eng026-sync-readiness.json。判断分开：

- 本地源码同步的代码条件：积累提交链完整、对象检查与当前测试通过，独立审查无已知剩余应用跨平台阻塞。发现的三处验收弱点已修；不存在通过猜根因掩盖旧CI失败的结论。
- 当前实际同步阻止项：用户明确暂停push/新CI；没有当前远端状态，不能承诺快进或GitHub已可见。后续同步也不是合并main/部署/生产发布许可。
- 原生验证缺口：旧Server CI具体失败case待日志，当前Server和Win11未实测；阻止声称F1原生通过、CI已修复或原生发布就绪，不能据此虚构应用缺陷。
- F2业务签收缺口：注册服务DAG/目标覆盖、通用ServicePlan/Approval/CaseStep/分派接单/通知及全业务Outbox、审核模板/冷会话、真实身份/资料规则/证明核验与履约、完整原V1端到端仍未完成。它们阻止F2/PR0-alpha签收与真实业务使用，不应误称已实现，也不等同于开发分支不能保存合成工程源码。

到本轮本地提交与独立说明完成即停止，不继续扩功能。R4保持关闭，F1/F2未签收。

## 本轮最终实际结果

594PASS/0FAIL/1WindowsSKIP/2既有WARN，JUnit174.96秒（pytest显示174.97秒）；121个包含JS的冻结源码hash一致。Windows相关本地136PASS/0FAIL/1既有WARN9.19秒，包括新Status伪成功判定、主体/仅清理失败摘要、渲染oracle及既有真实受限子进程/PowerShell桥/平台拒绝检查；均不是原生Windows。13份PowerShell AST、4个Linux拒绝守卫与YAML策略PASS；已有系统PyYAML解释器完成检查，无下载/安装或策略改动。

冻结后本机Linux Chromium/低权限API/独立worker/PG实际新诉求渲染PASS：精确script文本保留在Case.goal与页面JSON，无脚本节点/执行；Case仍NEEDS_INPUT、外部NOT_SUBMITTED/线下NO_EVIDENCE。这只证明当前共享应用渲染oracle，不代替原生ChromeDriver/Windows结果。

独立只读6.1sol medium最终确认三处验收弱点及仅清理失败跟进缺口修正完整，未发现新增应用跨平台同步阻塞；未由它执行测试。产品src/角色/原计划不变，31个历史保护文件字节保留，另外2个保护文件仅native_suite/browser_smoke验收修正；旧CI的失败case/根因仍UNKNOWN，不能宣称已修复该CI。

完整链、判断、实测元数据和源码hash见[evidence/eng026-sync-readiness.json](evidence/eng026-sync-readiness.json)。历史ENG025584/95页面/三角色链与55匹配图仍保留，不用当前结果替换旧报告，也不重做或覆盖截图；本轮未产生新截图。仅本地commit后停止，无push/newCI/备份/导出/上传/LIVE；F1/F2未签收R4关闭。
