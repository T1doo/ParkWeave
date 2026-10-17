# 本事项办理记录核对包：实现前合同

基线 `b0f3cb8d69f33413ff8ac06b4be03b39d2fe5da2`，分支 `dev/f2-case-record-pack-20261017`。本片由用户明确授权，是新增便携核对视图。原 V1 产品 §3（83–89行）、§5.2、§5.5、§11，以及 F2-T02/T04/T07要求目标、步骤、结果及完整记录和导出隔离；原件未单独规定这个命名的下载功能，不能以本片冒称完成原方案全部业务验收。

用户沿原已有资料事项入口，进入本事项持久步骤计划，读取“同Case必需目标总览”，显式生成并下载 UTF-8 TXT。包提供本次诉求、全部当前必需目标（含不支持/未满足/等待/整体PARTIAL）、允许的实际记录引用、原owner核验事件与其当前性、人工责任/阻塞/下一步、原采用来源及旧计划引用。它是当前owner所列可读记录的便携索引，不是全量事件归档。原双槽材料正文/补正/readiness文本包和独立facts.assess历史比较不重做，默认拒绝的P4/P5历史summary不调用或绕过。

服务器只在原goal-results同一parent读取中补显式current_required_goals；原身份/PREPARE/READ、owner/Case/Run/租户、来源/VERIFY与原P1–P5算法不重做。前端使用原goal-results GET，不增加端点、业务命令、表/迁移、Grant、批准或完成事件。当前目标顺序与全部结果逐项一致，不以旧adopted_goals或原trace裁剪当前目标。空目标明确UNKNOWN，未采纳目标保留NOT_ADOPTED。

生成及每次下载均重新GET两次并鉴权，验证身份和preparation/Case/Run/plan/request版本、原逐行result_sha256和原trace_sha256，完整的允许导出投影须与当前已展示结果、两次最新读取一致。整体SHA256绑定该投影及全部目标、行、历史引用和限制；它不是数据库防篡改签名，也不证明未导出的全来源原子快照。原trace只证明历史采用来源，不能当成当前全来源证明。材料/资源/权限/规则/期限变化导致所列结果不同就清候选，要求原入口重读。下载不输出旧页面缓存。

只按字段白名单输出原端点允许的引用；不打包资料正文、事实值/片段/假设、回执正文、原私有source快照、权限/Grant/permit/运行批准/凭据、生产者或目录完整对象、数据库/文件路径。原记录引用中的actor ID仅为已有本地事件责任标识，不是授权。用户原文按JSON转义显示和导出，不执行HTML。

复用goalSourceWritePending完整门：原在途/UNKNOWN写入、恢复句柄或全局写流阻止生成/输出；GET前、每个异步阶段后、发布/Blob前重查。当前真实403优先清私有DOM/内存，保留原不透明恢复句柄；身份/Case/计划/草稿/读取代际变化及迟到旧200/403不覆盖新上下文。不保存包或token到localStorage。已下载副本无法收回，有限重读不能保证服务端最后一次读取至客户端下载间没有外部变更。

包及页面明确SYNTHETIC快照：case_goal_completed=false、资格NOT_EVALUATED、外部NOT_SUBMITTED、线下NO_EVIDENCE；LOCAL_OUTPUTS_VERIFIED仅指原有限合成本地产物核验。原批准、提交、补正、VERIFY、重开/关闭均须在原入口另行明确操作。

验证覆盖真实普通configured_app进程、隔离合成PG、Chromium实际入口/生成/下载/冷重启，完整目标/PARTIAL/旧核验失效、缺口/无计划/空目标、同revision来源变化、两读间变化、撤权/跨角色/跨租户、迟到200/403及身份ABA、UNKNOWN/原句柄保留、纯文本/XSS/窄屏、业务与权限表无写入。Linux合成测试不替代真实来源/正式目录/合法provider、Windows原生正式AT或真实履约验收。

原行/原trace的SHA引用原接口完整投影；白名单裁剪后不承诺从子对象重算这些原SHA。可离线重算的是整个导出核对数据的SHA。服务选择仅保留已有release/instance/service/park ID及修订/指纹，不输出角色/资源/字段授权映射。未采用且不支持目标没有人工记录时，保留其未提供状态；半结构人工字段仍拒绝，不默认NOT_REQUESTED。
