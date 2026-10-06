"""Actual synthetic PG/API atomic notices, current authority and real crash recovery."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import json,os,subprocess,sys
from pathlib import Path
import psycopg,pytest
from parkweave import dispatch_notices as dn
from parkweave.store import Store,Conflict
from parkweave.process_env import minimal_environment
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture,ready
from test_service_dispatches import offer,command,REVIEWER


def drain(f):
    while dn.consume(f[0]):pass

def inbox(f,user):return f[3].get('/api/dispatch-notices',headers=headers(f[2],user))
def act(f,user,item,action):return f[3].post('/api/dispatch-notices/'+item['event_id']+'/commands',headers=headers(f[2],user),json={'action':action,'expected_revision':item['revision']})
def totals(f):
    with f[1].connect() as c:return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('dispatch_notice_outbox','dispatch_notices')]


def test_three_role_atomic_receivers_open_read_and_current_source_no_private_cache(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f,reason='<script>PRIVATE NOTICE REASON</script>');row=r.json()
    assert totals(f)==[2,0];drain(f)
    executor=inbox(f,'executor-a').json()['items'];owner=inbox(f,'fixture-a').json()['items']
    assert len(executor)==len(owner)==1 and not inbox(f,REVIEWER).json()['items']
    assert 'PRIVATE NOTICE REASON' not in inbox(f,'executor-a').text and parent['preparation_id'] in inbox(f,'executor-a').text
    x=executor[0];assert not x['historical'] and x['read_at'] is None and x['open_requested_at'] is None
    assert act(f,'executor-a',x,'MARK_READ').status_code==409
    opened=act(f,'executor-a',x,'OPEN').json()['notice'];marked=act(f,'executor-a',x,'MARK_READ').json()['notice']
    assert opened['open_requested_at'] and not opened['read_at'] and marked['read_at']
    assert act(f,'executor-a',x,'OPEN').json()['notice']==marked==act(f,'executor-a',x,'MARK_READ').json()['notice']
    accepted=command(f,row,'ACCEPT').json();assert accepted['receipt_step_id'];drain(f)
    assert len(inbox(f,REVIEWER).json()['items'])==1 and len(inbox(f,'fixture-a').json()['items'])==2
    assert inbox(f,'executor-a').json()['items'][0]['historical']
    assert not inbox(f,'fixture-a').json()['case_goal_completed'] and not inbox(f,'fixture-a').json()['external_send']
    assert dn.read(Store(f[0].dsn),f[2]['executor-a'],UUID(x['event_id']))['notice']['read_at']


@pytest.mark.parametrize('failure',['outbox','event'])
def test_notice_creation_failure_rolls_back_entire_business_change(receipt_fixture,failure):
    f=receipt_fixture;parent=ready(f)
    with f[1].connect() as c:c.execute('REVOKE INSERT ON '+('dispatch_notice_outbox' if failure=='outbox' else 'service_dispatch_events')+' FROM parkweave_app')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):offer(f,parent)
    with f[1].connect() as c:
        assert [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('service_dispatches','service_dispatch_offers','service_dispatch_events')]==[0,0,0]
    assert totals(f)==[0,0]


def test_same_business_key_and_concurrent_consumers_create_once(receipt_fixture):
    f=receipt_fixture;parent=ready(f);key=uuid4().hex;r,_,_=offer(f,parent,key=key);assert offer(f,parent,key=key)[0].json()==r.json();assert totals(f)==[2,0]
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:dn.consume(f[0]),range(8)))
    drain(f);assert totals(f)==[2,2]
    with f[1].connect() as c:assert c.execute("SELECT count(*) n FROM dispatch_notice_outbox WHERE state='PENDING'").fetchone()['n']==0


@pytest.mark.parametrize('kind',['assignment','read','inactive','role','tenant'])
@pytest.mark.parametrize('when',['before','after'])
def test_current_executor_authority_before_delivery_and_every_read_write(receipt_fixture,kind,when):
    f=receipt_fixture;row=offer(f)[0].json()
    if when=='after':drain(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        if kind=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        elif kind=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        elif kind=='inactive':c.execute("UPDATE principals SET active=false WHERE id='executor-a'")
        else:c.execute('UPDATE principals SET '+("role='resource_admin'" if kind=='role' else "org_id='org-b'")+" WHERE id='executor-a'")
        event=c.execute("SELECT event_id FROM dispatch_notice_outbox WHERE recipient_id='executor-a'").fetchone()['event_id']
    drain(f);r=inbox(f,'executor-a');assert r.status_code==403 or r.json()['items']==[]
    assert f[3].get('/api/dispatch-notices/'+str(event),headers=headers(f[2],'executor-a')).status_code==403
    x={'event_id':str(event),'revision':1}
    for action in ('OPEN','MARK_READ'):assert act(f,'executor-a',x,action).status_code==403
    if when=='before':
        with f[1].connect() as c:assert c.execute("SELECT state FROM dispatch_notice_outbox WHERE recipient_id='executor-a'").fetchone()['state']=='SUPPRESSED'


@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-b','executor-c','unassigned',REVIEWER])
def test_nonrecipient_cannot_read_or_mark_other_event(receipt_fixture,user):
    f=receipt_fixture;offer(f);drain(f);x=inbox(f,'executor-a').json()['items'][0]
    assert f[3].get('/api/dispatch-notices/'+x['event_id'],headers=headers(f[2],user)).status_code==403
    for action in ('OPEN','MARK_READ'):assert act(f,user,x,action).status_code==403


def test_revoked_before_delivery_is_not_resurrected_by_restore_or_business_replay(receipt_fixture):
    f=receipt_fixture;parent=ready(f);key=uuid4().hex;r,_,_=offer(f,parent,key=key)
    with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    drain(f)
    with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=true WHERE principal_id='executor-a'")
    assert offer(f,parent,key=key)[0].status_code==201;drain(f);assert not inbox(f,'executor-a').json()['items']
    assert totals(f)==[2,1]


def test_old_executor_notifications_do_not_reveal_new_offer_and_history_never_revives_state(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);old=r.json();drain(f);oldnotice=inbox(f,'executor-a').json()['items'][0]
    command(f,old,'DECLINE');drain(f)
    # Existing fixture-owner setup only, not app grant creation.
    with f[1].connect() as c:
        c.execute("INSERT INTO principals SELECT 'executor-second',token_hash||'x',park_id,org_id,'service_executor',true FROM principals WHERE id='executor-a'")
        c.execute("INSERT INTO capability_grants(principal_id,capability,active,park_id,org_id) SELECT 'executor-second',capability,active,park_id,org_id FROM capability_grants WHERE principal_id='executor-a'")
        c.execute("INSERT INTO run_assignments(run_id,principal_id,park_id,org_id,active) SELECT run_id,'executor-second',park_id,org_id,active FROM run_assignments WHERE principal_id='executor-a'")
    fresh=offer(f,parent,revision=2,executor='executor-second')[0];assert fresh.status_code==201;drain(f)
    visible=inbox(f,'executor-a');assert len(visible.json()['items'])==1 and visible.json()['items'][0]['historical']
    assert 'executor-second' not in visible.text
    with f[1].connect() as c:event=c.execute("SELECT event_id FROM dispatch_notice_outbox WHERE recipient_id='executor-second'").fetchone()['event_id']
    assert f[3].get('/api/dispatch-notices/'+str(event),headers=headers(f[2],'executor-a')).status_code==403
    assert act(f,'executor-a',oldnotice,'OPEN').status_code==200


def test_real_process_crash_before_ack_rolls_back_then_restart_delivers_once(receipt_fixture):
    f=receipt_fixture;offer(f)
    env=minimal_environment(os.environ,PYTHONPATH='src',PARKWEAVE_DSN=f[0].dsn)
    source="import os;from parkweave.store import Store;from parkweave.dispatch_notices import consume;consume(Store(os.environ['PARKWEAVE_DSN'],mode='FAULT_INJECTION'),crash_before_ack=True)"
    p=subprocess.run([sys.executable,'-c',source],env=env,capture_output=True,timeout=15);assert p.returncode==75 and totals(f)==[2,0]
    p=subprocess.run([sys.executable,'-m','parkweave.worker','--once'],env=env,capture_output=True,timeout=20);assert p.returncode==0 and totals(f)==[2,2]
    p=subprocess.run([sys.executable,'-m','parkweave.worker','--once'],env=env,capture_output=True,timeout=20);assert p.returncode==0 and totals(f)==[2,2]


def test_busy_outbox_skips_to_next_and_temporary_authority_wait_never_suppresses(receipt_fixture):
    f=receipt_fixture;offer(f)
    with f[1].connect() as c:
        first=c.execute("SELECT * FROM dispatch_notice_outbox ORDER BY event_id,recipient_id LIMIT 1 FOR UPDATE").fetchone()
        with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(dn.consume,f[0]).result(timeout=8)
        assert totals(f)==[2,1]
    drain(f);assert totals(f)==[2,2]
    # A locked principal is a transient conflict, never a SUPPRESSED notice.
    r,parent,_=offer(f,ready(f))
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(dn.consume,f[0]).result(timeout=8)
    with f[1].connect() as c:assert c.execute("SELECT count(*) n FROM dispatch_notice_outbox WHERE state='SUPPRESSED'").fetchone()['n']==0
    drain(f)


def test_read_only_owner_can_open_and_mark_no_execute_required(receipt_fixture):
    f=receipt_fixture;offer(f);drain(f);f[1].revoke_capability('fixture-a','EXECUTE');x=inbox(f,'fixture-a').json()['items'][0]
    assert act(f,'fixture-a',x,'OPEN').status_code==200 and act(f,'fixture-a',x,'MARK_READ').status_code==200


def test_notice_minimal_column_permissions_and_upgrade_without_legacy_backfill(receipt_fixture):
    f=receipt_fixture;r,parent,_=offer(f);before=r.json()
    with f[1].connect() as c:c.execute('DROP TABLE dispatch_notices,dispatch_notice_outbox');c.execute('DELETE FROM schema_version WHERE version>=17')
    f[1].migrate();f[1].migrate()
    # Keep the UUID fixture database boundary on native Windows too. Only the
    # CONNECT target is substituted; execute all real table/column grants intact.
    with f[1].connect() as c:
        roles=Path('src/parkweave/roles.sql').read_text().replace('GRANT CONNECT ON DATABASE parkweave','GRANT CONNECT ON DATABASE '+psycopg.sql.Identifier(c.info.dbname).as_string(c),1)
        c.execute(roles)
    assert totals(f)==[0,0] and not dn.consume(f[0])
    for sql in ('DELETE FROM dispatch_notice_outbox','UPDATE dispatch_notice_outbox SET recipient_id=recipient_id','DELETE FROM dispatch_notices','UPDATE dispatch_notices SET event_id=event_id'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)
    assert command(f,before,'WITHDRAW').status_code==200;drain(f);assert totals(f)==[2,2]


def test_busy_case_source_does_not_starve_other_pending_case(receipt_fixture,monkeypatch):
    f=receipt_fixture;r,a,_=offer(f);r,b,_=offer(f)
    # Force unrelated work beyond the bounded scan, rather than within its prefix.
    monkeypatch.setattr(dn,'SCAN_LIMIT',1)
    with f[1].connect() as c:
        first=c.execute("SELECT d.preparation_id FROM dispatch_notice_outbox n JOIN service_dispatch_events e ON e.id=n.event_id JOIN service_dispatches d ON d.id=e.dispatch_id ORDER BY n.event_id,n.recipient_id LIMIT 1").fetchone()['preparation_id']
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(first,))
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert not pool.submit(dn.consume,f[0]).result(timeout=5)
            assert not pool.submit(dn.consume,f[0]).result(timeout=5)
            assert pool.submit(dn.consume,f[0]).result(timeout=5)
        delivered=c.execute('SELECT d.preparation_id FROM dispatch_notices n JOIN service_dispatch_events e ON e.id=n.event_id JOIN service_dispatches d ON d.id=e.dispatch_id').fetchall()
        assert delivered and all(x['preparation_id']!=first for x in delivered)
        assert c.execute("SELECT count(*) n FROM dispatch_notice_outbox WHERE state='SUPPRESSED'").fetchone()['n']==0
    drain(f);assert totals(f)==[4,4]


@pytest.mark.parametrize('recipient',['fixture-a',REVIEWER])
@pytest.mark.parametrize('when',['before','after'])
def test_current_preparation_grant_controls_owner_and_reviewer_notices(receipt_fixture,recipient,when):
    f=receipt_fixture;r,_,_=offer(f)
    if recipient==REVIEWER:assert command(f,r.json(),'DECLINE').status_code==200
    if when=='after':drain(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,recipient,exclusive=True)
        c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(recipient,))
        events=c.execute('SELECT event_id FROM dispatch_notice_outbox WHERE recipient_id=%s',(recipient,)).fetchall()
    drain(f);assert inbox(f,recipient).status_code==403
    for event in events:
        item={'event_id':str(event['event_id']),'revision':1 if recipient=='fixture-a' else 2}
        assert f[3].get('/api/dispatch-notices/'+item['event_id'],headers=headers(f[2],recipient)).status_code==403
        for action in ('OPEN','MARK_READ'):assert act(f,recipient,item,action).status_code==403
    if when=='before':
        with f[1].connect() as c:assert not c.execute("SELECT 1 FROM dispatch_notice_outbox WHERE recipient_id=%s AND state<>'SUPPRESSED'",(recipient,)).fetchone()


def test_parallel_open_and_read_preserve_first_monotonic_timestamps(receipt_fixture):
    f=receipt_fixture;offer(f);drain(f);x=inbox(f,'executor-a').json()['items'][0]
    def call(action):return dn.command(f[0],f[2]['executor-a'],UUID(x['event_id']),dn.Command(action=action,expected_revision=x['revision']))['notice']
    with ThreadPoolExecutor(max_workers=4) as pool:opened=list(pool.map(call,['OPEN']*8))
    assert len({n['open_requested_at'] for n in opened})==1
    with ThreadPoolExecutor(max_workers=4) as pool:marked=list(pool.map(call,['MARK_READ']*8))
    assert len({n['read_at'] for n in marked})==1 and all(n['read_at']>=n['open_requested_at'] for n in marked)
    assert call('OPEN')==call('MARK_READ')==marked[0]
