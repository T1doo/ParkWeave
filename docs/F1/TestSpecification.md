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
