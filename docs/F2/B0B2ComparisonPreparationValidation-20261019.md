# B0/B2公平比较材料与最小协议回执

基线`db529a4f79300523a34583d8f27d9414688074d9`；冻结并受测`7a2862a73eb270b4d7aab10d4d65145f2053a3e4`；分支`dev/f3-b0-b2-comparison-preparation-20261019`。本片完成原F3-T04评测材料准备和一次原AT31守卫运行，**未完成B0/B2业务配对比较**，不改产品、测试、runner或固定42项验收状态。

## 可复用交付

[材料说明](B0B2ComparisonPreparation-20261019.md)和[冻结JSON](B0B2ComparisonPreparation-20261019.json)列出27份原协议/输入/fixture/runner文件的字节与hash，固定V4三服务六目标、原A首次/有效新输入/十类错误输入、B有限条件与冲突、C仅资源版本/缓冲变化，并规定两臂同目录/数据/权限/计划/变更/预算的等价条件。它们是已知开发样例的源文件配方，不是留出测试集、已物化的双臂数据库快照或代表性园区数据；UUID、实际DB时钟、有效期及具体catalog hash待物化时冻结，不静默归一化。

独立审查先给原合同/字面oracle判据，再读新材料；审查员已有项目上下文，不是外部领域专家或统计双盲实验。A六目标不能删，技术Run成功不替代产物/履约；B的23==23、23!=24及未解决冲突分别为TRUE/FALSE/UNKNOWN；C的独立应更新集是P2–P5，应保持集P1，另保其他园区A与旧占用历史。全量重算不是误改，应核语义、证据和人工决定是否无依据变化。不能由这些输入推出实际耗时/模型答复/总体成功率或真实资格。

已有普通五目标NO_MODEL LocalDemo、无模型六目标bounded proposal与隔离V4三目录的证明/信息条件不同，均不直接充当配对B0。C资源依赖单独变化也不满足原非local计划替换准入；全量原业务臂未就绪，不删plan或额外改request/catalog来开放。旧MockTransport声明usage是输入，不是实际模型用量。真实来源provider仍待实际合同，不从本材料生成权威。

## 实际运行

原命令：`.venv/bin/python scripts/run_acceptance.py --ids AT-31 --source-head 7a2862a73eb270b4d7aab10d4d65145f2053a3e4 --report .runtime/b0-b2-preparation-20261019/runner-report.json`。

| 范围 | 结果 |
| --- | --- |
| 原runner反误签守卫 | 1 PASS、0FAIL/ERROR/SKIP，exit0；JUnit suite 0.185秒，testcase 0.004秒；整次原CLI含来源核验5.523679秒，120秒上限、0自动重试。 |
| 原runner判定 | source_binding AVAILABLE，AT31 engineering_subset PARTIAL_PASS，whole_AT_EX和AT31 whole_status均NOT_RUN；full_regression=false。原gate文案按原绑定保留，不代表LOCAL材料必须等真实来源才能准备。 |
| 新业务对照执行 | B0/B2配对任务0；A/B/C产品执行0、DB/HTTP调用0、真实模型0；没有把守卫1项记作对照样本。 |
| 输入核对 | 817份既有源码/测试/脚本输入运行前后零漂移；27份选定输入与基线及前后hash相同。共享工作区运行，原CLI校验HEAD/test sources；不声称私有镜像或全量模块来源核验。 |
| 独立审查 | 10条合同/机械判据，有限材料静审0开放P1/P2；独立文件写入、产品import及动态执行0。 |

两天上限的材料误述在运行前由独审指出，已改为正窗口≤24小时，原拒绝样例是48小时；产品算法未改。旧稿及纠正hash保留，未称其为测试失败或产品缺陷。静审签收的实质JSON SHA为`9f1cc7e2c11ee70804206fdb0e324bb5fb156b14a191012de13fe048268480da`；之后仅将该文件的送审状态字段替换为签收说明，实质输入/答案/成本字段一致，根机械核对见证据。

[证据清单](evidence/b0-b2-preparation-20261019/publication-files.json)共21文件：20组原始/导出hash配对全部字节相同，另1清单；原始JUnit/log、runner report、前后输入图、送审旧稿与独立意见均保全。关键回执：[运行](evidence/b0-b2-preparation-20261019/invocation.json)、[原runner报告](evidence/b0-b2-preparation-20261019/runner-report.json)、[JUnit](evidence/b0-b2-preparation-20261019/actual-guard.xml)、[根核对](evidence/b0-b2-preparation-20261019/root-verification.json)、[独立判据](evidence/b0-b2-preparation-20261019/independent-source-blind-oracle.json)、[跑前签收](evidence/b0-b2-preparation-20261019/independent-pre-run-review.json)、[边界纠正](evidence/b0-b2-preparation-20261019/independent-input-boundary-correction.json)。没有采集或导出fixture会话或来源凭据，不声称穷尽扫描未知秘密。

## 成本与尚缺的配对条件

[成本记录](evidence/b0-b2-preparation-20261019/cost-ledger.json)只把5.523679秒记为本次runner工具开销，不能当用户办理时间。产品任务/参与者人工时间、目录清理/规则审核/fixture准备、模型/工具/排队/等待/失败修复等尚未测得的量为UNKNOWN或NOT_RUN，未估成人工节省或ROI。未运行比较臂的tokens/业务成本不填零。

继续实际公平比较仍需：同V4三目录的明确手工选择动作表；对完全相同既有计划/资源变更可合法应用的全量重规划臂及其历史/人工说明保全策略；双臂具体相同初态、时点、预算和执行顺序；实际主动人工记录。可先限定为planning-only，但须两臂使用同一观察层，不能把一臂只读proposal与另一臂业务执行成本相比。以上目前是NOT_READY/未尝试，不是本轮调用被拒或结果未知；无需真实来源即可准备这些LOCAL条件，但本片没有新造baseline、执行器或放宽产品门。

旧42项清单、AT33旧659/481与原DOM/冷恢复证据复用各自历史范围，不计本片新增成绩。Windows、真实浏览器、同真实模型B1、真实业务效果、正式AT31/全部项目仍未验；旧风险窗口不重试，HTTP UNKNOWN_OPEN不关闭。未改main/强推/部署、新费用、安全权限或真实身份/Grant/分派/目录/批准/凭据。最终交付SHA及远端差异以本轮Git回执核对。
