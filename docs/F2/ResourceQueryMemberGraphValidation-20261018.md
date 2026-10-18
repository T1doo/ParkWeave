# 原资源查询集合及成员的细粒度版本图

基线 `f522b6bfb4080d1fc557f1695dd6c909a61bda80`；冻结实现、合同及测试 `09ea99212b8ddcc70797ec7ac2bfc1909d574a18`，分支 `dev/f3-resource-query-members-20261018`。本片完成原产品设计§8/F3-T03的资源来源薄适配：[冻结合同](ResourceQueryMemberGraphContract-20261018.md)。没有签完整AT25/26或六目标全链，项目仍未完成。

## 实际接入与证据边界

原机会卡 `plan-revision` GET 显式携带 `dependency_scope=BOUNDED_MULTI_SOURCE_V1&graph_preview=RESOURCE_QUERY_MEMBERS_V1` 时，沿原身份、owner/READ/PREPARE、Case/Run/preparation、当前卡片、原计划和历史验证，附加 `resource_dependency_preview`。新适配从原P2已保存的规则/true授权原件与当前有权原始查询行直接构图，调用已审 `dependency_graph.snapshot/preview`，没有重写传播内核。外层旧typed投影仍沿原schema2转换保留兼容；不能宣称整个GET都不调用旧转换。

每个原UUID有稳定resource节点及规则/查询授权行指纹；查询节点按owner/park/org/query_version稳定，scope绑定原plan。集合保存成员指纹与complete状态，边为实际成员→查询集合→原P2，以及原plan已声明的步骤依赖。结果展示确定/不确定消费者、版本路径、当前人工锁冲突；原P1不受资源分支影响，原P2及实际下游路径可见。本图只描述资源查询范围，不取代其他来源预览或当前业务有效性判断。

原历史集合只存known/count/hash，不能恢复未保存的原查询行。适配只从有权读取的原Case核验历史重建已有规则和true授权行，相同true重复证据合并，false不当作inactive行存在证据，矛盾或无对应规则的证据保持未知。重建的行数、规范hash与原stamp精确一致且known，才确认历史全集；绝不用当前规则、授权或成员填补旧历史。当前查询先过滤同主体、同园区/组织、SYNTHETIC/LOCAL_AUTHORITY且有active READ的资源，不能借HOLD行读当前已无权详情；当前观察也须与原本次集合stamp精确匹配才complete。

前后均complete才列确认added/removed/changed；任一端partial则只列newly_observed/no_longer_observed/observation_changed，明确UNKNOWN。成员移出只表示查询成员关系变化，不表示物理资源删除、预约释放或取消。最多96成员、原查询256行，第257行检测溢出，超过界限409而非返回伪全集。显式资源mode要求原plan已有P2，否则409；页面先取原只读command-recovery计划，P1-only明确请求原 `VERSIONED_TYPED_GRAPH_V1`，不虚构资源消费者或由API静默降级。

升级既有类型图按钮，复用原callerCurrent、代次、身份ABA、草稿、迟到和当前403守卫。沿原规则清除旧确认与采纳投影，隐藏ADOPT控件；新GET不调用普通计划观察GET，不写localStorage，不新增上传图、快照仓库或写入口。页面检查当前绑定、hash、原始图结构/成员/边/路径引用和边界，不重算传播闭包；hash不是身份认证，完整锁来源证明仍由原服务器 `_manual_lock` 校验。

原 `build`、`validate_history`、`typed_dependency_preview` 逐字未改；传播内核、registered/typed/unified来源模块、service_case_steps、固定AT规格与绑定均与基线相同。新字段只在read附加，不入旧ADOPT正文、来源修订hash或历史；原v4采纳实跑保持。原权限、P1–P5与六目标编译器均未扩展。

## 实际验证

| 窗口 | 结果与实际范围 |
| --- | --- |
| 根冻结09ea私有镜像 | 16唯一collection/setup/call/teardown/JUnit全PASS，0FAIL/ERROR/SKIP；10原件纯测试＋6实际API/页面复合选择器。pytest121.78秒，outer127.824403627秒，保留4项原警告。780输入shared/mirror PRE/POST均相同，113个已加载项目/测试/helper模块origin及hash匹配冻结镜像。 |
| 独审主窗 | 同一09ea，本片16＋自有3复合选择器，19唯一PASS，0FAIL/ERROR/SKIP；pytest146.06秒、main147.830423498秒、outer149.378641608秒。780输入两端无漂移，113个冻结项目/helper模块及1个独立测试文件分别核origin/hash。 |
| 独审纯边界补窗 | 1唯一PASS，0FAIL/ERROR/SKIP；96成员、192原行可接受，97成员拒绝。pytest2.47秒、main3.262940864秒、outer5.521035238秒，无PG/fixture；780输入两端无漂移，16个冻结模块及1个独立文件origin/hash正常。 |

根与独审有效选择器交集16、并集20；独审20由19＋1两个窗口组成，不能写成单窗20或相加36。独立oracle的13行设计、页面请求、断言、坏DTO探针不计作pytest数量；不同选择器也有语义重叠。没有重跑旧17或141矩阵，没有迁移旧片成绩，外部依赖未插桩。开放P1/P2为0。

根验证完整历史原件、成员实际插入/移出/规则修订、重复true与false歧义、部分证据、严格界限/类型、当前READ过滤、跨主体403、精确双query、显式无P2与epoch变化409。复合API场景包含新Store/新API冷GET、旧响应逐字段相同、所有public业务/权限表行值不变（authorization_audit拒绝审计单列）、原P3解锁及旧v4 ADOPT201/原历史与P1保持。测试刺激只改自有临时合成fixture，GET前后快照围绕刺激分别结算。

独审额外用自有字面字段和独立JSON hash复证完整/partial/重复/规则版本标签；实际撤销已选历史成员的当前READ而保留HOLD，当前详情不读、只列no_longer_observed及UNKNOWN，不能确认为删除。独立完整页有39次实际GET、0POST、22断言，6个重hash坏DTO均拒绝，包含资源卡A迟到后切换P1-only卡B明确旧mode、冷页及当前403；普通计划观察GET为0。根页面也实际覆盖新mode/P1-only与6个wrapper重hash负向检查，未声称深层自洽DTO或浏览器安全证明。

所有正向页面DTO均来自实际HTTP/ASGI和原应用连接的自有临时PostgreSQL，完整HTML由NodeVM加载；不是浏览器或视觉验收。独审PG自然退出且data由原fixture清理，没有发信号或触碰未知资源。

## 失败保全及并发限制

开发窗1收集16、止于6：5PASS/1FAIL，pytest1.51秒。false授权不足以证明旧inactive行，初版误把partial共同成员指纹差异列确认changed；收紧产品、页面、合同为observation_changed。开发窗2收集16、止于11：10PASS/1FAIL，18.13秒；`FOR SHARE`要求UPDATE，原SELECT-only角色在synthetic_resources查询准确拒绝并返回500。已移除锁子句、保留原SELECT权限和读后epoch复核；没有增加角色/授权，也没有重试被拒锁操作。

开发窗3仅收集6、止于3：2PASS/1FAIL，76.17秒。测试先删固定第一资源授权，原add_resource helper复制其空授权，注入行不在owner查询/epoch中，200正确；改为第二个自有资源并先断言注入行有active READ，再期待epoch409。此窗未冻结且加载后有编辑，不签冻结成绩。开发窗4只重跑剩余4选择器，4PASS/0FAIL/ERROR/SKIP，53.50秒；之后最终冻结完整16窗独立运行。上述三次失败原stdout/JUnit均保留，开发窗口不累加到最终PASS。

新读取采用原READ COMMITTED和最后来源epoch比较，可拒绝本次测得的读间变化；没有全资源行锁或跨事务原子快照，可信外部管理员在最终检查后的提交仍属原并发边界。根继承证据只读校验器两次因逐文件进程/大内存聚合而主动终止，随后改流式hash；控制器调整另记，不当作产品测试失败或通过。没有重试先前浏览器sandbox或root/seal/发行拒绝。

[根JUnit](evidence/resource-query-members-20261018/runtime/frozen-09ea9921/results.xml) · [独审稳定报告](evidence/resource-query-members-20261018/independent/independent-final-review.json) · [实际计数](evidence/resource-query-members-20261018/runtime/counting-verification.json) · [失败台账](evidence/resource-query-members-20261018/runtime/failure-ledger.json) · [归档配对manifest](evidence/resource-query-members-20261018/manifest.json)。独审报告SHA256 `614ae700658e2e1d368a8fa6744cf69120f9479aeee6fabee2a71dc0612358fa`。公开112个唯一raw/public配对，108对字节相同，仅4份开发失败stdout/JUnit中的8处临时会话值/截断片段最小脱敏；私有原件保留。全部配对hash及JSON/JSONL/XML解析通过；82个已知临时会话全值与16字符前缀、2个凭据片段公开匹配均为0，详见[归档校验](evidence/resource-query-members-20261018/archive-validation.json)、[保密扫描](evidence/resource-query-members-20261018/confidentiality-validation.json)和[验证范围](evidence/resource-query-members-20261018/validation.json)。首版保密扫描误把历史文件名中的确定角色名片段 `ep-specialist-fixture-a` 当凭据，首版归档及诊断保留私有；仅排除这一确定角色名，不放宽实际会话扫描。原件之外4个衍生元数据不算测试或raw配对。

源码、合同、测试及报告空白检查exit0；原始证据检查exit2的2处空白告警保留，不修剪日志。交付在09ea后只增加报告与证据；源码、合同和测试780个冻结输入保持。34114个继承F2证据逐一核对保持，远端预检124个heads未变；实际交付完整SHA、推送/抓取结果、全部heads差异和目标分支0/0，以本地 `.runtime/resource-query-members-20261018/delivery-and-remote-verification.json` 的网络回执为准，不预写推送成功。

## 真实运行仍缺的输入

读取需要已有合法当前会话、同域READ/PREPARE、原Case/Run/preparation、精确当前目录与来源、当前机会卡/账本、原计划及核验历史。完整成员差异还需要历史真实保存过的完整规则/授权查询原件且可与原集合stamp复证；历史未保存的原行不能由当前值补，保持UNKNOWN。无P2不能用资源mode；当前无权资源不读详情，超界与来源epoch变化准确拒绝。

实际业务执行另需原有REVIEW_ASSIGNED、原EXECUTE/资源权限、精确Run的既有executor assignment及相应独立批准。本片没有创建这些authority。普通configured_app provider可信宿主注入、正式来源独立验真/当前head和撤销、主体/Case/Run/已采纳方案绑定及正式批准映射仍有缺口；NativeRunAccess permit/writer继续默认拒绝，IsolatedPlanApproval或临时合成fixture不能充普通批准。

未新增真实身份、Grant、分派、目录发布、批准、凭据、费用或安全网络权限；未调真实模型、改main、强推或部署，不动未知锁/进程。真实浏览器、Windows/Win11、正式AT、真实主体/来源/园区、生产宿主及现实履约均未验；远端Actions未运行。当前无本片代码交付阻塞，不能因此宣布完整项目或真实运行完成。
