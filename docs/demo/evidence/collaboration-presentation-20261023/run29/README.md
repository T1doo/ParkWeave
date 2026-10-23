# run29：协同、派单、回执与目标/TXT呈现

受测源码 `6ba3459f51929a46128b656d6452c2db8efd3a6c`，tree `bd287b61023e4cca2dfd8677422dc89617b1889a`，前版 `aa6b2fb7e92853ea4b22d163260b309bb7992f74`。[官方run29/attempt1](https://github.com/T1doo/ParkWeave/actions/runs/39886778975)，job `120196678972`。唯一执行限定PASS，独审范围见包内actual-review.json，无自动重跑。源码5文件含产品HTML、驱动、font/workflow run绑定与指纹，不称整提交CSS-only。

产品仅增加7个命名静态按钮组与定域样式：整段业务script逐字不变，其他HTML展开组并剥style后逐字同。原ID/hidden/disabled/事件和警示全文保留。派单的当前责任、后续入口与历史分层，进入已接单回执为主动作；回执正文、来源、完整hash与历史分层；目标原状态文字加不同chip，唯一本地产物核验为绿；TXT readonly全文与原重新核对逻辑不变。

8张真实390px视口原图（包内artifact.zip）为四个组件前后对比：01/02协同列表；03/04派单；05/06回执；07/08目标/TXT。图片为组件裁切，宽362或324px，不是手机实机。作者和独审核实际原图；按钮留距、证据分隔、状态层级可见改善。为触控留距，四个after面板都比before高，不宣称本片缩短全页；原7471px计划页未重测。1200px运行几何/可见glyph观察，但没有保留宽屏PNG。协同只有两个资料列表卡片有数据，其分派/回执列表为空，不能称全协同内容页完成。

run23两资料Case列表与run21详情是分开的历史场景，不改ID拼成新业务链。截图明示SYNTHETIC VIEW_REPLAY。原renderDispatch/renderReceipt和原目标读取/核对包生成函数执行；目标上下文仅由原响应字段建立最小绑定，不是假造完整计划或有效身份。16组件呈现的原文、ID、值、hidden/disabled/dataset逐字一致。原P1–P4本地产物已核验，P5实际为WAITING_OUTPUT，仍缺实际产物或当前有效来源；测试横幅说尚待VERIFY，不意味着仅缺VERIFY。原16500B TXT在四变体逐字重现，SHA256 `02c87cebbfa2c60737f6cfbfeb60628181241f2c5b5399433d4b13400cae9bdd`，没有实际下载或新鉴权导出，不是新履约核验。

20 GET在服务器/浏览器两侧观测同一批请求，不累加40；0 POST，未启动产品后端/数据库/模型；允许的API路径仅返回历史夹具GET，无pageerror、意外GET或越界。16几何+16可见glyph不是32tests，静态684码点与实际可见字形范围分列；759指纹不是tests，未重复pytest或collection。本地原夹具接口在两版机械DOM预检通过，0实际HTTP/Chrome，不冒充浏览器或权限验真。真实Tab/Shift+Tab核受检焦点3px，不称读屏或整页键盘验收。

工作与清理 19.699s，发布扫描 19.717s；保原10分钟job/3分钟依赖、90秒工作清理/360秒发布、40GET双侧/0POST、10文件8MiB预算。官方ZIP9成员总2104503B，7个绑定pidfd均退出、worker0、CLOSED/REFUSED，清理错误/信号为空。最终联合result PASS与官方step及worker0；stdout PENDING_FINALIZATION不是PASS，summary正文未独读，完整日志无upload-aborted。

只保留三个仓库文件，减少重复逐图blob：本索引、[完整官方日志](ci-original.log)、[证据归档](evidence.zip)。归档内含字节未改的官方artifact.zip（8原PNG+result）、三原API JSON、同份全文日志、本地检查/来源发布校验、visual-review/validation/独审记录和离线verify_run29.py。解压evidence.zip到新目录后运行`python verify_run29.py`仅离线核验；再解压内部artifact.zip即可直接查看原PNG和result。包内checksums覆盖全部成员。

外层evidence.zip SHA256 `5e64a8330dec76ecd3102fc1d77aae756110558dddd5ea2fb5693948126f85fa`（1758268B）；官方artifact.zip SHA256 `8ceffbad88b24d4a657fbf9b3998171b6e5141fa60e0229c9129aae85db8214c`（1573593B）；全文日志 SHA256 `1518a0b1f29f7e48101b81d2e00ded7895d338ecce7bc289bf6756000e687726`（675478B，641018字符，存盘与原API全文逐字回读一致）。本归档副本不算CI附件数量。

当前没有工具审批pending或未知写入；源提交5个不同文件各一次blob调用，均真实返回预期SHA。普通CLI此前凭据过期，公开git fetch可读不证明push认证恢复；沿既有GitHub连接正常CAS，不代批、不改token、不绕正在等待的审批。本轮后续无新业务、完整角色链、wheel、冷启动、Windows、正式来源、LIVE或正式AT35验收，不称整体前端完成。
