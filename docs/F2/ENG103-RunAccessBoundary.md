# ENG103 新Run执行者访问：精确阻塞与下一步

基线81ff445。本轮只改同Case只读界面的核对信息与人工办理说明，不实现或激活赋权API，不改数据库、凭据、角色、Grant、assignment或OS安全权限。原PR0/F1/F2阶段门保持。

## 实际已有权限与缺失项

| 项目 | 当前实际合同 | 新Case情况 |
| --- | --- | --- |
| 企业经办人 | 同tenant自有Run；当前READ/EXECUTE、可信case.create动作与PREPARE/事实字段权限独立校验 | 原UI提交Run，真实LOCAL worker创建Case；企业能够提交事实、选择用途来源及确认资料 |
| 获派资料专员 | 当前REVIEW_ASSIGNED、同tenant且资料reviewer绑定；不是Run访问审批人 | 能人工REVIEW当前材料；有同Run合法执行者才可从原目录分派 |
| 执行者身份/READ | Linux入口显式receipt-fixtures在原初始化阶段创建原合成receipt-executor-fixture-a/b/c与同tenant READ；不修复撤权 | 身份与READ可能已有，但不等于任意新Run访问；每次都检查active/角色/tenant/Grant |
| 精确Run绑定 | run_assignments持久表，精确principal_id/run_id/park_id/org_id/active | 新Run没有记录。CasePath BLOCKED_NO_EXISTING_ASSIGNMENT，目录为空，伪造执行者请求403 |
| 应用SQL权限 | roles.sql只授SELECT于principals/capability_grants/run_assignments | 应用不能自行写绑定，也没有真正申请/批准路由 |
| 安装方法 | Store.assign_status仅owner setup；检查现有非企业角色与同tenant，持有数据库owner连接才可写 | 不是终端用户CLI/API审批流程；不能调用它冒充普通专员批准 |
| Mock访问候选 | 独立默认关闭SQLite，独立Mock申请/审批/期限/撤销 | 不挂实际PG API；Mock批准不转成产品访问 |

这是“隔离合成业务的现有角色实际Run访问”缺口，同时实际落在持久授权表；两种描述都成立。它不涉及新账号、口令、READ Grant、EXECUTE/CONTROL/FILE_READ、OS owner或ACL，但对目标Run产生真实访问扩大，不能说只是显示一条业务记录。

assignment开放该Run读取，并成为同Run执行者目录、本人offer读取/接受与已单独分派的合成回执操作的前置。它本身不派单、接单、提交回执，也不能执行企业Run。每个业务命令仍独立检查当前材料/事实/父版本和本人分派。

## 当前实际用户路径与下一关

已实际完成：原身份/目录初始化之后，从0业务记录经网页新Run→真实LOCAL worker新Case→三字段有来源事实→用户DECLARE及显式来源选择CONFIRM→两材料→获派专员REVIEW→所属企业CONFIRM。资料LOCAL_CONFIRMED、Case NEEDS_INPUT、资格NOT_EVALUATED。

下一关是对同一正在运行临时库中这个精确Run确认具名现有执行者访问，不是重新确认已确认材料。当前界面新增只读编号文本（Case/Run/资料事项/资料版本），供现有负责人核对；不含会话、事实正文、材料或执行者名册，不发送消息，也不是申请或批准。身份/Case变化、403、读取失败沿既有清空机制清除文本。

后续必须用户亲自办理：企业重读同Case→获派专员从已有合法执行者目录明确选择及分派→被分派执行者本人接受→本人在同事项提交有来源的本地合成回执→所属企业核对当前版本；补正则退回、新版提交、再核对。若请求包含资源目标，还需从原资源入口逐项办理/核对；assignment不完成这些步骤。已有历史回执或另一个Case授权不能满足本Case。

“实际本地执行回执”仅指实际PG/API记录、由本人提交并经企业人工核对的合成回执。没有外部履约或真实资格证明，不能称真实业务完成。

## 仅在统筹需要时的一次性具体决定

最小合成演示范围建议：仅本次新自有临时库、现有同tenant receipt-executor-fixture-a、企业fixture-a明确新建且仍在运行的一个Run；把当前页面完整Run UUID作为核对对象，不使用旧截图UUID、通配或另一Case。执行前必须核实当前数据库/namespace、现有identity/READ/tenant与Run归属；拒绝猜填真实账号或补恢复撤权。

需明确同意的动作仅为owner安装方法写这个现有身份的单Run active assignment，接受上面的读取与独立分派协作可达范围。不新建身份/凭据/Grant，不新增DB角色或技术SQL权限，不挂赋权API，不扩大为真实生产或其他Run。当前owner操作暂停状态不能由旧笼统开发授权覆盖；本轮没有执行此动作。

现有legacy assignment没有expires_at/审批来源，不能承诺4h/8h自动撤销。fresh演示正常退出后仅该临时库被删除，这是夹具生命周期，不是访问TTL合同；停止未确认仍保留目录，不能把未确认删除当撤销证明。若需要持久库或定时授权，应另审ENG089启用决定包的审批主体、期限、撤销、最小函数权限与所有读取路径guard。

目前没有“用户点击批准”可执行入口或现成审批主体；在未取得上述明确动作范围前，唯一安全用户步骤就是从只读页核对当前编号并交由已有负责人处理，继续保持阻塞。不能声称用户可自行运行不存在的CLI命令。

## 本轮验证范围

界面窄改仅整理现有只读返回值及人工顺序；受影响case-path PG/API19PASS（6.70秒），实际0业务浏览器通过16PNG/15viewport，1200/390/320无页面横向溢出。390/320编号文本需框内滚动读尾部，完整值已检查；client注入403仅验证UI分支，另有伪造执行者真实POST403。7权限摘要未变/模型0，独立源码和3幅受影响像素复核无阻断，见[机器证据](../integration/ENG103-RunAccessEvidence.json)。原81ff445完整Linux2292PASS/9nativeSKIP与Server首次CI成功仍归原冻结源，不移用于新界面字节。无需重复未变化完整工程。

installed Windows另见[创建票据设计](ENG103-InstalledWindowsReceiptDesign.md)：本轮不执行真实Windows owner/ACL/security操作，不伪造receipt。R4关闭、模型预算0、F1未签收/F2并行、完整PR0和正式AT/EX未完成。


## ENG104 精确对象核实

最后0业务driver实际未初始化任何执行者；它不是Linux启动器receipt-fixtures分支。该临时parkweave与历史Run已清理，目前没有存活可授权组合。不能把启动器建议主体或历史UUID当作实际已有对象，详见[ENG104对象/撤销与代码验证](ENG104-CreationReceiptAdapter.md)。本轮不写新Run绑定。
