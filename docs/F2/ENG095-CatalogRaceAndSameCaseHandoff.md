# ENG095 目录竞争边界与同 Case 接单回执入口

基线 `8b4789bc3a694faf17ba4db6fd38f4c96e15f196`。按原始 V1《分阶段开发计划》F2-T02/T03/T04 与《平台产品设计》§5.5，推进已有计划、交接、执行者回执的可用连接；不更改原验收规格。这里的回执来自产品已有 SYNTHETIC 合同，实际 PG/API/UI 的办理记录不能证明外部真实履约或原目标完成。

## 本轮验收目标

1. 明确目录更新入口与事务保证，用真正管理员并发事务证明已可见变化拒绝及最后读取后的残余窗口；在现权限内拒绝最终响应已观察到陈旧的首次严格确认，保留原键历史恢复。
2. 同一 preparation/Case/Run，企业已有 P1/P2 核对 → 专员现有分派 → 有合法 Run 访问的执行者本人接受 → 企业 P3 核对 → 执行者现有回执提交 → 企业核对 → P4 核对与刷新回读。接受必须同事务创建唯一既有回执步骤；不生成替代 Mock 成功标签。
3. 从计划直接进入该 Case 的交接或已有接单回执，导航只 GET；缺当前接受、缺合法访问、不同身份/Case 与迟到响应不得回填私有旧视图或创建权限。
4. 保留完整回归计数、源冻结、实际浏览器截图及独立检查；已验证累积提交普通同步到原开发分支并核实精确 SHA 和现有 CI。

## 目录入口、保证与残余竞争

应用对 `preparation_catalog` 仅 SELECT。唯一现有写入口 `preparation.seed_synthetic(owner, tokens)` 使用测试/初始化 owner 插入不存在的合成目录条目，`ON CONFLICT DO NOTHING`，不是目录更新或正式发布 API。外部数据库管理员可直接 UPDATE/DELETE/INSERT；当前没有受支持的正式目录发布者或协作锁协议。

READ COMMITTED 下首/末比较读取语句开始时已提交的目录。原有父事项、计划、授权、资源/组合锁及 P1 gate 保持；首次严格关联插入后，最后 `_view` 如果已经观察到新关联来源 `NEEDS_RECHECK`，现回滚并返回 409。关联/impact/计划 invalidation 同事务回滚。旧键恢复仍在新鲜度检查前恢复不可变旧事件，并另行显示当前来源失效。

真实 PG 测试在 BEFORE INSERT 屏障中让管理员提交目录变更：末次比较已通过，但最终响应观察到变化，首次确认必须 409 且无新关联。另一测试在 DEFERRABLE AFTER INSERT 的 COMMIT 屏障中让管理员更新：所有目录读取已结束，管理员先提交，确认仍可能 201 保存旧来源 impact，后续读取明确 `NEEDS_RECHECK`。RC/RC、RR/RC、SSI/RC 与双方 SSI 四组均真实复现此窗口。这个通过的负向证据证明残余限制，不能算完全原子性修复。

应用缺 UPDATE 权限，因此不能取得目录行 `FOR SHARE` 等锁；仅 SELECT 的 ACCESS SHARE 表锁不阻 UPDATE。REPEATABLE READ 或 SERIALIZABLE 固定快照/串行化顺序也不保证按墙钟先提交的管理员版本已包含在确认里；没有冲突环时仍可把确认排在管理员之前。这些判断与 PostgreSQL 官方 [SELECT 锁权限](https://www.postgresql.org/docs/current/sql-select.html)、[LOCK 权限](https://www.postgresql.org/docs/current/sql-lock.html)、[事务隔离](https://www.postgresql.org/docs/current/transaction-iso.html) 和 [协作 advisory 锁](https://www.postgresql.org/docs/current/explicit-locking.html) 相符。没有现权限内的目录更新业务路径可接入共同协议，本轮不新增 GRANT、发布凭据、函数权限或安全配置。完整修复需正式发布合同/不可变版本与已授权写者协调，仍未实现。

## 产品连接与权限边界

新增计划页按角色显示的接单交接入口，以及企业/本人执行者的已有回执入口。后者先 GET 当前同 Case 分派，要求当前 offer 已 ACCEPTED、offer 与 dispatch 的 receipt_step_id 一致，再 GET 原回执；回执 preparation ID/材料 revision 必须与打开的计划一致，且计划 generation/token 在返回后仍相同才渲染。未接单时显示明确前置，不 POST 建回执。专员没有回执入口。

浏览器首轮发现旧 `clearPreparation/clearReceipts/clearDispatch → clearLocalCase → clearPlan` 清理链会提前使计划上下文失效；现以显式 `preservePlan` 仅在受控 fromPlan 导航的同步清理调用中传播。普通身份/Case/列表切换仍默认清计划，异步响应返回仍检查原 generation/token。修复后必须重跑完整实际浏览器流程，静态检查不替代该结果。

原分派接受事务、回执提交/企业核对、P3/P4 CHECK 与持久来源均复用；没有新增执行权、assignment、Grant、owner 动作或隐式责任转移。返回计划重新 GET 并显式 CHECK，不能把历史或迟到响应当当前核验。

## GitHub 累积同步

远端只读核实原基线 `e03dbf78c4b1daeafbd93cd7b6dc50ba9d923ecb` 后，ENG092–094 三个已完整验证提交普通快进推送至 `dev/f1-foundation`，再次核实远端精确 `8b4789bc3a694faf17ba4db6fd38f4c96e15f196`。对应 [37603417766/attempt1](https://github.com/T1doo/ParkWeave/actions/runs/37603417766) 精确同 SHA，`completed/success`，仅现有 Windows Server engineering 隔离 Job；没有新增 runner、预算或安全敏感 Windows owner 操作，不能称完整 Windows/Win11 验收。

专项目录/替代回归为57通过、0失败、0跳过；新增同Case后端链7通过、0失败、0跳过。最终实际浏览器1通过、0失败、0跳过（29.69秒、2个既有警告），同一Case六次原业务POST、导航0POST、五张授权表前后hash一致、1200/390/320无横溢出；七张最终PNG已实际独立看图。最终完整Linux回归1705通过、0失败、0错误、9个原生Windows跳过、2个既有警告（390.82秒）；239份冻结源0差异，日志/JUnit hash记录在机器证据中，不将专项/浏览器计数重复累加到全量。

最终本轮测试、冻结与浏览器证据见 [机器记录](evidence/eng095-catalog-race-and-handoff.json)。F1 未签收，F2 仅并行探索，R4 关闭，模型调用/预算 0。正式 Approval、目录发布与完整 ServicePlan/CaseStep/真实履约仍未交付。
