# 本事项办理记录核对包

基线 `b0f3cb8d69f33413ff8ac06b4be03b39d2fe5da2`；最终冻结源码 `8842a38a65a2b558939a6f26a41b9b2c95c86c9a`（首个功能提交637c66ab的失败窗口另存）；开发分支 `dev/f2-case-record-pack-20261017`。

## 用户得到什么

原来企业owner可以在线逐目标查看实际本地记录，却不能把本事项全部必需目标、未满足原因与原核验对应关系带走核对。本片在原“同Case必需目标总览”加入生成及下载UTF-8 TXT，保留当前完整目标顺序，包括不支持、等待、未采用和整体PARTIAL。它是新增便携核对视图，不是新增办理、审批或线下履约能力。

实际路径：用已有合法会话打开已有资料事项 → 点击“此Case持久步骤计划”原入口 → “只读核对逐目标结果” → “生成本次核对包” → “重新核对并下载TXT”。未取得当前结果时不允许直接导出。无合法身份、PREPARE、READ、原owner或当前资料/来源条件时，原接口继续准确拒绝，不创建身份、Grant、分派、目录或批准。

原V1没有单独点名“整事项核对包下载”。依据是[产品§3](../sources/V1/平台产品设计%20(2).md)83–89行的一事项概览/步骤/材料/记录、§5.2的完整必需目标和步骤交付/验收、§5.5的实际状态和软件记录/线下履约区分、§11的导出隔离及凭据不入包，以及[原开发计划F2-T02/T04/T07](../sources/V1/分阶段开发计划%20(2).md)85–102行的目标覆盖、角色办理、完整记录及PARTIAL。原方案全部业务验收仍未完成。

| 现有功能 | 原范围 | 本片的增量 |
| --- | --- | --- |
| 原资料文本包 | 当前双槽正文、来源标签、补正与准备度 | 不重做正文导出；整事项包仅引用允许输出的资料ID/版本/指纹 |
| facts.assess历史比较 | 原独立检查与当前字段来源对照 | 不合并事实正文，不当成Case采用或办理证据 |
| P4/P5历史summary | 独立资格和锚定来源下的隔离历史摘要 | 不调用或绕过其默认拒绝入口，不宣称全量历史 |
| goal-results | 在线逐目标结果、当前允许的产物引用、原采用来源 | 同一算法的便携文本视图，完整目标与版本绑定 |

## 内容、读取和指纹

包包含当前/原诉求，preparation/Case/Run/plan ID及preparation/request/plan revision；全部当前必需目标、原状态/原因/下一步；当前可读记录的最小引用；原owner核验事件及current真假；已有人工责任、阻塞和原答复来源指纹；原采用来源、步骤合同指纹及旧计划引用。未采用且不支持的目标没有人工记录时明确未提供，不填造NOT_REQUESTED或责任人。原采用目标与当前目标分别保存，最多8项当前目标不能按6个注册类型裁剪。

后端仅在原`case_goal_results.read`同一parent读取里补`current_required_goals`，不重做身份、来源、P1–P5、依赖、核验或采纳算法。前端复用原`GET /api/preparations/{id}/goal-results`、原摘要函数及`goalSourceWritePending`。生成和每次下载各重新GET两次：当前身份/owner、事项与各版本须匹配已展示结果；所有目标与行顺序一致；原行/原trace SHA核对通过；两次最新白名单投影均须与已展示投影一致。请求使用`cache:no-store`，下载不读取缓存或可编辑textarea正文。

整包“核对数据SHA256”覆盖完整允许导出的投影，含全部当前目标、行、原采用来源引用、旧计划引用及限制。可按UTF-8 JSON（`ensure_ascii=False`、键排序、紧凑分隔）重算该指纹。原`result_sha256`与`trace_sha256`引用原接口完整对象；白名单裁剪后的子对象不承诺能重算原指纹。原trace明确`historical_adoption_only`，不能冒充当前全部来源证明。两个不同底层来源可能产生相同允许投影，因此整包指纹不是全来源原子快照、管理员重写防护签名或独立履约证明。

资料、资源状态、期限或权限变化未必增加资料/计划revision；再次读取会按原算法判断当前产物和核验是否有效，所列结果变化即清除候选并要求原入口重读。有限重读不能消除最后一次服务端读取至客户端下载间的外部变化，已下载副本无法收回。包明确SYNTHETIC、资格NOT_EVALUATED、外部NOT_SUBMITTED、线下NO_EVIDENCE、case_goal_completed=false。

只输出字段白名单。资料/事实/回执正文、私有源快照、生产者对象、目录完整对象、Grant/permit/运行批准/凭据、数据库或文件路径均不入包。V4服务选择仅保留既有release/instance/service/park ID、版本与指纹，排除角色/资源/输入字段映射。已有事件actor ID仅表示本地责任引用，不是授权。

读取前、每个异步阶段后及Blob前均复查完整未决写门。原在途/UNKNOWN操作及恢复句柄阻止输出；当前真实403优先清私有内存/DOM，原不透明恢复句柄保留。身份ABA、换Case、计划/草稿/读取代际改变后，旧200/403不覆盖新上下文。按钮禁用状态在本片控制刷新时更新；不能把动作门拒绝冒称所有原写入都实时更新了按钮外观。包和token不新增localStorage持久化。

无新业务端点/POST、表/列/迁移、Grant、批准或完成事件。旧浏览器回归增加产物目录环境覆盖，各窗口输出到本片独立目录，避免覆盖原私有证据。完整回归还暴露原材料冷恢复在嵌套读回新上下文后继续使用旧上下文的问题；外层现检测上下文已替换便停止旧读取，保留原鉴权、恢复句柄和CAS规则。原权限、存储、运行访问默认拒绝和资料四格式/CR编辑代码均保持。

## 最终冻结与实际验证

最终冻结源码`8842a38a65a2b558939a6f26a41b9b2c95c86c9a`上的9个完整相关模块 **179唯一项全部PASS，0FAIL/ERROR/SKIP**；pytest1291.39秒，JUnit1291.378秒。新增31项已含内，不把开发窗口、18项修补复核或独立探针相加。728个源码/测试/脚本/配置输入SHA256零漂移。

首个冻结窗口在源码637c66ab上为161PASS/18FAIL/0ERROR/0SKIP，新增31项当时也全部通过。原窗口与源码快照保全；最小修补后18个原失败节点另窗18PASS，再进行上述同9模块/179完整复跑，未将定向结果替代全窗。

首窗18项失败分为：15项原Node DOM替身没有classList，旧清理器调用remove即抛错；已补与className同步的add/remove/contains和状态自检，保留全部原拒绝/GET-only断言；2项原材料冷恢复嵌套刷新后外层检查过时上下文，已停止外层旧读取；1项两秒资源窗口在P5验证时已到期，尚未进入预期锁等待。该测试改为先留10秒完成原验证，再按PG当前时钟等待至余1秒后提交读请求，仍观察真实最后来源行锁并跨期释放、保持原生产3秒锁超时和全部原断言。

| 完整相关模块 | 唯一项（新增31已含） |
| --- | ---: |
| tests/test_case_record_pack.py | 31 |
| tests/test_case_goal_results.py | 44 |
| tests/test_case_goal_results_browser.py | 28 |
| tests/test_plan_source_trace.py | 7 |
| tests/test_multi_goal_overview.py | 27 |
| tests/test_multi_goal_overview_denied.py | 11 |
| tests/test_native_preparation_entry.py | 16 |
| tests/test_native_preparation_entry_browser.py | 5 |
| tests/test_material_csv_newlines.py | 10 |

开发证据分别保留：dev-v1实际普通入口/下载/进程重启1PASS；dev-v2为17PASS/9FAIL，9项失败均发生在Playwright无法包装内建`list.append`监听器，尚未运行到对应否定场景，修成普通lambda；edge-v3受影响边界11PASS（17 deselected）；dev-v4新增离线候选来源及读取失败3PASS（28 deselected）。独审还在冻结前指出未采用不支持目标缺少human字段的可用性问题，已保留缺失而不臆造，新增实际浏览器覆盖。所有失败日志/XML和对应dev-v2源码快照保全。

独立只读审查覆盖新冻结完整功能及三项修补，A/B内存探针退出0，前后728文件各零漂移。包含8个完整目标、PARTIAL、私有字段排除、V4八字段引用、两GET/动作、UTF-8实际Blob、textarea改写不入下载、同revision投影变化、当前403优先UNKNOWN和迟到上下文保护。跨Python/实际Node摘要一致。它们不计入179；归档stdout是审查者报告的全文转录，根线程未复跑。首次辅助脚本误把独立合同当728映射键而KeyError，保留失败，改为单独计算合同hash后先通过前置核验再执行A/B。

## 仍缺的真实运行与正式验收

普通已有合成记录读取仍须合法原会话、原owner READ/PREPARE、已有同Case/Run/preparation及当前精确目录/资料来源；原专员与目录前置条件不由导出补齐。真实来源接入还缺具体来源结构、稳定ID/修订/指纹、当前head/撤销协议、源主体与本地主体的合法映射和用途授权、已有信任机制及获准只读宿主适配器；产品仍须据此实现专用证明/绑定和正式方案/资源批准映射，不能仅填provider对象或复制隔离测试文件。详见[正式来源入口报告](FormalPreparationEntry-20261017.md)与[已有资源方案批准读取报告](ResourcePlanApprovalRead-20261017.md)。

| 运行层次 | 仍需的已有输入/实现 |
| --- | --- |
| 本地普通合成记录读取 | 当前合法会话与原owner的READ/PREPARE；原preparation/Case/Run ID与相互绑定；原service ID/精确版本和preparation_catalog；原已采用计划/当前资料及各revision。不由本包生成这些对象。 |
| 正式资料来源 | source_domain/source_id、四对象的原稳定ID/类型/关联、owner/reviewer与park/org；preparation/plan revision、service ID/version、source_revision_sha256及规范化算法；当前head/撤销协议。 |
| 正式当前主体与证明 | 已有源主体→本地主体映射、用途/Case/Run/角色/字段范围、原授权依据ID/revision/生效/到期/撤销；既有采纳决定ID/方案指纹/主体/时间；原独立Run证明和已有公开信任验证协议。 |
| 可信宿主与产品代码 | 获准只读backend/宿主接线；按具体来源实现FormalSourceReader/IndependentProvenanceVerifier对应的独立证明、绑定与当前版本核验；正式方案与资源批准映射。仅填PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG或传provider对象仍不可用。 |
| 正式资源已有批准 | 原批准source/record ID、revision、主体/原授权依据、对应方案/动作/来源绑定、生效/到期/撤销与当前head/验真机制；不复用IsolatedPlanApproval或测试签名文件。 |

本片不提供真实业务身份、目录发布、批准、分派、凭据或模型账号。Windows原生正式AT、真实园区/企业来源和履约、生产host正向来源接线、真实模型、部署及全项目验收仍未执行。V4服务选择的整包实际普通进程下载、独立隔离执行报告的整包下载，也不以本片确定性/离线候选正向链冒称已全面验收。

## 证据与交付核对

[最终gate](evidence/case-record-pack-20261017/gate.json)、[最终完整JUnit](evidence/case-record-pack-20261017/final-v2.xml)、[实际完整日志公开副本](evidence/case-record-pack-20261017/final-v2.log)、[首个失败窗口](evidence/case-record-pack-20261017/final-v1.xml)、[18项修补复核](evidence/case-record-pack-20261017/repair-v2.xml)、[全部窗口与工具失误](evidence/case-record-pack-20261017/failure-ledger.json)、[冻结清单](evidence/case-record-pack-20261017/freeze.json)、[独审范围与命令](evidence/case-record-pack-20261017/independent-review.json)、[原件/公开件hash配对](evidence/case-record-pack-20261017/public-pairs.json)。

[普通进程重启与下载证明](evidence/case-record-pack-20261017/browser/final-v2/test_actual_original_entry_all0/proof.json)、[390px实际截图](evidence/case-record-pack-20261017/browser/final-v2/test_actual_original_entry_all0/record-390.png)。实际Chromium也检查1200/390/320px没有横向溢出；TXT下载逐字节匹配新鉴权结果，未从textarea读取。包的实际普通进程正向来源为隔离合成已存记录，不能冒称正式业务来源。

[当前源码推送前核对](evidence/case-record-pack-20261017/preservation-final-source-pre-delivery.json)确认728输入及28113继承证据Git blob零变化、实际远端101个原头和main未变；[实际祖先核对](evidence/case-record-pack-20261017/source-ancestry.json)确认db108、已准入b0f和预检实际main均为新源码祖先。先前637核对原件另存，未覆盖。

316对原件/公开件hash逐对匹配；严格解析全部99个JSON无重复键、7个JUnit XML可解析。仅4处临时合成会话值脱敏，JSON仅处理字符串值并保留所有键，JUnit标识/属性及远端引用逐字节保留；私有原件不覆盖。

交付检查中，全暂存区`git diff --check`返回2：168处均为保留的pytest失败日志/JUnit traceback及patch上下文尾空白。未格式化证据；完整输出另存私有delivery-whitespace-check.log。源码/测试/合同的基线至冻结差异、README/本报告分别检查均返回0。

交付提交仅添加README状态、本报告及公开证据。实际交付完整SHA、普通推送结果、推送后实际远端0/0与干净工作树，在完成后写入私有`.runtime/case-record-pack/delivery-verification.json`及最终回复；不预填尚未发生的远端成功。没有main修改、强推、部署、真实模型、Actions查询、新费用、真实身份/Grant/分派/目录/批准/凭据或安全网络权限；未知锁/进程未删。当前切片待父线程准入，完整项目未完成。
