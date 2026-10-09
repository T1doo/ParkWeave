# 资料交付异议开发分支集成

2026-10-09 后续明确授权将限定独审通过候选集成到 `dev/f1-foundation`。原候选为 `c3c9faaf3087432feb89bcdd0aa43182402e48f3`，原开发基线为 `88403af18b95b361114b303c3fae636f286d91b4`；正常 fast-forward，没有冲突或业务源码改动。集成证据提交仅追加本报告、候选阶段状态说明及证据。最终远端SHA由交付终态与私有远端核验记录给出。

重新核对[独立终态](evidence/material-objections/review-fix/independent-final-review.json)，结论仍为 **LIMITED_PASS_SYNTHETIC_SLICE**，原两项阻断均关闭。独立81项与额外5项日志hash吻合。候选业务源码与被审 `47d7406804daa08fdeaa8949aa33ae35b9817f01` 完全一致；其后唯一测试差异是 `tests/test_authorization_files.py:309` 的迁移预期25→26，独审已明确核对。最终301文件hash与实际文件全部相符。现有roles.sql和权限注册表相对原开发基线无变化。

先核验单一源码写入者（独审代理已结束且只读）、实际HEAD、干净工作树、无挂起Git操作、远端祖先关系；保留平台管理的index-refresh锁。origin原默认fetch只追踪main，首次带tracking切换被Git拒绝并留下base工作树中间态；核验该变化恰为命令自身造成的base tree、保全patch后恢复未变候选HEAD，再以明确基线SHA建立no-track本地dev并fast-forward。未改远端配置、凭据或安全网络配置；失败未改变任何远端。

集成后定向回归 **155 PASS / 0 FAIL / 0 ERROR / 0 SKIP，97.731秒，2 WARN**。包含9个授权/目录世代边界、41个API/真实PG异议、18个真实HTTP/Chromium异议、13个原资料包兼容、68个receipt边界与Linux TCP PG用例、5个Linux启动器和1个schema26迁移/撤权兼容用例。覆盖冷刷新及实际API进程重启、只读丢响应恢复、撤权/越权/跨企业、换版/目录ABA、CAS并发、迟到响应、重复写入、历史不可变和隐私负例。资料包仅运行既有兼容测试，旧产出证据不覆盖。上述回归并非全仓或Windows验收。

额外真实 **schema25 HTTP/PG/Chromium探针 1 PASS，3.278秒，2 WARN**：由原receipt路径创建实际25库，使用未修改的原roles.sql；原人工REVIEW和企业页面CONFIRM达到LOCAL_CONFIRMED；新异议GET/POST均409、没有新增事件；新Store缺少创建receipt时升级被拒绝，schema及CHECK保持25。没有借删除版本标记模拟旧库。探针前两次因脚本绕过原角色列表或未打开协同工作区而点击隐藏按钮超时，修正导航后通过，未修改业务实现；失败原件和修正说明均保全。成功探针源码归档为文本，复现时置于`.runtime/material-objections-integration/test_schema25_http.py`并使用同目录runner从仓库根目录执行。

schema26回归验证实际Linux创建receipt、无凭据重建的Store冷启动、旧receipt不自动授权26，以及新异议写入/恢复合同。原Windows/native路径仍止于25，本轮Linux TCP PG和模拟接缝不是原生Windows验证。两个WARN为既有Starlette/httpx弃用和XDG_RUNTIME_DIR回落，不调整依赖或安全环境。

全仓仍 **NOT_PASSED_NOT_COMPLETED**，未重跑无关全量；既有Windows Setup模拟失败不修改。Windows/native、42 AT/EX仍未签收，未形成F1/F2、R4/LIVE或现实履约验收。owner与协作锁仍为信任边界，`xmin`只是库内保守行世代。仅原合成合同与角色，真实模型调用、外部通知、权限扩展、政策审批、Case完成均无新增；不改main、不强推、不部署。

[集成机器记录](evidence/material-objections/integration/verification.json)、[155项日志](evidence/material-objections/integration/integration.log)、[JUnit](evidence/material-objections/integration/integration.xml)、[schema25探针日志](evidence/material-objections/integration/schema25-http.log)、[schema25结果](evidence/material-objections/integration/schema25-http.json)、[API冷重启](evidence/material-objections/integration/api-restart.json)、[页面截图索引](evidence/material-objections/integration/browser-output.json)、[探针源码](evidence/material-objections/integration/schema25-http-probe.py.txt)。`.runtime`保留原故障日志、失败探针、切换patch和私有核验，不发布合成会话值。
