# Win11 首次安装的最小剩余清单与预检修复

基线72f2312539936c56ea21451cea6d8ff060ccbd01。对应原F1-T01/AT01与AT34、原产品Win11原生交付要求。F1未签收/F2并行；本轮不继续扩合成政策演示，不安装用户设备或执行owner/ACL/security操作。

| 最小剩余项 | 需要的证据/动作 | 本轮能否自行推进 |
| --- | --- | --- |
| 用户Win11 x64首次运行 | 实际构建/架构、已批准Python/PG来源和精确版本、原生PG服务PID/数据路径、API/worker、停止后重启和数据保持、真实浏览器体验 | 需要用户设备与原安装授权、人工签收；Linux或Server隔离CI不代替。 |
| 新SESSION/CONFIG创建及附属对象权限合同 | 原创建暂停因实际DACL/control保持失败；log/PROCESS_RECORD原子新对象及真正受保护authority亦未闭合 | 授权/原生边界阻塞；本轮不恢复暂停、不换setter、不改ACL/身份/策略。 |
| 正常Job后代回收及完整Windows回归 | 历史normal exact descendant仍LIVE、S4未完整；当前CI只测controlled Job；全部分片/固定原生oracle仍须当前源码实测 | 不能据Linux/mock关闭；不恢复全量workflow或扩大时间预算。 |
| 真实模型链 | 安全注入、核实账户总额/速率、实际工具修订/usage证据 | 预算0、LIVE关闭；原模型许可与人工签收仍缺，不调用。 |
| 真实园区/政策业务来源 | 经许可且已审核发布的服务条件、材料要求、现实效果/独立回执 | 用户真实材料/审核门；合成规则不替代。 |
| 已知暂停下仍先执行Setup副作用 | 原Setup先venv/pip、DSN/migrate/roles，再在固定native CONFIG/SESSION创建暂停处失败 | **本轮离线代码修复**：提前只读预检拒绝，Doctor/指南明确真实阻塞。 |

当前manifest的文件/哈希/AST白名单已持续刷新，此处不再把ENG097历史69文件/1826collection过期状态当成当前阻塞。当前采集2478项/89文件，原2472稳定keys全部保留，四片612/607/632/627，预算/原生跳过合同不变。采集不是执行PASS。

## 本轮实际行为

Setup保留已有CONFIG拒绝覆盖，随后立即require_setup_readiness：固定BLOCKED/OWNER_MUTATION_PAUSED，早于check_python、环境建立/安装、任何DSN读取、数据库迁移/roles、目录保护、会话/配置创建。没有启用开关、宽松fallback或新的安装权。原synthetic_session_file/native setter与所有ACL/owner检查字节不改。先前未完成的环境/运行目录/配置和数据库保留，不以失败回滚名义删除用户文件。

Doctor仅增加new_setup说明，不把exit0当安装成功。其Python/既有私有目录和配置/数据库只读检查若先失败，仍按原错误退出，不保证输出该JSON字段；全新配置且前置检查通过时显示明确BLOCKED。已有安装仍按原Doctor/Start合同核对，不默认批准运行。首次体验指南改成一条只读Doctor命令，停止在明确阻塞处，不诱导提供维护DSN或盲目Setup。

## 证据与限制

新增6项Linux离线调用oracle，证明空目录、不完整环境、既有runtime/会话、CONFIG字节/目录保持，所有安装/DSN/目录保护路径均设陷阱；Doctor不安装/读DSN、不输出凭据；mock CLI非0及固定枚举穿过原诊断parser。它们不执行Windows安装或native owner/ACL操作。相关冻结回归、源字节/模式、同次collection/JUnit与加载来源、独审及初次错误见[机器证据](../integration/Win11SetupPreflightEvidence.json)。本切片不新跑完整Linux，全量2463仅属于此前0a185d8冻结源，不能覆盖本轮修改。

初次命令拼错了一个测试文件名，exit4无测试执行；修正后的首轮相关202PASS/1FAIL/2SKIP，失败是新增3个AST函数未刷新diagnostic白名单。原错误记录保留，不删白名单校验；刷新完整global/四片及AST记录后重新冻结验证。独审补充Doctor前置失败可能无new_setup字段的范围提示，文案已修正。

所有原AT/EX正式状态不改为PASS；Win11、完整Windows、受保护authority、现实履约未验收。R4关闭、模型0、原环境/备份保留。普通dev推送/首次精确Server隔离CI终态另记私有.runtime/win11-preflight-delivery.json。

最终冻结相关420PASS/4SKIP/0FAIL/2WARN（18.39秒），424同次节点一致、294源字节/模式0差异、38主进程模块加载来源/hash无偏离，精确pytest身份已退出。该次未捕获PG PID/数据根，不宣称专项数据库进程清理；本轮没有浏览器/PowerShell/Windows原生运行。
