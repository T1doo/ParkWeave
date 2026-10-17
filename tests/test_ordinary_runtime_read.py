"""Ordinary routes and read-only provider; no real authority is installed.

Signed positive preconditions use the original owned synthetic writer fixture.
Factory DI replaces ONLY the root-protected host binder, never signature, source,
permission or assignment checks. This is not production OS installation proof.
"""
from copy import deepcopy
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest

from parkweave import ordinary_runtime_read as runtime, native_run_access as native
from parkweave import native_run_access_writer as writer, native_run_access_restricted_host as host
from parkweave.api import configured_app
from parkweave.store import Store, Denied
from test_preparation import preparation_fixture, filled, headers
from test_executor_receipts import receipt_fixture
from test_native_run_access_writer import writer_fixture, approve, body
from test_native_run_access_activation import activate, activation_body
from test_service_dispatches import offer
from test_native_preparation_entry import TABLES


def snapshot(owner):
    with owner.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        return {t:c.execute(f'SELECT to_jsonb(t) row FROM {t} t ORDER BY to_jsonb(t)::text').fetchall()
                for t in (*TABLES,'service_dispatches','service_dispatch_offers','service_dispatch_events',
                          'service_receipt_steps','service_receipt_events')}


def selection(p, **changes):
    return dict(expected_case_id=p['case_id'],expected_run_id=p['run_id'],
                expected_service_id='synthetic-material-preparation',expected_service_version=1,**changes)


def get(api, f, p, operation, actor='fixture-a', changes=None):
    query=selection(p);query.update(changes or {})
    return api.get('/api/preparations/'+p['preparation_id']+'/runtime/'+operation,
                   params=query,headers=headers(f[2],actor))


def config_for(h):
    with h.f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(h.parent['preparation_id'],)).fetchone()
        service,generation=runtime._catalog(c,parent)
    return runtime.ReadConfig(schema_version='parkweave-ordinary-runtime-read/1',
        binding_path='/not-installed/SYNTHETIC-host-public-binding.json',binding_sha256='a'*64,
        preparation_id=UUID(h.parent['preparation_id']),case_id=UUID(h.parent['case_id']),run_id=UUID(h.parent['run_id']),
        service_id=parent['service_id'],service_version=parent['service_version'],
        catalog_sha256=runtime.catalog_hash(service),catalog_generation=generation)


def reference_factory(h, monkeypatch, cfg=None):
    """Test-only host binder DI; original PG, public client and signed RPC remain real."""
    cfg=cfg or config_for(h)
    calls=[]
    def bind(store,path,sha,*,read_only=False):
        assert (path,sha,read_only)==(cfg.binding_path,cfg.binding_sha256,True)
        bridge=native.NativeRunAccess(store,writer=writer.WriterClient(store,h.bootstrap['policy'],h.pin),read_only=True)
        store._native_run_access=bridge
        calls.append(bridge)
        return bridge
    monkeypatch.setattr(host,'bind_api',bind)
    monkeypatch.setenv('PARKWEAVE_DSN',h.f[0].dsn)
    monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    monkeypatch.setenv('PARKWEAVE_RUNTIME_READ_CONFIG',cfg.model_dump_json())
    return configured_app(),calls,cfg


def ordinary(f, monkeypatch):
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn)
    monkeypatch.delenv('PARKWEAVE_RUNTIME_READ_CONFIG',raising=False)
    return configured_app()


def test_original_run_dispatch_catalog_routes_work_and_missing_provider_refuses(receipt_fixture, monkeypatch):
    f=receipt_fixture;r,p,_=offer(f);assert r.status_code==201
    before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:
        assert get(api,f,p,'run').status_code==200
        dispatched=get(api,f,p,'dispatch');assert dispatched.status_code==200
        assert dispatched.json()['dispatch_id']==r.json()['dispatch_id']
        x=get(api,f,p,'catalog').json()
        assert x['catalog']['version']==1 and not x['provider_configured']
        assert not x['resource_plan_approval_available']
        assert x['resource_plan_approval_reason']=='ORDINARY_RESOURCE_PLAN_APPROVAL_CONTRACT_UNAVAILABLE'
        denied=get(api,f,p,'access-approval');assert denied.status_code==409
        assert denied.json()['detail']=='ordinary runtime read provider not configured; existing protected binding required'
        assert api.get('/api/plan-approval/status',headers=headers(f[2])).json()['enabled'] is False
    assert snapshot(f[1])==before


@pytest.mark.parametrize('field,value', [('expected_case_id',str(uuid4())),('expected_run_id',str(uuid4())),
    ('expected_service_version',2),('expected_service_id','SYNTHETIC-other-service')],ids=['case','run','service-version','service-id'])
def test_wrong_exact_selection_refuses_every_bound_original_read(preparation_fixture,monkeypatch,field,value):
    f=preparation_fixture;p=filled(f);before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:
        for operation in ('run','dispatch','catalog','access-approval'):
            r=get(api,f,p,operation,changes={field:value})
            assert r.status_code==409 and 'runtime selection' in r.json()['detail']
    assert snapshot(f[1])==before


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','prep-specialist-fixture-b'])
def test_current_tenant_and_preparation_assignment_still_required(preparation_fixture,monkeypatch,actor):
    f=preparation_fixture;p=filled(f);before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:
        for operation in ('run','dispatch','catalog','access-approval'):
            assert get(api,f,p,operation,actor).status_code==403
    assert snapshot(f[1])==before


@pytest.mark.parametrize('damage',['empty','json','extra','isolated','write-mode','relative','sha','bool-version','missing'])
def test_invalid_factory_config_never_reaches_host_or_database(monkeypatch,damage):
    raw=dict(schema_version='parkweave-ordinary-runtime-read/1',binding_path='/SYNTHETIC/existing-public.json',
        binding_sha256='a'*64,preparation_id=str(uuid4()),case_id=str(uuid4()),run_id=str(uuid4()),
        service_id='synthetic-material-preparation',service_version=1,catalog_sha256='b'*64,catalog_generation='10')
    if damage=='extra':raw['writer_dsn']='SYNTHETIC_MUST_NOT_ECHO'
    elif damage=='isolated':raw['isolated_plan_approval']=True
    elif damage=='write-mode':raw['read_only']=False
    elif damage=='relative':raw['binding_path']='relative.json'
    elif damage=='sha':raw['binding_sha256']='wrong'
    elif damage=='bool-version':raw['service_version']=True
    elif damage=='missing':raw.pop('case_id')
    encoded='' if damage=='empty' else '[' if damage=='json' else json.dumps(raw)
    monkeypatch.setattr(host,'bind_api',lambda *a,**k:pytest.fail('invalid config cannot load a host binding'))
    monkeypatch.setenv('PARKWEAVE_DSN','dbname=SYNTHETIC_not_connected')
    monkeypatch.setenv('PARKWEAVE_RUNTIME_READ_CONFIG',encoded)
    with pytest.raises(Denied,match='invalid explicit ordinary runtime read configuration') as error:
        configured_app()
    assert 'SYNTHETIC_MUST_NOT_ECHO' not in str(error.value)


def test_actual_unprotected_or_missing_pin_is_not_a_startup_authority(monkeypatch,tmp_path):
    import hashlib
    path=tmp_path/'untrusted-public.json';path.write_text('{}')
    cfg=dict(schema_version='parkweave-ordinary-runtime-read/1',binding_path=str(path),
        binding_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),preparation_id=str(uuid4()),case_id=str(uuid4()),
        run_id=str(uuid4()),service_id='synthetic-material-preparation',service_version=1,
        catalog_sha256='b'*64,catalog_generation='10')
    monkeypatch.setenv('PARKWEAVE_DSN','dbname=SYNTHETIC_not_connected')
    monkeypatch.setenv('PARKWEAVE_RUNTIME_READ_CONFIG',json.dumps(cfg))
    with pytest.raises(Denied,match='no fallback'):configured_app()
    assert path.read_text()=='{}'


def test_reviewer_catalog_projection_and_original_run_read_boundary(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=filled(f);before=snapshot(f[1])
    with TestClient(ordinary(f,monkeypatch)) as api:
        x=get(api,f,p,'catalog','prep-specialist-fixture-a');assert x.status_code==200
        x=x.json();assert not x['catalog_source_visible']
        assert set(x['catalog'])=={'service_id','version','namespace','qualification'}
        assert get(api,f,p,'run','prep-specialist-fixture-a').status_code==403
        assert get(api,f,p,'dispatch','prep-specialist-fixture-a').status_code==200
    assert snapshot(f[1])==before


def test_missing_live_verifier_refuses_bound_approval_and_existing_native_run_read(writer_fixture,monkeypatch):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    app,_,cfg=reference_factory(h,monkeypatch)
    before=snapshot(h.f[1]);h.stop(h.writer_process)
    with TestClient(app) as api:
        assert api.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
        denied=get(api,h.f,h.parent,'access-approval')
        assert denied.status_code==409 and 'provider current validation unavailable' in denied.json()['detail']
    with pytest.raises(Denied,match='no fallback'):configured_app()
    assert snapshot(h.f[1])==before


def test_real_signed_existing_assignment_survives_factory_restart_but_commands_stay_closed(writer_fixture,monkeypatch):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    r,_,_=offer(h.f,h.parent);assert r.status_code==201,r.text
    before=snapshot(h.f[1]);app,bridges,cfg=reference_factory(h,monkeypatch)
    original_rpc=writer.WriterClient.rpc;operations=[]
    def observe(client,operation,**data):
        operations.append(operation);assert operation in ('VALIDATE','VERIFY')
        return original_rpc(client,operation,**data)
    monkeypatch.setattr(writer.WriterClient,'rpc',observe)
    for application in (app,configured_app()):
        with TestClient(application) as api:
            assert api.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==200
            status=api.get('/api/run-access/status',headers=headers(h.f[2])).json()
            assert status['read_only'] and not status['enabled'] and not status['can_approve']
            access=get(api,h.f,h.parent,'access-approval');assert access.status_code==200,access.text
            x=access.json();assert x['writer_history_verified'] and x['actual_run_access'] and x['read_only']
            assert not any(x[k] for k in ('can_request','can_approve','can_reject','can_cancel','can_revoke','can_activate','activation_enabled'))
            assert get(api,h.f,h.parent,'dispatch').json()['dispatch_id']==r.json()['dispatch_id']
            assert get(api,h.f,h.parent,'catalog').json()['provider_configured']
            denied=api.post('/api/runs/'+h.parent['run_id']+'/access/commands',headers=headers(h.f[2],key='readonly-command'),json=body(h.a,'REVOKE').model_dump(mode='json'))
            assert denied.status_code==403
            denied=api.post('/api/runs/'+h.parent['run_id']+'/access/activate',headers=headers(h.f[2],key='readonly-activation'),json=activation_body(h.a))
            assert denied.status_code==403
    assert len(bridges)==2 and operations and snapshot(h.f[1])==before


@pytest.mark.parametrize('damage',['owner-read','prepare','reviewer','assignment','catalog-aba'])
def test_current_revocation_and_catalog_generation_deny_after_restart(writer_fixture,monkeypatch,damage):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    app,_,cfg=reference_factory(h,monkeypatch)
    with TestClient(app) as api:
        assert api.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==200
    with h.f[1].connect() as c:
        if damage=='owner-read':c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
        elif damage=='prepare':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        elif damage=='reviewer':c.execute("UPDATE principals SET active=false WHERE id='prep-specialist-fixture-a'")
        elif damage=='assignment':
            # Revocation through the original signed writer, never UPDATE its protected assignment.
            pass
        else:c.execute("UPDATE preparation_catalog SET name=name WHERE park_id='park-a' AND version=1")
    if damage=='assignment':
        from test_native_run_access_writer import act
        assert act(h.a,'REVOKE',key='original-explicit-test-revoke')['state']=='REVOKED'
    revoked=snapshot(h.f[1])
    if damage=='catalog-aba':
        with pytest.raises(Denied,match='no fallback'):configured_app()
        with TestClient(app) as api:
            assert api.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
            assert get(api,h.f,h.parent,'catalog').status_code==409
    else:
        with TestClient(configured_app()) as api:
            assert api.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
            if damage in ('owner-read','prepare','reviewer'):
                assert get(api,h.f,h.parent,'catalog').status_code==403
            else:
                x=get(api,h.f,h.parent,'access-approval');assert x.status_code==200
                assert x.json()['state']=='REVOKED' and not x.json()['actual_run_access']
    assert snapshot(h.f[1])==revoked


@pytest.mark.parametrize('damage',['case','run','preparation','service-version','catalog-hash'])
def test_provider_config_cannot_substitute_foreign_binding(writer_fixture,monkeypatch,damage):
    h=writer_fixture;cfg=config_for(h).model_dump()
    if damage=='case':cfg['case_id']=uuid4()
    elif damage=='run':cfg['run_id']=uuid4()
    elif damage=='preparation':cfg['preparation_id']=uuid4()
    elif damage=='service-version':cfg['service_version']=2
    else:cfg['catalog_sha256']='c'*64
    before=snapshot(h.f[1])
    with pytest.raises(Denied,match='no fallback'):
        reference_factory(h,monkeypatch,runtime.ReadConfig.model_validate(cfg))
    assert snapshot(h.f[1])==before
