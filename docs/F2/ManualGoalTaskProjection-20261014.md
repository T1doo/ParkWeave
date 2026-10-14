# 当前人工请求进入原个人待办

在已交付 c0942765eaa0bf63eecd96352c38075215b52580 上，原个人待办排除了 LOCAL_CONFIRMED，已确认事项的人工请求和企业补证责任因此不可见。本片源码冻结于 `7f0709b184dc4793e92f68b52969fd6d58066a30`；未改 main、F1、原 F2。源码到证据交付只增加文档证据。

`GET /api/preparation-tasks` 保留原企业 PREPARE／原专员 REVIEW_ASSIGNED 范围及 READ；按当前计划合法 ledger 和统一隐私 view 投影：原专员等待接责、继续人工核对，企业等待补证。LOCAL_CONFIRMED 只要有当前人工 ledger 也能参与检查。从未 REQUEST 的私有目标、WITHDRAWN 和旧计划历史不进入当前人工待办；历史原键恢复仍走原接口。损坏分享证明时原专员不见目标，原企业仅见记录待核对。

当前来源已变、材料引用不完整、撤销／核对中、本地关闭、历史上限或企业撤写权仍明确显示办理阻塞；列表不授予操作权。目标仍 UNSUPPORTED，整体 PARTIAL，Case 目标未完成。没有通知、自动接责、自动补证、外部受理、Grant、registry、迁移或新增服务能力。

默认每页检查100件事项；新增1–100界限及按创建时间／ID的前向只读游标，游标按原主体范围核对。检查件数与每目标待办数区分，明确提示还有更早记录，翻页不宣称全量。事务在授权前设为 READ ONLY；原页与 owned PG 对照验证 GET 不改业务记录及 Grant，不触计划隐式失效写。

点击仅只读重新核对原 Case、Run、计划 ID、人工 revision、来源 SHA 和当前目标责任，再由原人工表单明确操作。旧列表／身份／迟到响应均丢弃；token input 立即清空旧私有待办。未知原写句柄先由原入口守卫阻止跳转；列表读取不会清除未知写恢复状态。403保持原拒绝，不修复授权。

## 验收边界与失败保全

真实原 API 创建、采用部分计划、REVIEW／CONFIRM、REQUEST／TAKE／REQUEST_EVIDENCE／SUPPLY_EVIDENCE 及实际换计划；完整原 HTML 在 NodeVM 使用真实 ASGI 和 owned PostgreSQL。仅分页压力夹具的100件空 legacy 记录为规模克隆；另有4件真实 API 创建的独立 Case 验证游标，不把克隆计为业务验收。

开发红窗：确认事项当前人工请求在旧列表丢失，1 FAIL。后端两绿窗各32 PASS，属于冻结前窗口。原页前三窗各1 FAIL：第一次测试误把换计划后的合法 legacy REVIEW 当人工待办；第二次发现真实 token input 旧列表文本清理缺口；第三次 VM 测试表达式误引用未注入的 B 常量。分别修正测试、产品和测试，原 log/XML/exit/链路保留，第四窗1 PASS。事务 READ ONLY 独立开发探针1 PASS。开发窗口不与最终统计加总。

历史 Chromium data: ERR_BLOCKED_BY_ADMINISTRATOR 与 prepare 元数据 Forbidden 持续保持停止；本片浏览器、prepare、部署、生产迁移、真实／付费模型 **NOT RUN**。两份原 approval 保持 false/null/null，SHA256均 c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a。

最终结果与机器证据见下方验收记录；只说明本片实际运行范围，不宣称全部旧365项或完整Case生命周期均重验。

冻结根10模块 **222 PASS、0 FAIL/ERROR/SKIP、2 WARN、173.020秒、exit0**；独立真实PG/API **8 PASS、0 FAIL/ERROR/SKIP、2 WARN、8.384秒、exit0**。501文件前后hash零差异。原完整HTML **34断言PASS／24HTTP／3明确POST** 包含在根15项新待办用例中，不与222或独立8加总。

根运行模块及数量：

- `tests.test_manual_goal_tasks`：15
- `tests.test_preparation_tasks`：19
- `tests.test_manual_goal_requests`：25
- `tests.test_manual_goal_privacy`：11
- `tests.test_case_worklist`：17
- `tests.test_case_worklist_offline`：21
- `tests.test_template_full_chain`：4
- `tests.test_service_case_steps`：68
- `tests.test_template_consumer_planning`：25
- `tests.test_template_partial`：17

[原始证据导出索引](evidence/manual-goal-tasks-20261014/export-index.json)，[冻结验收统计](evidence/manual-goal-tasks-20261014/validation.json)，[独立审查](evidence/manual-goal-tasks-20261014/independent/review.json)。开发失败原件保存在.runtime；导出仅脱敏夹具会话repr，保持失败统计、文本和空白。下一步应由当前授权范围继续验证人工后续业务边界；本片没有实现目标完成／资格批准或首次接单后的撤销。

源码和报告空白检查 PASS；证据归档空白检查 exit2，仅原 pytest 失败 log/XML 的尾空格，原样保留，不修改失败原件来消除告警。

归档只读独审 PASS：44件原件／导出SHA256和字节数一致，逐行核对仅夹具repr脱敏；统计、失败保全、报告范围与501源码hash一致。审查原件保留 `.runtime/manual-goal-tasks-20261014/independent/archive-review.json`。
