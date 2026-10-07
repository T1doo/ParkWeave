# ENG101 演示指南集成与诊断类方法兼容

本提交集成外线 `1ae3f528f6180b632da903c2a408201db9a6fc6e` 的五个体验文件，并将指南基线更新为 ENG100 `9ab3c06567ec4d3ff2bcd8152008ba46c39089a5`。操作卡补充独立新 Case 显式材料复用与本人新诉求/人工核对要求，修复 320px 长 hash 溢出。产品 API、数据库及网页业务源字节保持 ENG100 基线；事实确认模块在另一个工作树联调，尚未签收。

实际浏览器最终 **1 PASS / 82.39 秒 / 24 图**：操作卡 9 图与既有 ENG099 恢复流程 15 图。操作卡经固定只读 localhost HTTP，1200/390/320 无水平溢出、12 个原生复选框清空/刷新、打印按钮与打印 CSS、无凭据字段/外部网络请求均核对。当前 managed Chromium 的 file:// 打开被管理员策略阻止，未更改策略，不能声称 file 打开通过。首轮策略阻止、打印 harness 误触发及实际移动端溢出失败均保留。

产品实际恢复采用原合成 UUID fixture，在浏览器开始前通过原入口建立两份 Case；不证明普通用户冷创建。浏览器开始后无 setup 业务写入，五步稳定 IDs、材料 prepRev6/12 与两代独立回执 v1、原执行者新 ACCEPT/提交核对、本地重开/重验/关闭均完成。七项权限表 hash 不变，最终 Case WAITING_CONFIRMATION。指南中的可选 ENG100 材料复用此轮只验证展示；实际复用业务证据属于既有 ENG100，不与此流程拼接计数。

新增 unittest 类测试使既有诊断白名单顶层函数精确匹配失败，首轮差异测试 **101 PASS / 1 FAIL**。现修复 schema1 精确 file::Class::method 支持，可信 AST 仅模块直属函数/类直属方法，JUnit 仅同模块精确类名；保留旧函数行为。最终差异测试 **107 PASS / 0 FAIL / 1 WARN / 4.45秒**。全量 collection **2194 项 / 79 文件**，四片 **540/549/540/565**，1005 个诊断 IDs；ENG100 原2183精确 keys 全保留，预算与 workflow 不变。此次未重新运行完整 Linux；既有2174 PASS/9 native SKIP是历史完整证据，不与107差异结果相加。

原外线历史说明保留在 `docs/demo/evidence.json`；当前实际机器证据见 [integration-evidence.json](../demo/integration-evidence.json)。普通推送和首次精确提交 HEAD 的 Server CI 终态由运行时同步记录，不预写通过。F1未签收/F2仅并行探索、Server非Win11、正式42项AT/EX仍NOT_RUN、R4关闭/模型预算0，不自动资格判断或外部履约。
