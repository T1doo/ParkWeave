# 同服务目录版本查询集合接入原采纳及重验

基线 `fd181ab1564d5b8b4a2feb44d9d93da8d9df08f8`。原产品§8、原F3-T03/AT25–26要求查询集合指纹跟踪未命中来源变化。本片接原机会卡同园区/同服务全部目录版本查询，补P1集合依赖与原ADOPT/VERIFY业务闭环，不新增预览入口、传播算法、目录发布或authority。

## 最小实现

读取沿原 `case_opportunities.sources` 查询范围与SYNTHETIC/NOT_EVALUATED/source.kind筛选，版本排序，最多32原行，第33行检测溢出。每个当前版本指纹含原service/version/name/source摘要及原 `catalog_publication.proof` 已校验的独立当前head（存在时）；从而未选中版本的插入、移出、来源修订或原撤回也改变查询指纹。查询不跨服务、园区或新主体范围，不借本片创建目录、记录或授权。损坏原发布证明准确拒绝；溢出UNKNOWN，不能返回伪完整集合。

SQL仅返回原目录六字段、park_id与可选发布journal/head九字段，避免把同row无关candidate/capability大JSON带回应用。可选列通过to_jsonb(row)取出以兼容旧schema；PostgreSQL仍会构造整行，不宣称数据库内部未读其它列或严格行字节上界。

原注册依赖声明升级为version2，在P1登记 `SERVICE_CATALOG_QUERY_COLLECTION`，`service_catalog` 集合根为P1。新初次ADOPT自然保存该集合stamp，当前变化依原closure影响P1及实际下游，旧核验不沿用；企业必须原入口明确local ADOPT再逐项VERIFY。集合stamp只存known/count/hash，不倒填历史原行或冒充资格规则真实性。typed/unified图仅增加这一实际集合的观察来源，保持原影响结果及原页面显示；不另建图内核或同义预览。

旧version1声明及历史按其原字节验证和呈现，不将今日集合补进旧事件。旧计划缺该集合证据时当前影响为THIS_CASE/UNKNOWN，要求原已有明确local ADOPT登记当前已知集合并全Case重验；不得静默称旧全集已知，也不得改写既往VERIFY/批准/业务产物。兼容不等于旧检查继续有效。所有原请求键、计划/步骤ID、旧事件前缀、人工说明与历史产物保持；受影响锁必须原UNLOCK，拒绝不补权。

## 有界验证

1. 独立字面应改/应留集合：同服务未命中版本新增/移出/来源改版/撤回影响P1及原实际下游；无关服务或园区不误伤。32完整/33未知、旧version1缺证据、损坏head与严格manifest结构另验。
2. 自有临时合成PG与原HTTP/ASGI：实际原计划/VERIFY，查询变化→旧VERIFY拒绝→原local ADOPT→原逐项VERIFY；旧事件前缀、稳定ID、真实业务与权限记录不因查询/采纳改变。覆盖当前锁、READ/PREPARE/跨主体拒绝、陈旧采纳证明、冷新Store/API原键只读恢复。必要时原机会来源入口复用，不把提示当来源。
3. 原完整HTML NodeVM至少一条目录变化到原按钮明确采纳再重验的实际路径；原页面已有上下文/迟到/403守卫复用，只补必要集合标签。不是浏览器。独审冻结自己的字面oracle及少量反例，按真实selectors和分窗交集去重，不重复旧预览/旧17/141矩阵。

正式reader/verifier仍缺具体来源四对象/主体/采纳/独立验真/current-head/撤销/原批准映射；没有编造生产合同。NativeRunAccess permit/writer保持默认拒绝，不以IsolatedPlanApproval充普通批准。不新增真实身份、Grant、分派、目录发布、批准、凭据、费用或安全网络权限；不真实模型、浏览器降级、root/seal、main/强推/部署、未知锁/进程操作。Windows/真实业务/正式AT及完整项目均未完成。
