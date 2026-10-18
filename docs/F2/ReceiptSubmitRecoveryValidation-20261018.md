# 普通人工回执原键恢复：冻结验证记录

基线 `d5f69a8fe9f0d8860c0325d46a035a7dbbb7f49f`；源码/测试/合同冻结 **`f7d47e704b07c1c0a9168535fbfdf41d7f77d5df`**，src 树 `6208c2d171acff6831ac7186b2d06f3993b91061`，tests 树 `023bb6380ceccd8c8ec75743862531ae326322e4`。开发分支 `dev/f2-receipt-submit-recovery-20261018`。本片属于原F2-T04/T05、AT18–20工程路径，项目整体仍未完成。

## 最终实际验证

**16完整相关模块，368唯一项PASS，0FAIL/ERROR/SKIP**；一个pytest进程每节点一次，无自动重跑；外层459.543727秒。755个src/tests/scripts/pyproject/原合成合同/本片合同输入PREPOST零漂移。新增89项已含其中；独立精确镜像89PASS全部逐ID与主JUnit重叠，不相加。不是全仓、正式AT或Windows验收。

| 完整模块 | 唯一PASS |
| --- | ---: |
| `test_assigned_demo_chain_browser` | 2 |
| `test_case_cancellation_offline` | 51 |
| `test_dispatch_accept_recovery` | 31 |
| `test_dispatch_accept_recovery_browser` | 5 |
| `test_dispatch_accept_recovery_offline` | 31 |
| `test_dispatch_recovery` | 46 |
| `test_executor_receipts` | 38 |
| `test_frontier_business_client` | 10 |
| `test_frontier_p4_race` | 1 |
| `test_pending_receipt_handoff_offline` | 9 |
| `test_receipt_submit_recovery` | 38 |
| `test_receipt_submit_recovery_browser` | 11 |
| `test_receipt_submit_recovery_frontier` | 1 |
| `test_receipt_submit_recovery_offline` | 39 |
| `test_resource_approval_host_browser` | 2 |
| `test_service_dispatches` | 53 |

[主调用](evidence/receipt-submit-recovery-20261018/runtime/final-v2-invocation.json)、[完整JUnit](evidence/receipt-submit-recovery-20261018/runtime/final-v2.xml)、[实际结算](evidence/receipt-submit-recovery-20261018/runtime/accepted-tests.json)、[独审](evidence/receipt-submit-recovery-20261018/runtime/independent-final-review.json)。

新增38项实际ASGI/自有PostgreSQL核COMMITTED/NOT_OBSERVED、归一化原Command fingerprint、精确actor/Case/Run/preparation/step/key/revision、当前READ/身份/assignment撤销、坏原子证据/正文SHA/版本序号、人工与本地生成排他、后续纠错/新版本/ACK及材料变版后的历史。正向case_history/authority快照不变；负例另外逐项核dispatch/receipt/notice记录，不冒称每个负例都比对全库所有表。

新增1项实际tracked-frontier自有PG从原SUBMIT再ACK推进epoch，随后GET原key仍按保存的历史frontier验fingerprint；该fixture含明确隔离批准，只用于测试原事务前置，未进入普通批准或真实来源。

新增39项Node VM执行实际窄生产函数，使用受控时钟/Promise/transport/renderer；覆盖坏/过期/未来/超容量/存储拒绝、COMMITTED/NOT_OBSERVED、迟到200/403、身份/Case ABA、内外层await、存储替换、坏当前history/receipt/role/executor/revision、renderer异常、草稿新编辑及UNKNOWN后恢复按钮。它们不是实际HTTP或浏览器。

新增11项实际Chromium→普通configured_app独立子进程→自有PG。6项含成功回包、已提交丢回复、未到达后测试人工投递原请求、当前撤READ、同端口API重启加页面冷启、真实GET后注入坏当前history；恢复区间页面request事件仅GET，不重发SUBMIT/ACK/P4，不新增Run，原历史/权限快照不变（明确撤权fixture除外）。实际320视口截图保留。页面request观察不含route.fetch和测试人工投递，不是全网络trace。

另外5项核确定拒绝：另一原客户端先提交后实际陈旧revision409；transport给原body加extra后由真实后端返回422；以及明确模拟的任意409/422/坏JSON422。前二保草稿/清句柄/清旧投影要求刷新，后三保持UNKNOWN、恢复GET可达且0额外POST。不会把故障注入响应冒称后端真实产生。

所有初态身份、目录、合法Run assignment、资料REVIEW/CONFIRM、已有回执步骤均由自有显式SYNTHETIC fixture在普通启动之前准备；普通工厂不补权。没有真实模型/来源/Grant/分派/批准/现实履约。

独测：同冻结755共享/镜像PREPOST零漂移，新合同SHA `2a1515676bf11a251b59ea36f835b49cf69b67ae5fba5483a48017062e6b629f`；实际pytest的89个parkweave模块全部来自mirror/src，字节匹配冻结输入。子API未额外插桩import origin；普通helper固定从镜像PYTHONPATH启动。89唯一项、无额外/重复/自动重试，pytest 150.05秒/外层152.003367秒，0个P1/P2阻断。observer与pytest退出，没有常驻观察器。

## 失败、漂移与修补

开发轮都在未提交工作树上，不能因runner记录当时HEAD为d5f就称其测试了d5f树；逐轮输入hash、调用、日志、XML保留，不将其成绩移到最终冻结。没有逐轮保存完整工作树源码快照。

| 开发窗口 | 原结果与边界 |
| --- | --- |
| dev-api-v1 | 38PASS、0输入漂移 |
| dev-offline-v1 | 97项92PASS/5FAIL：1处真实P2为raw替换后finally仍改旧提示；2处新fixture漏c.revision；2处旧renderer窄VM漏新增实际helper |
| dev-offline-v2 | 补实际依赖并修守卫后97PASS、0漂移 |
| dev-browser-v1 | 6PASS但4输入漂移，不计验收 |
| dev-frontier-v1 | 11项5PASS/6FAIL：实际PG新frontier例PASS；3旧dispatch Node模式classList stub缺失在未改d5f HTML实际复现；另3回执fixture缺新实际actor/step响应字段 |
| dev-regression-v1 | 修原DOM机制/完整响应fixture后138PASS，但新增browser测试文件使1输入漂移，不计验收 |
| dev-browser-v2 | 11项8PASS/3FAIL：独审发现的确定拒绝永久UNKNOWN P2已修；3个不确定响应反例实际暴露send finally用了plain h缺失的name/raw，原核对按钮未重新启用 |
| dev-browser-v3 | 修send局部name/raw后50PASS、0漂移；其中两新Node mode被编辑脚本误合并到旧late-context，不据此声称已覆盖新行为 |
| dev-offline-v4 | 独审指出两Node覆盖缺口后，待上轮自然结束才精确拆分reject+按钮及换raw+newstatus，完整39PASS、0漂移；随后冻结并重新跑最终16模块 |

首个同冻结16模块窗口 `final` 实际368项367PASS/1 setupERROR、755输入零漂移；唯一旧 `test_frontier_p4_race` 在autouse导入核验因调用遗漏 `FRONTIER_TEST_SOURCE_ROOT` 抛KeyError，未进入业务。[首窗口原JUnit](evidence/receipt-submit-recovery-20261018/runtime/final.xml)保持原状。核读原harness合同后仅补runner的真实src目录、冻结hash manifest及独有oracle输出根；定向实际并发用例通过后，以同一源码/测试冻结重跑完整16模块 `final-v2`。未改源码、测试、原导入断言或业务门；诊断与首窗367项不加到最终成绩。

三处产品P2均已修并经冻结独审：raw替换迟到收尾、精确确定拒绝可结束未知、UNKNOWN当页核对按钮恢复。原helper对确定拒绝的精确范围没有扩大；任意状态或解析错误仍未知。原失败与开发分数没有重写为最终通过，旧交付190项与更早575P1F等历史成绩不移签或累加。

## 证据与剩余范围

本片公开505对raw/public证据映射，合计2处临时合成会话候选脱敏；raw原件保留本机.runtime。实际校验SHA/字节长度、严格JSON/JSONL/XML、PNG CRC/解压，所有1313个JUnit testcase标识不变；JSON键和JUnit ID不脱敏，源码AST/路径可证标识豁免。见[manifest](evidence/receipt-submit-recovery-20261018/manifest.json)与[结构校验](evidence/receipt-submit-recovery-20261018/archive-validation.json)。私有fixture bootstrap/tokens不导出，现有私有原件保留；PGdata不导出，沿原自有fixture清理机制，不称其完整原件归档；既有证据保全在最终本地交付核验另查实际Git blob字节，推送与远端回执另存.runtime，避免自引用。

[产品/协议及可转发来源最小字段](ReceiptSubmitRecovery-20261018.md)是单独冻结合同，本验证文件与计划更新不改变源码/测试/脚本/合同树。localStorage比较删除不是跨进程数据库级原子CAS；本轮覆盖异步等待期间替换，保留该平台限制。

正式来源backend/主体/采纳映射仍待来源方现有结构、合法主体关系、原决定和公开验真/current-head/撤销定义，并需项目按该合同写专用适配器；不是只缺凭据。formal五证明继续UNAVAILABLE，NativeRunAccess permit/writer默认拒绝，IsolatedPlanApproval不作普通批准，资源批准读取仍不可消费。

普通人工路径仍需原受限DB/迁移schema、当前有效会话/READ、本人精确Run assignment、原合法PREPARE/REVIEW_ASSIGNED和精确preparation_catalog、当前资料/接单回执前置；资料准备/写入等前置继续沿原PREPARE/REVIEW_ASSIGNED及catalog门；本片历史元数据GET本身按当前READ和本人精确assignment判权，不冒称额外核过所有旧前置授权。缺项由各原入口准确拒绝。没有创建真实身份/Grant/分派/目录发布/批准/凭据。未改main、强推、部署、新费用、安全网络权限或调用真实模型；未知锁保留。Windows/Win11原生、正式AT/AT35、生产不同UID受保护安装、真实主体/资料/业务/模型/现实履约均未验。
