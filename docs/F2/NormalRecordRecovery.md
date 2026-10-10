# 正常本地记录全进程停启后的只读找回

先行合同 `cfcdb94027dae7249e6152f5645d516ae8eb6337`，运行源码 `4217e63c14259ddc679405c6228da948b877354c`，实际测试候选 `377a2bbe5c854359353967da11f71607e838ade4`。基于已审 P5 开发基线 `9f4aef7bea7000a102c1748ef0c70b69597087b7`。本片沿主方案 F1-T03/T04、F2-T05 与 AT01/17/19/34/35，完成 Linux 合成正常本地建单记录的冷启发现/读取；不把目录读取称完整 AT17 或 Windows 原生停启/关机。

正常页面协同区增加明确“找回我的本地办理记录”和分页/选择。GET `/api/runs` 在原 READ、active、角色及 park/org/owner 交集内，仅列本人已有 SYNTHETIC `case.create` Run，最多 50、默认 20。只读事务响应只含编号/状态/版本/namespace，游标按 UUID 升序，无私人正文、total 或自动重放。选择只走原 Run GET。身份/Run/tab 切换立即清目录；当前 Run 403 会失效在途旧目录 200，并清原输出。会话和目录只在内存，冷页面由本人重新输入原会话。

全停启实证：首次自有空 `/tmp` PG 按原合法 creation receipt/migrate/roles/CLI seed 初始化，由正常 configured_app 与连续 worker 建单并 drain；随后正常停止 API/worker/Chromium/PG，初始化发行父进程也退出。按 PID+create_time 核实所有原代际已不存在后，新子进程重启同一 PG data、普通 configured_app/worker 和冷浏览器。PG/API/worker PID 与 PG 启动代际变化；原 DB system_identifier/OID 及原 0600 会话文件保持；restart migrate/seed 均为 0、registry 空、proof_transport=false。三宽度实际目录/原 Run GET 均 200，同一完整原 Run/Case/Operation JSON，业务与身份/权限逻辑行 hash 不变，恢复页面仅 GET。原 Denied handler 的四条授权审计允许且单独计数；不声称 PG 物理 WAL/control 字节不变。

独审 **LIMITED_PASS**：[独立安全报告](evidence/normal-record-recovery/independent-report-safe.json) SHA256 `7908ee0cc8eadac1cf72e4424138c415c8f9cf969694541bc37ee2b9600b0df3`。其15接受窗实际924个唯一节点、923 PASS、1 Windows SKIP、0 FAIL/ERROR，collection/JUnit missing/extra/duplicates均0；覆盖根相同13范围919节点，另4项自写API和1项真实Run403/迟到目录200页面反例。独立核2650自有PID代际均已退出，371源字节/权限零漂移。根与独审成绩各自取实际窗口，[根安全报告](evidence/normal-record-recovery/root-report-safe.json)不充当独审成绩。根 13 窗：919 个唯一 collection/JUnit 节点匹配，918 PASS、1 SKIP、0 FAIL/ERROR，JUnit 521.564 秒；每窗正常退出，自有 PID 代际末核为空。各范围互不冒充全仓：

| 范围 | 根实际结果 |
| --- | --- |
| 全进程停启 | 1 PASS |
| 新目录 API/页面 | 24 PASS |
| 原 P5 及 29 相关模块 | 744 PASS |
| 原 worker/facts/authorization | 61 PASS、1 Windows SKIP |
| AT17 原 artifact/rate/fence 相关四节点 | 4 PASS |
| 原生生命周期/launcher/diagnostics 工程合同 | 84 PASS |

唯一 SKIP 为原 `test_native_windows_file_backend_gate`：Windows reparse points/ADS/ACL/clean lifecycle require Windows11 x64。Linux 工程合同测试不代替真实 Windows 关机；完整 AT17、全仓及真实模型/履约仍 NOT_RUN。

源码 [371 路径清单](evidence/normal-record-recovery/source-freeze.json) SHA256 `7eb0ca748996fc5fb26d3aafe2a0c94f01d630d215687d8a4eb7bd98a9224a67`；相对原 367 路径，仅 API/Store/页面及原 diagnostics 白名单变更，新增四个测试/生命周期 helper 文件。roles、依赖、SQL 及原预览协议/资格不改，无新业务 schema、Grant、凭据、审批或真实履约。工作区唯一后续主写入者，测试资源串行；没有重新供应实例、改 main/force push/部署/安全配置。

失败原件逐窗私有保全：三次全停启观察器失败（原 CSP 拒绝字符串 eval、原折叠 details 未展开两次）、两次页面观察器事件处理失败、真实 Run403 后迟到目录200隐私缺陷复现，以及冻结首候选漏11可信测试白名单（100P1F，旧候选 NOT_ACCEPTED）、新虚拟环境尚未安装本项目导致原白名单子进程 ModuleNotFoundError（1ERROR）。保持原 CSP、原隐私断言及环境过滤；只修实际403清理、登记原可信测试名、按 pyproject 固定 setuptools80.9.0 在项目虚拟环境/cache 注册同源码 editable 包。新源码重新冻结/根实测；历史 P5 的 KeyError、Cannot fork/EAGAIN、夹具 import 与旧通过范围公开原报告 hash 不变，旧实例没有恢复或读写，短探针不替代验收。公开仅安全分类/计数/hash，日志/XML/HTTP/会话/截图仅留私有 .runtime 和自有 /tmp。

## 仍未闭合的影子历史资格

正常已持久化 READ 身份允许普通记录读取；它不构成 P4/P5 组合历史或 managed Run access 的原 issued registry/PG-start-bound 证明。默认冷 Store 的这些路径仍403，不保留原发行者/代理、复制/重签 proof 或自动续权。P1/P2 独立读取的原目录/数据库/source/当前能力合同不同，其默认正常启动读取及 P3 其它类别资格未在本片验收，不能一概称依赖原 issuer。

要继续影子历史冷启，须先单独决定并审查已有合法核验主体、可信数据/namespace/source 与当前租户/权限绑定、撤权/到期/数据库替换时的拒绝、完整性和明确只读能力，以及是否允许持久资格。合同缺口保持 OPEN；完成的普通产品读取不借该缺口扩权。原 P5 关闭仍 WAITING_CONFIRMATION 而非 FULFILLED。

## 截图路由保全限制

本次根的原29模块未重定向其默认 OUT；独审早期观察器也遗漏该重定向，后续已仅修自有plugin隔离输出。共享默认 browser 目录同名临时截图及观察 JSON 摘要可能被覆盖，不能声称历史根截图或每个窗口共享产物始终保留。公开历史报告/hash维持原时点，不用当前同名产物冒充旧原件。新normal目录与全停启截图在各窗唯一自有 /tmp，未共享；原窗口日志/JUnit/资源/节点记录独立保存。独审本轮实际截图私有封存及上一轮已隔离的独审截图另核hash；不删共享图片、不循环重拍假冒旧截图。

独审 native 工程合同首窗36PASS1FAIL保全，PG原日志证实自有Unix socket路径超过107字节，私有runner只缩短唯一/tmp前缀；原PG参数/TMPDIR/断言/guard/源码不改，单次完整受影响窗84PASS后再实际额外4API/1页面。原失败和PG日志hash见独审报告，不纳入接受总数。上一轮独审40张隔离截图missing/changed均0，原223e1d62报告字节不变；本轮早期共享截图22PNG和4JSON仅封存实际当时本轮产物，不冒称旧原件。
