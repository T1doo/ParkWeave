# ENG-007 模型链与共享账号账本

这是F1有界基础工程。真实模型预算授权0、调用0。HTTP code路径实际由httpx.MockTransport测试；不能写成书生真实AT通过。Linux Python3.12.14/PostgreSQL16.2为当前证据，Windows11原生门NOT_RUN。

## HTTP与规划边界

固定官方端点https://chat.intern-ai.org.cn/api/v1/chat/completions，模型intern-s2，只接受已知ASCII大小写同名Intern-S2；官方字段来源延续ENG006的[Chat文档](https://internlm.intern-ai.org.cn/docEn/docs/Chat/)及[Models文档](https://internlm.intern-ai.org.cn/docEn/docs/Models/)。自建合成响应不是官方真实响应。

InternHTTPTransport实现实际Client.stream HTTPS路径，trust_env=False，无重定向、无自动重试、超时<=120秒，读取解码响应累积超过65536字节立即拒绝。不查询环境、不从模型文本执行代码。显式token须SecretStr；已知token明文或JSON转义回显拒绝，payload携带此token也拒绝。无法凭内容识别所有未知秘密，本工程不读取任何其他模型环境变量或密钥。wrong model、不完整参数、length、无完成、无预算均拒绝。

InternChatAdapter在默认socket传输前必须使用PersistentBudget且kind=LIVE；共享库owner批准窗口、产品角色绑定、总额及产品上限检查完成后，持久DISPATCHED标记先于发送。LIVE预算须有approval evidence引用及approved_by；这里只建立字段/受控规则，不创建真实授权。没有LIVE worker开关/部署配置/安全注入。完整LIVE链启用仍BLOCKED。

正常CLI worker的`--model-fixture good`显式选择离线规划链；其他scenario为自建失败fixture，绝不是端用户参数或真实模型策略。需要owner显式安装SYNTHETIC共享预算；缺预算时Run FAILED/零HTTP/零Case。默认路径仍可信直接本地动作；已有model_steps的恢复任务不能被默认worker绕过，缺链配置会安全停止。

ModelChain构造器可显式注入协调库DSN/account/product/kind/transport/token，当前CLI固定SYNTHETIC+MockTransport。规划只支持case.create，proposal goal必须逐字等于持久Intake；每次请求发送前、响应后、可信动作前、最终完成前重验当前身份/权限/控制/fence/input hash。模型请求等待不持有业务数据库长事务，LeaseKeeper独立续租；请求前检查与实际socket之间不能原子锁住远端，已发送后撤权仍记历史成本，禁止新增可信动作。

可信gateway同事务创建Case NEEDS_INPUT、SYNTHETIC、外部NOT_SUBMITTED、线下NO_EVIDENCE及VERIFIED本地回执，然后保留Run RUNNING等待FEEDBACK。反馈内容来自该已提交Case与receipt，不伪造外部成功。FEEDBACK只接受stop，第二个tool proposal拒绝。成功Run仅LOCAL_CASE_CREATED；模型文本不判资格、不承诺外部受理/线下履约。反馈错误时Run FAILED，但已知Case/VERIFIED回执/成功范围保留，不能改成FAILED_SAFE。

## 一个账号一个共享协调点

`quota.sql`由明确协调库owner安装到shared_model_quota，不能由API/worker自动创建或自动给预算。真实部署两个产品须配置**同一协调库、同一provider account不透明引用**，独立低权限DB role及product binding；本轮只在独立临时库中模拟第二产品，不修改Sim2Act。引用由授权owner配置，不从token猜测；使用不同协调点会失去共享保证，实际部署审核仍BLOCKED。

accounts为单个固定起止窗口的账号总calls/tokens；products为显式产品calls/tokens上限。默认未approved，0也有效且拒绝请求。建议owner分配之和<=总额度；即使错误超分配，账号行锁仍拒绝超过总额度。应用仅获得schema USAGE及两个已审核function EXECUTE，不获得表SELECT/UPDATE/DDL；db_role通过session_user强绑定，不能替别产品/账号预留，也不能提高预算/批准窗口。

每次预留8192 tokens和1 call，账号行锁原子协调并发。work为不透明Run UUID+PLAN/FEEDBACK，product/work唯一，内存重启不清零。共享账本仅元数据，不保存prompt、业务事实、响应原文、身份token或模型密钥；产品model_steps结果在产品库，不跨库共享业务资料。

RESERVED → DISPATCHED → SETTLED(严格usage)或OUTCOME_UNKNOWN。只有RESERVED确认尚未发送可RELEASED并返还call/tokens。发送标记竞争仅一个胜者；DISPATCHED/SETTLED/UNKNOWN重复work均不重发。usage缺失、timeout、secret echo等未知收费保守保留8192；已知usage按实际结算，超8192仍全额记账并拒绝输出，额度超额后拒绝下一次调用。重复相同结算幂等，冲突结算拒绝。不依据本地“没收到”退费。

发送后进程丢失而product阶段结果未持久化：预算DISPATCHED/SETTLED保留，恢复返回PREVIOUS_ATTEMPT_NO_RESEND，Run有界失败，不猜测返回/自动重发。PLAN已持久化且Case已提交时恢复只做未完成FEEDBACK，既有Case不重建；旧fence失效后只容许已发送成本结算，不允许旧worker写阶段/动作。

当前是单个冻结窗口的协调基础，不提供预算窗口滚动/重置、真实价格折算、provider账单校准/查询失联响应、跨多个协调库仲裁。owner不得重置有未决调用的窗口计数；后续窗口迁移需保留账本单独实现。TOKEN不是金额，真实计费与预算管理实际验收BLOCKED。这些边界不把本轮工程说成完整成本系统。

## 复核命令及后续独立工程

`.venv/bin/python -m pytest tests/test_model_chain.py tests/test_intern_adapter.py -q`；全量执行器仍42定义whole NOT_RUN。Windows安全文件backend单独派发；同账号真实共享部署、安全注入、LIVE worker activation、真实usage/计费/AT-02/30门另行授权。窗口滚动/货币账单核对需要后续有界规格，不借本轮扩F2。
