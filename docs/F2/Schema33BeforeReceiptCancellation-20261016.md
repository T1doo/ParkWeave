# schema33 接单后、首次回执前的明确取消与冷核对

冻结源码 `b46ea7c9c4379d3565f413077a1a5b339a8669d2`，接续 `75adba254a6455258b36d3b3e2f5707196548ec7`。开发分支 `dev/f2-schema33-before-receipt-cancel-20261016`，main只读。

复用原 `before_receipt` 合同：同一普通合成 Case 已有真实 ACCEPT，全部历史步骤从未提交任何回执，当前企业 owner 明确说明原因、勾选确认，以原 Case、资料版本、本地生命周期版本、来源摘要及当前 business frontier 提交取消。取消只改变 Case、本地生命周期和原取消事件；原成功建单、六目标、P1–P5计划、P1/P2核验、分派责任、ACCEPT/CREATE、审批、资源占用和 outbox 均保留。不释放、不重批、不恢复、不把取消当撤销履约事实。

新增资格仅精确 schema33、原 Store、无隔离执行来源；既有完整来源与历史证明继续重验。历史有回执、UNKNOWN/损坏证明、陈旧/缺失 frontier、非当前 owner 或权限撤回均拒绝。未扩大原 handoff 或 reconciliation 门。Native access 保持原合同，本片未新增或宣称其专门拒绝覆盖。

页面原取消句柄现在可走经当前鉴权 GET 重新核实的只读恢复入口，避开要求 EXECUTE 的材料复用装载；READ撤回仍403清除私有视图，句柄不能充当授权。只读样式随上下文清除；从已取消事项切换到另一合法 Case 的原表单恢复。原回执提交、转派及其它直接 Python writer 继续经过原取消守卫。

## 实际验证范围

| 窗口 | 唯一通过项 | 证据 |
|---|---:|---|
| 原 before_receipt 完整模块 | 107 | [JUnit](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/before-receipt.xml) |
| 原首次接单前取消与回执后核对两个完整模块 | 218 | [JUnit](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/original-cancel-policies.xml) |
| 原 schema33 frontier cancellation 完整模块 | 10 | [JUnit](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/frontier-cancellations.xml) |
| 四个直接客户端/权限绑定完整模块 | 133 | [JUnit](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/frozen-client.xml) |
| 新 schema33 实际自有PG/ASGI完整模块 | 15 | [JUnit](evidence/schema33-before-receipt-cancel-20261016/cancel33-oracle/frozen-v2/results.xml) |
| 新纯资格拒绝矩阵完整模块 | 20 | 同上，假SQL纯层不作PG证据 |
| 原实际HTML、安装Chromium、HTTP→ASGI→自有PG | 5 | [JUnit](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/frozen-chromium.xml) |

共 **11个完整直接相关模块、508唯一项 PASS，0FAIL/ERROR/SKIP**。独立冻结审查21纯检查、4 Node模式与主集合重叠，另列不加分。688个 tracked src/tests/scripts/pyproject 输入逐字节核实；[最终门](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/final-gate.json)、[冻结清单](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/freeze.json)、[独审](evidence/schema33-before-receipt-cancel-20261016/cancel33-review/frozen-v2-review.md)、[归档索引](evidence/schema33-before-receipt-cancel-20261016/index.json)。原335个PG回归在UI窄修前运行，涉及的后端源码与最终冻结版一致；最后UI由133项完整复验和本冻结版5项真实浏览器验证，不声称旧窗执行了新UI。

两种真实锁序在独占PG窗口执行：先取消则首回执409；先首回执则真实提交200、取消409，并从全部历史拒绝再次取消。两者均先按原命令完成P3 VERIFY，再捕获原请求，不关闭业务门、不增加锁预算。另覆盖事件实际写后抛错的整事务回滚、幂等参数冲突、原键丢回执冷GET、跨租户/owner/角色、READ/PREPARE/EXECUTE及失活撤权、直接Python writer拒绝、managed来源拒绝，以及资源/责任/通知快照无副作用。

浏览器5种模式为正常明确确认、丢回执、丢回执后撤EXECUTE、撤READ、伪外Case句柄；前三实际成功，后两实际拒绝并保留未知句柄。恢复使用新 Store、新ASGI app和原issued审批桥/前沿协议在同进程合法重挂；裸Store或只挂前沿协议拒绝。恢复只GET原key，没有自动重发POST。此证据不等于跨进程重启、备份恢复或一般生产恢复。

归档复核见[独立审计](evidence/schema33-before-receipt-cancel-20261016-audit/final-audit.json)。

## 失败保全与限制

开发时夹具缺依赖/目标字段拼写、目录证明拒绝、冷Store缺原审批桥、故障trigger破坏冻结目录、缺DOM classList、浏览器route清理等失败原件均保留。首个冻结独测34P1F是测试遗漏原P3 VERIFY，原SUBMIT因此409；保全v1后仅补原VERIFY与诊断，新冻结版完整35项重跑通过。未修改产品门、权限或等待预算。[失败原件hash账本](evidence/schema33-before-receipt-cancel-20261016/cancel33-root/failure-ledger.json)及[全部本轮primary原件封印](evidence/schema33-before-receipt-cancel-20261016/cancel33-delivery/public-primary-seals.json)可核对；私有登记、完整失败原件与数据库保留本地，公档只发布有界文本证据与原件摘要，已知合成令牌按完整登记值处理。

“直接writer拒绝”指原Python服务函数绕HTTP调用；不承诺阻止任意数据库owner SQL。schema33历史已有回执的 reconciliation、更广已接单来源迁移/继续履约合同仍未开放。原99个旧模块本轮未执行；不宣称全仓回归。Windows及其浏览器、广覆盖浏览器、正式AT、真实模型B0–B2、生产、跨进程恢复和原专用PG27前提均NOT_RUN。远端工作流分支过滤不含本开发分支，未改工作流或调度CI，CI NOT_RUN。

下一关键路径是已接单来源变更的明确收束、独立重批与继续履约合同；已有P4/P5效果、F5备份恢复和正式AT前提另行处理。继续按一周目标推进。模型调用0，无main修改、强推、部署、新费用、凭据、安全权限或绕访问拒绝。
