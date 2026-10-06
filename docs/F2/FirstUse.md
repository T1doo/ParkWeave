# 本地合成资料准备：首次使用

## ENG029 当前同步与Server CI结果

ENG028代码已普通快进同步，精确远端ff00b6d8ad0880b24afaca49e33b9f8b982ceb87。标准Server [run37417713362](https://github.com/T1doo/ParkWeave/actions/runs/37417713362)已completed/failure：PreparePASS、native_suite623.032秒exit1/外层timeoutFalse、受绑定PG StopPASS。获准check summary/text为空，19条注释未给具体case/counts；仍UNKNOWN，不把时长推断成内部超时或根因。下一定位仅需此新run页面安全JSON，旧截图请求已过时。见[ENG029真实同步记录](ENG029-SyncCI.md)。下方ENG028“本地未push/待核对”等均为当时快照，现已被本节取代；F1/F2未签收、Win11/36AT6EX NOT_RUN、R4关闭、真实模型/预算0。


## ENG027 当前同步授权

普通同步已完成：精确代码push头1baa2cf93f795dbf3036245b8f2ea2ec2ce15e56（含已验证54fad8c）。标准Server CI37414981257终态FAIL：Prepare成功、native_suite79.235秒exit1、owned cluster停止成功；具体case仍UNKNOWN。实际证据见[同步记录](ENG027-SyncCI.md)。旧ENG026未推送/暂停说明属于当时快照，不能当当前状态。未经精确远端验证不声称GitHub已更新，CI结果取得后据实记录；不force/merge main/deploy/LIVE，不重试被拒日志或换身份。F1F2/Win11/R4门槛保持。

## ENG026 当前复现与可见性

当前积累源码只在本地；不能因本地commit或缓存origin引用称GitHub已更新。已实现/未实现原V1项见[V1Status](V1Status.md)，实际CLI、fixture前置及Windows检查限制见[ENG026-SyncReadiness](ENG026-SyncReadiness.md)。自动Case/回执browser还需要调用者明确提供同一本机SYNTHETIC cluster的测试owner DSN准备合法分配，不能当作产品已有自动分派。历史临时runner/会话不等于干净环境复现入口。当前暂停push/newCI/备份/导出/上传/LIVE。

## ENG025 显式关联此Case的资源
企业先在资源工作区确认本人两资源组合，再打开本人已本地确认的资料事项，点“查看此Case资源并选择关联”。从有当前操作权的组合中选择，填写关联说明，点“确认此Case资源关联”。页面显示Case、资料版本、关联版本、创建快照及当前资源状态；刷新或重启仍可读取历史。
资料重开后旧关联显示需重验，原组合继续占用；重新人工核对/确认资料后，可明确关联同组合或新组合。换组合也不会释放旧预约；到资源工作区显式整组取消。已取消、使用时段结束、规则改变或归另一Case的组合不可关联。当前无HOLD的候选禁用，无EXECUTE只读历史；当前403清除旧私有视图。失败保留原输入用于相同key重试，选择/说明改变会成为新输入；忽略迟到UI不代表服务端POST回滚。
仅当前合成资料Case；没有通用ServicePlan、接单/通知/真实预约/线下履约。原Case仍NEEDS_INPUT，资料REOPEN不是Case生命周期重开。首次harness可使用原 `--preparation-fixtures --resource-fixtures --combination-fixtures --receipt-fixtures` 本机合成入口；执行者分派仍需测试owner准备合法SYNTHETIC assignment，产品没有分派写入口。预算0，不上传/导出，Windows结果待独立验证。细节见[ENG025-CaseResources.md](ENG025-CaseResources.md)。


## ENG023 获派执行者回执入口

显式Linux测试入口可追加 `--receipt-fixtures`，只准备三名明确假执行者READ会话，不自动分配Run、不修复撤权。需测试owner仅为本次新的SYNTHETIC Run准备既有assignment；应用没有assignment写API，不提供增加角色权限入口。

企业打开已本地确认的资料准备事项，选择“查看此运行已有获派执行者”，只从当前合法分配中选择“建立合成回执步骤”；已有步骤通过协同“刷新我的回执事项”进入。执行者切换本机假会话，填写合成回执和来源版本；企业填写说明后核对当前hash、要求纠正或重开，原回执/事件保留。父资料改变时显示“原资料已改变”，新操作被阻止；需后续显式规划流程，本片不自动重新绑定。

合成回执文本不证明真实办理，企业本地核对也不会关闭Case目标、判定资格或通知外部。执行者仅见必要事项/回执，不见企业材料正文。来源当前只SYNTHETIC，不提供真实证明上传或签名验证。ENG023回执截图.runtime/eng023-ui仍可复验；报告中的.runtime/eng023-preparation-ui目录恢复后缺失，不可复验，见ScreenshotEvidence。不用新图回填，不上传或导出。旧准备browser新增 `--screenshots` 并默认独立目录，后续回归不覆盖固定名图。

这是F2并行工程切片，F1与F2正式门未通过；不是PR0-alpha或真实园区试点。只整理纯文本候选资料，无资格裁决、外部受理、预约或线下履约。没有真实模型请求。

当前实测是Linux Python3.12.14、PostgreSQL16.2、Chromium，不能照作Windows安装结论。已准备本仓库依赖的Linux合成测试环境可运行：

```text
.venv/bin/python scripts/linux_fixture_server.py --preparation-fixtures
```

此显式测试入口只在本机8765开API/独立worker，准备合成目录/专员；首次产生本机合成会话，原有撤权不会被seed重激活。没有外部写入。结束时向该前台进程发送正常停止信号，由它停止自身API/worker；不杀其它程序。

1. 打开本机网页，将本地合成企业会话填入“合成身份会话”（fixture-a会话在私有.runtime/synthetic-sessions.json）。在“服务”点“查看可选服务与专员”，填写新目标，选同企业专员，再点“开始资料准备”。页面创建新的Case/Run，worker完成本地建单后进入资料准备。
2. 选择“诉求摘要”或“材料目录”，填写候选文本、来源类型和来源/文档版本，点“追加材料版本”。两个槽均需当前资料；来源真实性尚未核实。
3. 使用对应专员的本地合成会话（prep-specialist-fixture-a，在私有.runtime/preparation-sessions.json），到“协同”点“我的资料准备事项”，选择获派事项。专员可填理由“要求补正”；企业切回自己身份追加资料后，专员再“核对本地资料包”。切换身份清空旧事项资料显示，需要重新读取。
4. 企业切回并读取当前事项，填写理由后“确认本地资料准备”。这里只确认平台内资料准备：原Case仍NEEDS_INPUT，资格NOT_EVALUATED、外部NOT_SUBMITTED、线下NO_EVIDENCE。已知Run成功不能作为服务成效。
5. 有变化时企业填写理由“申请重开资料准备”，或追加新的材料版本；旧核对失效，历史仍可查。旧页面确认会被拒绝；刷新查看最新版本再操作。每事项最多64条事件，达到上限明确拒绝，不能无边界追加。

在“协同”点击“刷新我的资料准备待办”，企业看到缺少材料、专员补正说明或待确认事项；获派专员仅在两类材料都已提交后看到待人工核对的事项。点“打开资料准备事项”进入当前详情，继续上述补交/核对/确认流程。办理后手动刷新待办；已本地确认的事项不列为待办，企业重开后专员再次核对。待办没有材料正文，也不代表资格判断或消息已送达。切换事项、身份或刷新待办会清空未提交草稿，同事项详情刷新保留草稿。列表检查最近100个尚未本地确认的有权事项，存在更多记录会明确提示范围受限；达到当前记录上限会显示阻塞。

这里无需修改源码或数据库来完成办理。专员只读获派事项资料；不开放全企业档案或执行其它Run。当前没有文件上传/原生R4、真实身份接入、任意资格服务、通用ServicePlan或资源组合。目录与资料要求明确来自ENG014合成审核夹具，不冒充真实服务规则。

## 合成资源短期占位（ENG018）

同一已准备的本地环境使用 `.venv/bin/python scripts/linux_fixture_server.py --preparation-fixtures --resource-fixtures` 显式启用fixture。新增schema11及新表最小权限由owner迁移/roles SQL准备；不重激活旧撤权。注册的是容量2、前后各5分钟缓冲的合成协作空间，开放区间/来源/版本可读；不是真实房间预订。

在“资源”读取有权合成资源，填写UTC起止、份数、TTL5—300秒和说明，点“预检当前区间”；有容量再显式“创建短期占位”。最多4小时且含缓冲需在开放区间内，过去/超额/规则变化明确拒绝。预检只是本次读取，创建仍重验。刷新“我的占位记录”，有效占位可释放；过期从DB时点即时判定，不依赖清理worker。切身份/导航不能撤回已发请求，要刷新自己的记录核对。撤销授权阻止后续读/写或重放（依具体READ/HOLD/EXECUTE），已创建占位不自动撤回，最多等原TTL到期；应用不能延长TTL。

fixture-a与fixture-b可共享同一资源容量，彼此只能读自己的占位，预检只显示匿名峰值容量；fixture-c无该资源授权。这是本地短期占位，不是正式或组合确认、付款、外部受理或线下履约；无模型调用。仅最近100条本人可读记录，更多会提示。浏览器测试确认了本地真实API的表单路径和TTL5实际过期；原生日期选择器手势未测，测试harness用控件赋值/输入事件（缓存agent-browser fill会清空此原生控件）。Windows/Win11、真实园区资源与完整F2仍未签收。


## ENG019 单资源本地合成确认

本人HELD卡片提供“确认此单资源合成占位”，只在有效期限内、资源版本与当前规则一致时提交。确认卡显示“本地合成确认”，原占位截止作为历史显示；不会按原TTL自动释放已确认区间。可“取消此本地合成确认”释放容量，旧确认回执保留。发生容量/规则/期限冲突时刷新状态，规则版本已变则释放原占位并重新预检；原始区间/数量不可改。未完成请求可用相同输入重试，切身份/草稿/页面使迟到响应失效，但不撤回已发请求。

真实预约仍未确认，外部未受理、线下履约无证据；组合确认未实现。确认不自动关闭Case或开展资格判断。撤权后不能读/写/回放无权记录；撤权不会静默取消既有本地确认，故确认区间容量仍保留，恢复当前授权后才可本人取消。无需后台清理，区间及缓冲之外不占新窗口容量。日期picker手势仍NOT_RUN，浏览器只测原生值/input事件。


## ENG020 界面审阅

三个工作区顶栏显示当前位置；服务填写本次目标，协同查看本人待办，资源按预检→占位→本地确认操作。事实候选及必要澄清在“补充企业事实与必要澄清”中展开；本地JSON工程记录默认收起，错误和当前状态反馈直接可见。资源卡片的区间和历史确认截止均显示UTC可读时间，不改变数据库原始时间或期限。确认重试若返回已取消记录，显示当前已释放，并说明原操作回执是历史记录。

实际桌面/320/390截图在项目.runtime/eng020-ui-final/。服务入口service-desktop.png/service-mobile.png，资源普通合成确认resource-confirmed-readable.png/resource-confirmed-readable-mobile.png，其余含待占位/已取消/过期/空态/容量警告/权限错误及协同和资料状态。均为本地合成，不含真实企业数据或明文会话；未上传/导出。仍待用户审阅视觉效果，原生手机/Win11和日期picker手势未测。


## ENG021 两资源本地合成组合

显式运行 `.venv/bin/python scripts/linux_fixture_server.py --preparation-fixtures --resource-fixtures --combination-fixtures` 才登记第二个合成资源，owner迁移schema12及roles SQL中新表最小权限；原resource-fixtures仍只初始化原资源，不修复撤权。

分别选择合成协作空间/合成研讨设备，按各自区间预检并创建占位；刷新本人记录，勾选两条不同资源的本人有效HELD，再“确认这两个合成资源”。各自区间保留，没有强加同窗要求。两条都通过当前授权/版本/容量/期限才整组确认，失败无部分确认，原占位仍可能有效或已自然过期，可刷新/显式释放后重新预检。响应丢失可能已生效，必须同选择重试或刷新组合记录，不把未取得结果当没有作用。

本人组合记录展示两条当前状态。成功组只用“整组取消并释放两条容量”，单资源路径拒绝拆开释放；任一当前资源授权被撤销时，整组操作拒绝，不偷偷释放另一条。原确认回执保留，取消后旧key重试显示CANCELLED而不恢复占用。真实预约未确认、外部未受理、无线下履约，服务请求取消不自动等于资源释放。

本片最终截图保留项目.runtime/eng021-ui-verified（先前ENG020、ENG021初轮及ui-final目录仍保留），不上传/导出；原生日期picker/Win11/真实手机未验证。组合仅两个同库LOCAL_AUTHORITY的SYNTHETIC资源，不支持任意数量、部分替代、外部原子性、硬件控制或ServicePlan自动编排。


## ENG024 当前有边界跨模块演示

仅在已批准缓存齐备的Linux本地合成测试环境，运行fixture入口加 `--preparation-fixtures --resource-fixtures --combination-fixtures --receipt-fixtures`。企业新建资料整理诉求，补材料；获派专员要求纠错，企业追加新版本，专员核对后企业本地确认。转资源分别预检/占位，选两个不同资源一起确认；回协同由企业从既有合法分配中建回执步骤，执行者提交，企业要求纠正/核对/重开。测试脚本中的assignment仅明确合成owner为本次新Run准备，应用并无通用分派或接单界面；不能将其描述为客户无需人工准备的完整产品流程。

脚本scripts/cross_module_browser_smoke.py用现有接口复现该链，必须选择新的report/截图目录，PARKWEAVE_RECEIPT_FIXTURE_OWNER_DSN只由本地fixture owner显式提供，不读取外部凭据或真实身份。组合与Case没有业务绑定；脚本通过同一诉求说明和ID手动关联，回执确认不自动取消资源或关闭Case，结束用资源界面显式整组取消两条容量。桌面/320/390新图在.runtime/eng024-ui-final，对应hash见新证据，旧命名图不改。

通用运行/事实界面新增token/Run/请求代际守卫，切身份清旧JSON和事实/诉求草稿；编辑Run或导航使在途旧评审无效，旧成功或错误不恢复到新身份。已经发送的POST可能已提交，不因离开页面回滚；重新授权读取服务端状态。错误仍直接可见，不用视觉润色掩盖失败。外部通知/真实证明核验/履约和自动ServicePlan目标编排仍未实现。
