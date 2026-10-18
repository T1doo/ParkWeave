# F3-T03 原机会卡类型图只读预览

基线 `9be4788bb068eeead64cda2f7a4eb70099a4df4f`；冻结实现/合同/测试 `85dfd1a2c4fa9d4c17ca992949661cf969088525`，分支 `dev/f3-typed-dependency-opportunity-preview-20261018`。本片接续产品设计§8/F3-T03已有工程债：[合同](TypedDependencyOpportunityPreviewContract-20261018.md)。没有签完整AT25/26，原42项状态与验收规格字节保持，项目未完成。

## 结果与调用

原 `GET /api/preparations/{preparation_id}/opportunities/{card_id}/plan-revision` 显式携带 `dependency_scope=BOUNDED_MULTI_SOURCE_V1&graph_preview=VERSIONED_TYPED_GRAPH_V1` 时附加 `typed_dependency_preview`。沿原owner/READ/PREPARE、Case/Run、当前机会卡、账本与计划锁上下文，调用已审 `dependency_graph.from_unified_v1`；未另造传播引擎或接受客户端图。图版本、旧schema2摘要及逐消费者观察保持，结果分别列确定/不确定影响、保留/删除、路径见证及当前人工锁冲突。当前来源只覆盖原有界聚合关系，未扩成一般语义或自动发现依赖。

页面增加“只读比较类型图、版本路径与人工锁”。新按钮清除旧确认与 `opportunityPlanView`、隐藏采纳控件，仅读取原 command-recovery 的 NO_REQUEST/current 取得计划上下文，避免普通计划GET的invalidated观察写。原预览和原v4 ADOPT仍用原入口/证明；新字段只在 `read` 附加，不进入 `build`、ADOPT正文或历史。传播内核、registered/typed/unified依赖模块及service_case_steps与基线逐字相同。

页面核当前绑定、摘要、原图转换/步骤分区和版本路径引用，不重算传播闭包；哈希不是身份认证。command-recovery刻意脱敏来源与核验hash，页面只能核当前锁布尔、最后LOCK/UNLOCK事件/步骤身份及wrapper摘要格式；完整锁actor/来源/核验相等证明由服务器原 `_manual_lock` 核对。原快照不含锁，当前锁单列，不倒填历史。新增投影的authority/execution/adopt旗标均拒绝；保留不证明事实当前有效，阻塞另列。

## 验证分窗

| 窗口 | 实际结果与限制 |
| --- | --- |
| 根冻结85df私有镜像 | 14唯一collection/call/JUnit均PASS，0FAIL/ERROR/SKIP；新增13实际API/页面＋原客户端probe1，pytest169.42秒、outer172.62730524秒。775输入shared/mirror PRE/POST零漂移；112个项目与测试/helper模块origin及hash命中冻结镜像，外部依赖未插桩。 |
| 独审首窗 | collection16；主13 call全PASS，自有3 setup ERROR且无业务call；pytest142.72秒/main144.76968065秒/outer146.5263秒。 |
| 独审自有v2 | collection3，仍3 setup ERROR/0call/0PG；外部路径未发现原conftest的执行器配置问题保留。 |
| 独审自有v3有效补窗 | 显式注册原冻结conftest plugin，未改原fixture字节；3唯一call/JUnit均PASS，0FAIL/ERROR/SKIP，pytest44.13秒/main44.6020秒/outer47.3207秒。 |

独审三窗各775输入shared/mirror PRE/POST零漂移；有效窗各110个项目/原helper模块命中镜像，另记录1个自有测试模块，异常origin/hash为0。18行独立设计oracle不是18条pytest用例。首两窗夹具发现失败没有业务call，既不当作产品FAIL，也没有擦去或写成单窗16PASS。只补自有3，主13未重复执行。

根用例验证资源集合实际变化时P2–P5受影响而P1保留、P1/P3当前锁及P3冲突、旧响应字段逐项同一、新Store/新API仅GET、全public业务/权限快照不变（authorization_audit拒绝审计除外）、当前READ/PREPARE/角色/跨Case拒绝、UNKNOWN、精确双query及GraphError→409、旧v4原ADOPT/历史保持。页面7模式覆盖新按钮与旧确认清除、无普通观察GET、当前403清屏、同Case身份ABA后迟到200/403/JSON/运输/摘要await；正向为实际响应，5个wrapper重hash坏DTO为负向断言，未另计5条测试。原客户端probe1含8个控制断言，同样只计1个选择器。

主/独有效PASS的实际nodeid并集**17**、交集13：根14包含新增13和原probe1；独审有效16由首窗主13及补窗自有3组成。不是14+16=30，不迁入前片141，也不把断言/请求数当用例数。外部独立3个实际nodeid以 `::` 起始，collection原件另保存真实外部path，不补造前缀。

自有独审补验旧v2/v4响应和原hash同一、当前锁与历史、source epoch ABA、冷新API只读、坏锁/UNKNOWN及拒绝；其原完整页实际71GET/0POST、33断言，7个坏DTO探针全部拒绝，覆盖真正A→B迟到200、迟到403加身份ABA、冷新页与草稿守卫。新按钮路径普通plan观察GET为0。该请求/断言数均不另计测试。独审开放P1/P2为0，无需源码修补。

开发首窗13 collection，止于第7条：6PASS/1FAIL；第二窗仅重跑该页面positive，0PASS/1FAIL。两次均因页面误把原恢复投影刻意移除的verified hash当完整锁来源比较而拒绝合法结果。修正为上述准确客户端/服务端边界，不改变恢复字段、原auth或原锁算法；失败原件保留。第三窗只跑7条页面用例：7PASS/0FAIL/ERROR/SKIP（pytest110.35秒）。开发数不相加或转签冻结成绩。

完整HTML NodeVM加载实际发布页并向真实HTTP/ASGI/自有临时PostgreSQL发请求，正向DTO为实际响应；坏DTO重hash仅为明确负向探测。NodeVM不是浏览器，没有视觉/原生浏览器验收。本轮未启动Chromium、root/seal/发行或真实模型，也未新增运行时真实authority。

[结果与范围](evidence/typed-dependency-opportunity-preview-20261018/validation.json) · [根原JUnit](evidence/typed-dependency-opportunity-preview-20261018/runtime/frozen-85dfd1a2/results.xml) · [独审稳定报告](evidence/typed-dependency-opportunity-preview-20261018/independent/independent-final-review.json) · [精确计数](evidence/typed-dependency-opportunity-preview-20261018/runtime/counting-verification.json) · [失败台账](evidence/typed-dependency-opportunity-preview-20261018/runtime/failure-ledger.json)。独审稳定报告SHA256为 `688f6f32aadab9b28aab5dea40b6243af8b5f3dd6fe14fda25891215fcd9eb79`。

[原件配对manifest](evidence/typed-dependency-opportunity-preview-20261018/manifest.json)封存140个唯一raw/public配对，136对字节相同；仅4份开发失败stdout/JUnit中的16处临时SYNTHETIC会话值/截断片段脱敏，私有原件保留。独审77项公开原件无需脱敏；不导出token/config/镜像/PG data。所有JSON/JSONL/XML解析及配对hash核对通过，已知临时会话全值和16字符以上前缀公开匹配为0。[归档校验](evidence/typed-dependency-opportunity-preview-20261018/archive-validation.json)与[保密扫描](evidence/typed-dependency-opportunity-preview-20261018/confidentiality-validation.json)保存实际结果。元数据衍生件不计进140对原件。首次归档误把3份同字节oracle/补充别名重复计入配对；现只从独审最终清单选取一次，首版完整保全在私有runtime，测试计数和原件字节未变。

源码/合同/测试/报告空白检查exit0；全新增证据检查exit2的15处告警来自原始失败记录，原字节保留。继承33970个F2证据Git条目逐一核对保持，775冻结输入在报告完成后仍无漂移。交付在源码冻结85df后只增加报告/证据；实际完整交付SHA、远端全部heads差异、目标分支0/0及main状态以本地delivery回执记录的网络结果为准，不预写推送成功。

## 真实运行缺项及边界

此按钮需要已有合法当前会话、同域READ/PREPARE、原Case/Run/preparation、当前精确目录与来源、当前待审机会卡/账本及原计划/核验历史；缺失继续原403/409/UNKNOWN，不能从提示补事实。进入实际业务仍需原获派REVIEW_ASSIGNED、原EXECUTE/资源权限、精确Run既有executor assignment及相应独立批准；本片没有提供创建这些authority的入口。

普通provider可信宿主接线、正式来源独立验真/当前head与撤销、主体/Case/Run/已采纳方案绑定和正式批准映射缺口保持；NativeRunAccess permit/writer继续默认拒绝。IsolatedPlanApproval及本次临时合成fixture不充普通批准。没有新增真实身份/Grant/分派/目录发布/批准/凭据/费用/安全网络权限，没有改main、强推或部署，不动未知锁或进程。

Windows/Win11、正式AT、真实主体/来源/园区业务、生产宿主与现实履约均未验；远端Actions未运行。本片仅只读工程子集。
