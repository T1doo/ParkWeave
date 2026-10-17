# 普通资源方案已有批准只读契约

基线 `156b18355cdfb4dc450dbc78c73cb226a3db0d3e`，开发分支 `dev/f3-resource-plan-approval-read-20261017`。本片回到产品读取主线；诊断已经结束，不重跑427或扩SIGINT。最终冻结与实际验证结果见本报告末节及新gate。

## 原实现与本片范围

原 `service_plan_approval.IsolatedPlanApproval` 只有隔离候选批准/消费协议，原Run访问批准仅用于READ，原目录和资源绑定投影均不是普通资源方案批准。本片不把这些对象、candidate列、回执或布尔开关换名当作批准，不改变它们的算法、SQL、角色或写入/激活门。

新增独立 `ReadOnlyApprovalProvider`，只接受可信宿主代码显式提供的 `source_id/read_existing/verify_existing`。`configured_app(resource_plan_approval_provider=...)` 和原 `create_app` 接入该对象；普通CLI工厂不传对象时仍无来源，准确返回不可用。没有任意环境模块加载、目录自动发现、批准JSON环境变量、签名密钥生成或后端安装器。仓库没有提供真实批准后端或信任根，不能把这个Python组合接口本身称为真实来源已经接通。

适配器的读取函数只能选择一个**既有原记录**；原ID读取不能退回“最新”或别的记录。验真函数必须使用其已经合法存在的机制，独立验证原来源、批准主体的授权依据和当前revision/head/撤销状态，不得只相信正文中的verified/state字段或仅验旧签名。调用方不能通过HTTP注入适配器；它是可信宿主组合边界，不是运行不可信Python插件的沙箱。真实适配器仍须限定自己的IO时间，本片不创建连接凭据或扩大其读权限。

## 精确绑定与当前复核

只读事务复用原 `runtime.selected` 的当前READ、本人PREPARE或原获派REVIEW_ASSIGNED、专员、精确目录、同Case/Run及成功本地回执证明。只认可原已采纳且含P2的方案，复用原dependency/adoption证明、方案definition、材料当前性和权限检查，不重做计划或批准算法。

`Scope`精确绑定 preparation/Case/Run、owner/园区/组织、方案ID及revision、材料revision、方案definition SHA、原P2动作范围SHA、当前来源SHA、当前权限代际SHA及数据库名称/OID/端点/app角色SHA。来源包含原P1事实/材料/诉求/目录描述、实际目录xmin和材料版本代际；权限包含原主体/Grant及xmin，撤权后同值恢复不能复活旧绑定。对字段、capability和preparation权限直接复用原检查；不从角色或来源批准反推当前权限。

原 `entry_context` 仍只接受 `namespace=SYNTHETIC` 且目录 `source.kind=SYNTHETIC`；本片不解除该门。既有资料入口和本片正向验证仍属于本地合成边界，不能宣称接入真实批准源后真实业务便可运行；真实namespace/目录的合法入口还需后续单独实现和验收。

原批准记录另绑定source ID、批准ID/record revision/原来源记录ID、批准主体ID/角色/原授权依据、显式UTC批准与生效/到期时间、APPROVED或REVOKED及原撤销时间。只支持与该资料关联的原owner或原专员主体；其他真实审批角色映射不由本片推定。原来源记录ID与授权依据不接受纯空白。源原文最多64KiB，严格模型拒绝多余字段、Run READ用途、模糊时间和重复JSON键。

读取先验来源，再按原批准ID复读同一记录，之后复核当前身份/资料/权限/来源，投影前再次验当前来源head及数据库时钟。错误绑定、到期、撤销、换版、来源或权限变化均不返回“当前已核对批准”。403沿原协议隐藏记录存在性；绑定选择变化409须重读上下文；来源缺失或验真失败不回退隔离批准。这里只是各次检查时的只读观察，不承诺跨系统原子锁或以后仍有效。

当前动作范围只覆盖原已采纳P2的资源关联/重新核对定义；这不是组合成员/时段/费用交付批准。所有结果固定 `execution_authorized=false`、`approval_consumable=false`、`decision_writes_enabled=false`、`run_read_access_granted=false`。没有批准创建/激活接口，不接原资源执行、交付消费或Run assignment判断。

## 原资料页面与GET契约

原资料页新增“读取已有资源方案批准”，先读取当前合法来源上下文，再固定方案ID/revision/context SHA读取已有批准。与Run READ面板分别命名，显示本次核对通过、失效、缺来源或契约不可用；可按固定原批准ID再次GET核对原来源记录。展示字段使用textContent，来源不提供任意跳转URL。身份/资料/方案选择变化、ABA与迟到200/403不覆盖当前视图；当前403清除私有内容；原记录导航也创建独立请求代际。对长有效期记录，浏览器到32位计时上限后重新核对剩余时间并续排，只有实际到期才移除有效提示。仅同一当前绑定下的撤销/到期原记录可只读导航；错误绑定不投影记录细节，也不提供跨方案历史记录浏览。页面不自动POST或激活，也不修改原资源交付按钮。

三个GET均位于 `/api/preparations/{id}/runtime/`：

| 路径 | 固定输入 |
| --- | --- |
| `resource-plan-approval-context` | 原expected Case/Run/服务ID/精确版本 |
| `resource-plan-approval` | 上述字段＋expected方案ID/revision/context SHA |
| `resource-plan-approval/records/{approval_id}` | 同一固定选择＋精确原批准ID |

目录仍不构成批准，改为提示使用独立只读入口。旧隔离批准状态/写路径保持默认拒绝；新读取对象也不能与隔离批准混装。

## 合成证明与真实缺口

测试中的provider是明确 `SYNTHETIC_CONTRACT_FIXTURE`：原自有PG/API和独立签名文件/current-head控制器证明模型、验真调用、绑定、撤销/回放及读取行为；其签名/身份/源数据都是隔离测试输入，不证明真实批准、生产信任根或独立UID安装。UI明确显示“合成契约样本，不证明真实批准”。正向重启证明是新工厂/新浏览器读取同一既有源文件；实际普通Uvicorn子进程冷重启验证的是缺provider持续不可用，不把它称为真实来源正向进程接线。

真实运行仍须已有合法会话和READ/PREPARE或REVIEW_ASSIGNED、当前同一Case/Run/资料及原P2方案、当前材料/目录/权限代际；还须合法既有批准源、原批准主体授权与记录、当前head/撤销查询、已存在的验真信任机制及经批准的只读宿主适配器。没有这些输入就不可用，不能复制测试文件或设布尔值补齐；上述输入也不会自动解除原SYNTHETIC入口门。Windows/正式AT/真实业务/来源/批准、受保护生产host、真实后端正向进程重启、资源执行与完整项目均未验。

## 封存修正

保留原诊断收尾副本不动，新 [字段修正验证](evidence/connection-diagnostics-closeout-20261017-field-correction/validation.json) 与 [修正件](evidence/connection-diagnostics-closeout-20261017-field-correction/sigint-verification.json)恢复 `held_connection_closed_before_sessionfinish` 和 `owned_pytest_and_writer_proc_entries_absent` 两个普通字段名。它们曾被误脱敏为同名占位键；修正件严格解析无重复键，语义与原私有件/原gate完全一致，旧字节另存legacy文本，不重跑任何测试。后续新JSON导出仅处理字符串值，保留schema键，解析和配对校验均拒绝重复键。

开发首窗38setup ERROR是缺失原夹具导入；第二窗37PASS/1FAIL是等价UTC `Z/+00:00`文本比较，修正测试规范化比较；第三开发窗48PASS，另6个自审边界用例PASS，均不迁入新冻结成绩。所有窗口日志/XML保留。冻结首窗 `957ca92328f5542fba10221ceebfaf24565aa600` 六模块141PASS；随后自审修补长有效期界面计时与空白原授权依据。补测首窗1PASS/1FAIL：本机Playwright单次fast_forward将25天毫秒数转为int32而拒绝向过去跳跃；保留失败，将同一边界改为20天＋5天分段，再过6天验证真正到期，第二窗1PASS。这仅推进浏览器虚拟时钟，不推进数据库时钟，补测均与最终用例重叠，不累加。未改main、强推、部署、模型、真实授权/凭据/费用或安全网络权限，无Actions查询，未知锁/进程/session不处理。

## 最终冻结与验证

最终源码冻结 `5180e528c97018b556a8367960fa528aaf3cca40`，720个源码/测试/脚本/配置输入SHA256零漂移，原7个权限/计划/资源算法及角色SQL逐字节未改。原db108到准入基线156b、再到本冻结的祖先关系已核对。原有27715个F2证据Git blob保持不变，字段修正只新增副本。

六个完整相关模块 **143唯一用例全部PASS，0FAIL/ERROR/SKIP，JUnit 547.225秒**。新增50个接口与6个实际Chromium/HTTP用例已包含其中；不叠加旧141、开发/补测或此前获准入427。最终运行未启用连接诊断选项，不重跑427或SIGINT。

| 完整模块 | 唯一用例 |
| --- | ---: |
| `tests/test_resource_plan_approval_read.py` | 50 |
| `tests/test_resource_plan_approval_read_browser.py` | 6 |
| `tests/test_ordinary_runtime_read.py` | 31 |
| `tests/test_ordinary_runtime_read_browser.py` | 5 |
| `tests/test_native_preparation_entry.py` | 16 |
| `tests/test_preparation.py` | 35 |

| 保留窗口 | testcase元素 | FAIL | ERROR | SKIP | JUnit秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| dev-v1 | 38 | 0 | 38 | 0 | 1.264 |
| dev-v2 | 38 | 1 | 0 | 0 | 101.188 |
| dev-v3 | 48 | 0 | 0 | 0 | 225.609 |
| edge-v1 | 6 | 0 | 0 | 0 | 19.932 |
| final-v1 | 141 | 0 | 0 | 0 | 492.198 |
| fix-v1 | 2 | 1 | 0 | 0 | 16.787 |
| fix-v2 | 1 | 0 | 0 | 0 | 13.503 |
| final-v2 | 143 | 0 | 0 | 0 | 547.225 |

以上窗口各自保留，不相加；早期开发窗没有单独捕获调用元数据/准确源码SHA，未事后编造。final-v1为957ca923冻结，final-v2为上述5180冻结。

[最终gate](evidence/resource-plan-approval-read-20261017/gate.json)、[完整JUnit](evidence/resource-plan-approval-read-20261017/final-v2.xml)、[原日志的脱敏副本](evidence/resource-plan-approval-read-20261017/final-v2.log)、[原件/公开件hash配对](evidence/resource-plan-approval-read-20261017/public-pairs.json)、[全部窗口及原因](evidence/resource-plan-approval-read-20261017/failure-ledger.json)、[冻结清单](evidence/resource-plan-approval-read-20261017/freeze-v2.json)。新归档64对均核对原件未变与公开件hash；JSON/JSONL仅处理字符串值、保留schema键并严格拒绝重复键，JUnit节点/非message属性保持。旧错误副本保留，未默默覆盖。

本片仅完成本地合成边界下的已有资源方案批准只读契约，独立父线程审查仍待。交付使用普通开发分支提交与推送；最终交付SHA、实际远端和未提交差异于交付后写入私有 `.runtime/resource-plan-approval-read/delivery-verification.json` 并在最终回复给出，不在归档中预填尚未发生的远端结果。完整项目、真实业务、Windows/正式AT均未完成验收。
