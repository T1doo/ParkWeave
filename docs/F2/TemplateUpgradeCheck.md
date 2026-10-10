# F2-T06 / §7.5 逐实例模板升级检查

从已核dev `b496f6a4da7022c10c906ff722fd3279f4536f71` 独立候选推进，main保持 `31e7acb7e53bb1ab6465b9daae59de28757f7583`。先读原产品§7.5和F2覆盖表、真实模板不可变Release与consumer桥，发现缺逐实例升级检查。合同先提交4b82672，真实首轮又发现旧consumer采纳键与原计划历史证明不兼容，先补7cc83a7合同后修。

最小切片只检查本人原模板实例的新旧修订及现有Case/资料/请求/计划/锁/实际依赖，提供兼容、需重验、人工锁冲突、破坏性拒绝与变更原因。GET只读，不写原计划失效观察。原superseded/withdrawn Release仅用于精确历史证明，目标必须同模板、当前审核发布头且来源有效；提交前真实PG等待后再复核目标期限。兼容不等于Case完成，未决stage不会自动解决。

明确选择只在独立.upgrade.candidate.sqlite3追加不可变事件：KEEP_CURRENT；兼容或需重验可REQUEST_RECHECK；仅兼容可ACK_COMPATIBLE。人工锁冲突与破坏性拒绝只可保留旧版，在原入口由原角色明确处理。最多64事件，CAS检查源hash/审计revision，幂等绑定原key/body与actor/企业/DB/实例/Case及旧新Release/hash。重复是历史事件，不当作当前适用性。页面未知只原key GET核对，NOT_OBSERVED不重写；冷页重新认证、提供原实例/key只读恢复，身份/实例/目标切换清私有状态，迟到响应不覆盖新上下文。未自动保存令牌或恢复未知写正文。

原旧实例Release、consumer阶段key/body、Case、合成占用、资源回执、本人接单与业务回执/人工锁/历史都保留；选择不重新执行、迁移、回滚、撤销预约或写原业务。只显式精确组合到原默认关闭的隔离工厂，无生产路由、PG迁移、新Grant/角色或凭证复制。新建consumer stage规范键tc_<UUIDhex>_<stage>；原历史仅精确首ADOPT旧tc:<canonical UUID>:ADOPT_PLAN被原证明识别，仍验原owner/Case/Run/采纳指纹；升级checker还绑定精确原instance UUID，不改旧event字节。

最终精确源码 `076625a357fe9631cccb923132dad3cd224db48e`；335冻结源码，manifest SHA256 `da4de8663fe847f132a9e4b48c780bd32dd3a5ee98221688906306aad774e018`。

根最终同SHA完整10相关模块318PASS，0FAIL/ERROR/SKIP，JUnit256.680s、受控258.567393s，自然exit0。精确独审LIMITED_PASS：同10完整模块318PASS/253.948s（255.493853s），额外真实HTTP/PG API15PASS/26.948s（28.295560s）与真实Chromium/HTTP/PG页面7PASS/26.829s（27.951830s）；三窗都自然exit0且无失败、错误或跳过，分别记账，不冒称一次总数或全仓。独审原报告SHA256 `b56dba7dd1a98cf69f1072b303d46babc79298b6da684ad8289848126738e732`，335首尾零漂移且Git干净。原两条reason/choice body锚负例实际409；真实64最后槽双HTTP并发、跨模板/园区、legacy边界、Case锁等待跨期限、已撤回旧版历史、页面在途未知→冷热GET NOT_OBSERVED→原POST迟到单次提交→GET COMMITTED，以及迟到响应与撤权隐私负例独立复验。原所有PG业务/权限行（独立authorization_audit除外）及consumer/template字节不变；选择不构成资料复核、重新采纳或升级执行。

首轮精确e830虽root完整10模块314PASS/JUnit241.987s（受控243.650584s）、独立10模块314PASS/243.488s（245.166064s）及独立修正probe13PASS/21.847s（23.108415s），但实际末事件reason/choice与payload/hash被改而原body fp保持的2项FAIL/4.272s（5.123189s）使其BLOCKED，未单独整合。独立probe初窗13 ERROR/0FAIL/0PASS/1.040s（1.737999s）是私有探针未注册原conftest fixture，原窗保全、修probe另窗通过，不转签。先补1542ec5合同后076625a只从历史check/choice/reason/原revision重建Selection fp并核对独立body锚及固定类型/FLAGS，正常历史不改写。旧335源hash与BLOCKED原报告保留，报告SHA256 `75b21b6007b0ed031621aaa4671ff4a7c252772004745807f071d164ffa14853`；旧PASS不抵消FAIL或转签新源码。

初始开发22项实际21FAIL/1PASS/16.26s，旧真实consumer key导致原历史证明409及后续测试KeyError，原日志/XML保全。修后22PASS/18.11s；扩展含实际HTTP/Chromium冷页/迟到响应31PASS/33.04s；补实际PG Case锁等待跨期限与精确legacy原LOCK2PASS/3.21s。原body锚修复开发5PASS/6.71s（含实际64事件）；不同源状态与开发窗口保留各自范围，不拼算最终验收；最终成绩另列。诊断AST白名单最终1448只是安全诊断标识，不能称Windows验收。

保证只为固定合成模板/原consumer的检查观察与选择记录；不是跨PG/模板SQLite/consumerSQLite的迁移原子性或未来持续有效承诺。可信非协作DBowner篡改全部锚/禁用触发器为排除边界。正式ServiceRelease/ParkInstance、生产作者/独立审批/维护/安装权限、迁移执行及在途兼容/回退业务责任、完整新企业F2链仍缺。真实业务/政策/预约履约/通知/分享/模型/Case完成未实现或未授权；全仓、完整AT/EX、Windows未验收，ServerCI未查询，旧a823a28未迁移。原Approval实际新API/自有PG重启仅已消费证明GET恢复范围保持；未消费Approval新进程写入口仍关闭403，旧cap PG重启后拒绝，不复制/重签凭证。

精确076源码先普通推送候选 `candidate/template-upgrade-check-20261010`，获审时实际远端candidate076、dev仍b496、main仍31e7，335源码无漂移。获审后只新增文档/安全证据，再显式非强制fetch核对远端并正常快进/普通push开发分支。最终证据与dev整合SHA、实际远端复核另见整合记录，避免文档记录自身提交SHA。旧e830当时BLOCKED、未单独整合；最后只快进最终获审后代，不把旧故障成绩转签。

入口：[实施前合同](TemplateUpgradeCheckContract.md)、[机器核验](evidence/template-upgrade/verification.json)、[独立审查](evidence/template-upgrade/independent-review/report.json)、[正常整合](TemplateUpgradeCheckIntegration.md)、[工件hash](evidence/template-upgrade/artifact-hashes.json)。失败原始日志/XML仅在忽略.runtime中私有保全，不推送；安全通过工件导出。
