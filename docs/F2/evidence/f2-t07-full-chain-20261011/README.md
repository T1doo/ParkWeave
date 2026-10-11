# T07 整链有限交付证据

已验证普通生产 API、自有 PostgreSQL、独立 CLI worker 和新普通 API 子进程的合成整链；人工 REVIEW/CONFIRM/SUBMIT/ACK/VERIFY 由测试驱动。冻结源 `b5ea90ac9b366b015b43c426ad94b72faf7c8b72`，406 文件清单 SHA `fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf`；原405源零变。报告见 [T07FullChain.md](../../T07FullChain.md)，实施前合同见 [T07FullChainContract.md](../../T07FullChainContract.md)。

| 实际窗口 | PASS | FAIL | ERROR | SKIP | exit | 绑定源 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 根39模块 full-complete-final | 1570 | 0 | 0 | 1 | 0 | b5ea90a完整SHA如上 |
| 根目标产物PG完整专项 | 44 | 0 | 0 | 0 | 0 | 同源/406零漂移 |
| 独审完整新模块 | 10 | 0 | 0 | 0 | 0 | 同源/406零漂移 |
| 独审额外反例 | 3 | 0 | 0 | 0 | 0 | 同源/406零漂移 |

根前两窗无重复test ID，共40完整模块、1615 unique IDs，1614 PASS / 0 FAIL / 0 ERROR / 1旧Windows SKIP；不是一个40模块进程。原1561 IDs无缺失，新整链10 IDs另列。根39进程1523.631秒、2026-10-11T16:42:39.785894+00:00至2026-10-11T17:08:03.423022+00:00，独立PG专项65.906秒。独审13是不同独立窗口结果，不加入根数量。`driver_sha256`在各run记录是运行捕获程序SHA；具体测试源码绑定独立406清单，不误作同一字段。

A普通新Run实际无assignment、默认批准入口关闭，分派403且不自动赋权；正式生产首用仍BLOCKED。B在原owner-only合成assignment前提之外只用原API/worker推进业务，精确核对材料/资源关联/接单/回执/本地记录及VERIFY事件的同Case/Run/版本/hash。两次成功新输入来自同fixture-a；其他企业/园区/角色是拒绝矩阵。原AT01–35整项NOT_RUN，有限部分映射不构成正式AT35/F2/PR0-alpha签收。

## 最终原件对应的导出入口

- [根39实际进程/源码/计数记录](raw/full-complete-final-run.sanitized.json)；[根39完整JUnit](raw/full-complete-final.sanitized.xml)；[根39完整stdout/stderr](raw/full-complete-final.sanitized.log)。
- [PG专项实际进程记录](raw/goal-results-pg-complete-run.sanitized.json)；[PG专项完整JUnit](raw/goal-results-pg-complete.sanitized.xml)。
- [最终406源码清单](raw/final-frozen-source-manifest.sanitized.json)；[10项整链实际场景及trace索引](raw/final-scenario-map.sanitized.json)；[原35项完整定义与本窗精确finite test IDs](raw/original-at-finite-map.sanitized.json)。
- [独立有限业务审查](raw/independent-review/REVIEW.sanitized.md)；[独审机器记录](raw/independent-review/review.sanitized.json)；[独审后来证据附记](raw/independent-review/POST_SIGNOFF_EVIDENCE_NOTE.sanitized.md)。这些签署保持各自当时根窗口RUNNING状态；最终完整根结果由后续归档审计另核，不改旧签署。
- [22原失败执行/10唯一ID到最终同IDPASS对应表](raw/failure-to-final-map.sanitized.json)；[浏览器误选收集ERROR原诊断及未捕获字段说明](raw/browser-selection-collection-diagnostic.sanitized.json)；[首完整窗owned SIGINT停止原因](raw/full-first-window-stop.sanitized.json)。
- [原428归档文件集合/字节基线](raw/accepted-archive-byte-baseline.sanitized.json)；[独审精确12件静态程序白名单冻结](raw/static-approval-freeze.sanitized.json)。

原失败窗口分别是 first 0P/10F、second 9P/1F、third 1P/9F、proof-check 1P/2F；修正子窗2P、较早完整新模块10P单列。错误均为驱动oracle，不扩生产投影/权限。首根完整窗口17P/0F/0E/0S但exit1和teardown KeyError，为中断未完成，不计完整PASS。误选Chromium模块导致收集exit2、0P/0F/1ERROR/0S，在模块顶层缺playwright而未执行测试/启动浏览器；未安装或重试该模块，仍NOT_RUN，不声称不同PG test ID修复该ERROR。

## 导出与边界

[archive-manifest.json](archive-manifest.json)一次冻结167个输入，原件44,378,098 bytes；每项同时保留original hash/length、导出hash/length和解压payload hash/length、redaction计数及JUnit原状态。`.sanitized`明确是导出副本；超过512000 bytes以mtime0 gzip无损压缩，读取先解压。所有原私有输入未改写。JSON保留literal SHA/test IDs；stdout/JUnit沿原accepted policy；静态程序必须逐件审查后的精确path/hash批准。新归档审计/导出进程记录不倒塞进已冻结core，另列audit-support清单。

原before-accept/before-receipt/after-receipt三段取消归档428文件集合/字节不变。真实模型/付费调用、生产部署/迁移、新Grant/信任登记、凭据/网络配置、权限扩大、强推/保护分支修改均0。历史Chromium data:导航ERR_BLOCKED_BY_ADMINISTRATOR保持；浏览器启动/替代导航重试0。模型、正式服务发布、原生Windows、真实工作台/园区/线下效果NOT_RUN；历史Case_count0根因仍UNCONFIRMED，本次成功建Case不消除旧原因未知。

`build_archive.py`记录原一次性冻结导出程序；不要在已存在的core上重运行覆盖。复核读取清单逐件校验导出hash，并解压gzip核payload hash；具有当前私有原件时另核original hash。最终交付commit和正常push远端核对在任务收口后实际记录，不由本README预签。

本轮全量staged `git diff --cached --check`实际exit2，60项仅为first原FAIL stdout/JUnit的`E`空行尾随空白（两个清单内原导出文件）；作者文档/清单/导出程序和已提交测试/合同专项检查exit0。原失败标记、payload hash与签署不裁剪，未更改Git whitespace配置；全量检查不冒称PASS，实际stdout/stderr另列audit-support。

最终固定核心独审签署为 [ARCHIVE_AUDIT](audit-support/independent-review/archive-audit/ARCHIVE_AUDIT.sanitized.md)，[机器报告](audit-support/independent-review/archive-audit/ARCHIVE_AUDIT.sanitized.json)核实后来完成的根窗口与 commit/source 字节。有限归档结论 LIMITED_PASS，正式普通新 Run 授权合同仍 BLOCKED。

[独立审计附件清单](audit-support-manifest.json)另冻30件：25件独审原件、4件根 post-core 原件和1件精确库存描述。五件新审计程序按逐件批准的 path/SHA 原字节出口；三次审计程序 exit1 和一次组装 exit1 的原诊断均保留，其中组装 stderr 为事后精确工具输出转录、stdin NOT_CAPTURED。它们不计产品 testcase FAIL，也不倒入167件 core。原签署与核心清单保持原字节，未来交付/Git记录另列 post-stage。
