"""Prepare exact prefixes before gate; apply only after independent archive PASS."""
from pathlib import Path
import json,hashlib,sys
root=Path('.runtime/fact-provenance-delivery')
freeze=json.loads(Path('.runtime/fact-assertion-provenance-root/freeze-v2.json').read_text())
paths=['docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md']
sha=lambda b:hashlib.sha256(b).hexdigest()
if sys.argv[1]=='prepare':
 summary=json.loads(Path('.runtime/fact-assertion-provenance-root/final-regression-verification.json').read_text());record={}
 for index,name in enumerate(paths):
  p=Path(name);data=p.read_bytes();assert sha(data)==freeze['all_tracked_sha256'][name]
  link=('' if p.parent==Path('docs/F2') else 'F2/')+'EmployeesFactProvenance-20261015.md'
  prefix=f'''## 2026-10-15 F3-T02/T03：已选员工自述来源与原采纳闭环

冻结源码 `{freeze['source_sha']}`。新增已有Case中employees USER_ASSERTED_SYNTHETIC已选断言的细粒度来源；从原注册描述符重建原账本前缀与实际回执，不用当前事实填历史。本人原事实确认、机会刷新、明确预览、原ADOPT、必要业务补正和VERIFY到六目标本地证据/清单；未知拒绝，原六目标/P1–P5、历史及未影响锁保留。细节点不缩小原重验范围，不判断语义、真实性或授权。

同SHA最终所选集合的103完整相关模块/{summary['unique_passes']}唯一项PASS，0FAIL/ERROR/SKIP；新61项含4完整HTML→真实HTTP/ASGI/自有PG，原键冷GET/撤权/迟到/ABA/幂等冲突与默认v2兼容。另CI模块、独审38纯测试及6受控客户端分支分列；原root-2完整窗788P/1F及开发夹具/机械I/O失败原件保留；时序敏感前置失败所在完整30项以一次原预算低负载整模块复验替代，不推断唯一原因，不迁旧SHA成绩。[实际回执、设计覆盖与边界]({link})。

本片仅一种自述来源，MANUAL/双槽/模板组合增强路径尚不支持，原默认路径保持。一般材料语义、更多细粒度来源、一般传播/动态图、复杂在途升级/F5-T04、备份恢复和正式治理/Approval仍待补。继续按一周目标推进。Windows、真实浏览器、正式AT、人工语义、真实模型/B0–B2及生产未执行；旧181窗未采GET幂等键的边界保留，新冻结按实际请求记录该键。main与旧分支只读，未部署/强推/新增费用或安全权限，真实产品模型调用0。下方旧历史逐字保留。

'''.encode()
  q=root/('history-prefix-'+str(index)+'.md');q.write_bytes(prefix)
  record[name]=dict(old_sha256=sha(data),old_bytes=len(data),prefix_path=str(q),prefix_sha256=sha(prefix),prefix_bytes=len(prefix))
 (root/'history-prefix-prepared.json').write_text(json.dumps(record,indent=2)+'\n')
elif sys.argv[1]=='apply':
 gate=json.loads(Path(sys.argv[2]).read_text());assert gate['status']=='PASS' and gate['source_sha']==freeze['source_sha']
 record=json.loads((root/'history-prefix-prepared.json').read_text())
 for name,r in record.items():
  p=Path(name);old=p.read_bytes();prefix=Path(r['prefix_path']).read_bytes();assert sha(old)==r['old_sha256'] and sha(prefix)==r['prefix_sha256']
  p.write_bytes(prefix+old);assert p.read_bytes()[len(prefix):]==old;r['new_sha256']=sha(p.read_bytes())
 (root/'history-prefix-receipt.json').write_text(json.dumps(record,indent=2)+'\n')
else:raise ValueError('prepare/apply required')
