from pathlib import Path
import json
r=Path.cwd();runtime=r/'.runtime/note-template-carry-root';out=r/'docs/F2/evidence/note-template-carry-20261015';v=json.loads((runtime/'final-regression-verification.json').read_text());index=json.loads((out/'index.json').read_text());audit=json.loads((out/'audit.json').read_text());assert v['status']=='PASS' and v['complete_modules']==95 and v['unique_testcases']==2713
source=v['source_sha'];pairs=len(index['entries']);raw=sum(e['raw_bytes'] for e in index['entries']);exported=sum(e['export_bytes'] for e in index['entries'])
report=f'''# F3-T03 / AT26–27：携本人注记的兼容模板保全

基线交付 `ed5d32b6bbcf261d802fe579a2daab16330a5879`；最终验证源码 `{source}`。同 Case、同 owner、同模板谱系的既有同结构兼容版本，原升级页面展示旧新版本/来源、当前 MANUAL 正文与两槽实际材料、受影响/保留步骤。用户重新 check/choice，另行明确确认后，沿独立受控 carry 入口采用。原六目标、P1–P5、完整注记对象、UUID、历史与未影响锁保持。

目标模板来源相同、只改标题/说明且 Case 当前来源全部核验时，步骤和锁逐字保留；目标来源变化时，本次 fresh carry 绑定旧新来源，不沿用旧继续决定，全 P1–P5 按原规则失效，沿必要业务办理及五步 VERIFY 到六目标证据/清单。材料变化、KEEP/DEFER、继续后再编辑等未解决时，须先原来源冲突处理、局部 ADOPT 和重验，不能用 carry 消解。MANUAL 保全不代表新事实、语义义务、资格或履约成立。

仅同结构；破坏性/携注记结构增强、非局部替换、跨谱系、UNKNOWN/失效/撤回、锁冲突、撤权/ABA、迟到及幂等异参拒绝。原 /apply、/apply-structure 及旧事件封闭解析保持，新入口要求严格 true 和本次预览摘要。完整材料包绑定 carry 之前的原 P1 核验证明，后来合法换源不会改写旧收据。保存失败完整回滚；丢 ACK 后原 key 冷 GET，不自动 POST。

## 验证范围

同一冻结 SHA 的 **95 个完整相关模块、2713 个去重有效项全部 PASS，0 FAIL/ERROR/SKIP**。这是从八个实际执行窗口按完整模块明确选择的并集，不是所有原始窗口均 PASS，也不是全仓运行。

| 有效选择 | 完整模块 | PASS |
| --- | ---: | ---: |
| 根 root-1-v2 | 27 | 900 |
| 根 root-2-v2 中另外24完整模块 | 24 | 745 |
| goal-results-retry-v1 整模块 | 1 | 44 |
| common-v2 | 18 | 305 |
| 原来源 formal | 7 | 235 |
| 原继续 prior-manual-v2 | 1 | 33 |
| 新 carry note-carry-v2 | 1 | 28 |
| 独审 freeze-f686ada-extra-v2 | 16 | 423 |

原 root-2-v2 完整25模块实际788PASS/1FAIL；其失败模块全部44项（含43项原PASS）从有效并集排除，完整重跑44项独立加入。其余24模块逐模块全集选择，未删节点。全部原始collection/JUnit精确且节点唯一，选中95模块/2713节点不交；613源码路径和14392受控文件前后零漂移，上一交付2127份原始证据保持。[独立可复核并集](evidence/note-template-carry-20261015/note-template-carry-root/final-regression-verification.json)。

新28独测含2条完整HTML/24次实际HTTP、4个六目标闭环。title模式全steps及P1/P3锁逐字保持、0UNLOCK/VERIFY；source模式实际提交后受控丢响应，新VM只GET原key恢复，再5VERIFY/六目标清单。known2条/5应改及5应留对零漏更/误更/误保留；UNKNOWN影响精度未测，UNKNOWN资格拒绝另列。22独测设计9项限定scope PASS/8变体/5本模块NOT_RUN。原33独测8完整HTML/431HTTP、5六目标闭环（4MANUAL/1接受SOURCE），含真实丢choice/adopt回复及当前/迟到GET403回归；不冒充新carry的403页面样本。[独测核验](evidence/note-template-carry-20261015/note-template-carry-independent-formal-v2/final-handoff.json)。原7来源模块235项及41条完整HTML本冻结新跑，分模式与known/UNKNOWN/锁边界见[原来源摘要](evidence/note-template-carry-20261015/note-template-carry-backend-formal-v2/report-summary.json)。

另独审历史2pytest、预算6pytest单列；20个纯历史变异在一个成功收据夹具内，不是20个HTTP测试。补充及新后端19项使用旧五目标兼容夹具，不冒充新六目标证明；真实六目标依据独测fresh_chain。实际验证64计划事件的source58允许/59拒，title63允许、保留锁62允许/63拒；128机会账本不扩，carry不加机会事件。38独审设计11named/19variants/6NOT_RUN/2静态验证，未统签38或与22加成60完成。[冻结独审](evidence/note-template-carry-20261015/note-template-carry-review-formal-v2/review-summary.md)。

完整HTML是Node VM DOM→真实HTTP/ASGI→自有PostgreSQL，真实浏览器未执行。旧Chromium/Playwright模块collection因缺依赖阻断，余423仅收集未执行的首窗原件保持；未安装浏览器。Windows/Win11、正式业务AT、真实模型/B0–B2、正式治理/批准主体、现实履约、生产及无现有触发的本分支CI均未执行。产品模型调用0，无main修改、强推、部署、新费用/凭据/安全权限或访问拒绝绕过。

## 失败与有界修正

开发独审发现epoch版本接受True/1.0、以及材料全文可伪造重哈希两项真实阻断；分别补严格整数/封闭比较和迁移前P1完整快照锚。7562首冻结未启动正式窗；c376正式阶段发现新增独测错误引用preparation_grants不存在的revision列，并误期望EXECUTE撤权后GET200。真实原reader要求READ/PREPARE/EXECUTE/case.create；仅修新独测，产品字节不变，三权限POST/GET403复验通过后冻结f686。各自有旧pytest仅一次SIGINT收口，原partial/FAIL/未运行节点均保留；无名中断JUnit标记不计PASS，不迁旧分数。

同f686的独审首16模块窗422PASS/1FAIL：旧来源1秒期限在前置choose(:172)已安全409，未到目标回滚断言(:175)。原节点原断言PG单项通过；仅一次完整16模块重跑423全过。根25模块窗788PASS/1FAIL为旧资源2秒期限测试:148前置REVALIDATE409；单项triage在同:148稍后get状态UNVERIFIED。两者均未到:149行锁目标段。等其余pytest自然结束后，原完整44模块唯一低负载复跑全过。两类期限均不改产品/测试/时钟/断言/权限；全部原FAIL和单项原件保留，最终按上述整模块选择，不把它们抹为全绿。

开发新夹具曾对已VERIFIED步骤重复VERIFY，或调用不受支持的无证明ADOPT；仅纠正新夹具走原协议。私树旧兼容模块Git相对路径失败，经根目录只读Git与私树PYTHONPATH单项复验；旧测试不改。后端旧5目标夹具误名six已更名case_outputs，原错误口径撤回。所有证据在相应历史目录保留，版本/来源/设计/实际执行分别计数。

## 剩余关键路径

本批限同结构同谱系的本人MANUAL注记保全。更一般语义/多字段冲突、一般来源传播/动态图、正式替代Approval、复杂在途升级/F5-T04、备份恢复，以及通用ServiceRelease跨版本执行/正式治理/回退责任闭环仍待补。既有两类共享反查、有限合成Release/ParkInstance、第二园区冷输入、有限模板前向增强保持已交付。共享反查仍有两来源/32候选/跨页UNKNOWN/跨Case非原子边界。按10月15–22日一周目标，接续更广来源变更/内容冲突的有界可验证路径，再补正式运行前提。

## 合同与归档

[合同](NoteTemplateCarryContract-20261015.md)、[38设计](NoteTemplateCarryReviewOracles-20261015.json)、[22设计](NoteTemplateCarryIndependentOracles-20261015.json)逐字保持设计输入状态，实际映射另列。主档{pairs}个raw/export配对，原件{raw}字节，导出{exported}字节，hash/大小精确；去敏按已知合成session与fixture repr，原件不改。共享matcher来源和排除私树/缓存/私值清单见方法证据，不声称算法多样性。

[主档索引](evidence/note-template-carry-20261015/index.json)、[说明](evidence/note-template-carry-20261015/README.md)、[根checkpoint](evidence/note-template-carry-20261015/audit.json)、[独立终门](evidence/note-template-carry-audit-20261015/final-gate.json)。
'''
assert 'PENDING_' not in report
(r/'docs/F2/NoteTemplateCarry-20261015.md').write_text(report)
(out/'.gitattributes').write_text('* -text -whitespace\n')
(out/'README.md').write_text(f'''# 携本人注记兼容模板保全工程证据

最终验证源码 `{source}`。{pairs}个raw/export配对；原件{raw}字节、导出{exported}字节。原件保持，导出按登记的合成session精确去敏；JSON/XML先结构解析、fixture repr行仅文本遮盖，源码.py/.js不适用该行遮盖。完整值/截断上下文与结构解析由独立终门另核。

索引包含开发失败、旧冻结部分执行、最终冻结回归及有界重跑；顶层source_sha是最终参照，不代表每份历史文件都在该SHA执行。95完整模块/2713去重有效项来自八窗整模块选择；原root2失败模块44项全部排除后完整复跑，其他24模块全集保留，不声称全部原始窗口全绿。另8pytest/20纯历史变异及未执行设计分列。详见[报告](../../NoteTemplateCarry-20261015.md)。

11个本批runtime根纳入，私有session集合、PG文件、private-worktree/source-wip-v1/v2、缓存和pytest临时根排除；旧共享私值表仅供去敏，不是独占测试证据。KnownTokenRedactor为逐字共享helper，独立审计另做库存/重建/执行范围核对，不声称算法多样性。[index](index.json)、[root checkpoint](audit.json)、[独立终门](../note-template-carry-audit-20261015/final-gate.json)。

Windows、真实浏览器、正式AT、真实模型/B0–B2、正式治理/现实履约、生产、本分支CI未执行；产品模型调用0。未改main、未强推/部署/新增费用或权限。
''')
print(json.dumps(dict(report='docs/F2/NoteTemplateCarry-20261015.md',pairs=pairs,raw_bytes=raw,export_bytes=exported)))
