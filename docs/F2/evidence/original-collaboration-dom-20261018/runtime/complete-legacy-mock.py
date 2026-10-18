from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/original-collaboration-dom-20261018';assert (r/'repair-result.json').exists(),'wait for known-bad immutable window to finish'
reference=(root/'tests/multi_goal_overview_actual.js').read_text();complete=next(line for line in reference.splitlines() if line.startswith(' constructor('));assert len(complete)==634 and 'contains:' in complete and 'remove:' in complete
files=['manual_goals_actual.js','manual_goal_tasks_actual.js','manual_goal_tasks_late_actual.js','manual_goal_reply_actual.js','manual_goal_recheck_actual.js','partial_service_plan.js'];records=[]
for name in files:
    path=root/'tests'/name;old=path.read_text();current=next(line for line in old.splitlines() if line.startswith(' constructor('));assert len(current)==499 and complete.startswith(current)
    new=old.replace(current,complete,1);path.write_text(new);p=subprocess.run(['node','--check',str(path)],cwd=root,capture_output=True,text=True,timeout=15);(r/('complete-syntax-'+name+'.stdout')).write_text(p.stdout);(r/('complete-syntax-'+name+'.stderr')).write_text(p.stderr)
    records.append(dict(path='tests/'+name,before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(new.encode()).hexdigest(),syntax_exit_code=p.returncode,complete_constructor_equals_existing_reference=True))
assert all(row['syntax_exit_code']==0 for row in records)
(r/'complete-syntax-check.json').write_text(json.dumps(dict(kind='six bounded syntax checks only; not pytest/business PASS',reference='tests/multi_goal_overview_actual.js',records=records),indent=2)+'\n');print('copied complete constructor and six syntax checks succeeded')
