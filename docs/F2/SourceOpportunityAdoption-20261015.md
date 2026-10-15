# 来源机会到原计划明确采纳（2026-10-15）

本轮补齐 F3-T02/T03 在原合成注册 Case 中的来源变更闭环：同 Case 手动导入/刷新真实来源，绑定当前计划及版本，查看受影响与保留步骤，由本人明确执行原局部 ADOPT，随后用原 VERIFY 核对受影响实际产物，再读取原六目标证据和工作清单。这里的实际来源指自有合成数据库中的当前记录，现实政策来源仍未验收。原 IMPORT/REFRESH/IGNORE/WITHDRAW 没有重做，REFRESH 仍只刷新来源卡。

最终冻结源码为 `4c163fe23d8a841ece7b796e40e35511d70a0797`；完整业务回归执行于 `6b8da028182d9b4ce35996eaaef2e6a78cff0666`。两者之间只有诊断读取器、名单及诊断测试 3 文件变化，全部 `src` 字节相同，开发分支 `dev/f3-source-adoption-20261015`。基线 `6a035ef18f9db54c3563610fe27cd2e27f235747`，原 main `31e7acb7e53bb1ab6465b9daae59de28757f7583` 仅只读核对。源码冻结后的提交只归档本轮证据和更新文档；交付提交及推送核对见最终返回的实际 SHA。本报告的通过范围不延伸到全仓或正式 AT。

## 行为与保持规则

新增只读 `GET /api/preparations/{preparation_id}/opportunities/{card_id}/plan-revision`。预览绑定当前 actor、Case/Run、原计划 UUID/revision、机会 ledger/card/version/basis 和真实逐步骤来源指纹，返回直接变化、受影响、保留的稳定 step UUID、阻塞原因及原 ADOPT 正文。提示标题、note、reason 不参与事实或权限计算；必须存在旧本人 VERIFY/已采纳来源，不能把 UNKNOWN 解释成可采纳差异。

原 `POST .../service-case-plan` 的 ADOPT 入口仅在 `local_revision: true` 时接受有界 `opportunity_proof`。服务端在原事务及准备事项锁内重新核对全部原权限、请求/资料/目录/计划版本、原六目标、来源和卡片。按既有依赖声明传播影响，原 plan/step UUID、P1–P5、正文、历史及未受影响锁证据保持；受影响旧核验快照作为历史保留，当前产物必须原 VERIFY。请求、服务或目录合同变化仍走原明确替换。

实际来源的有界 PostgreSQL 行版本参与预览校验，拒绝预览后 A→B→A 恢复旧值、撤权、撤回、失效或晚到操作。超过集合边界时拒绝；原 64 事件上限同时预留受影响核验及全部活动锁的原 UNLOCK 额度。受影响人工锁阻塞 ADOPT，先由原 owner 明确原 UNLOCK；解锁不等于重验。未受影响锁不解锁、不重写。

页面把预览、明确确认和原命令连接起来。页面打开/导航/选择卡片不写；用户阅读分区、勾选确认并填写原采纳说明后才发原 ADOPT。丢回执沿用原 11 字段、640 字节、8 槽、24h 不透明句柄，保存的句柄不含正文、正文指纹或会话 token；重新认证后冷恢复只 GET 原键，不自动重发。身份、Case、草稿、版本与 ABA 世代隔离，当前 403 清除私有视图，迟到答复不能恢复旧视图或清掉新操作。新入口复用原未决操作门禁。

实现同时修复一个实际兼容回归：原 `/opportunities/recovery/{request_key}` 必须先于新增动态卡片路由注册，原合法 request key `plan-revision` 冷 GET 继续 200，不能被误解析成 card_id 而返回 422。根侧和独审均有真实 PostgreSQL RED→GREEN 记录。

## 当前冻结验证

| 窗口 | 精确范围 | 最终结果 |
| --- | --- | --- |
| 根完整受影响回归 | 52 个完整模块，包含上次交付模板/结构兼容、P1–P5、资源/回执/生命周期/取消/原生访问受限接口、机会、原恢复、目标、工作清单及新源码/UI测试 | 1661 PASS / 27 FAIL / 0 ERROR / 0 SKIP；1944.03 秒，原失败保留，下述分窗补验覆盖修复 |
| 最终 SHA 独测 | 独立 API 答案与五条完整原 HTML→真实 HTTP→ASGI→自有 PostgreSQL 流程 | 20 PASS / 0 FAIL / 0 ERROR / 0 SKIP；105.64 秒 |
| 业务冻结独审回归（6b8da028） | 10 个完整模块：来源采纳、原步骤/恢复/锁/局部修订/目标/机会、模板 legacy/独立迁移/结构独测 | 351 PASS / 0 FAIL / 0 ERROR / 0 SKIP；837.62 秒 |
| 业务冻结独审新增探针（6b8da028） | 无实际变化的提示、两次采纳历史、撤回后旧恢复/新拒绝、最终来源复读、EXECUTE 撤权、来源采纳与结构升级两个顺序、原恢复键兼容 | 8 PASS；53.28 秒 |
| 最终 SHA 根诊断链回归 | 8 个完整模块：diagnostics、summary publication、safe annotations、regression shards、minimal observations、lifecycle diagnostics、Windows CI preparation、CI cleanup | 297 PASS / 8 SKIP / 0 FAIL / 0 ERROR；13.24 秒，同次 collection/JUnit 305 节点精确一致 |
| 最终 SHA 独审 | 独立复跑上述诊断链与新增边界探针，并核实旧业务回归涉及字节与最终源码的同一性 | 297 PASS / 8 SKIP / 0 FAIL / 0 ERROR；14.67 秒；另 6 项实际文件边界检查通过 |

这些窗口分别计数，有重叠，不能相加称全仓或单次全部通过。旧业务 351/8 实际执行 SHA 为 6b8da028，最终独审以逐文件同一性延续其业务范围，未声称重跑于新 SHA。根首窗其中两项失败是旧测试在业务断言通过后写入缺失证据目录时报 FileNotFoundError；仅创建 `.runtime/template-hold-20261014`，源码/测试不变，完整 `test_template_hold.py` 另窗 7 PASS / 9.34 秒（见 [补验记录](evidence/source-opportunity-adoption-20261015/source-adoption/hold-recheck.json)）。首窗另 25 项为本轮刷新名单暴露的真实诊断读取器字节上限回归，修复后完整诊断链重新冻结验证。首窗原统计保留，不改写为单窗 1688 PASS。新环境复现原命令前须创建该既有证据输出目录；本轮没有为此修改产品或测试源码。旧根和业务独审各核对 592 个文件的前后字节；其中 587 个为 Git 跟踪的 src/tests/scripts/pyproject，另 5 个是当前 editable 安装的既有 egg-info 元数据。独测显式核对 587 个 Git 跟踪路径；各自执行窗口内均无源码漂移；新冻结诊断链与独测另核对 587 个跟踪路径。精确 argv、模块、JUnit 节点、退出码及哈希见[证据索引](evidence/source-opportunity-adoption-20261015/index.json)。诊断测试 ID 按原规则从 2190 补齐到 2612，无删除；新增 422 中 21 个是本轮新函数，其余 401 为已有测试的遗漏登记，不改变工作流、预算或权限。名单 286,539 字节超过原读取器 256 KiB，本轮仅引入独立 `MAX_ALLOWLIST_BYTES=512*1024`；原 schema、3000 条/256 字符/正则/去重及所有公开输出限制不变。真实文件恰好 512 KiB 接受，超一字节拒绝且公开诊断仅常量拒绝，不泄漏私有 XML。

完整原 HTML 的 JavaScript 在 Node VM 中执行，DOM/fetch 表面由测试夹具提供，业务请求实际走 HTTP、ASGI、自有 PostgreSQL。它不是实际浏览器验收。最终独测 positive 20 项检查/24 次请求/7 POST，lost 25 项检查/28 次请求/7 POST；冷 GET 没有重复 POST。late_draft、late_identity_aba、late_denied 各 12 项检查，最后一条真实 403 后不回填。各窗口确切 trace 路径在[独测结果](evidence/source-opportunity-adoption-20261015/source-adoption-independent/freeze-4c163fe-result.json)中；其中 `.runtime/` 前缀可相对本证据目录对应导出文件读取。

## 失败记录与归档

本轮 214 份证据已逐件导出，原件/导出哈希与大小、结构和确定性去敏检查通过；[根归档核对](evidence/source-opportunity-adoption-20261015/audit.json)、[独立归档核对及审计失败附录](evidence/source-opportunity-adoption-audit-20261015/archive-independent-audit.json)与[最终冻结独审](evidence/source-opportunity-adoption-20261015/source-adoption-review/REVIEW-4c163fe2.md)分别记录范围。私有原件保留。公开导出仅遮蔽合成会话值及 pytest fixture repr（包括截断值）；XML 先解析后处理文本、JSON 递归处理字符串，保留结构。索引逐件给出原件/导出 SHA-256、字节数及替换计数。两个继承模板测试使用共享的私有去敏值列表，本轮不把该列表称为各窗口独占证据；pytest stdout、JUnit、PG 数据根和源码清单分别隔离。此前 263 个已提交归档文件的导出字节/大小核对通过，旧环境私有原件不在本环境，未声称重审其原件。

| 历史窗口 | 结果与原因 | 后续 |
| --- | --- | --- |
| 独测 initial | 4 setup ERROR：PG basetemp 位于不符合既有创建收据合同的 `.runtime` | 改用 `/tmp` 自有库，保留拒绝日志 |
| 独测 html-first / api-first | 2 FAIL：DOM double 未正确显示 impact 节点；4 FAIL：未先建立旧 VERIFY 来源的 fixture | 修正独立夹具，不降低业务门禁 |
| 独测 round2 | 10 PASS / 5 FAIL：2 个真实页面采纳被自己的在途标记拦截，另 3 个把合法 409 拒绝当成功预览解析 | 原入口未决检查与本次在途标记分开；拒绝答案按实际状态验证 |
| 独测 html-round3 | 3 PASS / 2 FAIL：positive 19 项而断言至少 20；late_denied 等待了实际流程未走的路由 | 加入已消费预览不可再次使用的实际断言；等待首个真实 command-recovery GET |
| 独审 probes-first / probes | 同一次 4 PASS / 1 oracle FAIL，被外部测试改过的资源表错误计入“不得变化”快照 | 独立答案排除该已声明外部改动，其余业务表仍核对；原件保留 |
| 旧源码冻结回归 | 根 1d7f4c8 仅 2 PASS、957fb8df 仅 64 PASS；独审对应仅 9 PASS、39 PASS，均主动中断 | 在修正测试/真实路由回归前停止旧窗口；不作最终通过 |
| 当前根完整回归/诊断独立复现 | 名单读取器 256 KiB 小于补齐后的 286,439 字节，25 项真实级联 FAIL；完整 diagnostics 原样 25 FAIL / 34 PASS / 1.26 秒 | 保留失败；独立有界 512 KiB reader + 实际边界测试，名单 AST +1 后重新冻结并跑完整 8 模块 |
| 当前根完整回归/HOLD 单独复现 | 两项旧 HOLD 测试在原业务断言通过后写缺失证据目录，分别 FileNotFoundError；独立原样复现 2 FAIL / 2.89 秒 | 只创建原测试输出目录，完整模块另窗 7 PASS / 9.34 秒；冻结源码不变，首窗失败仍保留 |
| 原恢复键兼容 RED | 根 1 FAIL、独审 1 FAIL：合法 key `plan-revision` 冷 GET 422 | 路由顺序修复后根单例 1 PASS，并纳入本次全部最终窗口 |

根最终诊断窗首次后处理器误拆参数内 `::`，且独立 collect 与执行中的一个 UUID 参数在导入时随机，测试已是 297 PASS / 8 SKIP，但后处理断言失败；原日志/XML/清单保留在 `delta-first-postprocess-error/`。修正为同一 pytest 进程 collection hook 后，另窗相同 305 节点精确一致，未修改产品。独审首次 collect 因 PYTHONPATH 缺项目根而 collection ERROR，补足调用环境后完整执行成功；旧错误保留。旧 52 模块单独 collect 与实际 JUnit 仅一项 `test_template_candidate` 的导入时 UUID 参数不同，原两条值保存，仅该参数归一化后 1688 节点一致，不声称原字符串完全一致。

当前 52 模块测试集新增一项诊断边界后共 1689 项，其已通过覆盖来自明确分列的原业务窗口、HOLD 7 项补验及最终诊断链；不是同一次 1689 PASS。更广诊断窗口的 8 SKIP 均缺 PowerShell/原生前提，保留为未执行。逐节点关联见[分窗覆盖核对](evidence/source-opportunity-adoption-20261015/source-adoption/final-coverage.json)。

普通定向开发窗口和旧 `957fb8df` 的 20 PASS 只保留其历史范围，不替代当前冻结结果。工具 `apply_patch` 曾发生一次 transport closed，随后核对文件后用普通文件写入继续；没有权限升级或绕过拒绝。

## 边界与立即关键路径

本片是原合成注册 Case 的限定闭环。失效/撤回/UNKNOWN 不复活；同 key 异正文/异 Case、跨 tenant/owner、撤权、迟到、ABA 均拒绝新写；已成功回执是历史证据，不授予当前新操作权限。来源卡不被采纳操作写回，业务事实/批准/外发也不由机会提示写入。

SELECT-only 外部管理员在最后来源读取到 COMMIT 间提交的竞争仍属既有可信管理员边界，本片不是完整源发布协作/线性化协议。有限合成 ServiceRelease/ParkInstance、第二园区选择、既有 owner Approval 和前向有限结构增强均已有交付；剩余正式治理、一般类型化来源图、跨合同兼容预检、独立固定变化集上的漏更/误改统计及完整 AT24–27 仍未签收。Windows/Win11、实际浏览器、正式 42 项 AT、真实模型、生产迁移/真实履约均 NOT_RUN；真实模型调用 0。此前浏览器访问拒绝保持，本轮没有重试或改安全配置。已有 CI 触发器不包含本新分支，本轮不扩工作流/安全授权，远端 CI 未执行不得记 PASS。

按用户一周目标立即推进，当前目标窗口为 2026-10-15 至 2026-10-22，不再沿用月底慢排。后续先冻结原材料/事实/规则/容量/回执的有限稳定来源节点、类型边及来源证明，补逐有权 Case 影响定位与独立应改/应保留答案；按原 AT24–27 核对一般依赖、未知传播和跨合同兼容预检。已交付机会卡、本采纳闭环、有限 Release/第二园区选择及结构增强不重做；并行准备正式发布/Approval及真实来源主体合同、Windows与正式验收可执行前提。缺前提的真实模型/生产/正式外发保持关闭。详见[更新后的关键路径](../DeliveryCriticalPath-20261010.md)。第二作品在本环境未核实，不虚报其 SHA 或进度。
