# 实施前冻结：本Case事实来源包与人工锁

基线84af2948abc32415aaf6d7a4439e0596e0014405，本地与远端dev一致，main31e7acb7e53bb1ab6465b9daae59de28757f7583未改，88403af祖先已普通fetch再核。仅root源码写入，挂起Git操作无，平台索引刷新锁保留。本环境启动后实际重验，不假定旧实例状态。

原项：产品§5.1、F2-T01（AT06）与F3-T03（AT26）。现有三字段全局自述、按Case用途选来源、逐条件准备度和资料交付包均已实现，不重做；缺少实际材料摘录的结构化来源、与事实分开的假设、影响后续来源选择的人工锁。正式ServiceRelease/Approval、一般依赖图、一般FactBundle多用途/跨服务分享、真实模型与Win11有未就绪合同/环境，因此本片选既有授权可闭合的Case事实来源→原用途选择→原办理门，不冒充全部FactBundle或原AT签收。

范围固定原owner、同park/org、SYNTHETIC synthetic-material-preparation@1 Case/Run，先明确原LOCAL_SERVICE_PREPARATION_FACTS_V1 / SERVICE_PREPARATION用途。只用region/employees/service_need现有字段READ/WRITE、READ/EXECUTE及PREPARE/原case.create权限交集，无新角色/Grant/assignment。分享范围固定OWNER_CASE_USE_ONLY：只有原owner专用接口可见值、摘录与假设；原专员/下游只消费原既有脱敏事实门，不新增源值读取权。不得扩用途或声称外部共享/已获来源许可。

来源分三类：原事实表USER_ASSERTED_SYNTHETIC（原记录不变）；本Case实际当前两槽DOCUMENT_EXCERPT材料的人工摘录DOCUMENT_EXTRACT_SYNTHETIC；人工明确记录ASSUMPTION_SYNTHETIC。不是模型提取，不声称真实性或资格。摘录必须绑定实际slot、evidence UUID/version/hash、Python Unicode码点[start,end)、值/单位、有效期与Case范围；文本字段value必须等于实际摘录，员工数必须由实际摘录的规范ASCII整数精确得出、unit=people，不接受任意改写/伪造或历史/其它Case材料。假设只能未知候选，不能作为原事实选择或自动升级成事实；撤回保留历史。新来源最多12，来源包最多32事件，原preparation最大64修订上限不变。

原事实选择接口实际纳入仍当前的摘录来源；原确认必须拒绝假设/撤回/材料已换版/到期来源。来源换版只令当前有效性失效，原来源/来源包事件/事实确认历史均保留；须明确登记当前摘录及原来源再确认。任何来源包成功写入增加独立bundle revision与preparation revision，清原review、置IN_PREPARATION、失效P1同事务；原事实选择仍须原专员REVIEW/企业CONFIRM及既有资源/办理恢复，Case不自动完成。

人工LOCK仅绑定本Case当前已明确选择的field/source UUID/revision/fingerprint；同字段其它来源确认报LOCK_CONFLICT，不改原锁/选择/下游。来源陈旧或过期不自动换锁；UNLOCK须原owner明确原因与版本，后续独立原确认。来源WITHDRAW遇当前锁也拒绝，须先显式UNLOCK。锁定不证明事实真实，不把锁变成Grant或业务Approval。

写入需精确preparation revision、bundle revision、实际来源聚合SHA（含Case绑定、实际两槽、原事实源/授权世代与来源包描述），源字段及actor/key稳定锁、parent FOR UPDATE、原actor-wide preparation key、CAS、幂等与提交前复核。新键重复同一材料field/span/值/有效期摘录拒绝，不生第二来源；错key/body或Case409。SQL仅新增preparations.fact_bundle JSON与原preparation_events真实FACT_BUNDLE_COMMAND action，fixture migration028沿现有真实新建DB receipt协议，native不启用；roles.sql不变，无新权限。已有25/26/27/28保留启动不自动升级旧库；新fixture才到28。wheel必须携带028实际安装迁移。

来源包为追加事件/hash链与重建投影；原JSON可信应用/管理员边界，不称hash签名或数据库管理员不可改写。GET/recovery只读，当前授权先于历史回执；历史精确event与当前视图分开。NOT_OBSERVED/超时/坏证明不当成未提交，禁止自动POST。页面POST前最多8条opaque actor/id/key持久句柄（无token/值/摘录/理由/hash）；存储失败不POST，损坏/未知禁新来源包动作，冷刷新重认证仅GET恢复。迟到身份/Case/草稿成功或403不回填/清新私有视图，当前403清私有视图但保留句柄。原来源确认控件显示来源类别与有效性；服务器锁约束才是权威，不仅UI禁用。

完成判据：实际PG/API登记→选择材料摘录→原REVIEW/CONFIRM→真实原准备度/P1门；假设不可选、伪摘录/越范围/越角色/撤权/过期/换版/锁冲突/显式解锁/撤回/并发CAS/同键及跨Case重用/丢响应冷GET恢复/JSON坏证明/独立回滚负例；原事实、材料、Case/资源/办理历史及Grant不被偷偷改写；实际HTTP/Chromium三宽度、注入纯文本、隐私、迟到响应与真实API进程冷启动；必要旧用途/原办理集成/迁移/启动/wheel兼容。冻结源hash→普通推候选→精确SHA独立只读审查→限定通过后仅dev FF普通推送。原失败日志私有保全，不把较早失败窗口算全仓PASS。

兼容消费边界（2026-10-10，修复前再冻结）：既有USER_SELECTED_PREPARATION_BRIEF_V1摘要配方只明确分享三项全局自述，不能把本轮OWNER_CASE_USE_ONLY摘录标成自述或间接复制给原专员。只要本次选择含Case资料摘录，摘要GET明确BLOCKED、无草稿或值，摘要POST409且无写入；本次原资料包、事实选择与准备度/P1仍按原流程核对。重新明确选择三项原自述后，既有摘要生成与显式分享继续原合同。假设始终不可选。此补充收紧既有消费者，不新增用途、分享、角色或Grant。当前403仍须清私有视图、保留句柄并提供可见的页面提示。

资料包导出不重做。无真实业务/模型/外部通知/新权限/政策审批/Case完成/部署/安全网络与凭据变化，不改main/强推。完整FactBundle、多用途分享、正式发布与批准、一般依赖图、原42AT/EX/全仓/真实Windows均不由本片签收。

存储一致性补充冻结（独立审查 CFB-EMPTY-LEDGER-DOWNGRADE，2026-10-10，源码修复前）：首次未登记只允许SQL NULL且无FACT_BUNDLE_COMMAND回执；持久非NULL来源包必须有1..32条事件。每次读、恢复与写前必须逐一验证JSON链与原SQL回执的总数、actor/key/fingerprint、父revision、bundle revision/action与receipt SHA一致；空包、有效前缀截断或部分回执损坏均409且只读，不可接受新写或自动重建。SQL回执仍仅含既有脱敏元数据，不复制来源值/原因；同事务提交顺序保持完整回执后才提供当前视图。此约束检测部分存储损坏，仍不声称抵抗同步改写全部记录的管理员。
