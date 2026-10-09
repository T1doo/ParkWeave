# 资料交付异议候选

基线 `88403af18b95b361114b303c3fae636f286d91b4`，合同先冻结于 `aaabf758687b4d16dd3eec4b06fc6fb9361bf5fb`。沿原 V1 F2-T07、产品§5.5和PR0缺口实现现有合成双槽资料的企业反馈；[冻结合同与实现细化](MaterialDeliveryObjectionContract.md)。资料文本包产出功能未重做，既有资料包证据保留原字节。

企业提出资料交付异议→原获派专员说明回应→企业明确接受回应或仍未解决。专员回应不自动关闭；资料、诉求、人工审核来源或权限世代变化保留历史，须企业明确重绑定当前来源，再由原专员回应和企业复核。每事件绑定Case/Run/资料revision、双槽ID/version/正文hash、服务、请求版本、原主体及原回应UUID。资料确认及本地记录关闭拒绝未决/失效异议，不写Case完成。实际Case仍依原合成合同，资格、现实履约与外部受理不由本功能判定。

追加事件和资料revision同一PG事务；应用角色不能UPDATE/DELETE事件。写入CAS、原键原body重放、不同body冲突、当前撤权先于重放；恢复GET只读按原actor/key核对。浏览器仅存最多8个Case/key/actor/revision句柄，不存会话、正文或请求体；未知句柄不自动到期清除，NOT_OBSERVED保留锁；403清私有视图，身份/Case/generation迟到响应丢弃。

schema26仅扩展现有事件CHECK；现有roles/grants文件不变，新建隔离Linux数据库需原已验证creation receipt，未自动升级既有库。现有native receipt仍止于schema25，其原路径无新异议写入。Linux演示启动器接受既有25/26，fresh fixture为26；原25不补发建库receipt或自动升级。需要在冻结合同内安装的新候选只用于合成环境。

初始候选冻结专项 **72PASS/0FAIL/0ERROR/0SKIP，86.02秒，2WARN**，含41 API/PG、18真实HTTP/Chromium和13原材料文本包兼容用例。包括原HTTP API进程终止/重启及页面冷刷新后GET恢复、撤权和恢复世代、越权/跨园区企业/同企业另一Case、实际正文篡改、资料/诉求/目录/重开换版、并发同/异键、迟到读写响应、事件UPDATE/DELETE权限拒绝、事务回滚、隐私/注入/损坏存储负例及320/390/1200宽度。300个冻结源码/测试/脚本文件零漂移。此前相关回归416PASS属于当时源码，其后权限绑定和页面收紧由该轮72项验证，不重复相加宣称全仓。

全仓尚未通过且没有完整终态：首次私有runner收集13个导入错误，修正运行路径后普通单进程全仓测量出现共享fixture错误/既有Windows Setup模拟失败，主动中断，完整日志保全。两个相关文件在候选与独立detached原基线均为 **34PASS/13SKIP/1FAIL**，同一失败 `test_setup_checks_created_config_and_sessions_without_acl_repair`，不在本任务修改Windows accounting/ACL。原native、Windows、42 AT/EX、F1/F2、R4/LIVE都未签收。候选不部署、不合开发分支，普通push后交独立只读审查。

[机器记录](evidence/material-objections/verification.json)、[冻结专项日志](evidence/material-objections/targeted-frozen.log)、[JUnit](evidence/material-objections/targeted-frozen.xml)、[源码hash](evidence/material-objections/frozen-source.json)、[API重启证据](evidence/material-objections/api-restart.json)、[截图索引](evidence/material-objections/browser-output.json)。失败原始日志放在忽略的 `.runtime/material-objections`，公开记录保留各轮计数和原件hash，不发布fixture会话值。独立审查结果和最终远端SHA在交付终态补充。


## 独审阻断与修复后冻结

初始已推候选 `027709da07f7557ea0baeb23c5cd078d327fac5b` 被独审阻断。原72项独立复跑仍全PASS，但独审新增5个API/PG与2个真实HTTP反例均FAIL：无revision的身份/准备权限撤销恢复会复活旧回应；目录变更后未有对应新REVIEW即可REBIND。原结果与hash保留在[初始独审记录](evidence/material-objections/independent-initial-blocked.json)，不把当时72PASS改写成无缺陷。

修复合同先追加冻结于 `f936ea5`：只读绑定原 principals/preparation_grants/capability_grants/catalog 的实际行世代指纹；原人工REVIEW事件记录目录/世代/授权证明，当前资料异议须同时匹配真实REVIEW actor、材料snapshot和当前证明。目录ABA、准备权限或身份恢复都保留STALE，不允许旧回应复活；企业原流程REOPEN、原专员重新REVIEW后才可显式REBIND与新回应。旧无来源证明审核不自动升级。没有新增身份列、Grant、trigger或身份写入。

修复后同次冻结回归 **484PASS/0FAIL/0ERROR/0SKIP，208.19秒，2WARN**，覆盖原资料/事实/补正/准备确认/本地关闭/迁移/演示兼容、18个原页面HTTP/Chromium异议用例、独审原7反例及目录ABA/旧审核无证明的新负例。301个源码/测试/脚本hash零漂移。此前各轮不叠加宣称全仓；Windows和完整42AT/EX仍未签收。修复后独立复核尚待交付终态。

[修复冻结机器记录](evidence/material-objections/review-fix/verification.json)、[日志](evidence/material-objections/review-fix/review-fix-frozen.log)、[JUnit](evidence/material-objections/review-fix/review-fix-frozen.xml)、[301源码hash](evidence/material-objections/review-fix/review-fix-source.json)、[当前页面截图](evidence/material-objections/review-fix/browser-output.json)。旧证据保留原字节，新轮证据单独归档。
