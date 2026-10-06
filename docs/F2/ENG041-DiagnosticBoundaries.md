# ENG041 Doctor/Start及完整回归的最小阶段诊断

本轮沿用ENG040工程，用户要求先本地复现、回归及独立复核后报告，再决定单次CI。没有push、manual dispatch、rerun或日志下载，未回到旧恢复包迁移。

## 本次能证明什么

只读正常API再次确认[run37439323047](https://github.com/T1doo/ParkWeave/actions/runs/37439323047)：Doctor_native/Start_native FAIL exit1；API_browser_restart NOT_RUN START_FAILED；完整回归FAIL regression_run/TimeoutExpired/counts MISSING。已有annotations没有底层原因、pytest ID或计数，不能把本地合成故障认作Windows根因。

| 本地验证 | 可证明结论 | Windows实际原因 |
|---|---|---|
| 真正不存在的解释器；实际Linux解释器版本检查 | FileNotFoundError与PYTHON_VERSION_REFUSED可区分 | UNKNOWN |
| 缺配置、实际非法UTF-8配置 | CONFIG_MISSING与UnicodeDecodeError可区分 | UNKNOWN |
| 自有loopback连接拒绝及已占用端口 | database_connect/OperationalError与PORT_OCCUPIED可区分 | UNKNOWN |
| 新建自有loopback PG16临时集群、既有迁移和roles.sql | 专用app角色可连接并读schema18；owner角色被app检查拒绝；集群已停止 | 不能替代Server PG17证据 |
| 合成ACL、依赖freeze、输出编码、启动故障 | 只保留固定类别、阶段和原因码 | 不声称实际ACL/缺依赖/编码故障 |
| 合法非对象health、进程记录写失败与清理覆盖 | 保留主故障诊断及清理类别，原退出/清理行为不变 | UNKNOWN |
| 实际停滞pytest setup/call/teardown子进程 | 私有阶段记录分别正确，自有探针子进程已终止并回收 | 不是本次CI具体测试定位 |
| 实际直接父进程超时 | 后代仍可存活；独立监督器随后终止并回收本次自有实验后代 | 产品回收风险仍未修复 |
| 缩短参数的真实HTTP停滞探针 | 三次0.08s请求均ReadTimeout，累计0.310s；listener/connections/thread已关闭 | 不推断CI遇到此场景 |

完整回归目前是pytest无内部timeout、全部输出写私有文件、完成后才生成聚合报告。native_suite的600s只约束run_acceptance直接进程，外层900s同样不是后代回收证明。既有健康轮询最多100次，每次5s请求期限，停滞响应时可能累计约500s；逐fixture数据库创建/迁移和SQL也无统一执行期限。上述是代码及本地探针证明的风险，未证明Windows挂点或死锁，不简单提高600s。

## 已实现的最小诊断

- 仅Doctor/Start失败时，stdout发一个固定ASCII标记并立即flush，整条含LF不超过1024字节。字段限action/schema及固定boundary_phase/category/boundary_reason，可附固定cleanup_category。不分类异常正文，不输出路径、DSN、凭据、环境、ACL主体、health或日志正文。
- suite只解析stdout中的唯一标记，拒绝重复字段、未知/额外字段、错action、多标记、非ASCII和超限内容。缺失/无效为DIAGNOSTIC_UNAVAILABLE；不转发完整stdout/stderr。stdout避免PS5对native stderr的包装；原human stderr、exit1及Setup旧错误检查保持。真实PS5送达仍待另行决定的Windows验证。
- Start若清理异常覆盖启动异常，仅附主故障的固定元数据；原清理尝试、状态文件和退出异常保持。状态写入与health检查有明确子阶段，不因清理覆盖误标。
- 完整回归通过显式progress参数启用独立pytest插件，私有原子记录仅schema、当前UUID与固定阶段，读取上限512字节；正常publisher/helper保持纯标准库。公开regression_phase只表示读取时最后记录的阶段，不能保证超时瞬间准确或证明某测试失败。无测试ID、计数或用户文本。
- 原safe annotations的8条/单条UTF8含LF2048字节/总16384字节/整批25白名单ID上限及异常关闭保持；新增字段也经固定白名单两次投影。测试判定、600s/900s、工作流和发布成功合同保持。

## 验证与边界

最终相关203PASS/0FAIL/0SKIP/2既有WARN，8.01s。首轮完整回归893PASS/1FAIL/1SKIP，269.38s，唯一FAIL为新增无sitepackages publisher测试误期望exit0；按原SUMMARY_MISSING合同修为exit1，保留旧运行证据。最终冻结源码完整复验895PASS/0FAIL/1SKIP，271.73s，exit0；最后阶段report_write。逐项核对最终报告与测试时冻结hash一致；提交检查随后移除progress helper一个多余末尾LF，AST完全相同，其前后hash单列于证据，证据见[evidence](evidence/eng041-diagnostics.json)；不以首轮结果替代最终成绩。

两位独立只读复核闭合：publisher不应新增pytest运行依赖；state/health的主故障分类遗漏；PS5 stderr包装风险；无环境publisher的原失败合同。最终复核无剩余阻断，审查者未声称自行运行测试。10份诊断源码已冻结并核对。业务src、roles.sql、Common.ps1、环境白名单/phase config、Engineering.ps1与workflow字节未变。

早期后代探针的非子进程wait在本容器遇已终止孤儿zombie（无活动进程、尚有内核记录）；后续探针使用独立监督器仅收养/回收本次实验子进程，未改变产品进程策略。此项记录保留于本地证据，不把“PG停止成功”当作测试后代全部退出。

本地原环境、备份及失败/最终证据均保留。R4关闭、0真实模型调用/预算；F1/F2未签收，Server不是Win11，36AT6EX NOT_RUN。当前仅本地提交，下一步应由用户决定是否普通同步并做一次既有标准CI以取得新固定阶段诊断。
