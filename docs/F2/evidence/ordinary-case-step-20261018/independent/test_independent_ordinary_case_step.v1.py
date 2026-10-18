"""Literal ordinary-admission probes; no issuance wrapper or authority creation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID,uuid4
import json,os,time
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from parkweave import case_step_assignments as cs, dispatch_notices as dn
from parkweave.api import configured_app
from parkweave.store import Store
from test_preparation import preparation_fixture,create,add,command as material,headers
from test_executor_receipts import receipt_fixture,act
from test_service_dispatches import offer,command as decide
from test_case_step_assignments import ok,REVIEWER
from ordinary_case_step_support import ordinary_api,worker_once
from service_release_acceptance_support import authority_snapshot

OUT=Path(os.environ['PARKWEAVE_INDEPENDENT_ORDINARY_EVIDENCE'])
CONFIGS=('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG','PARKWEAVE_SERVICE_PROFILE','PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG')

def record(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(name+'.json')).write_text(json.dumps(data,sort_keys=True,indent=2,default=str)+'\n')

@pytest.fixture
def normal(receipt_fixture,monkeypatch):
    for key in CONFIGS:monkeypatch.delenv(key,raising=False)
    f=receipt_fixture
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn)
    monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    monkeypatch.setenv('PARKWEAVE_CASE_STEP_MODE',cs.ORDINARY_MODE)
    with TestClient(configured_app()) as api:yield (*f[:3],api)

def ready(f,user='fixture-a',label='A'):
    p,_,_=create(f,user=user,goal='PRIVATE_ORDINARY_'+label)
    p=ok(add(f,p,text='PRIVATE_NEED_'+label,user=user))
    p=ok(add(f,p,'material_outline','PRIVATE_OUTLINE_'+label,user=user))
    p=ok(material(f,p,'REVIEW','prep-specialist-'+user,reason='SYNTHETIC reviewed '+label))
    return ok(material(f,p,'CONFIRM',user,reason='SYNTHETIC confirmed '+label))

def read(f,d,user='executor-a'):
    return f[3].get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],user))

def inbox(f,user='executor-a'):
    return ok(f[3].get('/api/dispatch-notices',headers=headers(f[2],user)))['items']

def note(f,n,action,user='executor-a'):
    return f[3].post('/api/dispatch-notices/'+n['event_id']+'/commands',headers=headers(f[2],user),json={'action':action,'expected_revision':n['revision']})

def business(owner):
    with owner.connect() as c:
        return {t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events')}

def test_independent_two_domains_parallel_context_and_exact_recovery(normal):
    f=normal;baseline=authority_snapshot(f[1]);a=ready(f,label='DOMAIN_A');b=ready(f,'fixture-b','DOMAIN_B')
    with ordinary_api(f,OUT/'two-domains-api') as api:
        cold=(*f[:3],api)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(offer,cold,a),pool.submit(offer,cold,b,user='prep-specialist-fixture-b',executor='executor-b')]
            da,db=[ok(x.result()[0],201) for x in futures]
        keys=[uuid4().hex,uuid4().hex]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(decide,cold,da,'ACCEPT',key=keys[0]),pool.submit(decide,cold,db,'ACCEPT',user='executor-b',key=keys[1])]
            done=[ok(x.result()) for x in futures]
        for p,d,actor,key in [(a,done[0],'executor-a',keys[0]),(b,done[1],'executor-b',keys[1])]:
            x=ok(read(cold,d,actor));assert x['case_id']==p['case_id'] and x['run_id']==p['run_id'] and x['preparation_id']==p['preparation_id']
            assert all(secret not in json.dumps(x) for secret in ['PRIVATE_ORDINARY_DOMAIN_A','PRIVATE_ORDINARY_DOMAIN_B','PRIVATE_NEED_','PRIVATE_OUTLINE_'])
            other='executor-b' if actor=='executor-a' else 'executor-a';ok(read(cold,d,other),403)
            q=dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],offer_id=d['current_offer']['id'],expected_revision=1,preparation_revision=p['revision'])
            r=ok(api.get('/api/service-dispatches/'+d['dispatch_id']+'/accept-recovery',params=q,headers=headers(f[2],actor,key)))
            assert r['status']=='COMMITTED' and r['event']['receipt_step_id']==d['receipt_step_id']
            q['case_id']=b['case_id'] if p is a else a['case_id']
            ok(api.get('/api/service-dispatches/'+d['dispatch_id']+'/accept-recovery',params=q,headers=headers(f[2],actor,key)),403)
        assert authority_snapshot(f[1])==baseline
        record('two-domains',dict(parents=[a,b],dispatches=done,authority_unchanged=True))


def test_independent_owner_history_without_execute_and_withdraw_after_stale_source(normal):
    f=normal;p=ready(f,label='HISTORY');d=ok(offer(f,p)[0],201);d=ok(decide(f,d,'ACCEPT'))
    r=ok(f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')))
    r=ok(act(f,r,'SUBMIT',text='SYNTHETIC independent receipt'))
    worker_once(f,OUT/'history-worker')
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    after_negative=authority_snapshot(f[1]);before=business(f[1])
    with ordinary_api(f,OUT/'history-cold') as api:
        cold=(*f[:3],api)
        owner=ok(api.get('/api/executor-receipts/'+r['step']['id'],headers=headers(f[2])))
        assert owner['current_receipt']['source_sha256']==r['current_receipt']['source_sha256']
        n=inbox(cold,'fixture-a')[0];opened=ok(note(cold,n,'OPEN','fixture-a'));marked=ok(note(cold,n,'MARK_READ','fixture-a'))
        assert opened['notice']['open_requested_at'] and marked['notice']['read_at']
        ok(act(cold,r,'ACKNOWLEDGE'),403);assert business(f[1])==before
        with f[1].connect() as c:
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
        last_authority=authority_snapshot(f[1]);withdrawn=ok(decide(cold,d,'WITHDRAW'))
        assert withdrawn['current_offer']['state']=='WITHDRAWN';ok(read(cold,d),403)
        history=ok(api.get('/api/executor-receipts/'+r['step']['id'],headers=headers(f[2])))
        assert history['step']['id']==r['step']['id'] and history['current_receipt']['source_sha256']==r['current_receipt']['source_sha256'] and not history['is_current_step']
        assert authority_snapshot(f[1])==last_authority
        record('history-withdraw',dict(before=before,owner_history=history,withdrawn=withdrawn,negative_fixture_only=True))


def test_independent_fresh_worker_after_read_generation_aba_suppresses_only_executor(normal):
    f=normal;p=ready(f,label='ABA');d=ok(offer(f,p)[0],201)
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
    baseline=authority_snapshot(f[1]);before=business(f[1]);worker_once(f,OUT/'aba-worker-first');worker_once(f,OUT/'aba-worker-second')
    with ordinary_api(f,OUT/'aba-cold') as api:
        cold=(*f[:3],api);ok(read(cold,d),403);ok(decide(cold,d,'ACCEPT'),403)
        owner=inbox(cold,'fixture-a');assert len(owner)==1 and owner[0]['historical'] and not owner[0]['actionable']
        assert inbox(cold)==[] and owner[0]['assignment_valid_until']==d['assignment_valid_until']
    with f[1].connect() as c:
        rows={r['recipient_id']:r['state'] for r in c.execute('SELECT recipient_id,state FROM dispatch_notice_outbox')}
        assert rows=={'executor-a':'SUPPRESSED','fixture-a':'DELIVERED'}
        assert c.execute('SELECT count(*) n FROM dispatch_notices').fetchone()['n']==1
    assert business(f[1])==before and authority_snapshot(f[1])==baseline
    record('worker-aba',dict(outbox=rows,first_deadline=d['assignment_valid_until'],authority_unchanged_after_negative=True))


def test_independent_catalog_xmin_aba_is_not_fresh_after_process_restart(normal):
    f=normal;p=ready(f,label='CATALOG');d=ok(offer(f,p)[0],201)
    with f[1].connect() as c:
        original=c.execute("SELECT name,xmin::text generation FROM preparation_catalog WHERE park_id='park-a'").fetchone()
        c.execute("UPDATE preparation_catalog SET name=name||' negative ABA' WHERE park_id='park-a'")
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET name=%s WHERE park_id='park-a'",(original['name'],))
        changed=c.execute("SELECT name,xmin::text generation FROM preparation_catalog WHERE park_id='park-a'").fetchone()
    assert original['name']==changed['name'] and original['generation']!=changed['generation']
    baseline=authority_snapshot(f[1]);before=business(f[1])
    with ordinary_api(f,OUT/'catalog-aba-cold') as api:
        cold=(*f[:3],api);ok(read(cold,d),403);ok(decide(cold,d,'ACCEPT'),403)
        owner=ok(read(cold,d,'fixture-a'));assert owner['assignment_valid_until']==d['assignment_valid_until'] and owner['dependency']=='DEPENDENCY_CHANGED'
        assert ok(decide(cold,d,'WITHDRAW'))['current_offer']['state']=='WITHDRAWN'
        ok(offer(cold,p,revision=2)[0],409)
    assert business(f[1])['service_receipt_steps']==before['service_receipt_steps']==0
    assert authority_snapshot(f[1])==baseline
    record('catalog-aba',dict(original=original,restored=changed,first_deadline=d['assignment_valid_until']))


def test_independent_corrupt_ordinary_proof_stays_pending_in_fresh_worker(normal):
    f=normal;p=ready(f,label='CORRUPT');d=ok(offer(f,p)[0],201)
    with f[1].connect() as c:
        row=c.execute("SELECT id,payload FROM service_dispatch_events WHERE action='OFFER'").fetchone();payload=row['payload']
        payload[cs.MARKER]['binding']['preparation_revision']=True
        c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(payload),row['id']))
    baseline=authority_snapshot(f[1]);before=business(f[1]);worker_once(f,OUT/'corrupt-worker')
    with ordinary_api(f,OUT/'corrupt-cold') as api:
        cold=(*f[:3],api);ok(read(cold,d),403);ok(read(cold,d,'fixture-a'),403);ok(decide(cold,d,'ACCEPT'),403)
        assert inbox(cold,'fixture-a')==[]
    with f[1].connect() as c:
        states=[r['state'] for r in c.execute('SELECT state FROM dispatch_notice_outbox')]
        assert states==['PENDING','PENDING'] and not c.execute('SELECT 1 FROM dispatch_notices').fetchone()
    assert business(f[1])==before and authority_snapshot(f[1])==baseline
    record('corrupt-proof',dict(outbox_states=states,corruption='bool preparation_revision',quarantined=True))


def test_independent_cold_api_real_notice_lock_crosses_persisted_first_deadline(normal,monkeypatch):
    f=normal;p=ready(f,label='LOCK')
    monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=3))
    d=ok(offer(f,p)[0],201)
    # Only the initial shorter test deadline is injected. Cold API uses the actual
    # frozen implementation and reads that persisted original deadline unchanged.
    scope=cs.from_environment(Store(f[0].dsn),{'PARKWEAVE_CASE_STEP_MODE':cs.ORDINARY_MODE})
    for _ in range(4):
        if not dn.consume(scope.store,case_step_assignments=scope):break
    with ordinary_api(f,OUT/'lock-cold') as api:
        cold=(*f[:3],api);n=inbox(cold)[0];opened=ok(note(cold,n,'OPEN'))
        assert opened['notice']['assignment_valid_until']==d['assignment_valid_until']
        with f[1].connect() as lock:
            lock.execute('SELECT * FROM dispatch_notices WHERE event_id=%s AND recipient_id=%s FOR UPDATE',(n['event_id'],'executor-a'))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(note,cold,n,'MARK_READ');observed=False
                for _ in range(60):
                    with f[1].connect() as c:
                        observed=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM dispatch_notices%' LIMIT 1").fetchone())
                    if observed:break
                    time.sleep(.01)
                assert observed,'actual cold API must wait on the owned notice row lock'
                end=datetime.fromisoformat(d['assignment_valid_until'])
                remaining=(end-datetime.now(timezone.utc)).total_seconds()
                assert remaining<2.8,'lock release must remain within original 3s lock timeout'
                if remaining>0:time.sleep(remaining+.08)
                lock.commit();ok(future.result(timeout=8),403)
        with f[1].connect() as c:
            persisted=c.execute('SELECT seen_at,read_at FROM dispatch_notices WHERE event_id=%s AND recipient_id=%s',(n['event_id'],'executor-a')).fetchone()
            assert persisted['seen_at'] is not None and persisted['read_at'] is None
        assert ok(read(cold,d,'fixture-a'))['assignment_valid_until']==d['assignment_valid_until']
        ok(decide(cold,d,'ACCEPT'),403)
        record('cold-lock-deadline',dict(actual_pg_lock_observed=observed,first_deadline=d['assignment_valid_until'],persisted=persisted,denied_status=403))
