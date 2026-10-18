# 普通 P5 本地记录重验、关闭与重开验证

普通模式已接通原用户流程：P1–P4 明确核验 → 原本地记录重新校验 → 明确关闭本地记录 → 原 P5 VERIFY → 原目标结果和 TXT 核对包。关闭仍为 `LOCAL_RECORD_CLOSED` / Case `WAITING_CONFIRMATION`，`case_goal_completed=false`，不证明线下履约。本片仅验证 LOCAL / SYNTHETIC；完整项目尚未完成。

- 受测提交：`0d45e3c60ed62f40df242b462475a51d58c57cd7`。
- 受测 tree：`259ac36d83ef2d98fa33b4826822bff81e3664a3`。
- 接续基线：`1f7e4d4a11606a511062fecb1863803209f3831d`；原 `db1084100a2477bbff3da8b49287c755dbc83c1b`、前片受测/交付及远端 main 均实际核为祖先。
- 开发分支：`dev/f2-ordinary-case-record-recheck-20261018`。最终文档交付 SHA、推送结果和远端差异见最终返回及 `.runtime/ordinary-case-record-recheck-20261018/delivery-and-remote-verification.json`；受测 SHA 与文档交付 SHA 分列。
- [本片合同](OrdinaryCaseRecordRecheckContract-20261018.md)。此前39个有效节点属于已接收的 P3/P4 历史验收，不整包重跑或转计。

## 原文与具体实现

产品设计 §5.5（`docs/sources/V1/平台产品设计 (2).md`，175–179行）要求本人步骤、材料/预约/接单/凭据核验及本地记录与线下履约分开；分阶段计划 F2-T07 / AT-15（`docs/sources/V1/分阶段开发计划 (2).md`，90/98/287行）要求持久化、正确角色、无证据不关闭及重开保留历史。原生命周期、P5、恢复和核对包算法均已存在；原断点是普通 marker 被生命周期入口拒绝，P5 来源仍依赖旧 Run assignment。

`ordinary_plan_sources.parent` 传递原 write 锁语义；`case_lifecycle` 在显式同 Store 普通依赖下复用原权限、事务和来源检查，绑定现有 CaseStep/人工回执证明，复用原 REVALIDATE/CLOSE 请求指纹检查当前账本与事件。`service_case_steps` 的实际 P5 分支调用这些原检查，并将资源时效检查放在原账本锁之后；普通事务在后续等待结束后再次检查步骤/资源时效。没有新增状态机、schema 或批准协议。

原独立生命周期无需采用计划仍可办理；存在计划时仍走原 through4 前置。READY 仍可显式 VERIFY P5；本片正向流程验证关闭后 VERIFY。一个周期可因真实回执更正再次 REVALIDATE。REOPEN 保留原事件并开启下一周期，不重发邀请、续期、重授、释放资源或自动核验。原 REOPEN 被忽略的 optional SHA 无法从旧事件完整重建，保留原结构证明限制，不声称新增签名或防可信管理员重写数据库。

owner 当前 READ/PREPARE 与写入 EXECUTE 分开；撤 EXECUTE 后原 POST 重放也禁止。恢复读取仍要求历史及当前资源 READ；撤资源 READ 后普通历史页可按原接口显示失效检查，原恢复则拒绝。reviewer 仅原最小状态；执行者无全 Case/P5/计划/Run 权限。默认路径、Native 污染、active/inactive Run assignment、隔离 provider/marker 不回退采纳。

## 实际测试与失败

| 窗口 | 实际结果 | pytest / 外层秒 | 计数解释 |
| --- | --- | --- | --- |
| 开发首条 | 1 PASS | 19.71 / 未单列 | 未冻结，不转计 |
| 开发 full-v1 | 17 PASS / 1 FAIL | 242.32 / 未单列 | actor 损坏后的原键应为 NOT_OBSERVED，测试误期望409 |
| 开发 actor-scope-v2 | 1 PASS | 13.18 / 未单列 | 仅修断言；另以完好原键验证损坏当前账本409 |
| 开发 extra-v1 | 10 PASS | 239.81 / shell退出码未观察 | XML/终端总结已完整落盘；通道恢复后无活跃测试，没有重启 |
| 冻结根主窗 | **35 PASS / 1 FAIL** | 566.006 / 570.519388 | 36节点；一个等待测试的准备前提未满足 |
| 同 SHA 原样补充 | **1 PASS** | 38.070 / 41.401203 | 仅原失败 selector，一次补充，无源码/测试/权限/窗口时长变化 |
| 独立审查窗 | **9 PASS** | 244.670756 / 246.918880 | 6个自有复合节点及3个根重叠，全部 setup/call/teardown/JUnit 通过 |

根主窗失败项为 `test_actual_final_pg_wait_rechecks_step_and_resource_and_rolls_back[resource_end-VERIFY_P5]`。原资源结束于 `19:10:59.972152 UTC`，原 POST 到 `19:11:11.127532 UTC` 才开始，已经晚11.155380秒；接口于 `19:11:11.567664` 正确返回409，未进入最终 view、未观察到 PG 等待，未完成该调用的回滚断言。准备延迟致因保留 UNKNOWN，不能把它算作等待成功或产品回归。

唯一补充保持同一源码/脚本、原28秒资源窗口、原3秒 lock_timeout 和请求逻辑：资源结束于 `19:14:43.204168`，实际 PG 等待剩余 `0.961306s`，POST 于 `19:14:43.445861` 返回403；计划修订、账本/事件计数未变，后续读取不判当前有效。失败原件与补充原件分开保留，不称根单窗36 PASS。

最终根有效集合36（28个新根节点、8个定向回归，含旧 P5 范围断言更新）；独审9，实际交集3，**并集42个唯一节点通过**。83条 DOM 断言不是83个测试节点。P1/P2-only 不继承无关步骤期限在本片为静态核对并承接前片，未另计新动态测试；也未重做完整并发组合矩阵。

独审额外观察了真正的原 `case_local_lifecycles ... FOR SHARE` / transactionid 等待：`19:09:23.572474` 时资源剩余 `0.834877s`，资源于 `19:09:24.418903` 结束，HTTP 于 `19:09:24.679089` 返回403；步骤原期限仍到 `19:13:43.512301`。业务全表摘要及原1条账本/2条事件不变，未偏移应用时钟。这证明资源过期而非步骤先过期。末次准入检查不声称物理 COMMIT 瞬间检查或全来源全局原子快照。

独审结论 LIMITED_PASS，开放的 P1/P2 级问题均为0。另独验了无采用计划的原生命周期、同周期多次校验、原键历史/冷恢复、owner EXECUTE 与代际 ABA 分离、REOPEN 不续授、原 reason/跨 Case 快照损坏及角色/默认依赖边界。

## 实际普通进程、页面与冻结一致性

根主窗启动3个实际普通 `configured_app` API 进程，health PID 分别匹配实际 PID，最终观察各自退出码 -15；本片页面链新 worker 进程为0。完整原 HTML 在 Node VM 中执行原按钮，三个阶段为关闭后37、冷启动后19、重开后27条 DOM 断言；实际 HTTP calls 为27/17/22。冷轮全部 GET。生成/下载沿原每次两次新 GET，不写业务记录。

关闭与冷启动所得 TXT **14,482 bytes 完全一致**；整文件 SHA256 `7dabffa432d751ad0c7140b97fb49433c8de8e6672425dfe71e66258a24f03bc`，规范数据 SHA256 `b8edf6a0a2cc3aeaf22008e6fec820a3d8bcf1f5c11e8098509756820f4aeb22`。重开后保留原 P5 核验 ID，current=false、actual_output=null，核对包为 UNVERIFIED。该链未创建 Run assignment 或改变身份/Grant。

三窗12份共享/镜像 PRE/POST 映射均为同807个源码、测试、配置输入，零漂移，Git archive SHA256 同为 `add5984e946405535e04f4a1b011a0db279ec20eb0c6a076a8f523d8a3bd3b46`。根主窗117、补充窗114个实际 pytest 项目模块来源全部逐文件匹配冻结输入；独审117来源为116个冻结文件及1个私有探针。API 子进程验证固定 mirror cwd/PYTHONPATH、普通 factory 和 health PID，未单独挂子进程 import-origin hook。

59个保护文件与基线字节相同，包括 Native、roles/schema、CaseStep、固定计划/编译/目标结果模块、原 HTML、preparation、store、worker、conftest 和 AT 绑定。7个原生命周期定义及抽出的原恢复证明块 AST 一致。原文两份 Git blob 另行记录。旧 F2 证据无 tracked 差异，不宣称重新全量扫描旧证据。

补充控制器的 `nodevm_full_html:true` 是继承的固定标签，**补充实际仅执行1个 HTTP/PG selector，没有 Node VM 或普通 API 子进程**；已单独记录纠偏而不改原 result。开发通道断连后核对了实际 HEAD、11个落盘文件哈希、在途及远端；失联旧 shell 退出码未观察，不以XML替代该退出码。私有控制器 dict/list 诊断、独审原文路径误写和 proof 别名对账失败/修订均保留，不归为业务测试失败，也没有触发业务重跑。

## 证据

新目录 [evidence/ordinary-case-record-recheck-20261018](evidence/ordinary-case-record-recheck-20261018) 共191文件：188个 raw/public 对，184个字节相同、4个仅会话脱敏影子，共4次替换；另3个控制文件。460个已知自有合成 fixture 会话值的全文/16位前缀及已捕获片段扫描均0命中，结构文件/XML均解析且原测试结果保留。独审71份 canonical 全部直接逐字节复制，未二次脱敏。所有私有原件保留在 `.runtime/ordinary-case-record-recheck-20261018/`。

代码/合同及本报告空白检查通过；暂存证据有12处原 patch/失败日志/XML/终端原件空白提示，按原字节保留，不为消除提示改写证据。

- [实际节点集合与交并计数](evidence/ordinary-case-record-recheck-20261018/runtime/effective-test-accounting.json)
- [冻结输入、来源、两根窗口及等待证明](evidence/ordinary-case-record-recheck-20261018/runtime/frozen-window-source-and-outcome-verification.json)
- [根主窗原始 JUnit](evidence/ordinary-case-record-recheck-20261018/runtime/frozen-0d45e3c/results.xml)；[唯一补充 JUnit](evidence/ordinary-case-record-recheck-20261018/runtime/frozen-0d45e3c-resource-recheck-window2/results.xml)
- [原页面下载 TXT](evidence/ordinary-case-record-recheck-20261018/runtime/frozen-0d45e3c/process-artifacts/test_original_html_p5_close_ve0/closed-html/download.txt)
- [独审完整报告](evidence/ordinary-case-record-recheck-20261018/independent/independent-final-review.json)，SHA256 `fd48ad2525bef09522c9eaf328f45635db5a8fef2d6b9a5063e711fedeea9bf5`
- [独审71路径清单](evidence/ordinary-case-record-recheck-20261018/independent/publication-files.json)，SHA256 `c9a5fb72ab36d6c1b0a282d7de1770d2aff45eb7c287e0647a35cffb116e0c6e`
- [独审 raw/public 映射](evidence/ordinary-case-record-recheck-20261018/independent/raw-public-redaction-map.json)，SHA256 `10f4bddcded5a6a14e3b64d4f07e11a62a641a35217b67fc257ba7883236eb5e`
- [完整归档映射](evidence/ordinary-case-record-recheck-20261018/raw-public-redaction-map.json)；[归档核验](evidence/ordinary-case-record-recheck-20261018/archive-validation.json)

## 普通运行仍需的输入与未完成项

| 输入 | 当前要求与缺口 |
| --- | --- |
| 既有数据库/启动配置 | 已安装 schema32/33 的受限 LOCAL Store；已有 `PARKWEAVE_DSN`，API/worker显式 `PARKWEAVE_MODE=LOCAL`、`PARKWEAVE_CASE_STEP_MODE=CURRENT_PREPARATION`，API使用原 `parkweave.api:configured_app --factory`。本片未执行真实安装或配置初始化。 |
| 既有合法身份/会话/权限 | 同园区企业的原owner、指定reviewer及既有executor；owner READ/PREPARE，写入另需EXECUTE；reviewer READ/REVIEW_ASSIGNED；executor READ及原业务要求的当前权限/代际。没有合法输入准确拒绝，测试身份与Grant不能拿来充当真实授权。 |
| 精确原资料与目录 | 原 SYNTHETIC preparation/Case/成功case.create Run及VERIFIED operation；精确 service_id/version/current preparation_catalog，原材料/字段权限、人工核对和确认。不得有任何active/inactive Run assignment、Native污染或隔离provider。正式真实来源尚未准入。 |
| 当前业务来源 | 采用计划的路径须原P1–P4及其前置核验；原本人ACCEPT、人工SUBMIT/owner ACK及完整指纹/绑定证明，首次邀请UUID及原不超过300秒期限仍有效。重启/重开不能补授或延长。 |
| 当前资源来源 | 本人原CONFIRMED组合、Case link/claim、资源READ/HOLD、规则版本/容量及实际窗口均有效；恢复另核历史/current资源READ。此为本地资源记录，不证明线下预约履约。 |
| 真实初始化 | CLI企业合成初态与测试setup不是真实管理初始化；真实主体映射、获授权管理目标清单及配置/初始化流程仍缺。未新增真实身份、Grant、分派、目录发布、批准或凭据，未把 IsolatedPlanApproval fixture 用于普通批准。 |

Linux owned PG/API/原 HTML Node VM 的合成验证不能代替真实业务。真实浏览器、Windows原生场景、正式AT35及真实安装/批准/writer运行均 NOT_RUN；原 Native 拒绝保持，不绕过。本片未改 main、强推、部署、调用真实模型或新增费用/安全网络权限。远端基线130个分支头、main `31e7acb7e53bb1ab6465b9daae59de28757f7583`，恢复后均未变化；最终正常开发分支推送另有实际回执，默认 main-only fetch 不改。
