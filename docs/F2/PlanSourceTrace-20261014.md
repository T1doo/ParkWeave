# 原多目标总览的已采用方案来源追溯

基线 `165d1155490f887ac18476f9461d3d2d030e3286`，源码 `5fe302052682d54c9ec38751068e4a11f9f00687`。沿原产品§5.2、§5.5、§7.1、§7.3及F2-T02/T07，企业owner在原同Case多目标总览显式读取此已采用方案的原来源。provider关闭，没有真实/付费模型、服务注册、目录发布、Grant、schema或业务动作新增。

复用原`goal-results` GET的READ/PREPARE、原owner与Case/Run/租户范围。新增source_trace及每个目标的adoption_trace_sha256，来源投影绑定当前计划UUID/修订、原首ADOPT事件ID/指纹、原资料与诉求修订、source/catalog/registry摘要、原完整必需目标，以及实际采用的稳定步骤编号、依赖、责任、产物和验收。候选方案附原candidate ID/摘要/validator版本/accepted_at/期限；原无候选的确定性方案明确标识，不声称曾模型生成。

暴露投影前重核原首ADOPT及候选消费证明，不能借目标读取旁路绕过被删除/损坏的原请求、候选、消费时间或事件证明。V1历史按原摘要核对，不补造期限。source_trace是原采用事实，不代表当前资料、容量、授权、目标交付仍满足；已采用候选后来过期不抹掉历史，资料变化后当前结果仍保守重验。方案替换的当前trace只来自新计划，旧候选、原事件与原history保留；不把旧候选来源继承到新的无候选方案。

原页面增加“只读追溯此已采用方案来源”按钮，显式GET原总览并复核当前Case/Run、资料/诉求/计划版本、页面代次与精确trace SHA，然后显示完整来源与步骤。新目标/新方案/刷新后的迟到回复不覆盖当前视图或草稿；403沿原清理边界清私有，原请求句柄保留。读取前与返回后都检查原未决写，拒绝在材料、资料复用或其它原写入仍待核对时渲染迟到来源；403处理优先于第二次pending检查。实际办理仍走原步骤入口与原角色明确命令。

开发红验7FAIL记录缺字段和旧候选证明旁路，属实现前加载旧API的开发窗口；源码在开发期间推进，非冻结验收。首次相关开发109PASS，尚未覆盖独审发现的迟到材料写竞态。随后完整原HTML→实际ASGI→owned PG红验1FAIL复现：source GET响应延迟递送后，原ADD_EVIDENCE已commit、其ACK仍SUBMITTING，迟到GET错误渲染旧来源。修复返回后的pending重查，绿验1PASS；各窗原件保留，不和最终结果拼合。

原页面21项候选场景含6项追溯trace、trace_expired、trace_late、trace_revoke、trace_plan_switch、trace_pending_material。材料竞态页面真实POST分别为候选201、原ADOPT201、原ADD_EVIDENCE200，随后原资料readback结束；这是原HTTP在途响应交叉，不是另一项PG锁等待验收。方案替换/期限/撤权的桥接操作为明确自有夹具或时钟故障注入，与页面操作分别记录。页面为完整HTML脚本NodeVM→真实API/PG，非浏览器视觉验收。

独立精确源码审查最终 **21PASS、0FAIL/ERROR/SKIP、2WARN、16.211秒、exit0**，含8原创API/PG、7明确复用trace测试、6原页面，页面包含在21中。45public表全列快照比较不变，authorization_audit单列；原EXECUTE撤销但READ/PREPARE保留时原采用历史可读，三类证明破坏409、V1精确格式、材料/expiry历史稳定和无候选替换来源隔离通过。515源及两原approval零漂移；资料竞态独立复验通过，无剩余增量源码缺陷。

历史浏览器ERR_BLOCKED_BY_ADMINISTRATOR和prepare Forbidden持续停止。浏览器、全仓、native Windows、真实/付费模型、生产迁移、目录发布、部署NOT RUN。不签收完整PR0/T02/AT07/AT14/AT35、真实资格/机构受理/履约或通用DAG。登记闭包相同仍显示相同实际依赖，不为演示削减目标或伪造结构差异。

冻结最终主测9完整相关模块 **252PASS、0FAIL/ERROR/SKIP、2WARN、188.829秒、exit0**；根21候选页（含6追溯页）与26既有总览页均在252中，独审6追溯页在21中，分别统计不相加。515源首尾零漂移，twoapproval原哈希不变。详见[validation](evidence/plan-source-trace-20261014/validation.json)、[独审](evidence/plan-source-trace-20261014/independent/review.json)与[原/导出索引](evidence/plan-source-trace-20261014/export-index.json)。原开发7FAIL、材料竞态1FAIL、109PASS及单例1PASS分别保全，最终冻结结果不覆盖旧失败。

本轮11项既有403/迟到页面驱动使用原默认evidence目录，最终窗更新了同名阳性链；已复制到本轮denied-pages并记录[收集范围](evidence/plan-source-trace-20261014/page-collection.json)。此前公开冻结归档未改，旧默认路径阳性raw被更新，不声称所有历史runtime原件均保持；失败log/XML原件未覆盖。后续运行需设置该驱动已有OVERVIEW_DENIED_EVIDENCE环境参数到本轮目录。

源码与报告范围git diff-check各exit0。初次stage的102项原件归档cached diff-check为exit2：pending-red log/XML各三条原pytest `E`空白行有尾空格，共六处；按用户原样保留失败要求不改这些字节，不把它说成产品测试失败或格式全通过。检查完整原输出和范围见[diff-check](evidence/plan-source-trace-20261014/diff-check.json)。索引新增三件检查原件，共105exports。

补充三件检查原件后，105项最终stage的cached diff-check仍exit2，共12处：原失败log/XML六处，加检查日志逐字引用的六处。首归档审查HOLD指出此前报告把102阶段输出当成105当前范围，已纠正描述与metadata，不改失败/检查原文。最终12处stdout仅在私有runtime保全，不再导出再次递归产生空白引用；源码与报告仍exit0。

最终[归档复核](evidence/plan-source-trace-20261014/archive-review.final.json) PASS：105项哈希/字节/精确原文、源515及统计核对一致，格式检查仍按上述exit2记录，无增量源码阻塞。[首格式HOLD](evidence/plan-source-trace-20261014/archive-review.hold.json)保全，两审查文件在105索引外单独附上。
