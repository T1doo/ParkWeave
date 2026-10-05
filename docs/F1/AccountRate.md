# R2账号发送门（ENG010）

仅对显式同一协调库、同一account的调用统一协调；业务库、身份、日志、端口仍各自独立。独立数据库不会自动共享计数。本轮第二产品是临时PostgreSQL内的合成产品/独立低权限role，不修改或接入Sim2Act，不证明两真实产品部署已协同。

## 有界状态与速率

账号行锁串行预算和速率变迁，默认rate_limit=30，可下调/0关闭，不允许大于30。实际供应商窗口/额度仍需核实，不能把源默认值称为当前provider保证。

1. RESERVED预留8192 tokens/1call，rate slot尚未占用。`hold_rate`在同account计数后预约HELD，仍确定未发送。
2. `dispatch`以当前审批、有效期、速率/绑定及代次再次核查，原子转DISPATCHED/IN_FLIGHT后才允许调用HTTP。所有HELD及IN_FLIGHT不随时间自动释放，避免延迟发送或长请求跨窗口重获额度。
3. 返回、timeout、429、校验拒绝等调用都转COOLDOWN；从协调数据库完成时刻保守占位60秒，`finished_at > now-60秒`计数，因此恰好60秒可以重获slot。不是在发出后自动回收；不确定完成的调用可能长期占位，需要owner核对。
4. 已发、已结算、unknown的work不得重发或退款。只有确定未发的RESERVED可释放预算/slot；同work已RELEASED可重开新generation，旧句柄不能操作新代次。变迁台账保留每代预约/拒绝/释放/发送/结算。

发送授权与真实socket不是分布式原子事务。DB标记后进程失联保守视为已发送/未决，不盲重发；不能承诺远端到包时刻，也不能从模拟授权宣称实际provider限流通过。HELD/IN_FLIGHT持续占位加完成后冷却约束了本地许可，不以后台超时清理猜测未知结果。

rate拒绝不执行HTTP，Python释放仍RESERVED的预约并报告ACCOUNT_RATE_LIMITED_NOT_SENT。若只有COOLDOWN能给出最早可重试时间，Run以next_attempt_at持久延后且fence递增，不睡眠占worker；最多3次限流拒绝后有界失败。待决请求/禁发等无法给出时间则立即有界失败。已知Case/VERIFIED回执保留，cached PLAN与本地动作不重复。只重试明确未发送的限流预约，无供应商错误自动重试。

## 时间、迁移与安全配置

生产使用协调库clock_timestamp；回拨停止新预约/发送，历史费用仍结算且完成时刻取不早于已见时间，避免提前释放。owner-only synthetic_clock只用于SYNTHETIC，LIVE始终忽略，应用无表写权限。held_at/dispatched_at/finished_at及分类事件可核查时点；耗时可由finished_at-dispatched_at求差，未决不伪填。正文、key不写该台账。

quota.sql是独立协调器owner的幂等增量安装，不是产品schema8，也不由worker自动安装/批准额度。历史已发送而没有时点的记录保守迁移为IN_FLIGHT；不会按旧created_at猜时间而释放。升级保留预算/usage/历史，新函数要求generation并移除旧无代次签名；owner需重新授予受控函数EXECUTE。现有窗口总预算不自动滚动/清零，不做金额价目或供应商账单校准。

LIVE默认关闭。纯check_names只对显式传入Mapping读取变量名集合，检测PARKWEAVE_INTERN_API_TOKEN或INTERN_API_TOKEN、PARKWEAVE_QUOTA_DSN、PARKWEAVE_PROVIDER_ACCOUNT存在；不读取实际环境或value，不解析DSN/秘密。LiveSafety须显式启用及全部审批预算/注入授权/速率核实/共享绑定核实前提为真，缺值/未知/非bool拒绝；socket adapter同时需要LIVE持久账本，账本还核验owner审批证据/窗口/当前速率证据。

这些布尔门是接入前提，不是实际部署证明或授权凭据。正常CLI本轮仍只显式SYNTHETIC；不创建LIVE worker/注入，不接受聊天密钥，无真实环境探测/HTTP或网络设置修改。实际安全注入、真实额度/同协调点绑定及模型链验证是E2 BLOCKED。

## 确定性证据

tests/test_account_rate.py使用临时真实PG与固定2030合成时钟，禁止真实HTTPTransport：31st、60秒前1微秒/精确边界、长HELD/IN_FLIGHT、timeout/unknown、预算退款和usage、clock回拨、旧generation、owner下调/禁发、两产品40并发合计30、迁移幂等、Fake Mapping不取value、持久FEEDBACK延后恢复与三次上限。独立断言查询DB账本/Case/事件，Mock请求计数不等于真实provider请求。历史eng009-fixed-window-gap.json保留原已知失败，本轮以回归拒绝解除该代码缺口；whole AT30仍NOT_RUN。
