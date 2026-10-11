# F2-T07 冻结归档独立终核

**LIMITED_PASS**：本次有限归档核验没有未解决阻断，不签收正式 AT35/F2、全仓或浏览器验收。

源码 `b5ea90ac9b366b015b43c426ad94b72faf7c8b72`；406 清单 SHA256 `fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf`。冻结 `docs/F2/evidence/f2-t07-full-chain-20261011/archive-manifest.json` SHA256 `54d7a30888aeae04ea94b651fe3b46a092317dd217b790e7ae70d2676cf9f325`。

167 件私有原件与导出逐一核验，44,378,098 原 bytes、10,223,512 导出 bytes、39 件 gzip。原/导出/解压 payload 的 hash 与长度、脱敏计数及逐字节策略复现全相等。121 JSON、12 JUnit、12 精确白名单静态程序与 22 stdout/报告的闭合集合未变。12 静态程序与此前逐件审查的 path/SHA 白名单相同；没有覆盖原件或重建 core。

12 JUnit 的全部 testcase 身份、属性、状态、异常类型和 duration，以及除 hostname 外的 suite 属性/计数/时间全保留。JSON 字面 SHA/test ID 未改；凭据键规则及实际 Bearer/PG URI/执行绝对路径扫描无未解决敏感项。二次审计粗扫描的 61 个 opaque 候选实际是 48 个自有 UUID 数据库名：48 个 `$.owned_postgres.database` 与 13 个 `$.traces[index].owned_database`。它们严格匹配 `fixture_[0-9a-f]{32}`，与原 UUID 创建票据/删除护栏对应。修正只限这两精确字段及完整值形状，没有泛化放行 opaque 或凭据。

## 实际窗口

| 完整窗口 | PASS | FAIL | ERROR | SKIP | exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| 根 full-complete-final，39 模块 | 1570 | 0 | 0 | 1 | 0 |
| 根 goal-results-pg-complete，1 模块 | 44 | 0 | 0 | 0 | 0 |
| 原独审 frozen-complete | 10 | 0 | 0 | 0 | 0 |
| 原独审 frozen-probes | 3 | 0 | 0 | 0 | 0 |

根 argv 与 JUnit classname 精确对应 39 与 1 个完整模块；两窗 ID 不重叠，共 40 模块、1615 unique IDs、1614 PASS/1 SKIP，**不是一个 40 模块进程**。原 1561 IDs 全保留、根完整窗新增 10，另 44 项为独立目标产物 PG 完整模块。根进程 1523.631 秒、JUnit 1521.392 秒，PG 专项进程 65.906 秒。独审 13 项保持两个独立窗口，不加入根总数。

原 first/second/third/proof-check 的 22 次 FAIL、10 个唯一 ID 保持原失败，逐项对上最终根完整窗同 ID PASS。它们是驱动投影、可选列及资源成员查询 oracle 修正；原 405 产品源码零变。中断 full-final 保留 17 JUnit PASS、exit1、owned SIGINT 原因与原 teardown KeyError，不算完整回归。误选浏览器模块保留 `::tests.test_case_goal_results_browser` 收集 ERROR/exit2/缺 playwright 原诊断；没有执行测试或启动浏览器，未安装或重试，不以不同 PG ID 冒称修复。唯一最终 SKIP 是 `test_native_windows_file_backend_gate`，仍要求 Windows11 x64。

授权只读 `git cat-file --batch` 实际核齐 b5ea90a 的 406 commit blob，与冻结清单及工作区逐字节一致，树 `4a0d5385b6b590b6ad79e84dd73360bd4f3892b8`。原 405 源与旧三段取消归档 428 文件全集无新增/缺失/字节变化。旧已签业务 REVIEW 未改，其当时根窗口 RUNNING 字段原样保留，本报告另签后来完成结果。

## 原审计诊断

| 审计窗口 | exit | 实际含义 |
| --- | ---: | --- |
| audit-core-first | 1 | 原三件 post-core 声明后新增第四件 doc-link-check，集合断言失败 |
| audit-core-corrected | 1 | 61 个上述 UUID 数据库标识被粗 opaque 判定误报 |
| audit-core-final | 0 | 固定 167 集合、字节、策略、结果及旧档案核验通过 |
| source-commit-byte-proof | 1 | 只支持 loose-object 的初版遇到 pack 中旧 blob，FileNotFoundError |
| source-commit-byte-proof-corrected | 0 | 授权只读 cat-file 实际核齐 406 commit@execution/[REDACTED]/ 字节 |

五窗原 checker/argv/PID/UTC/时长/退出码与合并 stdout/stderr 保存。另一次报告组装 exit1 是通用 static-literal 正则匹配到审计程序自身扫描 regex 定义；报告当时尚未创建。其完整工具 stderr 作**事后精确转录**，provenance 明确 stdin 文件 **NOT_CAPTURED**，不冒称完整原 stdin 已存。以上为新增审计程序/组装 oracle，不计产品 testcase FAIL、不视为访问拒绝、不把旧退出改为 PASS。初版/修正版/原 findings 均保留。

全量 staged whitespace 真实 exit2：60 项都精确来自 first 导出 stdout 与 JUnit，各 30 个原 `E` 空白标记；已按报错行号读取核实。原行未裁剪，Git whitespace 配置未改。作者文档/helper/清单与已提交测试/合同专项 exit0；全量不宣称 PASS。

## 支持出口和范围

根 post-core 支持精确固定四件：`archive-export-run.json`、`root-core-check.json`、`staged-whitespace-verification.json`、`doc-link-check.json`，path/hash/内容及 JSON 凭据规则已核。新增独审支持与五件审计 `.py` 的精确出口批准另列 `archive-audit-support-inventory.json`；代码仅按所列精确内容/SHA 原样出口，日志/报告与 metadata 沿 accepted policy 脱敏。未知后缀、未来文件不自动批准；未来交付/远端记录另列 post-stage，不倒入本 core/闭集。

A 新普通 Run 无 assignment、默认批准入口关闭，正式合法生产批准/分派授权合同仍 BLOCKED；B owner-only 合成 assignment 是明示链外 setup，不是零 setup 正式 AT35。原 AT01–35 定义保留、整项 NOT_RUN。人工确认由合成驱动完成，真实模型、人类试点、外部效果、浏览器和干净 Windows 未签；历史 Chromium 管理员导航拒绝保持零重试，旧 Case_count0 原因仍 UNCONFIRMED。

独审未修改产品/原测试/docs/Git 或旧报告，未追加业务/PG/浏览器运行。正常交付 commit、push 与远端对比尚为根唯一写入者后续工作，本报告不提前签交付结果。
