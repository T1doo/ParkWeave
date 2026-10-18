# 普通步骤成果接入原计划核验与事项核对包

本片完成显式 `CURRENT_PREPARATION` 普通入口的 P3/P4 成果接入。已有合法 SYNTHETIC 资料事项的真实接单、人工提交及经办人核对，可经原持久计划的显式 VERIFY 进入原 goal-results 和原事项核对包。完整项目、真实业务运行及 P5 生命周期均未完成验收。

受测产品提交：`33aef7ab8f297c52bbb15d1ae0930ac33a253d7e`；`src` tree：`6ad4c25a8f230cbf3effbe2530ecf59f8c2e6bcd`。基线为已接受的 `5e657633ea9b132f994a7a5ed4e35e9556100a2d`，实际祖先包含最初指定的 `db1084100a2477bbff3da8b49287c755dbc83c1b`。分支：`dev/f2-ordinary-case-goal-results-20261018`。交付提交仅在受测提交后添加本报告及证据；完整交付 SHA、推送与最终远端差异以私有 `.runtime/ordinary-case-goal-results-20261018/delivery-and-remote-verification.json` 和最终答复为准。

原方案依据与边界见[合同](OrdinaryCaseGoalResultsContract-20261018.md)。原产品设计 §5.4/§5.5 要求步骤交付物、验收要求、实际材料与责任接受/回执核验；原分阶段计划 F2 T02/T04/T07 要求覆盖、角色回执、完整记录和持久刷新。材料文本包、事项核对包及源码 ZIP 已存在，本片没有重做它们。

**实现与实际行为**

- 工厂/显式 create_app 的精确普通服务提供同 Store 的来源依赖；marker 仅作证明材料，不选择权限路径。默认入口与旧隔离入口保留原拒绝行为。
- 原 P1/P2、ADOPT、依赖失效、owner VERIFY、ACCEPT→CREATE、回执版本及 SUBMIT/ACK 事件校验继续使用。普通 P3/P4 来源额外验证原 OFFER 指纹、既有角色和授权 generation、当前材料/目录、固定 UUID 与首次不超过 300 秒的绝对期限。没有新 Run READ、身份、Grant 或批准接口。
- 事务末尾在所有锁等待后复查真正使用 P3/P4 的来源；过期不能提交 VERIFY 或返回假当前结果。仅 P1/P2 的目标不继承无关步骤的期限。已有任意 active/inactive Run assignment、Native 痕迹、旧隔离 marker、损坏证明及混合 provider 均拒绝。
- 合法历史在期限或权限变化后保留原核验引用，P3/P4 不再当前，当前产物不导出。全部目标、未知目标、PARTIAL 和 P5 未满足状态保留；`case_goal_completed=false`。
- 当前预览显示普通受限步骤的范围说明，避免把原注册合同的 Run 字样当成已授予 Run 读取权。原 REGISTRY、历史 ADOPT 合同与来源指纹保持原样，核对包继续明确历史来源和导出局限。

54 个选定保护文件与基线逐字节相同，包括 Store、权限 SQL、原资料/分派/回执、worker、Native/runtime、迁移和 conftest；原合同、编排、事件、恢复及成果证明的 18 个选定 AST 对象也相同。原 CaseStep 业务算法没有重写。继承的 F2 evidence 对基线 Git diff 为零；没有把这项检查称为全部旧证据重新 SHA 扫描。

**实际测试与失败保全**

最终提交的根窗口：34 collection/setup/call/teardown/JUnit 全部 PASS，0 FAIL/ERROR/SKIP；26 个新 selector、8 个定向旧回归。pytest 298.41 秒，外层 301.77 秒。独审有效 8 个 selector（5 自有、3 与根重叠），并集 `34+8−3=39`；不重复计入此前 54/69/129 等矩阵。

| 窗口 | 实际结果 | 用途 |
| --- | --- | --- |
| `163e1f79…` 根 / 独审 | 32P / 5P3F | 原件保留；1 个产品 P2、2 个独审断言错误 |
| `8e7e5b6e…` 根 / 独审 | 34P / 8P | P1/P2 回调范围修正后验证，仍是历史提交 |
| 最终 `33aef7ab…` 根 / 独审主窗 | 34P / 7P1F | 最终主窗的原失败保持不变 |
| 最终提交独审唯一补窗 | 1P | 只补同一失败 selector，原请求/18 秒期限/2 秒启动参数/断言/权限不变，仅增加只读 POST 响应观察器 |

最终独审主窗的失败是未观察到预设的末锁等待；原测试没有保存该次 HTTP 响应，业务结果保持 UNKNOWN，不能用补窗反推或把原窗写成 8P。唯一补窗实际观察到 PG 锁，原最终 POST 从 `18:33:27.165858` 至 `18:33:29.303308`，跨原截止 `18:33:29.128176+00:00` 后返回 403，计划版本不变，无时钟偏移。之后没有再次业务重试。

原产品 P2 是仅含 P1/P2 的结果错误地继承普通步骤到期回调，末锁跨期时返回 403，而初始/刷新结果均当前。修正把期限回调限定到实际 P3/P4 消费者；根新增 P1-only/P2-only 的真实末锁测试，独审原字面反例验证通过。两条私有断言修正分别保留允许的 owner 原诉求，以及把负向撤权后的业务快照作为比较基线；v1/v2 probe、exact diff 和原红窗均保留。

开发窗另保留：一次生命周期测试路由误写 404；一次工作区 PG 临时路径不满足原 `/tmp` 夹具前置拒绝；一次 HTML 测试未为第二次 VERIFY 重填理由；两次末锁探针使用没有 UPDATE 权的 preparation_events，未达到等待观测前提，原 HTTP/异常结果未保全。后者改用原本允许更新的 operations 行，未修改 roles/conftest 或任何权限；不能把未保全的旧响应推定为特定状态。开发窗不冒充冻结结果。

最终根、独审主窗及唯一补窗的 803 项 Git 输入，shared/mirror PRE/POST 四图均相同，亦跨双方相等。根 114 个模块来源全部命中冻结镜像；独审主窗 114 个来源为 113 冻结输入加 1 私有 probe，补窗 112 个均命中冻结输入。子 API 未另设 import hook；其证据限于固定镜像 cwd/PYTHONPATH、普通 factory 和健康检查的实际 PID。不能声称全部子进程 import 都被单独观测。

根的四个真实末锁场景：P3 VERIFY 和结果 GET 跨期 403 且不增加核验事件；P1-only/P2-only 的无关步骤跨期 GET 200 且结果相同，均使用 DB 实际时钟。

**可复核交付物**

三个真实普通 API 进程依次完成原完整 HTML 的 owner P3/P4 VERIFY、原生成/下载按钮、冷启动 GET，以及合成执行者 READ 撤销后的降级。Node VM 仅提供 DOM/Blob 机械表面，调用原页面和真实 HTTP/PG；61 个页面断言，绝不称为正式浏览器。生成和下载各用原两次新鲜 GET，不自动写入。此片新链没有另起 worker；此前已接受的 worker 重启链不重复计数。

- [原实际下载 TXT](evidence/ordinary-case-goal-results-20261018/runtime/frozen-33aef7ab/process-artifacts/test_normal_process_original_h0/first-html/download.txt)：12,674 字节，与冷启动 TXT 逐字节相同；整文件 SHA256 `52b6198c2b57fc12020ee6a8d62e87310c61cb22ced2eb5a6d0cdaad8ebddcca`。
- 包内规范化数据 SHA256 `f909cdd4128968f582ebd1115d8bc67df8da478706098bb4a9cdc51175b802dc`。撤权后的包为 UNVERIFIED，保留全部目标和旧核验，P3/P4 当前产物为空。
- [根计数/来源核对](evidence/ordinary-case-goal-results-20261018/runtime/counting-verification-33aef7ab.json)、[最终跨窗计数](evidence/ordinary-case-goal-results-20261018/runtime/final-cross-window-verification.json)、[进程与末锁证明](evidence/ordinary-case-goal-results-20261018/runtime/process-and-last-lock-verification.json)。
- [独审 v3 报告](evidence/ordinary-case-goal-results-20261018/independent/independent-final-review-v3.json)、[完整原→公开影子配对](evidence/ordinary-case-goal-results-20261018/raw-public-redaction-map.json)、[归档验证](evidence/ordinary-case-goal-results-20261018/archive-validation.json)。所有 XML 实际解析并核对原 testcase/outcome；仅脱敏自有合成会话及截断片段，独审 canonical 影子照拷，不再次改写。原始日志留在私有 runtime。

首次归档扫描把一个 23 字符的已知合成专员名称片段误判为会话片段；29 个命中均为同一已知身份名称。首轮 457 个部分公开文件及逐项 hash、原脚本、stdout/stderr 和诊断保留在私有 runtime。仅排除精确的已知合成身份名称后重新归档，不改测试或独审 canonical，也没有把原扫描失败写成成功。

最终归档 465 文件：462 个原→影子配对加 3 个控制文件；448 对逐字节相同，14 对影子字节变化，共 26 处会话脱敏替换。全部配对 hash 命中；1,250 个自有合成会话的全值/16 字符前缀及截断片段扫描均为零命中。独审 v3 报告 SHA256 为 `9d964976bc45308069366446d11257e396ba3b1cafe0bf83909ecf51b8085ce2`。

**真实运行仍缺的明确输入与代码**

普通启动目前只消费已有合法 SYNTHETIC 资料，不初始化真实身份/目录/授权。需要预装 schema 32/33、既有受限 DB/DSN 与 LOCAL 配置；API/worker 的显式普通模式；当前有效企业 owner 会话与 READ/EXECUTE/PREPARE；原同域 reviewer 的 READ/REVIEW_ASSIGNED；原同域 executor 的 READ/正确角色；精确 SYNTHETIC preparation_catalog 及合法来源；原成功 Case/Run、两项有来源材料、当前人工 REVIEW/CONFIRM；P2 还需既有资源目录/规则、READ/HOLD、有效组合和关联。任意既有 Run assignment/Native 痕迹会使普通接入拒绝。新建 Case 另需既有 case.create 动作和相应字段权限。以上没有在真实环境补建。

这不只是“用户缺权限”。`cli.py` 只有 migrate/seed-synthetic/revoke/revoke-field；seed-synthetic 仅调用企业合成初态 Store.seed。专员、PREPARE/REVIEW_ASSIGNED 和资料目录由 `preparation.seed_synthetic` 明示 fixture-owner 初始化，执行者/资源角色及 READ/HOLD 也仍在合成测试 setup。面向获授权管理主体、真实主体映射、目标清单、合法目录来源的受审管理初始化/配置流程还缺；真实服务运行契约及既有安装边界未完成。本片没有把这些 fixture 当作普通批准，也没有新增真实身份、Grant、分派、目录发布、批准或凭据。

其他原预检/模板替换/生命周期组合未纳入本片普通办理验收。没有修改 main、强推、部署、真实模型调用、新费用或安全网络权限，也没有重试既有安装/Chromium 拒绝或删除未知锁进程。正式浏览器、Windows、正式 AT35 和真实业务场景仍为 NOT_RUN。
