# 原离线规划尝试的失败与未知恢复

基线交付 `387a9c2f96275d32785d777c354984aeedda14e7`，最终冻结源码 `a26a6c84e67bc85d8a24651886261fdb8c605e83`，524 文件。中间源码 `e3812fa167e6047ee8c61d785150d6af576d0e6a` 尚未进行正式冻结验收；下述最终窗只签收最终源码。

真实自有 PG/API 独审发现：原 OUTCOME_UNKNOWN 的 TRANSPORT_OUTCOME_UNKNOWN 只改持久 state 为 FAILED_SAFE，恢复 GET 原来返回200；原页面会清未知句柄。独审原单例1 FAIL与原 NodeVM 产品窗6 PASS/2 FAIL保全。它们分别证明服务端及坏响应的实际页面边界，不是纯静态推断。另有漏导入导致的驱动8 FAIL；在进入HTTP场景前失败，不能当产品缺陷证据。

现在 STARTED 必须 outcome=null 且字段精确三项；OUTCOME_UNKNOWN 只接受三个明确未知码；FAILED_SAFE 只接受有限且互斥的已审拒绝码；COMMITTED 必须 VALIDATED 与精确四项原证明。新的未审错误码保守归 PLANNER_OUTCOME_UNKNOWN，不能断言安全拒绝。候选列表/原 key 恢复与直接预核/原 ADOPT 使用同一严格语义，损坏记录返回409，GET不修复或改历史；V1/V2及正常V3仍兼容。

原页面核精确十项 attempt 字段、原 key/actor/CaseRun上下文、状态与 outcome、原900秒UTC窗口及实际年月日往返。额外字段、非法日期、坏flags或未知结果被改称安全拒绝，都保留原 opaque，不能自动POST。过期PENDING仍未知，不据浏览器时钟判失败。READ撤权清私有视图，保留原 opaque，不能以它恢复权限。

完整原 HTML 的 NodeVM 驱动通过真实按钮 onclick 验原write lease：同页/冷页安全拒绝只有显式GET核实后清句柄，用户另行明确生成才使用新key；未知/在途结果重复GET仅用原key，按钮即使被调用也不POST。实际PG单state损坏、桥接仅坏响应、extra字段、Feb30无效日期、撤READ、撤EXEC留PENDING均覆盖。桥接坏响应仅用于显式故障注入，真实API结果另行记录，不伪装成provider返回。

最终主测18完整模块 **530 PASS、0 FAIL/ERROR/SKIP、2 WARN、303.697秒、exit0**。隔离最终原页另窗 **10 PASS、0 FAIL/ERROR/SKIP、2 WARN、9.863秒、exit0**；独审7完整模块另窗 **141 PASS、0 FAIL/ERROR/SKIP、2 WARN、77.456秒、exit0**。根21旧候选页、4假规划页、26总览页与10恢复页已包含在530内；独审21旧页和10恢复页已包含在141内，各窗不相加。源524首尾零漂移、隔离加载路径已核，详见[validation](evidence/proposal-planner-recovery-20261014/postformat-validation.json)、[隔离验收](evidence/proposal-planner-recovery-20261014/isolated-tests/postformat-final-review.json)、[独审](evidence/proposal-planner-recovery-20261014/independent/review.json)。正式结果不覆盖开发窗。

默认应用和真实provider继续关闭。本片只修证明/页面恢复，没有新的模型调用、Grant/registry、凭据配置、权限扩大或业务执行入口。真实provider请求、provider凭据读取、LIVE配额写入、规划路径gateway执行各0。实际 owned Linux PG与进程内ASGI、全原HTML离线NodeVM可验；真实模型、浏览器渲染、Windows/native、完整PR0/T02/AT、生产迁移/部署均NOT RUN。历史浏览器与prepare明确拒绝没有重试，两原approval false/null及原SHA256保持。

根开发69PASS窗未设置既有四个假规划页的evidence参数，更新了上一任务同名开发阳性raw；上一任务公开冻结归档及其失败原件未变。本任务最终所有页使用独立目录，不声称历史runtime阳性件全部未变。

独审中途文件 consumer-extra-red 命名原拟用于红窗，实际因同步修复早于进程 import，XML为10 PASS；不把文件名当失败证据。根开发69PASS、隔离8PASS和扩展10PASS也各自只为开发窗。[307件原/导出索引](evidence/proposal-planner-recovery-20261014/export-index.json)保存hash、字节及11实际临时session的22处精确替换；失败原件不改。before-format中的重复件是归档副本，不是额外测试窗。最终源码与报告diff-check各exit0；相对基线的完整归档diff-check exit2，12处原pytest E空白尾空格保留，详见[检查metadata](evidence/proposal-planner-recovery-20261014/diff-check.json)。检查stdout私有保全不递归导出，metadata/归档审查在307索引外。

格式核查发现原新驱动EOF空行（源码diff-check exit2），源码480的530/141/10正式通过窗原样保留。仅清该测试驱动空行后重新冻结a26，其余523文件、所有生产代码逐字不变；最终仍按新SHA重新跑实际完整窗，不沿用旧结果。a26本地提交一并带入已暂存180草稿归档和报告，未在完成最终复核前推送；最终正常补交文档/归档，并审历史blob脱敏，不重写提交或强推。

当前补交stage的diff-check exit0；相对387基线完整归档仍exit2/12处，因为原失败空白已在a26历史。二者范围不同，不能以stage0替代完整归档2；公开检查metadata已分别记录。

[最终归档独审](evidence/proposal-planner-recovery-20261014/archive-review.json) PASS：307原/导出逐字核对、11临时session22处精确替换、524源零漂移与实际XML统计一致；另核a26历史183公共doc blobs，其中180旧草稿导出逐件按保全raw重算，全部无实际session残留。无需重写历史。审查及重跑脚本在307索引外，无剩余源码或归档阻断。
