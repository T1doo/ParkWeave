# 预览隔离与第二园区变化闭环

本批在原产品接口上补齐三个有限开发场景，原AT14/AT33定义与全局验收状态不改。所有业务效果证据来自owned Linux临时PostgreSQL、原ASGI接口和离线完整HTML NodeVM；没有生产、正式治理或真实模型签收。

## 实现范围

- 已明确采用且完整证明有效的V4计划，以可信实例映射选择同园区的两资源。预览的来源、守卫和比较共同复核；残损V4不能降级到旧固定A园区资源。P1–P5的原注册动作在隔离临时身份、权限、资源和pg_temp空间实际写入后回滚，预览账本独立持久。成功路径46张public业务/审计表逐值不变。原P2 CONTRACT仍是默认profile，B资源由精确动态source snapshot及影子映射另行证明。
- 默认关闭的有限合成规则适配器，必须显式注入owned PG、原候选规则模拟链、受信配置绑定及独立journal。原SAVE/SUBMIT/独立REVIEW/PUBLISH事件与当前权限、版本、时点、地区、事实purpose和全部同字段冲突共同核对。结果TRUE/FALSE/UNKNOWN只是开发模拟条件；事实仍USER_ASSERTED_UNVERIFIED，qualification_truth始终UNKNOWN，formal_review/business_publication均false。旧工程readiness未提升为正式规则。
- 同一V4两资源的替代时间只读提议，绑定六目标、原plan/link/资料与当前资源版本和依赖集合。本人逐项使用原HOLD、组合确认、资源绑定比较及明确确认、原P2–P5重核；旧占用不自动释放。真实资源revision及buffer变化须原局部ADOPT，保留P1、原V4证明和其他园区历史。P3/P4既有接单与合成回执保留并再次核验，不宣称新增线下履约。
- 新页面仅显式GET规则模拟、替代时段和原key恢复；建议预填仍需原资源预检和本人确认。没有新增页面写入编排或真实模型调用。取消、关闭、撤权、跨身份和未知结果继续受原守卫约束。

## 独审修复

保留独审真实红窗后修复：既有journal缺失/伪造不可变trigger必须在任何DDL/DML前拒绝；删除V4标记不得尝试旧固定资源；当前规则来源不可用时保留已提交历史回执并将当前有效性降UNKNOWN，当前READ撤销仍拒绝。另由实际HTML联调复现HOLD已提交但回复丢失时原入口门误挡恢复GET，现仅精确身份/key/原路径匹配才放行读取，不解除未确定状态、不重发。各首次失败、修复窗口分别存档，不相加。

## 人工配置与代码统计

相对e550983交付，本批产品源码6文件，643行新增、17行删除；新增测试11文件（含完整HTML桥接JS），另修1个继承的旧离线harness，不宣称一键迁移。B园区实测明确配置3个模拟角色/3项scoped模拟permit、2个发布版本/2个绑定epoch；本人另提交3条事实及1条刻意冲突事实、新Run/Case/资料。C资源变化为owned夹具管理员对原2资源的revision与buffer故障输入，另行统计，不冒称正式资源管理页面或治理发布。运行期间权限表保持不变；预览所需既有managed access申请/独立批准仅是夹具前提，影子权限仅在临时命名空间。

## 最终验证

最终源码：`5e339a247e33d1a4b6cb4c106e54af1ea22b5439`。本批工程范围LIMITED PASS，未提升原AT状态。产品src与1953逐字相同，最后一项变化是旧离线harness修复。

| 同SHA最终窗口 | 实际结果 | 时间与来源核对 |
| --- | --- | --- |
| 根30完整模块 | 659 PASS，0 FAIL/ERROR/SKIP，2既有WARN，exit0 | 555.59秒；566文件前后零漂移 |
| 独立24完整模块 | 481 PASS，0 FAIL/ERROR/SKIP，2既有WARN，exit0 | 372.54秒；567文件与commit及前后完全一致，74加载模块均在私树 |

两个完整窗口分列，不相加。旧1953独审460 PASS另存。根1953首个完整窗口实际638 PASS / 21 FAIL / 0 ERROR、SKIP / 2 WARN，550.63秒、566文件零漂移。21 FAIL集中于旧资源时段fragment harness缺少入口helper；干净e550983基线同样实际21 FAIL。仅修DOM及完整HTML加载，保原21模式、断言与手动响应顺序，先实际21 PASS后才重新冻结整批。

离线wheel核对全部154 package文件，missing/extra/changed均0；根wheel SHA256 `890b1f20fc9f20c43f876868f5629f632d5234f5c8dd22efc4605fe262ce6f5d`。独立包另建，SHA256 `61e3c7b43e731ff7f8240166f62b82e0224c51968ebe77f0a5dea9644ffc51b5`，并验证包内HTML GET200、默认规则模拟GET403；zip时间戳差异不等同payload变化。

根首轮错误清单包含6个依赖Playwright的模块，收集即6 ERROR/exit2，未启动浏览器，也未安装或重试。原件collection-first-final.*保留。独审旧74412窗口因最终文案冻结更新有证据中断，不计最终窗口。真实红窗、初始fixture错误和Node桥接超时均分列保留，不以最终绿覆盖或相加。

证据索引：[304份分列证据导出](evidence/preview-rules-change-20261014/export-index.json)；[同SHA独审](evidence/preview-rules-change-20261014/review/FINAL5E339_INDEPENDENT_SOURCE_REVIEW.json)。只精确替换两个已销毁夹具临时session的4处完整值，raw原件保留。[最终归档独审PASS/exit0](evidence/preview-rules-change-archive-audit-20261014/safe-handoff.json)，304份精确变换、路径及哈希全过；索引SHA256 `0c75064b75d6f7d4f370152655829c90f401ee1638ec1087ca609feea7c89189`。首轮保守扫描12处/3种metadata未分类exit1，独立上下文确认是分支名与JSON键；其原件及后续独立PASS另存，不覆盖。

源码与报告diff-check为0。保留原始pytest错误输出中的空格，证据目录diff-check为2；没有改写失败原件来消除该提示。

交付分支：`dev/f2-worklist-entry-isolation-20261013`。源码到交付只追加报告和证据；完整交付SHA、远端71分支/其他70分支及clean、ahead/behind核对在最终回复与本地delivery-verification.json记录。

## 未验边界

正式生产AT14、真实业务规则治理权和AT33跨园区正式上线均NOT RUN；真实模型/付费调用、Windows、浏览器、部署、生产迁移NOT RUN。Chromium历史ERR_BLOCKED_BY_ADMINISTRATOR未重试；GraphQL的Forbidden CI路线保持停止，未替换端点或配置凭据/网络。独立开发分支正常Git推送不等同CI通过。
