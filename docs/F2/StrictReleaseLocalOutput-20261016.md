# 新 strict Release 新事项的 P3–P5 页面验证

基线交付 `64f6068ef5bde98d2586835670be51bef178e616`，最终冻结 **`7b6315f3ed737264464957ad5aa37c80c251cc87`**，分支 `dev/f3-strict-release-local-output-20261016`。本批仅新增三个测试/支持文件；所有 src 与基线 Git blob 逐字一致，没有新增、替换或放宽业务入口。原 §7.5、六目标、P1–P5 与隔离版本边界保持。

## 实际页面链路

真实 Linux Chromium、原 HTML、loopback HTTP/ASGI 和自有 PostgreSQL，从当前 P1/P2 VERIFIED 初态执行九个原 DOM POST：专员 OFFER→获派执行者本人 ACCEPT→owner VERIFY P3→执行者手动 SUBMIT 合成回执→owner ACKNOWLEDGE 当前 hash→owner VERIFY P4→owner REVALIDATE→明确重新 GET→CLOSE_LOCAL_RECORD→owner VERIFY P5。九次包含六次带当前 business frontier 的业务命令及三次带当前 revision/source hash 的 VERIFY。六次 frontier epoch 严格前进；CLOSE 的 revision、snapshot hash、frontier 与刚完成的真实 GET 逐字段一致。

另用全新 owner 浏览器 context，只 GET 当前计划与六目标，再读取工作清单。六项均为 `LOCAL_OUTPUT_VERIFIED`，总状态 `LOCAL_OUTPUTS_VERIFIED`，新事项 attention=`LOCAL_CLOSED`；**`case_goal_completed=false`**，没有判资格、外部受理或线下履约完成的声称。新计划仍绑定三个新 ServiceRelease，原已接单 Case 的整份历史、责任、旧批准和占用不变。

浏览器起点之前的 strict 修订发布、原目录明确退休/register/bind、新输入、worker、新 Run assignment、资料 REVIEW/CONFIRM、独立 ADOPT/P1、issued Approval 桥、原 PROPOSE/APPROVE、资源交付/P2 都是明确的原 API/自有夹具步骤；离线选择规划替身仅用于该初态。本批不把这些前置步骤说成本轮浏览器操作，也不将手动合成文字称真实线下产物。前批 strict 模式仍只支持同合同的 name/description 修订、process opt-in，不是通用语义升级或仓库级发布治理。

## 恢复与拒绝的精确边界

页面普通 GET 是当前读取，没有原 key。浏览器完成后，另由 Python HTTP observer 显式调用既有 service-case-plan/command-recovery，以三个 VERIFY 的真实原 key 得到 COMMITTED/read_only/historical_only 证明，并核业务快照不变；该观察不是 DOM 自动恢复。API 正向另核 local-case 原 key GET。原 local-case 页面自身也沿现有恢复机制核对命令。普通 dispatch/receipt 没有同等通用 key GET；本批没有伪造接口，也没有把当前读取或 POST 重放改称通用原键恢复。

新 strict Release 的实际 API 反例包括：同一新事项真实 v1 回执经 REQUEST_CHANGES/SUBMIT 生成 v2后，用旧 v1 hash ACK 得409；这不是旧 Case 回执串用。旧 P2 计划读取在 P3 验后复用旧 revision/source 得409；receipt 当前 revision 携旧 frontier 得409。撤 executor assignment 或 owner EXECUTE 后的新写得403；本批这些反例未单独证明“同一原 key 撤权重放”，不扩大声称。

事务故障在原 receipt `_event` 已真实执行后抛受控异常，完整 public 产品表快照（拒绝审计单列）与原前沿全部回滚；移除故障后明确以同 key/同参数提交成功。每个反例还核旧 Case 全历史保持，没有绕拒绝、回写旧授权或自动换 key。

## 最终冻结证据

701个受控输入匹配当前 Git；全部正式主窗口执行同一最终 SHA `7b6315f3ed737264464957ad5aa37c80c251cc87`。**4个完整模块、38唯一项 PASS，0 FAIL/ERROR/SKIP**，同进程 collection 与原 JUnit 精确一致，无节点归一、拆拼或跨批加分。

| 正式窗口 | 完整模块 | PASS | 原实际耗时 |
| --- | ---: | ---: | --- |
| final-new-v2 | 新 strict API、Chromium 两模块 | 8 | 224.57s |
| final-contract-v2 | lifecycle recovery、原 P4 两事务竞争 | 30 | 108.99s |
| 独立 API | 新 strict API 完整模块 | 7 | 185.928s；与主窗重叠，不累加 |

29项恢复合同与1项并发合同是原已存在流程的必要补充；后者真实同 fence 两事务只一成功，另一个409。最初探索收集了原5模块229节点，未整组执行；其中29项 lifecycle recovery 已纳入正式合同窗，其余4模块200项本批未运行，不把预收集当通过。冻结独审 PASS，无范围内阻断；核701输入、仅3新测试、所有产品字节不变、DOM/夹具/API观察边界及反例。独测7项同最终SHA通过，前后源文件零漂移，未运行浏览器或模型。

## 失败、中断与保全

浏览器开发v1实际因点击 form 容器而没有提交，等待状态超时；只改测试点击原 `receipt-submit-button`，并删除潜在的不存在 receiptPending 条件。不存在变量没有被本次失败证实为运行时错误。开发v2真实页面通过。

首冻结 `cd6400ed6631c3d2dd452a8e8e44b3f1394df7aa` 后静态核对发现补充断言把无 key 当前 GET 错当原键恢复。根只向精确匹配的唯一自有 pytest PID 发 SIGINT，原 XML保留3PASS的未完成窗口，日志保留 KeyboardInterrupt 与 pytest stash KeyError、runner exit1。该错误断言尚未执行，不称其实际断言失败，也不把部分窗口计为通过。测试改为明确分列原 VERIFY API 观察后重新冻结，最终8项完整重跑。

首合同窗29PASS/1setup ERROR，缺原模块要求的 FRONTIER_TEST_SOURCE_ROOT，在原导入验真门拒绝；补原源码路径及精确 source hash manifest，未改守卫，完整30项从头重跑。失败/中断 log、XML、受控停止记录全部独立保留并登记hash，未覆盖原件或从通过窗口删节点。所有这些修正都在测试/执行命令，产品代码保持基线。

## 归档与后续

[主档索引](evidence/strict-release-local-output-20261016/index.json)、[逐窗范围终门](evidence/strict-release-local-output-20261016/release-p345-root/final-gate.json)、[失败原件账本](evidence/strict-release-local-output-20261016/release-p345-root/failure-ledger.json)、[冻结独审](evidence/strict-release-local-output-20261016/release-p345-review/frozen-review.md)、[独立归档审计](evidence/strict-release-local-output-20261016-audit/final-audit.json)。主档26文件、24 raw/export配对、359509字节；290完整登记合成值扫描残留0，本次选定公档0处需替换。67份新primary原件封存；旧6086份原件及前两次audit seal只读全量核验无漂移。失败正文和私有token不公开，原件hash保留。

前批剩91模块/2280原基线节点，本批补其中 lifecycle recovery 完整29项；当前剩 **90模块/2251原基线节点** 未重跑。新8项及旧frontier race不重复扣除原基线；不跨批合成全仓通过。

这一个新 strict Release 新 Case 的手动合成本地 P3–P5及六目标读取缺口已补。后续关键路径是更广定义/来源语义兼容、正式治理/批准主体与正式AT固定初态；一般在途迁移、取消复活和F5恢复不在本片。Windows/真实设备、正式AT、真实模型B0–B2、生产、外部部署、issued桥跨进程恢复、CI均未执行；本批没有新增费用、真实凭据、网络或安全权限，没有部署、强推、main写入或模型调用。
