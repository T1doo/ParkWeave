# 本人历史分派通知有界分页

冻结源码 `1bccc05381b5cf1ad58149709a35720d90ea79f0`；父候选 `c5b0a6fb7ece59f4a97e33ecfc021a1c785e6e4d`；独立开发分支 `dev/f2-notice-history-pagination-20261011`。原F2-T04与产品设计§5.5要求授权站内通知；AT-12要求仅获派数据/动作，AT-19要求当前权限优先。原ENG035明确列表只检查最新100条且无全历史覆盖，本片补该工程缺口，不修改原需求或AT整项NOT_RUN状态。

源变更仅 `dispatch_notices.py`、GET `/api/dispatch-notices`、原 `web.html` 通知区域及必要测试。按 `delivered_at DESC,event_id DESC` keyset，初次查询最新候选双键为固定浏览高水位；后续用严格小于最后已检查候选的双键，包含未授权候选也推进。每次SQL最多取100候选、逐项核验不超过100、返回不超过20；在返回界限处不跳过尚未检查的已取候选。

响应保留原scope与语义字段，新增固定page_limit和opaque next_cursor；没有filtered IDs、Case、正文、检查计数或总数。达到任一界限时返回继续句柄，哪怕合法项0；继续只表示还能检查，不保证下一页有合法通知。恰好20/100的末页允许最后一次空GET确认结束。分页句柄不是授权，不可作为业务命令或历史登记证据。

导航只存在app进程内，容量256、从浏览开始起绝对300秒；子句柄继承原期限/高水位，重用不续期。句柄绑定列表用途、主体、park/org、角色与当前会话hash，每页和每次重放都走原身份、READ能力、资料负责范围/Run assignment及具体offer核验。跨主体/租户/用途、篡改、重复参数、过期或淘汰通用403，不回显句柄；重启app需刷新。无registry/快照复制、DDL、Grant、新业务READ或持久授权机制。直接Store调用的导航同样仅存于该Store对象。

页面增加“继续查较早通知”。每页先清原通知/关联视图，替换页面而不累计私有卡片；空合法页仍能继续。refresh、返回、详情、清屏与身份切换推进generation并使旧回复失效，旧卡点击不能重新加载别的页面。继续发送中禁用按钮，GET不自动OPEN或MARK_READ；两者仍为原显式操作。接口及fetch均no-store；句柄失效提示刷新重新核对。

根最终定向68项全部通过：新owned SYNTHETIC PG/API分页26、离线NodeVM DOM/fetch doubles10、原通知32（含消费事务/崩溃恢复、原权限及显式OPEN/MARK_READ）。日志/JUnit见 `root/scoped.*`；新增测试中的业务/outbox/通知seen/read等11表前后比较相同。拒绝仍沿原authorization_audit记录，不将原审计误称业务写。测试fixture owner仅建立隔离合成历史候选，验证实际SQL/ASGI列表，不签真实办理事件生成或现实履约。

独审新增25项全部通过：18 owned PG/API、1纯导航、6离线VM；无剩余阻断。另验123同时间戳、整页边界、100失权、重放撤权/session轮换、期限不续期/淘汰、app重建、迟到详情和JSON解析身份ABA。报告、独立探针与原始日志/JUnit存于 `independent/`，按manifest核验（SHA256 `ff1a3a16ce0c84e11270763fbb7f228b242c704bd971542bbbe000d74711d83d`）；不把根68混计为独审。

失败保全：原c5代码只读导出并在隔离PG实测两缺口，原日志/XML及复现代码保持 `/tmp/parkweave-notice-pagination-baseline/`，2failed原值不改，hash/count见root verification；不公开fixture私密repr。离线夹具初次10failed因VM漏传mode，修正后9pass/1failed因click回调不返回promise，后补异步等待；两轮原证据均保留，不当最终通过。初步26通过也不倒签最终源码。

高水位是固定逻辑键界限，正常后来送达的更大键需刷新才进入；不是长期MVCC快照或任意owner回写送达时间/时钟回退保证。导航进程亲和、多worker部署、真实浏览器/Windows/整页、完整AT/F2与全仓未验收。原 `data: ERR_BLOCKED_BY_ADMINISTRATOR` 暂停保持，未启动浏览器、改URL绕过或部署。真实历史可信代际/维护隔离仍缺，registry/loader未开启。只正常推此开发分支，main/dev既有主线及父候选不改。

原始失败log/XML含pytest输出的22处尾随空格，保持原字节与hash；staged diff --check仅该四份原始失败文件报出此项，源码及其余MD/JSON/探针格式检查通过。
