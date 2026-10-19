# 普通未接单另派：验证与运行缺口

本片从 `ac9988489a3a495eac47a8b5def824b5d133d60a` 正常分支接续，原 `db1084100a2477bbff3da8b49287c755dbc83c1b` 为其祖先。原产品 V1 §5.5 要求专员说明原因调整责任方，F2-T04/T07要求协同办理。原普通 CaseStep 在 DECLINE／接单前 WITHDRAW 后仅允许一次 OFFER，导致已有合法执行者之间的明确另派无法继续；旧 Run 交接路径不覆盖此入口。此前提出的待办范围元数据候选已撤回，没有另造防御任务。

## 实际交付

原负责专员从原列表打开同一事项，读取原历史，选择另一位已有合法执行者并说明原因，明确提交新邀请；新方本人接单、提交人工回执，企业独立核对。使用原表、原接口、事务、CAS、请求键、outbox和回执算法，不创建身份、Grant、Run assignment或批准。原页对另派使用独立 `can_offer_again` 能力和明确按钮，不借用已接单交接或新版材料重新接单。

全部代次继承首次截止、资料修订/hash、目录hash/xmin和owner/reviewer授权代际。最多31次邀请；任何历史 ACCEPT 或任何回执均拒绝此路径。完整历史证明损坏、权限或资料变化、旧请求键/坐标、过期和并发冲突均保持拒绝。历史通知先证明来源再核当前权限，旧执行者即使随后重新获派，也不能使旧通知重新可操作。详见[协议](OrdinaryUnacceptedRedispatchContract-20261019.md)。

仅普通 `CURRENT_PREPARATION` 增加此功能，原 Isolated 和本地demo保持首邀请合同。NativeRunAccess、provider、正式来源、SQL/迁移、角色权限和现有工具算法未改。

## 最终验证范围

最终冻结827个源码、测试、脚本和配置文件。清单 SHA256：

```text
4dd148ef89523eae2fb877adb750bbd4a61d8cfa3262806178113b56c14ed9e0
```

独审者逐项重算零差异，有限静态独审未见开放P1/P2；通知代次隔离、损坏回执键异常和跨代来源证明三项已报问题均闭合。独审者动态测试、产品import、文件写入和私有会话读取均0，不转签作者动态结果。

| 完整相关模块 | 唯一用例 |
| --- | ---: |
| `test_ordinary_step_redispatch.py` | 32 |
| `test_case_step_assignments.py` | 33 |
| `test_ordinary_case_steps.py` | 37 |
| `test_case_step_notices.py` | 28 |
| `test_ordinary_case_step_process.py` | 2 |
| `test_local_demo_case_step_chain.py` | 6 |
| `test_personal_task_pagination_ui.py` | 15 |
| `test_record_directory_error_ui.py` | 11 |
| `test_browser_readiness_smoke.py` | 1 |
| 合计（0重复） | 165 |

`frozen-final` 全部165唯一项实际执行：**163 PASS、1 FAIL、2 ERROR、0 SKIP**，pytest 668.198秒，控制器671.39秒，冻结源码零变化，不能称此完整窗口通过。XML有166条记录，因同一用例call失败与teardown错误分别记账，不能作为166唯一项。Python AST、原HTML内联JS/Node harness、workflow YAML/shell语法、diff检查均通过；其他七个workflow逐字未变。未运行全仓或正式验收。

失败栈均保留：新增`target_read`在`prepared→ADD`阶段原2秒连接超时，尚未撤销目标READ或进入另派；同例teardown DROP触发原5秒statement timeout。原隔离模块`WITHDRAW[material]`在fixture建权阶段原2秒连接超时，其异常清理也超时。没有业务断言失败证据，连接超时根因仍未知，不能据此宣称已修复。

同冻结只对原顺序前49项（覆盖两个受影响节点及紧随其后的节点）启用既有自有连接诊断做了一次有界复验：**49 PASS、0 FAIL/ERROR/SKIP**，含新增完整32项；pytest XML 344.032秒，控制器351.00秒。此pytest进程受测1,880次连接均成功并观测关闭，sessionfinish未观测关闭0，49例setup/call/teardown共147条report全部通过；子进程连接不计入1,880。未触发失败采样，因而无法反推首窗超时原因。原2秒连接和5秒清理预算未变，没有改连接实现，没有再跑165刷数；仍不称完整165无误窗口通过。

父级收到环境断连通知后，本实例于2026-10-19 09:45:31 UTC实际成功执行date/HEAD/status只读检查；HEAD仍为原起点，12文件改动和日志完整，owned pytest PID仍在。09:46:07实查主机名与首窗XML一致，随后收到该进程49项结束回执；没有重建实例、另开写入者或重启未知进程。检查原件单独保留。

新增32项含普通工厂与自有合成PG的两种终态→另派→通知/打开/已读→ACCEPT恢复→SUBMIT→ACK→冷读；原权限表运行前后不变、无全Run访问授权。负例含既往接单/回执、清空回执指针后的既往ACCEPT、同方/跨域、缺权/撤权、源变化、旧代次键/迟到操作、A→B→A旧通知、并发CAS、跨事务最终到期、首marker损坏和31次邀请实际边界。

完整原HTML通过Node VM的DOM接口配真实普通loopback HTTP/PG执行用户点击链；4次API进程、3次原worker进程，含另派已提交但响应丢失后本人明确使用同key/body重试，新执行者接单/回执、企业核对和重启GET冷读。此为实际HTTP/PG工程证据，DOM替身不是Chrome。

Chrome另用原受限免费公开GitHub CI，精确本开发分支、run6/attempt1、Ubuntu24、六分钟上限；CI结果与本地165/49分别结算。新增场景读取从自有合成PG导出的公共DTO，所有API请求均在浏览器端fulfill/abort；只读取原页面字节，不向服务器发业务POST、不开DB。证明原表单、首次截止提示和显式同key/body重试；不代表Chrome执行了后台另派或真实办理。原sandbox、零DB、无会话401等门保留。本地Chrome启动未重试，Windows未运行。原Actions REST/日志接口的Forbidden仍保留，不重试；公开状态与父级已登录浏览器原步骤读取分列。

## 保留的开发窗口

原件留在忽略目录 `.runtime/unaccepted-step-redispatch-20261019/`，包含stdout/stderr、XML、命令、耗时和源码清单；不包含在普通发布或CI artifact中。各窗口独立，不相加：

| 窗口 | 结果及用途 |
| --- | --- |
| `baseline` | 3失败；原普通入口无法另派，修补前记录 |
| `core-v1` | 1通过／2失败；回放payload字符串与UUID比较错误及作者断言误用event.id |
| `core-v2` | 1通过／2失败；作者断言误用通知DTO未提供的offer_id，按原最小投影修正 |
| `functional-v3` | 25通过／1失败；发现目录变化仍可另派，补冻结来源/负责人代际比较 |
| `path-v4` | 3通过；完整原页/实际HTTP链、A→B→A通知、目录变化拒绝 |
| `edge-v5` | 3通过；31邀请、历史ACCEPT、损坏回放键 |
| `prefix-v6` | 2通过；损坏首代目录hash／owner代际后新代读写拒绝，坏通知仍PENDING |
| `ui-snapshot` / `ui-snapshot-v2` | 各1通过的导出窗口；首份角色不符未采用，第二份真实reviewer公共DTO用于纯客户端Chrome场景 |
| `frozen-final` | 165唯一实际执行，163通过／1失败／2错误／0跳过；原连接/清理超时，完整窗未全绿 |
| `bounded-prefix` | 同冻结原顺序前49项一次有界诊断复验全通过，含新增32和两受影响节点；根因未确立，不替换首窗 |

最终冻结后不改产品/测试/CI源码。早期开发窗口不具备这一冻结承诺；所有失败保留，没有重写成通过。

## 尚缺的实际运行输入

普通业务路径必须已具备以下输入；本轮没有创建或恢复任何真实初态：

1. 已安装原业务schema的合法受限LOCAL数据库、已有合法会话和同园区/企业当前主体；企业owner具当前READ/PREPARE，写入另具EXECUTE，负责专员具READ/REVIEW_ASSIGNED，另一位当前active service_executor具同域READ。步骤分派本身不授予全Run访问。
2. 既有精确preparation→Case→成功case.create Run／VERIFIED operation关系、正确owner/reviewer及原 `preparation_catalog` 服务ID/版本/来源；原资料已确认且当前、P1/P2和业务fence满足。普通路径仍只接受原明确SYNTHETIC资料服务，不把fixture证明升级为真实来源。
3. 同一原dispatch的可证明DECLINE或接单前WITHDRAW，整段历史从未ACCEPT且没有任何receipt；首次最多300秒截止仍未到，资料/目录/负责人授权代际没有变化。过期、损坏、混合Native/legacy/隔离历史拒绝，不续期或删历史消除拒绝。
4. API与原worker均显式使用 `PARKWEAVE_MODE=LOCAL` 和 `PARKWEAVE_CASE_STEP_MODE=CURRENT_PREPARATION`，复用原受限连接配置；不得与Native、isolated provider、正式来源或独立demo配置混合。

正式来源成功接入仍缺专用backend与既有来源合同适配：来源域/ID/版本及获准脱敏只读结构，preparation/Case/Run/adopted-plan关系与当前head/revision/hash，原ADOPT决定及actor/状态/撤销，来源主体映射到已有本地主体及当前用途/字段权限/有效期/撤销，公开trust与签名覆盖/独立验真协议。还须实现并验证五证明接线，不能仅提供凭据或 `verified` 标签启用。Native permit/writer默认拒绝，IsolatedPlanApproval不用于普通批准。

Windows11原生安装/停启/关机/干净复现、正式AT逐项回执、真实主体/资料/业务、现实履约、真实模型和完整项目均未验。本片不部署、不改main、不新增费用或安全网络权限，不调用真实模型。后续按[剩余实质交付门](RemainingDeliveryGates-20261018.md)选择原方案允许的具体技术用例，复用已有成功实现和证据；正式来源、Windows和LIVE分别仅受各自缺项限制。
