# 产品闭环执行进度

## 等待隔离测试确认前修复的初始化字节问题

- 基础schema32与原Store默认目标一致；migration033是另一个显式fixture路径，不自动升级主库。
- 实测原生026–032迁移及样例storage的raw SHA全部不匹配，原因是Windows工作树CRLF；转换LF后与Git原始blob及原锁定SHA逐一一致，不是SQL语句差异。
- .gitattributes为src/parkweave/*.sql固定LF。仅对验证“CRLF转LF后等于HEAD原字节”的39个SQL文件恢复换行；原字节备份 .cache/windows-desktop/sql-before-lf.zip，没有覆盖语义修改、没有改锁定哈希或执行DDL。
- 新增两项raw SQL pin回归与原factory拒绝检查，共3 passed。前后证据 windows-schema-source-check.json / windows-schema-source-check-after-lf.json 保留。
- 旧候选仍含旧SQL字节，不能用于最终新建验收；后续需按新冻结源重新构建。当前核心真实初始化验证仍等待用户确认临时分支与一次限时Windows隔离执行，未推送或运行Actions。

## 隔离测试授权等待期间的本地准备

- 未收到云端执行确认；没有提交、推送、触发Actions或产生该工作流运行。
- 原工作流仅匹配旧dev分支且构建器只接受Linux。已准备Windows构建支持、固定Windows Zig资产与安全ZIP解包；候选只下载当前平台工具，保留精确版本/大小/哈希。
- native-business-trial-once.yml 的构建job调整为Windows，新增精确临时分支 codex/windows-closure-20261105；两个job的false禁用条件保留，native_business_window.json仍为null。没有通过分支名赋予运行授权。
- tests/test_windows_ci_candidate_build.py及原null授权拒绝测试：5 passed；无授权时仍在Git、网络、临时目录动作前拒绝。
- 实际执行仍需用户确认、冻结源码与精确执行记录；当前修改只是本地准备，不算Windows完整办理证据。

## 启动消息已贯通，真实新建被历史初始化门拒绝

- w15隐藏消息自测实际经过EXE内前端→WebMessage→私有Python管道→原request解析器；固定无效请求被拒绝，backend_refused_original_request=true、child_closed=true，进程退出0。证据 windows-w15-message-probe.json。
- 再向已核包的真实 desktop_bridge 发送有效新建请求（随机合成四角色密码、全新工作区测试目录），实际返回 PW1 REFUSED OWNER_MUTATION_PAUSED，退出2，无实例目录创建。证据 windows-new-request-gate.json。这是当前新建的真实阻断，不是前端按钮、端口或用户目录输入错误。
- 现有 source setup_readiness 仍无条件BLOCKED，后续需补真正可执行的Windows初始化与原始安全检查闭环，不能把返回值硬改READY，也不能把此拒绝当完整业务通过。
- 消息自测初次发现探针遗漏SystemDrive，Windows组件在候选目录下生成字面%SystemDrive%缓存路径；旧候选保留诊断，重新从已核ZIP解出clean副本，探针补齐SYSTEMDRIVE/PROGRAMDATA/ALLUSERSPROFILE后运行。最终再次verify_directory通过，3058文件不变。未修改用户全局环境或系统缓存设置。

## w15：EXE内真实像素确认

- 用户要求先证明EXE能显示已认可前端。w14完全隐藏窗口的CapturePreview未产出帧并超时，保留 windows-w14-startup-capture.json，未把DOM回执冒充画面成功。
- w15仅诊断模式使用不抢焦点、置底工具窗口进行实际绘制，无鼠标键盘操作。实际 ParkWeave.exe → WebView2 → CapturePreview(PNG) 取得210188字节图像，已查看确认原侧栏、蓝紫背景、工作台和启动引导正常显示。
- 图像 windows-w15-startup.png、回执 windows-w15-startup-capture.json；exit0、watchdog_terminated=false、stderr空，workspace=2、dialog=true。它是EXE内的WebView内容截图，不是外部浏览器，也不是完整Windows标题栏截图。
- source snapshot e1128e41574231828a918968e6830e6b20459063da1d49adb60716af03a464f0；包53759578字节，SHA4a3bbeb1c213f0cfa452f1c318351d0d542c4e9330f229e94a025eb239451f81。未验证业务创建/重开成功，不标软件可用。
- 外观暂时冻结；剩余重点为真实启动消息、初始化、办理、退出重开，不继续另画原生表单或更换配色。

## w10：真实EXE内启动页加载与退出回执

- 新增 --startup-probe 私有管道诊断，要求 stdout 为管道，隐藏本次窗口，不进行桌面输入、不连接业务后台；30秒内置观察上限，外部45秒看门狗仅管理本次进程。不会伪造 RUNNING 或产品准入。
- w10 原生编译与完整候选组装通过，source snapshot 37cb75deb9c1b824a405568e823dfabfd520ae1e91df78212dba8acf4887cbed；候选53753675字节，SHA e24b71a0e464915a44141388fa71d843812a88c4ec982f3498a9925056198241。
- 在普通Windows用户环境实际执行候选内 ParkWeave.exe：state=complete、workspace=2、dialog=true、nodes=9、document bytes=1197615。随后原WM_CLOSE启动页路径退出0，看门狗未终止，stderr为空。证据 windows-w10-startup-probe.json。
- 这证明内嵌页面不再是空文档，以及无后台启动页可正常退出；不证明业务后台运行后的关闭或完整办理，也不替代原生像素检查。
- 创建/重开的 WebMessage 转发尚未启用。下一步接原请求验证/私有管道，处理启动页到真实后台页面的profile交接，保留原状态、权限和恢复边界。

## Sim2Act 参考与当前内嵌页面加载调整

已只读核对用户指定 Sim2Act 宿主、监督协议与后台入口。借鉴就绪绑定、未启动后台直接关闭、有限停止、共享状态文件按持有句柄方式读取；不复制其配置/凭据或改动该项目，详见 DesktopArchitectureReference.md。

当前园合启动文档为2332384 UTF-16字节，而 NavigateToString 有2MB总大小边界；同时原空白页缺实际导航诊断，不能仅凭返回S_OK判完成。已改为固定 .invalid 内部地址、GET精确匹配、WebResourceRequested 内存响应，页面仍是编译入EXE的原前端，不依赖外部网站。其余网络请求与导航仍拒绝，原业务页面待真实READY后加载原本机API地址。

新增 startup_policy.h 与真实C++白名单测试；w9宿主正在编译（3031）。内存页承载、实际退出及宿主消息转发尚需后续验证，不宣称白屏或完整办理已通过。

## 当前启动空白根因：系统 WebView2 硬链接

- 用户诊断截图指出“WebView2 目录身份未通过”。只读核对注册版本156.0.4314.58、逐级目录打开、所有者及DACL，均符合原规则。
- 实际拒绝发生在随后 runtimePin=pin(exe)：微软安装的 msedgewebview2.exe 链接数为3，旧私有文件pin强制链接数1，且阶段标签仍停在目录身份，形成误导。
- 修正仅为系统运行时 pin 显式允许正链接数；仍持有拒绝写/删除共享的原文件句柄，新增文件所有者/DACL核验，只接受SYSTEM/Administrators/TrustedInstaller写权，继续微软签名与固定Loader检查。私有项目文件仍强制单链接，不修改系统文件、权限或全局设置。
- desktop-w6正在重建（session16505），本轮尚未启动新窗口。需要原生复测，不能仅据源码修正认定白屏已解决。

## 当前最高优先级：复用已认可前端

用户指出 w3 首次启动界面仍是旧工程表单，并明确要求直接用已有新前端。已停止另画 Win32 启动页；本轮未获认可的 GDI 重绘源码保存到 .cache/windows-desktop/abandoned-native-startup-w4.cpp，host.cpp 恢复到该尝试前的 source-w3 字节，不回滚 web.html/workspace_design.css/js 或任何业务改动。desktop-w4 编译产物不是交付方向。

下一步必须接通初始化前的 WebView 前端承载与受限桥接，复用现有设计；现有宿主只有收到后台 RUNNING 才调用 showWeb，因而不能靠换个按钮样式解决。保留实际来源、初始化及恢复状态，不伪造后台就绪。当前工程启动页只是待替换实现，不再作为产品首页验收。

### 复用前端启动封装（宿主接线未完成）

- startup_document.py 直接读取现有完整 web.html，内联原 workspace_design.css/js 和已认可 PNG，不复制另一套设计；仅增加 desktop_startup.js 引导层。
- 初始化前禁止网络、框架与表单导航。页面消息使用固定协议，原 desktop_bridge.request 继续校验原请求，禁止任意动作或扩展字段。未接宿主时明确提示预览，UNKNOWN 不自动再提交。
- 新增9项测试通过，覆盖真实资产复用、CSP 在脚本之前、原请求形状、未知动作/重复字段/超大消息拒绝。初次测试发现原 HTML 没有显式 head 标签，已修正 CSP 插入锚点，不能假设注入成功。
- 仅前端封装及协议验证，C++ WebView 初始化承载、来源校验、消息转发与 profile 生命周期仍待接入；不是已修复 EXE。页面预览文件 .cache/windows-desktop/startup-preview.html，不当作独立软件运行证据。

### 初始化前 WebView 承载接线（进行中）

- desktop build 将当前完整前端封装为 UTF-8 编译常量；宿主新增启动阶段，在原 runtime/Loader 验证后创建当前用户与 SYSTEM 限定的新临时 WebView 目录，直接 NavigateToString，不打开外部浏览器。
- 原导航、弹窗、权限、自动填充和外部资源限制保持；启动阶段仅允许 about:blank 文档。旧工程控件隐藏，不作为产品首页。
- 此片尚未启用启动消息转发，真实 new/reopen 及启动 WebView 到正式受保护 profile 的交接/退出仍未完成；不能把页面可渲染当成可办理。
- w5 后台与桌面构建正在执行（13854 / 35143），前端封装/协议9项检查通过。尚无原生像素结果，后续以进程实际结果与新产物为准。

## 恢复后的 Windows EXE 构建结果

- 暂停前 session 22596 已不存在、无 zig/clang/lld 进程及桌面产物；使用新目录 desktop-w3-r1 重建，旧目录保留。
- 原生编译实际退出 0：ParkWeave.exe 1201152 字节，SHA256 8289555750f139cb0aa07eea25298a411800cc7033021d6c5980a3a9ef2b04bc，含项目 ICO。不是 Python 脚本替代 EXE。
- 完整组装 ParkWeave-w3-candidate.zip 53387668 字节，SHA256 cadb25874bf8b3ac0625a838575708e88aa1e3573481548096a4f439c51a98a6；与 source-w3 SHA 12e441bef6534dea1af7c5b40820713f17b10ffeb4250754e414925e793a73ef 及宿主构建字节绑定。
- 证据 windows-desktop-w3-build.json。独立窗口尚未实际启动，初始化/重开门未签收，usable_product=false；下一步从完整包解压并验证原生窗口，不能以成功出包代签。

## 最新用户决策：Windows 主线

2026-11-05：用户明确先不管 Linux，开发并打包可用的 Windows 独立软件。已修订执行计划，新增 Windows独立应用交付计划.md；W0–W5 成为当前实施顺序，原 G0–G5 的业务和证据要求保留。Linux 环境询问不再是当前待办或阻塞前置。不提交/推送/部署的原约束仍保留。

### W0 / Windows 构建入口改造

- 当前 build.py 实际锁定 Linux Zig 归档且给子进程传 Linux PATH，不能直接作为 Windows 本机构建命令。已增加官方 Zig 0.15.2 Windows ZIP 的精确 SHA256 支持，保留逐成员校验、额外文件拒绝、别名/路径逃逸拒绝；Windows 编译进程使用明确 System32 路径与临时目录，不继承通用编译搜索变量。
- 官方索引 https://ziglang.org/download/index.json 已核对 Windows SHA256 3a0ed1e8799a2f8ce2a6e6290a9ff22e6906f8227865911fb7ddedc3cc14cb0c，大小 92614574。仅增加当前固定版本的宿主平台支持，不升级产品运行时。
- test_desktop_compiler_distribution、test_desktop_bridge、test_desktop_startup_inputs：18 passed / 17 skipped；不是原生启动或 EXE 构建通过。
- 三个运行准入函数仍有明确拒绝，未解除；便携 builder 仍要求精确 Git commit，如何在不提交现有改动的前提下冻结当前源码出包尚待实现。不得拿 HEAD 的旧界面出包冒充当前版本。

### W0 源码快照构建与本机回归

- 已新增 --source-snapshot 模式，用明确 SHA256 绑定 ZIP 内的源码字节；source_commit 留空，另记 source_snapshot_sha256，不伪造提交号。保留 builder/payload/lock 一致性及原启动门。
- 快照拒绝越界路径、ADS、重复大小写路径、链接对象、无关目录及超限成员；新增定向测试。
- 回归发现独立测试 fixture 漏了 native_sample.py，已补齐实际产品模块，未删除断言。另发现 Windows Git archive 的换行转换与 git show 原字节不一致，构建器对本次只读 Git 命令明确禁用 autocrlf，避免包字节漂移，不改用户 Git 配置。
- 一项原 symlink 测试因当前用户 WinError 1314（无创建符号链接权限）失败，保留失败，未更改系统策略。
- 官方编译器下载 session 77971 本轮仍存活，文件由 0 增至 3 MiB；不是已校验完整包，不重复启动下载。

### W0 当前源码实际冻结与依赖获取

- source_snapshot.py 已提供命令行冻结工具；测试实际通过 snapshot → assemble，将未提交 web.html 的精确字节装入候选，且 source_commit=null、原 usable_product=false 保持。定向 7 项通过。
- 已冻结 `.cache/windows-desktop/source-w0.zip`，703 文件，6616113 字节，SHA256 `6aa6c4d93cd32aa2f499e4963906c091e2ecbc2d48cb7933191266a83d41f71f`。这是 W0 源码快照，后续修改需重新冻结，不是最终软件包。
- 依照已有 runtime-assets.json 的 HTTPS URL/大小/SHA256 获取本项目 Windows 运行依赖；不运行安装器、不从其他软件复制运行时。不完整下载使用 .part，只有大小及 SHA 均匹配后改为正式资产文件。session 92645；结果写 .cache/windows-desktop/runtime-acquisition.json。
- 编译器 session 77971 仍存活并缓慢增长，未启动重复下载。以上进程只获取字节，不代表工具已执行或 Windows 原生业务已通过。

### W1 快照身份的运行链缺口

- 发现 credential_envelope、fixed_store_security、native_instance_security、native_preparation_candidate、native_secret_store_candidate 仍只接受 40 位 source_commit；entry/runtime_payload/staging/trial_authority 也直接引用该字段。因此新快照包尚不能被现有运行链完整接受，组装通过不代表运行通过。
- 新增 source_identity.py，明确 Git commit 与 snapshot SHA256 两种互斥身份，绑定完整 manifest SHA256。7 项纯逻辑测试通过：保留旧身份，拒绝混合/缺失/错误长度及跨来源匹配。
- **该模块尚未接入上述运行链**；下一步逐处接入、保留旧安装解封兼容与原拒绝门，并补新/重开绑定回归。不得把本片算作完整身份迁移完成。
- Python 官方重试尝试 curl 的系统 TLS 失败 SEC_E_NO_CREDENTIALS；未关闭 TLS 校验或改变系统凭据设置。原 urllib 运行依赖任务继续处理独立资产，opentelemetry 与 pydantic_core 也分别记录网络超时，未采用未校验文件。

### W1 来源身份接入

- source_identity 已接入 entry、credential_envelope、fixed_store_security、native_instance_security、native_preparation_candidate、native_secret_store_candidate、runtime_payload、native_runtime_staging 及 trial authority/domain/facts。Git 与快照各自绑定，混合身份拒绝；新增运行模块纳入构建及独立 fixture 清单。
- 配置封装新增快照 roundtrip／混合拒绝测试。定向运行：33 passed / 2 skipped / 53 subtests passed。全部 portable Python 文件 AST 语法检查通过。
- 首次较广集合 22 failed / 27 passed / 13 skipped：fixed_store_security 的合成生命周期测试在当前 Windows 进入原 OWNER_MUTATION_PAUSED，早于其预期状态；未修改或删除断言，不能记 Windows 启动通过。后续需隔离核对该组平台夹具和实际原生试验。
- 运行准入仍闭合，旧安装原生解封/冷重开尚未实跑；CI 专用证据路径与 loader 输入报告还需核对快照兼容，不把这次纯逻辑通过升级为完整迁移完成。
- 依赖获取 session 92645 已完成；PostgreSQL 381531864 字节官方资产 SHA256 校验通过。失败依赖以 runtime-acquisition.json 为准，后续仅重试已确认失败项。

### W1 Windows 当前用户原生 DPAPI 诊断

- 用现有 _NativeDPAPI 仅处理随机内存数据，隔离执行环境调用返回 Windows 错误 2。发现产品把 CALL 失败错标为 ALLOCATION，已修正 phase；12 passed / 24 subtests passed，保留原清理与拒绝逻辑。
- 同一修正源码在获准的普通 Windows 用户执行环境实跑：加密→解密相等、错误 entropy 被拒绝，PASS。无创建应用 profile、账户、权限变更，仅写诊断报告。说明隔离环境失败不能直接归因为用户电脑 DPAPI 不可用。
- 证据 windows-dpapi-sandbox-comparison.json，源码 SHA 45bb8ce16177e61cf4a2d0fcb1543d4d4f6b402babb144d6b0f90657237c8475，Windows 10.0.22631。跨身份隔离、受保护目录、initdb、重开与生产准入仍 NOT_TESTED，未打开三道门。
- 对原六个失败依赖仅启动一次定向 retry1（session 46101），opentelemetry_api、typing_inspection、tzdata、pydantic_core 已校验通过；其余等待本次任务结果，不重复请求。

### W0/W1 启动工厂绑定与资产收口

- 新增 test_desktop_payload_runtime_identity，直接调用实际 native_invocation 并捕获 factory 参数，覆盖旧 Git、新 snapshot、混合身份拒绝。与 source_identity 定向共 10 passed，不执行原生初始化。
- loader 输入诊断新增独立 snapshot 字段，不把空 source_commit 误当完整来源。CI 专用 native_business_window 仍要求已审 Git parent，保持独立门，不由快照自动签发试验授权。
- 官方 WebView2 1.0.3537.50 SDK 已下载并核对 SHA256 5ea526bbd728adda0da4d31219267e96460494a427e4894c4e09d9f320f4b9aa，8957746 字节。
- psycopg_binary 重试校验通过，运行锁文件 24 项中已重新逐字节核对 23 项，剩余 Python。状态见 windows-runtime-asset-status.json。
- 唯一仍阻塞的 retry1 下载进程经精确脚本匹配后主动停止，部分数据保留；普通用户环境一次 curl 官方下载，保留 TLS 校验、总时限 120 秒，session 51685。编译器旧 session 77971 仍单独处理，未把未完成文件称为可用资产。

### W1 原生受限令牌派生与下载状态更正

- 补记真实结果：上段 Stop-Process 当时实际返回空引用错误，不能算停止成功。后续对同一脚本唯一进程 PID 51848 再核实，以 Process.Kill/WaitForExit 成功结束；原文件保留。
- curl session 51685 在 120 秒退出（code 28），已下载 3082304/11133606 字节。随后明确从该断点续传，session 12238，总时限 600 秒、低速超时 30 秒、保留 TLS 校验；没有从零重复下载，也没有采用部分文件。
- 当前用户原生 DERIVE_ONLY 诊断 PASS：调用既有 _RestrictedPrimaryCandidate 派生受限令牌，原代码的主令牌用户/组/权限查询比较通过，句柄关闭。未调用 Owner/DefaultDacl setter、未启动子进程、未创建账户。证据 windows-token-derive-diagnostic.json。
- 该结果只覆盖派生/查询，不覆盖主令牌全部属性、Owner/DefaultDacl 变更、实际 initdb、跨身份隔离或生产准入，三道门仍未开放。

### W1 默认 DACL 原生兼容修复

- 原生 CREATE_CANDIDATE 准备首次失败于 ADMIT_DEFAULT_DACL_SUBSET；保留 windows-derived-token-preparation.json。匿名只读分类发现默认 ACL 有 CURRENT_USER、SYSTEM 和实际当前令牌中的 CURRENT_LOGON_GROUP 允许项；未输出 SID。
- 修复只在本次派生令牌候选 ACL 中移除已从该令牌真实查询确认的 logon-group 允许 ACE，保留 deny，随后仍走原闭集检查。未观察到的组/普通组授权仍拒绝，不扩大可信主体，不改变原主令牌，不修改文件 ACL。
- 新增 tests/test_windows_logon_dacl.py；相关纯逻辑/源码检查 10 passed。
- 修正源码 Windows 原生复验 PASS：派生 DefaultDacl 与 Owner 准备成功，原主令牌所查询的类型/用户/组/权限/Owner/DefaultDacl 前后相同，句柄关闭。证据 windows-derived-token-preparation-r2.json，SHA 21080c434bd874051b7be7274628e2106f0e04a9b51e3fdeaefcf0cb4fe0cf79。
- 未启动子进程/数据库，未创建账户；这仅补上 OWNER 的部分证据，原生完整安装、跨身份、日志与 loader 仍未签收。

### W0 后台候选实际组装与 Windows loader 数据

- Python 断点续传完成，11133606 字节、SHA256 4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3 匹配。24 项锁定运行依赖已齐全。
- source-w1.zip（SHA 1621961ed7ff3703c4a47c60f6d83dbec35d01b520a6bab8979527d2c273ae5c）组装 bootstrap-w1.zip，52718312 字节，SHA 93805757dcb893b6bcf6a22af0745f64f61c8a93302608e9a655dd4eacc92bb1。解包原 verify_directory 核验 3052 文件通过；无缺失私有 DLL，455 项平台依赖待核。无桌面 EXE，usable_product=false，不对用户发布为成品。
- 读取本机 Windows 22631.3235 的系统 DLL 与 ApiSetSchema 数据，不加载这些映像、不获取签名缓存、不改系统。CRT 文件版本 14.50.35719.0 为观察值，不自动证明最低工具链兼容。
- 原 API-set 采集器拒绝本机合法 kernel.appcore.dll、win32kbase.sys、winspool.drv。修正文件元数据解析允许这类有限 basename；路径仍拒绝，用户态 resolver 对非 DLL 主机明确 NON_DLL_HOST_NOT_ACCEPTED，不授予加载许可。
- 本机 schema 哈希索引核对通过，16 项请求得到 15 项、缺 1 项。不能把缺 schema 映射直接判成 DLL 不可用；下一步结合实际系统文件/导出定位。
- test_api_set_map：7 passed / 1 failed，失败为 Windows 下 read_bounded 增长测试未到达其 os.read 注入；已保留，后续定位，不修改断言。新映射兼容场景通过。
- 本片采集器/解析修复发生在 source-w1 冻结之后，后续候选须重新冻结；不得把当前树或新修复标成 w1 包内字节。

### W1 元数据读取修复与同步合同原生解析

- 复现 Windows lstat 与 fstat 的 ctime 不同口径：旧跨方法直接相等比较误拒绝正常文件。read_bounded 保留 dev/inode/size/mtime 跨方法比较，并分别核各方法读前/读后 ctime，未删除变化检测。
- 新增模拟不同方法 ctime 与读取中变化反例。tests/test_api_set_map.py：10 passed / 1 skipped。符号链接检查拆为独立用例，只有实际 WinError1314 时标注无法验证；保留原拒绝断言，不把跳过计通过。
- 本机 selected 元数据已实际通过 Python 读取/解析，生成 windows-apiset-resolution.json。
- 唯一静态缺项 api-ms-win-core-synch-l1-2-0.dll 经固定合同名、System32-only 原生解析到 KERNELBASE.dll，WaitOnAddress/WakeByAddressAll/WakeByAddressSingle 符号存在，未调用这些导出。证据 windows-synch-contract-probe.json。不能把 namespace 精确名称缺失等同 OS 加载失败，也不凭此将整个 loader 标为通过。
- 编译器 session 77971 仍存活，继续原下载，不重复启动。

### W1 固定日志组件 Windows 文件证据

- 原 FixedJournal / INSTANCE_V2 配合 Windows 实际文件 IO 执行初始化双槽、合法 UNKNOWN 转移、fsync、回读、关闭/重开同文件、损坏拒绝，全部观察为 true。仅新建本工作区 .cache 下随机独立测试目录，无旧资料修改。
- 证据 windows-journal-component.json；可复现诊断 scripts/windows_ci/windows_journal_component_probe.py。该适配仅检验原算法与真实文件 IO，不是 FixedWindowsFilesystem 的生产 lease，未测排他、进程中断、断电、受保护对象 ACL；不开放 fixed journal 准入。
- 编译器下载继续同一 session 77971；55 秒有界等待不重复发起网络请求。

### W0 编译工具传输与当前后台重新冻结

- 原 Zig 下载持续推进但速率很低，明确采用额外的官方同地址分段方案（不是因一次观测超时盲重启）：4 路、每段 2 MiB，严格要求 HTTP206 与完整 Content-Range/长度，整包仍核官方锁定 SHA256。session 95384；首四段合计 8 MiB 已收到，未称完整资产校验通过。原 session 77971 仍保留。
- source/编译器/入口绑定/默认 DACL 定向集合 21 passed。
- 最新源码重新冻结为 w2 后台候选，构建脚本 .cache/windows-desktop/build-bootstrap-w2.py，结果 windows-bootstrap-w2.json；不以旧 w1 的文件清单绑定新代码。仍无桌面 EXE 或产品准入声明。

### W1 身份对照范围与桌面图标接线

- 普通用户随机数据 DPAPI roundtrip 成功后，读取两个既有执行环境的 TokenUser 摘要确认 SID 不同；另一环境解密拒绝。但其自身随机加解密对照也失败（错误 2），所以 windows-dpapi-cross-context.json 最终结论为 INCONCLUSIVE，cross_os_identity_verified=false，不能据此签收跨身份隔离。未创建任何账户；密文/entropy 仅为随机测试夹具。
- host.cpp 原先使用 IDI_APPLICATION 通用图标；改为从 EXE 资源读取项目现有 ICO 的大小图标。desktop build 编译 RC 资源并记录 icon SHA256，portable assembly 核同源码图标哈希，防止混包。
- 构建参数统一绝对路径，避免资源编译 cwd 切到临时目录后相对编译器/缓存路径失效。Python 语法与 ICO 结构检查通过；相关集合 5 passed / 15 skipped（C++ 编译器仍未完成获取），RC/EXE 尚未实际编译，不宣布图标渲染通过。
- 分段任务 session 95384 已收到 14 个完整 2 MiB 段，仍待全部完成与最终 SHA256。此后源码又有改动，w2 包保持原字节，不声称包含这些图标接线。

### W2 工作台窗口尺寸接线

- 发现宿主 WM_GETMINMAXINFO 始终限制 1040×720，即使进入已具重排能力的 WebView 工作台。改为 controller 存在时最小 360×360，首次安装表单暂保留原限制（尚未做原生表单重排，不让控件静默裁切）。
- 状态标签宽度随客户区变化，WebView 顶部边界不超过客户区高度。仅源码检查，未编译/未原生像素验证，不能标窗口缩放验收通过。
- 分段下载已收到 22 段约 44 MiB；继续同 session 95384 有界等待，最终 SHA256 仍未验证。

### W1 包内真实私有运行时执行

- 已核完整 w2 payload 后，实际调用其私有 Python 3.12.10（-I -B -S -X utf8），在白名单环境/明确 System32 PATH 下导入 FastAPI 0.142.2、psycopg 3.3.6、pydantic 2.13.5、uvicorn 与 parkweave.api，退出 0。未调用 app factory、数据库或服务。证据 windows-private-runtime-import-r2.json，重用脚本 scripts/windows_ci/private_runtime_import_probe.py。
- 初版探针漏 -B，产生仅由探针创建的 __pycache__；逐项确认全部额外文件均是包根内 .pyc 后清理，再核包恢复原清单。产品宿主/API/worker 原命令均已有 -B，没有把探针失误算作产品缺陷。
- 初版白名单大小写敏感遗漏 SystemRoot，导致 Winsock 错误10106；保留 windows-private-runtime-import.json。修正探针按 Windows 大小写不敏感语义选环境变量后成功，无系统设置修改。
- 真实执行包内 initdb.exe/postgres.exe/pg_ctl.exe 的 --version 均退出0、报告17.11；未创建 cluster/启动服务器。执行后 verify_directory 再次通过。证据 windows-private-pg-version.json。
- 分段下载收到 26 个完整段；最终整包验证仍未完成。

目标保持 active。未提交、未推送、未部署；本轮不是阶段验收通过报告。

## G0 初始冻结

- 分支 codex/material-polish-20261105，HEAD ace8d1c9c6b23d32a8a3019ebdeac7f07e56364e。
- 保留已有修改，冻结 1340 个源码、测试、脚本及前轮证据文件。baseline-manifest.json 记录逐文件与 tracked diff SHA256；完整副本位于 `.cache/product-closure-20261105/pre-G1-source.zip`。
- 冻结只能证明本次捕获的字节，不倒签历史截图与源码对应关系。
- 复制完整用户 MD 为执行计划.md。Downloads 未找到所述完整 ZIP 或独立 Codex_执行入口.md；已按完整计划第 18 节执行。
- at-audit.json 保留原绑定总表全部 42 个条目（含工程条目），不改变原 whole_status。仅检查 selector 文件存在性，函数有效性、实现映射和本轮执行待逐项核对。

## G1 进行中

- U7：协同工具栏与各分类原面板移入统一实色阅读面；不新增请求、不替换原操作。
- U5：日期入口可见文字明确开始／结束，原 accessible name 暂保留以兼容键盘回归。
- U13：紧凑头部已实现。窄窗/低高度仅收起原 token 输入及静态说明，其他状态节点不折叠；新增跳到当前事项。宽窗恢复展开，改变窗口时不折叠正在操作的输入。
- U2：非选中导航移除默认按钮阴影。
- 浏览器回归通过（HTTP mock）：三恢复状态、日期/表单、分类、来源菜单、事项切换及返回过滤；无 pageerror、无写请求。协同首条记录 y≈394，不再为坐标挤压内容。
- 720×450、1024×640、320×700 实测展开会话、聚焦原输入、收起、跳转到事项标题与水平溢出检查通过。720×450 标题约 y=260，正文未缩小。
- 两个现有 DOM 套件通过；证据与源码哈希在 evidence/g1/verification.json，新脚本 tests/frontend_product_closure_browser.js。该记录不是原生缩放或真实后端验收。
- 下一步：U10 三恢复状态截帧/祖先透明度诊断；U13 窄窗壳层，资源去重复，组件状态及旅程映射。

### G1b 定向补证

- U10 已实测 INVALID 无 pending、SUBMITTING、UNKNOWN，字体 ready 后等待 300ms 截图。无 pending 为白字 rgb(49,95,196) 蓝底，disabled/:disabled/aria-disabled 均 false；祖先 opacity 全为 1、filter 全 none。当前版本未复现祖先导致的淡化；无法反推旧截图生成时序。
- 两种 pending 均真实禁用，显示原原因；没有改写原业务 disabled。记录见 evidence/g1b/browser.json，三状态截图和 source manifest 同目录。
- U4：摘要使用“查看当前所选资源”引用而非再次排长名称，accessible name 保留完整原名称与来源入口。原生选择框及附近可换行全文保留，未裁剪原始限定词；READY 目录回执压缩边距，错误与拒绝不改。
- 新一轮浏览器回归及三档紧凑窗口任务通过，无 pageerror/写请求。
- journey-state-matrix.json 已建立 12 个旅程家族的实际 HTML ID 清单，明确只是静态入口盘点；角色/handler/DTO/完整状态仍待逐项核对，非 G2 通过。
- 确认较新 local_sample.py 提供四角色独立初始安装且不 seed 办理结果；scripts/local_product.py 当前入口要求非 root Linux。该源码存在不证明当前 Windows 已有可运行隔离后端，未尝试绕过平台门。

## 后端证据边界

已读取 LocalMaterialProduct 与 LocalSyntheticExperience：Linux 原安装/原私有库路径不能当作当前 Windows 的可用授权数据库。尚未使用任何 DSN、未安装数据库、未启动 worker、未调用 LIVE。继续检查较新的完整样例入口和合法环境，不把旧材料样例限制外推为整个产品未实现。

G2–G5 未完成，PR0 不作通过结论。

## G2 派单角色状态与 AT 绑定核查

- 115 条现有 engineering_selectors 的文件及 Python AST 名称全部找到。at-audit.json 标为 AST_NAME_FOUND；这不等于 pytest collect 或执行，更不改变 whole_status。
- 阅读原 renderDispatch、dispatchPendingUI、dispatchAcceptRead，以及 readCollaborationList、loadNoticeList、loadCaseWorklist 和 renderReceipt 的角色/状态逻辑。
- 新测试 frontend_dispatch_journey_browser.js 用显式 DTO 调用原渲染器，验证执行者 OFFERED、STALE、专员 OFFERED、无合法执行者和 cancelled 五态；无 pageerror 或写请求。证据在 dispatch-renderer-evidence.json。
- 最初测试 DTO 缺少合法 actor_ref 导致接单禁用；原规则要求 64 位十六进制引用。修正合成测试输入后通过，未改产品守卫。保留这一失败原因，避免把不完整 DTO 的保护性拒绝当成 UI 缺陷。
- 旧 service_dispatches_browser_smoke 会在业务中途 owner.assign_status；executor_receipts_browser_smoke 包含 --no-sandbox。两者均未运行，也不能直接用于本计划 BE1。后续以较新 local_sample_normal_entry 的安装与普通 API 路线核对，不关闭浏览器安全门。
- G2 仅派单展示层此项有新证据；服务方案、补正、回执重开、完整 API 角色链和其余旅程状态仍需继续。

## Windows 验收绑定可收集性复核

- 追加一次云端运行的确认仍待用户答复；本轮没有触发新 Actions，没有改 main 或更新冻结的 r4 软件包。
- 原 AT 审计中的 115 个绑定出现次数对应 105 个不同 selector。首次实际 pytest collection 发现 AT-28 共享辅助函数导入连带要求 Linux `pgserver`，导致 2 个入口无法收集。
- 将 `scripts/linux_fixture_server.py` 的 `pgserver` 导入移到已有 Linux 平台守卫之后，保留 Windows 拒绝数据库创建规则。Windows 共享进程停止辅助函数不再要求该 Linux 包；没有启动或开发 Linux 服务。
- 新增 `tests/test_windows_test_collection.py`：实际子进程禁止导入 pgserver，仍能导入共享辅助函数；模拟 Windows 平台在创建数据库临时目录前拒绝；自有子进程停止逻辑仍可调用。该定向回归 1 passed。
- 修复后 105 个不同 selector 全部成功收集，展开为 212 个参数化用例，collection exit 0。不是 212 项业务执行通过。
- `at-audit.json` 现在按 ID 关联 `docs/验收规格.json` 中的场景、步骤和 oracle，逐 selector 记录收集后的 nodeid 与源码 SHA-256；保留原工程范围，whole_status 及 execution_this_round 均未提升。
- 13 项 AT 仍没有原工程 selector：AT-07/08/09/10/11/12/14/15/24/29/33/35/36。空绑定不能直接解释为功能未实现；后续须审阅较新实现与测试，建立有限工程绑定及完整目标环境执行路线。
- 证据：`at-collection-evidence.json`、`at-collection-output.txt`。真实后端、Windows 完整四角色办理与正式 AT 通过仍未建立。

## EXE 首次使用表单：模式切换校验修复

- 发现新建模式填写非法高级端口后，切回“打开已有工作台”，隐藏且未禁用的端口仍会参与浏览器原生表单校验；折叠高级设置时，错误字段也未展开。
- 在真实 Edge headless 中先复现 `invalid advanced field stays hidden`，再修复：重开模式禁用无关端口；新建模式恢复 required/enabled；invalid 捕获展开高级设置；相同端口的自定义错误聚焦应用端口。
- 真实浏览器验证非法、空、相同端口不会发送请求，错误字段可见且聚焦；切回重开能提交原 reopen 协议（端口为 0，密码为空）。宿主消息明确为 fake host，不是原生办理证据。
- 原 DOM 测试的重复拦截、UNKNOWN 不重试、REFUSED 可恢复、密码清空仍通过；启动文档/桥接约束 pytest 9 passed。
- 已冻结本地临时源码 `6aff1499a2174b61cdc515eaceb5a3ad4712e3e2`，构建 r5 新候选成功。ZIP 53,760,516 字节，SHA-256 `788923c498ad6b096b9a70c5e0b2a2eb01c18a09f584a33f5ffd3b3db8d8265f`。
- r5 取代 r4 作为下一次隔离运行准备的最新候选；见 `ci-frozen-candidate-r5.json` 与 `desktop-startup-validation-r5.json`。r4 保留历史，不覆盖旧证据。
- 未推送新提交、未触发追加云端运行，当前 main 不变。EXE 真实初始化、四角色办理与冷重开仍未通过，`usable_product=false`。

## AT-09/10/11/29 补充工程绑定及私有运行时期限计算

- 已审阅资源组合、单资源确认、占位并发与期限计算测试的实际断言，新增 `at-resource-clock-bindings.json`，按四个 AT ID 记录覆盖点、缺口、22 个精确 selector、88 个收集后的参数化 nodeid 和源码哈希。
- AT-09 绑定合成双资源原子确认、无效第二成员和写入失败整体回滚；AT-10 绑定并发容量/同键去重/异参冲突；AT-11 绑定提交时当前版本与锁等待后的实际时钟重验。这些数据库测试本轮仅收集，未执行。
- AT-29 的 7 个纯计算入口展开 54 项，已在 Windows 开发 Python 及 r5 私有 Python 中分别全部通过。私有运行时使用包内 handling_deadline 与 vendor 依赖，pytest 来自开发测试工具；不属于普通用户交付依赖，也不启动 API/PG。
- 计算覆盖 UTC/业务时区、半开工作时段、显式合成日历、DST 歧义/不存在时点、过期与不完整来源、极端日期。合成来源不是正式 SLA。
- 当前 handling_deadline 明确无合法停表授权，非空 pauses 返回 PAUSE_AUTHORITY_UNAVAILABLE。合法停表的完整目标仍未实现，不能把技术暂停/补正等同停表，也不能用 54 项通过宣布 AT-29 完成。
- 当前 `at-audit.json` 增加四项补充绑定引用，whole_status 均保持 NOT_RUN；AT-29 仅记录有限计算测试通过。此前 collection 所绑定的原审计字节另存 `at-audit-at-collection-snapshot.json`，原 SHA 核对一致，不覆盖旧证据。
- 证据：`private-runtime-clock-tests-r5.json`、`at-resource-clock-collection.txt`。未修改 r5 程序、未触发新云端运行；Windows 初始化及真实办理仍待获准的追加测试。

## 用户追加授权后的 run 19 与本地修复

- 用户明确允许再运行一次，已在现有临时分支绑定并执行 run 19：42025305561，approval commit bcfbff7918dabfd944ea9bdc0ffcfa656cc7899a。持续跟踪到 completed/failure；约 361 秒，无重试，无 main 更新。
- 首个 runner 精确重建冻结 r5 成功，EXACT_APPROVED_BYTES；第二个 runner 原源绑定和私有解包成功，CRT 严格检查通过。
- 在 CLUSTER/PIN_COMMAND_PATH 返回 NtCreateFile 0xc0000043 共享冲突，尚未运行 initdb 或桌面 trial。租约清理有拒绝记录，结果保持 UNKNOWN / NOT_ACCEPTED，不宣称正常办理或正常退出。
- 本地追到确定的自有目录句柄冲突：OwnedNativeObjects 的保留标记目录采用写入+DELETE 权限，妨碍 PGDATA 的 read/list 锚点。仅将标记目录改为只读枚举/元数据；原文件写入/DELETE、share-read、产品路径/身份/ACL 和原生准入规则均不放宽。
- 新真实 Windows 用例复现旧 ERROR_SHARING_VIOLATION，验证新句柄允许原 PGDATA 读/list 打开，竞争写入和 DELETE 仍拒绝；测试仅针对一个自有空目录，不运行 DPAPI、服务身份或数据库。
- 相关 46 项检查通过。最小修复冻结在本地提交 049d16e34ed12de739fe38683c6aef5dfc6d879b，r6 候选已构建，源码/产物绑定见 ci-frozen-candidate-r6.json。
- 原始去敏结果 windows-run19-native-result.json；汇总 WindowsRun19Result.json；根因/范围 WindowsRun19Diagnosis.md。执行记录恢复 null、工作流禁用，新本地提交未推送；没有第三次运行。
- G3/G4/G5 和 EXE 可用结论仍未完成；真实业务和关闭重开不能从本次构建/解包成功推出。

## r6 的单次授权运行 20：进入受限身份阶段

- 用户明确允许用 r6 再运行一次。run 20（42028107349）已跟踪到 completed/failure，约 297 秒，无自动重试；main 仍为 ace8d1c9…。
- 构建、精确哈希、传递、私有解包及 CRT 检查通过。run 19 的共享冲突已清除，进入 initialize_protected 后发生 TokenRefused / TokenFailure；桌面未启动，初始化及业务仍未完成。
- 现有日志遗漏 TokenFailure 自带的 phase/winerror，来源表也未包括令牌模块，不能分辨具体令牌子阶段。没有猜测或放宽令牌校验。
- 补充只读去敏诊断，输出固定来源阶段及 uint32/null 错误码，加入令牌与 protected bootstrap 的编译源码匹配；34 项测试通过。不输出异常原文、SID、ACL 或凭据。
- 另补真实 Windows 原 _pin_command_path 局部集成测试 1 passed：旧父目录权限失败、新只读父目录完整路径链通过；仅元数据 stand-in，不创建 lease/PGDATA capability，不做数据库/DPAPI/服务身份操作。初次断言仅因 PostgreSQL 规范路径用正斜杠，修正为 Path 等价比较，产品未改。
- 冻结本地提交 7602ccac0e6a2de762ff41cf4035aa35dd6240db，r7 诊断包已构建；这不是令牌问题的功能修复。首次本地 zig rc 超时，确认进程终止后同源码本地重建成功；未再运行云端。
- 证据：WindowsRun20Result.json、windows-run20-native-result.json、WindowsRun20Diagnosis.md、run20-token-diagnostic-tests.json、run19-original-path-pin-check.json、ci-frozen-candidate-r7.json。

## r7 单次定位运行 21 与受限组条件修正

- 用户明确允许用 r7 定位一次。run 21（42038672968）已跟踪到 completed/failure，约 316 秒，无重试。云端精确构建、传递、私有解包、CRT 检查通过，main 未改。
- 新诊断成功定位到 restricted_token_candidate._check:182 的组属性相等检查；TokenFailure phase=QUERY_3、winerror=null。说明此处为软件谓词拒绝，不是查询 API 返回失败。原日志没有具体组属性前后值，不能声称已证明唯一组变化根因。
- 对照微软 CreateRestrictedToken 规范，修正被明确禁用组的后置条件：DENY_ONLY 必须设置，两个启用位必须清除，只许移除原有其他属性，不许新增；未指定组仍逐位相同，用户/组集合/主令牌类型/权限护栏不变。
- 新 TokenGroupRefused 的去敏字段仅含固定分类和 uint32 属性值，不含 SID/ACL/令牌，供仍失败时定位。没有扩大实际禁用 SID 列表或生产准入。
- 相关 52 项受控快照/源码测试通过；未在用户电脑派生/修改原生令牌，未签收 runner 初始化。
- 本地冻结提交 5b0be26846cbab86e732e90a796f33cf02ae89af，r8 已构建，53,760,849 字节，SHA-256 aa9c56c04562d81261486af3aa89c181b4d4c3b7411f02371130a76321a6506c。执行记录 null、工作流禁用，新提交未推送，无下一次云端运行。
- 证据：WindowsRun21Result.json、windows-run21-native-result.json、WindowsRun21Diagnosis.md、run21-group-postcondition-tests.json、ci-frozen-candidate-r8.json。EXE 初始化、真实办理和关闭重开仍未完成。

## 用户持续授权、运行 22 与管道修复

- 用户明确“我都允许，你别再问我了”，同范围连续修复/冻结/打包/隔离验证不再逐次确认。临时分支、合成数据、每次 25 分钟上限、无 main/发布/部署/真实数据/模型密钥范围保留。授权记录见 后续隔离验证授权.md。
- run 22（42041684226）约 309 秒后 completed/failure。精确构建/传递/源绑定/私有解包/CRT 通过；令牌组属性修正通过，流程进入管道创建后 PipeFailure。控制清理错误计数为零，整体仍 UNKNOWN / NOT_ACCEPTED，未启动桌面或 initdb。
- 本机原管道边界在沙箱和普通进程均复现：GetKernelObjectSecurity 成功、描述符有效且原生长度 92，但 LengthNeeded=0 导致原代码拒绝。仅创建/读取/关闭当前用户随机空管道，无客户端、密码、写入、派生令牌或服务身份，不注册 lease/pipe 能力。
- 修复为固定缓冲区内所有相对结构先经原严格解析，再原生结构/长度交叉验证；非零报告长度必须相等，最后按精确长度再解析。当前用户/受保护 DACL/唯一允许 ACE/权限 mask 等限制全部保留。
- 相关 36 项检查通过，包括原真实 Windows 管道边界；普通进程原边界另验证通过。扩大固定来源回溯覆盖管道/客户端/受限启动/进程/端点，并补有限 PipeFailure phase/数字码，不输出身份或凭据。
- 冻结源码 6faa42b7d3aa9e755deee763713f7badd3bb7cd4，r9 候选 53,760,977 字节，SHA-256 fffe9fdcd4965cf17fcec277c4a347b777ee7c1bd124106127217e1538aeadf9。按持续授权绑定并启动 run 23（42045112136），不是无变更重试。
- 证据：WindowsRun22Result.json、windows-run22-native-result.json、WindowsRun22Diagnosis.md、run22-local-pipe-readback.json、run22-pipe-fix-tests.json、ci-frozen-candidate-r9.json、WindowsRun23Result.json。完整办理与冷重开仍未签收。

## 运行 23 与初始化观察预算交接

- run 23（42045112136）约 408 秒后 completed/failure。管道修复已通过，流程到 _freeze → PGDATA _profile_held 时因旧 target.deadline 过期被拒绝；尚未启动 initdb、工作台或办理。清理有拒绝记录，仍 UNKNOWN / NOT_ACCEPTED。
- 源码显示配置尾部 require_inputs 默认 10 秒观察窗口覆盖 target.deadline，后续 bootstrap 未将初始化调用方原有明确截止时间交接给复用对象。
- 修复 require_inputs 的可选 deadline 传递，initialize_protected 进入 bootstrap 前按原调用方截止时间重新验证；原 source budget 裁剪和局部 <=30 秒限制保留，不重置整体计时，不在 lease 公共入口内嵌套启动。
- 定向 6 passed；扩大回归 10 passed、4 failed。四项旧 subwindow fixture 在 Windows claim_fresh 时先被 OWNER_MUTATION_PAUSED 挡住，尚未到预算断言，保留为 fixture 阻断，不改门或冒充通过。
- 冻结源码 25a8cbc1f0249d1934d7cb1277bbc0d19b78e8b8，r10 候选构建成功：53,761,119 字节，SHA-256 5ac98ffc3261eb42720b458944a550a03ef5798fc293dd468f2da348127ca600。
- 按持续授权绑定并启动 run 24（42048148928），只推现有临时分支，无 main/发布/部署。结果见 WindowsRun24Result.json；相关诊断见 WindowsRun23Diagnosis.md。

## 运行 24 与嵌套探针预算同步

- run 24（42048148928）completed/failure。原 PGDATA 观察截止时间已交接，但布局内部独立 _NativeSecretFiles 探针仍使用旧 deadline，_leaf_held → layout._root → probe._time 被拒绝，尚未启动 initdb 或桌面。
- 统一在原 _run 的受控入口为 store.api、PGDATA target、layout 和其已有 probe 同步同一个 source-clamped end；不新增计时起点，不改变目录/身份/权限检查。新 probe=None 的构造中间状态也被测试覆盖。
- 11 项受控预算/输入绑定回归通过。冻结源码 dcb5c9846a49e50432d97739bf47fad358c76aae，r11 候选 53,761,207 字节，SHA-256 16faf1debaacd3fd25bf5d3226b007a8c713a825e0aa5080248048aae7792fde。
- 按持续授权启动 run 25（42050547410），原临时分支/25 分钟上限/main 不变。真实原生初始化与完整办理依旧待验，不把控制时钟测试当成原生通过。证据：windows-run24-native-result.json、run24-nested-deadline-tests.json、ci-frozen-candidate-r11.json、WindowsRun25Result.json。

## 2026-11-06 干净版交付与正式 AT 源码复核

- 独立 Windows 产品交互提交 `040c796a9ecf6181390e9cd4e761c4d685bf837a` 已推送到 `codex/demo-video-20261106`。保持新版视觉，移除可见开发注释与冲突开关，冲突由实际使用时间输入触发。完整软件/素材包见 artifacts/demo-delivery-20261106-release。
- 新版 ZIP 经 CRC 校验并解压到中文带空格目录，停止开发服务器后实际 EXE 启动/退出成功；10 张渲染截图、5 类文件导出。此前同前端完成两进程持久恢复；正常 SaveAs 手动选目录仍未验收。
- 正式 AT 36 条重新读取要求及当前源码：29 条已有工程入口，7 条仍无；未发现已绑定入口丢失或旧哈希漂移。AT-07/08 增加源码审阅子项。所有正式状态不变，未把演示标为正式验收。
- 真实执行服务选择响应边界 44 项通过（开发 pytest 工具路径），只使用离线响应，无数据库、无真实模型。首次默认 Python 缺 pytest；使用已有开发工具目录后运行通过，没有安装或修改用户系统环境。
- 本轮未追加云端运行。run 26 的 initdb 0xC000000D 仍是实际后端未完成的最近证据；删除过时“等待批准”作为当前阻塞的表述，保留历史正文。
- 证据：AT当前源码核对_20261106.md、at-current-source-20261106.json、selection-planner-20261106.xml、../demo-delivery-20261106/standalone-release-no-server/verification.json。

## 2026-11-06 Run 27：启动路径修复后的新位置

- 只读版本查询复现 GUID image 退出 0xC000000D、DOS image 成功，工作目录两种形式均不改变结果。原始结果 initdb-path-version-probe-20261106.json；用户可见错误框来自诊断探针，未初始化业务数据库，后续不在用户桌面重复失败启动。
- 受限 initdb 启动采用既有 PGDATA 持有链绑定的 DOS 根，并与原文件句柄查询路径一致；原 GUID/NT 身份、哈希、ACL、令牌、Job 及管道检查保留。32 项普通 Windows 定向检查通过，源码冻结 456bbea0，r13 候选 acf5947f…。
- 持续授权 run 27（42085195491）完成 failure，云端精确重建/包验证成功；原生失败转移到 server adapter launch 的 WindowsJobProcess.create:206 / backend.resume，OwnedJobError。源码调用顺序说明 initialize_protected 已返回，但没有独立成功回执，不能签收完整初始化。
- ResumeThread 数值返回与当时进程状态缺失，新根因待定位。无桌面、无真实业务、无冷恢复通过。工作流恢复禁用、记录 null；未盲目重试。
- AT 补充达到 35 条工程入口及 AT-36 人工路线；新 11 selectors 收集 22 个 nodeid，无数据库执行。正式状态不变。

## 2026-11-06 Run 29：取得暂停计数并补调试附加握手

- r15 源码 39ab9b2 云端精确构建/包验证通过；42088432491 已 completed/failure。原服务进程仍活着（wait=258），ResumeThread previous_count=2、winerror=null，尚无桌面或真实办理。
- 所有通用 Windows runtime 的 loader image 已使用原句柄核对的 DOS 表示，原 GUID/NT 身份与哈希保留。60 passed / 19 Linux-only skipped。恢复/Job/诊断检查 126 passed / 1 目录旧清单失败另记，不声称全套通过；目录有 98 文件未登记。
- 原调试 watch 只等 attach 返回，未等初始断点 Continue 完成；按文档与观测作时序假设，现补等待原泵 ready、初始事件/断点/未退出/无失败、原 birth 与 deadline。暂停计数守卫仍恰好 1。37 passed / 19 skipped，新时序原生待验。
- 本次源窗口恢复 null，工作流禁用；没有盲目重试，也没有修改前端或录屏包。
