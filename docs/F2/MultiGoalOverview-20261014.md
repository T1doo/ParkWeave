# 同 Case 必需目标总览与精确只读跳转

基于原产品 §5.2、§5.5及已签收 `d7f6fb10fc99c06f4b8f6a306820e3e99d7ca644`。冻结源码 `13de6b8f0496194a59da16f961025507efea4463`。本片完善企业 owner 同 Case 多目标总览；Case 仍未完成，原 UNSUPPORTED/PARTIAL 保留。

复用原 goal-results 与当前计划合法 manual_goal_requests.view，逐目标展示支持结果、人工状态、责任人／待接续角色、来源阻塞和精确入口。未请求目标不自动申请；等待再次接续时责任人仍为空。owner 原读取授权保留，专员及跨租户 owner 无法借此读取私人目标。每行 result_sha256 是本次投影一致性摘要，不是授权证明。

点击先 GET 原总览，核当前 Case/Run/plan、计划／资料／诉求版本及所选行摘要；人工入口在渲染前另核目标、状态、人工 revision/source。原分派及本地关闭读取仅补 Run／资料版本定位字段。P1资料、P2资源关联、P3分派、P5本地关闭跳转原只读入口；P4尚无实际接单时明确阻塞，不伪造 receipt。

总览代次与跳转代次独立；同一总览 B 请求迟到也不能覆盖随后 A。刷新、实际换计划、权限撤销和来源改变会丢弃旧响应。caller 检查传到原 preparation 辅助链，每次等待返回后重核，旧 readiness 请求不能继续清空新目标面板。只释放已失效调用者的人工读取 busy，保留新草稿和原 key 恢复句柄。每次 GET 是当时投影；不保证之后来源永远不变，真实写动作仍依原当前权限／版本核验。

冻结验收根17模块 **472 PASS、0 FAIL/ERROR/SKIP、2 WARN**；独立真实 PG/API 与原完整 HTML 检验 **6 PASS、0 FAIL/ERROR/SKIP、2 WARN**。根15个 NodeVM→实际 ASGI→owned PG 页面窗包含在472项内，独审3页面窗包含在6项内，不重复加总。独审覆盖精确B、人工迟到、P1辅助迟到；P2–P5由根专项实测，不宣称独审执行。详细模块数、耗时、请求计数见 [validation.json](evidence/multi-goal-overview-20261014/validation.json)，独审范围见 [review.json](evidence/multi-goal-overview-20261014/independent/review.json)。

原合成 owner/reviewer 使用 template-new-enterprise-a／template-new-reviewer-a，拒绝矩阵含 b 主体。正向读取比较11业务表、授权审计及 Grant；根另比较9资源表当前夹具（允许为空），不宣称完整预约容量验收。页面请求全部 GET、0 POST；测试桥的明确 setup／换计划／撤权动作另行标记。无自动提交、新 Grant、资源释放、通知、模型调用或 Case 目标推进。

先行红窗2 FAIL（缺少逐目标人工责任元数据、点击B打开A），原 log/XML/exit 保留。初始红窗 page-chain.json 被首轮绿窗同名覆盖，未保留；当前同名文件是绿窗，不能用于红窗原件。其它开发窗口分别保留，不与冻结成绩相加。导出索引记录原件及导出 SHA256／字节，合成夹具 session repr 在 log/XML 可脱敏；原失败文本其余保留。509源码文件前后零漂移，两原 host_case_once approval SHA256 均为 c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a。

浏览器历史 ERR_BLOCKED_BY_ADMINISTRATOR 与 prepare Forbidden 持续停止，无替代重试。浏览器、prepare、全仓测试、Windows/native、部署、生产迁移及真实／付费模型 NOT RUN。没有扩大安全权限或改配置。源码和报告 diff 检查与失败证据原文的空白警告分开记录。

下一步仍需按原产品逐片验证其它尚不支持目标的人工履责与业务完成证据；本片不宣称完整 Case 生命周期完成。

归档独审结论 PASS_WITH_EXPLICIT_HISTORICAL_EVIDENCE_GAP：53项索引原件与导出全部SHA／字节匹配，无未决源码或hash问题；初始红页链缺失已明确披露。全归档 diff-check exit2仅为red.log／red.xml六行原pytest尾空格，源码范围与报告检查exit0。[归档独审原件](evidence/multi-goal-overview-20261014/archive-review.json)在53项索引之外单独附上。
