PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B - <<'PY'
import ast,json,subprocess
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from parkweave import bounded_planning as bp,controlled_plans as cp
from parkweave import service_selection as ss,service_capability_contract as contract
from parkweave import local_synthetic_demo as demo,local_demo_selections as ld
from parkweave import service_plan_candidates as old,service_selection_candidates as v4
from parkweave.store import Conflict,Denied

# Execute only the three pre-existing pure fixture builders and their constants.
tree=ast.parse(Path('tests/test_service_selection.py').read_text())
names={'release','instance','request','NOW','INTERVAL','BINDING'}
selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)]
ns=dict(bp=bp,deepcopy=deepcopy,datetime=datetime,timezone=timezone,digest=contract.digest,hash_release=contract.hash_release,hash_instance=contract.hash_instance,CHECKS=contract.CHECKS)
exec(compile(ast.Module(body=selected,type_ignores=[]),'<existing-pure-fixtures>','exec'),ns)
R,I,Q=ns['release'],ns['instance'],ns['request']; now=ns['NOW']; binding=ns['BINDING']
# Compare the old wrapper implementations against the new shared core.
base='e7cf6cabea6174a672667d7ae8af6a5238589791'
old_source=subprocess.check_output(['git','show',base+':src/parkweave/service_selection.py'],text=True)
old_tree=ast.parse(old_source)
prior=dict(vars(ss))
exec(compile(ast.Module(body=[n for n in old_tree.body if isinstance(n,ast.FunctionDef) and n.name in {'enumerate_solutions','rebuild_selection'}],type_ignores=[]),'<base-oracle-builders>','exec'),prior)
r=R();i=I(r); cases=[]
def case(label,rs,ins,req): cases.append((label,rs,ins,req))
case('unique',[r],[i],Q())
rs=[R(suffix='a'),R(suffix='b')];ins=[I(rs[0],'a'),I(rs[1],'b')]
case('multiple',rs,ins,Q())
for state in ('FALSE','UNKNOWN'):
 q=Q();q['mapping_states']['fields']['need_summary']=state;case(state,[r],[i],q)
case('unsupported',[r],[i],Q(['REAL_FULFILMENT']))
case('other-park',[r],[I(r,park='park-b')],Q())
case('no-instances',[r],[],Q())
q=Q();q.pop('mapping_states');case('missing-states',[r],[i],q)
q=Q();q['planning_constraints']['excluded_roles']=['park_specialist'];case('excluded-role',[r],[i],q)
q=Q();q['planning_constraints']['additional_requirements']=['SYNTHETIC unresolved'];case('unknown-requirement',[r],[i],q)
rs=[R(),R('synthetic-resource-coordination',['LOCAL_INTERNAL_ACCEPTANCE'],'b')];ins=[I(rs[0]),I(rs[1],'b')]
case('cross-service',rs,ins,Q(['LOCAL_MATERIAL_PREPARATION','LOCAL_INTERNAL_ACCEPTANCE']))
rebuilt=0
for label,rs,ins,q in cases:
 a=prior['enumerate_solutions'](rs,ins,q,now=now);b=ss.enumerate_solutions(rs,ins,q,now=now)
 assert a==b,label
 if a['state'] in ('UNIQUE','MULTIPLE'):
  s=dict(schema_version=1,binding=binding,selections=a['minimal_solutions'][0])
  assert prior['rebuild_selection'](s,rs,ins,q,binding,now=now)==ss.rebuild_selection(s,rs,ins,q,binding,now=now),label
  rebuilt+=1
 print('oracle '+label+'='+a['state']+' old_new_equal=true')
assert ss.enumerate_solutions([r],[],Q(),now=now)['state']=='UNSAT'
print('old_oracle_cases='+str(len(cases))+' rebuilt_graph_cases='+str(rebuilt))

value=dict(schema_version='parkweave-local-synthetic-demo-pack/1',kind='SYNTHETIC',id='demo-memory',revision=1,validity=ns['INTERVAL'],park_id='park-a',org_id='org-a',
 roles={x:'principal-'+x for x in ('enterprise_operator','park_specialist','service_executor')},resources={x:'resource-'+x for x in ('primary','secondary')},
 fields={x:dict(slot=x,input_field=x) for x in ('need_summary','material_outline')},services=['synthetic-material-preparation','synthetic-resource-coordination','synthetic-local-record-recheck'])
value=demo.pack(value);releases,instances=demo.contracts(value,'d'*64,now=now)
goals=sorted(set().union(*(set(r['supported_goals']) for r in releases)))
q=Q(goals)
snapshot=dict(scope=demo.PROFILE,revision=1,demo_pack=value,pack_sha256='d'*64,journal_sha256='e'*64,database_sha256='f'*64,releases=releases,instances=instances,mapping_states=q['mapping_states'],unknowns=[],business_publication=False,new_grants=False)
frozen=deepcopy(dict(steps=bp.REGISTRY,actions=bp.ACTIONS))
coverage,steps=bp.compile(goals)
base_doc=dict(preparation_id='00000000-0000-4000-8000-000000000001',case_id='00000000-0000-4000-8000-000000000002',run_id='00000000-0000-4000-8000-000000000003',preparation_revision=1,request_revision=1,catalog_sha256='a'*64,registry_sha256=cp._hash(frozen),legacy_source_sha256='b'*64,capability_catalog_sha256=cp._hash(cp._normal(snapshot)),profile=demo.PROFILE,catalog_snapshot=snapshot,selection_request=q,selection=None,source_unknowns=[],state='COVERED_PREVIEW_ONLY',required_goals=goals,goal_coverage=coverage,steps=steps,global_requirements=[],constraint_evaluation={})
base_doc['source_sha256']=cp._hash(dict(legacy_source_sha256=base_doc['legacy_source_sha256'],capability_catalog_sha256=base_doc['capability_catalog_sha256']))
pairs=demo.validated_pairs(snapshot,q,now=now);base_doc['selection_oracle']=ss._enumerate_pairs(pairs,q)
selection=demo.LocalDemoSelector().select(base_doc)
assert base_doc['selection_oracle']['state']=='UNIQUE' and len(goals)==6
window=dict(version=2,created_at=now.isoformat(),expires_at=(now+timedelta(seconds=old.VALIDITY_SECONDS)).isoformat(),seconds=old.VALIDITY_SECONDS)
data=ld.Capture(expected_preparation_revision=1,expected_source_sha256=base_doc['source_sha256'],expected_capability_catalog_sha256=base_doc['capability_catalog_sha256'])
record=dict(id='00000000-0000-4000-8000-000000000004',profile=demo.PROFILE,revision=1,actor_id=value['roles']['enterprise_operator'],request_key='memory-probe',fingerprint=ld._fingerprint(base_doc['preparation_id'],data),candidate_request=data.model_dump(),validity=window,base_document=base_doc,selection=selection,frozen_registry=frozen)
record['producer']=ld._producer(record)
saved=ld._apply(base_doc,selection,now=now);saved.update(candidate_validity=window,candidate_producer=record['producer'])
record.update(document=saved,candidate=ld.document(saved));record['candidate_sha256']=cp._hash(record['candidate'])
parent=dict(id=base_doc['preparation_id'],owner_id=record['actor_id'],planning_previews=[record])
ld._proof(parent,record)
view=ld.verify(parent,record,saved,now=now)
assert view['can_adopt'] and [s['id'] for s in view['steps']]==['P1','P2','P3','P4','P5']
assert not {'usage','call_id','budget_record','response_raw'}&record['producer'].keys()
rejected=0
for label,mutate in [
 ('bool-as-calls',lambda r:r['producer'].update(real_model_calls=False)),
 ('fake-model',lambda r:r['producer'].update(model='fake-model')),
 ('extra-usage',lambda r:r['producer'].update(usage={})),
 ('mixed-profile',lambda r:r.update(profile='TRUSTED_SERVICE_SELECTION_V4')),
 ('missing-selection',lambda r:r['selection']['selections'].pop()),
 ('changed-frozen-registry',lambda r:r['frozen_registry']['steps'][0].update(responsibility='changed'))]:
 altered=deepcopy(record);mutate(altered)
 try: ld._proof(parent,altered)
 except Conflict: rejected+=1
 else: raise AssertionError(label+' accepted')
print('demo goals=6 adapters=P1,P2,P3,P4,P5 unique=true NO_MODEL=true provenance_tamper_rejected='+str(rejected))
original_registry=bp.REGISTRY
try:
 bp.REGISTRY=deepcopy(bp.REGISTRY);bp.REGISTRY[0]['responsibility']+=' later live registry'
 ld._proof(parent,record)
 assert demo.contracts(value,'d'*64,now=now)[0]!=releases
 assert ld.verify(parent,record,saved,now=now,historical=True)['can_adopt']
finally: bp.REGISTRY=original_registry
print('frozen_history_survives_live_registry_change=true live_contract_changed=true')
request=SimpleNamespace(candidate_id=record['id'],partial_adoption=False,expected_candidate_sha256=view['candidate_sha256'],expected_verification_sha256=view['verification_sha256'],expected_preparation_revision=1,expected_request_revision=1,expected_source_sha256=saved['source_sha256'],required_goals=goals)
proof=ld.consume(parent,saved,request,now=now)
plan=dict(candidate_consumption=proof,adoption_preparation_revision=1,adoption_preview=saved,required_goals=goals,binding=dict(request_intent=dict(revision=1),service_selection=dict(profile=demo.PROFILE,capability_catalog_sha256=saved['capability_catalog_sha256'],selection=selection)),events=[dict(candidate_consumption_sha256=cp._hash(proof))],steps=[dict(adapter_id=s['id'],adapter=s['adapter'],adapter_revision=s['revision'],depends_on=s['depends_on'],contract=s) for s in saved['steps']])
ld.consumption_proof(parent,plan,request)
plan['events'][0]['candidate_consumption_sha256']='0'*64
try: ld.consumption_proof(parent,plan,request)
except Conflict: pass
else: raise AssertionError('tampered adoption event accepted')
assert demo.configure(None,None,None) is None
for profile,raw in [('REAL','{}'),(demo.PROFILE,None),(None,'{}')]:
 try: demo.configure(None,profile,raw)
 except Denied: pass
 else: raise AssertionError('unconfigured profile accepted')
class FakeCatalog(demo.LocalDemoCatalog): pass
try: demo.LocalSyntheticDemo(object.__new__(FakeCatalog),demo.LocalDemoSelector())
except Denied: pass
else: raise AssertionError('subclass accepted')
print('adoption_proof_and_tampered_event_gate=true exact_types_and_default_off=true')
print('probe_scope=memory-only; actual_DB_API_browser_network_file_writes=0')
print('WIRE='+json.dumps(dict(producer=record['producer'],producer_sha256=cp._hash(record['producer'])),ensure_ascii=False,separators=(',',':')))
PY