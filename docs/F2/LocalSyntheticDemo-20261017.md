# LOCAL_SYNTHETIC_DEMO 普通启动最小切片

2026-10-18 后续：已有目录选择可通过新增显式 `LOCAL_DEMO_CURRENT_PREPARATION` 接普通 CaseStep 与冷恢复，见[组合合同](LocalDemoCaseStepChainContract-20261018.md)。该模式不需要也不接受 Run assignment；下文保留原切片验证历史，其中原全链的单行测试分派不用于新组合模式。原单独 demo 与 CURRENT_PREPARATION 入口语义均保留。

已接入默认关闭的 `LOCAL_SYNTHETIC_DEMO`，在普通 `configured_app` 上读取已存在的、精确绑定的合成输入和当前授权，复用原 V4 选择算法、原显式 ADOPT 与 P1–P5。没有真实模型、权限补建或正式批准。

代码冻结：`8ae2892fe56465fbf53e23ae2010258ce7881b47`。基础：`e7cf6cabea6174a672667d7ae8af6a5238589791`，其原始祖先含 `db1084100a2477bbff3da8b49287c755dbc83c1b`。本轮 source 4 个提交（实现、EOF 规范化、两处旧 DOM 测试夹具补 `classList`）。后续交付只增加说明和证据。

原方案允许明示合成测试目录与自建样例：[原开发计划](<../sources/V1/分阶段开发计划 (2).md>)、[原产品设计](<../sources/V1/平台产品设计 (2).md>)。本片没有把历史 review_demo 证据索引当作可运行来源。

## 实现边界

- 独立精确 `LocalSyntheticDemo / LocalDemoCatalog / LocalDemoSelector` 和版本化包/journal 合同；默认关闭，未知 profile、真实源、错库/角色/园区、失效 Grant、来源变化均拒绝。
- 预存在的 pack/journal 原始文件哈希、实际数据库 name/OID/address/port/user、原 SYNTHETIC preparation_catalog 内容哈希/xmin 绑定。普通 schema 32 先已安装；journal 私有；文件先检查 regular/size 再有界读取。
- 合同由既有有限注册表编译，不伪造 source_review、TemplateEngine 发布或旧模型 wire；唯一解才生成 NO_MODEL 候选，多解无自动选择。保存冻结注册表，原接受时历史证明独立于当前注册变化。
- 旧 `service_selection_candidates.py` 整文件与基础提交逐字节一致；旧 Isolated 类型门保留；共享的只是原穷举/图重建和原身份/资源授权检查。
- 启动不执行 migrate、seed、身份/Grant/分派/目录发布/批准/凭据创建。NativeRunAccess permit/writer 默认拒绝不变。未接入新的 cold-input 向导或原 schema33 扩展演示。

## 验证

最终冻结：12 个完整相关模块 **317 唯一 PASS，0 FAIL / ERROR / SKIP**（新增27含内），JUnit 497.920 秒；735项 tracked 源码/测试/脚本/合同输入前后零漂移。以 `final-validation.json`、`final-result.json`、JUnit 与独审记录为准，不累加开发轮次、重复传输探针或先前267例。

| 完整相关模块 | 唯一用例 |
|---|---:|
| local_synthetic_demo | 26 |
| local_synthetic_demo_browser | 1 |
| service_selection | 38 |
| service_capability_contract | 56 |
| service_selection_candidates | 23 |
| service_selection_web | 43 |
| service_selection_nodevm_actual | 2 |
| service_selection_full_chain | 6 |
| service_selection_source_safe | 1 |
| service_capability_catalog_actual | 39 |
| service_plan_candidates | 66 |
| native_preparation_entry | 16 |
| 合计（新增27含内） | 317 |

新增 API 用例使用显式隔离合成初态，通过普通 factory 完成新 Run/preparation/两槽材料、人工 REVIEW/CONFIRM、NO_MODEL 选择、显式采用、原资源关联/接单/回执/确认/本地重验和 P1–P5 VERIFY；读取六个 LOCAL_OUTPUT_VERIFIED，重建 factory 后结果一致。精确 Run assignment 是测试在加载器外另加的一行；startup/runtime authority 变化均为零。缺 assignment 的原 dispatch 仍拒绝。

真实 Chromium 经过独立 uvicorn `parkweave.api:configured_app --factory` 进程做目录读取、NO_MODEL 候选、GET 原 key、显式确认采用和冻结来源显示；1200/390/320 宽度和重启后 GET-only 读取。浏览器初始材料由原 API 准备；此浏览器测试不声称做完同一条 P1–P5 全链，完整原业务链是另外的 API 验证。

保留的失败：开发 v1 10P/9F（SELECT-only catalog 不能 FOR SHARE，未增权，去掉该要求并保留前后绑定核对）；开发 v2 18P/1F（办完后旧选择的失配异常未映射历史不可用）；开发 v3 单全链通过；开发 v4 121 唯一 PASS。首个冻结 harness 139P/1F/177E：177 为 PG fixture 创建证明要求 `/tmp` 而 runner 误放工作区；privacy 单例为既有 fake DOM 缺 classList，已在基础 HTML+原 harness 内存复现，补测试夹具。baseline 探针首次误用系统 Python 缺 pytest，未执行 Node，改仓库 Python 后复现。另有 source commit 前 diff-check EOF 告警，后续独立格式提交已清除。第二冻结窗296P/21F，21均因私有cwd无旧Node相对源码路径而未启动脚本、API请求0；补路径的小窗normal通过、trace_revoke因同类旧classList缺口失败，该缺口亦在e7原HTML+原legacy夹具内存复现。随后只补测试夹具并修runner源码路径，产品源码自8551未变。全部失败日志、两次基线复现与清单均保留。


另以同一冻结产品代码、已提交全链断言和单独HTTP客户端适配探针，通过**三个独立普通factory进程**完成实际HTTP全链、重启只读及当前PREPARE撤销后403。单列1PASS（JUnit 31.338秒），不加到317，不将同一断言重复计算。API进程自行从env读取配置/Store，不接收父进程provider对象；原Approval/access状态关闭。精确Run分派一行和随后PREPARE撤销均为加载器外的显式测试操作，业务请求不创建权限。探针脚本、原HTTP响应哈希/状态及子进程日志保全。

## 真实运行仍需输入

1. 已授权应用 PostgreSQL DSN、当前已安装普通 schema32、正确 park/org 的原 SYNTHETIC preparation_catalog 内容及 generation。
2. 已存在且有效的三种身份、当前会话和原 READ/PREPARE/REVIEW_ASSIGNED/EXECUTE 权限；不提供或生成真实凭据。
3. 已存在的两项 SYNTHETIC 资源及原资源 READ/HOLD 等业务要求；严格批准路径仍须其原合法 Approval 输入，demo 不代替批准。
4. 包的版本/有效期/服务种类、精确园区角色/资源/字段映射、绝对 pack 路径和 SHA256、独立私有 journal 路径及 SHA256、数据库/目录绑定 JSON。
5. 原 preparation（或用户经普通 API 建立记录并补齐两槽及 REVIEW/CONFIRM）和 P3 所需该精确 Run 的原 executor assignment。

全部项目尚未完成；没有零准备一键全新办理、真实园区/正式业务接入、正式 AT 或 Windows 验证。未改 main、未强推、未部署、无费用/网络安全权限新增，无真实模型调用，原未知锁保留。

## 独审、证据与交付

独立只读审查0剩余阻断。A2/B是内存Python/Node探针，不是实际DB/API/浏览器，不加回归数；旧、新oracle 11组及3组图重建一致，NO_MODEL篡改与冻结/采用证明、前端精确profile核对通过。之后只补legacy DOM夹具，产品源码零变化，增量独审及735项输入仍零漂移。helper命令经无损解压并核原SHA，stdout按helper消息转录，明确不称根raw。首次大WIRE工具截断、废弃POST编码与辅助hash误转换已记明。

公开证据：[manifest](evidence/local-synthetic-demo-20261017/manifest.json)、[最终317项JUnit](evidence/local-synthetic-demo-20261017/runtime/final-pytest.xml)、[冻结结果](evidence/local-synthetic-demo-20261017/runtime/final-result.json)、[实际HTTP跨进程结果](evidence/local-synthetic-demo-20261017/runtime/ordinary-http-result.json)、[独审](evidence/local-synthetic-demo-20261017/runtime/independent-review.json)。共131对raw/public映射逐项复核：88个JSON、9个XML、3个PNG，临时会话脱敏0处。私有原件保留于`.runtime/local-synthetic-demo`及记录中的自有tmp目录；未打包PG数据或凭据。继承28799个F2证据Git blob零漂移。

交付分支：`dev/f2-local-synthetic-demo-20261017`。正常推送的实际完整SHA、本地/远端差异和main核验以本次最终回执及私有`delivery-verification.json`为准，未部署。

源码/测试/合同及本次说明的diff-check通过；完整交付diff-check仅原样证据中的1272处空白告警，未修剪原始日志。后置交付校验metadata不计131对映射。首个交付检查器曾误把日志内的file:line文本当成diff告警位置，已校正并保留该失败，提交前重新通过。
