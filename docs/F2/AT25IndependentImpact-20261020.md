# AT-25：独立影响统计与既有容量重绑定工程证据

原 runner 执行源码：`203bf00732a3e189e53b58dac56b30dd241206b5`。统计输入校验修订源码：`9d2f8e8bd3c0ace96a7d60cef6768e674ccefa14`。接续 AT26 交付 `480768a40817d12be17547f4f6c5b838e4e2bca1`。正式 AT-25/whole_AT_EX 仍为 NOT_RUN；产品运行代码、原测试场景、旧 oracle 与上限未改变。

## 当前实际执行

原 `run_acceptance.py --ids AT-25 --source-head 203bf…` 实际 **5 PASS / 0 FAIL / 0 SKIP，86.71 秒**，source_binding AVAILABLE，engineering_subset PARTIAL_PASS，full_regression=false。四参数影响识别场景加一个已有已选容量业务场景；不是五轮重复测试。绑定约束另窗 2 PASS / 0 FAIL / 0 SKIP，0.06 秒，不加到上行。

同一冻结执行的原 16 条观察，按源码/run/精确参数测试节点和场景×Case归属、重复 payload 完全一致后去重为 10 个独立场景×Case观察。预期从原 literal oracle 的 P1–P5 符号和本次五组 baseline UUID 独立重建，未从产品闭包输出倒推。

| 范围 | 物理读数 / 去重观察 | 预期影响 / 保全步数 | 漏影响 FN | 误影响 FP | 保全分区对称差 |
|---|---:|---:|---:|---:|---:|
| 已知材料、可选容量、catalog source 版本 | 10 / 6 | 23 / 7 | 0 | 0 | 0 |
| 已选容量动作场景 | 2 / 2 | 8 / 2 | 0 | 0 | 0 |
| UNKNOWN，单列保守扩大 | 4 / 2 | 10 / 0 | 0 | 0 | 0 |

已知组合计 8 个观察、31 个影响步和 9 个保全步。UNKNOWN 不计入已知精度。三项诊断可能描述同一错分，不相加为“总错误”。FN/FP 是影响识别误差；**实际正文自动修改漏更/误改率没有测量**。四参数读取无写范围仅为 stored plans 及 `original_rows` 所列两 Case 的12类记录，不声称所有 public 表或所有 SQLite 无写。

容量场景实际给两 Case 的 P1 加锁，改变原已选资源真实 capacity/revision；旧 P2 VERIFY 拒绝，显式 ADOPT 后保留原 P1 全锁证明。两 Case 各用原新 holds/组合、当前比较、明确确认 resource-link 重绑定、P2–P5 VERIFY 与本地 REVALIDATE，恢复六目标本地输出 VERIFIED；原6类 reservation/link 实体行仍保留。已有 first-delivery Approval 保留，替换正式 Approval 仍 NOT_IMPLEMENTED。原源码循环逐 Case 断言旧 VERIFY=409；记录字段重用了循环最后变量，不能称每 Case 独立 HTTP 原始回执。材料完整业务纠正链引用[本次 AT26](AT26FixedManualHistory-20261020.md)，不把其1项重复加到本次5项。

## 汇总器修复与源码分界

独审用纯 JSON 变异复现了旧统计脚本的输入完整性缺口：缺少反向观察、替换测试节点、实际分区重叠等会被接受。实际原件仍正确，未作废当前5项结果。最小修复约束精确固定测试节点/参数、固定物理观察数、同 Case 的完整互斥 actual 分区和独立 baseline；另补跨 Case UUID 与错参数节点拒绝。

同5个变异在旧 consumer 下被接受，在新 consumer 下全部拒绝；原16行正控两版均接受。此为纯 JSON 输入检查，不是新增产品/PG测试。用新 consumer 重新计算同一 producer203 原件，数值不变，未重跑5个 PG 场景。

原 producer 冻结900输入在执行前后零漂移；后续 consumer 也冻结900输入，只有 `recompute.py` 一项有意变化，其余899输入与原执行字节一致。两份清单和两个完整 SHA 分列，不宣称203执行过修订后的统计器，或9d2重新执行过5项产品测试。

## 原件与剩余范围

[合同](AT25IndependentImpactContract-20261020.md)、[原 runner 回执](evidence/at25-independent-impact-20261020/acceptance-report.json)、[结果](evidence/at25-independent-impact-20261020/result.json)、[独立计算明细](evidence/at25-independent-impact-20261020/impact-accounting.json)、[可重算脚本](evidence/at25-independent-impact-20261020/recompute.py)、[原件 SHA256](evidence/at25-independent-impact-20261020/artifact-provenance.json)，原 baseline/oracle/at-results/容量比较 JSONL 在同目录。独审和修前/修后输入拒绝回执在 `independent/`。

本片没有新 test 字节或目录代，没有重复 collection。沿用 AT26 源码 `5f28e77ed4415f6d3d468635195eda26f381d5e8` 上实际9366项/395文件、四片2352/2309/2368/2337精确收集；573个 manifest 绑定输入与当前代码字节完全一致，源标记仍为原实际收集 HEAD，见[连续性原件](evidence/at25-independent-impact-20261020/collection-continuity.json)。该数字不是本轮实跑数。

无真实浏览器、原生 Windows、真实模型、正式来源或项目整体验收；自动正文更新的漏更/误改与原方案完整业务覆盖仍未验。Windows 完整安装、OWNER_MUTATION_PAUSED、owner/DACL、原生026–032/roles/seed及真实场景授权门保持。没有新费用、凭据、安全/网络权限、部署或用户电脑动作；main、旧分支不改，正常新分支推送不触发其命名范围之外的免费 CI。

最终独立只读审计 LIMITED_PASS、无开放 P1/P2；未新增 PG/产品测试。审计 SHA256：`14e0bed36502bda42b830a8a87b0417ab2fae349e736891cbd5e7001318fec7d`。审查独立核对 raw literal/baseline/算术、原5项JUnit和producer/consumer两个冻结、collection连续性，并保全修前输入拒绝FAIL及修后同变异拒绝。
