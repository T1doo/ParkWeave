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

资料包导出不重做。无真实业务/模型/外部通知/新权限/政策审批/Case完成/部署/安全网络与凭据变化，不改main/强推。完整FactBundle、多用途分享、正式发布与批准、一般依赖图、原42AT/EX/全仓/真实Windows均不由本片签收。
