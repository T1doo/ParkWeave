# AT28 当前资源预检来源披露：有限交付

本片关闭一个实际产品缺口：目录读取后来源换版，原预检已按当前登记版本计算容量，却没有返回/显示该次计算所用的来源。现在原资源工作区分列目录观察和本次预检来源，显示当前资源名/版本、来源 kind/id/revision/statement、本地 authority 范围和本次数据库观察时刻；缺失/无效元数据不保存可操作预检，不启用占位，也不留下上次成功来源冒充新观察。外部资源可用性始终 UNKNOWN，仍需来源方确认；本地占位和确认继续由原入口明确执行。不是完整 AT28 或真实预约交付。

基线 `4c1aa1005d3e81dce5a240b3a9056627ff527f1b`；先行合同 `48fd48f0dc8f39c60d32f25f8800cfd5a8f66f05`；最终受测源码 `555edeacd7720b34e9055a1fecdbfef1ef13dbe0`。见[最小合同](AT28CurrentResourceObservationContract-20261018.md)。独立 source-blind 先审冻结 8 条字面 oracle，SHA256 `68a815972db60d1362b6e67b7e141dd52411febbabb9cfe45313ecfbe87e10c5`，确认本片是原固定 oracle 的真正增量，未先读新实现。

选项依据：[RemainingDeliveryGates](RemainingDeliveryGates-20261018.md)、固定 AT22–29/33、[AT22/23 回执](AT22AT23FiniteValidation-20261018.md)、[AT24–27 变化批](AT24-27ChangeBatch-20261015.md)、[事实历史对照](FactHistoryComparison-20261016.md)及[第二范围首次办理](OrdinarySyntheticScopesValidation-20261018.md)已有各自工程证据，未当新覆盖重跑。第二园区固定冷输入不冒称 AT33 全部配置迁移；本片未再运行其 P1–P5。合法停表仍缺既有有权主体/独立决定、适用来源/日历/版本、原始事件/当前 head、Case 时钟修订/有效时段/撤销与幂等回执合同，故本轮没有实现该写入、编造 SLA 或暂停权。这些缺项不阻塞本片的原本地资源观察披露。

后端只在原 `resource_holds.preview` 返回值中增加原资源锁后 `_scope` 同一行的 `resource_name/source/authority/timezone` 与固定 `external_availability=UNKNOWN/confirmation_required=true`。原 `resource_id/resource_revision/server_time` 和窗口、缓冲、峰值、可用量计算保持。`server_time` 是本次数据库观察时间，不是源更新时间、上游刷新时间或后续容量保证。没有新增 endpoint、schema、权限、发布、pin、journal 或算法，未增加真实来源/身份/Grant/分派/批准/凭据。`LOCAL_AUTHORITY` 只对原本地合成账本有效。

前端复用原 generation/token/resource/window 守卫，先核响应元数据，再保存 `resourcePreview` 并允许原明确 HOLD。文本按 textContent 显示，旧目录不自动换版。原 HOLD `expected_revision`、锁后时间、授权、确认、回执及恢复算法不变；原 template/CURRENT/provider/Native 默认拒绝保持。只为一个原 offline 响应替身补齐新元数据，不改变其断言或原流程。ATBindings 仅将 AT28 工程定位指向新增两个测试函数并说明有限范围；42 项 whole_status 与固定验收规格保持 NOT_RUN，未运行已知来源门拒绝的通用 whole-AT runner。

最终冻结窗 **7 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，JUnit 17.609 秒，外层 20.379323169996496 秒。collection、JUnit 和 setup/call/teardown 对应；821 份输入的 shared-before/mirror-before/shared-after/mirror-after 完全一致，93 个实际相关模块均来自冻结镜像、哈希相符。API 子进程使用同一冻结镜像和原普通 configured_app 启动路径，未另装逐模块导入探针，不能扩称子进程全面 import 审计。

| 实际节点 | 结果与范围 |
| --- | --- |
| 新 API/PG 1 项 | 读原目录 v1，再在本次自有原资源 fixture 将登记/source 推进 v2、容量改为字面 3，原 preview 返回同一当前行的 source/name/revision=2/authority/timezone，peak=0/available_quantity=3/available=true。外部 UNKNOWN、须确认及原未预约/未受理/无履约边界保持；所列 6 组业务表与授权快照不变。 |
| 新完整 HTML/NodeVM/实际 HTTP 3 项 | 原普通 API 进程上，先显示目录 v1，明确预检后显示实际来源 v2/观察时间；没有自动 HOLD/CONFIRM。正向仅本人明确提交后得到原 HELD，再独立点击原 CONFIRM 得本地 CONFIRMED，真实预约仍未确认。两个负例先取得有效预检，再使新响应缺 source 或观察时间无效，原成功文字清空、cache=null/HOLD 禁用、0 业务写请求。NodeVM 是机械 DOM 替身，不是浏览器。 |
| 必要兼容/静态 3 项 | 原匿名容量/跨企业信息隔离节点验证新增 source 不泄漏其他企业占位；原 offline 建议→明确 HOLD/CONFIRM 节点核响应形状兼容；原固定绑定完整/唯一/安全静态节点核 AT28 定位及状态。均因本次返回值或绑定变更而定向选择，未复跑完整旧矩阵。 |

实际状态副作用分列：catalog 和 preview 不写所列业务表；新 preview 路径使用 POST 表达只读计算，不能把 POST 计数都称业务写。正向页面恰有 1 次本人明确 HOLD 与 1 次本人明确 CONFIRM，保存 1 占位/2 原回执，0 Run/Case/model_step；两个无效观察场景均为 0 占位/回执。fixture 初始化和来源 v2 推进明确属于自有合成初态/变化，不是 GET-only 或真实目录发布。授权表不变；拒绝的原审计行为不被泛称全数据库零写。

开发与历史分窗保全：首开发窗 5 PASS/1 FAIL，JUnit 15.65 秒；产品已验证元数据但显示字符串仍接旧 suffix，来源 ID 显示断言在新的正向 HOLD/CONFIRM 前失败。修显示接线后定向正向与原静态 2 PASS，JUnit 7.67 秒。最初冻结 `b379a61fe2fb17adde5de7a6f346f02db93505ee` 为 7 PASS；静审提示错误时旧成功文字仍可留在结果区，随后 555 仅增加开始新预检时同步清空显示，并将同两个负例收紧为先有效后无效，节点数不增加。上述均不叠加为最终 7 的额外覆盖。原日志/XML/调用保留，失败会话字典只在公开副本脱敏，不覆盖原件。

本轮独审仅明确 Git SHA 的静态审查与字节/AST核对；独立动态测试为 **0**，不把根 7 PASS 改签为独立动态 PASS。前片 `4c1aa100` 的最终独立动态 0、历史独立 5 PASS/1 FAIL、平台风险标记窗口与两项修补分别保留，未重试该受阻窗口或绕过拒绝。本轮静态证据控制器两次 matcher 断言失败，涉及原 catalog 业务 handler 与页末异步包装 handler 的机械定位；最终改为精确 body 起点匹配。未执行产品 import/DB/HTTP/测试，脚本、差异、错误和归因保留，不算产品用例或动态复测。

真实外部资源状态、正式来源和确认/预约履约、正式 AT28、真实浏览器、Windows、真实业务与模型均未验；未部署或修改 main。首双范围开发 HTTP 超时仍为 **UNKNOWN**，不因本片通过关闭。完整项目与 AT22–29/33 总体仍未完成。


独立最终静态结论为有限通过、无开放 P1/P2。去除仅 6 个新增返回 keyword 后原资源模块 AST 全等；186 个 src 中另 184 个逐字节相同。原 801 code 中 798 相同，另 3 处变化为 resource/web/旧 offline 响应替身，另新增两个测试文件。原页面去除新 helper 并还原两个业务 handler 后字节相同；权限、锁、数据库时钟、窗口、峰值、HOLD expected_revision、模板、roles/schema 和脚本守卫保持。静态报告 SHA256 `f01d0e8dd0d447279e6df99421797e7247c58d1429ef6f8371dbe47e1ade4fcf`，独立动态仍为 0。

证据：[最终根窗及精确节点](evidence/at28-resource-observation-20261018/runtime/root-verification-555edeac.json)、[独立静态结论](evidence/at28-resource-observation-20261018/independent/independent-final-review.json)、[原文 oracle](evidence/at28-resource-observation-20261018/independent/literal-oracle-plan.json)、[公开清单](evidence/at28-resource-observation-20261018/publication-files.json)、[原件/公开件映射](evidence/at28-resource-observation-20261018/raw-public-redaction-map.json)。109 个公开文件、106 组配对，104 组逐字节一致，2 个开发失败文件各脱敏 1 处会话字典；31 个已登记自有会话值及 16 字符前缀扫描零命中，XML 原用例与失败结果形状保持。独立 27 个 canonical 按原 hash 直接复制、未二次脱敏，私有 registry/PG data/配置不发布。根封存脚本首次误读独立静态映射的字段名，在公开目录创建前 KeyError；保留原错误，改按该映射实际 entries 字段读取，原 canonical 不改。此归档控制器错误不算业务测试，也不覆盖此前任何失败。
