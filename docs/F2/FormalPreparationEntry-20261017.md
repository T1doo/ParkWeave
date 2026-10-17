# 正式资料来源入口预检与未实现边界

基线 `0fbd39513cf9aaf90375a28c01be4534414186a9` 保持在原开发分支供并行独审；本片另用 `dev/f3-formal-preparation-entry-20261017`，只有当前代理写源码/Git。原143项交付成绩不迁入本片最终成绩。没有访问已拒绝的Actions、真实来源、模型或部署，不改main/强推，不创建身份、Grant、分派、批准、凭据或安全权限，不删除未知锁/进程。

## 源码原因：缺外部资源与缺代码不是同一件事

原方案[权限与资料设计§11、数据分层§12.1及无真实条件§12.4](../平台产品设计.md)要求当前授权、Case范围、运行身份与Grant取交集，合成/公开/授权真实资料分层；同时允许继续完成可运行软件与合成验证，没有要求普通代码开发再次等待批准。

当前正式业务未实现，依据不只是一条namespace判断：

| 原路径 | 实际限制 |
| --- | --- |
| `src/parkweave/schema.sql:13`、`:31` | runs.namespace和cases.source的CHECK只允许SYNTHETIC |
| `src/parkweave/migration-009.sql:5`、`:18` | preparation_catalog和preparations的CHECK只允许SYNTHETIC，外键指向上述Case/Run |
| `src/parkweave/preparation.py:CreatePreparation/create` | service_id固定合成服务，创建固定写入SYNTHETIC |
| `src/parkweave/ordinary_runtime_read.py:selected/_catalog` → `preparation.entry_context` | 要求当前合成资料、精确合成目录及已有成功本地Case来源 |
| `src/parkweave/native_run_access.py:_source` | 验证SYNTHETIC Run/Case、case.create、SUCCEEDED/LOCAL_CASE_CREATED与独立本地Operation回执 |
| `src/parkweave/store.py:__init__/create_run/finish` | mode仅LOCAL/FAULT_INJECTION；建Run与Case固定合成，不存在正式业务存储模式 |

因此已有会话、READ/PREPARE或REVIEW_ASSIGNED、DSN及普通Run READ配置不能把现有表变成正式来源；单删namespace/kind或相信provider自报REAL/verified会破坏既有证明，不能这样接线。原SQL、身份/权限、NativeRunAccess及合成来源/资源批准算法均保持。

正式只读读取可以在将来使用独立来源适配器，而不先把现有表改为REAL；现有Store可只承担已存在会话与本地Grant检查。上表说明不能把原合成表/回执当正式来源证明，不是把数据库迁移说成所有外部只读接线的必需前置。

尚缺的**产品代码**：针对具体真实来源的资料、Case、Run、已采纳方案及当前主体授权的独立核验器，源域内当前head/撤销与完整绑定，正式方案来源指纹及资源批准映射；若要把正式数据持久化到本地，另需明确存储/迁移合同。现有SYNTHETIC表不能自动复用。尚缺的**外部开发/运行输入**：有权使用的真实来源结构、稳定ID/修订/指纹及当前head/撤销协议、既有记录与主体授权合同、已存在的信任机制及获准只读宿主接线。没有取得这些结构，不能编造一个“真实成功”证明格式来替代。

## 需要来源提供者给出的具体开发输入

以下需要现有说明/脱敏结构与公开引用，不要求提供密码、私钥、新身份或新增授权；拿到结构后，专用解析/核验与映射代码由本项目实现。

| 提供方需明确的字段或语义 | 已有接口位置 | 本项目仍需实现 |
| --- | --- | --- |
| 来源的规范source_domain、source_id、数据类别、现有只读接口/文件格式及用途限制 | ReadConfig、FormalSourceReader | 针对此来源的只读backend；现无自动发现或网络访问 |
| 资料/Case/Run/已采纳方案的原稳定ID、对象类型、相互关联、owner/当前reviewer和park/org；若不同命名，给出字段映射 | SourceReference、Selection的preparation_id/case_id/run_id/plan_id；FormalReadLookup当前本地主体 | 独立重建/核验四对象关系；不能按同名UUID连到合成表 |
| 资料revision、方案revision、服务ID/version、来源修订指纹；指纹算法、规范化、覆盖字段与当前head读取规则 | Selection与ReadConfig.binding；source_revision_sha256 | source-specific指纹/当前版本核验与正式方案绑定 |
| 既有方案的明确采纳决定记录ID、对应方案版本/指纹、决定主体/时间、当前有效/撤销语义；Run成功含义与原独立回执语义 | IndependentProvenanceVerifier；EXISTING_RUN/EXISTING_ADOPTED_PLAN要求 | 实现此来源的原始证明核验；不能套LOCAL_CASE_CREATED或测试采纳回执 |
| 源主体ID到当前本地主体ID的合法映射、原授权依据ID/修订、精确Case/Run/用途/角色/字段范围、生效/到期/撤销及当前授权head | FormalReadLookup与CURRENT_SOURCE_SUBJECT_AUTHORITY要求 | 源主体/当前授权核验；本地READ/PREPARE不自动证明源Case分派 |
| 已存在的签名/发行者/信任引用与验证协议、签名覆盖字段、当前head及撤销查询、有效期时区语义；只给公开机制说明 | IndependentProvenanceVerifier的source_domain/contract_id；verify_existing(lookup,raw) | 对应协议的独立验真adapter和抗旧版本重放核验；不创建信任根或签名凭据 |
| 正式资源批准的来源、方案/动作/来源绑定字段、主体授权/有效期/撤销与当前版本协议 | 既有资源批准只读契约可作字段参考，但其Scope仍是本地合成绑定 | 正式provenance到独立资源批准的映射；不得把旧SYNTHETIC Scope或Run READ签名直接复用 |

入口预检的unimplemented_*字段表示代码缺项，external_inputs_required表示上述外部开发/运行输入。当前没有source-specific成功合同；“提供provider对象/JSON配置”本身不能解决这些证明，也不能成为真实成功验收。

## 本片实际实现

新增 `formal_preparation_entry`，实现必要接口、类型、源域绑定与默认拒绝预检；**没有正式记录读取成功分支**，不称正式数据已经接入。

`SourceReference`将源域、对象类型与原ID组成引用；相同ID在不同源域或PREPARATION/CASE/RUN/ADOPTED_PLAN中不互认。`FormalReadLookup`还固定当前主体ID/租户/园区/角色及READ_EXISTING_PREPARATION用途，不接收token或verified授权字段；它本身仍不是来源授权证明。`Selection`固定四个原ID、资料/方案revision、服务版本及来源修订SHA。public ReadConfig仅缩小到现有租户/园区与一个精确选择，不能提供凭据、proof、verified、allow_synthetic或writer参数。

可信宿主可以显式提供 `FormalSourceReader` 与独立 `IndependentProvenanceVerifier` 接口；HTTP和环境字符串不能加载Python模块、创建信任根或注册验真profile。SYNTHETIC_CONTRACT_FIXTURE/PUBLIC类型拒绝，原IsolatedPlanApproval、NativeRunAccess和资源批准reader也不是正式证明。声明AUTHORIZED_BUSINESS仍不是证明；即便两个回调都存在且声明匹配，未知来源合同保持 `FORMAL_PROVENANCE_CONTRACT_NOT_IMPLEMENTED`，**read/verify回调均不调用**。没有Boolean启用、动态注册或复用旧ID/签名/历史的后门。

`configured_app`从显式 `PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG` 读取最多16KiB公开JSON，仅解析与校验；默认不提供，缺项拒绝，不读取文件/凭据或连接外部来源。provider/verifier只能由已获准的可信宿主代码注入；这个Python组合接口不是未知插件沙箱，也不是生产后端安装证明。

两个GET：`/api/formal-preparations/entry-status`只核对当前已有会话及原READ＋角色对应preparation Grant和接线条件；`/api/formal-preparations/entry`另外核对完整固定Selection。前者没有选择任何正式记录，后者不接受重复/额外查询参数。两者均不调用原合成资料/Run/Case读取，也不把本地Grant等同于真实Case分派或来源授权。真实主体授权始终标false。

结果固定UNAVAILABLE、read_only=true、source_access_attempted/business_record_read/entry_available/source_proofs_verified/current_source_subject_authority_verified/approval_granted/resource_plan_approval_available/execution_authorized/decision_writes_enabled=false。结果分别列unimplemented_source_contracts、unimplemented_integration和external_inputs_required，不能把所有缺项都写成“缺用户凭据”。POST无入口。

原页面新增“正式资料来源·入口条件”，仅在用户明确点击时GET预检。用现有会话，不输入/上传企业正文，分列缺产品实现与缺外部输入，说明本次未访问外部来源。身份切换、ABA与迟到回复不恢复旧结果；旧材料操作未决时先沿原恢复入口核对。原合成资料入口继续原路径，并明确其合成范围。

## 验证解释

测试全部为隔离合成合同/拒绝证明。标记AUTHORIZED_BUSINESS的测试接口也只用于证明“自报标签和回调不够”，始终不可用、回调计数0；没有将fixture作为普通合法业务来源。浏览器只验证默认不可用、原普通子进程冷重启仍不可用、当前撤权及迟到/身份ABA，HTTP与PG为实际本地自有组件。迟到200的原因字段和403为客户端故障注入，不能当真实来源变更或真实后端核验。

Windows/正式AT、真实业务来源与合法主体、生产host适配器正向接线、正式批准和完整项目仍未验收。后续必须依据既有真实来源结构实现上述专用证明和映射后，另行验证；当前不是仅等待运行密码就能开启的成品。

## 最终冻结与实际验证

源码冻结 `e4160e51c063764dba66aaf72bde37efeb881a81`，723输入无漂移。八个完整相关模块 **186唯一项PASS，0FAIL/ERROR/SKIP，JUnit 560.825秒**；新增40项接口/纯契约及3项浏览器拒绝用例已含内。原143项在本片新SHA重新执行，不加历史成绩；不是全仓、正式AT或真实来源正向验收。

| 完整模块 | 唯一项 |
| --- | ---: |
| `tests/test_formal_preparation_entry.py` | 40 |
| `tests/test_formal_preparation_entry_browser.py` | 3 |
| `tests/test_resource_plan_approval_read.py` | 50 |
| `tests/test_resource_plan_approval_read_browser.py` | 6 |
| `tests/test_ordinary_runtime_read.py` | 31 |
| `tests/test_ordinary_runtime_read_browser.py` | 5 |
| `tests/test_native_preparation_entry.py` | 16 |
| `tests/test_preparation.py` | 35 |

开发窗dev-v1的38PASS及edge-v1的2PASS分别保留且与最终重叠，不相加。首窗结束后补充主体/用途Lookup、禁止旧signature/history/approval字段及严格布尔revision拒绝，再正式冻结。首窗原五个源码/测试文件、原diff与调用记录保留，未把WIP标成最终冻结。

首版归档把两条普通Git分支名误当43字符会话值脱敏，共4处；首版完整副本、原helper及错误记录保留，加入原远端引用白名单和逐字节一致性检查后重新导出，不重跑测试。

一次web apply_patch因整行上下文不匹配未应用，API补丁已独立成功；核对后完整应用web补丁。执行通道一次transport disconnected，随后一次pwd确认恢复，原pytest PID及session继续，未重复启动测试；落盘证据确认继承核对实际完成。错误、恢复及结果保留于action-failures.json，不推断产品根因，不扩连接诊断。

继承27785个F2证据blob未改；所有原src文件除API接线和页面外逐字节保持，新增formal模块只做封闭预检。原SQL/身份/权限/NativeRunAccess及合成来源/资源批准算法保持。实际远端98个原头及main在交付前未变，0fbd独审分支仍冻结。

归档56对原件/公开件hash已核对，JSON只脱敏字符串值并保留键、严格拒绝重复键，JUnit标识/属性保持。原始私有文件不覆盖。

[最终gate](evidence/formal-preparation-entry-20261017/gate.json)、[完整JUnit](evidence/formal-preparation-entry-20261017/final-v1.xml)、[原日志公开副本](evidence/formal-preparation-entry-20261017/final-v1.log)、[冻结723输入](evidence/formal-preparation-entry-20261017/freeze.json)、[原件配对](evidence/formal-preparation-entry-20261017/public-pairs.json)、[通道与补丁失败记录](evidence/formal-preparation-entry-20261017/action-failures.json)。

交付提交仅添加报告/历史状态和证据；实际交付SHA、远端与未提交差异于提交/推送后写入私有 `.runtime/formal-preparation-entry/delivery-verification.json` 和最终回复。新片待独审。正式来源读取卡点尚未全部解决：未知来源结构下本片只交付必要接口/类型与拒绝面；专用证明/绑定/批准映射仍须由本项目依据上表具体输入实现，不归因于单纯环境或凭据。完整项目未完成。
