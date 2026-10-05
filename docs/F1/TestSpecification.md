# F1 有界工程测试规格（新建）

来源：完整V1产品§6—7、开发计划F1及§10，本轮新建；未收到原验收包。固定AT/EX全文定义见../验收规格.json，均NOT_RUN。本文件只冻结当前可执行工程子集，不降低完整验收标准。

环境：Linux cloud / Python 3.12.14 / PostgreSQL 16.2。测试类型为合成工程（MODEL_MOCK范围，模型未调用）和FAULT_INJECTION；不包含LIVE链/Windows/园区效果。

重置：tests/conftest.py为每个测试创建独立临时PostgreSQL数据库，owner迁移、seed，应用最小角色执行；退出删除临时库。身份为fixture-a（park-a/org-a）、fixture-b（park-a/org-b）、fixture-c（park-b/org-c），全部自建合成；随机会话仅测试期有效，非真实授权资料。

| 工程检查 | 输入/操作与独立oracle | 对应AT子范围 |
| --- | --- | --- |
| 持久建单及进程重启 | API202后启动独立worker子进程两次；唯一Case、VERIFIED回执；Run成功而Case待补件 | 13、16、17（局部） |
| 同键并发与指纹 | 16次并发同输入同键→一Run；不同目标同键拒绝；8worker抢占→一claim/Case | 16、17（局部） |
| 两园区/三企业隔离 | 猜ID读/取消返回403；请求体伪造org/role返回422 | 04（局部，尚无资料/缓存/资源入口） |
| 领取后撤权 | owner撤权后finish无Case，Run FAILED；读写拒绝，seed不恢复授权 | 19（局部） |
| 过期接管与fencing | owner显式过期租约，新worker token增大；旧worker所有finish拒绝，最终唯一Case | 17（本地原子动作子集） |
| 暂停/取消 | 领取后控制，旧claim无效果；暂停可恢复，取消不声明撤销 | 18（无远端在途） |
| 原子提交与outbox | 事务中插Case后抛故障→业务/回执/outbox全部回滚；消费者ack前故障回滚；倒序、重复消费不回退投影 | 16（局部） |
| 契约拒绝 | 未知字段/任意工具/路径/真实来源/空目标/超长/错误类型→422；库内无Run/Operation | 03、05（无文件导入） |
| 注入文字及尺寸 | >16KiB实际body→413；脚本字符串只存为文本，不产生宿主文件；UI用textContent | 03、05（局部） |
| 迁移权限隔离 | 应用角色执行身份UPDATE/DDL→InsufficientPrivilege | 04、19（角色边界局部） |
| 三值真值表 | 9种AND/OR各组合对独立Kleene表；UNKNOWN不变TRUE | 21最小基础函数，完整准备度NOT_RUN |
| 领域契约 | 计划目标覆盖、有限DAG、未知依赖/环/工具拒绝；未审ServiceSpec拒绝 | 03（契约子集） |

运行：`.venv/bin/python -m pytest -q`。可信动作仅case.create/1，由代码字面注册，ServiceSpec/Plan为0.1严格投影，尚不覆盖V1完整有效期、材料、资源、批准等契约；未接入运行规划入口。上限：16KiB请求、2000字符目标、16步骤；文件导入关闭，真实模型预算禁用。

租约30秒，本地动作只在短事务执行；回执与业务一起提交，因此过期接管可核对为无部分提交再执行。本轮不支持非原子外部适配器、OUTCOME_UNKNOWN、远端撤销、模型长等待心跳；这些完整AT-17—20/30仍NOT_RUN。当前pause/cancel直接fence本地待提交动作，不能外推为远端取消语义。

API身份表只读，以共享授权advisory锁和owner撤权独占锁串行化；所有支持路径同一锁顺序。字段级授权、服务执行者、运营人员、材料/导出/缓存授权尚未实现。无真实园区目录、规则许可、用户观察或业务收益。

## ENG-002 新增工程子集

本轮新增13个FAULT_INJECTION测试与6个契约边界测试；全量40 PASS，原21仍在回归内。tests/test_fault_ledger.py只有在独立临时测试数据库显式安装fault-schema.sql后才可运行；Store.migrate、正常roles.sql、API动作注册与worker均不启用它。没有真实网络、外部账号、真实园区系统或业务履约。

| 新增检查 | 明确初态/操作与oracle | AT子范围 |
| --- | --- | --- |
| 丢响应后的核对 | PREPARED→持久DISPATCHED→模拟效果单独提交→丢响应→OUTCOME_UNKNOWN；新claim仅query，VERIFIED；dispatch_count恒为1，无Case | 20；16/17局部 |
| 失联与撤权 | 派发后效果已提交、未记回执；过期接管，撤权后内核仍能记历史效果，旧token拒写，用户读拒绝；不重发 | 17、19、20局部 |
| 暂停取消未知 | 已派发后PAUSE/CANCEL令旧token失效；未查到效果保持UNKNOWN，不推断未生效；在途模拟效果随后出现，核对保留原意图与事实，不声称撤销 | 18、20局部 |
| 派发前控制/撤权/过期 | 取消或撤权→无效果；暂停不领取、继续后只执行一次；过期worker不可dispatch | 17—19局部 |
| 跨企业/园区账本隔离 | fixture-b/c猜操作ID读/控制均拒绝；相同key按principal分离；同key改输入冲突 | 04、19局部 |
| 回执真实性 | 园区/企业/操作ID/指纹/来源/效果类型精确匹配；串企业回执EFFECT_KNOWN_INVALID，不能VERIFIED | 20局部 |
| 默认关闭 | 普通数据库没有fault表；API请求fault.record仍422 | 03局部 |
| 计划契约边界 | 重复目标/覆盖/依赖、空白目标、超长目标/覆盖和越界引用ID拒绝；有效DAG保留 | 03局部 |

模拟远端fault_effects与fault_operations故意分事务。查不到记录只是未观察到，不是权威“未执行”；DISPATCHED/UNKNOWN禁止第二次dispatch。模拟器记录dispatch_count作为独立oracle，并不据此宣称上游接口幂等。核对函数只记先前派发的效果，撤权后不新发动作、不恢复用户读权限。未知仍未知，不能自动跳到FAILED_SAFE。

FAULT账本是测试驱动的持久工程原型，尚未与正常Run/worker/outbox集成，不代表完整AT-16—20通过。正常产品仍只有原子本地case.create/1。测试重置仍为每测试临时库创建/删除，数据与身份来源全部自建合成。故障schema不随普通安装迁移生效，应用角色仅在临时测试库获得fault_operations表权限；模拟器owner独立写fault_effects。

## ENG-003 正常API/worker路径（本轮当前能力）

此前ENG-002“未接入正常worker”的限制已由本轮工程接入解决；其余未实现项保留。本轮范围仅运行器网关、Schema2非破坏迁移、可信本地动作与显式故障适配器。完整V1契约、事实冲突与字段级Grant未散开实现，不进入F2。

新增tests/test_worker_gateway.py为14个工程测试，每个临时PG库启动真实uvicorn API子进程，使用真实HTTP受理/控制/读取，再启动独立CLI worker子进程。这里不使用TestClient替代新增API验证、不手改Run状态恢复；租约过期按数据库时钟真实等待1.1秒。模拟器fixture_effects通过第二事务记录效果，独立SQL oracle检查唯一效果/dispatch_count=1/没有Case。owner只在无效回执用例改变模拟远端输入，不伪造运行器终态。

| 工程检查 | 新增实际路径与oracle | AT覆盖仍为子集 |
| --- | --- | --- |
| 持久未知结果 | HTTP202→worker派发丢响应→OUTCOME_UNKNOWN；授权HTTP核对→独立worker VERIFIED；outbox投影与最终状态一致，重复worker不重发 | 16、20 |
| 实际进程失联/旧回报 | worker在派发或效果提交后退出75；DB时钟租约过期或授权控制后接管；旧fence提交被同一网关拒绝 | 17 |
| 取消/暂停与在途效果 | 实际HTTP控制，RECONCILING期间不宣称无效果；查询后保留VERIFIED回执、CANCELLED/PAUSED及意图；不能重复resume已知单步效果 | 18 |
| 撤权 | owner CLI走同授权锁撤权；派发前FAILED_SAFE/零效果；效果提交后由worker核对历史但原用户读/控制/新请求403 | 19 |
| 未观察到结果 | after-dispatch失联后无远端结果，三次自动未知观测后停止自动领取，RECONCILING保留；手动核对只重启查询、不派发 | 20、30工程步数局部 |
| 跨企业/园区 | 实际HTTP其他两身份猜ID读/取消/核对403；回执org错则EFFECT_KNOWN_INVALID且不成功 | 04、20 |
| 共用网关与默认关闭 | 同CLI worker处理case.create（Case仍NEEDS_INPUT）与fault.record；默认LOCAL worker即使有测试权限仍不派发故障任务，默认API仍422 | 03、13、17 |
| 非破坏迁移 | 从精确migration001合成历史库升级，Run/Case/Receipt ID及事实原样保留；重复迁移稳定；未来版本拒绝，不删历史 | 27工程迁移局部 |

真实worker领取仍短租约，未实现长模型等待心跳；撤权后的历史核对只是内核记录之前派发结果，不授权新外发。fixture不是外部连接器；真实接口的幂等、授权、凭证与回执合同均未验证。只支持一个动作/Run，未开放服务组合、资源预约或政府自动申报。模型调用0，全部SYNTHETIC/FAULT_INJECTION，Windows/LIVE BLOCKED。

普通迁移002创建隔离的fixture_effects记录表，但正常roles.sql不给写权限，默认LOCAL模式同时在API及worker拒绝/跳过故障能力；测试harness必须--fault-fixtures显式授予权限并设置双方模式。ENG-002侧表fault_operations没有进入普通迁移，保留独立历史测试，不计运行器集成通过证据。

完整AT-01—36/EX仍NOT_RUN；以上工程映射不代表全条验收通过，特别是文件、字段Grant、缓存与真实消息、完整准备度、长任务、Windows和真实模型范围尚未验证。

## ENG-004 当前闭环：V1最小结构、事实/字段Grant、独立心跳

本轮新增24个检查：14事实/心跳实际路径、9契约实际HTTP校验、1无真实值token兼容。原54继续回归。Schema3保留前两版历史，增加事实断言、来源/证据、字段Grant及心跳观测。旧0.1投影作为历史测试类型保留；V1ServiceSpec/V1ServicePlan/V1ActionSpec明确使用parkweave-domain/1.0-draft，所有产品§6.2/6.3必备最小字段均存在。结构完整不代表完整PR0语义或发布/审批权已验证。

| 新增工程检查 | 实际路径及独立oracle | AT子范围 |
| --- | --- | --- |
| 长等待续租 | 真实CLI worker lease=1秒、MODEL_MOCK等待3.3秒；独立线程/连接续租≥2次、DB时点租约有效；第二CLI worker不能抢占，最终唯一Operation | 17、30工程局部 |
| 等待撤权/取消 | API受理→worker等待→owner CLI撤READ或真实HTTP取消，2秒内控制完成（无长事务）；等待提前结束，无事实结果/Case副作用 | 18、19 |
| 失联旧心跳 | 真正kill等待worker，按DB时钟过期；旧heartbeat Conflict，第二CLI worker接管，旧token不能复活 | 17 |
| 事实冲突 | HTTP保存两个不同来源断言→正常worker facts.assess；保留双方Evidence ID/源引用/值/单位/有效期/hash，结果UNKNOWN/CONFLICTING_EVIDENCE；缺字段UNKNOWN/MISSING_EVIDENCE | 06、21基础局部 |
| 来源与时间 | 只接纳USER_ASSERTED_SYNTHETIC，有效期必须有时区且递增；过期保留UNKNOWN，回执明确assessed_at及各证据applicable_at_assessment；KNOWN只代表一致性 | 06、22基础局部 |
| 字段Grant当前有效 | own park/org/principal+字段+SERVICE_PREPARATION+READ/WRITE交集；真实API入口/worker/已生成回执再次读取都重验；READ与WRITE分别撤回，seed不恢复；app不能UPDATE Grant | 04、19 |
| 跨企业/园区 | 其他两个身份猜Fact ID与Run ID拒绝403，各自列表为空；请求体伪造org拒绝422 | 04 |
| V1最小结构 | 真实契约API拒绝必备字段缺失、无来源SLA、无时区、危险动作/额外script、过深规则、陈旧服务依赖锁；完整有效样例STRUCTURE_ONLY且不创建Run/Case、不发布 | 03、06结构局部 |
| token名字兼容 | 虚构Mapping：PARKWEAVE_INTERN_API_TOKEN优先，INTERN_API_TOKEN fallback，空值None，SecretStr repr/str不含值；不读取真实.env/环境值、不调用LIVE | 02/30准备，不计真实模型通过 |

事实接口限region/employees/service_need、每字段16断言、3请求字段、16KiB请求。员工数须非负整数+people，文本须非空有界+text。事实来源是经办人的合成自述，不是已独立验证的真实证据；一致性KNOWN不变成资格TRUE，qualification_decision始终NOT_EVALUATED，Case不创建。矛盾/缺证据/过期均UNKNOWN，不按文件名或日期替用户选一方。

字段Grant是当前单一企业经办角色的最小闭环；没有实现服务执行者分派、多角色委托、全部CaseStep交集、全权限审计或真实消息撤回。查询/回执现入口无缓存且重验，已交给用户的历史输出不能靠撤回本地收回。标准服务/计划契约只校验结构与受控引用类型，不验证所声明审核人真实身份，不发布正式服务、执行规则资格或F2计划。

LeaseKeeper是独立线程和短连接，不是另一个独立服务；MODEL_MOCK长等待无网络，不证明真实托管模型、平台限流/非流式/截断/usage或Windows心跳已通过。心跳异常关闭派发权，过期fence不续租；实际数据库断网/复杂负载/所有停止边界仍需后续覆盖。

用户确认Windows11仅作为环境自报记录；精确版本、架构、原生进程、权限和干净复现仍BLOCKED。完整AT/EX保持NOT_RUN，真实模型预算/注入与真实园区来源门未通过。


## ENG-005 冻结权限/outbox/文件工程子集

执行前映射见[ENG005-Mapping.md](ENG005-Mapping.md)，逐测试覆盖见[ENG005-Coverage.json](ENG005-Coverage.json)。新增29 PASS+1 Windows SKIP，原78回归，共107 PASS/1 SKIP/2 WARN（71.87秒）。新增实际HTTP沿既有runtime（uvicorn+独立CLIworker+临时PG最小应用角色，显式FAULT_INJECTION支持单个故障分支），文件API额外进程设置独立临时根。默认LOCAL连续worker与浏览器也单独通过。未使用ENG-002侧账本替代正常网关。

| 固定子集 | 已执行oracle | AT子范围 |
| --- | --- | --- |
| 四角色交集 | 企业owner原路径；其他三角色无指派403，有同scope指派仅4项状态数据；控制/建单/事实/文件拒绝；撤指派立刻403；role降级不能沿旧owner身份读receipt | 04、19；不计F2 AT-12 |
| 错配范围/队列 | 跨企业/园区即使人为错配assignment仍403、Run/Operation/Case/fixture效果/文件数量不变；撤EXECUTE或动作Grant后worker FAILED_SAFE、Case/fixture效果0；seed/重复key不恢复 | 04、19 |
| outbox消费交付 | ack前中断回滚delivery/投影；同事件重放不重复delivery、倒序不回退投影；撤READ/字段后SUPPRESSED；已有READY即时读取403，worker清空payload为RETRACTED | 16、19 |
| 文件范围/渲染 | owner合成纯文本fixture按UUID实际HTTP attachment；其他企业/园区/已获派执行者403；FILE_READ撤回后旧ID403；后端调用探针证明授权拒绝前不读文件；文本脚本不执行 | 03、04、05、19 |
| 路径/完整性 | 盘符/UNC/ADS/反斜线/穿越不被当ID；Linux descriptor拒根symlink、文件symlink/hardlink/directory、大小/hash改动；setup root symlink不写宿主目标 | 05 Linux工程 |
| 原生Windows | 本机重解析点、ADS、ACL、原生Python/PG与启动停止未执行；文件backend未验证平台fail closed | 05 Windows NOT_RUN、01/34 BLOCKED |

权限细则为当前单Run范围：企业字段仍三字段/一用途；非企业角色只有明确同scope Run状态指派，无材料/回执/企业事实/控制/执行权，即使数据库错误授予额外能力也受可信角色上限约束。正式服务发布/CaseStep交集属后续业务范围，未开放。当前最小审计仅API拒绝、worker撤权失败、本地消息交付/抑制/撤回；元数据包含合成principal ID/分类/时点，不含会话token、请求体、资料片段；不声称完整生产审计。

LOCAL_INBOX交付与消费在同一授权锁+数据库事务。发给浏览器的副本无法收回；投影只供内核状态，不是授权缓存，当前API不从投影跳过权限。SUPPRESSED/RETRACTED事件即使重放也不重新READY。当前没有外部消息适配器，外部在途发送/撤回语义NOT_RUN。文件仅管理员合成setup，读取端≤16KiB；不声称通用导入、PDF解析、成果原子文件落位、备份恢复已经验收。

浏览器首尝试FAIL：原CSS定位点击未提交表单，空Run ID刷新307→405；没有POST建单。修复为snapshot后语义button定位，并断言获得真实Run ID再刷新。重测桌面及320/390视口PASS，无横向溢出、可见按钮≥44px、textContent危险字符串不执行。它们全部Linux Chromium模拟，Android/iOS/Mac/Windows实机NOT_RUN。

完整36AT/6EX状态维持NOT_RUN；当前工程子集PASS不改整条验收状态。仍有原生生命周期脚本及固定AT完整执行绑定独立工程缺口；LIVE预算/安全注入/限流、Windows实机、真实园区/来源许可及C0赛方资料另属外部门槛。

提交前完成范围绑定后最终107 PASS/1 SKIP/2 WARN（71.87秒）。增量schema5修复本轮未发布schema4的Grant scope，保持active及所有业务历史，重复迁移稳定；身份改属不带走旧Grant，非企业角色即使获派Run状态也不能读旧inbox。对应AT-27迁移工程子集，不表示整条AT-27通过。


## ENG-006 收尾工程绑定与审查修复

执行前范围见ENG006-Mapping；ATBindings逐项覆盖全部42固定定义，run_acceptance读取pytest JUnit按testcase独立计数，whole_status永远NOT_RUN；绑定缺失/unsafe selector/预填PASS拒绝，未执行选择器为INCOMPLETE，失败和Windows跳过不能PASS。全部工程回归146 PASS/1 Windows SKIP/2 WARN（75.04秒）。原107继续；新39含生命周期mock/格式边界/来源完整性与目录安全，重叠AT计数不能相加。Linux实际API/worker/PG路径仍在回归里，没有真实模型调用。

生命周期：Linux上实际Python CLI六操作全部拒绝；PowerShell7.6.6实际AST解析7脚本+2内嵌ACL片段零错误，六PS脚本都以NOT_RUN拒Linux。共享安全策略用mock进程检验PID复用/外国命令/cwd/AccessDenied拒绝，配置EXCL防覆盖、DSN/app身份边界、环境白名单未知项不读取/转发、既有WindowsACL只Get-Acl不Set-Acl。Windows执行/权限/PG服务/安装依赖/签名NOT_RUN，不用Linux解析等同Win5.1兼容通过。

模型：官方格式来源见ModelBoundary；离线单位样例涵盖两次工具反馈、已知大小写、其他型号/重复JSON/未知工具/script拒绝、length/无完成标记、429/鉴权/5xx/重定向/超时/断链/坏JSON、usage错误/缺失/超预留、并发本地尝试预算。数据全部自建SYNTHETICHTTP，strict MockTransport、live入口拒绝，不调用密钥resolver或真实服务。不证明真实限流/超时终止/全成本。

审查修复：临时files0777在旧代码真实accepted，修复后root/files/currentUID+group/other0校验拒绝，mode保持0777；新增root777/files777/files755实际HTTP403、登记拒绝且0新增文件/业务、属主错配mock、新files0700。新files/文件descriptor最小权限；既有目录/ACL不自动改。WindowsACL读检查必须原生验证，backend仍禁用。详见eng006-directory-review.json。

真实失败保留：PowerShell首次初始化因/home/agent缓存只读失败，配置XDG_CACHE_HOME后仍因XDG_DATA_HOME默认只读失败；指定工作区XDG缓存/配置/数据后AST成功，未改HOME/全局策略。浏览器npx开放版本解析在最小env下open/close各30秒超时，未记PASS；改用缓存中验证版本0.38.2的CLI直接执行，免registry解析，单独重测，结果另见browser证据。pytest本轮无意外FAIL，预期拒绝/skip均有独立oracle。

剩余独立实现与外部门槛逐条见Checklist。本轮交付后停止新增；完整AT/EX没有PASS，不进入F2。

最终浏览器缓存CLI修复后桌面及320/390模拟PASS、无页面错误；该脚本是全回归后唯一源变动，实际浏览器单独验证，acceptance-summary保留原pytest源快照并记录post_regression_verification，未伪造覆盖全回归hash。


## ENG007新增T05工程子集（新建来源，非原验收包）

固定AT02/30绑定新增test_model_chain.py：实际CLIworker两次离线请求+真实PG Case回执；wrongmodel/缺args/length/secret/timeout/反馈错误零不可信效果，已知效果保留。临时共享协调库双合成产品/角色并发只获一个账号预算，产品上限/账号绑定/owner-only/授权证据/过期拒发、确认未发释放、usage冲突重放/未知收费保留/超额真实计入及阻断后续。

发送标记竞争仅一胜者，崩溃恢复不重发；已知Case恢复只feedback，默认worker不能绕过已有模型阶段；撤权/旧fence返回只历史费用、零新增动作；等待1.4秒独立续租与竞争claim拒绝。strict usage校验后才可结算，错误usage保持UNKNOWN预留。所有provider响应自建MockTransport；测试进程拦截真实httpx.HTTPTransport，实际CLI代码固定MockTransport。真实API/原生Windows/完整业务AT EX仍NOT_RUN/BLOCKED。
