# ENG-011 F1收敛核对：有限断言与任务

依据原Library V1《分阶段开发计划》§3/§10固定表（原件454/410行与hash不改），本表不改阶段、不降验收标准。F1首次执行的是AT01—06、16—20、30共12项；T06只承担AT31/32的规格/来源准备，它们完整对照/效果评测首次执行仍F3。Windows候选保持未启用，本轮不操作/扩展它。所有whole AT/EX仍NOT_RUN。

状态分类：**1**=该断言代码与合成工程证据已有，完整签收需原生/真实模型/来源验证；**2**=明确代码或独立oracle仍缺，不能只写外部BLOCKED；**3**=原文明确F2/F3等后续阶段。已实现的纯工程断言保留PASS证据，不因whole NOT_RUN否认；不把局部PASS提升为完整验收。有限欠项编号固定R1—R4，不使用“还有完整性工作”泛称。

## F1任务到具体验收断言

| F1任务/固定AT | F1具体应核对的断言（原意保留） | 当前代码/独立工程证据 | 分类与具体残余 |
| --- | --- | --- | --- |
| T01/AT01 | native API/worker/PG真实进程、PID/版本/数据路径、停止再启数据可读、错误不覆盖旧配置；WSL/远程不可替代 | Linux实际进程/PG/重启与候选六脚本、可信PID/EXCL配置/私有权限检查；生命周期与worker测试 | 1：E1 Windows原生安装/精确依赖/运行/停止再启实测；候选本身不是Windows通过 |
| T01+T03/AT05 | 逻辑资源ID、类型/大小/授权根、当前scope、Windows traversal/UNC/reparse/ADS、危险输入不执行、凭证/宿主资料不入输出日志 | Linux descriptor根/owner/mode/nlink/hash/UTF8；API当前Grant/Case范围；下载attachment+CSP、网页textContent；拒绝任意路径/执行/未知格式，来源仅owner合成夹具；69候选policy/ABI测试 | 1：E1 native候选语义/替换/ACL验证；2：R4验证后受控reader dispatch/合成fixture metadata注册集成。通用材料导入/转换未承诺为F1产品功能，禁止接口不是“已实现通用导入”；本轮不再扩backend |
| T02/AT03 | 候选规格先结构/规模/注册能力/权限拒绝，无业务副作用；残缺内容不部分执行，不动态加载工具 | strict Pydantic、版本/规模/DAG、可信注册case.create/facts.assess与未知工具/代码/路径拒绝；contracts仅校验不发布；domain/v1/adapter/gateway测试 | 1：基础断言有工程证据，随native/LIVE签收重跑；正式服务发布/组合编排是3，不移入F1，也不能在启用后免测该安全标准 |
| T02+T03/AT06 | 候选事实来源保留双方、不猜权威、不把缺值判不符合，必要问题集中展示 | 已有三字段SYNTHETIC FactInput/来源/有效期/READ-WRITE Grant、冲突/缺证据UNKNOWN、qualification NOT_EVALUATED；facts API/CLIworker独立oracle | R3本轮IMPLEMENTED：三字段结构化来源projection/明确mock候选、版本保留、全UNKNOWN与统一必要问题、正常API/worker/浏览器、append-only澄清/取消/重试oracle；1：真实来源/模型抽取核验归E2/E3。任意文档抽取、真实资格引擎/办理不加入该任务 |
| T03/AT04 | scope来自后端身份；猜另一企业/园区事实、Case、结果、文件/上下文不可泄露；资源匿名占用不能泄露身份/用途，汇总需另授权 | 三企业/两园区/四角色、owner或授权单Run状态、字段/Case/行动Grant交集；跨scope/身份变更/赋派/文件/消息及新plan revisions拒绝 | 1：当前已开表面的断言有工程证据。尚未开放的资源/汇总接口当前无可读输出，不冒充匿名资源产品已经实现；其业务首次是3（AT09/10/12/28），开放时必须继续执行原AT04安全断言，不改AT04阶段 |
| T03+T04/AT19 | 撤权后读/写/发送重验当前授权；缓存/旧批准不恢复授权；在途无法收回边界可见 | queued执行、lease/field/action/role、outbox抑制/撤回、逻辑file/API缓存、model发送前后与revision读取；历史已发usage仍记账 | 1：独立回归已实现；真实provider在途/network及native文件实际行为归E1/E2，不把fixture继承为真连接 |
| T04/AT16 | 业务与outbox同事务；中断消费恢复、同事件不重复；倒序旧事件不盖新版 | event UUID/Run revision、LOCAL_INBOX ack TX、单调projection/抑制撤回；outbox ack故障/重复/倒序oracle | 1：本地工具基础完成；真正外部消息渠道是3，首版无发送授权，不新增渠道以充当F1完成 |
| T04/AT17 | 租约失联恢复不重复已知效果；旧fence不能写新状态；未知先核对 | DB租约/fence/独立心跳、失联claim、正常worker FI query不重发；model已发无结果不重发，R1双版本及terminal/outbox同事务恢复 | 1：本地/合成工程已有，native并发进程归E1；真实provider query合同未知归E2。FI核对不是实际外部连接 |
| T04/AT18 | pause/cancel不派新动作；不等于外部撤销；在途/丢响应与已知影响可见 | control_intent+fence、本地事务前控制、FI DISPATCHED/UNKNOWN核对、已知Case/VERIFIED不覆盖成FAILED_SAFE；model反馈失败保留本地作用 | 1：本地/FI基础有独立oracle；真实外部撤销不承诺为F1，其接入需后续授权合同 |
| T04/AT20 | 结果UNKNOWN按业务ID核对、不盲重发；故障源明确FI、不称真实集成 | 正常CLI统一gateway、FAULT_INJECTION默认关闭、3次自动观察/人工核对仅查询、invalid receipt拒绝；fixture_effects idempotency | 1：明确工程要求有实际PG/CLI证据，不要求一个真实园区接口才能完成该工程断言 |
| T05/AT02 | 真实理解/选工具/确定反馈/修订计划；call ID/tool回填/revision可核查，无开发模型兜底/stub PASS | HTTP字段/身份/工具strict parse；正常worker合成PLAN→trusted Case→真实DB receipt→结构化revision；ENG009 revision1/2/调用ID/前版本与receipt hash/独立oracle | R1本轮实现；1：E2真实书生/账号预算/精确模型证据；R2本轮有界工程实现：账号发送门/显式LIVE前提与变量名检查；真实安全注入/CLI启用仍关闭归E2。不把stop文本当修订或mock当AT02通过 |
| T05/AT30 | 共享或明确划分核实总额度；非流式完整校验、轮次/工具步数/失败上限、未知usage非零、注入不冒充真实上游 | account协调库总额+product上限/角色绑定/锁、持久RESERVED/DISPATCHED/SETTLED/UNKNOWN、已发不重发、2请求/1动作、未知保守8192、超额真实计入、无自动修复重试；错误/截断/SECRET拒绝 | R2本轮代码缺口修复（见AccountRate）；1：E2真实速率/配额核实、共享部署/实际usage/429/截断计费。元数据tokens不叫金额全成本；未承诺价目折算/供应商账单校准不无限搬入F1 |
| T06/AT31/32规格准备 | 固定规格/代码版本/独立oracle/来源与重置可追溯；全部失败修复保留；开始获取目录/规则授权、痛点假设明确 | 完整42定义NOT_RUN、ATBindings/JUnit、UUID临时PG重置、代码hash/evidence/log、完整Library档案、DataLedger/痛点假设；本轮收敛表与R1固定oracle/R2已知失败证据 | 1：已有F1准备产物；E3真实来源/许可获取未成功，授权缺失不编资料；3：B0/B1/B2真实比较/使用观察/效益是原F3，不以F1准备称通过AT31/32 |

上述AT05的F1“恶意导入”边界是针对当前支持合成UTF8文本/JSON接口、逻辑UUID下载与网页呈现，以及拒绝未授权/未知路径/类型/执行；不会用禁止任意文件导入来声称真实材料导入产品已完成。后续若增真实格式/导入器，必须按原AT05全标准复验，不能跳过文件/凭证边界。F1文件通路在native仍有明确R4集成门，未降标准。

## 有限独立代码任务（2），不再泛称“完整”

| ID | 明确交付及退出断言 | 本轮状态 |
| --- | --- | --- |
| R1 | 一goal/可信case.create的动作前revision1及接真实receipt后的模型结构化revision2；goal保留、Case仍NEEDS_INPUT；op/Case/tool/provider IDs、previous/receipt hash绑定；immutable history/当前权限GET；坏修订拒绝且已知Case保留；after artifact+Run terminal+outbox同TX，恢复无新模型调用 | ENG009 IMPLEMENTED/合成独立oracle；真实AT02依旧BLOCKED |
| R2 | 原产品§10默认每用户30RPM，核实实际provider额度后按同account共享数据库时钟的pre-send gate；已发送失败/429/unknown同计速率，未发送可释放预算但不能退已发速率；两产品aggregate不超核实额度。仅补既有协调器最小发送门与显式LIVE安全注入/config、发送/返回时点与耗时/错误分类元数据（原产品§10要求；正文/key不入账），审批/未知配置仍拒绝。测试31st拒绝、两个产品竞争、60秒边界、重启、usage独立保留；不做通用协调平台 | ENG010 IMPLEMENTED/合成独立oracle：30RPM发送门、代次预约、未发退款/有界延后、时点/事件；LIVE默认关闭及只读变量名/授权前提门。正常CLI仍SYNTHETIC，真实启用/安全注入/真实共享部署待E2；无真实预算/API，不新增高级财务功能 |
| R3 | 针对现有region/employees/service_need，严格候选事实提取projection→已有source保留/Grant/assessment→按UNKNOWN/MISSING/CONFLICT/EXPIRED集中列出必要问题；无猜测/无自动资格通过；明确fixture+独立缺值/冲突/撤权oracle及呈现 | ENG011 IMPLEMENTED/合成独立oracle：当前三字段来源与mock模型候选、集中问题、权限/源版本/回填与取消/幂等/不可变历史；全UNKNOWN，不自动核实。真实抽取/授权来源签收仍E2/E3，不扩F3引擎 |
| R4 | 保持Windows候选未启用；E1原生确认后再复核最小reader dispatcher及受控合成fixture metadata注册，使当前FILE_READ/scope/Case检查同一入口、原生逻辑ID下载可测。仅补已有闭环集成，不开放真实上传、创建任意文件/unsafe fallback | 条件性未做，当前暂停、不继续扩后端；不能写成仅差原生测试，也不当前强行实现 |

历史ENG009固定窗口缺口复现（保留证据，不改写）：`test_fixed_long_window_admits_31_in_minute_known_normative_gap`仅在新临时SYNTHETIC协调库配置64/hour总预算，同角色提交31个不同work并标DISPATCHED，全部在<60秒获许可，违反源默认30RPM的发送门要求。它没有发送HTTP；pytest对“成功复现已知失败”计工程PASS，不代表AT30速率PASS。单独证据status=KNOWN_IMPLEMENTATION_GAP_NOT_AT_PASS；金额、provider实际额度/错误不是猜测。此前只将滚动窗口列后续增强过宽，现收敛为R2这个明确来源约束；原阶段/规范没有改。

## 有限外部门（1）

- E1 Windows11 x64原生依赖/权限/精确版本、candidate native ACL/reparse/share/race与API/worker/PG生命周期。candidate不启用、不继续扩展，Linux证据不能替代。
- E2 Park安全注入/账号及核实shared总额/速率/授权预算，两个真实产品同协调点配置、实际Intern模型工具修订/usage/计费/失败证据。真实请求0/授权预算0；不从聊天取key，不读取model真实env。R2最小发送门与显式安全前提/变量名检查已实现；真实注入与正常CLI启用仍关闭，部署核实不是布尔单测可代替。
- E3 真实园区目录/规则/资料授权与模型发送范围；无许可只用SYNTHETIC，不编试点。C0模板/关联作品规则/准确截止独立待核实，用户日期2026-11-05保留。

## 后续阶段（3）原编号保持

F2首次AT07—15、28/29、35：复合ServicePlan/模板/组合资源容量与占位/协同CaseStep/业务验收和履约。不把匿名资源产品、完整办理或外部消息渠道搬入F1；新增接口仍重复执行F1安全标准。

F3首次AT21—27、31—34：完整三值资格/规则版本/材料/事件/变更/锁/发布/B0-B2效果/第二园区配置/干净原生复现。若F2资格需最小三值可以按用户授权前移，但无证据不能默认通过。T06只准备31/32规格，未移首次执行阶段。36=C0、6EX=F4—F6；通用金额折算/账单校准/跨协调库仲裁不加入F1最小退出标准。

本轮唯一代码交付R3，最终Linux证据及失败记录见ENG011与[CandidateReview](CandidateReview.md)；交付push后结束，R4未操作/未启用。R2历史交付见ENG010与AccountRate。ENG009历史失败JSON与源规格不变，31st回归现在拒绝；R1历史交付保留。不再追加没有新来源/具体失败断言的“完整oracle”任务；新的业务属于原阶段，新的基础缺口必须明确原断言、复现与有限范围，不能靠标签新增范围。
