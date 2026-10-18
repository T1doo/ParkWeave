from pathlib import Path
import json
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018'
a=json.load(open(r/'accepted-tests.json'));v=json.load(open(r/'final-focused-summary.json'));ind=json.load(open(r/'independent-final-review.json'))
assert ind['source_sha']==a['source_sha'] and ind['passed']==ind['actual_unique_nodes']==77 and not any(ind[k] for k in ('failures','errors','skipped','blockers'))
assert ind['overlap_in_focused161']['all_nodes_present'] and ind['overlap_in_focused161']['additional_unique_tests']==0
e='evidence/dispatch-accept-recovery-20261018/'
rows='\n'.join('| `'+m+'` | '+str(n)+' |' for m,n in sorted(v['modules'].items()))
text=f'''# 普通接单 ACCEPT 原键只读冷恢复

继续原 F2-T05/AT19–20 的未知结果路径。交付基线 `25d2b524cbc0fa80fda9eed4b86b64b1cf647984`；产品实现冻结 `35031ba7334006089889f6488dfbe1feb5bc10b4`，最终源码/测试冻结 `{a['source_sha']}`，产品 src 树均为 `e0f8443127b49b5feb9e1b880e8998ca67b5c404`。普通开发分支 `dev/f2-demo-original-page-intake-20261017`，仍由当前代理唯一写源码/Git；原已 completed 任务没有恢复写入。

## 最小用户路径

此前普通 ACCEPT 已有 actor/key/fingerprint 的事务事件和原子回执 CREATE，但没有对应 GET；页面 pending 只在内存。新 GET `/api/service-dispatches/{{dispatch_id}}/accept-recovery` 复用原身份、READ、精确 Run assignment、tenant/preparation scope、actor/key 锁及两份原事件，比较原 offer、资料/Case/Run、原 revision，以及 ACCEPT 与 CREATE 的相同已存 fingerprint。响应只含历史元数据，无 reason/材料/会话，不提供动作、Grant 或批准；不重算或重做原接单/分派/回执算法，不新增表或 SQL 权限。

COMMITTED 仅证明原 actor/key 对应原 offer/version 的 ACCEPT 与原回执 CREATE 相互一致，不恢复或核验用户草稿说明。NOT_OBSERVED 仅表示当前未观察到提交，原请求仍可能稍后到达；不是已回滚或允许重发。当前权限撤销仍统一403，历史成功不恢复权限。使用原事务的共享/建议锁；代码无业务DML，不冒称数据库级 READ ONLY transaction。

页面在第一次原 ACCEPT POST 之前保存固定 12 字段的 opaque 句柄：actor hash、原对象/offer/key、revision 与期限；无 token、reason 或请求正文。每项最多640字符、每 actor最多8项、严格有限未来24小时；重复读取不延长期限。损坏/超限/过期保留字节并停止新写入，不能删除未知句柄后重做。全局 storage 未决检查在导航、身份切换及冷启未读取原单前继续阻断新写入；不同身份的句柄不当授权。

已收到成功响应时也通过同一 GET 原事件证明及当前 GET 读回后再结束；未知回包只允许用户明确“只读核对原接单”，随后明确“核对后读取当前状态”。从未重发 ACCEPT，也不自动 P3 VERIFY、创建批准或领取权限。每层 await 后复核当前身份/导航代次/原 raw；当前视图须绑定原本人 lineage，渲染成功后才对完全相同 raw 删除，迟到200/403、Case/身份ABA或替换句柄不能释放新记录。DECLINE/WITHDRAW/OFFER、普通回执SUBMIT/ACK没有因此获得通用冷恢复协议。

## 实际验证与初态

**最终8个完整直接相关模块，{v['unique']}唯一pytest项PASS，0FAIL/ERROR/SKIP**。两分片按完整模块互不重叠，每节点一次，无自动重试；外层最大窗口 {v['elapsed_max_seconds']:.3f}秒；各 {v['input_count']} 个源码/测试/脚本/合同输入 PRE/POST 零漂移。全体来自上述最终冻结，新67项已含内，不搬旧296、开发或独测分数。此前bfb的24完整模块实际576唯一项575PASS/1FAIL、745输入零漂移，原296与新67逐ID都PASS；唯一旧过期fixture在进入目标锁前P5准备409。该广回归不是全绿，旧成绩没有转签到最终冻结，也不相加。不是全仓或正式AT。

[调用A]({e}runtime/final-focused-A-invocation.json)、[调用B]({e}runtime/final-focused-B-invocation.json)、[完整JUnit]({e}runtime/final-focused-pytest.xml)、[去重/输入结算]({e}runtime/final-focused-summary.json)。

| 完整模块 | 唯一PASS |
| --- | ---: |
{rows}

新API31项是实际ASGI/自有PG：COMMITTED/NOT_OBSERVED、原请求后来到达、当前READ/身份/Run assignment撤销、跨 actor/tenant/Case/offer/版本/键、严格重复/额外参数、错误原子证据及材料后来修订。正向case_history及权限快照无漂移；跨scope/撤权/坏证据等反例的records另外覆盖dispatch/receipt/notice表，不把未逐项断言的表称为全部覆盖。负向fixture的撤权/破坏只发生在明确自有合成库。

新31项 Node VM执行实际窄生产函数，固定时钟和受控 Promise：期限/形状/空间界限、错误证明、换 raw、迟到200/403、内外层await身份/Case ABA、当前GET非法history/role/revision/offer/executor及renderer异常；均无实际HTTP，不冒称浏览器或真实来源。renderer异常用stub表示异常边界。

新5项是实际 Chromium→普通 configured_app 独立子进程→自有PG。初态由明确合成 fixture 在普通启动之前准备原材料REVIEW/CONFIRM、该精确Run已有executor assignment及OFFER，绝不是普通运行补权或新真实业务。实际原 ACCEPT 提交后故意丢回包、原请求晚到、当前撤权、同端口普通API进程重启与页面冷启、真实GET后故障注入坏history：恢复区间页面 request 事件观察均只有GET；原key保留直到可信当前读回，无重复回执/自动P3。晚到场景由测试人工投递截获的原请求，恢复UI不重发；页面request观察不包括route.fetch与该人工动作，不是全网络trace。导航/冷启先切原owner尝试另建Run时0POST、runs计数不变。坏200明确由测试在真实GET后注入，不声称后端会产生它。320宽度截图/日志/JSON均保留。

独立精确镜像静审0剩余P1/P2阻断，实跑77PASS/0FAIL/ERROR/SKIP，全部与最终161重叠，不相加。共享与镜像各{v['input_count']}输入 PRE/POST 零漂移；实际pytest的parkweave模块来源逐个指向mirror/src；普通子API沿原helper固定镜像PYTHONPATH启动，未额外插桩其import origin。[独审/独测]({e}runtime/independent-final-review.json)。

原已有Run DOM全链2项继续只签 LOCAL_OUTPUT_VERIFIED/case_goal_completed=false；它们没有新增对6个精确goal ID或跨Case攻击的独立断言。本片新跨Case接口反例只针对ACCEPT恢复协议，不能转签整个六目标业务。

## 失败、中断、修补与证据

首API red真实404；开发31项中的7FAIL是测试误写原统一403文案，改回原合同后31PASS。旧handoff窄VM有6项 entryFailureFlows ReferenceError；冻结25d2同输入实跑一例复现，补入实际源码两行依赖后9PASS，没有改业务或空实现。

首冻结35031 A完整397项为393PASS/4FAIL，4项均旧取消renderer窄VM遗漏新dispatchAcceptRead；补实际源码helper及actor_ref。首B的外层会话Ctrl-C退出130，当时无XML，后验发现子pytest仍继续；最终自然完成178项177PASS/1FAIL，4个测试输入已在后续修补中改变，**0项计入验收**。不是用户暂停；外层退出从不证明整个进程树已停。尝试/proc精确发现时只见当前调用的隔离命名空间，断言在发信号前结束；没有提权或操作未知进程。原初始观察与最终[对账]({e}runtime/first-B-final-reconciliation.json)分开保留。其后restart单例实跑FAIL明确为测试helper重绑旧端口OSError98，补自有loopback端口SO_REUSEADDR；不是新增安全网络权限。修补两旧夹具和端口后53项PASS，再冻结bfb执行24模块，实际575PASS/1FAIL。

开发浏览器一轮5PASS期间2输入发生漂移，不计验收；导航反例一轮3FAIL定位为阻断handler遗漏preventDefault导致浏览器默认刷新，修补后3PASS。最后仅修未通过的旧fixture：采用仓库已有10秒准备、持有原lifecycle行锁后才逼近1.5秒期限的模式；发读前SQL证实两资源均存活且剩余不超过2秒，观察到真实waiter后再次证实存活，持锁至DB实际到期后才释放。原3秒锁、1秒waiter、5秒future和全部负断言不变；新增tmp JSON保存三次真实SQL时钟见证。旧窗只证明P5前置409，没有SQL时钟证明唯一致因，不能回写为已证实过期。修后完整30PASS，再以最终测试冻结重跑上述8模块。产品src字节完全不变。

所有失败/中断/调用/输入hash保留；不把开发成绩或旧窗口改写为本轮通过。静审发现并修补4项P2（全局冷启阻断、外层await复核、先完整渲染再raw CAS删除、当前本人lineage）。

[bfb广回归结算]({e}runtime/final-v2-broad-summary.json)与[完整失败XML]({e}runtime/final-v2-broad-pytest.xml)保留575/1原状。旧恢复测试的固定目录输出跨残留窗口共用，未将共享截图归属某个最终窗口；新5项截图均来自各自tmp_path。

[manifest]({e}manifest.json)是raw/public哈希映射，[结构与哈希校验]({e}archive-validation.json)验证实际结构。临时会话候选脱敏保留私有原字节；仅以Git路径与AST证明静态标识豁免，避免再次误遮蔽测试ID。故意oversize的非法JSON输入按精确路径/测试ID/SHA单列，不按结构产物解析；PG data不导出。继承29851证据blob中29831原样，另外20件仅已授权测试标识更正（18件及manifest/校验）；旧副本保留，[整合校验]({e}runtime/identifier-correction-integration.json)。此次标识更正没有重跑旧296。

## 普通运行仍需输入与未实现项

| 输入/缺口 | 精确边界 |
| --- | --- |
| 原受限DB、已迁移schema、已有有效会话及当前身份/tenant/park/org | 由既有运维提供；本片没有创建凭据或主体 |
| 原owner PREPARE/EXECUTE、reviewer REVIEW_ASSIGNED/READ、executor READ及精确Run合法assignment | 普通读取/写入继续原授权检查；缺项准确拒绝，fixture不能迁入普通运行补权 |
| 已存在Case/Run/preparation、原材料来源/当前修订与REVIEW/CONFIRM、精确preparation_catalog | GET绑定这些原对象；没有目录时不能通过label或同UUID代替 |
| 本片冷恢复的原 actor/key/offer/原revision、未损坏句柄与当前原对象读取权 | 丢失/过期/损坏或NOT_OBSERVED不会自动解锁或重做；须原事件/运维人工核对 |
| 当前本地合成profile的pack/journal、路径/hash、DB/目录绑定与原资源权限 | 只用于原明确LOCAL_SYNTHETIC_DEMO；不是合法正式业务来源证明 |
| NativeRunAccess可信宿主、原签名绑定/当前head/撤销及普通provider完整接线 | permit/writer仍默认拒绝；没有新增Grant或分派写入，不能只加密码即开通 |
| 正式来源的source-specific结构、四对象映射、主体授权依据、当前revision/head/签名/撤销及独立验真合同 | 未实现的来源合同保持UNAVAILABLE；需据既有来源规范继续写adapter/验真，不能自报REAL |
| 正式方案采纳和独立资源批准的既有决定/版本/来源/主体/有效期/撤销绑定 | 原资源批准只读接口继续独立；IsolatedPlanApproval不能作普通批准 |

详见[正式来源缺项](FormalPreparationEntry-20261017.md)和[原合成配置](LocalSyntheticDemoContract-20261017.md)。Windows/Win11、正式AT/AT35、真实主体/资料/业务、生产宿主/部署、真实模型及现实履约均未验；完整项目仍未完成。没有main修改、强推、部署、新费用、新真实身份/Grant/分派/目录发布/批准/凭据或安全权限扩大，未知锁保留。
'''
(root/'docs/F2/DispatchAcceptRecovery-20261018.md').write_text(text)
