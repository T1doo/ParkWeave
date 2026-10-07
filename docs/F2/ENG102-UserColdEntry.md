# ENG102 普通用户临时冷入口

本轮修复实际体验起点：Linux启动器原来没有schema25创建票据，普通用户不能按指南启动新的演示。新增显式 `--fresh-fixture`，原Store、迁移保护、身份授权和产品API保持既有合同。外线固定名测试修复a26d99c已整合为03a8230，只传递原receipt对象，没有改断言或guard。

## 用户可执行路径

1. 安装者用已批准的Python/Linux依赖，在仓库前台运行首次体验文档的 `linux_fixture_server.py --fresh-fixture` 命令。它只在新自有临时目录初始化PG，CREATE DB前capture，创建后record，原loader同事务authorize并迁移到25。确认health属于本次API进程后，输出本机端口与私有runtime_directory。
2. 安装者只从该目录给使用者提供原合成企业/专员会话；普通使用者进入服务目录，明确新目标和专员，点开始资料准备。网页原Run API与实际LOCAL worker创建新Run/Case，再关联新资料事项，不预建Case。
3. 企业在当前事项逐项追加三字段合成事实来源，声明本Case用途并亲自选择每项来源；填写两份有来源的材料。获派专员人工REVIEW，企业CONFIRM。来源真实性和资格仍未判定。
4. 查看此Case协作入口与已有Run访问。当前从零新Run没有executor assignment，显示BLOCKED_NO_EXISTING_ASSIGNMENT；分派表单不可用，伪造执行者请求403，分派和回执记录仍为0。此处必须停，不借另一Case授权，不自动补Grant。
5. 只有同一Run已具备合法访问，才能走原资源/P1–P5、本人接单、回执与本地关闭路径。该前置目前仍由原fixture/安装准备提供；上一轮预建Case恢复21图不能算新Case冷链到回执。

新临时模式退出时关闭本次API/worker/PG，删除仅本次临时目录；不能用它保留本次业务至下次启动。停止未确认则保留目录并明确失败。仓库已有.runtime、旧数据库、会话及备份保持；只有既有schema25支持原持久模式，低版本不补造创建证明或自动升级。真实Windows installed入口仍没有受审票据适配。

## 实际验证范围

启动/票据专项7PASS/6.44秒，包括真实launcher就绪与SIGTERM回收、旧24保护、首子进程清理失败仍尝试后项、未确认服务时保留目录，以及固定名外线与原loopback lifecycle。初轮6PASS/1FAIL仅新测试漏创建临时父目录，原始日志/JUnit保留；修正测试前置后通过。

新的实际Chromium走查从0 Run/Case/Preparation/事实/材料/分派/回执/计划开始，经真实网页与worker创建业务，完成事实和双角色材料确认。最终Run SUCCEEDED、Case NEEDS_INPUT、资料LOCAL_CONFIRMED、qualification NOT_EVALUATED。7张权限表前后hash相同，assignment/dispatch/receipt为0，模型计划和步骤为0；13图覆盖1200/390/320，先前五次脚手架/汇总错误保留且不计为PASS。浏览器使用原empty-owned fixture，未调用新launcher；两份验证分开记录，不伪称同一次普通安装运行。

独立旧冷图审还发现专员在无执行者时误提示再次确认资料：catalog.ready已包含执行者非空，原无执行者文案分支不可达。仅修renderer原因提示，不改变ready、按钮可用性、API或授权；修改后另从0业务库完整复验13图通过，旧错误图保留。

最终Linux验证、开发分支同步和精确HEAD Server CI另以机器证据终态记录。当前不预写通过。原R0/PR0、F1未签收/F2并行、42AT/EX及T06/AT08/AT35未验收；R4关闭，真实模型预算0，Server不等同Win11。

见[当前机器证据](../integration/ENG102-ColdUserEntryEvidence.json)、[首次体验](../首次体验.md)和[用户操作卡](../demo/AcceptanceWalk.html)。旧五个浏览器复现脚本尚未适配fresh runtime，不得复制私有会话到仓库补齐。
