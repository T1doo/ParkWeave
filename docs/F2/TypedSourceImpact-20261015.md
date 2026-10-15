# 有限类型化来源与逐 Case 影响定位

本片沿原产品 §8 / F3-T02、F3-T03，从 `f353da680d919fcb4033a02ab57f4fec95335f86` 接续。开发分支 `dev/f3-typed-source-impact-20261015`，冻结源码 **`a5d9da251c223e3a64e20d3d47987d5b58fcdb6f`**。本文件及归档随后提交；交付 HEAD 与冻结源码的 `src/tests/scripts/pyproject.toml` 字节差异为零。main 与上一交付分支保持原值，实际推送回执另列。

## 实际完成

- 工作清单每个本人有权 Case 增加明确只读来源查看，无机会卡也可定位变化；无计划与缺少原核验基线分别显示。原办理按钮仍为首入口，不代为导入、刷新、采纳或核验。
- 由原 VERIFY / 已采用来源与当前原适配器实际读取、资源/Run 访问集合编译有限类型化来源组和原步骤端点，显示变化原因、受影响/保留步骤、原前置传播、已有资源时段及聚合证明摘要。源组 ID 在原计划的 adapter/facet 内稳定，不是跨 Case 统一源实体 ID。
- 新来源采纳保存 v2 图证明，完整进入原预览/请求/事件指纹；与原来源分区不一致立即拒绝或明确 UNKNOWN。schema 1 历史固定使用 `build_v1/GROUPS_V1`，旧 v1 来源事件仍按旧算法验证，当前编译器变化不能重解释旧历史。
- 材料、事实只保留原聚合证明，不从当前资料倒填旧 slot/assertion ID 或事实值；未识别字段、缺基线或无法解释的来源结构扩大到此 Case，并拒绝新采纳。资源集合覆盖既有可选资源，不只看已选资源。日期缺证据明确 UNKNOWN；日期元数据未知与影响关系未知、当前来源可用性分别处理。
- 原同 Case 来源机会→原计划预览→本人明确 local ADOPT→受影响原 VERIFY→六目标证据/工作清单闭环保持。P1–P5、全部原目标、UUID、正文、原事件和历史、未受影响锁及核验证明保持；受影响锁须原 UNLOCK，解锁不代核验。原幂等/参数冲突/opaque 冷 GET 恢复规则保持。
- 页面隔离当前身份/Case/世代，当前 403 清私有视图，迟到 403/身份 ABA 不清新视图；来源查看和导航没有新持久存储或自动 POST。

## 冻结验证（分别记录窗口）

| 冻结窗口 | 完整模块 | 实际结果 | 时间 |
| --- | ---: | --- | --- |
| root-1 | 27 | 900 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 1020.69s（runner） |
| root-2 | 25 | 789 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 1122.36s（runner） |
| independent-formal | 2 | 53 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 220.35s（JUnit） |
| review-extra | 8 | 262 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 187.64s（runner；pytest 185.87s） |
| 独立混合历史探针（单列） | runtime 3 probes | 3 PASS /0 FAIL/ERROR/SKIP | 37.59s（JUnit） |

同一冻结版本的四个完整模块窗口互不重叠，覆盖旧 52 个模块、补充 8 个事实/材料/可信服务模块、新增 2 个来源图模块；不是单次全仓回归或正式 AT。每窗 collection/JUnit 对齐、源码哈希无漂移。独审 591 tracked 源及元数据 +5 editable 元数据的全测试窗检查，与另行全仓 11,596 tracked 文件静态子窗匹配 Git blob 的时点分开说明，不把后者冒称 pytest 起始快照。

正式独测 11 条字面 oracle：8 条已知影响分区，漏更/误更/误保留为 0；另 3 条 THIS_CASE 未知扩大（事实用途不可用及 2 条故意未知）单列，不当作精细影响准确率。expected/actual affected 均 38 对。混合历史另 3 条 oracle、12 对，零漏误。答案按原稳定 step UUID 映射字面 P1–P5 集，不调用产品 closure 生成期望。

6 条完整原 HTML 脚本经真实 HTTP/ASGI/自有 PostgreSQL：正向 26 checks /38 请求/7 POST；丢回执 30 checks /42 请求/7 POST，冷恢复只 GET；来源读身份 ABA/迟到 403 各 16 checks；图打开原材料的当前/迟到 403 各 10 checks，拒绝窗口全部 GET。DOM 与浏览器传输表面由 Node VM 提供，不代表真实浏览器。

## 失败和修复原件

- 原 UI 两模块首窗 63 PASS /11 FAIL /13.93s：新按钮排在原入口前，旧导航命中新按钮。原按钮保持第一后完整复验 74 PASS /11.98s。
- canonical 类型 RED：`1→True/1.0` 被 Python 相等掩盖，2 FAIL（22 deselected）/0.51s。节点变化改用 canonical 摘要，和旧 direct 分区不一致则 UNKNOWN 拒绝；完整 focused 24 PASS /45.43s。旧 v1 算法未改。
- 独测开发完整窗 28 PASS /1 FAIL /131.19s，单例 RED 保留：夹具重复 REVALIDATE 已核验同一周期被原规则正确 409。仅修测试用原 CLOSE_LOCAL_RECORD→REOPEN→REVALIDATE 产生新周期；P5 字面答案和产品 guard 不变，单例 GREEN 1 PASS /5.77s，正式 53 项全部通过。
- 旧来源采纳开发完整模块 23 PASS /126.63s；该窗期间源码尚在定稿，不能代替冻结后的完整窗口。后端首窗 22 PASS、独测 focus 4 PASS 和目录 metadata 60 PASS 均为开发/定点窗口，不重复计入正式范围。
- 初次 Node 语法检查的 `/proc` pipe 调用 ENOENT/BrokenPipe 属验证命令失败，保存工具回执转录及摘要；写入真实 JS 文件后语法检查通过。此回执非当时重定向得到的原始文件，不冒称字节级 stdout 捕获。

原始失败日志/JUnit 保留在 `.runtime/typed-source-impact*`；公开归档逐文件记录原件/export hash、大小及明确去敏次数，XML 先解析再去敏，不删失败 testcase。私有合成会话值集、PG 文件和缓存不导出。来源门、未知拒绝、64 事件和预留解锁/VERIFY 规则、权限/预算/CI 工作流未放宽。

## 剩余关键路径和外部验收

最高价值下一片是共享来源版本→所有当前有权 Case 的有界反向定位。复用 owner/tenant 工作清单候选、现有限来源图和 scoped epochs；分页绑定来源 epoch、候选集合及 Case 版本，未知/溢出/未遍历不可宣称完整覆盖，变化/ABA 立即 stale。每 Case 独立原锁序事务，仍逐 Case 明确采纳。现每 Case 按钮尚未实现此反向发现；一般动态/语义依赖和业务包未知扩大、完整 AT24–27/比较尚未签收。

既有有限 ServiceRelease/ParkInstance、第二园区冷输入及有限模板结构增强已交付；正式来源许可、审核发布/Approval 主体、真实业务产物与独立回执仍需真实前提。Windows 原生安装/owner/ACL/Job、真实浏览器、正式 AT、真实模型及生产全部 NOT_RUN；产品真实模型调用 0，无部署、权限或费用扩展。既有 CI 工作流只匹配历史固定分支，无此新分支/手动触发器，远端 CI NOT_RUN；没有新增工作流或借旧分支触发。参赛规则/模板/视频/上传权限及第二作品状态须其既有负责人/环境独立核实。

继续按当前一周目标推进，不等待日期；工程 PASS 不替代外部门签收。详见[证据索引](evidence/typed-source-impact-20261015/index.json)、[冻结合同](TypedSourceImpactContract-20261015.md)和归档独立审计。

## 归档与最终独审

主归档保留 135 对原始/公开导出文件，共 18,029,669 公开字节；6 行夹具 repr 明确去敏，精确私有值替换为 0。独审独立重建全部导出字节、核验哈希/大小/结构，13,591 个指定合成会话值残留为 0；重算分窗 collection、字面 oracle 与 6 条 HTML 记录一致，最终门 `PASS_BOUNDED_LINUX_SYNTHETIC`，本片剩余阻断为空。原失败与准备阶段记录保留，主归档未被最终审计覆盖改写。

最终审计单独归档，见[审计附件索引](evidence/typed-source-impact-audit-20261015/index.json)、[最终门报告](evidence/typed-source-impact-audit-20261015/final-gate.md)及[详细审计](evidence/typed-source-impact-audit-20261015/archive-independent-audit.json)。此限定 PASS 不替代上述外部验收。
