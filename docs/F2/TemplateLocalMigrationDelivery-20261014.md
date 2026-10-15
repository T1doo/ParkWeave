# 在途模板修订采用交付

基线 `adf867156fcf0b22d15a18007cf8fa3fc65f34a2`，原开发分支 `dev/f2-worklist-entry-isolation-20261013`。源码/测试冻结 `f25a46e3b405775a99ed0fe874236a0ad3547434`。本片落实原 F3-T03 / F2-T06 与 AT25–27 的有限合成执行路径；不改原验收规格全局 NOT_RUN，不宣称全部生命周期或通用数据迁移。

原检查和选择保留独立审计语义。新增明确原因和精确版本确认的 APPLY，采用事件与有效模板绑定在原 PG plan 同事务提交；consumer 原绑定和阶段不改。仅同结构、合同、服务和注册步骤的修订：说明修改保全部旧核验；模板来源变更因缺细粒度边而扩大本 Case 全 P1–P5 重验，保稳定 ID、原正文、人工决策、旧 verified 快照及事件。结构变化、人工锁冲突、非当前/未审/撤回/过期目标、撤权、取消及本地关闭拒绝。原业务资源、预约、接单、回执和 Run 成功事实保留；没有自动业务执行或反向回滚。

来源核原 SAVE/REVIEW/PUBLISH 独立列、指纹和不可变事件锚。原 parent→dispatch→Case→source 锁序及租约覆盖真实 PG commit，等待后重核时效与权限。新事件完整 typed 请求和多跳链证明共享给原步骤、恢复及 goal-results。历史读取与当前有效性分列；撤回、过期或未挂载时历史 GET 可读且全部 PG 表零写入，当前不再显示 VERIFIED。P1–P5 原步骤逐项 VERIFY 后，按原诉求的 goal-results 核真实业务输出。

页面保原 check/choice，再独立确认采用，明确只采用定义并要求原步骤重验。结果未知只 GET 原 key；NOT_OBSERVED 保留 pending，不自动重发。热恢复核原 11 字段及指纹，冷恢复核有限内部链；错回执、迟到回复和身份变化均不能解除 pending。合法历史 tc:<instance UUID>:ADOPT_PLAN 精确支持；伪 key 与其他实例 key 仍拒绝。

实际测试窗口分别记录，不能合并为一个全通过窗口。开发中原来源证明篡改、旧 key 返回新有效版本、goal-results409、撤回后仍 VERIFIED、UI 错回执解锁、合法旧采用键409、采用后事件额度耗尽等真实产品红例完整保留；fixture/路径/锁列错误及主动中断另行标明，不能改签或删除。

来源变更采用前预留本次全部 affected 必要 VERIFY 事件及原锁 UNLOCK 额度；不足提前409且PG零写入，防止采用后在64上限内无法完成本次重验。零 affected 说明修订不新增重验预算，其他原有待办仍受原64上限限制。

| 最终同版窗口 | PASS | FAIL | ERROR | SKIP | WARN | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 根任务39模块完整回归 | 1355 | 0 | 0 | 0 | 2 | 0 |
| 独立复验（原独立36＋容量5） | 41 | 0 | 0 | 0 | 2 | 0 |
| 独审12模块（24独立反例＋259相关） | 283 | 0 | 0 | 0 | 2 | 0 |

三窗均绑定上述完整源码/测试SHA，分别为1081.81、129.37、441.04秒。根任务575个源码/测试/脚本路径、独审576个包含pyproject的tracked路径及独立155产品文件/三测试前后零漂移，加载路径均指向实际被测源码。原1350测试范围全部保留：1349个原ID精确一致，仅一项既有uuid4参数标识按相同源码、固定函数与参数规范化核对；原12失败ID全部精确PASS，另增5项容量边界。没有删除测试或合并窗口。

根任务原完整窗为1338PASS/12FAIL/0ERROR/0SKIP，12项均在adf867基线独立复现，确为未包含entryFetch的旧抽取脚本测试；修后完整HTML保原12判据，两个注入错误负例均被断言捕获。旧源码的67PASS与359PASS窗口主动中断，退出2，仅作部分执行记录。容量产品缺陷、独审目标构造错误、验证helper随机ID比较错误及其他开发FAIL/ERROR均单独保留并明确资格，参见归档各窗口原JUnit/日志/exit及failure-qualifications，不能升级为最终通过。

根任务与独审均离线构建wheel并逐字节核155/155产品文件，missing/extra/changed均0；根任务wheel SHA256为`27cb5ec624ce7d6926bb1891fefe550aa3c3bcf41c2131c1f2fd841af83c34fe`。

[证据索引](evidence/template-local-migration-20261014/export-index.json) SHA256为`0d2311e7fecd39969aaa67b94fbec9f73156f7b10c50e61cbc2f8a30cc9b9c8a`。[独立归档审计](TemplateLocalMigrationArchiveAudit-20261014.json) PASS，398/398原件及副本、哈希与字节完整，无missing/extra/private泄漏；6980个实际临时fixture session候选无残留，实际脱敏替换0，全部导出字节保持原样。源独审为有限范围通过，最终归档另置审计，不回写已冻结raw或递归索引。

交付为正常开发分支文档/证据提交；源码至交付的src/tests/scripts/pyproject差异必须为0，推送后核远端、clean与ahead/behind。最终完整交付SHA及实际核验结果见交付回复。

范围限制：仅自有 Linux 临时合成 PG、进程内 ASGI 和完整 HTML 离线 NodeVM。真实模型/付费调用、Windows、浏览器、CI Forbidden 路线、生产迁移及部署 NOT RUN。历史 Chromium data: ERR_BLOCKED_BY_ADMINISTRATOR 保留且未重试；无凭据、网络、权限或 Grant 配置，无保护分支改写或强推。

下一步按原计划补结构变更的兼容预检及迁移策略；当前结构增删继续明确拒绝，正式 AT25–27 与发布治理另行验收。

自动审批曾拒绝删除私有src目录，理由为非必要的广泛不可逆源丢失。删除未执行、未重试；旧目录保留，在新空私目录完成验证。完整原始报错保留于[native-harness/auto-review-delete-rejection.txt](evidence/template-local-migration-20261014/native-harness/auto-review-delete-rejection.txt)，该操作拒绝与测试FAIL分列，当前无剩余阻断。
