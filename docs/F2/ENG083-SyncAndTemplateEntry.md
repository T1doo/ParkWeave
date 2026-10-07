# ENG083 精确同步与历史Case模板入口说明

精确 `797f426dc2f6274a973a82bb7909dc5d820b8f79` 已普通快进推送到原 `dev/f1-foundation`，推送后原origin远端查询核实相同SHA。本轮历史Case模板说明是其后的独立本地切片，尚未推送，也不在本次CI源码中。

## 指定6提交的整体核对与同步

区间 `381a20a…797f426` 严格线性6提交，独立只读审查无范围或权限阻断。差异仅为已说明的产品体验、浏览器验收、证据与来源绑定及测试合同对齐；生产路径为Web与计划当前资料版本投影。workflow、Windows原生脚本、权限/store/资料/Case生命周期实现字节均与区间基线相同，无owner、Grant、角色或动作范围扩张。

推送前原origin、默认代理和既有身份核验远端为 `381a20a72da7770927b1bd339f1859012b7e14f9`；最初默认沙箱的Git连接无法接通代理8080，通过本次用户已授权的命令访问执行相同Git只读流程后正常，无代理/身份/网络策略修改。推送前再次核实未变，一次普通push精确797f426，推送后远端再次核实精确797f426。无force、merge main、部署或附带推新切片。

在独立检出 `/workspace/ParkWeave-sync-797f426` 完整复验精确源码：**1454 PASS/0 FAIL/9原生Windows SKIP/2既有WARN，303.64秒**。当前产品开发在原工作树并行，未污染该测试版本；两次准备性运行因隔离版本/补接原已批准PowerShell缓存而主动停止，不作通过计数或Windows验收。最终隔离源码干净，原有ENG082真实浏览器证据5份源blob逐一匹配797f426。新切片不能借此宣称全仓1454复跑。

唯一push触发 [run37574021406](https://github.com/T1doo/ParkWeave/actions/runs/37574021406)，同797f426、attempt1、completed/success。job `112638772159` Server2025独立Job测量16秒，measurement步骤4秒，步骤均success；这是状态元数据，直接safe JSON及exact membership/signal/unrelated cleanup回执未获取。没有读取或重取日志、访问/上传产物、rerun、新权限、owner helper或恢复完整工程CI；Server不是Win11，不关闭原Windows工程/S4缺口。详见[同步证据](evidence/eng083-exact797-sync.json)。

## 独立本地产品切片

总设计§1.2要求看清当前阻塞和下一步，§5.5区分本地记录与实际履约，§5.6保留历史，阶段F2-T04/T07要求角色与真实入口一致。实际历史Case已有资源关联、内部分派与回执，但原NOT_STARTED计划投影只按EXECUTE授权返回 `can_create=true`，界面称“新事项入口”并提供启用按钮；服务端CREATE原本就拒绝这种历史Case。本轮没有尝试为保留Case创建模板。

现在 `controlled_plans.py` 在现有parent锁下共用原CREATE的三类存在前置，企业只读投影分别说明已有资源关联/分派/回执，另独立核查已有EXECUTE；满足“企业、当前执行权、无这些历史记录”才可启用。CREATE仍作原权威拒绝，不改幂等重放、模板/资料版本、已有记录或授权规则。专员和执行者不查询/显示企业详细启用原因，`creation_blockers=None`、`can_create=false`。

`web.html` 明确“此Case已有办理记录，未启用四步模板”，隐藏不可用启用入口，提供继续当前资料/资源关联、分派/回执的说明与既有同Case导航；独立新诉求从新资料事项开始，历史保留。未知原因固定中文回退。即使对隐藏按钮触发调用，前端也不发送已知不可用的CREATE；服务端当前权限/历史检查仍是最终依据，不自动补启用、删除记录、迁移旧资料或办理。

本轮相关回归 **109 PASS/0 FAIL/2既有WARN，59.93秒**。4个新增参数用例验证三类历史前置的GET与原CREATE409一致、计数不变，以及无历史可用事项与失去EXECUTE后的CREATE403；它们是隔离PG/API测试，不修改保留fixture权限，也不是实际用户撤权实测。

保留的两Case、三个真实角色、当前API/worker/PG/Chromium实际只读验收通过：三项历史原因清楚、不能启用、同Case资料/资源入口仍可用，收起/重进与迟到角色/Case读取不泄原因或覆盖新视图；已启用另一Case保留revision8/8事件。1200/390/320无横向溢出，root/独立审查实际看图。业务写请求0，16业务/授权表摘要与计划version/checked/events/observations全相同。新Case完整启用UI未行使，不冒称AT35/冷会话全链通过。自有API/worker与PG均正常停止并保留。

源码为 `src/parkweave/controlled_plans.py`、`src/parkweave/web.html`、`scripts/template_entry_browser_smoke.py` 与 `tests/test_controlled_plans.py`。本地复现 `.runtime/eng083-template-read-only-replay.py` 只读已有Case，不seed/migrate/assign。源码与6张实际PNG指纹、前后复现及独立结论见[产品证据](evidence/eng083-template-entry.json)。本轮最终本地commit只包含该切片与如实同步记录，尚未推送。

## 下一片与当前交付范围

当前可交付的是本地合成Case的具体阻塞/下一步、角色/版本连续导航和历史模板入口的准确前置说明。下一片选用已有合法企业/专员角色，从全新合成诉求建立新资料Case，验证“看见启用前置→用户明确启用→清楚待办理步骤”的实际冷入口，不新增Runassignment/Grant，也不自动推进四步或绕过P3已有执行者访问前置；尚未实施。

F1未签收/F2仅并行，R4关闭，模型调用/预算0；owner修改及日志拒绝路线限制保持。只有本次精确797推送和一次既有独立测量被执行，新切片后续push/CI未获本轮授权、未执行；完整Windows、Win11、真实资格判断、外部受理及线下履约未验收。
