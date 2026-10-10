# 本Case实际资料摘录、待核假设与人工来源锁

从已集成的84af2948abc32415aaf6d7a4439e0596e0014405继续，实施前合同23d6fc22b806ad1c173718c560a9ba1e2c926071；兼容消费边界在26d80c010ab728ce543e19ecab8c61512d19fbbd另行修复前冻结。原项为产品§5.1、F2-T01/AT06、F3-T03/AT26的有限合成Case子集。既有自述来源、用途确认及资料包导出不重做；本片补实际资料摘录参与原事实选择、假设独立保存、服务器人工锁及来源变化后的明确复核。

企业先按原入口明确本事项事实用途，再打开“本事项事实来源与人工锁”。登记摘录须从本人当前两槽DOCUMENT_EXCERPT资料复制原文，绑定真实evidence UUID、slot、版本、内容SHA、Unicode码点区间、类型/单位与适用期。文本值必须等于实际摘录，员工数必须等于规范ASCII非负整数摘录；伪值、旧版、其它Case、任意类别改写均拒绝。来源仍未核验，不作资格判断。人工假设保存理由但一直UNKNOWN，不能作为原事实选择或自动升格。

现有三字段全球自述表保持原记录；本Case摘录仅进入本Case的来源选择。来源包最多12条来源、32条追加事件，原资料64修订边界保持。每次成功来源操作增加来源包及资料修订，清旧人工核对并失效P1。必须刷新当前事项、逐项重新明确来源，然后由原获派专员REVIEW、企业CONFIRM；Case目标和外部办理不自动完成。

LOCK绑定当前明确选择的字段、来源UUID/revision/fingerprint及完整源值摘要。原事实确认实际执行服务器约束，同字段另一来源及撤回被锁来源均拒绝。来源换版或过期不自动换锁，先明确UNLOCK，再独立选择。撤回、换版、原诉求变化保留来源包及原选择历史。每个来源事件保存实际两槽与事实聚合摘要、资料修订、原请求revision/hash；只读恢复返回精确历史回执和独立当前状态，旧回执不代表新来源已确认。

专用接口只限原owner、同park/org、原SYNTHETIC Case/Run、synthetic-material-preparation@1及SERVICE_PREPARATION用途。权限仍交集原READ/EXECUTE、PREPARE/case.create和三字段READ/WRITE；只读历史也重验现有范围。固定OWNER_CASE_USE_ONLY，无新角色或Grant。原专员和一般资料、准备度、待办接口不携带私有来源包、假设及理由，只消费原既有脱敏事实门。原已明确分享的材料仍按既有角色权限可读。旧自述摘要配方遇Case私有摘录选择时GET无草稿、POST拒绝，不间接复制或改称自述；明确选择原全局自述后原摘要流程继续。

fixture migration028只新增preparations.fact_bundle JSON与原preparation_events的FACT_BUNDLE_COMMAND action，沿实际新建数据库receipt协议；roles.sql不改，native仍停25。既有25/26/27/28演示启动保留原版本，不自动升级旧库；新隔离fixture到28。wheel携带028，实际安装包新建库迁移在原机会wheel测试中验证全部Store迁移资源字节与新JSON列。JSON按追加hash链重建投影，API没有历史编辑/删除；hash不是签名，可信应用/管理员仍能改写存储，不声称数据库管理员不可变性。

所有写入使用原actor-wide preparation key、精确双revision及来源SHA、稳定锁、parent CAS和提交前现有授权/适用性复核。同键同体仅一事件，错体或错Case409；新键同一材料摘录不产生第二来源。POST前浏览器最多保存8条opaque actor/id/key，无凭据、值、摘录、理由或正文；存储失败不POST。丢响应、坏证明、损坏或超界存储保持未知并阻止此事项新来源/用途确认。冷页重新认证只GET核对，不自动重发。当前403清私有视图但留句柄，迟到身份/事项/草稿成功或拒绝不清新草稿、不删原句柄。

实际核对范围、每轮失败史、冻结318路径与独立审查证据位于[evidence/case-fact-bundle](evidence/case-fact-bundle/verification.json)。早期原始失败JUnit/日志和UI草稿保留私有忽略.runtime/case-fact-bundle；其中包含合成会话，不公开原失败栈。原P1观察会记录既有步骤失效标志，集成测试只允许这一既有明确变化，其他业务历史、来源/事件、权限全部逐行比较。

本片不签收完整一般FactBundle、多用途/跨服务分享、正式ServiceRelease/Approval、一般依赖图、全部原AT06/26/42AT/EX、全仓回归、真实业务、Windows11或真实模型。没有外部通知、新权限、政策审批、Case完成、部署、凭据/安全网络变化；main不修改，旧a823a28 Windows Job/accounting未迁移，不声称Windows验收通过。

最终修复源码dded6b0e450dfcabda0baef0ace3cbfd386b7fa1，冻结318路径/诊断AST1312；12个最终完整受影响模块431PASS/0FAIL/0ERROR/0SKIP，JUnit270.782秒，前后源码无漂移，含47项新真实PG/API、24项真实HTTP/Chromium、原事实/集成/摘要/机会/wheel/迁移/启动/诊断。此前424PASS为pre-storage-fix旧字节窗口；29模块971项为970PASS/1nativeSKIP，524.009秒，属于更早pre-consumer-source。各次独立列出，不能合称最终全仓通过。

首轮精确候选3b5785b453169f8197a3df0e3563e45a09a83c97独审347PASS及5个额外真实HTTP/PG探针4PASS/1FAIL，结论BLOCKED：非NULL空JSON账本可使保留SQL回执的可见历史重置。保全报告后，在85b21ba先冻结存储一致性合同；修复现在逐条交验SQL/JSON总数、actor/key/fingerprint、父revision及Case/Run/bundle动作/修订/回执SHA，空包/有效前缀截断/部分SQL损坏均409且无写，未知键恢复也先验证账本。旧过期测试直接改JSON的46PASS/1FAIL窗口私有保全，已改真实PG时钟越过期限。新SHA普通候选推送后重新独审，尚未审的修复不合dev。
