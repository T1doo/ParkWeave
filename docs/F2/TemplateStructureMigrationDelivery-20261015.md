# 有限模板结构增强交付

基线 `aceb01d2351a695fa1358d91ea944615ba4a468c`；源码与测试冻结 `60ed07b10c854c25ec575c5769c5ad539f7a6ba9`。沿原 F2-T06 / F3-T03 与产品 V1 §7.5、§8，在原开发分支 `dev/f2-worklist-entry-isolation-20261013` 推进。详细边界见[冻结合同](TemplateStructureMigrationContract-20261015.md)。本片不是通用结构迁移，也不改签正式 AT25–27。

支持前向模板版本严格追加既有注册必需目标及其编译闭包；新增义务必须已在原 Case 的初始请求、采用证明与计划内，且底层当前全部 VERIFIED。原六目标、coverage、步骤 ID、初始 ADOPT、历史和业务事实不改。新增 Case 目标/节点、删除、重排原目标、任意依赖边、schema/service/registry/contracts 变化及不完整原计划均明确拒绝。

新增目标映射与闭包节点沿原图向下游传播：P1→P5 影响 P2–P5；原 P1–P4→P5 仅 P5；新增 P4 别名影响 P4/P5。实际 source 同时变化则全部重验。仅受影响人工锁冲突，保留步骤的锁与 hash 保持；采用前预留一次采用、受影响 VERIFY 及全部现存锁 UNLOCK 的 64 事件额度，不足时零业务写入。

企业先检查、记录选择，再通过独立勾选和原因确认 `/apply-structure` 的 13 字段请求；原 `/apply` 的 11 字段请求与 9 键事件不放宽。结构事件增加独立封闭证明，从原 Case 与前后 Release 重算，并把原请求 hash、实际存储证明 hash 和重算 hash 严格绑定。每次结构事件仅给实际影响步骤累计来源 token；后续说明修订与多跳增强保留它们。同 key 同参回原结果、异参冲突，丢响应只 GET 原 key。热/冷页面使用完整原 HTML 核回执，错误回复、撤权与迟到状态不能解除 pending。

事件与有效模板绑定在原 PG plan 同事务保存，资源、预约、ACCEPT、回执与 Run 成功事实不变。沿原 parent→dispatch→Case→source 锁序。独审确认实际 UPDATE 后跨目标到期点的缺陷，现将目标 SourceLease 登记到原 guarded connection，在真实 commit 重核；结构、原来源与原说明三分支均实际拒绝并全回滚，只允许原生 DENIED 审计追加。没有新 Grant、registry、生产迁移或业务反向回滚。

| 最终同版完整窗口 | PASS | FAIL | ERROR | SKIP | WARN | 秒（原生测试） | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 根任务 44 模块受影响回归 | 1430 | 0 | 0 | 0 | 2 | 1235.14 | 0 |
| 独测单一进程 | 81 | 0 | 0 | 0 | 2 | 295.394 | 0 |
| 独审 14 模块 LIMITED_PASS | 302 | 0 | 0 | 0 | 2 | 553.74 | 0 |

三窗均绑定上述完整源码 SHA，分列不相加。根任务与独审 583 个源码/测试/脚本/pyproject 文件前后零漂移，独审与 Git 对象逐字节一致、74 个加载模块均来自私树；独测 155 产品文件和六个执行测试模块零漂移。原 1355 项全部保留并 PASS，另增 75 项；仅原模板测试一个既有 uuid4 参数标识在固定函数/固定字段内规范化比较，原测试源码 hash 未改，其余原 ID 精确一致。原 V1、分阶段计划和正式验收规格 hash 均未改。

根任务、独审和归档独审分别核离线 wheel 全部 155/155 产品文件字节，missing/extra/changed 均 0。根任务 wheel SHA256 `caf4975162a7c212153422909f83744d8bb173d3c8f92c24e2ed5b7694996fb1`；独审独立打包 SHA256 `7ba34d7d897650d8f4a81a3724ad8b6246c59f8e9457b266d9e5cf2a4f3f3213`。构建未联网、未安装或部署。

真实产品红例包括安全结构不支持、布尔/浮点证明类型替换、实际 UPDATE 后目标到期仍提交；修后均有独立真实 PG 绿例。错误 fixture、过强 DENIED 审计 oracle、私树缺 Git、系统 Python 缺依赖、旧 b8 部分窗口退出 2 等另列，原日志/XML/exit 不删除、不改签。实施者额外 86 项私有调试窗实际 83 PASS / 3 FAIL，后续定位命令因 `exec-server transport disconnected` 在创建进程时被拒，已停止且未重做；该窗不计 PASS。归档独审仅判读既存 XML，确认三项断言遗漏原审计行合法的 `recorded_at` 列；导出时尚未归因的原始 ledger 也保持不改。根、独测与独审以各自独立原案例验证回滚，不以这些绿窗覆盖原 FAIL。另一次 `/proc/1660512/cwd` 读取 PermissionError 原件保留，该读取未重试或扩大权限。

[证据索引](evidence/template-structure-migration-20261015/export-index.json) SHA256 `9297a61d8c39fe918ebd13a87010284d47a9b90bf16ea79f2c6c95b988d2cfc7`。[独立归档审计](TemplateStructureMigrationArchiveAudit-20261015.json) PASS/exit0：263/263 原件与副本完整，missing/extra/哈希/字节偏差均0；8740个实际临时fixture值仅2处精确替换，其余字节保持，敏感残留及未知候选均0。审计补充 helper 首次误找证据文件名产生 FileNotFound/exit1，完整 traceback 与修后 exit0 分列保留于[独立审计附件](evidence/template-structure-archive-audit-20261015/audit-deliverables.json)，不计作产品测试。主索引与原件未为补充审改写。

源码和交付报告的 `git diff --check` 退出0；原样归档的同一检查退出2，共66项诊断全部位于已审计证据路径。保留原 pytest 日志/XML/脚本空白，不清理或重写这些字节；完整诊断及范围核验保存在 `.runtime/template-structure-migration-20261015/delivery-archive-diff.txt` 与 `delivery-precommit-check.json`。

范围为自有 Linux 临时合成 PostgreSQL、进程内 ASGI 与完整 HTML 离线 NodeVM。浏览器、Windows 原生、真实模型/付费调用、正式治理、生产迁移及部署 NOT RUN；原 Chromium `data:` 的 `ERR_BLOCKED_BY_ADMINISTRATOR` 与 GraphQL `Forbidden` 路线均未重试。源代码与交付提交之间的 src/tests/scripts/pyproject 差异必须为 0，最终交付 SHA、远端及 clean/ahead/behind 核验见交付回复。

下一步仍按原方案评估更广结构差异；需要改 Case 目标/节点/合同的迁移继续拒绝，正式 AT 与原生验收另门，不通过本片工程结果升格。
