"""Real owned PostgreSQL V4 selection attempts; no live model or browser."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4
import httpx
import pytest
from psycopg.types.json import Jsonb
from parkweave import bounded_planning as bp, service_selection_candidates as sc
from parkweave import controlled_plans as cp
from parkweave.service_selection_planner import OfflineSelectionPlanner
from parkweave.service_plan_planner import OfflineBudget
from parkweave.store import Conflict, Denied
from parkweave.intern_adapter import MODEL
from test_preparation import preparation_fixture, add
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog,capability_resource_catalog,register,material_instance,coordination_instance
from test_bounded_planning import setup
from test_plan_preview import digest


def arrangement(a,goals=None):
    f=a['f'];release=register(a)['release'];a['catalog'].bind_instance('park-a',uuid4().hex,material_instance(release))
    parent=setup(f,goals or ['LOCAL_MATERIAL_PREPARATION'])
    with a['catalog'].connection() as c:
        p,row=bp._context(f[0],c,f[2]['fixture-a'],parent['preparation_id'])
        value=sc.current(f[0],c,p,row,a['catalog'])
    data=sc.Capture(expected_preparation_revision=value['preparation_revision'],expected_source_sha256=value['source_sha256'],expected_capability_catalog_sha256=value['capability_catalog_sha256'])
    return f,parent,data,value


def planner(calls,callback=None,mode='ok'):
    def handle(request):
        calls.append(json.loads(request.content));context=json.loads(calls[-1]['messages'][1]['content']);context.pop('scope')
        if callback:callback()
        if mode=='timeout':raise httpx.ReadTimeout('SYNTHETIC lost outcome')
        selection=dict(schema_version=1,binding=context['binding'],selections=[v['ref'] for v in reversed(context['available_services'])] if mode=='all' else [context['available_services'][0]['ref']])
        if mode=='goal':selection['required_goals']=[]
        return httpx.Response(200,json=dict(id='synthetic-selection',model=MODEL,choices=[dict(index=0,message=dict(role='assistant',content=json.dumps(selection)),finish_reason='stop')],usage=dict(prompt_tokens=2,completion_tokens=3,total_tokens=5)))
    return OfflineSelectionPlanner(transport=httpx.MockTransport(handle),budget=OfflineBudget())


def run(a,f,parent,data,key,model):return sc.generate(f[0],f[2]['fixture-a'],parent['preparation_id'],key,data,catalog=a['catalog'],planner=model)


def test_v4_real_pg_compact_selection_rebuild_recovery_no_business_or_grant_writes(capability_catalog):
    a=capability_catalog;f,p,data,current=arrangement(a);calls=[];model=planner(calls);key=uuid4().hex
    before=digest(f);v=run(a,f,p,data,key,model)
    assert v['validator_version']==4 and v['can_adopt'] and v['steps'][0]['service_refs']
    assert v['steps'][0]['instance_mappings'][0]['roles']['enterprise_operator']=='fixture-a'
    assert run(a,f,p,data,key,model)==v and len(calls)==1
    recovered=sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],key=key,catalog=a['catalog'])
    assert recovered['status']=='COMMITTED' and recovered['items'][0]==v
    assert len(calls)==1 and v['new_grants'] is False and v['execution_enabled'] is False
    prompt=json.loads(calls[0]['messages'][1]['content'])
    assert set(prompt)=={'scope','binding','required_goals','planning_constraints','available_services'}
    assert 'steps' not in prompt and 'fixture-a' not in json.dumps(prompt)
    with pytest.raises(Conflict):run(a,f,p,data.model_copy(update={'expected_source_sha256':'0'*64}),key,model)


@pytest.mark.parametrize('change',['downgrade','producer','selection','mapping','action','goal_coverage','oracle'])
def test_v4_rehashed_tampering_cannot_be_consumed(capability_catalog,change):
    a=capability_catalog;f,p,data,_=arrangement(a);v=run(a,f,p,data,uuid4().hex,planner([]))
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();h=parent['planning_previews'][0]
        if change=='downgrade':h['profile']='LEGACY';h['document'].pop('profile')
        elif change=='producer':h['producer']['version']=3
        elif change=='selection':h['selection']['selections'][0]['config_revision']=2
        elif change=='mapping':h['document']['steps'][0]['instance_mappings'][0]['roles']['enterprise_operator']='fixture-c'
        elif change=='goal_coverage':h['document']['goal_coverage'][0]['status']='UNSUPPORTED'
        elif change=='oracle':h['document']['selection_oracle']['minimal_solutions']=[]
        else:h['document']['steps'][0]['actions'][0]['commands'].append('UNREGISTERED')
        h['candidate']=sc.document(h['document']) if change!='downgrade' else h['candidate'];h['candidate_sha256']=cp._hash(h['candidate'])
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(parent['planning_previews']),p['preparation_id']))
    with pytest.raises(Conflict):sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],candidate_id=v['candidate_id'],catalog=a['catalog'])


def test_source_changes_while_model_waits_preserve_original_attempt_and_get_only(capability_catalog):
    a=capability_catalog;f,p,data,_=arrangement(a);calls=[];key=uuid4().hex
    def change():assert add(f,p).status_code==200
    model=planner(calls,change)
    with pytest.raises(Conflict):run(a,f,p,data,key,model)
    recovered=sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],key=key,catalog=a['catalog'])
    assert recovered['status']=='FAILED_SAFE' and not recovered['items'] and len(calls)==1
    assert run(a,f,p,data,key,model)['status']=='FAILED_SAFE' and len(calls)==1


def test_timeout_outcome_unknown_never_retries_original_key(capability_catalog):
    a=capability_catalog;f,p,data,_=arrangement(a);calls=[];model=planner(calls,mode='timeout');key=uuid4().hex
    with pytest.raises(Conflict):run(a,f,p,data,key,model)
    for _ in range(2):assert run(a,f,p,data,key,model)['status']=='OUTCOME_UNKNOWN'
    assert sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],key=key,catalog=a['catalog'])['status']=='OUTCOME_UNKNOWN'
    assert len(calls)==1


def test_same_key_actual_concurrent_dispatch_once(capability_catalog):
    a=capability_catalog;f,p,data,_=arrangement(a);calls=[];model=planner(calls);key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:run(a,f,p,data,key,model),range(2)))
    assert len(calls)==1
    assert all(v.get('can_adopt') or v.get('status')=='PENDING' for v in results)
    assert sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],key=key,catalog=a['catalog'])['status']=='COMMITTED'


def test_withdrawn_catalog_cold_get_retains_saved_candidate_without_write(capability_catalog):
    a=capability_catalog;f,p,data,_=arrangement(a);key=uuid4().hex;v=run(a,f,p,data,key,planner([]))
    from parkweave.template_candidate import Command
    current=a['engine'].read('template-publisher',a['scope'])
    a['engine'].command('template-publisher',a['scope'],uuid4().hex,Command.model_validate(dict(action='WITHDRAW',expected_revision=current['revision'],expected_definition_sha256=current['definition_sha256'],reason='SYNTHETIC withdrawal')))
    before=digest(f);read=sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],key=key,catalog=a['catalog'])
    assert read['status']=='COMMITTED' and read['items'][0]['candidate_id']==v['candidate_id'] and not read['items'][0]['can_adopt']
    assert digest(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_original_current_authority_rejects_cross_owner(capability_catalog,user):
    a=capability_catalog;f,p,data,_=arrangement(a)
    with pytest.raises(Denied):sc.generate(f[0],f[2][user],p['preparation_id'],uuid4().hex,data,catalog=a['catalog'],planner=planner([]))


def test_unsupported_required_goal_not_dropped(capability_catalog):
    a=capability_catalog;f,p,data,value=arrangement(a,['LOCAL_MATERIAL_PREPARATION','EXTERNAL_REAL_FULFILMENT'])
    assert value['selection_oracle']['state']=='UNSUPPORTED'
    assert value['required_goals']==['LOCAL_MATERIAL_PREPARATION','EXTERNAL_REAL_FULFILMENT']
    calls=[]
    with pytest.raises(Conflict):run(a,f,p,data,uuid4().hex,planner(calls))
    assert calls==[]


def test_historical_frozen_proof_survives_current_registry_change(capability_catalog,monkeypatch):
    a=capability_catalog;f,p,data,_=arrangement(a);v=run(a,f,p,data,uuid4().hex,planner([]))
    with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    h=sc.find(parent,v['candidate_id']);registry=deepcopy(bp.REGISTRY);registry[0]['acceptance']='SYNTHETIC current registry unavailable'
    monkeypatch.setattr(bp,'REGISTRY',registry)
    assert sc.find(parent,v['candidate_id'])['id']==v['candidate_id']
    from types import SimpleNamespace
    request=SimpleNamespace(candidate_id=v['candidate_id'],expected_candidate_sha256=v['candidate_sha256'],expected_verification_sha256=v['verification_sha256'],partial_adoption=False)
    accepted=sc.old._time(h['validity']['created_at'])
    proof=sc.consume(parent,h['document'],request,now=accepted,historical=True)
    assert proof['verification_basis']['validator_version']==4


def test_final_candidate_failure_rolls_back_to_original_attempt(capability_catalog,monkeypatch):
    a=capability_catalog;f,p,data,_=arrangement(a);calls=[];key=uuid4().hex
    def broken(*args,**kwargs):raise RuntimeError('SYNTHETIC final candidate write failure')
    monkeypatch.setattr(sc,'verify',broken)
    with pytest.raises(RuntimeError):run(a,f,p,data,key,planner(calls))
    with f[1].connect() as c:records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews']
    assert len(records)==1 and 'candidate' not in records[0] and records[0]['planner_attempt']['state']=='OUTCOME_UNKNOWN'
    assert len(calls)==1


@pytest.mark.parametrize('field,value',[('expected_preparation_revision',True),('expected_source_sha256','A'*64),('extra','forbidden')])
def test_capture_strict_exact_versions_and_no_extra(field,value):
    from pydantic import ValidationError
    data=dict(expected_preparation_revision=1,expected_source_sha256='a'*64,expected_capability_catalog_sha256='b'*64);data[field]=value
    with pytest.raises(ValidationError):sc.Capture.model_validate(data)


def test_actual_multi_capability_unordered_refs_rebuild_and_frozen_history(capability_resource_catalog):
    a=capability_resource_catalog;release=register(a,service='synthetic-resource-coordination')['release']
    a['catalog'].bind_instance('park-a',uuid4().hex,coordination_instance(release))
    f,p,data,value=arrangement(a,['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION'])
    assert value['selection_oracle']['state']=='UNIQUE'
    assert len(value['selection_oracle']['minimal_solutions'][0])==2
    calls=[];v=run(a,f,p,data,uuid4().hex,planner(calls,mode='all'))
    assert v['can_adopt'] and len(v['selection']['selections'])==2
    assert len(v['steps'][0]['service_refs'])==2 and len(v['steps'])==4
    with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    assert sc.find(parent,v['candidate_id'])['id']==v['candidate_id']


def test_committed_key_after_catalog_withdrawal_returns_original_locator(capability_catalog):
    a=capability_catalog;f,p,data,_=arrangement(a);calls=[];model=planner(calls);key=uuid4().hex;v=run(a,f,p,data,key,model)
    with f[1].connect() as c:h=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'][0]
    snapshot=h['document']['catalog_snapshot']
    a['catalog'].withdraw_instance('park-a',uuid4().hex,snapshot['instances'][0]['instance_id'],snapshot['revision'],'SYNTHETIC explicit fixture withdrawal')
    recovered=run(a,f,p,data,key,model)
    assert recovered['candidate_id']==v['candidate_id'] and not recovered['can_adopt'] and len(calls)==1
