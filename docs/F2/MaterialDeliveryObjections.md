# 资料交付异议候选

基线 `88403af18b95b361114b303c3fae636f286d91b4`，合同先冻结于 `aaabf758687b4d16dd3eec4b06fc6fb9361bf5fb`。沿原 V1 F2-T07、产品§5.5和PR0缺口实现现有合成双槽资料的企业反馈；[冻结合同与实现细化](MaterialDeliveryObjectionContract.md)。资料文本包产出功能未重做，既有资料包证据保留原字节。

企业提出资料交付异议→原获派专员说明回应→企业明确接受回应或仍未解决。专员回应不自动关闭；资料、诉求、人工审核来源或权限世代变化保留历史，须企业明确重绑定当前来源，再由原专员回应和企业复核。每事件绑定Case/Run/资料revision、双槽ID/version/正文hash、服务、请求版本、原主体及原回应UUID。资料确认及本地记录关闭拒绝未决/失效异议，不写Case完成。实际Case仍依原合成合同，资格、现实履约与外部受理不由本功能判定。

追加事件和资料revision同一PG事务；应用角色不能UPDATE/DELETE事件。写入CAS、原键原body重放、不同body冲突、当前撤权先于重放；恢复GET只读按原actor/key核对。浏览器仅存最多8个Case/key/actor/revision句柄，不存会话、正文或请求体；未知句柄不自动到期清除，NOT_OBSERVED保留锁；403清私有视图，身份/Case/generation迟到响应丢弃。

schema26仅扩展现有事件CHECK；现有roles/grants文件不变，新建隔离Linux数据库需原已验证creation receipt，未自动升级既有库。现有native receipt仍止于schema25，其原路径无新异议写入。Linux演示启动器接受既有25/26，fresh fixture为26；原25不补发建库receipt或自动升级。需要在冻结合同内安装的新候选只用于合成环境。

最终冻结专项 **72PASS/0FAIL/0ERROR/0SKIP，86.02秒，2WARN**，含41 API/PG、18真实HTTP/Chromium和13原材料文本包兼容用例。包括原HTTP API进程终止/重启及页面冷刷新后GET恢复、撤权和恢复世代、越权/跨园区企业/同企业另一Case、实际正文篡改、资料/诉求/目录/重开换版、并发同/异键、迟到读写响应、事件UPDATE/DELETE权限拒绝、事务回滚、隐私/注入/损坏存储负例及320/390/1200宽度。300个冻结源码/测试/脚本文件零漂移。此前相关回归416PASS属于当时源码，其后权限绑定和页面收紧由最终72项验证，不重复相加宣称全仓。

全仓尚未通过且没有完整终态：首次私有runner收集13个导入错误，修正运行路径后普通单进程全仓测量出现共享fixture错误/既有Windows Setup模拟失败，主动中断，完整日志保全。两个相关文件在候选与独立detached原基线均为 **34PASS/13SKIP/1FAIL**，同一失败 `test_setup_checks_created_config_and_sessions_without_acl_repair`，不在本任务修改Windows accounting/ACL。原native、Windows、42 AT/EX、F1/F2、R4/LIVE都未签收。候选不部署、不合开发分支，普通push后交独立只读审查。

[机器记录](evidence/material-objections/verification.json)、[冻结专项日志](evidence/material-objections/targeted-frozen.log)、[JUnit](evidence/material-objections/targeted-frozen.xml)、[源码hash](evidence/material-objections/frozen-source.json)、[API重启证据](evidence/material-objections/api-restart.json)、[截图索引](evidence/material-objections/browser-output.json)。失败原始日志放在忽略的 `.runtime/material-objections`，公开记录保留各轮计数和原件hash，不发布fixture会话值。独立审查结果和最终远端SHA在交付终态补充。
