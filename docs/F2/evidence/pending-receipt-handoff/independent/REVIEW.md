# 尚未回执事项交接：独立只读审查

结论：限定范围 PASS；最终源码 `0418146b7c2024577e4bdaba509ec5fd9b6c433d` 未发现剩余阻断。直接父源码为 `a5ea0c61ebef365527aac9f570494c61cec1fac9`，业务基线为 `4a0ec78ec7d554204e6fea66a75afd26242c3cd5`。根代理是唯一仓库/Git写入者；本独审只读源码/Git，只在本私有 `/tmp/parkweave-handoff-independent-review` 写探针和证据。

## 最终实际运行

本次重新在最终041源码上执行 **51 PASS、0 FAIL、0 ERROR、0 SKIP，12.26秒**。51不是与旧源码成绩相加，也不含根作者测试、旧通知分页25项或之前其他切片成绩。

| 本轮独立探针文件 | 数量 | 实际范围 |
| --- | ---: | --- |
| test_handoff_independent.py | 32 | 新owned合成PG / 进程内ASGI，真实锁等待、字段篡改、实际ACCEPT、代际/当前授权、schema约束、隔离附件、人工办理链 |
| test_lineage_exact_types.py | 4 | 自有夹具owner修改JSONB：REOFFER三个等值不同类型负控、原ACCEPT revision浮点负控；实际类型先核验，HTTP409且事务无业务变化 |
| test_handoff_vm_independent.py + handoff_vm_independent.js | 15 | 从最终web提取真实分派JS；独立DOM/fetch/storage/时钟doubles，完全离线 |

命令使用 `/tmp/parkweave-summary-venv/bin/python -m pytest`，显式 `pythonpath='src tests /tmp/parkweave-handoff-independent-review'`、`--confcutdir` 指向本私有目录；只选择上述三个私有探针文件。私有conftest显式导入仓库原conftest，复用已授权Linux fresh-owned fixture创建/迁移/清理协议及 `drop_owned_fixture_database`，没有另建授权路径。PG/ASGI测试仅复用原fixture和基本offer/accept准备助手，独立断言、锁等待观察、篡改负控、恢复检查与VM场景为本次新写。

最终原始日志：`final-0418146b.log`；JUnit：`final-0418146b.xml`。JUnit的testcase总数及各文件分布在manifest中再次解析核对。两条环境warning为既有Starlette TestClient弃用提示及XDG运行目录fallback，未导致跳过或失败。

## 关键证据与源码判断

- SUBMIT先与HANDOFF先两路探针分别在获胜事务取得现有锁后暂停，启动竞争事务，独立查询 `pg_stat_activity` 实际观察第二backend `wait_event_type='Lock'` 且future尚未完成，才释放第一事务。结果均为第一COMMITTED、第二CONFLICT，检查实际receipt数量/current_offer状态；不是仅凭线程启动顺序推断并发。
- 9个handoff lineage字段逐一篡改均拒ACCEPT并保持事务前业务表快照；最新实际ACCEPT选择拒绝更旧代；只有offer state/step而没有有效实际ACCEPT事件不足以发交接。首次旧材料代与最终新UUID人工SUBMIT/企业ACK仍分离，Case目标未自动完成。
- schema29实际存在 `UNIQUE(receipt_step_id)`，第二offer复用同step被数据库拒绝；原直接legacy CREATE仍拒绝已有步骤。探针在自有夹具恢复实际旧28约束及marker，发交接与待接单ACCEPT都在写前409。原迁移SQL在没有原fresh-owned fixture票据时拒绝；复用该fixture已有创建证据的迁移重放保留历史和权限集合。
- 恢复GET重核专员本人当前READ、preparation assignment、active、role及tenant，拒绝无私密ID/key/原因回显且零业务写入。恢复COMMITTED只返回原历史事件，不代替新方接单、不恢复旧方写入。
- 普通Store exact type与全部7种隔离access/execution/preview附件负控均关闭交接。源码差异对照确认原executor_receipts、通知实现、preview SQL/执行、信任/登记及角色权限文件没有因本片改写；详细冻结blob/hash记录见manifest。
- VM独立检查损坏JSON、错误根形状、额外正文、actor类型、超24小时期限、9条句柄拒绝；8条容量不发POST；绝对24小时期限不随GET续期。NOT_OBSERVED只读核对并禁新提交；合法过期句柄按既定合同清理，不能据此认定旧请求失败。迟到恢复JSON/403在身份A→B→A后不改新视图/原句柄；不匹配的scope/key/event actor/event dispatch及等待期间被改句柄均不释放未知结果锁。所有实际调用均为原恢复GET、no-store、无body；无自动commands/receipt调用。

## 发现与保留的失败历史

初次a5主要PG为30 PASS/1 FAIL（私有造坏数据删除ACCEPT事件被原outbox外键挡住），VM为14 PASS/1 FAIL（容量分支已有两项有效断言，私有wrapper误要求至少三项）；原日志/JUnit/探针字节均存 `initial-*`。后续只修私有探针：改事件action使缺实际ACCEPT而保留外键，补容量错误消息断言，并补原票据迁移验证；a5主要探针32+15通过，仍不签最终041。

类型探针最初有一次ImportError collection（0执行，`collection-*`）；下一轮一项bool真正进入ACCEPT得到HTTP200，而另两项float硬写4.0与实际revision5不等，在私有布置阶段失败（`first-types-*`，不能计为应用缺陷）。独审首次即时消息误把三项均称为已进入ACCEPT，随后按完整日志明确更正该误报。动态 `float(old)`后，`lineage-types-confirmed-a5ea0c61.log/.xml` 三项均先验证数据库加载为bool/float，再实际ACCEPT得到HTTP200：前代receipt revision 1→true、前/当前preparation revision 5→5.0。这是精确lineage完整性缺陷，不表示外部用户能修改不可写事件或已经越权。

根在041限定修复新handoff字段的type+value校验，并在新handoff predecessor内核原ACCEPT关键字段类型；共享旧 `_latest_accepted`/新材料恢复逻辑保持原边界。最终51重新运行包含三项缺陷复测及新增原ACCEPT浮点控，均实际HTTP409且无业务变更。所有失败原文保留，历史哈希索引在 `a5-failure-and-run-history.json`，不以重跑绿覆盖历史。

## 限制

仅签本片普通SYNTHETIC人工待回执交接及上述独立工程子场景。owner篡改负控不是对数据库owner全面替换攻击的防御证明。不运行真实模型、旧隔离execution/receipt证明链、HTTP listener、外部网络、浏览器或替代URL；原 `data: ERR_BLOCKED_BY_ADMINISTRATOR` 限制持续保留。没有生产/安装/native授权、权限文件修改、持久信任登记、部署或主线整合；不宣称Windows、真实浏览器、多worker部署、全部AT/F2、现实外部受理或线下履约验收。

原始失败日志/JUnit可能带自有短命合成fixture诊断repr，应留私有原字节及哈希；公开报告可使用本报告及历史分类，不需要发布这些repr。最终PASS证据不含失败fixture正文。
