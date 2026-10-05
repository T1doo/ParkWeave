# F1 有界工程测试规格（新建）

来源：完整V1产品§6—7、开发计划F1及§10，本轮新建；未收到原验收包。固定AT/EX全文定义见../验收规格.json，均NOT_RUN。本文件只冻结当前可执行工程子集，不降低完整验收标准。

环境：Linux cloud / Python 3.12.14 / PostgreSQL 16.2。测试类型为合成工程（MODEL_MOCK范围，模型未调用）和FAULT_INJECTION；不包含LIVE链/Windows/园区效果。

重置：tests/conftest.py为每个测试创建独立临时PostgreSQL数据库，owner迁移、seed，应用最小角色执行；退出删除临时库。身份为fixture-a（park-a/org-a）、fixture-b（park-a/org-b）、fixture-c（park-b/org-c），全部自建合成；随机会话仅测试期有效，非真实授权资料。

| 工程检查 | 输入/操作与独立oracle | 对应AT子范围 |
| --- | --- | --- |
| 持久建单及进程重启 | API202后启动独立worker子进程两次；唯一Case、VERIFIED回执；Run成功而Case待补件 | 13、16、17（局部） |
| 同键并发与指纹 | 16次并发同输入同键→一Run；不同目标同键拒绝；8worker抢占→一claim/Case | 16、17（局部） |
| 两园区/三企业隔离 | 猜ID读/取消返回403；请求体伪造org/role返回422 | 04（局部，尚无资料/缓存/资源入口） |
| 领取后撤权 | owner撤权后finish无Case，Run FAILED；读写拒绝，seed不恢复授权 | 19（局部） |
| 过期接管与fencing | owner显式过期租约，新worker token增大；旧worker所有finish拒绝，最终唯一Case | 17（本地原子动作子集） |
| 暂停/取消 | 领取后控制，旧claim无效果；暂停可恢复，取消不声明撤销 | 18（无远端在途） |
| 原子提交与outbox | 事务中插Case后抛故障→业务/回执/outbox全部回滚；消费者ack前故障回滚；倒序、重复消费不回退投影 | 16（局部） |
| 契约拒绝 | 未知字段/任意工具/路径/真实来源/空目标/超长/错误类型→422；库内无Run/Operation | 03、05（无文件导入） |
| 注入文字及尺寸 | >16KiB实际body→413；脚本字符串只存为文本，不产生宿主文件；UI用textContent | 03、05（局部） |
| 迁移权限隔离 | 应用角色执行身份UPDATE/DDL→InsufficientPrivilege | 04、19（角色边界局部） |
| 三值真值表 | 9种AND/OR各组合对独立Kleene表；UNKNOWN不变TRUE | 21最小基础函数，完整准备度NOT_RUN |
| 领域契约 | 计划目标覆盖、有限DAG、未知依赖/环/工具拒绝；未审ServiceSpec拒绝 | 03（契约子集） |

运行：`.venv/bin/python -m pytest -q`。可信动作仅case.create/1，由代码字面注册，ServiceSpec/Plan为0.1严格投影，尚不覆盖V1完整有效期、材料、资源、批准等契约；未接入运行规划入口。上限：16KiB请求、2000字符目标、16步骤；文件导入关闭，真实模型预算禁用。

租约30秒，本地动作只在短事务执行；回执与业务一起提交，因此过期接管可核对为无部分提交再执行。本轮不支持非原子外部适配器、OUTCOME_UNKNOWN、远端撤销、模型长等待心跳；这些完整AT-17—20/30仍NOT_RUN。当前pause/cancel直接fence本地待提交动作，不能外推为远端取消语义。

API身份表只读，以共享授权advisory锁和owner撤权独占锁串行化；所有支持路径同一锁顺序。字段级授权、服务执行者、运营人员、材料/导出/缓存授权尚未实现。无真实园区目录、规则许可、用户观察或业务收益。

## ENG-002 新增工程子集

本轮新增13个FAULT_INJECTION测试与6个契约边界测试；全量40 PASS，原21仍在回归内。tests/test_fault_ledger.py只有在独立临时测试数据库显式安装fault-schema.sql后才可运行；Store.migrate、正常roles.sql、API动作注册与worker均不启用它。没有真实网络、外部账号、真实园区系统或业务履约。

| 新增检查 | 明确初态/操作与oracle | AT子范围 |
| --- | --- | --- |
| 丢响应后的核对 | PREPARED→持久DISPATCHED→模拟效果单独提交→丢响应→OUTCOME_UNKNOWN；新claim仅query，VERIFIED；dispatch_count恒为1，无Case | 20；16/17局部 |
| 失联与撤权 | 派发后效果已提交、未记回执；过期接管，撤权后内核仍能记历史效果，旧token拒写，用户读拒绝；不重发 | 17、19、20局部 |
| 暂停取消未知 | 已派发后PAUSE/CANCEL令旧token失效；未查到效果保持UNKNOWN，不推断未生效；在途模拟效果随后出现，核对保留原意图与事实，不声称撤销 | 18、20局部 |
| 派发前控制/撤权/过期 | 取消或撤权→无效果；暂停不领取、继续后只执行一次；过期worker不可dispatch | 17—19局部 |
| 跨企业/园区账本隔离 | fixture-b/c猜操作ID读/控制均拒绝；相同key按principal分离；同key改输入冲突 | 04、19局部 |
| 回执真实性 | 园区/企业/操作ID/指纹/来源/效果类型精确匹配；串企业回执EFFECT_KNOWN_INVALID，不能VERIFIED | 20局部 |
| 默认关闭 | 普通数据库没有fault表；API请求fault.record仍422 | 03局部 |
| 计划契约边界 | 重复目标/覆盖/依赖、空白目标、超长目标/覆盖和越界引用ID拒绝；有效DAG保留 | 03局部 |

模拟远端fault_effects与fault_operations故意分事务。查不到记录只是未观察到，不是权威“未执行”；DISPATCHED/UNKNOWN禁止第二次dispatch。模拟器记录dispatch_count作为独立oracle，并不据此宣称上游接口幂等。核对函数只记先前派发的效果，撤权后不新发动作、不恢复用户读权限。未知仍未知，不能自动跳到FAILED_SAFE。

FAULT账本是测试驱动的持久工程原型，尚未与正常Run/worker/outbox集成，不代表完整AT-16—20通过。正常产品仍只有原子本地case.create/1。测试重置仍为每测试临时库创建/删除，数据与身份来源全部自建合成。故障schema不随普通安装迁移生效，应用角色仅在临时测试库获得fault_operations表权限；模拟器owner独立写fault_effects。
