"""Prepared independent activation regression: acquire key before relation/DDL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from queue import Queue
from pathlib import Path
from uuid import UUID,uuid4
import time,json,pytest
from parkweave import catalog_publication as pub,case_resource_delivery as delivery
from test_service_plan_approval import link_fixture,receipt_fixture,preparation_fixture,setup as original_setup,approved,ledger
from test_case_resource_delivery import effects,recover
from test_resource_bundles import states
OUT=Path('.runtime/independent-catalog-approval-coordination-final-review/activation-regression')

def locks(f,pid):
    with f[1].connect() as c:
        return c.execute("SELECT l.locktype,l.mode,l.granted,r.relname FROM pg_locks l LEFT JOIN pg_class r ON r.oid=l.relation WHERE l.pid=%s",(pid,)).fetchall()

def wait_shared_or_exclusive(f,pid,mode,granted):
    end=time.monotonic()+6
    while time.monotonic()<end:
        value=locks(f,pid)
        if any(x['locktype']=='advisory' and x['mode']==mode and x['granted']==granted for x in value):return value
        time.sleep(.02)
    raise AssertionError('real expected catalog advisory wait not observed')

@pytest.mark.parametrize('first',['consumer','activation'])
def test_activation_and_consumer_serialize_before_any_catalog_ddl(link_fixture,monkeypatch,first):
    f=link_fixture;p,hs,data,bridge=original_setup(f);item,_=approved(f,p,data)
    held=Event();release=Event();owner_pids=Queue();consumer_pids=Queue();old=pub.lock;before_exclusive=[];key=uuid4().hex
    def controlled(c,target,exclusive=False):
        pid=c.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
        if exclusive:
            owner_pids.put(pid);before_exclusive.extend(locks(f,pid))
        else:consumer_pids.put(pid)
        result=old(c,target,exclusive)
        if (exclusive and first=='activation') or (not exclusive and first=='consumer'):
            held.set();assert release.wait(8)
        return result
    monkeypatch.setattr(pub,'lock',controlled)
    def activate():
        try:pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True);return 'ACTIVATED'
        except Exception as e:return type(e).__name__
    def consume():
        try:delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,delivery.Deliver(**{**data,'approval_id':item['id']}));return 'COMMITTED'
        except Exception as e:return type(e).__name__
    with ThreadPoolExecutor(max_workers=2) as pool:
        lead=pool.submit(consume if first=='consumer' else activate)
        try:
            assert held.wait(5)
            tail=pool.submit(activate if first=='consumer' else consume)
            if first=='consumer':
                owner=owner_pids.get(timeout=5);waiting=wait_shared_or_exclusive(f,owner,'ExclusiveLock',False)
            else:
                consumer=consumer_pids.get(timeout=5);waiting=wait_shared_or_exclusive(f,consumer,'ShareLock',False)
        finally:release.set()
        lead_result=lead.result(timeout=12);tail_result=tail.result(timeout=12)
    outcomes={'consumer':lead_result if first=='consumer' else tail_result,'publisher':tail_result if first=='consumer' else lead_result}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(first+'-first.json')).write_text(json.dumps({'first':first,'before_exclusive':before_exclusive,'actual_advisory_wait':waiting,'outcomes':outcomes,'effects':effects(f),'approval_revision':ledger(f,p)['revision']},indent=2)+'\n')
    assert not any(x['relname']=='preparation_catalog' and x['mode']=='AccessExclusiveLock' and x['granted'] for x in before_exclusive)
    assert outcomes['publisher']=='ACTIVATED' and 'DeadlockDetected' not in outcomes.values()
    if first=='consumer':
        assert outcomes['consumer']=='COMMITTED' and effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3
        result=recover(f,p,key);assert result.status_code==200 and result.json()['independent_check']['status']=='NEEDS_RECHECK'
    else:
        assert outcomes['consumer'] in ('Conflict','Denied') and effects(f)==[0]*5 and states(f,hs)==['HELD']*3
