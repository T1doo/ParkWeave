"""Prepend actual verified slice; retain every original byte as suffix."""
from pathlib import Path
import hashlib,json
r=Path('.runtime/plan-reapproval-root');load=lambda p:json.loads(p.read_text());f=load(r/'freeze.json');v=load(r/'final-regression-verification.json');assert v['status']=='PASS'
sha=lambda b:hashlib.sha256(b).hexdigest()
paths=['docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md'];records={}
for n in paths:
 p=Path(n);old=p.read_bytes();assert sha(old)==f['all_tracked_sha256'][n]
 link=('' if p.parent==Path('docs/F2') else 'F2/')+'PlanSourceReapproval-20261016.md'
 prefix=f'''## 2026-10-16 F2-T03/T05：来源变更后的明确再批准与原资源交付

冻结源码 `{f['source_sha']}`。同Case、同稳定计划从原机会真实来源刷新、预览、明确局部ADOPT，进入原PROPOSE/明确APPROVE→新HELD资源原COMMIT/重绑定/CONSUME同事务→受影响VERIFY→六目标及工作清单读取。复用原角色和capability，只有原已签发自有PG合成fixture显式开启，默认关闭；不是生产Approval/自动批准/新授权。绑定旧link/snapshot/批准计划、新source ADOPT及版本/资源/有效期；陈旧批准、去profile/重哈希/自引用、双proof缺失及后续link伪装首次均拒绝。原历史、原六目标/P1–P5、未影响锁及旧资源占用保留。

同SHA134个完整相关模块/{v['unique_passes']}唯一pytest项PASS，新增4模块54项已在总数；CI原12完整模块独占433P/14原Windows前提SKIP，其后原2秒预算完整30项独占一次。独审完整client8PASS与11pure协议探针分列，不重复相加。4原HTML→native HTTP/ASGI/自有PG覆盖正向/提交丢回执/当前与迟到403；4实际Chromium模式覆盖正向及COMMIT/PROPOSE/APPROVE丢回执原键冷GET，随后P2–P5、六目标/清单。浏览器源刷新/ADOPT/P1使用原Python前置，不移植Node负向成绩。WIP失败、修正及所有原件保留；32行独立设计按实证分类，NOT_RUN明确。[实际范围、分层映射及归档]({link})。

继续按一周目标推进更多明确来源、复杂在途升级/F5-T04、备份恢复与正式治理/运行前提。本片不扩大到复杂迁移。Windows/Win11、正式AT、真实模型B0–B2、现实履约及生产未执行；限定Linux本地Chromium四模式不代表全面浏览器验收。清单仍recorded_states_only/evidence_verified=false/case_goal_completed=false，不是现实完成。main与旧分支只读；无强推/部署/新费用/凭据/安全权限/绕拒绝，产品真实模型0。下方历史原字节保全。

'''.encode()
 p.write_bytes(prefix+old);assert p.read_bytes()[len(prefix):]==old
 records[n]=dict(old_sha256=sha(old),old_bytes=len(old),prefix_sha256=sha(prefix),prefix_bytes=len(prefix),new_sha256=sha(p.read_bytes()),exact_original_suffix=True)
(r/'history-prefix-receipt.json').write_text(json.dumps(records,indent=2)+'\n');print('Four history prefixes; original bytes retained exactly')
