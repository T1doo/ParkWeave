# 固定B0选择与B2同层规划对照回执

基线 `75caa18af46b40f01e75f65b696cbf39a822dfcb`；冻结并实际受测 `b111d7292258faf0fff1db55f1699fabcbefe312`；分支 `dev/f3-b0-b2-planning-only-20261019`。完成一个固定合成样例的共享初态、B0固定选择适配、FULL/LOCAL同观察层候选规划及独立字面判分。**两臂候选相等，各漏更0/4、误改0/1；业务应用均NOT_RUN。** 本片落实原方案要求的合成fixture与执行器，不再将这些实现工作列作用户需要提供的前提。

## 交付与回放

[固定协议](B0B2PlanningOnlyContract-20261019.md)、[B0/B2适配脚本](../../scripts/b0_b2_planning_only.py)、[场景测试](../../tests/test_b0_b2_planning_only.py)、[先于运行冻结的字面oracle](../../tests/fixtures/b0_b2_planning_only_oracle.json)。复用原compact_context、parse_selection、rebuild_selection和registered_dependencies.inspect；未修改产品src、普通provider、API、权限、迁移、原service_case_steps准入、固定42项清单或AT绑定。没有新增框架或授权算法。

实际57,083字节的[同一输入快照](evidence/b0-b2-planning-only-20261019/frozen/planning-artifacts/shared-input.json)不含会话，文件SHA256为 `dba1227fdd933cfb3a15413e1db3c6a6269d9f69403d5d738e64dacd6c136bb1`。在已有依赖的项目根目录可离线回放到新的输出路径，无需DB、HTTP或模型；下列为复用命令，本次未额外重跑：

```sh
.venv/bin/python scripts/b0_b2_planning_only.py \
  --input docs/F2/evidence/b0-b2-planning-only-20261019/frozen/planning-artifacts/shared-input.json \
  --sha256 dba1227fdd933cfb3a15413e1db3c6a6269d9f69403d5d738e64dacd6c136bb1 \
  --report .runtime/b0-b2-local-replay.json
```

脚本核对输入文件字节hash并记录自身hash；报告另有规范化JSON内容摘要，不能与文件字节摘要互换。交付的四份源文件保持受测版本字节不变。固定B0按预定三个service_id及精确ref选择，不读取oracle选择答案，也不调用模型；它是脚本操作，不能记作人工办理或AI答复。

## 共享条件与实际结果

两臂使用同一V4三服务、六目标、既有计划/五节点UUID映射、目录及配置ref、原ADOPT身份锚、当前来源、空manual_locks/owner_amendments、预算和时间，固定FULL后LOCAL。as_of为 `2026-10-19T00:48:50.035153+00:00`；quantity为2，资源时段为该时点后5至6小时。只把两个选中资源revision从1改2、buffer从300改360；原READ/HOLD四行、集合count/hash及资源完整行逐项对应。两臂没有另建Case、另采时钟或重贴身份标签。

| 同一正样例的观察量 | FULL | LOCAL |
| --- | ---: | ---: |
| 原rebuild_selection调用 | 1 | 1 |
| 重建器返回契约节点 | 5 | 5 |
| 原依赖inspect调用 | 0 | 1 |
| 构造候选投影行 | 5 | 4 |
| 复用旧候选投影行 | 0 | 1 |
| 最终候选节点 | 5 | 5 |
| contract diff | 0 | 0 |
| source witness diff | P2–P5 | P2–P5 |
| 漏更 / 应更新 | 0/4 | 0/4 |
| 误改 / 应保留 | 0/1 | 0/1 |
| 臂内自动秒 | 0.010785451 | 0.010307446 |
| 业务ADOPT尝试 | 0 | 0 |

[原始对照输出及判分](evidence/b0-b2-planning-only-20261019/frozen/planning-artifacts/comparison.json)中的最终五节点payload相等。契约不变，变化只在直接来源/上游见证摘要；P1保持。每臂都重建五个契约，LOCAL的四行投影不代表只计算四个契约，也不代表内部总操作量或计算节省。共同适配另构造旧投影5行；判分器再构造旧投影5行，均未归入某臂成果。

臂计时在deepcopy之后开始，仅覆盖重建、inspect及候选投影；导入、I/O、预检、复制、共同准备和判分不在其中。整个CLI明确exit0、墙钟1.116025410秒、60秒上限、0自动重试。一次固定脚本的秒数差没有统计意义，不证明人工分钟、成本节省、ROI或AI语义优势。

## 实际验证与失败保全

冻结镜像仅选择 `tests/test_b0_b2_planning_only.py` 和 `tests/test_service_selection.py`。[JUnit](evidence/b0-b2-planning-only-20261019/frozen/results.xml)为 **39 PASS、0FAIL/ERROR/SKIP，14.754秒**：新场景1项加原selection兼容38项；这是一个比较场景、两个正向规划臂，不能称39个对照任务。场景内12个无效输入控制和5个判分控制单列，不计额外比较样本；不是全回归。没有重跑AT31反误签守卫、旧B/C全套、浏览器、Windows或旧风险窗口。

原控制器在pytest及四份输入图完成后，因glob同时匹配真实case目录和pytest的current符号链接，触发 `assert len(artifacts)<=1`，**外层exit1**。pytest子进程退出码在此之前未落盘，明确为NOT_SEPARATELY_RECORDED；不能把JUnit通过数补作已记录的pytest exit0。后续仅用resolve去重两个路径为同一目录、收集既有工件并核验，收集恢复exit0，产品/测试/CLI重跑0次。[原失败](evidence/b0-b2-planning-only-20261019/controller-postprocess-failure.json)、[工具失败的作者转录](evidence/b0-b2-planning-only-20261019/controller-tool-failure-transcript.json)、[原控制器](evidence/b0-b2-planning-only-20261019/run-frozen.py)、[收集恢复](evidence/b0-b2-planning-only-20261019/postprocess-recovery.json)均保留；不声称整条控制器流水线exit0。

共享运行前后和镜像运行前后四份输入图各818项完全相同；当前共享/镜像对应文件亦核对一致。113个已记录项目模块来源均位于冻结镜像，不扩称所有第三方依赖。[根核对](evidence/b0-b2-planning-only-20261019/root-verification.json)、[运行结果](evidence/b0-b2-planning-only-20261019/frozen/result.json)、[调用](evidence/b0-b2-planning-only-20261019/frozen/command.json)及全部四图/模块记录已归档。

独审先给10条原合同/字面判据，再读本实现；静审发现资源查询绑定、原ADOPT身份锚、空/单臂及摘要判分三项P2，均在运行前修复并有限签收。[初始发现](evidence/b0-b2-planning-only-20261019/independent-initial-findings.json)和[修复中间稿](evidence/b0-b2-planning-only-20261019/pre-identity-score-fix.py)保留；中间稿已含第一项资源修复，不能称最初未修版本。脆弱旧版未执行动态反例。修复后的有限无效控制由根测试执行，独审动态仍0次。[跑前签收](evidence/b0-b2-planning-only-20261019/independent-pre-run-review.json)、[跑后核对](evidence/b0-b2-planning-only-20261019/independent-post-run-review.json)未发现新的确定P1/P2；独审无产品import、文件写入或私有会话读取。原合同、开发样例和项目上下文已暴露，非留出集、外部领域资格或统计双盲验证。

## 准备成本与未运行范围

[准备及纯度回执](evidence/b0-b2-planning-only-20261019/frozen/planning-artifacts/setup-and-purity-proof.json)明确共同准备有写入：复用原owned PG/fixture完成2次合成ADOPT、2次Run assignment，fixture初始化资源Grant行4条，再修改2个资源来源行。另保留有实际历史的park-a五目标事项作隔离见证；它不是与六目标park-b配对的实验臂。比较前后公共DB行、authority及该非空A历史均不变；零业务写入仅适用于双臂规划回放，不能扩称整个窗口零写入。

共同准备复用原离线MockTransport一次，声明20 prompt/10 completion/30 total仅是合成输入；实际模型调用0。fixture进入后准备计时6.571965155秒，最初目录/fixture初始化耗时、参与者主动人工、真实模型成本为UNKNOWN/NOT_RUN。JUnit、CLI、准备及臂内时间包含关系不同，不相加当办理时间；未填人工节省或业务收益。

C仅资源变化的全量业务ADOPT仍受原service_case_steps替换门限制，两臂业务应用均NOT_RUN且未尝试。没有删计划、伪造request/catalog、改成partial或放宽权限来开放全量臂；也没有把局部实际ADOPT成本与全量只读候选成本混比。空manual_locks/owner_amendments样例已完成，不再要求未来人工策略才可做本片。

普通真实业务仍需要已有合法PREPARE/REVIEW_ASSIGNED/preparation_catalog、真实来源合同及对应provider/适配器注入；不能用IsolatedPlanApproval或本合成快照产生普通批准。正式C全量应用还需满足原替换合同及其历史/人工说明保全要求，不由本候选对照自动解决。这些属于后续真实执行范围，**不阻塞本片已完成的规划比较，也不是本轮被拒调用**。

Windows正式AT、真实业务/真实浏览器、真实模型B1、主动人工比较、正式AT31及完整项目均未验；固定42项验收状态未改。旧52、659/481及其他历史测试成绩不并入本次39。未改main、强推、部署、新费用或安全网络权限，未触碰未知锁/进程或重试旧HTTP UNKNOWN_OPEN。

## 证据导出

[公开清单](evidence/b0-b2-planning-only-20261019/publication-files.json)共35文件：34组原始/导出hash及字节完全相同，另1清单；原始工件私下保全。两份private会话文件排除，合并捕获的10个精确合成会话值在导出中出现0次。另对独立43字符候选作有限扫描：4项在既有src/tests/scripts中，2项为逐字复核的JSON字段键。归档扫描先后因这两个字段键中止，确认后只恢复归档，未重跑产品或测试；[归档失败与恢复说明](evidence/b0-b2-planning-only-20261019/publication-scan-initial-failure.json)保留。不声称穷尽未知秘密。最终交付提交只追加本报告和证据，受测四源文件不变；完整交付SHA及实际远端差异见交付Git回执。
