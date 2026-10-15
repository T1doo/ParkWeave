from pathlib import Path
import json
b=Path('.runtime/at24-27-root');d=json.loads((b/'final-regression-verification.json').read_text());assert d['status']=='PASS' and d['unique_testcases']==2617 and d['complete_modules']==90
text=(b/'delivery-draft.md').read_text().replace('C25 六变化及 C26混合','C25五场景、另列目录UNKNOWN变体及C26混合')
block='''正式统一冻结 SHA：**`5a7eee826564426a4c36607ac038bd61e00665d7`**。五个不重叠窗口合计 **90个完整相关模块、2617个唯一测试，0 FAIL/ERROR/SKIP**，不是全仓运行。原72模块完整重跑，并依据首轮失败揭示的公共入口消费者清单补充18完整模块；不延用77059旧窗成绩。

| 窗口 | 完整模块 | PASS | runner耗时 |
| --- | ---: | ---: | ---: |
'''
for r in d['window_results']:
 block+=f"| {Path(r['path']).stem} | {r['modules']} | {r['counts']['PASS']} | {r['elapsed_seconds']:.3f}s |\n"
block+='''
各窗实际原始collection/JUnit精确一致且唯一，五窗模块/节点并集不重叠；605个受控源码路径及原12417 tracked文件在文档/新证据提交前与冻结清单一致。根同时复核上一批归档273个私有原件hash/大小均无变化。原始命令、开始/结束UTC、before/after、源码与完整文件清单见[五窗并集](evidence/at24-27-change-batch-20261015/at24-27-root/final-regression-verification.json)，没有对本轮原始nodeid归一或删项。独审[精确新SHA报告](evidence/at24-27-change-batch-20261015/at24-27-review-v2/freeze-5a7eee8-review.md)无阻断；另20项实际页面函数NodeVM探针重新通过，0.119404s，与2617完整模块项及完整HTML流分开。

[逐AT结果与20场景映射](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-per-at.json)、[完整独测交接](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-handoff.json)、[原始精度统计](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-oracle-statistics.json)。20固定设计场景全部对应通过节点；设计场景、pytest项、观测记录、步骤对分别统计，不混为同一分母。新批35条传播记录：known27条/100应影响步骤对，保守UNKNOWN8条/40对，漏更/误更/误保留均0，无额外未声明UNKNOWN。35条记录没有locked字段，不能把0锁字段说成35条锁测试：实际已选容量两Case各自P1锁逐字保持、原预约/历史保全、原比较与明确重绑后六目标均核验，单列2例。原preflight本窗重跑known15/62对、UNKNOWN4/20对，受影响锁交集3/3、错锁0；typed8known/23对、2声明UNKNOWN/10对及另1实际UNKNOWN/5对分列；shared8known/14对和4UNKNOWN/10对分列。各组漏更/误更/误保留均0。

[41条完整HTML轨迹](evidence/at24-27-change-batch-20261015/at24-27-independent/independent-v3-html-summary.json)：typed6/shared9/preflight14/new12，均在本轮实际执行并核原件hash。新12严格分9真实后端响应模式与3受控客户端异常/坏DTO模式（late JSON、transport、bad UNKNOWN）；全41含5条DOM/transport负向，不称41条都为真实后端拒绝。Node捕获957个实际HTTP请求，Python test-body捕获6109个loopback HTTP请求，不声称包含全部fixture setup。原完整HTML由NodeVM/DOM替身执行，服务为真实HTTP/ASGI/自有PostgreSQL，真实浏览器仍NOT_RUN。

真实说明GET403直接before/after无业务写另列2例；5次原GET观察导致当前invalidated字段变化单列，其他业务/历史表无变化，既有authorization_audit拒绝审计不算业务事实变化。实际已选容量的原比较/新hold/明确rebind没有省略；原第一次交付Approval保留，替代正式批准仍NOT_IMPLEMENTED。MIGRATE422仅证明封闭类型拒绝；BREAKING完整apply409有当前完整proof，superseded403不声称执行业务回滚。UNKNOWN真实行界由实际130新资源触原256 joined-row界，扩大重验且拒绝采纳；不是成功完整反向遍历。schema1实际投影/原页面parser与旧v1管理员夹具分别列证，不倒填新业务历史。
'''
old='正式精度统计、逐窗结果、完整页面/HTTP数量及独立归档状态待同 SHA 窗口全部结束后填入，不引用开发分数代签。';assert old in text;text=text.replace(old,block)
text+='''
## 证据归档

ARCHIVE_SUMMARY_PLACEHOLDER

[主档索引](evidence/at24-27-change-batch-20261015/index.json)、[主档说明](evidence/at24-27-change-batch-20261015/README.md)、[根checkpoint](evidence/at24-27-change-batch-20261015/audit.json)、[独立最终门](evidence/at24-27-change-batch-audit-20261015/final-gate.json)、[独立附件索引](evidence/at24-27-change-batch-audit-20261015/final-artifact-index.json)。根checkpoint保留当时PENDING独审状态，后续结论见独立sibling，不覆盖原始失败或制造自引用。独立重构不导入根producer/verifier；known-token matcher有明确共享来源，不声称算法来源多样性。
'''
Path('docs/F2/AT24-27ChangeBatch-20261015.md').write_text(text)
