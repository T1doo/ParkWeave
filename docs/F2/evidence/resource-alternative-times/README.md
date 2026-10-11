# 同一资源替代时段搜索交付证据

业务基线：`a954bf6811e395d7515181f8bad8dd8f12d1cd7c`。
首个实现提交：`3e0c51eac33cd3ea017fee9b6361785c786daca7`，直接父提交为业务基线。
**最终源码：`f9bf9b76b512eb98ce23f92beba2fc4327e0b8a1`**，直接父提交为3e。证据归档提交直接基于最终源码，不再改变业务代码。独立分支：`dev/f2-resource-alternative-times-20261011`。

## 最终执行

- 根代理：最终源码 **399 PASS，0 FAIL/ERROR/SKIP**，包含新增功能30真实owned PG/进程内ASGI、21实际JS离线NodeVM。其余348为相关资源占位、确认、组合、资源Case/计划与先前手动回执转交回归。新功能51已经包含在399中，不重复计数。完整执行命令、UTC窗口、前后HEAD与clean状态见 `root/final-execution.json`，原始通过日志/JUnit见同目录。
- 独立审查：最终源码 **38 PASS，0 FAIL/ERROR/SKIP**，22 owned PG/ASGI、16 NodeVM。独立容量分段中点oracle、实际pg_stat_activity Lock等待、锁后规则/时钟、完整表快照/SELECT+SET审计和完整组合控制函数验证见 `independent/REVIEW.md`。哈希manifest验证了14个交付文件。
- 整页实际JS仅作语法解析通过，无浏览器执行。source-manifest签392个代码/测试/脚本文件；相较业务基线，386个原代码文件未变，运行改动仅resource_holds.py/api.py/web.html。roles、迁移、四preview SQL、registry/旧隔离来源不变；独审另核121其他runtime Git blob一致。

## 保留的失败与历史窗口

`root/development-history.json`保留每次原始log/XML的SHA256、字节数、计数、私有路径与分类。失败原始字节留当前实例 `/tmp/parkweave-alternative-times/`，不放入仓库（pytest夹具repr可能包含临时会话信息），不假定跨实例共享或持久保留。

1. 原a954入口404：1 FAIL，确认实际功能缺口。
2. 首轮20 API项：19 PASS/1 FAIL；测试夹具企图写入IMPORTED_SNAPSHOT被原schema约束拒绝。改为验证原约束与extra字段422，未改约束或授权。
3. 开发组合40 PASS。
4. 开发相关389项：388 PASS/1 FAIL；合法极值UTC候选buffer计算OverflowError，真实实现错误。仅新搜索处理不可表示buffer；新模型覆盖四日期字段的UTC转换溢出为422。修复功能50 PASS。
5. 旧3e冻结窗口根398 PASS、独审37 PASS，均分别保留，不当作最终f9结果。根实际bundleControls负控1 FAIL，独审静态确认原循环禁用新的只读按钮；处理器级VM不足以签完整控制交互。f9只保持新的搜索按钮可用，原preview/HOLD/confirm写入保护未解除。补完整控制函数探针后，根最终399/独审最终38均重新运行通过。

## 业务边界

原产品§5.4资源紧张替代时间需求，由本片完成同一已授权SYNTHETIC/LOCAL_AUTHORITY资源时段搜索。固定原时长/数量、显式最多24小时窗口、窗口起点15分钟网格、兜底最多100候选/最早10结果；正时长实际最多96网格候选，未声称触发100扫描截断。空结果仅覆盖所查网格。复用当前READ/租户scope/共享锁/DB时钟/峰值容量/双侧与历史buffer/开放时间，无占用者、原因、hold ID泄露，无业务写入。

选择仅填表清旧预检；仍须重新预检、明确占位与确认。真实冲突→后续建议→原占位确认成功，以及建议后被其他人抢占导致原提交拒绝均验证。未新增产品Grant或真实权限，未改main/dev基础分支、未部署、未接管其他写入者、未用真实模型或registry/旧受限证明链。

保留原 `data: ERR_BLOCKED_BY_ADMINISTRATOR`，本轮完全未启动浏览器、未换URL重试。NodeVM是离线DOM/fetch替身，不代表真实浏览器、Windows、多worker、全AT或完整F2通过。功能说明见 `docs/F2/ResourceAlternativeTimes.md`。
