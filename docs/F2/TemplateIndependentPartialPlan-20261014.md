# 模板新事项的独立部分办理

接续交付 `c09d3cd447789876edb0abe58a8af0bca2f800dc`，对照原 [V1 产品设计 §5.2](../sources/V1/平台产品设计%20(2).md) 和 [原事项独立部分合同](IndependentPartialServicePlan-20261013.md)。源码冻结为 `cdfc8047e88ab7afd18a793eb294afae8933e32b`。沿现有正常开发分支 `dev/f2-worklist-entry-isolation-20261013` 交付，生产发布不在本片范围。

模板新事项页现在允许选择明确的独立机构审批目标，标示为目录无能力、待人工/新服务；该选项没有进入注册服务能力目录。模板强制目标和全部已保存目标保留。页面逐项显示完整预览、可独立采纳步骤、等待依赖及人工目标，重新 GET 核对同一主体、实例、Case、Run、资料和诉求版本、嵌套预览及来源 SHA。用户必须勾选部分确认并填写明确原因，原 ADOPT 才提交 `partial_adoption:true`。整体始终 PARTIAL，不宣称机构审批、正式受理或整体完成。

原附加条件继续作为全局要求；没有可将地区、期限等未知全局要求改名成独立目标的自由输入入口。原 UPDATE_REQUEST 历史条件仍进入来源证明，清空当前表单也不能解除其阻塞。后端保留 `unadopted_only=True`、模板强制目标、未决阶段隔离和原 parent/key 锁；既有计划只能进入原办理入口，不能通过模板命令覆盖。

新增 GET `/api/template-consumer/instances/{id}/planning-recovery`，以 Idempotency-Key 给定外部原采纳键。服务端逐次核对当前 READ/PREPARE/EXECUTE、企业owner、数据库/实例、候选来源及专员权限；验证不可变 consumer request 指纹、阶段请求键与正文 SHA、完整规范 ADOPT 参数、强制目标，以及原 preparation/Run 的精确 ADOPT 回执。等待后重核权限。成功 GET 不发送 ADOPT、不修复日志，不写业务表或审计观察；当前403拒绝可按原权限路径写拒绝审计；测试包含业务及授权审计全表快照、consumer 三表快照。

同参 CONFIRMED 键保留原幂等结果，异参冲突。已有 ADMITTED/STARTED/UNKNOWN 键明确拒绝再次 POST，其他键也不能替代未决采纳。页面在首次发送前保存有界不透明句柄，只存主体摘要、UUID、原键、版本、SHA和部分确认标志，不存会话、原因或材料正文；存储失败不发送。成功或丢响应后，只 GET 原键核对。精确 COMMITTED 回执才开放原办理入口，句柄保留供冷页重新核对。未知、不提交旧来源、拒绝、句柄缺失或损坏均保持未决，不自动重发。当前最多八个恢复句柄，容量满时明确阻止新采纳；本片未提供清理或未知结果结束流程。

独审发现并修复了成功 GET 后的页面阻塞：只读日志仍 UNKNOWN，旧渲染会重新制造无效句柄。现在仅凭本次精确原阶段键回执放行；不改日志、不删除冷恢复键。另一实例/身份的迟到响应被丢弃，当前403清空私有页面并保留恢复句柄。

冻结源码根回归：**200唯一 PASS、0 FAIL/ERROR/SKIP、2 WARN，143.420秒，exit0**。八模块覆盖模板消费/规划/兼容与原页面、原部分计划/目标扩展和全部注册步骤。真实 owned PostgreSQL 的既有 parent 锁竞争、同异键竞争、未选步骤及资源/分派/receipt/本地生命周期守卫也在本窗口中。独立验收另窗 **42唯一 PASS、0 FAIL/ERROR/SKIP、2 WARN，39.366秒，exit0**，不与根或历史窗口加总。224项冻结文件哈希一致。

根及独审均实际运行原完整 HTML NodeVM → ASGI → owned PostgreSQL：**31断言、23次页面HTTP，审核确认桥额外4次HTTP，共27次，一次ADOPT、一次真实服务端提交后丢响应**。两次冷页 GET 原键恢复后接原模板事项链接、原审核/企业确认、P1明确核验、逐目标结果与工作清单，P1 LOCAL_OUTPUT_VERIFIED，机构审批 UNSUPPORTED，整体 PARTIAL，全部权限快照不变，无分派、receipt或本地关闭。独立页面另有五模式47断言：冷恢复、迟到GET、当前403、损坏句柄、存储拒绝；这些页面守卫不代替后端权限验收。

失败原件均保留，见 [结果索引](evidence/template-partial-20261014/results.json) 和 [脱敏导出哈希](evidence/template-partial-20261014/sanitized-exports.json)。首红验2 FAIL证明旧实现未知结果再次POST和缺少GET恢复。第二窗26 PASS/7 FAIL是离线夹具缺少actor_ref，补齐身份绑定字段、保留全部原断言后8 PASS。扩展窗12 PASS/4 FAIL是测试直接修改正文/键被既有不可变触发器阻止，改为断言持久防护拒绝和GET结果，另保留Run绑定错误409验收。实际链首窗16 PASS/1 FAIL为Python尾部误把投影state当持久字段，页面31断言已通过；修正为coordination_state和verified_sha256后冻结窗口通过。一次八模块命令误列不存在的test_template_consumer_offline.py，exit4/0测试，明确NOT RUN；随后核真实模块并完成最终200项。独审首存储拒绝测试失败是其夹具残留旧句柄，修正夹具后五模式通过，首日志和脚本说明均保留。公开导出仅脱敏生成fixture会话repr行，私有原件及原始SHA保留，不修剪证据空白或失败统计。

浏览器 NOT RUN：保留历史 Chromium `data:` 导航 `ERR_BLOCKED_BY_ADMINISTRATOR`，本任务未启动或重试浏览器。真实模型/付费调用、生产迁移/部署、安全prepare均NOT RUN。未修改main、F1、原F2、registry或两份host_case_once审批文件；审批仍false/null/null，SHA256 `c5ad0c6c38daa921479972d864e9f2da5478bfeead0acec034f1758305f8a69a`。

下一片可独立处理原键的明确非提交结果结束流程及有界句柄清理，或扩展其他明确的人工目标合同；不能通过隐藏/删除未知全局条件或自动重发来解除未决。

归档补件：独审 actual-chain.json 由已归档 frozen-review.json 的 actual_chain 以 indent=2、ASCII转义及末尾换行恢复，7808字节、SHA256 `dfb0685e68a260e2787f374659f7a35c04c1a6767debdcbbf540b9aaca5aaf61` 与原索引完全一致；未重跑或改造原链证据。
