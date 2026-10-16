# 兼容服务定义修订与全新事项

从交付 `3ddae44f271cdb1c024ef987fbb601de5fecb6b2` 接续。最终冻结源码 **`b01025cc0be4a5a5a9b956a7e8cb45bb74a44de4`**，开发分支 `dev/f3-compatible-release-new-case-20261016`。落实原主方案 §7.5、F3-T03/AT-27 的有限隔离版本流程；不是正式 AT-27 或业务发布验收。

## 实际产品变化

保留原 TemplateEngine 草稿、独立审核、候选发布、不可变 Release 与原 journal；增加明确 `compatible_publication_only=True` 的进程级隔离模式。默认模式、旧 TemplateConfig/Command 序列化和旧幂等指纹保持。此模式不是仓库级持久治理：受信代码仍可显式重开旧默认 engine，不能据本片声称全局禁止不兼容发布。生产 app 不挂候选发布路由，未新增数据库权限或 HTTP 目录管理权。

模式仅允许同 scope 最近原 Release 与当前 REVIEWED 修订在来源、目标、步骤、参数、编译注册表和授权合同完全相同，仅 name/description 展示文字变化。原 Release 必须有正确不可变 hash、有效期限及可支持合同；缺失、撤回、未知、陈旧、非前向或不支持字段变化拒绝。来源/目标/步骤即使未来可能兼容，也按本有限合同拒绝，不推断一般语义兼容。

原页面先 GET 当前已审修订的兼容预检，展示原 Release、草稿/审核/合同摘要与判定，另勾明确确认后生成新隔离候选 Release。原 engine.command 在原 SQLite BEGIN IMMEDIATE 事务内重算并校验 preflight hash 与严格布尔 True；确认、摘要和原发布命令同指纹绑定，新事件保存确认与预检证明。严格模式中的旧裸发布入口也拒绝，无“UI 勾选即授权”。旧 journal/schema 不迁移；没有新增通用 Case 迁移器。

新发布只保留不含正文/token的 actor/scope/key/hash/revision 恢复句柄；发送前存储逐字读回，未知结果与重新打开页面只 GET 原 key。NOT_OBSERVED、坏证明、撤 READ、存储失败或恢复期间句柄被替换均保留并拒解锁，不自动重发或换 key。历史 COMMITTED 不表示当前来源仍可用。预检的 scope、hash、边界标志与页面代次都检查，迟到结果不能恢复已清状态。

## 新 Release 到新事项的真实执行边界

真实 Linux Chromium 页面执行：原 RETURN_DRAFT→SAVE_DRAFT→SUBMIT→独立 REVIEW→发布主体读取 COMPATIBLE 预检→明确勾选发布；真实 ASGI 已提交后故意丢弃响应，再 reload，只 GET 原 key 核实 COMMITTED。其后走原产品页面的新目录、独立新诉求/材料、五个 cold 阶段、GENERATE、未确认 ADOPT 无 POST、明确确认 ADOPT；新计划选中三个新 ServiceRelease 引用并保留六目标/P1–P5结构。浏览器到新明确 ADOPT 为止，没有端用户浏览器全程履约的声称。

原 catalog 的 register/bind/retire 没有 HTTP 写入口，仍由已签发自有 fixture owner 明确执行。原 RETURN_DRAFT 会把旧候选标为 SUPERSEDED，旧 Release 的 payload/hash不改；原目录中失去当前来源的旧条目必须另走原明确 withdraw，不能忽略 UNKNOWN 后自动上新。新 Release 及 revision2 实例再经原 register/bind 准入。这些都是明确夹具操作，不是自动 rollout，也不是正式业务发布。

本批的旧 Case 是原 schema33 已 ACCEPT、尚无回执的独立事项，未取消、未迁移、未复活。新事项具有新 Run/Case/preparation/材料/计划/批准，旧 Case 全部业务行、历史、责任、已接单记录、旧批准与 CONFIRMED 占用保持；旧 Release 的当前可用性与不可变历史分列。新占用使用容量2中剩余1单位，不自动释放旧1单位。

新 API/ASGI/自有 PostgreSQL 组合实际执行到：新输入→资料独立 REVIEW/CONFIRM→新 ADOPT/P1→另行 PROPOSE/APPROVE→版本与容量重验的资源交付/P2→丢弃回执后的原 key GET。旧批准串用于新事项拒绝；新旧 Release/hash 串用、旧配置、批准后配置或容量变化、EXECUTE/PREPARE/READ 撤权均按各原门拒绝，无部分资源确认。

自有初态与角色配置、原 local worker、新 Run executor assignment、浏览器段前置资料 REVIEW/CONFIRM、issued IsolatedPlanApproval 证明桥，以及离线选择规划替身均明确为夹具。批准本身仍调用原 PROPOSE/APPROVE，不是直接写批准事实。资源/权限变化是受控故障夹具，不能当新应用赋权。本批新严格 Release 未执行 P3–P5、新接单/回执/本地结案或六目标完成/工作清单完成；旧默认 full_chain 完整回归不能继承成新严格流程全履约证据。

## 最终验证

698个受控输入匹配 Git blob；全部正式主窗口实际执行 HEAD 均为 `b01025cc0be4a5a5a9b956a7e8cb45bb74a44de4`，冻结后只归档和文档。两个无交集窗口共 **10个完整直接相关模块、227唯一项 PASS，0 FAIL/ERROR/SKIP**；同进程 collection 与原 JUnit 精确相等，不归一或拼接节点。

| 完整窗口 | 模块 | PASS | 范围 |
| --- | ---: | ---: | --- |
| final-new | 3 | 40 | publication24（SQLite/ASGI）、new_case8（自有PG/ASGI）、Chromium8（1正向及7拒绝） |
| final-old | 7 | 187 | 原候选36、完整模板链4、模板规划8、目录39、cold consumer12、审批55、旧升级33 |
| 独立 frozen-v2 | 2 | 32 | 与主窗完全重叠，24SQLite/ASGI与8PG/ASGI；不累加 |

真实浏览器负向包括迟到编辑/换身份、存储写失败、坏 COMMITTED DTO 故障注入、真实 NOT_OBSERVED、真实 READ 撤权和恢复期间替换句柄。坏 DTO 是对真实响应的客户端故障注入，不是后端生成了坏证明。未用固定 sleep 代替业务通过门，原断言和超时预算保留。

最终源码独审 PASS，无范围内阻断；独审还核旧配置/命令 AST及默认指纹不变、严格事务门、无迁移/新授权、每个 DOM shim 实例真实 Set 语义。独审纯层探针另列，不累加227。独测32项同最终SHA通过，698输入前后零漂移。

## 失败与原件保全

开发 chain-v1 的8FAIL包括原目录 UNKNOWN 拒绝及无用 Input 导入：新 fixture 补原明确退休旧目录命令，未让 UNKNOWN 成功。chain-browser-v2 为1PASS/1FAIL，fixture input_field含空格被原 schema 正确拒绝，只修合成标识。开发38PASS窗与最后2探针不并入最终227。

首冻结 `957c2752d25b1e95dcd5d5110527a0266877ee4b` 原187窗为185PASS/2FAIL：旧 NodeVM Element 缺 classList，进入原页面清理后计划视图未建立，原断言失败。仅补测试 DOM 的 Set-backed add/remove/contains；相较首冻结只有该JS变化，全部 src 字节保持，未改业务断言/超时预算。最终 SHA 从头完整重跑227，不把旧957成绩搬作最终通过。原两测试日志、XML与此前独审都保留。

独测首轮24PASS/8ERROR，原证明拒绝 workspace 下的临时 PostgreSQL；没有改 TMPDIR/证明或绕拒绝。按原真实 /tmp 自有夹具规则做一次安全重试通过，随后最终SHA又完整32通过。最初的数字1/1.0确认与迟到预检缺陷由独审纯探针复现；失败探针与修复复验都保留。所有失败原始文件按hash留存，公开档不发布私有令牌或未完整脱敏的错误正文。

## 归档与剩余范围

[主档索引](evidence/compatible-release-new-case-20261016/index.json)、[范围和逐窗终门](evidence/compatible-release-new-case-20261016/release-new-root/final-gate.json)、[失败原件账本](evidence/compatible-release-new-case-20261016/release-new-root/failure-ledger.json)、[冻结独审](evidence/compatible-release-new-case-20261016/release-new-review/frozen-v2/review.md)、[独立归档审计](evidence/compatible-release-new-case-20261016-audit/final-audit.json)。45个公档文件、43 raw/export配对、514777字节，830完整登记合成值扫描残留0；本次选定公档无需替换（0处）；200份新 primary 文件封存。旧1151+4463+168+104原件及上一独立audit seal全量只读核验无漂移。原始路径全集在私有manifest，公档以路径hash标识，脱敏不改变原件。

上一批剩96模块/原基线2400节点，本批补跑其中5模块，原历史节点精确36+4+8+39+33=120；当前剩 **91模块/2280原基线节点** 未重跑。只改变本批实际覆盖口径，不把历史批次与本批227相加冒称全仓通过。

下一关键路径为更广定义/来源语义兼容、正式治理与批准主体、独立新版本的P3–P5业务验证，以及正式AT固定初态与覆盖。一般在途迁移、取消后复活、回滚业务事实、F5恢复都未实现；不据本切片扩大范围。Windows/原生与真实设备、正式AT、真实模型B0–B2、生产、外部部署/业务发布、issued双桥跨进程恢复及本分支CI未执行。已有CI工作流限历史分支且无dispatch，未改工作流触发。真实模型调用0，无新增费用、凭据、网络/安全权限、强推、main修改或部署。
