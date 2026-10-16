from pathlib import Path
import json,hashlib,sys
r=Path('.runtime/unified-propagation-delivery');f=json.loads(Path('.runtime/unified-propagation-root/freeze.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
paths=['docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md']
if sys.argv[1]=='prepare':
 v=json.loads(Path('.runtime/unified-propagation-root/final-regression-verification.json').read_text());assert v['status']=='PASS';records={}
 for i,n in enumerate(paths):
  p=Path(n);old=p.read_bytes();assert sha(old)==f['all_tracked_sha256'][n]
  link=('' if p.parent==Path('docs/F2') else 'F2/')+'UnifiedSourcePropagation-20261016.md'
  prefix=f'''## 2026-10-16 F3-T03：有限多来源统一传播与原局部修订

冻结源码 `{f['source_sha']}`。复用原机会卡plan-revision与原ADOPT，以显式dependency_scope生成独立schema2/source-change v4；固定来源族共享节点，每步骤保留独立历史观察，仅变化观察边经原PRECEDES传播，不能共享node扇出误伤已核新版步骤。保留原schema1/v1/v2/员工v3、原六目标/P1–P5、正文/UUID、历史与未影响锁；未知扩大本Case并拒绝，不造一般语义或任意图/新字段端点。

同SHA107完整相关模块/{v['unique_passes']}唯一pytest项PASS，新增88含在总数；原2秒预算完整30项（1模块）从开始即安排最后独占运行，预算未改。原CI完整窗432P1F14S保留：0.6秒超时已返回124但子进程stdout空；空闲后完整12模块仅一次原预算重跑433PASS/14原Windows/PowerShell前提SKIP，独审66纯项及8受控分支与主集合重叠不相加。4完整HTML→nativeHTTP/ASGI/自有PG共136页面请求，正向/丢回执原ADOPT+5VERIFY→六目标及清单，当前与迟到403隔离。WIP34P11F/40P5F、路径修正及客户端strict原件保留，不迁成绩。[实际统计、36行分层映射和归档]({link})。

材料/事实/资源集合/回执混合可沿原明确确认与业务补正闭环；目录合同规则变更仍CATALOG_CHANGED拒绝局部ADOPT，未绕原替换规则。MANUAL/DEFER/保留继续与UNLOCK仍原命令。小范围来源结构证明不代表事实、授权、现实履约或Case正式完成。

按一周目标继续更多明确来源覆盖、复杂在途升级/F5-T04、备份恢复、正式治理及运行前提；Windows、真实浏览器、正式AT、真实模型B0–B2、生产及本分支远端CI未执行。main和旧分支只读，未强推、部署、新费用/凭据/安全权限或绕拒绝，真实产品模型0。下方历史逐字保留。

'''.encode()
  q=r/('history-prefix-'+str(i)+'.md');q.write_bytes(prefix);records[n]=dict(old_sha256=sha(old),old_bytes=len(old),prefix_path=str(q),prefix_sha256=sha(prefix),prefix_bytes=len(prefix))
 (r/'history-prefix-prepared.json').write_text(json.dumps(records,indent=2)+'\n')
elif sys.argv[1]=='apply':
 g=json.loads(Path(sys.argv[2]).read_text());assert g['status']=='PASS' and g['source_sha']==f['source_sha'];records=json.loads((r/'history-prefix-prepared.json').read_text())
 for n,row in records.items():
  p=Path(n);old=p.read_bytes();prefix=Path(row['prefix_path']).read_bytes();assert sha(old)==row['old_sha256'] and sha(prefix)==row['prefix_sha256'];p.write_bytes(prefix+old);assert p.read_bytes()[len(prefix):]==old;row['new_sha256']=sha(p.read_bytes())
 (r/'history-prefix-receipt.json').write_text(json.dumps(records,indent=2)+'\n')
else:raise ValueError('prepare/apply required')
