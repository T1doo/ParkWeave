"""Actual PG/API local record closure; no fulfillment state or evidence fabrication."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID,uuid4
import psycopg,pytest
from parkweave import case_lifecycle as lc
from parkweave.store import Store,Conflict
from test_preparation import preparation_fixture,headers,command as prep_act
from test_executor_receipts import receipt_fixture,act as receipt_act,create as legacy_create,ready
from test_case_resources import link_fixture,group,post as link
from test_service_dispatches import offer,command as dispatch_act
from test_resource_combinations import cancel,pair,write


def built(f):
    parent=ready(f);hs,data=pair(f,quantity=2);g=write(f,data).json()["combination"];assert link(f,parent,g).status_code==201
    r,_,_=offer(f,parent);dispatch=dispatch_act(f,r.json(),'ACCEPT').json()
    step=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    step=receipt_act(f,step,'SUBMIT',text='SYNTHETIC local work only').json()
    step=receipt_act(f,step,'ACKNOWLEDGE').json()
    return parent,g,dispatch,step


def read(f,parent,user='fixture-a'):
    return f[3].get('/api/preparations/'+parent['preparation_id']+'/local-case',headers=headers(f[2],user))


def act(f,parent,row,action,user='fixture-a',key=None,**extra):
    body=dict(action=action,expected_revision=row['revision'],expected_cycle=row['cycle'],reason='SYNTHETIC explicit '+action)
    if action!='REOPEN':body['expected_snapshot_sha256']=row['current_snapshot_sha256']
    body.update(extra)
    return f[3].post('/api/preparations/'+parent['preparation_id']+'/local-case/commands',headers=headers(f[2],user,key or uuid4().hex),json=body)


def counts(f):
    with f[1].connect() as c:return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('case_local_lifecycles','case_local_events')]


def closed(f):
    parent,g,d,s=built(f);row=read(f,parent).json();row=act(f,parent,row,'REVALIDATE').json();row=read(f,parent).json()
    r=act(f,parent,row,'CLOSE_LOCAL_RECORD');assert r.status_code==200
    return parent,g,d,s,r.json()


def test_local_close_reopen_explicit_new_cycle_recheck_without_fulfillment(link_fixture):
    f=link_fixture;parent,g,d,s,row=closed(f)
    assert row['local_record_state']=='LOCAL_RECORD_CLOSED' and row['case_state']=='WAITING_CONFIRMATION'
    assert not row['case_goal_completed'] and row['offline_fulfillment']=='NO_EVIDENCE' and row['external_acceptance']=='NOT_SUBMITTED'
    before=None
    with f[1].connect() as c:before=c.execute('SELECT state FROM synthetic_resource_holds ORDER BY id').fetchall()
    row=act(f,parent,row,'REOPEN',reason='SYNTHETIC check again').json()
    assert row['cycle']==2 and row['local_record_state']=='REOPENED' and row['case_state']=='REOPENED'
    assert row['verified_snapshot_sha256'] is None and set(row['required_rechecks'])==set(lc.RECHECKS)
    now=read(f,parent).json();assert act(f,parent,now,'CLOSE_LOCAL_RECORD').status_code==409
    row=act(f,parent,now,'REVALIDATE').json();row=act(f,parent,read(f,parent).json(),'CLOSE_LOCAL_RECORD').json()
    assert row['revision']==5 and row['cycle']==2
    assert [e['action'] for e in row['history']]==['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN','REVALIDATE','CLOSE_LOCAL_RECORD']
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM synthetic_resource_holds ORDER BY id').fetchall()==before
        assert c.execute('SELECT state FROM service_receipt_steps WHERE id=%s',(UUID(s['step']['id']),)).fetchone()['state']=='LOCAL_ACKNOWLEDGED'
    assert lc.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(parent['preparation_id']))['revision']==5


def test_missing_evidence_and_legacy_receipt_cannot_close(link_fixture):
    f=link_fixture;parent=ready(f);row=read(f,parent).json()
    assert row['checks']['ACCEPTANCE_RECHECK']==['ACCEPTED_DISPATCH_REQUIRED']
    assert row['checks']['RESOURCE_RECHECK']==['CURRENT_CASE_RESOURCE_LINK_REQUIRED']
    assert act(f,parent,row,'REVALIDATE').status_code==409 and counts(f)==[0,0]
    r,_,_=legacy_create(f,parent);step=receipt_act(f,r.json(),'SUBMIT').json();receipt_act(f,step,'ACKNOWLEDGE')
    row=read(f,parent).json();assert 'LEGACY_ACCEPTANCE_MISSING' in row['checks']['ACCEPTANCE_RECHECK']
    assert act(f,parent,row,'CLOSE_LOCAL_RECORD').status_code==409 and counts(f)==[0,0]


@pytest.mark.parametrize('change',['prep_state','prep_revision','material_tamper','dispatch','executor_assignment','reviewer_grant','receipt_state','receipt_text','receipt_executor','resource_cancel','resource_end','resource_revision','resource_disabled','resource_capacity','resource_claim','resource_hold_grant'])
def test_changed_dependencies_block_validation_and_do_not_modify_records(link_fixture,change):
    f=link_fixture;parent,g,d,s=built(f)
    if change=='resource_cancel':cancel(f,g['id'])
    else:
        with f[1].connect() as c:
            if change.startswith('prep_'):c.execute('UPDATE preparations SET '+('revision=revision+1' if change=='prep_revision' else "state='IN_PREPARATION',review_sha256=NULL")+' WHERE id=%s',(UUID(parent['preparation_id']),))
            elif change=='material_tamper':c.execute('UPDATE preparation_evidence SET text=%s WHERE preparation_id=%s',('SYNTHETIC changed',UUID(parent['preparation_id'])))
            elif change=='dispatch':c.execute("UPDATE service_dispatch_offers SET state='WITHDRAWN',receipt_step_id=NULL WHERE id=%s",(UUID(d['current_offer']['id']),))
            elif change=='executor_assignment':f[1].lock_principal(c,'executor-a',exclusive=True);c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
            elif change=='reviewer_grant':f[1].lock_principal(c,'prep-specialist-fixture-a',exclusive=True);c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a'")
            elif change=='receipt_state':c.execute("UPDATE service_receipt_steps SET state='AWAITING_RECEIPT' WHERE id=%s",(UUID(s['step']['id']),))
            elif change=='receipt_text':c.execute("UPDATE service_step_receipts SET text='SYNTHETIC tampered' WHERE id=%s",(UUID(s['current_receipt']['id']),))
            elif change=='receipt_executor':c.execute("UPDATE service_receipt_steps SET executor_id='unassigned' WHERE id=%s",(UUID(s['step']['id']),))
            elif change=='resource_end':c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(UUID(g['members'][0]['id']),))
            elif change in ('resource_revision','resource_disabled','resource_capacity'):
                c.execute('UPDATE synthetic_resources SET '+{'resource_revision':'revision=revision+1','resource_disabled':'enabled=false','resource_capacity':'capacity=1'}[change]+' WHERE id=%s',(UUID(g['members'][0]['resource_id']),))
            elif change=='resource_claim':c.execute('DELETE FROM resource_case_claims WHERE combination_id=%s',(UUID(g['id']),))
            else:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    row=read(f,parent).json();assert any(row['checks'].values());assert act(f,parent,row,'REVALIDATE').status_code==409 and counts(f)==[0,0]


@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-b','executor-c','unassigned'])
def test_tenant_owner_and_assignment_read_write_isolation(link_fixture,user):
    f=link_fixture;parent,g,d,s,row=closed(f);before=counts(f)
    assert read(f,parent,user).status_code==403
    assert act(f,parent,row,'REOPEN',user).status_code==403 and counts(f)==before


@pytest.mark.parametrize('user',['executor-a','prep-specialist-fixture-a'])
def test_legal_counterparties_read_only_minimal_state_and_no_private_payload(link_fixture,user):
    f=link_fixture;parent,g,d,s,row=closed(f)
    observed=read(f,parent,user);assert observed.status_code==200;x=observed.json()
    assert x['local_record_state']=='LOCAL_RECORD_CLOSED' and x['checks'] is None and x['current_snapshot_sha256'] is None
    assert 'SYNTHETIC explicit' not in observed.text and s['current_receipt']['text'] not in observed.text and g['id'] not in observed.text
    for action in ('REOPEN','REVALIDATE','CLOSE_LOCAL_RECORD'):assert act(f,parent,row,action,user).status_code==403


def test_owner_execute_revoked_prevents_replay_and_disables_actions(link_fixture):
    f=link_fixture;parent,g,d,s=built(f);key=uuid4().hex;row=read(f,parent).json();done=act(f,parent,row,'REVALIDATE',key=key).json()
    f[1].revoke_capability('fixture-a','EXECUTE');before=counts(f)
    assert act(f,parent,row,'REVALIDATE',key=key).status_code==403 and counts(f)==before
    now=read(f,parent).json();assert not now['can_revalidate'] and not now['can_close_local_record'] and not now['can_reopen']


@pytest.mark.parametrize('change',['resource_cancel','executor_assignment','prep_state','resource_read_grant'])
def test_reopen_works_after_dependency_invalidity_and_preserves_close_history(link_fixture,change):
    f=link_fixture;parent,g,d,s,row=closed(f)
    if change=='resource_cancel':cancel(f,g['id'])
    else:
        with f[1].connect() as c:
            if change=='executor_assignment':f[1].lock_principal(c,'executor-a',exclusive=True);c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
            elif change=='prep_state':c.execute("UPDATE preparations SET state='IN_PREPARATION',review_sha256=NULL WHERE id=%s",(UUID(parent['preparation_id']),))
            else:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    done=act(f,parent,row,'REOPEN').json();assert done['cycle']==2 and done['local_record_state']=='REOPENED'
    assert done['history'][1]['payload']==row['history'][1]['payload'] and counts(f)==[1,3]


def test_old_validation_and_close_replays_never_restore_reopened_cycle(link_fixture):
    f=link_fixture;parent,g,d,s=built(f);row=read(f,parent).json();vk=uuid4().hex;valid=act(f,parent,row,'REVALIDATE',key=vk).json()
    ready_row=read(f,parent).json();ck=uuid4().hex;close=act(f,parent,ready_row,'CLOSE_LOCAL_RECORD',key=ck).json();opened=act(f,parent,close,'REOPEN').json();before=counts(f)
    replay=act(f,parent,row,'REVALIDATE',key=vk).json();assert replay['event']==valid['event'] and replay['cycle']==2 and replay['local_record_state']=='REOPENED'
    replay=act(f,parent,ready_row,'CLOSE_LOCAL_RECORD',key=ck).json();assert replay['event']==close['event'] and replay['verified_snapshot_sha256'] is None and counts(f)==before
    assert act(f,parent,row,'REVALIDATE',key=vk,reason='changed').status_code==409


def test_binding_change_after_validation_requires_new_explicit_validation(link_fixture):
    f=link_fixture;parent,g,d,s=built(f);row=act(f,parent,read(f,parent).json(),'REVALIDATE').json();old=read(f,parent).json()
    with f[1].connect() as c:c.execute('UPDATE service_receipt_steps SET revision=revision+1 WHERE id=%s',(UUID(s['step']['id']),))
    now=read(f,parent).json();assert not now['verification_current'] and not any(now['checks'].values())
    assert act(f,parent,old,'CLOSE_LOCAL_RECORD').status_code==409
    row=act(f,parent,now,'REVALIDATE').json();assert act(f,parent,read(f,parent).json(),'CLOSE_LOCAL_RECORD').status_code==200


@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_close_requests_atomic_one_event_or_same_key_replay(link_fixture,same_key):
    f=link_fixture;parent,g,d,s=built(f);act(f,parent,read(f,parent).json(),'REVALIDATE');row=read(f,parent).json();key=uuid4().hex
    body=lc.Command(action='CLOSE_LOCAL_RECORD',expected_revision=row['revision'],expected_cycle=row['cycle'],expected_snapshot_sha256=row['current_snapshot_sha256'],reason='SYNTHETIC close')
    def send(_):
        try:return lc.command(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),key if same_key else uuid4().hex,body)['local_record_state']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(send,range(2)))
    assert out.count('CONFLICT')==(0 if same_key else 1) and counts(f)==[1,2]


def test_close_and_reopen_with_stale_same_revision_cannot_both_commit(link_fixture):
    f=link_fixture;parent,g,d,s,row=closed(f);opened=act(f,parent,row,'REOPEN').json();row=read(f,parent).json();act(f,parent,row,'REVALIDATE');row=read(f,parent).json()
    def send(action):
        data=lc.Command(action=action,expected_revision=row['revision'],expected_cycle=row['cycle'],expected_snapshot_sha256=row['current_snapshot_sha256'],reason='SYNTHETIC race')
        try:return lc.command(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,data)['local_record_state']
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(send,['CLOSE_LOCAL_RECORD','REOPEN']))
    assert out==['LOCAL_RECORD_CLOSED','CONFLICT'] and counts(f)==[1,5]


def test_event_failure_rolls_back_case_state_and_validation_ledger(link_fixture):
    f=link_fixture;parent,g,d,s=built(f);row=read(f,parent).json();before=counts(f)
    with f[1].connect() as c:c.execute('REVOKE INSERT ON case_local_events FROM parkweave_app')
    body=lc.Command(action='REVALIDATE',expected_revision=0,expected_cycle=1,expected_snapshot_sha256=row['current_snapshot_sha256'],reason='SYNTHETIC')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):lc.command(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,body)
    assert counts(f)==before and read(f,parent).json()['case_state']=='NEEDS_INPUT'


def test_repeat_migration_minimal_permissions_and_no_fulfilled_state(link_fixture):
    f=link_fixture;parent,g,d,s,row=closed(f);before=read(f,parent).json();f[1].migrate();f[1].migrate();assert read(f,parent).json()==before
    for sql in ('DELETE FROM case_local_lifecycles','UPDATE case_local_lifecycles SET case_id=case_id','UPDATE case_local_events SET payload=payload','DELETE FROM case_local_events'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)
    with pytest.raises(psycopg.errors.CheckViolation):
        with f[1].connect() as c:c.execute("UPDATE cases SET state='FULFILLED' WHERE id=%s",(UUID(parent['case_id']),))
    for sql in ("UPDATE case_local_lifecycles SET verified_sha256=NULL","UPDATE case_local_lifecycles SET state='REOPENED'"):
        with pytest.raises(psycopg.errors.CheckViolation):
            with f[1].connect() as c:c.execute(sql)


def test_resource_ends_while_close_waits_for_case_lock(link_fixture,monkeypatch):
    import threading,time
    f=link_fixture;parent,g,d,s=built(f);act(f,parent,read(f,parent).json(),'REVALIDATE')
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '1 hour',ends_at=clock_timestamp()+interval '1 second' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(UUID(g['id']),))
    row=read(f,parent).json();act(f,parent,row,'REVALIDATE');row=read(f,parent).json();entered=threading.Event();original=lc._sources
    def sources(*a):
        result=original(*a);entered.set();return result
    monkeypatch.setattr(lc,'_sources',sources)
    data=lc.Command(action='CLOSE_LOCAL_RECORD',expected_revision=row['revision'],expected_cycle=row['cycle'],expected_snapshot_sha256=row['current_snapshot_sha256'],reason='SYNTHETIC wait')
    def close():
        try:return lc.command(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,data)
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as blocker:
            blocker.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE',(UUID(parent['case_id']),))
            future=pool.submit(close);assert entered.wait(2);time.sleep(1.05)
        assert future.result(timeout=5)=='CONFLICT'
    assert counts(f)==[1,2] and read(f,parent).json()['local_record_state']=='READY'


@pytest.mark.parametrize('dependency',['resource_cancel','receipt_reopen'])
def test_close_and_dependency_change_have_serializable_effects(link_fixture,dependency):
    f=link_fixture;parent,g,d,s=built(f);act(f,parent,read(f,parent).json(),'REVALIDATE');row=read(f,parent).json()
    def close():
        try:return lc.command(f[0],f[2]['fixture-a'],UUID(parent['preparation_id']),uuid4().hex,lc.Command(action='CLOSE_LOCAL_RECORD',expected_revision=row['revision'],expected_cycle=row['cycle'],expected_snapshot_sha256=row['current_snapshot_sha256'],reason='SYNTHETIC concurrent close'))['local_record_state']
        except Conflict:return 'CONFLICT'
    def change():
        if dependency=='resource_cancel':return cancel(f,g['id']).status_code
        return receipt_act(f,s,'REOPEN').status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(close);b=pool.submit(change);out=a.result();assert b.result()==200
    after=read(f,parent).json();assert any(after['checks'].values()) and not after['verification_current']
    assert after['local_record_state']==('LOCAL_RECORD_CLOSED' if out=='LOCAL_RECORD_CLOSED' else 'READY')
    assert counts(f)==[1,2 if out=='LOCAL_RECORD_CLOSED' else 1]


def test_version_15_upgrade_preserves_existing_preparation_dispatch_receipt_resources(link_fixture):
    f=link_fixture;parent,g,d,s=built(f)
    with f[1].connect() as c:
        c.execute('DROP TABLE case_local_events');c.execute('DROP TABLE case_local_lifecycles');c.execute('DELETE FROM schema_version WHERE version>=16')
        before=[c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('preparations','service_dispatch_offers','service_step_receipts','case_resource_links','synthetic_resource_holds')]
    f[1].migrate()
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) n FROM schema_version').fetchone()['n']==21
        assert before==[c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('preparations','service_dispatch_offers','service_step_receipts','case_resource_links','synthetic_resource_holds')]
        c.execute(__import__('pathlib').Path('src/parkweave/roles.sql').read_text().replace('GRANT CONNECT ON DATABASE parkweave TO parkweave_app;',''))
    assert not any(read(f,parent).json()['checks'].values())
