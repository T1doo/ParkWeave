from pathlib import Path
import json,hashlib,sys,ast,inspect
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID
sys.path.insert(0,str(Path.cwd()/'src'))
from parkweave import p3_never_accepted_closure as qv,service_plan_approval as spa,controlled_plans as cp
p=next(Path('.runtime/p3-closure-root/dev/core01/p3-fixture').glob('positive-closed-history-original-tail-cold-get-*.json'));v=json.loads(p.read_text());q=v['qualification'];context=v['new_receipt']['delivery_binding']['context'];data=SimpleNamespace(expected_previous_plan_id=UUID(q['previous_plan_id']))
qv.validate_qualification(q,data,context)
rows=[]
for field in ('dispatch.id','dispatch.current_offer_id','dispatch.events.0.id','dispatch.events.0.offer_id','verified_prefix.0.step_id','verified_prefix.0.event_id'):
 original=q
 for token in field.split('.'):original=original[int(token)] if isinstance(original,list) else original[token]
 for mode,value in [('bool',True),('float',1.2),('none',None),('uppercase',original.upper()),('hex',UUID(original).hex),('braced','{'+original+'}'),('urn','urn:uuid:'+original)]:
  changed=deepcopy(q);parts=field.split('.');target=changed
  for key in parts[:-1]:target=target[int(key)] if isinstance(target,list) else target[key]
  target[parts[-1]]=value
  if field in ('dispatch.current_offer_id','dispatch.events.0.offer_id') and isinstance(value,str):
   for event in changed['dispatch']['events']:event['offer_id']=value
   changed['dispatch']['current_offer_id']=value
  try:qv.validate_qualification(changed,data,context);result='ACCEPTED'
  except Exception as exc:result=type(exc).__name__
  rows.append(dict(field=field,mutation=mode,result=result))
source=inspect.getsource(spa._ledger);tree=ast.parse(source);handlers=[ast.unparse(h.type) for h in ast.walk(tree) if isinstance(h,ast.ExceptHandler)]
out=Path('.runtime/p3-closure-review/strictq-development-v1/result.json');out.write_text(json.dumps(dict(scope='PURE_VALIDATOR_ONLY_NO_PG_HTTP',baseline_path=str(p),baseline_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),baseline_pass=True,actual_validator_path=qv.__file__,actual_validator_sha256=hashlib.sha256(Path(qv.__file__).read_bytes()).hexdigest(),mutations=rows,ledger_outer_handlers=handlers),indent=2)+'\n');print(json.dumps(dict(rows=len(rows),accepted=sum(x['result']=='ACCEPTED' for x in rows),results={s:sum(x['result']==s for x in rows) for s in set(x['result'] for x in rows)},ledger_outer_handlers=handlers)))
