"""Isolated exact-Run candidate and stale access-context refusal."""
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,sqlite3,uuid
import pytest
from fastapi.testclient import TestClient
from parkweave.run_access_candidate import *
from parkweave.run_access_candidate_api import create_run_access_candidate_app
from scripts.run_access_candidate_demo import mock_config,configured_mock_app

OWNER='mock-run-owner';APPROVER='mock-run-access-approver';TARGET='mock-run-executor'
SCOPE=RunScope(park_id='park-a',org_id='org-a',run_id='mock-run-a')
OTHER=SCOPE.model_copy(update={'run_id':'mock-run-b'})

@pytest.fixture
def candidate(tmp_path):
    now=[datetime(2026,10,7,10,tzinfo=timezone.utc)];r=RunAccessRepository(tmp_path/'test.run-access.candidate.sqlite3');e=RunAccessEngine(mock_config(),r,lambda:now[0]);return e,r,now

def interval(now,seconds=3600):return {'valid_from':now.isoformat(),'valid_until':(now+timedelta(seconds=seconds)).isoformat(),'timezone':'UTC'}
def body(e,action,now,actor=None,scope=SCOPE,view=None,**kw):
    actor=actor or (APPROVER if action in ('APPROVE','REJECT','REVOKE') else OWNER);v=view or e.read(actor,scope)
    payload={'action':action,'expected_revision':v['revision'],'expected_run_revision':v['run_revision'],'expected_authority_sha256':v['authority_sha256'],'reason':'SYNTHETIC '+action,**kw}
    if action=='REQUEST':payload.update(target_id=kw.get('target_id',TARGET),target_role='service_executor',capability='READ',requested_validity=kw.get('requested_validity',interval(now)))
    if action=='APPROVE':payload['approved_validity']=kw.get('approved_validity',v['request']['requested_validity'])
    return actor,RunCommand.model_validate(payload)
def command(e,action,now,actor=None,key=None,scope=SCOPE,view=None,**kw):
    a,d=body(e,action,now,actor,scope,view,**kw);return e.command(a,scope,key or uuid.uuid4().hex,d)
def approved(e,now):command(e,'REQUEST',now);command(e,'APPROVE',now)
def probe(e,scope=SCOPE):
    v=e.read(TARGET,scope);return AccessProbe(expected_revision=v['revision'],expected_run_revision=v['run_revision'],expected_authority_sha256=v['authority_sha256'],lease_id=v['lease_id'])
def stable(r):
    with r.connect() as c:return {t:[dict(x) for x in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ('access_tickets','access_events','access_leases')}
def replace(e,change):
    c=e.config.model_copy(deep=True);c.revision+=1;change(c);e.replace_test_contract(c)

def test_default_disabled_and_both_factory_flags_required(tmp_path,monkeypatch):
    api=TestClient(create_run_access_candidate_app());assert not api.get('/api/run-access/status').json()['candidate_demo'];assert api.get('/api/run-access/park-a/org-a/mock-run-a',headers={'X-Mock-Actor':OWNER}).status_code==403
    assert '候选流程未启用' in api.get('/').text
    path=tmp_path/'disabled.run-access.candidate.sqlite3';monkeypatch.setenv('PARKWEAVE_RUN_ACCESS_TEST_DB',str(path));monkeypatch.delenv('PARKWEAVE_RUN_ACCESS_ENABLE_TESTS',raising=False)
    assert not TestClient(configured_mock_app()).get('/api/run-access/status').json()['candidate_demo'];assert not path.exists()
    with pytest.raises(ValueError):RunAccessConfig(enabled_for_isolated_tests=True)
    with pytest.raises(ValueError):RunAccessEngine(mock_config())

def test_request_independent_approval_exact_read_probe_and_immutable_audit(candidate):
    e,r,n=candidate;command(e,'REQUEST',n[0]);v=e.read(TARGET,SCOPE)
    assert not v['candidate_access_available']
    with pytest.raises(Denied):e.access(TARGET,SCOPE,AccessProbe(expected_revision=1,expected_run_revision=1,expected_authority_sha256=v['authority_sha256'],lease_id='not-approved'))
    command(e,'APPROVE',n[0]);assert e.access(TARGET,SCOPE,probe(e))['candidate_read_allowed']
    v=e.read(TARGET,SCOPE);assert not v['actual_run_access'] and not v['actual_assignment_written'] and not v['case_goal_completed'] and v['qualification_truth']=='UNKNOWN'
    assert v['request']['requester_id']!=v['request']['approver_id'] and v['request']['capability']=='READ'
    with pytest.raises(sqlite3.IntegrityError):
        with r.connect(write=True) as c:c.execute('UPDATE access_events SET revision=99')
    with pytest.raises(sqlite3.IntegrityError):
        with r.connect(write=True) as c:c.execute("UPDATE access_leases SET payload='{}'")

@pytest.mark.parametrize('actor,action',[(OWNER,'APPROVE'),(TARGET,'APPROVE'),('prep-specialist-fixture-a','APPROVE'),('mock-resource-reader','APPROVE'),('mock-other-owner','REQUEST'),('mock-other-executor','APPROVE'),('missing','REQUEST')])
def test_roles_and_cross_tenant_denied_no_writes(candidate,actor,action):
    e,r,n=candidate;command(e,'REQUEST',n[0]);_,d=body(e,action,n[0],APPROVER if action=='APPROVE' else OWNER);before=stable(r)
    with pytest.raises(Denied):e.command(actor,SCOPE,'denied',d)
    assert stable(r)==before

def test_existing_same_tenant_target_read_and_role_required(candidate):
    e,r,n=candidate;before=stable(r)
    for target in ('mock-other-executor','prep-specialist-fixture-a','missing'):
        with pytest.raises(Denied):command(e,'REQUEST',n[0],target_id=target)
    replace(e,lambda c:setattr(next(f for f in c.read_facts if f.principal_id==TARGET),'active',False))
    with pytest.raises(Denied):command(e,'REQUEST',n[0])
    assert stable(r)==before

def test_reject_cancel_and_new_request_versions_preserve_history(candidate):
    e,r,n=candidate;command(e,'REQUEST',n[0]);command(e,'REJECT',n[0]);command(e,'REQUEST',n[0]);command(e,'CANCEL',n[0]);command(e,'REQUEST',n[0]);command(e,'APPROVE',n[0]);old=probe(e);command(e,'REVOKE',n[0]);before=stable(r)
    with pytest.raises(Denied):e.access(TARGET,SCOPE,old)
    assert stable(r)==before
    command(e,'REQUEST',n[0]);command(e,'APPROVE',n[0]);v=e.read(TARGET,SCOPE)
    assert len(v['history'])==9 and len(v['leases'])==2 and v['leases'][0]['state']=='REVOKED'
    with pytest.raises(Conflict):e.access(TARGET,SCOPE,old)

@pytest.mark.parametrize('seconds',[0,28801])
def test_bounded_deadline_and_approval_cannot_expand_interval(candidate,seconds):
    e,r,n=candidate;before=stable(r)
    with pytest.raises((Conflict,ValueError)):command(e,'REQUEST',n[0],requested_validity=interval(n[0],seconds))
    assert stable(r)==before
    command(e,'REQUEST',n[0]);before=stable(r)
    with pytest.raises(Conflict):command(e,'APPROVE',n[0],approved_validity=interval(n[0],7200))
    assert stable(r)==before

def test_expired_and_future_access_and_old_approval_replay_are_denied(candidate):
    e,r,n=candidate;start=n[0]+timedelta(seconds=60);v=interval(start,60);command(e,'REQUEST',n[0],requested_validity=v);a,d=body(e,'APPROVE',n[0]);e.command(a,SCOPE,'approve-once',d)
    with pytest.raises(Denied):e.access(TARGET,SCOPE,probe(e))
    n[0]=start;e.access(TARGET,SCOPE,probe(e));old=probe(e);n[0]+=timedelta(seconds=60);before=stable(r)
    with pytest.raises(Denied):e.access(TARGET,SCOPE,old)
    with pytest.raises((Denied,Conflict)):e.command(a,SCOPE,'approve-once',d)
    assert stable(r)==before

@pytest.mark.parametrize('mutation',['target_inactive','target_read_revoked','target_role_changed','approver_revoked','requester_revoked','run_version','run_owner','contract_only'])
def test_current_rechecks_reject_cached_context_after_revocation_or_version_change(candidate,mutation):
    e,r,n=candidate;approved(e,n[0]);old=probe(e)
    def change(c):
        if mutation=='target_inactive':next(p for p in c.personas if p.id==TARGET).active=False
        elif mutation=='target_read_revoked':next(p for p in c.read_facts if p.principal_id==TARGET).active=False
        elif mutation=='target_role_changed':next(p for p in c.personas if p.id==TARGET).role='resource_admin'
        elif mutation=='approver_revoked':next(p for p in c.permits if p.principal_id==APPROVER and p.scope==SCOPE).active=False
        elif mutation=='requester_revoked':next(p for p in c.read_facts if p.principal_id==OWNER).active=False
        elif mutation=='run_version':c.runs[0].revision+=1
        elif mutation=='run_owner':c.runs[0].owner_id=APPROVER
    replace(e,change);before=stable(r)
    with pytest.raises((Denied,Conflict)):e.access(TARGET,SCOPE,old)
    assert stable(r)==before and not e.read(OWNER if mutation=='approver_revoked' else APPROVER,SCOPE)['candidate_access_available']

def test_self_approval_is_denied_even_when_mock_role_is_changed(candidate):
    e,r,n=candidate;command(e,'REQUEST',n[0]);_,d=body(e,'APPROVE',n[0]);before=stable(r)
    def change(c):
        next(p for p in c.personas if p.id==OWNER).role='park_specialist'
        next(p for p in c.permits if p.principal_id==OWNER and p.scope==SCOPE).actions=['STATUS','APPROVE']
    replace(e,change)
    _,d=body(e,'APPROVE',n[0],actor=OWNER)
    with pytest.raises(Denied):e.command(OWNER,SCOPE,'self',d)
    assert stable(r)==before

def test_old_versions_cross_run_cached_probe_and_command_key_replays_rejected(candidate):
    e,r,n=candidate;v=e.read(OWNER,SCOPE);a,d=body(e,'REQUEST',n[0],view=v);e.command(a,SCOPE,'request-once',d)
    assert e.command(a,SCOPE,'request-once',d)['revision']==1
    before=stable(r)
    _,other=body(e,'REQUEST',n[0],scope=OTHER)
    with pytest.raises(Conflict):e.command(a,OTHER,'request-once',other)
    with pytest.raises(Conflict):command(e,'REQUEST',n[0],view=v)
    assert stable(r)==before
    a,approval=body(e,'APPROVE',n[0]);e.command(a,SCOPE,'approval-once',approval);old=probe(e)
    command(e,'REQUEST',n[0],scope=OTHER);command(e,'APPROVE',n[0],scope=OTHER)
    with pytest.raises(Conflict):e.access(TARGET,OTHER,old)
    command(e,'REVOKE',n[0]);before=stable(r)
    with pytest.raises(Conflict):e.command(a,SCOPE,'approval-once',approval)
    assert stable(r)==before

def test_two_engines_same_key_and_cas_concurrency_are_atomic(candidate):
    e,r,n=candidate;second=RunAccessEngine(mock_config(),RunAccessRepository(r.path),lambda:n[0]);a,d=body(e,'REQUEST',n[0])
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda x:x.command(a,SCOPE,'lost-response-key',d),[e,second]))
    assert results[0]==results[1] and len(e.read(OWNER,SCOPE)['history'])==1
    a,d=body(e,'APPROVE',n[0])
    def approve(engine):
        try:return engine.command(a,SCOPE,uuid.uuid4().hex,d)['state']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(approve,[e,second]))==['APPROVED','CONFLICT']
    assert len(e.read(OWNER,SCOPE)['leases'])==1

def test_atomic_rollback_and_foreign_database_kept_unchanged(candidate,tmp_path):
    e,r,n=candidate;command(e,'REQUEST',n[0]);before=stable(r)
    with r.connect(write=True) as c:c.execute("CREATE TRIGGER fail_event BEFORE INSERT ON access_events BEGIN SELECT RAISE(ABORT,'SYNTHETIC failure'); END")
    with pytest.raises(sqlite3.IntegrityError):command(e,'APPROVE',n[0])
    assert stable(r)==before
    path=tmp_path/'foreign.run-access.candidate.sqlite3'
    with sqlite3.connect(path) as c:c.execute('CREATE TABLE legacy(value TEXT)');c.execute("INSERT INTO legacy VALUES('KEEP')")
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(Conflict):RunAccessRepository(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before

def test_api_client_cannot_expand_capability_or_fake_actor_and_refresh_is_readonly(candidate):
    e,r,n=candidate;api=TestClient(create_run_access_candidate_app(e));base='/api/run-access/park-a/org-a/mock-run-a';before=stable(r);a,d=body(e,'REQUEST',n[0]);payload=d.model_dump(mode='json')
    for bad in ({**payload,'capability':'EXECUTE'},{**payload,'actor_id':APPROVER},{**payload,'target_role':'resource_admin'}):assert api.post(base+'/commands',headers={'X-Mock-Actor':OWNER,'Idempotency-Key':'invalid'},json=bad).status_code==422
    assert api.get(base,headers={'X-Mock-Actor':'mock-other-owner'}).status_code==403 and stable(r)==before
    assert api.get(base,headers={'X-Mock-Actor':OWNER}).status_code==200 and stable(r)==before
    assert api.get('/api/run-access/bad!/org-a/mock-run-a',headers={'X-Mock-Actor':OWNER}).status_code==422


def test_generic_status_or_material_reviewer_cannot_read_private_access_audit(candidate):
    e,r,n=candidate;approved(e,n[0]);before=stable(r)
    for actor in ('mock-resource-reader','prep-specialist-fixture-a'):
        with pytest.raises(Denied):e.read(actor,SCOPE)
    assert stable(r)==before


def test_authority_is_rechecked_after_write_lock_wait(candidate,monkeypatch):
    from contextlib import contextmanager
    e,r,n=candidate
    replace(e,lambda c:setattr(next(p for p in c.permits if p.principal_id==APPROVER and p.scope==SCOPE).validity,'valid_until',(n[0]+timedelta(seconds=1)).isoformat()))
    command(e,'REQUEST',n[0]);a,d=body(e,'APPROVE',n[0]);before=stable(r);original=r.connect
    @contextmanager
    def waited(write=False):
        with original(write) as c:
            if write:n[0]+=timedelta(seconds=2)
            yield c
    monkeypatch.setattr(r,'connect',waited)
    with pytest.raises(Denied):e.command(a,SCOPE,'expired-during-write-lock-wait',d)
    assert stable(r)==before


def test_expiry_during_read_wait_cannot_return_cached_access(candidate,monkeypatch):
    from contextlib import contextmanager
    e,r,n=candidate;approved(e,n[0]);old=probe(e);original=r.connect;before=stable(r)
    @contextmanager
    def waited(write=False):
        with original(write) as c:
            if not write:n[0]+=timedelta(seconds=3601)
            yield c
    monkeypatch.setattr(r,'connect',waited)
    with pytest.raises(Denied):e.access(TARGET,SCOPE,old)
    assert stable(r)==before
