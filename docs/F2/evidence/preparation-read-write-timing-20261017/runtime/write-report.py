from pathlib import Path
from collections import Counter
import json,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/preparation-read-write-timing';result=json.loads((r/'final-result.json').read_text());archive=json.loads((r/'archive-validation.json').read_text());assert result['unique']==284 and result['failures']==17 and not any(result[k] for k in ('errors','skipped','input_drift','status'))
counts=Counter(t.attrib['classname'] for t in E.parse(r/'final-pytest.xml').findall('.//testcase'))
failed=Counter(t.attrib['classname'] for t in E.parse(r/'final-pytest.xml').findall('.//testcase') if t.find('failure') is not None)
rows='\n'.join('| `'+name.split('.')[-1]+'.py` | '+str(count-failed[name])+' | '+str(failed[name])+' |' for name,count in counts.items())
body=f"""# 普通页面资料读取就绪与写入错误归属

**开发检查点：全回归有17项失败，尚未闭环，不是通过验收。**\n\n源码及测试冻结：`25c64f1dd4bb2ca9a79be88650d3a1b410c4bef5`。基础：`175918d440bb06d3749cb5fc1de5b79c0a4e9b0f`。同一分支 `dev/f2-demo-original-page-intake-20261017`、同一源码/Git写入者；独审只读源码，并仅在独立等字节/tmp镜像和证据目录写入测试产物。

## 本片修复的实际问题

实际Chromium → 普通configured_app子进程 → 自有隔离PG的定向红测，在未改的基础页面直接证明两项问题：最后一项必要取消协调GET尚未结束时，材料按钮已可提交；在材料POST实际提交、回复暂缓期间，先前独立计划GET的500错误会把全局active写flow标记失败，阻塞下一次材料提交。基线两例均失败，原stdout/XML、原测试及诊断保留。本次直接证明这两种时序的因果，不倒推此前历史失败每次都由同一错误导致。

页面现在显示“正在核对 / 处理中 / 已就绪 / 读取已失效 / 原操作待核对”。读取对象、token、导航代际、调用者当前性和资料修订共同约束状态；只有必要readiness、corrections、objection及企业owner的cancel/reconciliation快照全部与当前资料同版本，才允许新材料、决定、准备度操作。按钮fieldset与函数提交门同时约束鼠标和Enter；草稿字段在只读核对时保留。失效须用户明确刷新。辅助facts/reuse失败保留原授权检查，不能任意污染当前写入。

错误WeakMap只关联捕获的原flow；自身nested mutator重抛仍归属原flow。GET错误不再全局标记任意正在进行的写操作；validated读回仅核对调用开始前已经observed、且同actor/domain/id的原操作。原事件、CAS、来源版本和恢复证明算法保持。UNKNOWN仍保留原正文、参数、key及显式GET恢复；迟到读取、身份ABA、取消、导航不能解锁或清除新的当前读取。原恢复控件在新fieldset之外。

独审发现共享包装还需覆盖资源调用者的绑定校验。资源五动作红测先实际提交，再仅破坏首响应绑定，五例均失败：旧代码在绑定校验前清掉原key。现将四处原字段校验移入resourceWrite回调，await校验并再次检查原上下文后才删原key；动态confirm/release及cancel也由原tracked mutator覆盖，≥3成员writeBundle原协议和校验保留。新增五例证明坏响应后另一入口被阻止，明确重试仍同path/key/body且无重复DB记录，成功后入口恢复。此处保留原窄绑定语义，不宣称完整响应schema或成员双射校验。

产品源码只改web.html，未修改身份/Grant、分派、目录、SQL、正式来源、NativeRunAccess或选择/采纳算法。原页面测试的preparation等待改为可见“已就绪”；其余已有计划等待不在本片重写。新测试以可见控件、HTTP响应及DB原事件观察，唯一内部flow读取仅作红测诊断，不用于等待、导航或解锁。

## 冻结后实际验证

原已收集279项 **实际执行**，加资源5项，共 **284唯一项：267PASS、17FAIL、0ERROR/SKIP**，13个完整模块；全回归门未通过。新增资料时序13项和资源5项全部通过且已含内，不与历史成绩累加。JUnit/外层实测时间见[最终结果](evidence/preparation-read-write-timing-20261017/runtime/final-result.json)，外层 {result['elapsed_seconds']:.3f} 秒。738项源码、测试、脚本和原合成合同前后零漂移，窗口worktree干净。

| 完整模块 | 唯一项 |
| --- | ---: |
{rows}

[实际调用与范围](evidence/preparation-read-write-timing-20261017/runtime/final-invocation.json)、[完整JUnit](evidence/preparation-read-write-timing-20261017/runtime/final-pytest.xml)、[stdout](evidence/preparation-read-write-timing-20261017/runtime/final-pytest.log)、[738输入哈希](evidence/preparation-read-write-timing-20261017/runtime/final-inputs.json)。包含1200/320原页面新诉求/两槽材料/原角色REVIEW/CONFIRM、NO_MODEL选择和明确采纳等既有回归；新Run仍无assignment，P3保持拒绝。

独立精确字节/tmp镜像独审四文件增量，0阻断；这个结论不能覆盖后来完整回归发现的17项失败。单独执行两项最初时序及资源五动作 **7PASS/0FES，117.73秒**。共享与镜像各738输入前后零漂移，实际模块从mirror/src导入。此7项与主284重叠，绝不相加。[独审及独测报告](evidence/preparation-read-write-timing-20261017/runtime/independent/reviewer-25c64f1d-e1el95ol/review.json)连同原stdout/stderr、JUnit、7API日志和证明文件归档。

## 最终17项失败与仍需修复\n\n9项属于冷态、热态、在途及旧成功来源清除时的expired/future句柄检查。readServicePlanHandle在175918和25c整行逐字相同，SHA256为d285e2f9fdcfe94f763aa02069101d8647dd398fc9f6d84755623a3654cb674c，未引用h.expires。既有合同及历史实现要求数值有限、晚于当前时间且不超过24小时；这是基线已有TTL缺口，本片没有恢复它。完整JUnit已证过期句柄仍被接受等断言失败，不能当作仅环境问题。\n\n另8项位于template_plan_continuity模块：1项ASGI桥接连续性、7项模板入口迟到/身份/绑定检查。trace包括未取得servicePlanView和calls的path/resolve为空。只读静查发现两个既有Node Element模拟均无classList，而原clearCaseCancellation无条件调用prep-detail.classList.remove；该清理及模拟也在基线中存在。此归属以独审补充说明为准；未启动基线重测或第二回归，不把静态分析冒称额外运行证明，不为通过而放松产品清私有视图。\n\n依最新指令仅结算现有session99434，不启动第二回归。源码保持25c，TTL修复及模拟适配尚未实施或验证。发布到普通开发分支仅保全可审查检查点，不能称284项通过或完整项目完成。[17项完整失败](evidence/preparation-read-write-timing-20261017/runtime/final-failure-details.json)、[TTL字节核对](evidence/preparation-read-write-timing-20261017/runtime/ttl-static-findings.json)。\n\n## 开发失败与证据保全

原基线red-v1两例失败；green-v2为7PASS/4FAIL（UNKNOWN字段已被原产品锁定，测试不应尝试编辑；另发现fromPlan原clearPlan会递增代际，需在原load调用后捕获）；green-v3和green-v4各4PASS，offline-v1为94PASS。资源red为5FAIL，原测试复制留存；随后补可见跨入口fence观察，resource-green为5PASS。开发窗口均不加最终唯一数。**green-v1虽2PASS，但未证明不可变窗口，明确排除**，不作为修复通过依据。收集279只表示收集，最终284由实际JUnit证明。

一次实际exec-server transport disconnected发生在四个独立读操作，没有待确认写入；一次安全pwd重试成功，同环境安全检查、完整源码快照及原日志tar保存在私有recovery-check目录。未切换实例或重复启动写入者，未知锁和遗留进程未动。第二次平台断连通知的根因保持Unknown；14:26检查证实原进程存在、日志刚更新且无磁盘不足证据，状态检查不算代码成果。

公开[manifest](evidence/preparation-read-write-timing-20261017/manifest.json)含 {archive['pairs']} 对raw/public哈希映射，临时合成会话候选脱敏 {archive['redactions']} 处；JSON/XML/PNG标准库结构及全部配对哈希核验见[校验](evidence/preparation-read-write-timing-20261017/archive-validation.json)。原件在私有.runtime保留。仅复制仍可取得的诊断；不含PG数据目录。原29065个继承F2证据blob在交付检查逐个核对，结果以最终回执及delivery-verification为准。

## 运行尚缺输入与实现边界

普通合成运行仍须已有授权应用DSN、schema32、正确park/org的精确SYNTHETIC preparation_catalog内容/hash/generation，已有会话及READ/PREPARE/REVIEW_ASSIGNED/EXECUTE与资源READ/HOLD等原权限；需要当前pack/journal、绝对路径/hash、私有journal权限、精确DB/目录绑定和普通worker。原用户明确输入诉求/目标、两槽有来源正文，再由原专员/企业分别REVIEW/CONFIRM。继续P3必须另有该精确Run的既有合法executor assignment；页面及本片不创建它，不能靠fixture回填。需要资源批准的动作仍须原合法批准输入。

NativeRunAccess permit/writer继续默认拒绝，configured provider接线未因此补全。正式来源仍缺来源专用的独立证明核验、当前head/撤销、Case/Run/已采纳方案/当前主体授权绑定及正式资源批准映射等产品代码；也缺有权来源结构、稳定ID/修订/指纹协议、既有记录与授权/信任合同及获准只读宿主接线。不能仅补凭据、自报REAL或使用IsolatedPlanApproval测试fixture当普通合法批准。具体合同见[原合成配置](LocalSyntheticDemoContract-20261017.md)与[正式来源缺项](FormalPreparationEntry-20261017.md)。

全部正向实测都是Linux隔离合成夹具；HTTP坏响应为客户端故障注入。未验Windows、正式AT、真实主体/业务/来源、生产host接线或真实模型，完整项目尚未完成。普通运行没有新增身份、Grant、assignment、目录发布、批准或凭据；既有回归中的显式合成角色、权限和assignment仅属隔离夹具初态，不能迁入普通运行。不新增费用或安全网络权限，没有改main、强推或部署。
"""
(root/'docs/F2/PreparationReadWriteTiming-20261017.md').write_text(body)
print('report written')
