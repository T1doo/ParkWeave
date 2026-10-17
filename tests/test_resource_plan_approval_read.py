"""Actual factory/PG reads and signed synthetic source; no real approval fixture."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest
from parkweave import resource_plan_approval_read as approval
from parkweave.api import create_app
from parkweave.store import Denied
from test_executor_receipts import receipt_fixture
from test_ordinary_runtime_read import selection,snapshot
from test_preparation import preparation_fixture,filled,headers
from test_service_case_steps import verified
from resource_approval_read_support import seeded,current,factory,path,read


def test_default_no_provider_or_source_does_not_infer_approval(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1])
    with TestClient(factory(f,monkeypatch)) as api:
        x,_=current(api,f,p);assert x['state']=='CONTRACT_UNAVAILABLE'
        x=read(api,f,p,query).json();assert x['state']=='CONTRACT_UNAVAILABLE' and not x['verified_existing_approval']
        assert api.get('/api/plan-approval/status',headers=headers(f[2])).json()['enabled'] is False
        assert api.get('/api/run-access/status',headers=headers(f[2])).json()['enabled'] is False
        assert api.post(path(p),headers=headers(f[2]),json={}).status_code==405
    assert not source.calls and snapshot(f[1])==before


@pytest.mark.parametrize('actor',['fixture-a','prep-specialist-fixture-a'])
def test_exact_signed_existing_source_read_and_original_navigation_are_read_only(receipt_fixture,tmp_path,monkeypatch,actor):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1])
    with TestClient(app) as api:
        x=read(api,f,p,query,actor).json();assert x['state']=='VERIFIED' and x['verified_existing_approval']
        assert x['purpose']=='RESOURCE_PLAN_APPROVAL' and x['approval_source_kind']=='SYNTHETIC_CONTRACT_FIXTURE'
        assert all(x[k] is False for k in ('execution_authorized','approval_consumable','decision_writes_enabled','run_read_access_granted'))
        record=source.record();canonical=approval.ApprovalRecord.model_validate(record).model_dump(mode='json')
        assert x['record']==canonical and len(source.calls)==2
        old_write=api.post('/api/preparations/'+p['preparation_id']+'/plan-approval/commands',
                           headers=headers(f[2],actor,'SYNTHETIC-no-write'),
                           json={'action':'APPROVE','approval_id':record['approval_id'],'expected_revision':1,
                                 'expected_binding_sha256':'a'*64,'reason':'SYNTHETIC must remain denied'})
        assert old_write.status_code==403
        original=read(api,f,p,query,actor,suffix='/records/'+record['approval_id']);assert original.status_code==200
        assert original.json()['record']==canonical
        assert read(api,f,p,query,actor,suffix='/records/'+str(uuid4())).json()['state']=='MISSING_SOURCE'
    assert snapshot(f[1])==before


@pytest.mark.parametrize('field,value',[('expected_case_id','UUID'),('expected_run_id','UUID'),('expected_service_id','other'),
    ('expected_service_version',2),('expected_plan_id','UUID'),('expected_plan_revision',2),('expected_context_sha256','f'*64)])
def test_wrong_requested_binding_is_refused_before_source_read(receipt_fixture,tmp_path,monkeypatch,field,value):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch);query[field]=str(uuid4()) if value=='UUID' else value
    with TestClient(app) as api:assert read(api,f,p,query).status_code==409
    assert not source.calls


@pytest.mark.parametrize('field', ['preparation_id','case_id','run_id','plan_id','plan_revision','plan_definition_sha256',
                                 'action_scope_sha256','source_sha256','authority_sha256','database_binding_sha256'])
def test_signed_wrong_record_binding_never_becomes_current_approval(receipt_fixture,tmp_path,monkeypatch,field):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch);record=source.record()
    record['binding'][field]=2 if field=='plan_revision' else 'f'*64 if field.endswith('sha256') else str(uuid4())
    source.write(record)
    with TestClient(app) as api:
        x=read(api,f,p,query).json();assert x['state']=='INVALID' and x['reason']=='APPROVAL_EXACT_BINDING_MISMATCH' and 'record' not in x


@pytest.mark.parametrize('state',['expired','revoked','future'])
def test_existing_expiry_revocation_and_not_yet_valid_remain_invalid_after_restart(receipt_fixture,tmp_path,monkeypatch,state):
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch);record=source.record();now=datetime.now(timezone.utc)
    if state=='expired':record.update(approved_at=(now-timedelta(hours=2)).isoformat(),valid_from=(now-timedelta(hours=1)).isoformat(),valid_until=(now-timedelta(seconds=1)).isoformat())
    elif state=='revoked':record.update(state='REVOKED',revoked_at=now.isoformat(),record_revision=2)
    else:record['valid_from']=(now+timedelta(seconds=10)).isoformat()
    source.write(record);before=snapshot(f[1])
    for _ in range(2):
        with TestClient(factory(f,monkeypatch,source.provider)) as api:
            x=read(api,f,p,query).json();assert x['state']=='INVALID' and not x['verified_existing_approval']
    assert snapshot(f[1])==before


@pytest.mark.parametrize('damage',['signature','duplicate-key','run-read-purpose','extra-credential','absent'])
def test_unverified_missing_or_wrong_contract_source_never_approves(receipt_fixture,tmp_path,monkeypatch,damage):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch);record=source.record()
    if damage=='signature':source.signature.write_text('0'*64)
    elif damage=='absent':source.path.unlink()
    elif damage=='duplicate-key':
        raw=source.path.read_bytes()[:-1]+b',"state":"REVOKED"}'
        source.path.write_bytes(raw)
        import hmac,hashlib
        source.signature.write_text(hmac.new(source.key,raw,hashlib.sha256).hexdigest())
        source.head.write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'record_revision':1}))
        with pytest.raises(ValueError,match='duplicate'):approval.strict_json(raw)
    else:
        if damage=='run-read-purpose':record['purpose']='RUN_READ_ACCESS_ONLY'
        else:record['writer_dsn']='SYNTHETIC_DO_NOT_ACCEPT'
        source.write(record)
    with TestClient(app) as api:
        x=read(api,f,p,query).json();assert x['state']=='MISSING_SOURCE' and not x['verified_existing_approval'] and 'record' not in x


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','unassigned','prep-specialist-fixture-b'])
def test_cross_scope_reader_never_calls_source(receipt_fixture,tmp_path,monkeypatch,actor):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch)
    with TestClient(app) as api:assert read(api,f,p,query,actor).status_code==403
    assert not source.calls


@pytest.mark.parametrize('change',['read','prepare','owner-execute','catalog-aba','plan-version'])
def test_current_permissions_catalog_generation_or_plan_revision_change_refuses_old_binding(receipt_fixture,tmp_path,monkeypatch,change):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch)
    if change=='plan-version':verified(f,p,'P1')
    else:
        with f[1].connect() as c:
            if change=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            elif change=='prepare':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
            elif change=='owner-execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
            else:c.execute("UPDATE preparation_catalog SET source=source WHERE park_id='park-a'")
    before=snapshot(f[1])
    with TestClient(app) as api:
        r=read(api,f,p,query);assert r.status_code==(403 if change in ('read','prepare') else 409)
        if change not in ('read','prepare'):
            _,fresh=current(api,f,p);x=read(api,f,p,fresh).json();assert x['state']=='INVALID' and not x['verified_existing_approval']
    assert snapshot(f[1])==before


def test_revocation_during_source_read_and_permission_change_during_read_cannot_return_verified(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch)
    def revoke(src,lookup,n):
        if n==2:
            record=src.record();record.update(state='REVOKED',revoked_at=datetime.now(timezone.utc).isoformat(),record_revision=2);src.write(record)
    source.on_read=revoke
    with TestClient(app) as api:
        x=read(api,f,p,query).json();assert x['state']=='INVALID' and x['reason']=='ORIGINAL_APPROVAL_CHANGED_DURING_READ'
    source.on_read=None
    def remove_permission(src,lookup,n):
        if n==3:
            with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
    source.on_read=remove_permission
    with TestClient(app) as api:assert read(api,f,p,query).status_code==403


def test_isolated_or_run_provider_cannot_be_installed_as_independent_reader(receipt_fixture):
    from parkweave.service_plan_approval import IsolatedPlanApproval
    from parkweave.native_run_access import NativeRunAccess
    for obj in (object.__new__(IsolatedPlanApproval),NativeRunAccess(receipt_fixture[0]),{},True):
        with pytest.raises(Denied,match='independent read-only'):create_app(receipt_fixture[0],resource_plan_approval_provider=obj)


def test_old_signed_record_replay_cannot_replace_current_revocation_source_head(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch)
    old,mac=source.path.read_bytes(),source.signature.read_text();record=source.record()
    record.update(state='REVOKED',revoked_at=datetime.now(timezone.utc).isoformat(),record_revision=2);source.write(record)
    source.path.write_bytes(old);source.signature.write_text(mac)
    with TestClient(factory(f,monkeypatch,source.provider)) as api:
        x=read(api,f,p,query).json();assert x['state']=='MISSING_SOURCE' and not x['verified_existing_approval']


@pytest.mark.parametrize('change',['identity','role','subject'])
def test_original_approver_identity_and_role_are_exact_current_participants(receipt_fixture,tmp_path,monkeypatch,change):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch);record=source.record()
    if change=='identity':record['approver_id']='unassigned'
    elif change=='role':record['approver_role']='park_specialist'
    else:record['approver_id']='prep-specialist-fixture-b';record['approver_role']='park_specialist'
    source.write(record)
    with TestClient(app) as api:
        x=read(api,f,p,query).json();assert x['state']=='INVALID' and x['reason']=='CURRENT_APPROVER_IDENTITY_REQUIRED'


@pytest.mark.parametrize('value',[1740000000,'2026-10-17T10:00:00+08:00'],ids=['numeric-epoch','non-UTC'])
def test_existing_source_requires_explicit_iso_utc_times(receipt_fixture,tmp_path,monkeypatch,value):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch);record=source.record();record['valid_from']=value;source.write(record)
    with TestClient(app) as api:assert read(api,f,p,query).json()['state']=='MISSING_SOURCE'


def test_reader_cannot_mix_with_isolated_provider_or_accept_client_approval_fields(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch)
    monkeypatch.setattr(f[0],'_isolated_plan_approval',object(),raising=False)
    with pytest.raises(Denied,match='cannot be combined'):create_app(f[0],resource_plan_approval_provider=source.provider)
    with TestClient(app) as api:
        r=read(api,f,p,{**query,'approval_id':str(uuid4()),'verified':True});assert r.status_code==422
    assert not source.calls


def test_owner_action_permission_uses_original_tenant_grant_rules_even_with_new_signed_record(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch)
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET org_id='org-b' WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    with TestClient(app) as api:
        ctx,fresh=current(api,f,p,'prep-specialist-fixture-a');assert 'CURRENT_OWNER_AUTHORITY_REQUIRED' in ctx['current_source_issues']
        record=source.record();record.update(binding=ctx['binding'],record_revision=2);source.write(record)
        x=read(api,f,p,fresh,'prep-specialist-fixture-a').json();assert x['state']=='INVALID' and x['reason']=='CURRENT_PLAN_SOURCE_INVALID'


def test_regrant_same_permission_does_not_revive_old_authority_generation(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,app,query=seeded(f,tmp_path,monkeypatch)
    for active in (False,True):
        with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=%s WHERE principal_id='fixture-a' AND capability='EXECUTE'",(active,))
    with TestClient(app) as api:
        assert read(api,f,p,query).status_code==409
        ctx,fresh=current(api,f,p);assert ctx['binding']['authority_sha256']!=source.record()['binding']['authority_sha256']
        assert read(api,f,p,fresh).json()['state']=='INVALID'


def test_source_current_head_is_reverified_immediately_before_projection(receipt_fixture,tmp_path,monkeypatch):
    from dataclasses import replace
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch);verified_count=[]
    def verification(lookup,raw):
        verified_count.append(lookup)
        return len(verified_count)<3 and source.verify(lookup,raw)
    with TestClient(factory(f,monkeypatch,replace(source.provider,verify_existing=verification))) as api:
        x=read(api,f,p,query).json();assert x['state']=='INVALID' and x['reason']=='CURRENT_APPROVAL_SOURCE_CHANGED' and 'record' not in x
