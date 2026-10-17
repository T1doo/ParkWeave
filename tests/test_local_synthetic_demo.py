"""Ordinary factory with explicitly installed synthetic inputs and permissions.

No isolated catalog/consumer/planner/Approval is passed to the application.
Fixture authority setup occurs outside startup and is separately asserted.
"""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from parkweave.api import configured_app, create_app
from parkweave import local_synthetic_demo as demo
from parkweave.store import Denied
from test_preparation import preparation_fixture, headers, create, add, command as prep_command
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_service_case_steps import command as plan_command
from test_service_dispatches import offer, command as dispatch_command
from test_case_lifecycle import read as local_read, act as local_command
from test_request_intents import save
from service_release_acceptance_support import authority_snapshot, case_history

GOALS = ['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION',
    'LOCAL_INTERNAL_ACCEPTANCE','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
    'LOCAL_SYNTHETIC_COORDINATION_RECORDS','LOCAL_CASE_RECORD_RECHECK']


def ok(response, code=200):
    assert response.status_code==code,response.text
    return response.json()


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    return sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def demo_inputs(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture
    from parkweave.resource_combinations import seed_synthetic
    from parkweave import resource_holds as rh,resource_combinations as rc
    seed_synthetic(f[1])  # Explicit original synthetic resource/Grant fixture only.
    with f[0].connect() as c:
        now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
        database=demo.database_binding(c)
        row=c.execute("SELECT service_id,version,name,source,namespace,qualification,xmin::text row_generation FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1").fetchone()
    generation=row.pop('row_generation')
    from parkweave.ordinary_runtime_read import catalog_hash
    value=dict(schema_version='parkweave-local-synthetic-demo-pack/1',kind='SYNTHETIC',id='local-demo-fixture',revision=1,
        validity=dict(valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=1)).isoformat(),timezone='UTC'),
        park_id='park-a',org_id='org-a',roles=dict(enterprise_operator='fixture-a',park_specialist='prep-specialist-fixture-a',service_executor='executor-a'),
        resources=dict(primary=str(rh.RESOURCE_ID),secondary=str(rc.SECOND_RESOURCE_ID)),
        fields={slot:dict(slot=slot,input_field='demo_'+slot) for slot in ('need_summary','material_outline')},services=list(demo.contract.SERVICE_GOALS))
    pack_path=tmp_path/'demo-pack.json';journal_path=tmp_path/'input-journal.json'
    pack_sha=write(pack_path,value)
    cfg=dict(schema_version='parkweave-local-synthetic-demo-config/1',pack_path=str(pack_path),pack_sha256=pack_sha,
        journal_path=str(journal_path),journal_sha256='0'*64,database=database,catalog_sha256=catalog_hash(row),catalog_generation=generation)
    journal=dict(schema_version='parkweave-local-synthetic-demo-journal/1',kind='SYNTHETIC',pack_sha256=pack_sha,
        database=database,park_id='park-a',org_id='org-a',catalog_sha256=cfg['catalog_sha256'],catalog_generation=generation)
    cfg['journal_sha256']=write(journal_path,journal)
    journal_path.chmod(0o600)
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn)
    monkeypatch.setenv('PARKWEAVE_SERVICE_PROFILE','LOCAL_SYNTHETIC_DEMO')
    monkeypatch.setenv('PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG',json.dumps(cfg))
    for name in ('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_MODE'):
        monkeypatch.delenv(name,raising=False)
    return f,cfg,value,journal


def prepared(f):
    p,_,_=create(f)
    p=ok(save(f,p,goals=GOALS,text='SYNTHETIC independent demo request'))
    p=ok(add(f,p,text='SYNTHETIC current need'))
    p=ok(add(f,p,'material_outline','SYNTHETIC current outline'))
    p=ok(prep_command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC original specialist review'))
    return ok(prep_command(f,p,'CONFIRM',reason='SYNTHETIC original owner confirmation'))


def generate(f,p,key=None):
    path='/api/preparations/'+p['preparation_id']
    current=ok(f[3].get(path+'/service-capabilities',headers=headers(f[2])))
    capture=dict(expected_preparation_revision=p['revision'],expected_source_sha256=current['source_sha256'],
        expected_capability_catalog_sha256=current['capability_catalog_sha256'])
    response=f[3].post(path+'/service-selections',headers=headers(f[2],key=key or uuid4().hex),json=capture)
    return current,capture,response


def test_ordinary_factory_original_full_chain_and_cold_recovery(demo_inputs,tmp_path):
    initial,cfg,value,journal=demo_inputs
    before=authority_snapshot(initial[1])
    with TestClient(configured_app()) as api:
        f=(*initial[:3],api)
        assert authority_snapshot(f[1])==before
        # New Run/preparation/material inputs all enter through ordinary APIs.
        p=prepared(f)
        ok(api.get('/api/service-instance-configurations',headers=headers(f[2])),403)
        # Required original Run assignment is explicit TEST initial state,
        # outside the loader, and never presented as a startup capability.
        f[1].assign_status('executor-a',UUID(p['run_id']),active=True)
        baseline=authority_snapshot(f[1])
        assert len(baseline['run_assignments'])==len(before['run_assignments'])+1
        key=uuid4().hex
        current,capture,response=generate(f,p,key);candidate=ok(response,201)
        assert current['profile']==demo.PROFILE and current['selection_oracle']['state']=='UNIQUE'
        assert candidate['can_adopt'] and candidate['producer']['mode']=='NO_MODEL'
        assert candidate['producer']['model'] is None and candidate['producer']['real_model_calls']==0
        assert not {'usage','call_id','response_raw','budget_record'}&candidate['producer'].keys()
        assert all('source_review' not in r for r in current['catalog_snapshot']['releases'])
        path='/api/preparations/'+p['preparation_id']
        original=case_history(f[1],p['preparation_id'])
        replay=ok(api.post(path+'/service-selections',headers=headers(f[2],key=key),json=capture),201)
        assert replay==candidate and case_history(f[1],p['preparation_id'])==original
        recovered=ok(api.get(path+'/service-selections/recovery',headers=headers(f[2],key=key)))
        assert recovered['status']=='COMMITTED' and recovered['items'][0]==candidate
        ok(api.get(path+'/service-plan-candidates',headers=headers(f[2])))
        body=dict(expected_preparation_revision=p['revision'],expected_request_revision=current['request_revision'],expected_plan_revision=0,
            expected_source_sha256=current['source_sha256'],required_goals=GOALS,reason='SYNTHETIC explicit NO_MODEL candidate adoption',
            candidate_id=candidate['candidate_id'],expected_candidate_sha256=candidate['candidate_sha256'],expected_verification_sha256=candidate['verification_sha256'])
        adopted=ok(api.post(path+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=body),201)
        assert [s['adapter_id'] for s in adopted['steps']]==['P1','P2','P3','P4','P5']
        def verify(adapter):
            reply=ok(plan_command(f,p,adapter))
            assert next(s for s in reply['steps'] if s['adapter_id']==adapter)['state']=='VERIFIED'
        verify('P1')
        from test_case_resources import group,post as link
        combination=group(f);ok(link(f,p,combination),201);verify('P2')
        dispatch=ok(offer(f,p)[0],201)
        dispatch=ok(dispatch_command(f,dispatch,'ACCEPT'));verify('P3')
        receipt=ok(api.get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a')))
        receipt=ok(receipt_command(f,receipt,'SUBMIT'))
        ok(receipt_command(f,receipt,'ACKNOWLEDGE'));verify('P4')
        local=ok(local_read(f,p));ok(local_command(f,p,local,'REVALIDATE'));verify('P5')
        results=ok(api.get(path+'/goal-results',headers=headers(f[2])))
        assert results['state']=='LOCAL_OUTPUTS_VERIFIED' and len(results['results'])==6
        assert not results['case_goal_completed']
        assert results['source_trace']['candidate']['producer']['mode']=='NO_MODEL'
        assert results['source_trace']['service_selection']['profile']==demo.PROFILE
        assert authority_snapshot(f[1])==baseline
        cold_history=case_history(f[1],p['preparation_id'])
    with TestClient(configured_app()) as cold:
        assert ok(cold.get(path+'/goal-results',headers=headers(initial[2])))==results
        assert ok(cold.get(path+'/service-selections/recovery',headers=headers(initial[2],key=key)))['status']=='COMMITTED'
        assert case_history(initial[1],p['preparation_id'])==cold_history
        assert authority_snapshot(initial[1])==baseline
    evidence=dict(scope='EXPLICIT_SYNTHETIC_ORDINARY_FACTORY_API_CHAIN',profile=demo.PROFILE,real_model_calls=0,
        initial_fixture_assignment_rows_added=1,startup_authority_changes=0,runtime_authority_changes=0,
        result_state=results['state'],result_count=6,cold_results_equal=True,adapters=['P1','P2','P3','P4','P5'],
        browser='NOT_RUN',Windows='NOT_RUN',formal_AT='NOT_RUN',real_business='NOT_RUN',zero_preparation_one_click=False)
    (tmp_path/'actual-ordinary-demo-chain.json').write_text(json.dumps(evidence,indent=2)+'\n')


@pytest.mark.parametrize('target',['READ','PREPARE','REVIEW_ASSIGNED','EXECUTE','resource','reviewer','tenant'])
def test_missing_current_authority_refuses_without_writes(demo_inputs,target):
    initial,_,_,_=demo_inputs
    p=prepared(initial)
    with TestClient(configured_app()) as api:
        f=(*initial[:3],api);current,capture,_=generate(f,p)
        with f[1].connect() as c:
            if target in ('READ','EXECUTE'):
                c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',target))
            elif target in ('PREPARE','REVIEW_ASSIGNED'):
                c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability=%s',
                    ('fixture-a' if target=='PREPARE' else 'prep-specialist-fixture-a',target))
            elif target=='resource': c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a'")
            elif target=='reviewer': c.execute("UPDATE principals SET active=false WHERE id='prep-specialist-fixture-a'")
            else: c.execute("UPDATE principals SET org_id='org-b' WHERE id='fixture-a'")
        before=case_history(f[1],p['preparation_id']);auth=authority_snapshot(f[1])
        path='/api/preparations/'+p['preparation_id']
        ok(api.post(path+'/service-selections',headers=headers(f[2],key=uuid4().hex),json=capture),403)
        assert case_history(f[1],p['preparation_id'])==before and authority_snapshot(f[1])==auth


@pytest.mark.parametrize('target',['unknown_mode','missing_config','config_without_mode','real_source','pack_hash','journal_hash','database','park','catalog','relative_path'])
def test_startup_bindings_default_off_and_invalid_inputs(demo_inputs,monkeypatch,target):
    f,cfg,value,journal=demo_inputs;cfg=deepcopy(cfg)
    before=authority_snapshot(f[1])
    if target=='unknown_mode': monkeypatch.setenv('PARKWEAVE_SERVICE_PROFILE','REAL')
    elif target=='missing_config': monkeypatch.delenv('PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG')
    elif target=='config_without_mode': monkeypatch.delenv('PARKWEAVE_SERVICE_PROFILE')
    elif target=='real_source':
        value['kind']='AUTHORIZED_REAL';cfg['pack_sha256']=write(Path(cfg['pack_path']),value)
    elif target=='pack_hash': cfg['pack_sha256']='f'*64
    elif target=='journal_hash': cfg['journal_sha256']='f'*64
    elif target=='database': cfg['database']['oid']+=1
    elif target=='park': journal['park_id']='park-b';cfg['journal_sha256']=write(Path(cfg['journal_path']),journal)
    elif target=='catalog': cfg['catalog_generation']='0'
    else: cfg['pack_path']='relative.json'
    if target not in ('missing_config',): monkeypatch.setenv('PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG',json.dumps(cfg))
    with pytest.raises(Denied): configured_app()
    assert authority_snapshot(f[1])==before


def test_default_off_and_isolated_types_not_substituted(demo_inputs,monkeypatch):
    f,cfg,_,_=demo_inputs
    monkeypatch.delenv('PARKWEAVE_SERVICE_PROFILE');monkeypatch.delenv('PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG')
    p=prepared(f)
    with TestClient(configured_app()) as api:
        ok(api.get('/api/preparations/'+p['preparation_id']+'/service-capabilities',headers=headers(f[2])),403)
    runtime=demo.configure(f[0],demo.PROFILE,json.dumps(cfg))
    with pytest.raises(Denied): create_app(f[0],capability_catalog=runtime.catalog)
    with pytest.raises(Denied): create_app(f[0],local_synthetic_demo=object())
    with pytest.raises(Denied): create_app(f[0],local_synthetic_demo=runtime,selection_planner=runtime.selector)


def test_saved_proof_survives_current_registry_change_and_rejects_forgery(demo_inputs,monkeypatch):
    from parkweave import local_demo_selections as selections,bounded_planning as bp
    from parkweave.store import Conflict
    initial,_,_,_=demo_inputs;p=prepared(initial)
    with TestClient(configured_app()) as api:
        f=(*initial[:3],api);current,capture,response=generate(f,p);candidate=ok(response,201)
        with f[1].connect() as c: parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        saved=selections.find(parent,candidate['candidate_id'])
        for change in ('producer','selection','registry','profile'):
            changed=deepcopy(parent);r=changed['planning_previews'][0]
            if change=='producer': r['producer']['real_model_calls']=False  # bool must not equal integer proof.
            elif change=='selection': r['selection']['selections'].pop()
            elif change=='registry': r['frozen_registry']['steps'][0]['responsibility']='SYNTHETIC changed frozen contract'
            else: r['profile']='TRUSTED_SERVICE_SELECTION_V4'
            with pytest.raises(Conflict): selections.find(changed,candidate['candidate_id'])
        registry=deepcopy(bp.REGISTRY);registry[0]['responsibility']+=' SYNTHETIC later registry description'
        monkeypatch.setattr(bp,'REGISTRY',registry)
        assert selections.find(parent,candidate['candidate_id'])==saved
        # Historical structure/provenance remains readable; current admission stops.
        old=selections.verify(parent,saved,saved['document'],now=selections.old._time(saved['validity']['created_at']),historical=True)
        assert old['candidate_sha256']==candidate['candidate_sha256']
        item=ok(api.get('/api/preparations/'+p['preparation_id']+'/service-selections/'+candidate['candidate_id']+'/preview',headers=headers(f[2])))
        assert item['state']=='CURRENT_SOURCE_UNAVAILABLE' and not item['can_adopt']


def test_missing_run_assignment_stops_original_dispatch_without_creating_authority(demo_inputs):
    initial,_,_,_=demo_inputs;p=prepared(initial)
    with TestClient(configured_app()) as api:
        f=(*initial[:3],api);current,capture,response=generate(f,p);candidate=ok(response,201)
        path='/api/preparations/'+p['preparation_id']
        body=dict(expected_preparation_revision=p['revision'],expected_request_revision=current['request_revision'],expected_plan_revision=0,
            expected_source_sha256=current['source_sha256'],required_goals=GOALS,reason='SYNTHETIC explicit adoption without assignment',
            candidate_id=candidate['candidate_id'],expected_candidate_sha256=candidate['candidate_sha256'],expected_verification_sha256=candidate['verification_sha256'])
        ok(api.post(path+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=body),201)
        from test_case_resources import group,post as link
        ok(plan_command(f,p,'P1'));ok(link(f,p,group(f)),201);ok(plan_command(f,p,'P2'))
        before=authority_snapshot(f[1]);history=case_history(f[1],p['preparation_id'])
        assert not before['run_assignments']
        ok(offer(f,p)[0],403)
        assert authority_snapshot(f[1])==before and case_history(f[1],p['preparation_id'])==history


@pytest.mark.parametrize('target',['oversize','public_journal','FAULT_INJECTION','missing_catalog','real_catalog'])
def test_bounded_files_mode_and_existing_catalog_required(demo_inputs,monkeypatch,target):
    f,cfg,_,_=demo_inputs;before=authority_snapshot(f[1])
    if target=='oversize': Path(cfg['pack_path']).write_bytes(b'x'*65537)
    elif target=='public_journal': Path(cfg['journal_path']).chmod(0o644)
    elif target=='FAULT_INJECTION': monkeypatch.setenv('PARKWEAVE_MODE','FAULT_INJECTION')
    else:
        with f[1].connect() as c:
            if target=='missing_catalog': c.execute("DELETE FROM preparation_catalog WHERE park_id='park-a'")
            else: c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"AUTHORIZED_REAL\"') WHERE park_id='park-a'")
    with pytest.raises(Denied): configured_app()
    assert authority_snapshot(f[1])==before
