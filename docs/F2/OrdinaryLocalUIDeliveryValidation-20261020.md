# 普通合成本地演示：实际操作闭环

2026-10-20 在指定 Linux 环境从 `6b5551085c5d6a328b64c275d3e8c22a3cfd72c0` 执行既有[普通演示说明](../demo/OrdinarySyntheticDemo.md)，补齐此前没有实际执行的普通页面写入链。产品、测试、SQL、迁移、权限合同和启动器均未修改；本提交只记录此次技术演示及证据。

原产品 V1 §4、§12.4 和阶段计划允许先完成可运行的本地软件及合成技术验证。真实园区资料、正式来源接入、Windows 和用户人工验收分别保留各自缺项，不作为本次 Linux 本地演示的总前置；本次结果也不代表完整 PR0 或固定 AT 全部通过。

## 环境与执行方式

先核对单写入者、干净 Git、实际 HEAD、默认网络和远端147个分支。当前主机 `9ff7ff919935` 与此前165项窗口的 `cd8f6963ff1b` 不同，不能假定旧进程或临时库仍在。未知 `.git/codex-index-refresh.lock` 原样保留。使用已有 Python 3.12.14、Node、pgserver 0.1.4、psycopg 3.3.6 和原依赖，没有安装或升级依赖。

实际执行一次原 `ordinary_synthetic_demo setup`，1.574秒成功，创建全新独立私有合成集群，初始 Run、Case、preparation、dispatch、receipt 和 Run assignment 均为0。六个主体、两园区企业范围与权限仅由已授权的原合成初始化建立；后续 serve 不补权、不迁移、不修复状态。没有读取真实 DSN、调用真实模型或外部业务服务。

Node VM 只提供机械 DOM 接口，加载完整原 `src/parkweave/web.html`，调用原表单和按钮处理函数，实际通过 loopback HTTP、原 worker 和 PostgreSQL 落库。复用 `tests/ordinary_case_goal_record_pack_html.js` 的 DOM/fetch 支持，启用原新建资料入口所需的轮询计时器；关闭、P5核验及下载使用该原脚本，列表按精确事项选择。资源 HOLD、组合确认和事项关联通过原 API 明确提交。没有复制或重做业务决策算法。

**此处没有真实浏览器点击证据。** 本环境已有 `/usr/bin/chromium`，一次 `chromium_sandbox=True` 启动实际失败：SUID sandbox helper 配置不满足要求，另有 crashpad database 错误；浏览器中止。没有修改权限、关闭 sandbox、安装浏览器或继续重试。当前受阻动作是本环境 Chromium 页面操作，其余原页面/实际 HTTP/PG 项已完成；这不是自动批准审查拒绝。

## 三件实际新事项

| 普通输入 | 实际闭环结果 | 原 TXT 的 SHA256 |
| --- | --- | --- |
| 第一园区企业：维护事项 | 新 Run/Case → 新资料 → 人工审核与企业确认 → 原确定性计划 ADOPT → 两资源关联 → 派发/本人接单 → 人工回执/企业核对 → 独立 P1–P5 VERIFY → 本地关闭/导出 | `3acf8ebe4bdfecb77bb713953781c06dd9c8c8dad17d51c03d99c4b87a5e7acc` |
| 同企业：培训事项 | 独立新建并完成同一链；首事项结果结构和值未变 | `ea297ed93bb29028f965206556b2ccbdd680624cf96581f13c05d782c39d430e` |
| 第二园区企业：新诉求 | 从自身空事项列表独立新建并完成同一链 | `1473a017a0f24ca20b4513a929d94bdd9e07707a869adb77fcdfa908b03d0993` |

三件最终均为 `LOCAL_OUTPUTS_VERIFIED`，五个当前目标全部保留，本地记录 `LOCAL_RECORD_CLOSED`。`case_goal_completed=false`、资格未评估、外部受理未提交、线下履约无证据；本地关闭不代表现实履约。

首事项关闭后正常停止本次自有 API、worker 和 PG，再使用同一私有状态目录执行原 serve。API/worker/PG PID 分别从 `1451/1452/1442` 变为 `1710/1711/1701`。冷读没有业务 POST，导出 TXT 字节和规范化 pack hash 均与停机前一致；原 goal-results JSON 结构和值一致，然后才办理第二事项。

两方向分别读取对方资料、目标结果、dispatch、receipt、资源组合，共15次，全部403。三组 Run/Case/preparation/plan/dispatch/receipt UUID 各自独立。最终 Run、Case、preparation、dispatch、receipt各3条，Run assignment为0；原 authority 全量相等，状态 marker 未修改。自有服务正常停止，无 postmaster.pid、无 stop-unconfirmed；私有资料、库和日志保留。

全部21次页面脚本调用共记录571次实际请求：514 GET、57 POST；57次 POST 全部返回成功（3×202、9×201、45×200）。35个页面 GET `/fact-clarifications` 返回403，这是初始化未授予字段权限的可选面板，保持拒绝；没有补Grant。其余页面请求成功。另有12次明确资源 API POST（各3组两HOLD、组合确认、事项关联），均201且请求键各异；它们及控制器读取不混入571次页面请求。最终续办、冷启动、第二和第三事项窗口47.323秒；该耗时不包括前述初始化和失败脚本窗口。各窗口不相加为测试用例数。

## 保留失败与有限续办

这次场景驱动有三处自身错误，未发现对应产品缺陷，没有因此修改产品：

1. v1误将原状态 `LOCAL_CONFIRMED` 写成 `LOCALLY_CONFIRMED`，在原 CONFIRM 已返回200后断言失败。保留原写入，续办先 GET 核对，未重建或重发确认。
2. v2配置字典重复传入 label，在调用页面或业务 API 前失败。
3. v3以事项标题定位执行者行，但原接口使用统一回执标题；只完成列表 GET，未发送 ACCEPT。原 OFFER 已201成功，保留其 UUID、请求键和首次截止。v4通过原按钮打开并核对 dispatch UUID，在原截止前对同一邀请接单，未重新 OFFER、延长截止或删除历史。

原 stdout/stderr、traceback、各版脚本和中间 JSON 均保留。成功续办没有抹去失败文件，没有重发任何结果未知的业务 POST。

## 原165项失败的因果边界

重新读取此前原 XML 和原始栈，不重跑165刷数：`target_read` 的 call 失败发生于 `prepared → ADD` 的原2秒连接超时，早于目标READ撤销和另派；其 teardown DROP 触发原5秒 statement timeout。原 `WITHDRAW[material]` 在 fixture GRANTS 建权阶段连接超时并清理超时。没有这些场景的业务断言失败证据；原失败时的连接/活动/锁采样缺失，当前是另一实例，**根因仍未确立**。

原完整窗口仍是165唯一项、163 PASS / 1 FAIL / 2 ERROR / 0 SKIP；XML166条含同例call与teardown两条。此前同冻结原顺序49项一次有界诊断复验全通过、观测1,880次连接正常关闭，未触发失败采样，不能反推原失败原因。此次三事项成功也不替换原165项状态。没有改原2秒/5秒预算、连接实现或清理逻辑。详见[原验证记录](OrdinaryUnacceptedRedispatchValidation-20261019.md)。

## 可核对证据及剩余输入

提交的[脱敏执行摘要](evidence/ordinary-local-ui-20261020.json)包含三组实际UUID、阶段请求/成功写入、跨域拒绝、TXT和pack hash、进程代际及原件hash。原件在忽略目录 `.runtime/pr0-local-ui-execution-20261020/`：`setup-result.json`、`walk-result.json`、`ui-01`至`ui-21` stdout/stderr、四份TXT、服务日志、`browser-probe.json`、`prior165-failure-location.json` 和各失败版本。私有会话文件没有提交。

执行产品内容绑定 SHA256：`b5a552984d5cb9b812ea385352ee184a4d8a72ab53b17cf29efc6422fbe692c4`。本地状态仍绑定该产品内容，普通启动不重建已完成事项。

有限只读独审通过，未发现需分级的问题：独立离线核对100个原件hash、三件事项六组UUID、四份TXT及冷启动字节/pack、571次请求和57个唯一键页面POST、另列12次资源POST、15次跨域403及失败续办描述。独审没有写文件、产品import、网络请求、会话读取或动态独测；权限和marker未变依据原驱动及执行成功断言，没有独立连接数据库复测。

后续复现这个合成演示只需原说明规定的 Linux/Python/PG 依赖、全新 setup 或本次已有私有目录与原会话、可用 loopback 端口；不需真实园区或正式来源适配器。真实浏览器技术验证尚需具有正常 sandbox 的可用浏览器环境。用户人工操作记录、Windows11干净原生安装/停启/关机复现、原固定正式AT和真实业务仍未验。

实际授权业务运行另需合法受限数据库与schema、已有真实主体/会话及当前 PREPARE/REVIEW_ASSIGNED/执行权限、合法 preparation_catalog 与当前资料来源和修订；不从本次合成状态取得这些输入。Native permit/writer继续默认拒绝，正式 provider/来源接线和 IsolatedPlanApproval 边界未改。真实系统连接属于原F4–F6的独立门，不据此阻止本地技术演示，也不据本次演示宣称已经完成真实接入或整个项目。
