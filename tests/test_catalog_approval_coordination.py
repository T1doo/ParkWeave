"""Real independent PG connections for cooperative publication vs actual commit."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID,uuid4
from queue import Queue
from threading import Event
import time
import psycopg,pytest
from parkweave import catalog_publication as pub,case_resource_delivery as delivery
from parkweave.store import Conflict,Denied
from test_service_plan_approval import (link_fixture,receipt_fixture,preparation_fixture,enable,approved,ledger,read,propose)
from test_case_resource_delivery import prepared,quoted,submit,effects,recover
from test_resource_bundles import bundle,states
from test_service_case_steps import adopt,adopt_body,verified,read as plan_read
from test_preparation import headers


def setup(f):
    p=prepared(f);hs,d=bundle(f);bridge=enable(f,p)
    protocol=pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True)
    body={**adopt_body(f,p),'expected_plan_revision':plan_read(f,p).json()['revision']}
    r=adopt(f,p,body);assert r.status_code==201,r.text
    verified(f,p,'P1');data=quoted(f,p,d);return p,hs,data,bridge,protocol


def publish(protocol,p,revision=1,source_revision=2,action='PUBLISH',key=None):
    return protocol.publish(p['preparation_id'],key or uuid4().hex,dict(action=action,expected_revision=revision,
        reason='SYNTHETIC explicit source '+action,**({'source_revision':source_revision} if action=='PUBLISH' else {})))


def catalog(f,p):
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        return pub.row(c,pub.key_of(parent))


def wait_blocked(f,pid):
    end=time.monotonic()+5
    while time.monotonic()<end:
        with f[1].connect() as c:
            r=c.execute("SELECT wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock'",(pid,)).fetchone()
            pending=c.execute("SELECT 1 FROM pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted",(pid,)).fetchone()
        if r and pending:return
        time.sleep(.02)
    raise AssertionError('actual publisher advisory wait not observed')


@pytest.mark.parametrize('action',['PUBLISH','WITHDRAW','ABA','same_source'])
def test_publication_commits_first_old_approval_cannot_execute_or_revive(link_fixture,action):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    if action=='WITHDRAW':publish(protocol,p,action='WITHDRAW')
    elif action=='same_source':publish(protocol,p,source_revision=1)
    else:
        publish(protocol,p)
        if action=='ABA':publish(protocol,p,revision=2,source_revision=1)
    r=read(f,p);assert r.status_code==200,r.text
    assert not r.json()['items'][-1]['current_available']
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
    assert ledger(f,p)==before and effects(f)==[0]*5 and states(f,hs)==['HELD']*3
    assert plan_read(f,p).json()['binding_issues']


@pytest.mark.parametrize('rollback',[False,True])
def test_delivery_final_validation_first_publisher_waits_through_commit_or_rollback(link_fixture,monkeypatch,rollback):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data)
    entered=Event();release=Event();pids=Queue();old=bridge.recheck;old_lock=pub.lock
    def pause(store,c,check):
        old(store,c,check)
        if check['consumed']:
            entered.set();assert release.wait(8)
            if rollback:raise Conflict('SYNTHETIC fail after final source check')
    def observed(c,key,exclusive=False):
        if exclusive:pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
        return old_lock(c,key,exclusive)
    monkeypatch.setattr(bridge,'recheck',pause);monkeypatch.setattr(pub,'lock',observed)
    def consume():
        try:return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**{**data,'approval_id':item['id']}))
        except Conflict:return 'ROLLED_BACK'
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=pool.submit(consume)
        try:
            assert entered.wait(5);publisher=pool.submit(publish,protocol,p);pid=pids.get(timeout=5);wait_blocked(f,pid)
            assert not publisher.done() and effects(f)==[0]*5 and pub.proof(catalog(f,p))['revision']==1
        finally:release.set()
        actual=result.result(timeout=10);event=publisher.result(timeout=10)
    assert event['revision']==2 and pub.proof(catalog(f,p))['revision']==2
    assert effects(f)==([0]*5 if rollback else [1,3,1,1,1])
    assert states(f,hs)==(['HELD']*3 if rollback else ['CONFIRMED']*3)
    assert (actual=='ROLLED_BACK')==rollback
    assert ledger(f,p)['revision']==(2 if rollback else 3)


def test_owner_publication_failure_rolls_back_source_history_and_head(link_fixture,monkeypatch):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);before=catalog(f,p);old=protocol._append
    def failure(*args,**kwargs):old(*args,**kwargs);raise RuntimeError('SYNTHETIC publication failure')
    with monkeypatch.context() as m:
        m.setattr(protocol,'_append',failure)
        with pytest.raises(RuntimeError):publish(protocol,p)
    assert catalog(f,p)==before and effects(f)==[0]*5
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==201


def test_another_original_approval_bridge_cannot_bypass_activated_catalog_protocol(link_fixture):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    fresh=enable(f,p)
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==403
    assert ledger(f,p)==before and effects(f)==[0]*5
    pub.IsolatedCatalogPublication(fresh,enabled_for_isolated_tests=True)
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==201


def test_shared_catalog_lock_precedes_any_resource_lock_in_original_delivery(link_fixture,monkeypatch):
    from parkweave import resource_holds as rh
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);old=rh._lock;seen=[]
    name=pub.lock_name(protocol.parents[p['preparation_id']])
    def checked(c,id,shared=False):
        locked=c.execute("SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory' AND granted AND mode='ShareLock' AND classid=((hashtextextended(%s,0)>>32)&4294967295)::oid AND objid=(hashtextextended(%s,0)&4294967295)::oid",(name,name)).fetchone()
        assert locked;seen.append(str(id));return old(c,id,shared)
    monkeypatch.setattr(rh,'_lock',checked)
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==201
    assert seen and effects(f)==[1,3,1,1,1]


def test_catalog_stays_select_only_for_application_and_default_off(link_fixture):
    f=link_fixture;p=prepared(f)
    with f[0].connect() as c:
        assert c.execute("SELECT has_table_privilege(current_user,'preparation_catalog','SELECT') s,has_table_privilege(current_user,'preparation_catalog','UPDATE') u,has_table_privilege(current_user,'preparation_catalog','INSERT') i").fetchone()=={'s':True,'u':False,'i':False}
    bridge=enable(f,p)
    with pytest.raises(Denied):pub.IsolatedCatalogPublication(bridge)
    protocol=pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True)
    for query in ('UPDATE preparation_catalog SET source=source','UPDATE preparation_catalog SET candidate_catalog_head=NULL','DELETE FROM preparation_catalog'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(query)
    assert pub.proof(catalog(f,p))['revision']==1
    assert f[3].post('/api/catalog/publications',json={}).status_code==404


def test_publication_cas_idempotency_immutable_prefix_head_and_rewithdraw(link_fixture):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);original=catalog(f,p);key=uuid4().hex
    e=publish(protocol,p,key=key);assert publish(protocol,p,key=key)==e
    with pytest.raises(Conflict):publish(protocol,p,key=key,source_revision=3)
    with pytest.raises(Conflict):publish(protocol,p)
    for query in ('UPDATE preparation_catalog SET candidate_catalog_head=NULL','UPDATE preparation_catalog SET candidate_catalog_revisions=NULL','UPDATE preparation_catalog SET source=source-\'revision\''):
        with pytest.raises(psycopg.Error):
            with f[1].connect() as c:c.execute(query)
    x=catalog(f,p);assert x[pub.COL]['events'][:1]==original[pub.COL]['events']
    withdraw=publish(protocol,p,revision=2,action='WITHDRAW');assert withdraw['state']=='WITHDRAWN'
    new=publish(protocol,p,revision=3,source_revision=1);assert new['state']=='ACTIVE' and new['id']!=original[pub.HEAD]['id']
    assert effects(f)==[0]*5


def test_publication_after_committed_delivery_preserves_receipt_but_current_sources_stay_stale(link_fixture):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);key=uuid4().hex
    assert submit(f,p,{**data,'approval_id':item['id']},key).status_code==201
    verified(f,p,'P2');original=ledger(f,p);old=recover(f,p,key).json()['receipt']
    publish(protocol,p,source_revision=1)
    publish(protocol,p,revision=2,source_revision=2)
    publish(protocol,p,revision=3,source_revision=1)
    r=recover(f,p,key);assert r.status_code==200,r.text
    assert r.json()['receipt']==old and r.json()['independent_check']['status']=='NEEDS_RECHECK'
    assert ledger(f,p)==original and effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3
    assert plan_read(f,p).json()['binding_issues']


def test_shared_catalog_wait_crosses_deadline_without_any_delivery_effect(link_fixture,monkeypatch):
    from datetime import timedelta,datetime
    from parkweave import controlled_plans as cp,resource_holds as rh
    f=link_fixture;p,hs,data,bridge,protocol=setup(f)
    with f[0].connect() as c:
        principal=c.execute("SELECT * FROM principals WHERE id='fixture-a'").fetchone()
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        _,source,_,now=delivery._candidate(f[0],c,principal,parent,delivery.Deliver(**data))
    deadline=now+timedelta(seconds=2);data={**data,'valid_until':deadline.isoformat(),'expected_source_sha256':cp._hash(dict(source=source,valid_until=deadline.isoformat()))}
    item,_=approved(f,p,data);original=ledger(f,p);pids=Queue();old_lock=pub.lock;target=protocol.parents[p['preparation_id']]
    def observed(c,key,exclusive=False):
        if not exclusive:pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
        return old_lock(c,key,exclusive)
    def consume():
        try:return delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**{**data,'approval_id':item['id']}))
        except Conflict:return 'EXPIRED'
    with ThreadPoolExecutor(max_workers=1) as pool:
        with f[1].connect() as block:
            old_lock(block,target,exclusive=True);monkeypatch.setattr(pub,'lock',observed)
            future=pool.submit(consume);wait_blocked(f,pids.get(timeout=5))
            while rh._now(block)<deadline:time.sleep(.02)
            assert not future.done() and effects(f)==[0]*5
        assert future.result(timeout=5)=='EXPIRED'
    assert ledger(f,p)==original and effects(f)==[0]*5 and states(f,hs)==['HELD']*3


def test_reachable_publication_limit_preserves_last_explicit_withdrawal_and_history(link_fixture):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);first=catalog(f,p)[pub.COL]['events'][0];key=uuid4().hex
    for revision in range(1,31):
        event=publish(protocol,p,revision=revision,source_revision=revision,key=key if revision==30 else None)
    assert event['revision']==31 and pub.proof(catalog(f,p))['state']=='ACTIVE'
    with pytest.raises(Conflict):publish(protocol,p,revision=31)
    withdraw=publish(protocol,p,revision=31,action='WITHDRAW');assert withdraw['revision']==32
    assert publish(protocol,p,revision=30,source_revision=30,key=key)==event
    with pytest.raises(Conflict):publish(protocol,p,revision=32)
    value=catalog(f,p);assert value[pub.COL]['events'][0]==first
    assert pub.proof(value)['state']=='WITHDRAWN' and len(value[pub.COL]['events'])==32 and effects(f)==[0]*5


@pytest.mark.parametrize('publisher_first',[False,True])
def test_first_installation_takes_catalog_key_before_ddl_and_consumer_cannot_deadlock(link_fixture,monkeypatch,publisher_first):
    from test_service_plan_approval import setup as original_setup
    f=link_fixture;p,hs,data,bridge=original_setup(f);item,_=approved(f,p,data);before=deepcopy(ledger(f,p))
    entered=Event();release=Event();publisher_pids=Queue();consumer_pids=Queue();old=pub.lock
    def controlled(c,key,exclusive=False):
        pid=c.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
        if exclusive:
            publisher_pids.put(pid)
            if publisher_first:old(c,key,exclusive)
            entered.set();assert release.wait(8)
            if not publisher_first:return old(c,key,exclusive)
        else:
            consumer_pids.put(pid);return old(c,key,exclusive)
    monkeypatch.setattr(pub,'lock',controlled)
    def activate():
        try:pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True);return 'ACTIVATED'
        except Exception as e:return type(e).__name__
    def consume():
        try:delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**{**data,'approval_id':item['id']}));return 'COMMITTED'
        except Exception as e:return type(e).__name__
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(activate)
        try:
            assert entered.wait(5);publisher_pid=publisher_pids.get(timeout=5)
            b=pool.submit(consume);consumer_pid=consumer_pids.get(timeout=5)
            if publisher_first:
                wait_blocked(f,consumer_pid)
                assert not b.done() and effects(f)==[0]*5
                with f[1].connect() as c:
                    assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparation_catalog' AND column_name=%s",(pub.COL,)).fetchone()
                    assert not c.execute("SELECT 1 FROM pg_locks WHERE pid=%s AND relation='preparation_catalog'::regclass AND mode='AccessExclusiveLock'",(publisher_pid,)).fetchone()
            else:
                # The owner paused before requesting its first key: no DDL relation
                # lock may exist, so the original consumer can commit independently.
                assert b.result(timeout=5)=='COMMITTED'
                assert effects(f)==[1,3,1,1,1]
                with f[1].connect() as c:
                    assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparation_catalog' AND column_name=%s",(pub.COL,)).fetchone()
                    assert not c.execute("SELECT 1 FROM pg_locks WHERE pid=%s AND relation='preparation_catalog'::regclass AND mode='AccessExclusiveLock'",(publisher_pid,)).fetchone()
        finally:release.set()
        outcomes={'publisher':a.result(timeout=12),'consumer':b.result(timeout=12)}
    assert outcomes['publisher']=='ACTIVATED' and 'DeadlockDetected' not in outcomes.values()
    assert pub.proof(catalog(f,p))['revision']==1
    if publisher_first:
        assert outcomes['consumer'] in ('Conflict','Denied') and effects(f)==[0]*5
        assert ledger(f,p)==before and states(f,hs)==['HELD']*3
    else:
        assert outcomes['consumer']=='COMMITTED' and ledger(f,p)['revision']==3
        assert states(f,hs)==['CONFIRMED']*3
