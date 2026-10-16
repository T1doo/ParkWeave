from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID
import ast,hashlib,importlib.util,json,sys
root=Path('/workspace/ParkWeave');sys.path.insert(0,str(root/'src'))
from parkweave import controlled_plans as cp
file=root/'.runtime/p3-closure-backend/candidate-v3/src/parkweave/p3_never_accepted_closure.py'
spec=importlib.util.spec_from_file_location('parkweave._closed_candidate_v3',file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert Path(m.__file__).resolve()==file.resolve()
baseline=next((root/'.runtime/p3-closure-root/dev/core01/p3-fixture').glob('positive-closed-history-original-tail-cold-get-*.json'))
v=json.loads(baseline.read_text());q=v['qualification'];context=v['new_receipt']['delivery_binding']['context'];data=SimpleNamespace(expected_previous_plan_id=UUID(q['previous_plan_id']))
m.validate_qualification(q,data,context)
fields=['birth.generation','dispatch.id','dispatch.current_offer_id']+[f'verified_prefix.{i}.{k}' for i in range(2) for k in ('step_id','event_id')]+[f'dispatch.events.{i}.{k}' for i in range(len(q['dispatch']['events'])) for k in ('id','offer_id')]
def get(obj,path):
 for token in path:obj=obj[int(token)] if isinstance(obj,list) else obj[token]
 return obj
rows=[]
for name in fields:
 parts=name.split('.');old=get(q,parts)
 for mode,value in [('bool',True),('float',1.2),('none',None),('list',[]),('dict',{}),('uppercase',old.upper()),('hex',UUID(old).hex),('braced','{'+old+'}'),('urn','urn:uuid:'+old)]:
  assert value!=old
  changed=deepcopy(q);target=get(changed,parts[:-1]);target[int(parts[-1]) if isinstance(target,list) else parts[-1]]=value
  if name=='birth.generation':
   changed['birth_sha256']=cp._hash(changed['birth'])
   for event in changed['dispatch']['events']:event['business_frontier']['generation']=value
  if name=='dispatch.current_offer_id' or name.endswith('offer_id'):
   for event in changed['dispatch']['events']:
    if event['offer_id']==old:event['offer_id']=value
   if changed['dispatch']['current_offer_id']==old:changed['dispatch']['current_offer_id']=value
  try:m.validate_qualification(changed,data,context);result='ACCEPTED'
  except Exception as exc:result=type(exc).__name__
  rows.append(dict(field=name,mutation=mode,result=result))
assert all(x['result']=='ValueError' for x in rows),[x for x in rows if x['result']!='ValueError']
a=ast.parse((root/'.runtime/p3-closure-backend/source-v2/src/parkweave/p3_never_accepted_closure.py').read_text());b=ast.parse(file.read_text())
strip=lambda tree:ast.dump(ast.Module(body=[n for n in tree.body if not isinstance(n,ast.FunctionDef) or n.name!='validate_qualification'],type_ignores=[]),include_attributes=False)
assert strip(a)==strip(b)
out=dict(scope='PURE_ONLY_NO_PG_HTTP',baseline_path=str(baseline),baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),baseline_pass=True,actual_validator_path=str(file),actual_validator_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),only_validate_qualification_changed=True,mutations=rows)
(root/'.runtime/p3-closure-backend/pure-v3/result.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(baseline_pass=True,mutations=len(rows),rejected_valueerror=len(rows),only_validate_qualification_changed=True,sha256=out['actual_validator_sha256'])))
