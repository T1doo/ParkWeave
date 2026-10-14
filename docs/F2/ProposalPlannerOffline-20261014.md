# 默认关闭的离线 JSON 规划候选闭环

基线 `f3235b3b623af9521940bf5718756480392c3fa2`，冻结源码 `a60c83c5cfc5b037c607f6f192f840dfdde42783`。独立开发分支 `dev/f2-worklist-entry-isolation-20261013`；普通交付仍核远端完整 SHA、源摘要及未提交/未推差异。

原候选 POST 只有显式注入 `OfflineProposalPlanner` 才启用本路径，默认应用保持关闭。它只接受现有 `InternHTTPTransport` 包装的精确 `httpx.MockTransport` 和 `OfflineBudget`，没有 provider token 参数、凭据读取或 LIVE 预算路径。原 `InternChatAdapter` 的 case_create 与 `ModelChain` 的执行职责没有转作规划；本路径不调用 ExecutionGateway。

假 provider 的 JSON 是不可信提案。独立确定性解析拒绝重复 JSON 键、额外字段、非 UTF-8/非有限数字、类型替换、目标遗漏、来源变更、未知注册版本、环、缺依赖及硬约束降级。有限范围是完整复述当前独立编译的注册 P1–P5 合同，不能任意创造服务图；UNKNOWN/UNSUPPORTED 原样保留。请求 max_tokens=1024，截断、tool_calls（包括空数组）、异常 usage 或返回身份均拒绝，没有自动修复或重试，不宣称真实模型可用性。

原 key 先在短事务内持久登记 STARTED 和数据库 UTC 首次 900 秒窗口，网络等待不持有 Case/业务锁。发送前与保存时各按原 parent→dispatch→Case 顺序短锁，复核当前 READ/PREPARE/EXECUTE、精确资料/目录/registry 来源、actor/key、原窗口与期限；撤权、来源改变、期限到达不保存候选。保存修改同一锁定 parent JSON 槽，避免更新另一次读取的副本。两个应用实例竞争同 key 只有一次假请求；异参冲突。失败落 FAILED_SAFE，传输未知落 OUTCOME_UNKNOWN；撤权无法写终态时保守留 PENDING，原 key GET 核对，均不自动重发。

V3 请求指纹、原 response 字节、严格提案、实际离线预算 ledger 与首次 attempt/window 绑定；删除全部模型来源也不能降级为 V2。通过后使用原候选预核、明确原 ADOPT 与 goal-results 来源追溯。生成只写规划 metadata，业务快照不变；原 V1/V2 指纹、消费历史及期限行为兼容。既有取消 Case 的写封锁、资源独立释放和历史读取规则继续适用。

原页面标明离线假来源与未执行。PENDING/OUTCOME_UNKNOWN 保留原 opaque，只 GET；FAILED_SAFE 需 GET 核实后清本地句柄，新的生成仍须明确发起。本窗原 NodeVM 页面覆盖正常、生成丢响应冷读、采用丢响应冷读和追溯；失败/未知冷页的完整 NodeVM 交互是下一片，当前 API 状态及并发边界已测。

冻结主测 **510 PASS、0 FAIL/ERROR/SKIP、2 WARN，JUnit 285.645 秒，exit0**，16 完整相关模块。隔离测试另窗 **26 PASS、0 FAIL/ERROR/SKIP、2 WARN，17.735 秒**；独审另窗 **159 PASS、0 FAIL/ERROR/SKIP、2 WARN，22.946 秒**，原页独审另窗 **4 PASS、0 FAIL/ERROR/SKIP、2 WARN，5.237 秒**。各窗不相加；根原 21 候选页、4 假规划页及 26 总览页已包含在 510 内。521 源文件首尾零漂移，隔离加载路径及实际统计见 [validation](evidence/proposal-planner-offline-20261014/validation.json)、[独立验收](evidence/proposal-planner-offline-20261014/isolated-tests/final-review.json) 与 [独审](evidence/proposal-planner-offline-20261014/independent/review.json)。

实际 owned Linux 临时 PG 的锁等待/API 与全原 HTML 离线 NodeVM 已执行，未用 SQLite 或浏览器替代。socket 探针仅为自有 loopback 的真实拒绝，假 handler 将它显式转成 ConnectError；构造门禁 spy 验证零网络 connect，不能据此宣称真实 provider HTTP 验收。实际 provider 请求、provider 凭据读取、LIVE 配额写入、规划路径业务 gateway 执行各 **0**。真实模型、浏览器渲染、Windows/native、完整 PR0/T02/AT、生产迁移/部署 **NOT RUN**。本窗刻意不跑含 LIVE 配额写测试的 ModelChain 模块；原 InternAdapter 23 项回归已在 510 内。

原失败窗保全：隔离开发 8 PASS/18 FAIL，修后开发 15 PASS/11 FAIL；独审开发 2 PASS/7 FAIL，修后 9 PASS；根边界开发 131 PASS/1 FAIL，修后 133 PASS。JSON 副本未落盘缺陷已修；终态 POST replay 返回原 201 的测试 oracle、原 response 空白变更探针的错误 oracle 也已纠正。它们不覆盖冻结结果。全部原 log/XML 保留，公开导出只替换真实临时 SYNTHETIC fixture session；原/导出 hash、字节、替换次数见 [134 件索引](evidence/proposal-planner-offline-20261014/export-index.json)。

开发 legacy 窗未设置候选页 evidence 参数，更新了旧默认路径同名阳性链；原已公开冻结归档及失败 log/XML 没改，不声称所有历史 runtime 阳性件均未变。本轮冻结页使用本任务独立目录。

历史 Chromium `data:` 的 `ERR_BLOCKED_BY_ADMINISTRATOR` 以及 prepare workflow Forbidden 均未重试；两原 approval JSON 的 false/null 与 SHA256 `c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a` 不变。无新 Grant/registry、凭据或权限配置、真实付费调用、主线修改、强推或部署。

源码与报告 diff-check 各 exit0。134 件原件归档初次 staged diff-check **exit2**，40 处原 pytest `E` 空白行尾空格；依原样保留失败要求保留这些字节，非产品测试失败。完整检查 stdout 私有保全，不递归导出产生重复空白引用；[检查 metadata](evidence/proposal-planner-offline-20261014/diff-check.json) 位于134索引之外。

[归档独审](evidence/proposal-planner-offline-20261014/archive-review.json) PASS：134项原/导出 hash、字节及仅38实际会话的127处替换核对一致，源521零漂移、实际统计一致。首 Bearer 扫描误报原 NodeVM `SYNTHETIC_<actor>` 固定占位；核原桥接映射后修正 oracle，[原 HOLD](evidence/proposal-planner-offline-20261014/archive-review-bearer-oracle-hold.json)保全，产品与134导出未改。两审查与重跑脚本在索引外。
