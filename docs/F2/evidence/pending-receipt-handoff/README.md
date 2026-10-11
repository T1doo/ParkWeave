# 尚未回执事项的明确交接：限定交付证据

本轮业务是原产品§5.5“园区专员可调整责任方，但必须说明原因”的待回执人工事项交接。完整当前模块/T01–T07剩余核查、原ENG032断点与行为边界见[业务说明](../../PendingReceiptHandoff.md)。这28项修改由本线程根作者产生；需求复现始于2026-10-11 09:49 UTC，原工作树文件mtime为09:52:50–10:05:04，原路径/状态/时间/hash清单保存在[root inventory](root/original-working-tree-inventory.json)。没有另外的仓库写入者，已有独审只在自己的私有/tmp写探针。

业务基线为已签收通知分页提交 `4a0ec78ec7d554204e6fea66a75afd26242c3cd5`，初冻28项源码为 `a5ea0c61ebef365527aac9f570494c61cec1fac9`，最终修复源码为 **`0418146b7c2024577e4bdaba509ec5fd9b6c433d`**，直接父a5。分支 `dev/f2-pending-receipt-handoff-20261011`。本目录所在交付提交仅新增证据，直接父为041；实际推送结果以正常Git回执及随后远端查询为准。旧通知68作者/25独审签收不计作本片新验收。

## 实际交付行为

已接单的普通SYNTHETIC事项须仍为当前资料、AWAITING_RECEIPT且从未提交任何回执。原获派专员明确选择已有同Run合法访问的新执行者并说明原因；事务追加原REOFFER事件/通知outbox，旧步骤马上只读且原字节保留。新方须独立ACCEPT才创建新receipt UUID，随后人工SUBMIT、企业ACK。Case目标仍未完成，不复制回执、授予权限或自动履约。新方拒绝/专员撤回不会复活旧步骤；已提交/重开过回执、陈旧资料、隔离路径和旧schema均拒绝。

schema29只调整同材料的receipt代际约束，并以offer→receipt唯一约束防止共用步骤；保留原legacy CREATE拒绝和新材料恢复规则。只沿原fresh-owned Linux测试夹具证据迁移，未迁移生产或native数据库。页面复用原表单，最多8条/绝对24h保存actor/dispatch/preparation/key/期限；无理由正文或token。先保存句柄再POST，未知结果禁新动作，只GET原key并重核当前授权，刷新/迟到响应不自动重发。

## 最终同一源码的实际验证

| 窗口 | PASS | FAIL/ERROR/SKIP | 证据 |
| --- | ---: | --- | --- |
| 作者核心 | 335 | 0/0/0 | [日志](root/final-core.log)、[JUnit](root/final-core.xml)、[命令/时间/分布](root/final-core-run.json) |
| 作者schema29兼容 | 327 | 0/0/0 | [日志](root/final-compat.log)、[JUnit](root/final-compat.xml)、[命令/时间/分布](root/final-compat-run.json) |
| 本轮新增独审 | 51 | 0/0/0 | [报告](independent/REVIEW.md)、[日志](independent/final-0418146b.log)、[JUnit](independent/final-0418146b.xml) |

作者总662，核心含新交接PG/ASGI47+交接NodeVM9，原分派53/回执36/材料换代46/通知32/分页26+10/Linux启动10/澄清66。兼容327覆盖材料bundle/机会、Case生命周期、受控方案、异议/复用/诉求、资源组合/占位，以及受影响的授权、worker与lifecycle迁移用例；实际wheel包含029，并在安装wheel后新owned数据库迁移重放。两窗口各2条既有Starlette/XDG环境warning，未跳过测试。源码在运行中及结束后不变；[作者manifest](root/manifest.json)记录389份源码/脚本/测试/pyproject文件hash及最终testcase清单。新增独审51是32 PG/ASGI+4 JSONB类型完整性控+15离线VM，全部对041重新运行，不复用a5或旧分页成绩。[独审manifest](independent/manifest.json)逐文件hash已由根核对，最终JUnit计数/类型分布与报告吻合。

根使用原owned Linux startup用例做了临时loopback API健康/清理验证；其余业务验证为owned PG/进程内ASGI及离线NodeVM。独审完全没有HTTP listener。NodeVM执行实际原页面JS配DOM/fetch/storage/时钟doubles，没有浏览器、截图或外部HTTP。独审真实观察竞争PG backend的Lock等待，两种先后顺序均一提交一冲突；并验证9字段lineage篡改、当前GET撤权、代际选择、数据库唯一约束、全部7种隔离附件、句柄篡改/绝对期限与身份ABA迟到响应。

## 保全失败与独审修复

作者预冻结基线collection 1 ERROR后修夹具导入，真实缺口1 FAIL；初轮131为129 PASS/2 outbox计数oracle FAIL；第二轮256为255 PASS/1旧corrupt-pointer造坏数据先被新SQL唯一约束挡住；第三轮331为330 PASS/1未来版本marker仍写当前29。原始日志/XML留私有，未覆盖；[来源与失败索引](root/source-and-failure-provenance-final.json)保留原字节hash、准确数量/名称及说明。修正oracle、保留旧完整性断言的一次性fixture造坏方式及future30均已复验。

a5冻结核心331通过，但类型证明尚有缺陷，不能替代最终041签收。a5兼容初窗326 PASS/1 FAIL为声明的`setuptools==80.9.0`在私有测试venv缺失，精确错误为`ModuleNotFoundError: No module named 'setuptools'`；[原日志](root/frozen-compat.log)/[JUnit](root/frozen-compat.xml)原文保留。仅补齐原固定测试依赖后wheel单例通过，最终041兼容327重新全部通过，源码/凭据/代理/权限配置没有为安装依赖改动。

独审初轮有outbox外键挡住造坏数据及VM断言计数两个探针错误，类型控又有一次collection错误。最初float硬写4.0与实际5不同，是探针布置FAIL，首次即时误报已经明确更正。动态float(old)之后，a5的三个负控实际从JSONB读出bool/float，再实际ACCEPT得到HTTP200，确认Python等值将true/1及5.0/5视为相等的完整性问题。041限定核handoff原ACCEPT及REOFFER必需字段的类型和值，最终三控及新增原ACCEPT浮点控都409且事务无变。没有将owner造坏权限当成外部越权证明。独审原失败字节全部留私有，[分类/hash历史](independent/a5-failure-and-run-history.json)区分真实产品负控失败与探针错误。

## 限定范围

仅签普通SYNTHETIC人工待回执交接。原浏览器 `data: ERR_BLOCKED_BY_ADMINISTRATOR` 保持，不启动浏览器、不换URL或工具重试。没有真实模型、真实外部通知/受理、真实履约、生产/native新授权、持久信任登记、部署或main/既有dev整合。原executor_receipts、通知、角色权限、隔离执行/preview/信任文件逐字节保留，根14份与独审23份保护文件对照已记录。不签完整AT/F2、Windows、真实浏览器或多worker部署。原T01–T07剩余的正式业务来源/ServiceRelease/权威资源/模型/实际履约等依赖在业务说明中列明，未以本片或空接口替代。
