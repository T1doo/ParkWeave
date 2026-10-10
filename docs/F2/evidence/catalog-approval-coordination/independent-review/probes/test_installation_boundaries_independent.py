"""Independent same/different key fresh/repeated installation and live consumption."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event,local
from queue import Queue
from pathlib import Path
from uuid import UUID,uuid4
import json,time,pytest
from parkweave import catalog_publication as pub,service_plan_approval as approval,case_resource_delivery as delivery
from test_service_plan_approval import link_fixture,receipt_fixture,preparation_fixture,enable,approved,ledger
from test_preparation import create
from test_case_resource_delivery import prepared,quoted,effects,recover
from test_resource_bundles import bundle,states
from test_service_case_steps import adopt,adopt_body,verified,read as plan_read
OUT=Path('.runtime/independent-catalog-approval-coordination-final-review/installation')

def actual_locks(f,pid):
    with f[1].connect() as c:return c.execute("SELECT l.locktype,l.mode,l.granted,r.relname FROM pg_locks l LEFT JOIN pg_class r ON r.oid=l.relation WHERE l.pid=%s",(pid,)).fetchall()

def waited(f,pid,kind):
    end=time.monotonic()+6
    while time.monotonic()<end:
        records=actual_locks(f,pid)
        if any(r['locktype']==kind and not r['granted'] for r in records):return records
        time.sleep(.02)
    raise AssertionError('real expected installation lock wait not observed')

def parents(f,ids):
    with f[1].connect() as c:return c.execute('SELECT * FROM preparations WHERE id=ANY(%s)',([UUID(i) for i in ids],)).fetchall()

def heads(f,keys):
    with f[1].connect() as c:return [pub.proof(pub.row(c,key)) for key in keys]

def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')

@pytest.mark.parametrize('other_user',['fixture-b','fixture-c'])
@pytest.mark.parametrize('already_installed',[False,True])
def test_two_original_keys_fresh_or_repeated_installations_serialize_and_preserve_head(link_fixture,monkeypatch,other_user,already_installed):
    f=link_fixture;pa,_,_=create(f);pc,_,_=create(f,user=other_user);ba=enable(f,pa);bc=enable(f,pc)
    ka,kc=[pub.key_of(r) for i in [pa,pc] for r in parents(f,[i['preparation_id']])];different=ka!=kc;assert different==(other_user=='fixture-c')
    if already_installed:
        pub.IsolatedCatalogPublication(ba,enabled_for_isolated_tests=True);pub.IsolatedCatalogPublication(bc,enabled_for_isolated_tests=True)
    original=heads(f,[ka,kc]);entered=Event();release=Event();second_pids=Queue();context=local();schema=pub.IsolatedCatalogPublication._schema;lock=pub.lock
    def hold_first(self,c):
        result=schema(self,c)
        if self.approval is ba:entered.set();assert release.wait(8)
        return result
    def observe(c,key,exclusive=False):
        if exclusive and getattr(context,'bridge',None) is bc:second_pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
        return lock(c,key,exclusive)
    monkeypatch.setattr(pub.IsolatedCatalogPublication,'_schema',hold_first);monkeypatch.setattr(pub,'lock',observe)
    def activate(bridge):
        context.bridge=bridge
        try:pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True);return 'ACTIVATED'
        except Exception as e:return type(e).__name__
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(activate,ba)
        try:
            assert entered.wait(5);b=pool.submit(activate,bc);pid=second_pids.get(timeout=5);records=waited(f,pid,'relation' if different else 'advisory')
            if different:assert any(r['locktype']=='advisory' and r['mode']=='ExclusiveLock' and r['granted'] for r in records)
            assert not b.done() and effects(f)==[0]*5
        finally:release.set()
        results={'first':a.result(timeout=12),'second':b.result(timeout=12)}
    after=heads(f,[ka,kc]);save(other_user+'-'+str(already_installed),{'different_keys':different,'already_installed':already_installed,'wait_locks':records,'results':results,'original_heads':original,'heads':after,'effects':effects(f)})
    assert results=={'first':'ACTIVATED','second':'ACTIVATED'} and all(h['revision']==1 for h in after)
    if already_installed:assert after==original
    assert ledger(f,pa) is None and ledger(f,pc) is None and effects(f)==[0]*5
    with f[0].connect() as c:assert c.execute("SELECT has_table_privilege(current_user,'preparation_catalog','SELECT') s,has_table_privilege(current_user,'preparation_catalog','UPDATE') u").fetchone()=={'s':True,'u':False}


def test_repeated_setup_waits_for_other_original_case_full_consumption_commit(link_fixture,monkeypatch):
    f=link_fixture;pa=prepared(f);pb=prepared(f);hs,d=bundle(f)
    bridge=approval.IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,preparation_ids=[pa['preparation_id'],pb['preparation_id']],enabled_for_isolated_tests=True);bridge.attach_store(f[0]);protocol=pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True)
    for p in [pa,pb]:
        body={**adopt_body(f,p),'expected_plan_revision':plan_read(f,p).json()['revision']};assert adopt(f,p,body).status_code==201;verified(f,p,'P1')
    data=quoted(f,pb,d);item,_=approved(f,pb,data);key=uuid4().hex;initial=heads(f,[protocol.parents[pb['preparation_id']]])
    entered=Event();release=Event();pids=Queue();check=bridge.recheck;lock=pub.lock
    def pause(store,c,value):
        result=check(store,c,value)
        if value['consumed']:entered.set();assert release.wait(8)
        return result
    def observe(c,target,exclusive=False):
        if exclusive:pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
        return lock(c,target,exclusive)
    monkeypatch.setattr(bridge,'recheck',pause);monkeypatch.setattr(pub,'lock',observe)
    def consume():return delivery.deliver(f[0],f[2]['fixture-a'],UUID(pb['preparation_id']),key,delivery.Deliver(**{**data,'approval_id':item['id']}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(consume)
        try:
            assert entered.wait(5);b=pool.submit(pub.IsolatedCatalogPublication,bridge,enabled_for_isolated_tests=True);pid=pids.get(timeout=5);records=waited(f,pid,'advisory')
            assert not any(r['relname']=='preparation_catalog' and r['mode']=='AccessExclusiveLock' and r['granted'] for r in records)
            assert not b.done() and effects(f)==[0]*5
        finally:release.set()
        result=a.result(timeout=12);b.result(timeout=12)
    assert heads(f,[protocol.parents[pb['preparation_id']]])==initial and ledger(f,pa) is None and ledger(f,pb)['revision']==3
    assert states(f,hs)==['CONFIRMED']*3 and effects(f)==[1,3,1,1,1]
    cold=recover(f,pb,key);assert cold.status_code==200 and cold.json()['receipt']==result['receipt'] and cold.json()['independent_check']['status']=='CURRENT'
    save('other-case-consumption-repeat-setup',{'real_advisory_wait':records,'head_preserved':True,'other_case_ledger_empty':True,'consumed_case_revision':3,'effects':effects(f),'cold_receipt_current':True})


def test_multiple_original_keys_acquired_in_stable_order_before_relation_installation(link_fixture,monkeypatch):
    f=link_fixture;pa,_,_=create(f);pc,_,_=create(f,user='fixture-c');ids=[pa['preparation_id'],pc['preparation_id']]
    bridge=approval.IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,preparation_ids=ids,enabled_for_isolated_tests=True)
    wanted=sorted(pub.key_of(r) for r in parents(f,ids));seen=[];lock=pub.lock;schema=pub.IsolatedCatalogPublication._schema;schema_locks=[]
    def observe(c,key,exclusive=False):
        records=actual_locks(f,c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
        assert not any(r['relname']=='preparation_catalog' and r['mode']=='AccessExclusiveLock' and r['granted'] for r in records)
        assert exclusive;seen.append(key);return lock(c,key,exclusive)
    def capture(self,c):
        result=schema(self,c);schema_locks.extend(actual_locks(f,c.execute('SELECT pg_backend_pid() pid').fetchone()['pid']));return result
    monkeypatch.setattr(pub,'lock',observe);monkeypatch.setattr(pub.IsolatedCatalogPublication,'_schema',capture)
    protocol=pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True)
    assert seen==wanted and len(set(seen))==2
    assert sum(r['locktype']=='advisory' and r['mode']=='ExclusiveLock' and r['granted'] for r in schema_locks)==2
    assert any(r['relname']=='preparation_catalog' and r['mode']=='AccessExclusiveLock' and r['granted'] for r in schema_locks)
    assert all(h['revision']==1 for h in heads(f,wanted)) and effects(f)==[0]*5
    save('stable-multiple-keys',{'stable_key_order':True,'keys_count':2,'actual_locks_at_schema':schema_locks,'all_source_keys_exclusive_before_relation':True,'heads':[h['revision'] for h in heads(f,wanted)],'effects':effects(f)})
