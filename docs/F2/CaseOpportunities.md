# 原F3-T02的本Case合成机会业务切片

原要求为V1 F3-T02、AT-24及产品§5.3的显式导入/手动刷新、授权匹配、去重、忽略及撤回。基线`9c1b9f91f539ff757e58235535f253e1a9e38434`没有机会API、存储或页面；现有Case事实用途已显示来源/单位/摘录/适用期并支持明确目的确认，因此不重复做FactBundle外观或资料导出。实施前合同`565afd133795cfbc21db20b14fced4bc6bb21f65`。

仅原owner的既有合成资料Case。本人手动导入“本Case资料变化”或“既有合成服务版本”提示，选取实际同service_id合成目录版本；这是一条用户导入的未核验声明，不是政策规则、资质判断、正式发布或受理。导入绑定实际Case/Run/owner/park/org/service、资料revision、两槽ID/version/hash和实际目录source SHA。当前来源与历史导入分开，目录不可消费时显示历史提示，刷新也不会恢复或发布目录。

8个来源族、16张卡、128个请求事件上限。每族generation1–64单调，同代同内容不产生第二张卡，同代异内容409；乱序较旧新代不覆盖最新。忽略/撤回后同代重复导入及刷新不会复活；新代次明确产生新的待审卡并保留旧记录。刷新只更新最新未决卡的实际来源绑定，仍待人工审阅。原资料revision、REVIEW/CONFIRM、Case状态、资源、计划均不因机会操作改变。

GET只读并重验active原owner、READ/PREPARE；POST还需EXECUTE，精确ledger CAS/source SHA及card/version。实际当前同actor/key幂等，错指纹或错Case409。GET原键恢复返回精确历史回执和单独当前视图，NOT_OBSERVED或锁超时仍未知。页面在POST前持久保存最多8条opaque actor/id/key，无token/正文/理由/hash；保存失败不POST，未知/损坏/超界暂停此Case新机会操作，冷刷新重认证后仅GET。证明缺失或迟到身份/Case/草稿响应均不删原句柄、不回填新私有视图。当前403清私有视图，原句柄保留。

只新增preparations.opportunities JSON列，既有应用表UPDATE覆盖该列；roles.sql和身份/能力/字段/访问Grant未改。按现有新建合成DB实际receipt安装fixture migration027，缺receipt拒绝，重复迁移保留业务和权限；native仍停既有25，不启用机会功能。账本按序追加hash链并重建投影，API无历史编辑/删除；这是原JSON业务账本的可信应用/管理员边界，hash不是签名，也不声称授权UPDATE账号无法改写列。目录只有SELECT，使用来源SHA且不申请UPDATE锁；不声称目录在COMMIT时的管理员改动原子性。

通用资料/readiness/待办接口不携带私有机会账本；获派专员无机会正文/操作权。标题/说明只用textContent显示。证据位于evidence/case-opportunities，失败原日志留私有.runtime/case-opportunities；执行通道断连经实际只读恢复，失败调用没有创建测试文件或执行测试，不按inProgress计成果。

本片是AT-24有限合成Case子集，不签收原完整AT-24、一般企业/政策匹配或全部42AT/EX。一般FactBundle三类来源/多目的、一般依赖图、正式Release/Approval主体、真实来源许可、真实模型和Win11仍缺；不把Linux工程/原生边界Mock等同真实验收。没有新角色/Grant/模型/外部通知、后台在线、Case完成、部署或安全网络/凭据变化。资料包导出未重做。

首候选冻结314条源码/测试/脚本hash，前后无漂移；首候选受影响完整模块137项通过（34 API、22真实HTTP/页面、14 worker、8 Linux启动、59诊断），JUnit107.949秒，无失败/错误/跳过。此前862项扩大回归为857通过、4失败、1原生Windows跳过；修正窗口270项为269通过、1旧health版本断言失败，之后已修正并在最终完整worker模块复测。各轮源码manifest与失败原因单独保全，不把较早范围合并宣称全862或全仓通过。最终三宽度截图与两个实际独立API进程同PG恢复证据随存。

首候选086d637c9f5be1f5367fe712687ba494decd0f84经独立实际wheel检查被BLOCKED：027未列入package-data，安装后读027实际FileNotFoundError。安全阻断报告随存，未合dev。已补027并在test extra固定既有build backend setuptools80.9.0，新增wheel构建/解包后独立Python进程实际新库迁移及重复迁移测试（包含全部Store migration资源字节比对，不宣称其它fault模块包验收）。重新冻结314源路径，诊断AST1284；完整受影响138通过：35 API、22 HTTP/页面、14 worker、8 Linux启动、59诊断，JUnit111.588秒，无失败/错误/跳过。新精确SHA独立审查尚待完成；未经限定通过不合dev。
