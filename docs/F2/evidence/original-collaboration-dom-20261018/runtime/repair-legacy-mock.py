from pathlib import Path
import hashlib,json
root=Path('/workspace/ParkWeave');r=root/'.runtime/original-collaboration-dom-20261018';result=json.loads((r/'final-result.json').read_text());assert result['unique']==301 and result['passed']==282 and result['failures']==19 and result['errors']==0
files=['manual_goals_actual.js','manual_goal_tasks_actual.js','manual_goal_tasks_late_actual.js','manual_goal_reply_actual.js','manual_goal_recheck_actual.js','partial_service_plan.js']
reference=(root/'tests/multi_goal_overview_actual.js').read_text();start=reference.index("this.className='';const tokens=");end=reference.index(';}',start)+1;extension=reference[start:end]
probe=next(line for line in reference.splitlines() if line.startswith('const classProbe='))
records=[]
for name in files:
    path=root/'tests'/name;old=path.read_text();needle='this.style={};this.listeners={};}';assert old.count(needle)==1 and 'classList' not in old
    new=old.replace(needle,needle[:-1]+extension+'}',1);marker='\nlet delayedResponse' if '\nlet delayedResponse' in new else '\nconst lines='
    assert new.count(marker)==1;new=new.replace(marker,'\n'+probe+marker,1);path.write_text(new)
    records.append(dict(path=str(path.relative_to(root)),before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(new.encode()).hexdigest(),change='same stateful className/classList and existing local probe; no business assertions/budgets altered'))
(r/'legacy-mock-repair.json').write_text(json.dumps(dict(reference='tests/multi_goal_overview_actual.js:6,13',records=records,original_failures=19,production_source_changed=False),indent=2)+'\n')
print('repaired six existing mock Element classes; no tests started')
