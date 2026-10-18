# 未命中服务目录版本集合变化的采纳与重验

基线 `fd181ab1564d5b8b4a2feb44d9d93da8d9df08f8`；最终受测源码/合同/测试 `9fd652a29dfbf642fa0f4a49547bf3553417bd74`，分支 `dev/f3-service-catalog-query-20261018`。本片对应原产品§8、F3-T03及AT25–26的查询集合工程子集，[先行合同](ServiceCatalogQueryDependencyContract-20261018.md)。未提升正式AT或完整项目状态。

## 业务变化

原机会卡已经读取同园区、同服务全部目录版本，但原注册依赖只登记resources/existing_access，P1只核命中的服务记录。新 `service_catalog_dependencies.collection` 沿原范围、筛选和版本排序，给全部可读合成版本生成集合指纹，包含原source摘要及经原 `catalog_publication.proof` 校验的当前发布head。未命中版本插入、移出、来源修订或撤回，现在能使P1和实际下游的旧检查失效。无关服务、园区不改变该集合。

原注册声明version2增加P1的SERVICE_CATALOG_QUERY_COLLECTION及service_catalog集合根；影响仍使用原closure/impact_between。原计划页明确local ADOPT登记当前已知基线，再经原逐项VERIFY恢复核验，未自动选择新服务版本、更换资源、分派、发布目录或执行业务。原typed/unified来源投影增加实际集合观察和原页面标签，没有新预览入口、写路由或传播内核。

历史V1预览不含此查询时，manifest重建固定原V1声明和hash；历史typed schema1/unified schema2图也保持原字节。当前缺旧集合证据明确THIS_CASE/UNKNOWN，不用今日值补旧事件；企业可经原无opportunity_proof的local ADOPT登记当前known集合并全Case重验。旧UNKNOWN不会变成永久无法迁移，也不能由来源机会图越过未知门。受影响锁先原UNLOCK，原计划/步骤ID、事件前缀、核验原件和业务产物保留。

筛选前原33行检测保持：32完整、33未知，即使第33行本会被过滤也不伪造全集。损坏原发布证明409。SQL仅返回原六目录字段、park_id和必要可选journal/head；to_jsonb(row)仍在PostgreSQL构造整行，不声称数据库内部不读其它列或行字节有严格上界。复用原并发检查和事务，未新增所有目录版本的发布锁或跨事务原子快照保证。

## 实际窗口

| 源码及窗口 | 实际结果 |
| --- | --- |
| 最终9fd根私有镜像 | 15唯一collection/setup/call/teardown/JUnit均PASS，0FAIL/ERROR/SKIP；14本片新选择器＋1原资源V4采纳兼容选择器。pytest159.17秒、outer164.587819999秒，4原警告；785输入两端PRE/POST零漂移，119项目/测试/helper origin及hash匹配镜像。 |
| 最终9fd独审补验 | 8唯一PASS，0FAIL/ERROR/SKIP；5自有复合选择器＋上述根选择器中的3个。pytest100.69秒、main102.773217010秒、outer104.201781434秒；785输入两端零漂移，115冻结模块＋1自有文件来源/hash正常。 |
| 初版351根冻结 | 15PASS，0FAIL/ERROR/SKIP；pytest171.88秒、outer178.356913182秒，785输入零漂移。属于旧投影源码，不迁签到9fd。 |
| 初版351独审 | 20 collected、setup/teardown各20PASS；call/JUnit为18PASS/2FAIL，0setupERROR，pytest182.09秒、outer186.745809763秒；785输入零漂移。原15全PASS，两个自有用例错误及原件保留。 |

最终源码根15与独审8交集3、有效并集20，不是单窗20或23，也不迁入351的PASS。独立oracle16条规格不是16个pytest用例。开发首窗12PASS/104.57秒、补窗4PASS/60.49秒，交1并15但测试处于开发版本，均不累加为最终冻结成绩。没有重跑旧17/141矩阵、六目标全链或全仓。

实际验证包括：未命中v2插入/移出/source修订；原v2发布head撤回而已选v1和原机会basis不变（v2由原自有fixture append/proof/trigger helper构造，不是普通目录发布路由）；旧VERIFY拒绝、原local ADOPT、P1–P5逐项重验与原业务/授权不变；无关服务/园区不误伤；真实V1来源修订及schema1/schema2历史重建、当前UNKNOWN后明确迁移；人工锁、陈旧请求、目录ABA机会证明、当前READ/PREPARE撤销、跨主体/Case拒绝、冷新Store/API原键GET。纯字面fork另核P1与P2受影响、独立P3/P5保留，不将合成fork冒称新增注册业务图。

原完整HTML NodeVM通过实际HTTP/ASGI和自有临时PG，完成原按钮一次明确ADOPT及五次VERIFY；独审另核P1页面的目录标签与原操作。正向DTO为实际响应，未运行真实浏览器或视觉验收。页面说明在成功操作后清空，下次VERIFY须重新明确填写；请求/断言数不另计用例。

## 失败与修补保全

351独审自有测试曾以namespace=REAL构造过滤行，原migration009的SYNTHETIC-only CHECK准确拒绝，未到目标路径；改为原schema允许的source.kind过滤场景，不放宽约束。另一条自有P1页测试在ADOPT后未重新填VERIFY必需说明，因而没有VERIFY POST；按原用户操作补填后重验。两条失败、原自有测试源、stdout/JUnit与修正版hash均保留，不能删除或写成351单窗20PASS，也未发现需归为产品P1/P2的缺陷。

根另发现SELECT *会返回不必要的同row元数据，经独审确认作常规投影收紧；没有已证泄漏或权限扩大。待351全部shared POST落盘后才改两项输入，另冻结9fd并重新运行根15和独审8。没有在旧窗口运行中编辑shared输入。早期检索猜错测试文件名、归档后猜错输入清单名各一次只读exit2，均为0tests并保留记录；没有新的权限/安全拒绝或重试既有浏览器/root/seal拒绝。

[最终根JUnit](evidence/service-catalog-query-20261018/runtime/frozen-9fd652a2/results.xml) · [实际计数](evidence/service-catalog-query-20261018/runtime/counting-verification.json) · [失败台账](evidence/service-catalog-query-20261018/runtime/failure-ledger.json) · [独审稳定报告](evidence/service-catalog-query-20261018/independent/independent-final-review.json) · [归档配对](evidence/service-catalog-query-20261018/manifest.json)。公开文件仅对失败日志中的临时合成会话值/截断片段最小脱敏，私有原件保留；实际数量、原始/公开hash及已知凭据扫描见归档元数据。测试标识不改。源码、合同、测试、报告whitespace检查通过；保留原失败日志的整体检查exit2，8条空白警告仅来自两份公开失败原件，未为消除警告改写证据。最终156对中154对字节相同、2对最小脱敏，共8处替换（4完整值、4实际fixture键绑定前缀）；另有4个派生归档元数据文件，已知完整值及16字符前缀扫描零命中。独审稳定报告SHA256为 `5d1782eead3084cda791043a2800e45806fe2971299b8759e7e1462fd30d0f5a`。归档控制器对已脱敏影子重复转换曾触发精确hash断言，随后计数曾包含未采用的转换；各次归档及失败stderr均私存保留，最终按已验影子原字节和实际8处替换配对，详见公开runtime/archive-controller-note.json。

17项原文件/传播函数与基线逐字相同，包括原ADOPT/VERIFY、source_change_adoption、内核、formal/NativeRunAccess/provider、API与固定AT规格/绑定；34230个继承F2证据实际流式hash核对保持。9fd后仅增加本报告和证据，785受测输入保持。最终交付SHA、普通push/fetch和全部远端heads差异，以本地 `.runtime/service-catalog-query-20261018/delivery-and-remote-verification.json` 实际回执为准。

## 运行范围及缺项

原合法会话、READ/PREPARE、原Case/Run/preparation、原服务目录、已采纳计划及业务核验前置仍是必要输入；新增集合不赋予目录治理权或执行权。超界、坏发布证明、缺历史原证据、受影响锁及当前撤权按原入口拒绝或UNKNOWN，不能补权。

正式reader/verifier仍缺具体来源四对象关联/版本、主体授权映射、原采纳和Run回执语义、独立验真/current-head/撤销及原批准映射，代码未宣称完成这些接线。原IsolatedCatalogPublication/IsolatedPlanApproval仅用于明确自有合成目录原件测试，不是普通批准；NativeRunAccess permit/writer保持默认拒绝。没有新增真实身份、Grant、分派、目录发布、批准、凭据、费用或安全网络权限，没有真实模型、main/强推/部署或未知锁/进程操作。Windows/Win11、真实浏览器、正式AT、真实园区/主体/来源/业务和现实履约均未验；项目未完成。
