# ENG052：有界启动/数据库定位与Start记录保留修复

对CI37462634764再次走正常check-run/安全annotations只读入口，结果与ENG051逐字段一致：head7596427/attempt1/failure，6PASS2FAIL1NOT_RUN，非PASS0遗漏。Setup、拒绝覆盖、CONFIG/session字节保留及Doctor通过仍是固定流程与完整非PASS集合的推断，未取得逐项PASS行；直接字段为Start READINESS_TIMEOUT、后续API/browser/restart NOT_RUN，以及600秒回归TimeoutExpired/countsMISSING/最后pytest_setup-plan_revision恢复测试。没有读取原日志、路径、响应正文或秘密，没有改变代理/身份。汇总及hash见[evidence JSON](evidence/eng052-bounded-diagnostics.json)，逐项分类耗时见[CSV](evidence/eng052-bounded-db-cost.csv)。

Start源码使用同一已验证loopback配置端口启动uvicorn并请求health，当前CI新CONFIG模板为8765，已有HTTP opener关闭loopback代理；未发现静态地址不一致。到达READINESS_TIMEOUT意味着两次Popen/create_time及STATE写入已完成，轮询点没有发现两个启动进程退出；不等于API已返回健康响应或worker已处理业务，真实退出状态未观测。health每次连接DB并查询schema，HTTP单次1秒而Store连接2秒，查询另无统一期限；不能据此判定实际DB延迟。Windows健康响应、mode/model/PID各条件、venv redirector候选均未观测，不能猜测放松PID核验。

一次初始有界成本探针实际仅执行4项，4PASS/1.85秒；重复命令行选择没有形成重复运行，保留原证据，未冒充32项。随后采用私有参数wrapper显式八轮，每轮调用四组既有原目标断言，每项独立fixture，32PASS/0FAIL/0SKIP，JUnit9.633秒、监督10.6858秒；120秒总限额、原阶段监督，无截止触发。仅定点，不重跑完整套件。

|分类|次数|总秒数|首轮四项总秒数|末轮四项总秒数|
|---|---:|---:|---:|---:|
|连接|913|1.680168|0.219402|0.200311|
|CREATE DATABASE|32|0.369975|0.052985|0.048027|
|迁移事务|32|2.053811|0.258965|0.261875|
|seed事务|32|0.338365|0.048113|0.044487|
|GRANT execute|1008|0.146988|0.021042|0.016675|
|DROP DATABASE|32|0.106988|0.017703|0.015249|

连接计时嵌套在迁移/seed内，GRANT仅execute、不含提交，类别不可相加当总成本。32项setup5.072798秒、call4.151493秒、teardown0.225229秒。每次teardown后维护连接采样：自有fixture库0、pg_stat_activity总行5（排除当前observer，包含背景backend）、idleTxn/Lock/blocked均0；不等于连续无泄漏或精确client inventory。9个1Hz样本主进程live连接最大1，线程最大4、fd最大17；末样本live1处于测试期间，不能当最终泄漏。可见子进程0不包含监督器收养的PG。监督器随后实际回收自有后代。首末轮未见持续成本上升，仅为短期Linux证据。

本地打包PG实际为16.2，pgserver默认Unix socket；CI要求PG17并用loopback TCP。平台、存储与连接路径均不同，本地完整290.942秒与本轮成本不能外推Windows吞吐或证明600秒纯累计预算。最后测试多次移动、这次处于setup，也不能直接归因该测试本体。下一项必要观测是累计elapsed/ordinal/已完成数量与当前fixture阶段/耗时，少量边界采样client连接、fixture库连接、idleTxn/Lock/blocked及已创建后台进程状态。

另做一次真实Linux API/worker启动探针，使用自有UUID库、LOCAL/MOCK、现有8765监听则拒绝，日志stdout/stderr丢弃。1PASS，JUnit1.503秒（控制台1.52秒）、监督2.5073秒；两child创建，第7次请求得到1个有效响应，LOCAL/MODEL_MOCK/process均匹配，末次两child为RUNNING。准确主动停止后两child为EXIT_NONZERO，这不是启动失败。只证明此次Linux通用启动与health路径；worker业务未验证，Windows未验证。model_calls/budget字段是声明的策略常量，并非计量。私有probe自身部分失败清理未被证明，本次两个直接child退出与监督器实际收养/回收记录分别保留；不能宣称任意失败路径保证整树回收。

发现并复现一个独立的本地缺陷：Start失败清理忽略stop_record的FOREIGN_REFUSED返回值，仍删除STATE；普通Stop原本保留该记录。受控四参数修改前2FAIL2PASS，拒绝在任一位置均丢记录。最小修复仍每记录调用一次原stop_record，仅全部STOPPED/ABSENT才删STATE；拒绝/未知返回值保留原字节，并沿既有primary机制保留READINESS_TIMEOUT，另附固定cleanup_category=BoundaryError。没有增加终止、force、身份或权限操作，也不声称Windows曾走此分支或因此累积。清理直接抛异常后中断后续操作的既有行为不变。

修改后定点138PASS/0FAIL/2WindowsSKIP/2既有WARN/控制台4.99秒。首次默认sandbox该集合136PASS2socket-EPERM2SKIP另存；使用已授权正式工具审批原样执行后通过，不换代理、不绕拒绝，无自动审批拒绝。32项/health实验在此修复前，不能当修改后全套成绩。两位独立只读review无修复阻断，确认计时嵌套、短期/Linux与cleanup证据限制。私有db-cost plugin仅独立子进程使用，未完整恢复connect，不可用于长期同进程pytest会话；临时测试文件已删除，私有源/原始证据保留。

下一最小必要health观测仅在既有循环记录0–50 attempts/responses、固定last_observation；仅有有效响应时给mode/model/process匹配布尔值；清理返回STOPPED/ABSENT/FOREIGN_REFUSED各0–2，另记attempted/recorded，未检查项不当已停止。保留原JSON/结构错误与主失败，不输出正文、reason/message、PID、URL、DSN或日志，不放宽身份判定。回归复用既有单条原子snapshot添加有界elapsed/ordinal/completed和fixture阶段，少量边界计数，不增加持续复杂追踪框架。上述产品观测尚未实现，本轮没有push/新CI；600/900、CONFIG/SESSION批准范围、F1/F2未签收、Server非Win11、36AT6EX NOT_RUN、R4关闭和预算策略0保持。代码及报告仅本地commit，原环境与恢复包保留。
