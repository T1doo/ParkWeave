# F1 真实日志

## 2026-10-05 DOC-001

仓库 origin=https://github.com/T1doo/ParkWeave.git；初始31e7acb7e53bb1ab6465b9daae59de28757f7583，work干净；新分支dev/f1-foundation。仓库与工作区没有可读AGENTS.md或相关技能文件。没有访问Sim2Act或用户电脑。

完整Library read：454行44220字节、410行31271字节；has_more=false。文本响应均少一个末尾LF；补一个LF后精确匹配元数据，哈希见sources/V1/manifest.json。原件不可修改，工作正文追加授权小修。

新增验收规格由全文转录，未收到原JSON/DocumentReview等原包附件；初态与执行器待实现，全部NOT_RUN。文档完整性核对PASS，仅为文档检查；产品测试NOT_RUN。模型/Windows/真实园区主张BLOCKED。代码提交：本记录随文档提交，实际SHA在下一日志记录。

## 2026-10-05 ENG-001（首个有界工程增量）

文档基线提交00f1d8a317e6676c9139cb8d9f6702ee504617a5，已push并用git ls-remote核对一致。本记录随首个工程提交；实际提交SHA通过Git历史/交付链接关联，执行代码逐文件hash见evidence/engineering-manifest.json。

变更：自建Python包/API/独立worker/PostgreSQL迁移及应用角色权限、严格0.1契约投影、有限三值函数、可信case.create/1、事务Operation/Receipt/outbox、租约fencing、当前授权锁、暂停取消、三工作区骨架；全部合成，本地建单不推进业务履约。没有访问或复用Sim2Act代码，没有调用真实模型API。

实际环境：Linux云x86_64，Python3.12.14，PostgreSQL16.2（pgserver0.1.4测试分发），其他精确版本见requirements-linux-evidence.txt。API/worker端口/PID、运行/操作ID、输入hash及状态见evidence/http-smoke.json；它们是本次历史进程证据，不代表一直在线。Windows精确版本尚未测。

失败与修复：
- 默认uv缓存/home/agent/.cache只读→失败；指定工作区缓存后安装成功。
- 第一次pytest：10 FAIL / 11 PASS。身份表FOR SHARE要求UPDATE权限，与最小角色冲突；改为共享advisory授权锁，owner撤权同键独占锁，不给应用身份修改权限。第二次21 PASS，最终21 PASS，见pytest-final.txt。
- 浏览器默认socket目录只读→指定XDG_RUNTIME_DIR；后续缺少容器沙箱参数失败→每次明确Chromium及--no-sandbox（仅测试容器）。初始UI刷新验证失败；点击轨迹显示布局切换后点击落在html根节点，补页面快照与语义定位后流程通过。另修复UI吞掉错误，显示请求错误。临时诊断和截图未纳入交付。

实际命令：uv venv/uv pip install；python -m pytest -q --tb=short；python scripts/linux_fixture_server.py（启动独立API/worker）；agent-browser0.38.2本机Chromium验证，由scripts/browser_smoke.py复现。浏览器open/页面内容/三入口/受理及状态读取PASS，错误为空；实际HTTP202、Case NEEDS_INPUT、Run LOCAL_CASE_CREATED、跨园区403，工程PASS。均仅Linux合成工程结果；未映射整个AT为PASS。

剩余：完整AT/EX NOT_RUN；AT-01/02/34的Windows/真实模型门BLOCKED，真实园区效果BLOCKED。资格自动判断、资源预约、文件导入、多角色/字段Grant、外部结果不明、长任务心跳、共享总限流/成本都未完成。Schema0.1仅当前投影，不宣称V1全契约已实现。C0模板正文/关联作品政策/截止时刻仍BLOCKED，用户当前报名和提交日期2026-11-05。

所有依赖为安装的上游包，不复制依赖源码/二进制进仓库；Linux测试包pgserver不作Windows运行依赖。当前未开展开源许可证发布选择，不宣称整个仓库已有开源许可。提交前排除.venv/.cache/.runtime/egg-info；审查差异及高置信秘密模式，原件hash重验。合成会话、数据库文件、访问日志与截图不提交。

下一步候选：补V1完整领域契约与事实冲突；增加作用域Grant与各角色；独立FAULT_INJECTION外部未知结果账本。Windows及模型条件未满足前保持对应门BLOCKED，不自动进入F2真实办理。

## 2026-10-05 ENG-002（第二有界F1增量）

基线05625e07db8d8b633843b40b92abfeb398c4ec9e，dev/f1-foundation干净，远端仍T1doo/ParkWeave；没有新增可读AGENTS/技能规则。复核Plan/AT后选择独立基础缺口：结果不明的持久核对与计划契约边界，不进入F2。

新增FAULT_INJECTION账本原型：测试单独安装fault-schema，模拟远端效果独立事务；DISPATCHED持久化后才发送；OUTCOME_UNKNOWN只核对，不重发；暂停取消令旧worker回报失效、未知不会变“无影响”；撤权后不新发，但可记已派发历史效果且用户不可再读；回执按企业/园区/ID/指纹/来源精确核对。常规迁移/角色/API/worker不注册故障能力，正常库缺表，HTTP任意故障动作422。没有使用真实账号或聊天密钥。

发现并修复：基线领域契约错误接受重复必需目标、重复覆盖引用和17项重复覆盖。用固定基线源码在临时.runtime重现，证据eng002-contract-defect.json；新约束拒绝空白/重复/过长/非ID引用及重复依赖。当前0.1投影仍不是完整V1资格/材料/有效期契约。

测试命令：python -m pytest -q --tb=short；第一轮31 PASS，补契约后37 PASS，补派发前控制/过期后最终40 PASS（2 WARN，沿用httpx deprecation和pgserver runtime目录fallback）。13新故障断言+6契约边界+原21。最终输出eng002-pytest-final.txt，代码hash及环境eng002-engineering-manifest.json。没有将任何完整AT预填PASS。普通API/worker浏览器回归由scripts/linux_fixture_server.py及scripts/browser_smoke.py --report docs/F1/evidence/eng002-browser-smoke.json完成，实测结果以该文件为准；Linux不能替代Windows。

失败记录：本轮pytest无FAIL；先前契约输入错误接受有固定提交复现，不隐藏该缺陷。修复仅严格化未发布0.1契约。故障账本还未接入正常Run/worker/outbox，这是NOT_IMPLEMENTED，不当作已通过。Windows/LIVE/真实园区主张仍BLOCKED，全部完整AT/EX仍NOT_RUN。

没有修改Sim2Act、共用数据库、持续凭据或预算；全为自建合成。提交前将审查秘密/个人数据和原件hash；原件不修改。代码提交本条随ENG-002提交，准确SHA通过Git历史与最终交付链接关联。下一轮最合适独立工作：字段级Grant及事实冲突契约；另由具备条件的执行者办理Windows/真实模型门。

证据工具记录：一次误用系统python导入项目时ModuleNotFoundError；改用项目.venv/bin/python后schema和manifest生成成功，原件hash再次核对一致。此错误不隐藏，未当产品测试FAIL或PASS。ENG-002 Linux Chromium回归PASS（202建单、持久读取、三入口、浏览器错误为空）；原ENG-001证据保持不变，新证据单独归档。

## 2026-10-05 ENG-003（正常worker网关与未知结果）

基线a1858b16846dfc981cad4a5aa23f8ea9abf96324，dev/f1-foundation干净，origin仍T1doo/ParkWeave。按父任务选定唯一主范围：把ENG-002核对语义接入正常runs/operations和真实API/worker，非只增旁路测试；完整V1契约/事实冲突/字段级Grant本轮不散开。

变更：ExecutionGateway连接正常worker；本地case.create和显式fault.record共用Store.locked_execution的当前身份、事务锁、租约/fencing；持久派发意图后才模拟效果，恢复只查不重发；未知自动观测最多3次（未知派发响应也计），之后保留RECONCILING，由当前授权手动核对重新启用查询；取消/暂停未知操作只记录意图并fence旧worker，已知效果不冒充撤销。已派发后撤权仍允许内核记录历史结果，不允许新发或原用户读。

Schema2为独立owner原子迁移，保留历史Run/Case/Receipt，版本健康检查改max(version)。显式fault模式需要API/worker双方配置及合成库fixture_effects权限；默认API422、LOCAL worker跳过故障任务。旧fault_operations旁路原型保留对照测试，但正常worker不使用它。没有新外部接口或真实调用。

真实路径：新增tests/test_worker_gateway.py启动uvicorn、HTTP客户端与独立CLI worker，使用最小应用角色及临时PG16.2库；崩溃注入after-dispatch/after-effect退出75，恢复按真实DB时钟到期（非手写Run终态），旧callback在同网关拒绝。迁移从原001历史库重建后检查ID和事实保留；无效回执只改变模拟远端输入，真实worker拒绝成功。已有40测试继续回归，完整AT没有预填PASS。

实际命令：python -m pytest -q --tb=short：初始40 PASS，新API/worker测试后51 PASS，追加迁移/无效回执后53 PASS，最终补默认模式拒绝派发测试的结果见eng003-pytest-final.txt（14新增+原40）。本轮pytest无FAIL；预期负例是旧fence Conflict、撤权403、非法回执EFFECT_KNOWN_INVALID、未来DB版本Conflict，并未当意外失败删除。两个既有WARN保留：Starlette/httpx弃用和pgserver runtime目录fallback。

实际连续运行：python scripts/linux_fixture_server.py --fault-fixtures（Linux云、独立API/worker、PG16.2、127.0.0.1:8765），python scripts/browser_smoke.py --report docs/F1/evidence/eng003-browser-smoke.json，python scripts/gateway_smoke.py。浏览器PASS；实际HTTP轨迹QUEUED/PREPARED→RECONCILING/OUTCOME_UNKNOWN→SUCCEEDED/VERIFIED，success_scope=FAULT_INJECTION_EFFECT_KNOWN，Case=null，跨园区403。输入hash、run/operation ID与历史PID见eng003-gateway-smoke.json，源码hash见eng003-engineering-manifest.json。模型0次调用，全部明确合成或FAULT_INJECTION，不代表真实外部受理/线下履约/模型链或Windows通过。

剩余：完整V1契约、事实冲突、字段级Grant及其他角色、长等待心跳、outbox撤权/消息完整语义与固定AT全执行器尚未实现。Windows/LIVE/真实园区条件保持BLOCKED，完整AT/EX NOT_RUN，F1未通过。未修改Sim2Act、未共用其数据库、未配置持续凭据、未读取隐藏密钥；提交前秘密/个人数据及原件hash检查，测试数据/会话/截图/访问日志不提交。实际代码SHA本条随工程提交，通过Git历史和交付链接关联。

最终回归54 PASS / 2 WARN（20.12秒），包括原40与新增14条实际API/worker/PG路径测试。当前仅该明确工程范围有PASS；完整AT/EX未改状态。本轮没有意外FAIL；所有注入失联和负例均保留断言与日志，不删用例。浏览器及连续worker HTTP证据各自单独保存，不覆盖ENG-001/002历史。

## 2026-10-05 ENG-004（心跳、V1最小结构、事实/字段Grant）

基线eb8b38bb7d538400fad6a2c143f6c9a1d6cc7fb5，dev/f1-foundation干净，远端T1doo/ParkWeave。范围限定当前事实闭环与长等待租约，不开展F2组合服务。用户新确认电脑Windows11；这是自报系统家族，精确构建/架构/原生实测/安装条件仍BLOCKED。

实现：Schema3源事实断言与字段Grant/心跳计数；V1ServiceSpec/Plan/ActionSpec当前可信能力的全部V1必备最小结构，实际鉴权HTTP结构校验但不发布/执行；facts.assess经正常worker/Gateway读取当前READ Grant，在事务内保存来源/时点/证据/hash与冲突/缺证据UNKNOWN（资格NOT_EVALUATED，无Case）。字段READ/WRITE分开，Grant管理员CLI按同一principal授权锁撤回；app只SELECT Grant，seed不恢复撤销状态，Run结果读取重验，旧已送达输出无法本地收回。

独立LeaseKeeper线程/连接在主worker模拟模型等待期间以租约1/3（最大5秒）续租，不持长事务；DB时钟与fence/current授权始终检查。过期、取消或撤权停止续租及派发，kill后接管，旧heartbeat拒绝。模拟等待0—10秒，模型网络调用0，不能声称真实模型长请求/Windows验证。

安全配置命名协调：rg检查仓库此前没有INTERN/API_TOKEN读取器，本次新增resolve_intern_token显式Mapping助手：PARKWEAVE_INTERN_API_TOKEN优先，INTERN_API_TOKEN fallback，SecretStr不打印。只用虚构值测试，不读取真实.env/模型凭据；当前API/worker未调用该助手或真实适配器。用户安全注入与预算仍未完成，不从聊天/别任务复制密钥。

失败与修复保留：初始2 FAIL /52 PASS（旧迁移oracle仍期待Schema2）；更新Schema3/未来版本4，继续保留历史不变/未来版本拒绝断言。随后一个编辑脚本SyntaxError导致该改动与Grant seed未生效，新增测试12 FAIL /57 PASS（无Grant时API安全拒绝403，而非默认允许）；修正脚本并将合成owner seed显式初始化Grant，兼容旧schema无Grant表，已撤回Grant ON CONFLICT不恢复。修复后专项15 PASS。加入V1结构测试后全量78 PASS；最后补回执各证据有效期/适用标记并重跑78 PASS /2 WARN，44.68秒。没有放宽拒绝断言，没有隐藏失败。原有Starlette/httpx与pgserver runtime fallback两个WARN保留。

命令与实际路径：python -m pytest -q --tb=short；新tests/test_facts_heartbeat.py与test_v1_contracts.py使用实际uvicorn HTTP+独立CLI worker+临时PG最小应用角色，不用旁路执行器；长等待3.3秒/lease1秒，heartbeat>=2/当前租约有效，第二worker不能抢占；真实HTTP取消/owner CLI revoke-field及时返回；kill与旧heartbeat拒绝；跨企业/园区403和app Grant UPDATE InsufficientPrivilege。model_config只虚构Mapping，无真实key。初始失败输出在本轮日志列示，未保存带随机会话的pytest traceback进Git。

连续工程检查：python scripts/linux_fixture_server.py（LOCAL，PG16.2，Python3.12.14，127.0.0.1:8765）；python scripts/browser_smoke.py --report docs/F1/evidence/eng004-browser-smoke.json；python scripts/facts_smoke.py。重启服务以运行最终回执代码后browser PASS、实际两来源事实201→worker事实核对SUCCEEDED/FACT_EVIDENCE_ASSESSED，region冲突UNKNOWN、employees缺证据UNKNOWN、qualification NOT_EVALUATED、Case=null；跨园区读Fact 403。时点、输入hash、Fact/Evidence/Run/Operation ID、历史PID见eng004-facts-smoke.json，源码hash见eng004-engineering-manifest.json。

完整AT/EX仍NOT_RUN，新增24检查+原54是工程范围，不是完整验收成绩。剩余多角色/获派步骤Grant、审计、outbox当前授权/消息、文件边界、原生脚本/完整AT执行器尚未完成；LIVE/Windows/真实园区效果BLOCKED。不修改Sim2Act、不共用其数据、未持续配置凭据，原始Library文档不改；提交前代码与原件hash/秘密扫描，.runtime会话、数据库、日志、截图不提交。实际commit随本记录，通过Git历史与最终链接关联。


## 2026-10-05 ENG-005（权限交集、outbox、逻辑文件边界）

基线8abf48f276a0b991f215cde996eba7593884dfad，独立dev/f1-foundation/https://github.com/T1doo/ParkWeave.git，工作区干净；扫描未发现AGENTS.md或.agents/skills。本轮先新增ENG005-Mapping冻结任务/AT子范围，再改实现与测试。无子任务、无Sim2Act修改、不共用数据、不查看凭据/配置持续凭据、不调用真实模型或公网部署。

Schema4/5新增capability_grants/action_grants/run_assignments/deliveries/file_resources/authorization_audit，保留历史ID/回执/状态；seed ON CONFLICT不恢复撤销Grant。四角色可信角色上限与当前Grant交集、园区/企业owner或单Run状态指派、运行身份/租约/fence与可信动作/字段约束重验。其他三角色只见被明确分派Run的ID/state/revision/visibility；不给receipt/Case目标/企业事实/文件/执行/控制。旧owner改为非企业角色也不继承全量读。owner配置按principal独占锁，app只SELECT授权表，不能自行赋权或修改文件登记。当前还没有CaseStep/正式Service发布执行，不宣称F2多人协同通过。

正常worker处理现有case.create/facts.assess/显式fault.record，排队后撤EXECUTE或对应动作Grant→FAILED_SAFE，0Case/0fixture_effect。outbox与本地交付用同一当前授权锁+数据库事务；read/字段撤权后未交付SUPPRESSED，已有READY立即API403、worker下一消费清空payload并RETRACTED。同事件去重、投影版本单调、ack前故障全部回滚。站内状态LOCAL_INBOX，不使用外部通知账号；已发给客户端的副本不能收回。最小审计只合成principal ID/分类/结果/DB时点，不含body/token/source片段；拒绝有安全审计元数据，业务/效果计数仍零变化。

文件默认关闭，显式私有root+管理员合成setup；只接纳UTF8 text/plain≤16KiB，按UUID取资源。API currentFILE_READ/READ/owner范围及关联字段授权先检查，才读文件；attachment/nosniff/sandbox不执行动态HTML。Linux目录descriptor逐组件O_NOFOLLOW，拒绝symlink/hardlink/目录/篡改size/hash；setup也用同目录descriptor，symlink根拒绝前不写目标。没有宿主文件导入或公开上传入口，没有通用文件/DB成果提交协议；Windows backend未验证则关闭，原生ADS/重解析点/ACL NOT_RUN。

实际测试：首轮原78回归PASS（44.36秒）；新增固定子集初轮23 PASS/1 Windows SKIP（22.91秒），补动作Grant/脱敏审计、descriptor写入及角色降级后专项23 PASS/1 SKIP（23.10秒）；再加入4个独立oracle（当前动作/旧身份、字段消息撤回、拒绝不触碰文件backend、fixture写入symlink拒绝）后首个全量105 PASS/1 SKIP/2 WARN，71.23秒。命令python -m pytest -q；tests/test_authorization_files.py大部分经真实uvicorn HTTP/CLIworker/临时PostgreSQL应用角色，不用旁路故障账本；rollback/replay与文件backend探针用确定性DB/调用oracle。两个既有WARN保留。此轮pytest没有意外FAIL，授权403/非法ID422/404/原生Windows SKIP都是固定负例，没有删掉测试凑PASS。

真实浏览器失败保留：连续LOCAL harness（LinuxPython3.12.14/PG16.2，API38897、worker38898，127.0.0.1:8765）首次browser_smoke原CSS点击未发POST；空Run ID刷新307→405，assert失败，没有PASS产物。修复snapshot后语义button定位，并加入Run ID拿到后才刷新断言；重跑PASS，Run5744f914-3b79-4e57-a7a1-7e1963fd2c93、Case8554d286-cec6-4796-9d17-bd405b142e19、Operation26990e0a-c2d8-48e6-adaf-8918937184c0，本地NEEDS_INPUT/NOT_SUBMITTED/NO_EVIDENCE不变。Linux Chromium桌面与320/390像素视口模拟无水平溢出、可见按钮高44px、文字script未执行。实际命令scripts/linux_fixture_server.py与scripts/browser_smoke.py --report docs/F1/evidence/eng005-browser-smoke.json；截图/原访问日志/会话/数据库留忽略目录，不提交。

用户新偏好记录：跨平台响应式网页保留Windows11 x64本地后端主门，Mac本地后端独立验证，Android/iOS仅浏览器访问已运行获授权后端；没有手机数据库/原生App承诺。当前无Windows/Mac/iOS/Android实机测试，不把视口模拟说成实机；localhost绑定/防火墙不变。另有Sim环境官方返回Intern-S2与请求intern-s2大小写差异，只作为未来已知型号身份兼容约束，不放开其他型号/删除校验，不读取其配置或继承其安全验证。Park预算0，无真实模型调用。

工程子集覆盖/源码hash/最终结果见ENG005-Coverage及eng005-engineering-manifest，原始Library两原件与hash不变。完整36AT/6EX保持NOT_RUN；Windows/模型/真实园区/C0外部门槛保持BLOCKED。F1还有原生生命周期脚本与完整固定AT初态/oracle执行绑定独立工程，不声称只剩外部条件；本轮不继续扩范围，提交push并核实远端SHA后停供复核。实际commit由Git历史/交付链接关联，不预填自commitSHA。

提交前交集审查修正：给能力和动作Grant显式绑定park/org，防止身份改属后旧Grant跟随；追加独立oracle后106 PASS/1 SKIP（71.56秒）。本轮已运行的未发布schema4缺这两个scope列，因此新增migration005按当前合成setup范围增量补齐、保留active/业务历史，未修改已发布migration001—003。新迁移oracle只构造旧schema元数据，Run状态不手改；原新回归107 PASS/1 SKIP（71.12秒）。审查同时明确本地inbox只限当前企业经办recipient；非企业角色即使获派Run状态仍不能沿旧消息通道扩大读范围，撤回独立断言随最终完整回归验证。此处修正属于原冻结权限交集，不增加新业务或F2。

最终发布候选完整回归107 PASS/1 SKIP/2 WARN，71.87秒（原78+新增29 PASS、1原生Windows跳过），同样保留既有WARN。schema5迁移后的最终连续LOCAL服务API51815/worker51816重新加载最新代码，browser_smoke PASS，Run19431b07-e07f-455f-9547-b4196b82b692、Caseaa64cbc0-5e7f-4003-94c1-4cd54487f315、Operation484d45d7-fd61-41dc-9f3a-0b0fb0976698。最终覆盖表/源码hash与此版本一致；完整AT/EX NOT_RUN，原件未改，交付后关闭本地服务。
