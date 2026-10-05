# F2 本地两个增量的有界收尾

审查范围固定：已发布基线 `6ff160abe979f9d1c28d0e7804fda668daf72cf5` 到本地 `c285da844fcf86f397e052826743e4fe7360a9e8`（ENG015 请求/草稿竞态修复）、`3aa99e45e82517a80a5197d140a92ebce8c92ff2`（ENG016 个人待办）。没有扩大功能、修改原阶段门、推送或重跑Windows CI。本文件收敛既有证据，不产生新测试成绩。

## 独立只读审查

已完成同一工作区独立只读 reviewer `/root/local_f2_review` 的检查（用户指定6.1 sol / medium），范围 `6ff160a..3aa99e4`。它与实现 agent 分开，未修改/复制/导出源码，未安装/访问外网/执行业务API/项目模型动作；没有读取私有会话或DSN。

结论：**未发现所审两增量的实质 correctness/security finding**。reviewer 核对了 web.html:29—43 的token/事项/generation绑定、迟到成功失败守卫、草稿清理与写入case/revision绑定、重复键；preparation.py:159—195的后端当前role/READ/准备授权与tenant/owner/assignment过滤、单语句快照和无材料正文；详情/commands仍独立重新授权。它独立执行Python AST、页面/Oracle JavaScript语法、diffcheck，并确认ENG016记录的六个源码hash匹配，未重跑419项回归或19项新PG/API测试。

reviewer明确的限制：UI race oracle为mock fetch响应排序；实际本地API浏览器只证明所列顺序双角色/双case流程，不证明所有并发排列或完整生产安全，也不认定发生真实资料泄露。该审查不是外部审计、渗透测试、真实用户/生产数据验证，不代替原生Windows或完整AT验收；未因“无finding”把F1/F2改为签收。

## 功能与用例覆盖矩阵（实现 agent 对已有证据的整理）

| 断言/用户功能 | 当前可复核证据 | 未测或边界 |
| --- | --- | --- |
| case/session 请求代次、身份和选中 id 绑定；迟到 GET/写/失败不覆盖新选择 | ENG015原页面合成复现四项缺陷；修复20 checks，ENG016延伸23/23 checks；源hash记录 | 合成响应序列，不是后端授权测试或真实数据泄露证据；未穷举所有网络/事件时序 |
| 跨case材料/来源/人工说明清空；同case刷新/编辑保护；提交case/id/revision | 原竞态复现、A→B→A、编辑中迟到写、id/case/revision guard、失败草稿/幂等重试/导航/New oracle | 已发送事务不会因离开页面撤回；浏览器本地内存会话，未验证多设备真实身份接入 |
| 企业补交/补正/确认、获派专员核对的个人待办 | 新19项PG/API测试、真实本地低权限API/独立worker/PG双case双角色表单链；确认退出、重开返回专员、reload回读 | 仅固定两个合成材料槽；齐全不表示真实性/资格满足；无通用ServicePlan、跨服务办理或资源组合 |
| 待办role/tenant/owner/assignment范围与当前撤权 | 19项中跨企业/园区、同scope未获派专员、resource_admin/service_executor、伪造role/owner query、身份/READ/准备Grant撤销；现有command权限回归 | 同园区同企业第二enterprise owner的待办专属新用例未单独执行；owner_id过滤可静态核对，不能把静态检查计新测试PASS |
| 重复读取无新业务事件、历史与材料按case保留 | 新PG重复GET/Store重建、双case资料/说明隔离、浏览器重复读/确认/reload/reopen；既有不可变历史/CAS回归 | 待办是当前记录的只读视图，没有通知创建/送达/已读账本；没有真实站外消息渠道 |
| 一致快照、规模与阻塞明确 | PG并发提交/20次读取只接受完整已提交状态；单语句读取；101记录的100件上限/更早记录提示；revision64阻塞 | 100个最近未确认有权事项的检查范围，不是全部事项分页或全量待办；64上限用隔离owner fixture，非64步真实用户长程体验 |
| 纯文本与窄屏、失败回到正常读取 | 双角色浏览器中脚本文字不执行、错误身份清空队列、错误确认拒绝、320/390无横滚、页面错误0 | Linux Chromium与模拟viewport；不是真实手机、Safari、Win11桌面或生产渗透结果 |
| 工程回归与保护边界 | c285最终400 PASS/0 FAIL/1 Windows SKIP/2既有WARN；3aa最终419 PASS/0 FAIL/1 Windows SKIP/2既有WARN、23checks、原V1 bytes/hash、24保护文件逐字一致 | 成绩来自不同提交，不相加；checks不加到pytest；Linux/static不能替代Windows、LIVE或整项AT |

证据入口：[ENG015](evidence/eng015-ui-race.json)、[ENG016汇总](evidence/eng016-acceptance-summary.json)、[ENG016真实本地浏览器](evidence/eng016-browser.json)。该审查时点（3aa）源码hash与ENG016冻结源一致。后续ENG018修改共享web/api等源文件，不能把此旧审查继承为资源新片独立审计；独立审查不会改写旧失败或结果。

## 剩余依赖与恢复顺序

| 条件 | 当前已证实/未证实 | 下一步解锁范围 |
| --- | --- | --- |
| 最新Server失败明细（立即所需外部输入） | run37324704568 completed/failure；Prepare/受绑定PG启停PASS；native_suite exit1/78.094s/no timeout；具体FAIL/NOT_RUN子项与原生回归计数缺失 | 只需页面engineering JSON的失败cases及已有exit_code/category/reason，加full_engineering_regression.counts（如有）；据实定位Server命中子项 |
| E1 Win11 x64原生条件与证据 | Server不是Win11；Win11精确环境/权限/生命周期与candidate ACL/reparse/share/race没有验收 | 原Win11 guard不改；只有取得原生证据后，才复核条件性R4 reader/fixture集成；R4集成仍是未完成代码任务，不能包装成纯外部阻塞 |
| E2 真实模型安全配置、额度与授权预算 | 真实请求0、预算0；LIVE关闭；真实provider/跨产品shared配额/速率/usage与错误未证实 | 获明确安全注入/账号及核实总额度/预算授权后，才执行限定真实模型链验收；不把mock或其他项目成功继承为本项目PASS |
| 来源台账与合法合成fixture（F1-T06工程条件） | 已有原文来源manifest/数据台账、显式版本化合成fixture与oracle；真实来源获取未完成 | 可继续对应合成F1/F2工程；原文要求开始获取授权，不要求先拿真实样例才做全部工程 |
| E3 对应真实样例/试点价值许可 | 无真实园区资料/模型发送范围授权与真实用户效果证据 | 停对应真实样例/真实试点主张；获取受控来源/许可/验证者后另验，不把许可缺失笼统作为全部F1或合成F2硬阻塞 |

本地两增量已经保留，等待条件不意味着F1只剩日志、F2全量已完成或所有缺口都是外部因素。F1-T06的台账/合法合成fixture工程条件与对应真实样例的来源许可分开，F2原文允许明确合成测试目录；真实模型、Windows和安全门不降低。完整F2 ServicePlan/资源/模板/执行者与通知等原计划能力仍未实现，属于后续阶段而非本次收尾。C0规则/模板等提交条件独立于本轮工程验证，不新增任务充填等待时间。

收到最新JSON后：首先核对run id/源码9a8cbc5与失败子项，保留缺失字段和真实计数；将子项映射到原native_suite阶段及对应oracle，只修实际证实且在授权范围内的问题，留下复现/修复/本地定向验证。遇到需私有原始日志但现有字段不足的情况，明确说明最小缺项，不重试被拒日志或替代路线。恢复下一次Windows运行前比较原origin分支/历史，保留远端6ff与本地c285/3aa祖先；根据届时授权普通push实质修复与已审查增量并统一安排一次CI，监测到终态，失败如实保留。无新日志/实质修复时不原样重跑，不force/reset/merge main/deploy；Server通过仍不解除Win11/真实模型/安全门或R4条件性集成；对应真实样例仍须来源许可。
