# 已选员工自述来源与原计划采纳

基线：`6dad1e3d6220f4b1a0711afd851ccd8e8b95343d`。唯一共享源码及 Git 集成者为 root；实现、字面 oracle、独测和审查仅在本任务独立私有目录中准备。

本片新增员工人数 `USER_ASSERTED_SYNTHETIC` 已选断言的细粒度 provenance，保留断言引用、原版本、来源摘要、适用 UTC 和原确认决定。具体来源从原 VERIFY/ADOPT 注册描述符精确定位原事实账本前缀，校验原 Declare/Confirm、完整实际 preparation_events 回执。不会用今天的事实补旧历史，不公开事实值和摘录。

原 typed graph schema1/build_v1、source-change v1/v2、人工说明与双槽协议继续原义。明确选择新 scope 才产生独立 source-change v3；随后仍可使用默认旧路径。新路径对尚未建立兼容合同的 MANUAL/双槽/已迁移模板组合明确拒绝。历史、回执或来源不足返回 UNKNOWN、affected 全 Case、preserved 空且 adoption=null。

细节点只解释来源，不缩小原受影响分区。事实确认增加 preparation revision 时仍可能影响 P1–P5；资源变化保留 P1 原锁与证据，回执变化保留 P1–P3。本人须分别完成原事实用途确认、机会刷新、预览、原 ADOPT、原业务补正及受影响 VERIFY，未影响证据和全部六目标保留。

公开 proof 的 receipt_bindings_sha256 是可由原账本确定性重建的原回执语义摘要；fact_provenance_capture_sha256 是当次提交前实际数据库行与 xmin 的短期绑定，不能宣称为管理员签名。结构证明仍沿原系统信任边界。

页面复用原提交互斥、原键恢复和冷 GET；恢复句柄不保存 provenance、事实值或请求正文。机会提示不作为事实或授权；失效、撤回、撤权、迟到、ABA、UNKNOWN 与幂等异参沿原规则拒绝。

冻结源码：`8fe3e6c6ebdb14366dd80032c953c79e746e3fd1`，开发分支 `dev/f3-employees-fact-provenance-20261015`。624 个源码/测试/脚本路径、16505 个跟踪文件及4个冻结运行辅助文件在正式窗口前后哈希不变；交付文档随后在独立文档提交中归档；实际交付提交以远端最终核验为准。

同一冻结源码最终所选集合的 **103 个完整相关模块、2996 个唯一测试 PASS，0 FAIL/ERROR/SKIP**，不是全仓，也不是全部原始执行窗全绿。新片61项已包含在该总数，不能再相加。另 CI 元数据完整12模块：433 PASS/14 原 Windows 或 PowerShell 前提 SKIP；独审38纯测试及其中1pytest内6个受控客户端分支另列，不当作额外端到端测试。

|正式窗口|完整模块|PASS|
|---|---:|---:|
|independent-new|2|52|
|common|18|305|
|independent-prior|1|33|
|additional|2|179|
|root-2|24|759|
|backend|8|254|
|root-1|27|900|
|review|16|423|
|new|4|61|
|recovery-lowload|1|30|

完整模块选择说明：root-2：原完整789项为788P/1F；P5准备核验HTTP200/BLOCKED，目标锁等待未开始，原件缺TTL和阻塞原因。所属完整30项含29P全排除；其余24完整模块759P保留，以全部其他窗口结束后一次同SHA原预算低负载完整30项替代。复验不能证明唯一负载原因，原失败保留。。原始窗计数 {'PASS': 788, 'FAIL': 1, 'ERROR': 0, 'SKIP': 0}；有效分母仅取所列完整模块。

完整模块选择说明：recovery-lowload：一次同SHA、原预算、无其他pytest并行的完整30项复验；替换原完整模块所有节点，保留原失败。。原始窗计数 {'PASS': 30, 'FAIL': 0, 'ERROR': 0, 'SKIP': 0}；有效分母仅取所列完整模块。

同SHA原 root-2 完整789项结果为788 PASS/1 FAIL；失败发生在 test_actual_resource_expiry_during_last_lifecycle_lock_wait_is_read_only 的P5准备核验，返回HTTP200/BLOCKED，目标锁等待尚未开始。原件未记录剩余期限或阻塞原因，不能证明负载为唯一原因。其所属完整30项（含原29 PASS）整体排除，以其他重窗结束后一次同SHA、原命令及原预算的完整30项低负载复验替代；原失败日志/JUnit完整保留，复验通过不抹去原失败。


原命令、完整收集与JUnit、SHA和前后哈希见[正式回归收据](evidence/employees-fact-provenance-20261015/fact-assertion-provenance-root/final-regression-verification.json)、[模块清单](evidence/employees-fact-provenance-20261015/fact-provenance-final-v2/selection.json)和[新片原始日志](evidence/employees-fact-provenance-20261015/fact-provenance-final-v2/new.log)。每窗为整模块执行，收集与JUnit精确一致，主集合不重复。

4 类完整原 HTML 经 native fetch→真实 HTTP/ASGI→自有 PostgreSQL，共 **136 次页面请求**。正向和模拟已提交后丢回执分别只有一次原ADOPT，随后五个不同步骤沿原业务补正后VERIFY、六目标本地证据和原工作清单读取；当前403清私有视图，迟到403经身份ABA保留新Case，两权限流只有GET。Python control通过原业务API办理的附加调用总数未作汇总，不能混入页面请求数。Node机械DOM不是真实浏览器。

|页面模式|实际请求|POST|真实403|
|---|---:|---:|---:|
|positive|39|8|0|
|lost_ack|53|8|0|
|current_403|16|0|1|
|late_403|28|0|1|

新冻结驱动从实际请求提取原 Idempotency-Key 为 request_key，仅用于精确核对原冷 GET 与唯一 ADOPT；不保存 Authorization 或其余请求头。恢复句柄不含事实或正文。旧181冻结没有记录GET幂等键，该旧边界不补录、不套用新证据。[原始轨迹机械核对](evidence/employees-fact-provenance-20261015/fact-provenance-independent/final-8fe/html.json)。

独测实际记录11次字面分区检查，其中3次是预期UNKNOWN；另有5次原断言哈希与日期精确核对。日志条数与设计行数都不能当独立测试数量。

[40行冻结设计](EmployeesFactProvenanceOracle-20261015.json)仍为 DESIGN_ONLY_NOT_EXECUTED；下表是实际原回执映射，分区字面验证、纯拒绝、变体和未执行分开。同一测试可支持多个设计行，行数不能相加当测试数。纯拒绝不证明完整HTTP影响分区。[逐行实际证据](evidence/employees-fact-provenance-20261015/fact-provenance-independent/final-8fe/coverage.json)。

|设计行证据类别|行数|
|---|---:|
|BOUNDED_HTTP_LITERAL|10|
|NOT_RUN|8|
|VARIANT_MULTIPLE_SOURCE_FIELDS_CHANGED|2|
|PURE_REJECTION_ONLY|9|
|VARIANT_PURE_SCOPE_REJECTION_AND_HTTP_REQUEST_DENIAL|1|
|VARIANT_PURE_TYPE_AND_REVISION_REJECTION|1|
|VARIANT_HTTP_UNKNOWN_MALFORMED_LEDGER|1|
|LEGACY_PURE_LITERAL_ONLY|1|
|VARIANT_LEGACY_REQUEST_SERIALIZATION|1|
|VARIANT_CURRENT_ADOPT_AUTHORITY_DENIAL|1|
|VARIANT_REAL_TWO_COMMIT_ABA_BOUNDARY|1|
|VARIANT_COMMITTED_RESPONSE_LOSS_AND_COLD_GET|1|
|VARIANT_ORIGINAL_KEY_PARAMETER_CONFLICT|1|
|VARIANT_NEW_V3_THEN_LEGACY_V2_AND_COLD_GET|1|
|VARIANT_COMBINATION_REJECTS_WITH_LEGACY_PREVIEW|1|

已验证原历史确认/断言身份、同值换源、未选断言及其他字段变化、资源/回执分区、缺历史/回执损坏UNKNOWN、跨租户/owner/角色、撤权恢复、真实两提交A→B→A、受影响原锁明确UNLOCK、幂等异参、丢回执后原冷GET、增强v3后默认v2及MANUAL/双槽组合拒绝。未独立执行的设计变体继续保留，不宣称通用语义理解或任意传播。

开发与首冻结原件全部保留：纯历史/receipt校验及scope降级修复、机械驱动漏接按钮错误包装、未打开原计划即冷恢复、未明确结束恢复核对、文本缓冲造成selector伪超时、自有应用连接无field_grants写权限的正确拒绝、原有效周期重复REVALIDATE的正确拒绝。真实onclick预检另暴露当前403处理顺序缺陷，产品修为先处理权限错误再使预览上下文失效；6分支客户端红→绿及真实current403均重新验证。

首冻结18145586整新窗58PASS/3FAIL，另外root-1 107PASS、root-2 145PASS、common132PASS后因受控重冻中断，additional179PASS；这些全部仅作历史，不迁入最终8fe分母。修复后四HTML+三兼容预检7PASS，最终103模块全部从头执行。调度143仅是停止父协调进程，保留已运行测试（包括顺序调度的common子runner和后来资源均衡调度），不能当测试失败/成功；真正中断的pytest仅首冻结三窗，退出码/JUnit另存。

原始本任务证据的导出仅替换已知合成测试会话值和pytest夹具repr行；结构化JSON/XML保持可解析，原件不变。主档index列每个raw/export路径、字节和hash，独立终门从原件重新计算；原历史4107 raw、79旧审查raw及额外121旧归档审查文件保持。最终归档终门和Git逐blob核验不等于正式业务验收。

仅 Linux 本地工程证据。Windows/Win11、真实浏览器、正式AT、人工语义、真实模型B0–B2、正式治理/Approval、现实履约和生产未执行；本分支无既有触发CI的缺口保留。本地六目标仅 LOCAL_OUTPUTS_VERIFIED，清单 recorded_states_only=true、evidence_verified=false、case_goal_completed=false。没有改main、强推、部署、新费用、新凭据或安全权限；没有绕访问拒绝或调用真实产品模型。

下一关键路径仍是更多明确来源的细粒度历史和字面影响验证、一般材料/语义冲突及传播、复杂在途升级/F5-T04、备份恢复、正式治理与运行前提。当前片只交付employees自述来源，不把既有聚合图扩充为任意动态图；按一周目标继续推进。

[主档索引](evidence/employees-fact-provenance-20261015/index.json) · [冻结独审](evidence/employees-fact-provenance-20261015/fact-provenance-review/frozen-8fe3e6c-v2/review.json) · [独立归档终门](evidence/employees-fact-provenance-audit-20261015/final-gate.json)
