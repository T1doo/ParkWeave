"""Explicit multi-solution selection through original PG candidate/adoption paths.

Two real independently bound synthetic instances of an actual reviewed fixture
release produce the alternatives. No invented product catalog or model calls.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from parkweave.api import create_app,configured_app
from parkweave.store import Store,Conflict
from parkweave import service_selection_candidates as sc,service_capability_contract as contract
from parkweave.template_candidate import TemplateEngine,TemplateRepository,Command
from parkweave.template_consumer import TemplateConsumer,ConsumerRepository
from parkweave.service_capability_catalog import IsolatedServiceCapabilityCatalog
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog,material_instance
from test_service_selection_candidates import arrangement
from test_independent_selection_integration import adoption
from test_local_synthetic_demo import demo_inputs,prepared,ok
from test_local_resource_reapproval import ordinary_local
from service_release_acceptance_support import authority_snapshot,case_history


def alternatives(a):
    f,p,_,_=arrangement(a)
    with a['catalog'].connection() as c:
        actor,parent=sc.bp._context(f[0],c,f[2]['fixture-a'],p['preparation_id'])
        current=sc.current(f[0],c,actor,parent,a['catalog'])
    release=current['catalog_snapshot']['releases'][0]
    other=material_instance(release);other['instance_id']='park-a-material-explicit-alternative'
    other['source']['id']='SYNTHETIC-explicit-independent-alternative'
    other['config_sha256']=contract.hash_instance(other)
    a['catalog'].bind_instance('park-a',uuid4().hex,other)
    with a['catalog'].connection() as c:
        actor,parent=sc.bp._context(f[0],c,f[2]['fixture-a'],p['preparation_id'])
        current=sc.current(f[0],c,actor,parent,a['catalog'])
    create_app(f[0],capability_catalog=a['catalog'])
    assert current['selection_oracle']['state']=='MULTIPLE'
    assert len(current['selection_oracle']['minimal_solutions'])==2
    return f,p,current


def request(current,index=1):
    return sc.Capture(expected_preparation_revision=current['preparation_revision'],expected_source_sha256=current['source_sha256'],
        expected_capability_catalog_sha256=current['capability_catalog_sha256'],manual_selections=current['selection_oracle']['minimal_solutions'][index])


def generate(a,f,p,data,key=None):
    # No planner exists. The explicit branch must never dispatch a model.
    return sc.generate(f[0],f[2]['fixture-a'],p['preparation_id'],key or uuid4().hex,data,catalog=a['catalog'],planner=None)


def reopen(a):
    store=Store(a['f'][0].dsn)
    engine=TemplateEngine(a['engine'].config,TemplateRepository(a['engine'].repository.path),lambda:a['now'][0])
    consumer=TemplateConsumer(store,engine,a['consumer'].config,ConsumerRepository(a['consumer'].repository.path))
    catalog=IsolatedServiceCapabilityCatalog(consumer,a['f'][1],enabled_for_isolated_tests=True)
    return store,catalog,create_app(store,capability_catalog=catalog)


def test_explicit_second_solution_preview_save_adopt_and_fresh_factory_readback(capability_catalog):
    a=capability_catalog;f,p,current=alternatives(a);data=request(current);key=uuid4().hex
    authority=authority_snapshot(f[1]);before=case_history(f[1],p['preparation_id']);path='/api/preparations/'+p['preparation_id']
    with TestClient(create_app(f[0],capability_catalog=a['catalog'])) as api:
        preview=ok(api.post(path+'/service-composition-preview',headers=headers(f[2]),json={k:v for k,v in data.model_dump().items() if k!='manual_selections'}|{'selections':data.manual_selections}))
        assert preview['can_generate_original_candidate'] and preview['minimal_selection']
        assert case_history(f[1],p['preparation_id'])==before
        chosen=ok(api.post(path+'/service-selections',headers=headers(f[2],key=key),json=data.model_dump()),201)
        assert chosen['validator_version']==5 and chosen['producer']['mode']=='OWNER_EXPLICIT_NO_MODEL'
        assert chosen['producer']['real_model_calls']==0 and chosen['producer']['model'] is None
        assert chosen['selection']['selections']==data.manual_selections and chosen['can_adopt']
        # A saved candidate is not adoption. Source/preparation business state is unchanged.
        with f[1].connect() as c:
            row=c.execute('SELECT service_case_plan,revision FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
            assert row['service_case_plan'] is None and row['revision']==p['revision']
        repeated=ok(api.post(path+'/service-selections',headers=headers(f[2],key=key),json=data.model_dump()),201)
        assert repeated==chosen
        assert api.post(path+'/service-selections',headers=headers(f[2],key=key),json=request(current,0).model_dump()).status_code==409
        body=adoption(chosen).model_dump(mode='json');adopt_key=uuid4().hex
        adopted=ok(api.post(path+'/service-case-plan',headers=headers(f[2],key=adopt_key),json=body),201)
        assert adopted['candidate_consumption']['producer']==chosen['producer']
        assert adopted['candidate_consumption']['selection']['selections']==data.manual_selections
    history=case_history(f[1],p['preparation_id']);store,catalog,app=reopen(a)
    with TestClient(app) as api:
        recovered=ok(api.get(path+'/service-selections/recovery',headers=headers(f[2],key=key)))
        assert recovered['status']=='COMMITTED' and recovered['items'][0]['selection']==chosen['selection']
        replay=ok(api.post(path+'/service-case-plan',headers=headers(f[2],key=adopt_key),json=body),201)
        assert replay['plan_id']==adopted['plan_id']
        result=ok(api.get(path+'/goal-results',headers=headers(f[2])))
        assert result['source_trace']['candidate']['producer']==chosen['producer']
    assert case_history(f[1],p['preparation_id'])==history and authority_snapshot(f[1])==authority


def test_same_key_concurrent_save_and_two_choices_concurrent_adopt(capability_catalog):
    a=capability_catalog;f,p,current=alternatives(a);data=request(current);key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(lambda _:generate(a,f,p,data,key),range(2)))
    assert rows[0]['candidate_id']==rows[1]['candidate_id']
    second=generate(a,f,p,request(current,0))
    from parkweave.service_case_steps import adopt as adopt_plan
    def attempt(row):
        try:return adopt_plan(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,adoption(row))['plan_id']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[rows[0],second]))
    assert results.count('CONFLICT')==1 and len(set(results))==2
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        assert len(parent['planning_previews'])==2 and len(parent['service_case_plan']['events'])==1


def test_expired_withdrawn_or_stale_choice_is_readable_but_not_adoptable(capability_catalog,monkeypatch):
    a=capability_catalog;f,p,current=alternatives(a);data=request(current);row=generate(a,f,p,data);path='/api/preparations/'+p['preparation_id']
    future=sc.old._time(row['validity']['expires_at'])+timedelta(seconds=1)
    original=sc.clock;monkeypatch.setattr(sc,'clock',lambda c:future)
    observed=sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],candidate_id=row['candidate_id'],catalog=a['catalog'])
    assert observed['state']=='EXPIRED' and not observed['can_adopt']
    from parkweave.service_case_steps import adopt as adopt_plan
    with pytest.raises(Conflict):adopt_plan(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,adoption(row))
    monkeypatch.setattr(sc,'clock',original)
    source=a['engine'].read('template-publisher',a['scope'])
    a['engine'].command('template-publisher',a['scope'],uuid4().hex,Command.model_validate(dict(action='WITHDRAW',expected_revision=source['revision'],expected_definition_sha256=source['definition_sha256'],reason='SYNTHETIC explicit source withdrawal')))
    before=case_history(f[1],p['preparation_id'])
    observed=sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],candidate_id=row['candidate_id'],catalog=a['catalog'])
    assert observed['state']=='CURRENT_SOURCE_UNAVAILABLE' and not observed['can_adopt']
    with pytest.raises(Conflict):adopt_plan(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,adoption(row))
    assert case_history(f[1],p['preparation_id'])==before


def test_redundant_stale_or_unauthorized_selection_does_not_write(capability_catalog):
    a=capability_catalog;f,p,current=alternatives(a);authority=authority_snapshot(f[1]);before=case_history(f[1],p['preparation_id'])
    all_refs=sum(current['selection_oracle']['minimal_solutions'],[])
    with pytest.raises(Conflict):generate(a,f,p,request(current).model_copy(update={'manual_selections':all_refs}))
    with pytest.raises(Conflict):generate(a,f,p,request(current).model_copy(update={'expected_source_sha256':'0'*64}))
    with TestClient(create_app(f[0],capability_catalog=a['catalog'])) as api:
        path='/api/preparations/'+p['preparation_id']+'/service-selections'
        assert api.post(path,headers=headers(f[2],'fixture-b',uuid4().hex),json=request(current).model_dump()).status_code==403
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        assert api.post(path,headers=headers(f[2],key=uuid4().hex),json=request(current).model_dump()).status_code==403
    assert case_history(f[1],p['preparation_id'])==before
    # Revocation is explicit fixture authority change; product adds no authority.
    assert authority_snapshot(f[1])['run_assignments']==authority['run_assignments']



def test_saved_manual_choice_observes_revoke_and_read_scope(capability_catalog):
    a=capability_catalog;f,p,current=alternatives(a);key=uuid4().hex;data=request(current);row=generate(a,f,p,data,key)
    path='/api/preparations/'+p['preparation_id'];before=case_history(f[1],p['preparation_id'])
    with TestClient(create_app(f[0],capability_catalog=a['catalog'])) as api:
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        observed=ok(api.get(path+'/service-selections/'+row['candidate_id']+'/preview',headers=headers(f[2])))
        assert not observed['can_adopt'] and observed['state']=='CURRENT_SOURCE_UNAVAILABLE'
        recovered=ok(api.get(path+'/service-selections/recovery',headers=headers(f[2],key=key)))
        assert recovered['status']=='COMMITTED' and not recovered['items'][0]['can_adopt']
        assert api.post(path+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=adoption(row).model_dump(mode='json')).status_code==403
        # The original READ scope remains; revoked execution is an unavailable mapping.
        fresh=ok(api.get(path+'/service-capabilities',headers=headers(f[2])))
        payload=dict(expected_preparation_revision=fresh['preparation_revision'],expected_source_sha256=fresh['source_sha256'],expected_capability_catalog_sha256=fresh['capability_catalog_sha256'],selections=data.manual_selections)
        assert api.post(path+'/service-composition-preview',headers=headers(f[2]),json=payload).status_code==409
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        assert api.get(path+'/service-selections/recovery',headers=headers(f[2],key=key)).status_code==403
        assert api.get(path+'/service-selections/'+row['candidate_id']+'/preview',headers=headers(f[2])).status_code==403
    assert case_history(f[1],p['preparation_id'])==before


def test_bad_manual_references_fail_before_fingerprinting_without_input_echo(capability_catalog):
    a=capability_catalog;f,p,current=alternatives(a);path='/api/preparations/'+p['preparation_id']+'/service-selections'
    data=request(current).model_dump();data['manual_selections'][0]['instance_id']='\ud800'
    import json
    with TestClient(create_app(f[0],capability_catalog=a['catalog'])) as api:
        response=api.post(path,headers={**headers(f[2],key=uuid4().hex),'Content-Type':'application/json'},content=json.dumps(data))
        assert response.status_code==422 and response.json()=={'detail':'invalid bounded service selection request'}
    with f[1].connect() as c:assert not c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews']


@pytest.mark.parametrize('damage',['producer','request','selection'])
def test_manual_provenance_cannot_be_rehashed_into_another_choice(capability_catalog,damage):
    a=capability_catalog;f,p,current=alternatives(a);row=generate(a,f,p,request(current))
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();record=parent['planning_previews'][0]
        if damage=='producer':record['producer']['actor_ref']='0'*64
        elif damage=='request':record['candidate_request'].pop('manual_selections')
        else:record['selection']['selections']=current['selection_oracle']['minimal_solutions'][0]
        record['candidate']=sc.document(record['document']);record['candidate_sha256']=sc.cp._hash(record['candidate'])
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(parent['planning_previews']),p['preparation_id']))
    with pytest.raises(Conflict):sc.read(f[0],f[2]['fixture-a'],p['preparation_id'],candidate_id=row['candidate_id'],catalog=a['catalog'])


def test_local_no_model_explicit_choice_uses_same_proof_and_cold_factory(demo_inputs):
    initial,_,_,_=demo_inputs
    with TestClient(configured_app()) as api:
        f=(*initial[:3],api);p=prepared(f);path='/api/preparations/'+p['preparation_id'];current=ok(api.get(path+'/service-capabilities',headers=headers(f[2])))
        data=request(current,0);key=uuid4().hex
        row=ok(api.post(path+'/service-selections',headers=headers(f[2],key=key),json=data.model_dump()),201)
        assert row['validator_version']=='LOCAL_SYNTHETIC_DEMO_MANUAL_V3' and row['producer']['mode']=='OWNER_EXPLICIT_NO_MODEL'
        body=adoption(row).model_dump(mode='json');adopted=ok(api.post(path+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=body),201)
    with TestClient(configured_app()) as cold:
        recovered=ok(cold.get(path+'/service-selections/recovery',headers=headers(initial[2],key=key)))
        assert recovered['items'][0]['selection']==row['selection']
        result=ok(cold.get(path+'/goal-results',headers=headers(initial[2])))
        assert result['source_trace']['candidate']['producer']==row['producer']
        assert result['source_trace']['plan_id']==adopted['plan_id']


def test_local_manual_difference_observation_keeps_original_seal_and_page_guards(ordinary_local,tmp_path):
    from test_no_model_difference_observation import first,source_adopt,stored,tail_pending
    f,_,_=ordinary_local;p,_,_,candidate=first(f,tmp_path/'worker',manual=True)
    assert candidate['validator_version']=='LOCAL_SYNTHETIC_DEMO_MANUAL_V3'
    original=deepcopy(stored(f,p)['candidate_consumption'])
    event=source_adopt(f,p,page_directory=tmp_path)
    current=stored(f,p);tail_pending(current)
    assert current['candidate_consumption']==original and current['candidate_consumption']['difference_observation']
    assert event['action']=='ADOPT' and event['revision']>1
