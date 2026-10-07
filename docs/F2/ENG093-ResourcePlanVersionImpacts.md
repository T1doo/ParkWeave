# ENG093：资源与工程计划版本绑定及变更影响

基线 e3a13a3f8257e2c20e952032ea12db67e580b9d6。本片按原设计 §5.6/§6.1/§6.3/§7.4/§8 与 F2-T03/AT09–11/28 处理最关键现有缺口：资源关联已保存材料版本，工程计划已保存核对，但目录、全部目标、占位来源和授权变化的具体影响未完整绑定与说明。已有工程 checkpoint 不是正式业务 Approval；本片不新建真实批准、Grant 或 ServicePlan 执行器，不能宣称完整 T03 已验收。

## 实际门控与读取

controlled_plans 的 P1/P2 使用与新只读投影共享的版本描述。P1 绑定 Case/Run、材料版本/指纹、原诉求和全部已保存目标、模板指纹、当前服务目录 ID/version/source/namespace/qualification 及经办人已有 READ/EXECUTE/PREPARE 状态。P2 绑定关联 ID/版本、组合 ID/状态、成员资源修订/数量/时段/缓冲/状态、占位来源与期限、当前资源规则/source/authority、已有 READ/HOLD 状态。

新增来源字段会使旧工程核对保守失效，须在既有入口显式重新核对。真实业务 gate 使用同一 descriptor；修改目录或未知来源后，不仅 UI 标记失效，原 offer/resource-link 命令也拒绝陈旧核对。未知目录不是重新 CHECK 就能变合法。confirmed 资源组合保留预约，原 HELD TTL 到期不自动取消；预约时段结束、规则变化、容量约束或整组撤回独立重验。

新增 GET `/api/preparations/{id}/resource-plan-binding`，可选 `candidate_combination_id` 只比较本人已有可读组合。事务首句 READ ONLY；当前 Bearer READ、enterprise_operator、PREPARE、owner/tenant、SYNTHETIC、精确 Case/Run 均检查。资源 READ 撤回拒绝私有读取；HOLD/EXECUTE 撤回仍允许合法 READ，但明确显示不能关联。核对人身份在共享授权锁后重新读取 active/角色/tenant 与当前 READ/REVIEW_ASSIGNED。GET 不执行 CHECK、不写 invalidate，不新增关联、预约、分派、回执、权限或身份；拒绝沿用既有授权审计。

返回当前 descriptor 指纹、P1/P2 历史核对与当前来源的具体差异、关联历史/当前资源状态、候选替代差异与关联阻塞、上游和下游重验步骤。正式 Approval 为 NOT_IMPLEMENTED，所有 execution_enabled=False。投影在 READ COMMITTED 多次读取，不承诺原子业务快照；写入口继续在各自事务内独立检查。历史 link 没保存完整旧资源规则时不虚构；旧 checkpoint 有存规则可比较。

## 同一 Case 用户流程

产品四步计划增加“核对方案与资源变化”。先读取当前关联和本人可读组合，再选候选进行比较；选择不提交关联，也不释放旧预约。明确换组合仍回原资料入口关联，之后重新核对 P2/P3/P4；取消旧预约是独立现有操作。

修改诉求/目标、刷新、换 Case/身份、候选选择变化均清旧结果；两次异步读取后检查 Case/身份/资料 revision 与代际，旧回复不能回填。403 清整个私有计划。界面显示可读的材料/目标、组合、资源时段/数量/状态/规则与重验说明，历史指纹简写，避免原始内部 JSON 淹没操作信息。刷新恢复的是当前变化影响，不是批准或执行权。

真实缓存 Chromium 在新隔离产品 PG/API/web 同一 Case 完成：当前工程 P1/P2 → 比较替代且不释放原占用 → 通过原 UI 明确关联替代 → 旧 P2 失效 → 通过原 UI 整组取消替代 → 修改必需目标使 P1 失效 → 刷新重新显示历史和当前变化。浏览器之外未用合成 SQL替代这些业务动作。原组合仍 CONFIRMED，替代组合只有显式取消后 CANCELLED，两条关联历史保留，权限行不变，无新增 dispatch/receipt，自有服务停止，原演示 PG 未启动。测试 fixture 的合成既有身份/权限仅隔离测试前置，不是生产初始化。

## 验证与剩余范围

最终 234 份冻结源码差异 0；完整 Linux 回归 1641 PASS / 0 FAIL / 9 原生 SKIP / 2 WARN，360.75 秒。相关接口回归 107 PASS（新接口 29 项），真实浏览器 1 PASS、1200/390/320 无横溢。源码、接口/完整回归、真实三屏宽浏览器、权限/历史摘要与独立安全复核见[证据](evidence/eng093-resource-plan-version-impacts.json)。实现代理只改 module/API/controlled_plans，测试代理只改新测试，root 负责 web/browser/整合；数据库各自独立，没有并行写同一文件或共享数据库。

仍缺正式不可变 ServiceSpec Release、业务 Approval 与有效期/授权 epoch、持久通用 ServicePlan dependency_lock、全部资源需求组合与正式规则绑定、锁定字段冲突/变更事件影响图和跨 Case 扩大核对。下一片建议在既有显式替代关联中加入当前比较版本 CAS 和持久变更影响记录，防止用户确认已过时的候选；继续沿用既有权限，不创建真实审批或自动释放。

本片只本地 commit，不新增 push/CI/部署/owner 或真实权限修改。F1 未签收、F2 并行探索，Server 非 Win11，R4 关闭，模型调用/预算 0，生产激活关闭，原环境与备份保留。
