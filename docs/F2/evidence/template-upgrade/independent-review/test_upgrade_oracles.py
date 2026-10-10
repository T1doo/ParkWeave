"""Independent loopback HTTP oracles; all business inputs remain synthetic."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import hashlib, json, sqlite3, threading, time
import httpx
import pytest
from conftest import pg, fixture
from psycopg.types.json import Jsonb
from parkweave.template_candidate import sha, canonical, Command
from parkweave import service_case_steps as plans
from test_template_upgrade import (upgrade_case, link_fixture, receipt_fixture, preparation_fixture,
    instance, publication, check, choose, recover, snapshot, confirmed, verified, plan_read, plan_command)
from test_template_upgrade_browser import server

OUT = Path('/workspace/ParkWeave/.runtime/independent-template-upgrade-fixed-review/oracles')

@pytest.fixture
def live(upgrade_case):
    with server(upgrade_case) as base, httpx.Client(base_url=base, timeout=15) as client:
        yield {**upgrade_case, 'client':client, 'base':base}

def evidence(name, data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')

def baseline(u):
    return (snapshot(u), [hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (u['consumer'].repository.path, u['engine'].repository.path)])

def ledger_count(u):
    with u['repository'].connect() as c:
        return c.execute('SELECT count(*) FROM upgrade_events').fetchone()[0]

def test_quota_64_concurrent_last_slot_recovery_readonly(live):
    u=live;row,_=instance(u);target=publication(u);x=check(u,row,target).json();before=baseline(u)
    first='independent-quota-0'
    for revision in range(63):
        assert choose(u,row,{**x,'revision':revision},key='independent-quota-'+str(revision)).status_code==200
    with ThreadPoolExecutor(2) as pool:
        responses=list(pool.map(lambda i:choose(u,row,{**x,'revision':63},key='last-'+str(i)),range(2)))
    assert sorted(r.status_code for r in responses)==[200,409]
    assert ledger_count(u)==64
    assert choose(u,row,{**x,'revision':64}).status_code==422
    assert choose(u,row,x,key=first).status_code==200
    journal=hashlib.sha256(u['repository'].path.read_bytes()).hexdigest()
    assert recover(u,row,first).json()['event']['revision']==1
    assert recover(u,row,'not-observed-independent').json()['status']=='NOT_OBSERVED'
    assert hashlib.sha256(u['repository'].path.read_bytes()).hexdigest()==journal
    assert baseline(u)==before
    evidence('quota',dict(events=64,concurrent_last_slot_statuses=sorted(r.status_code for r in responses),over_bound=422,original_get_readonly=True))

@pytest.mark.parametrize('damage',['different-scope','bad-check-hash','bad-previous','bad-revision'])
def test_single_event_damage_fails_closed_even_with_payload_hash_recomputed(live,damage):
    u=live;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex
    event=choose(u,row,x,key=key).json()['event'];event.pop('event_sha256');before=baseline(u)
    if damage=='different-scope':event['scope']['case_id']=str(uuid4())
    elif damage=='bad-check-hash':event['check_sha256']='0'*64
    elif damage=='bad-previous':event['previous_sha256']='0'*64
    else:event['revision']=2
    with sqlite3.connect(u['repository'].path) as c:
        c.execute('DROP TRIGGER upgrade_no_update')
        c.execute('UPDATE upgrade_events SET payload=?,hash=?',(canonical(event),sha(event)))
        c.execute(u['repository'].TRIGGERS['UPDATE'])
    assert recover(u,row,key).status_code==409
    assert choose(u,row,x,key=key).status_code==409
    assert check(u,row,target).status_code==409
    assert ledger_count(u)==1 and baseline(u)==before

@pytest.mark.parametrize('kind',['foreign-template','foreign-park'])
def test_target_same_original_scope_required_before_comparison(live,kind):
    u=live;row,_=instance(u);target=publication(u);before=baseline(u);fake=str(uuid4())
    # A fault fixture introduces only a foreign immutable record. No PG grants or identity changes.
    with u['engine'].repository.transaction() as c:
        original=c.execute('SELECT * FROM template_releases WHERE id=?',(target['release_id'],)).fetchone()
        payload=json.loads(original['payload']);scope=deepcopy(payload['scope'])
        scope['template_id' if kind=='foreign-template' else 'park_id']='synthetic-foreign-target'
        payload['scope']=scope
        c.execute('INSERT INTO template_releases VALUES(?,?,?,?,?)',(fake,canonical(scope),'PUBLISHED',canonical(payload),sha(payload)))
    before=baseline(u)
    response=check(u,row,dict(release_id=fake,release_sha256=sha(payload)))
    assert response.status_code==403 and row['case_id'] not in response.text
    assert ledger_count(u)==0 and baseline(u)==before

@pytest.mark.parametrize('fault',['wrong-instance','uppercase','wrong-stage','legacy-on-command'])
def test_legacy_key_exact_instance_and_registered_action_boundary(live,fault):
    u=live;row,_=instance(u,legacy=True);target=publication(u);before=baseline(u)
    with u['f'][1].connect() as c:
        parent=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
        plan=deepcopy(parent['service_case_plan'])
        if fault=='legacy-on-command':
            p=confirmed(u,row);verified(u['f'],p,'P1')
            plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan']
            plan['events'][-1]['request_key']='tc:'+row['instance_id']+':ADOPT_PLAN'
        else:
            key='tc:'+row['instance_id']+':ADOPT_PLAN'
            if fault=='wrong-instance':key='tc:'+str(uuid4())+':ADOPT_PLAN'
            elif fault=='uppercase':key='tc:'+row['instance_id'].upper()+':ADOPT_PLAN'
            else:key='tc:'+row['instance_id']+':CREATE_RUN'
            plan['events'][0]['request_key']=key
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    before=baseline(u)
    response=check(u,row,target)
    assert response.status_code==409 and ledger_count(u)==0 and baseline(u)==before

def test_source_wait_across_expiry_real_pg_lock_and_full_rollback(live,monkeypatch):
    u=live;row,_=instance(u);target=publication(u);x=check(u,row,target).json();before=baseline(u)
    now=[datetime(2026,10,10,tzinfo=timezone.utc)];u['engine'].clock=lambda:now[0]
    initial=threading.Event();original=u['engine']._available
    def available(*args):
        result=original(*args)
        if result['candidate_available']:initial.set()
        return result
    monkeypatch.setattr(u['engine'],'_available',available)
    observed=None
    with u['f'][1].connect() as blocker,ThreadPoolExecutor(1) as pool:
        blocker.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE',(row['case_id'],))
        future=pool.submit(choose,u,row,x)
        assert initial.wait(2)
        end=time.monotonic()+2
        while time.monotonic()<end:
            with u['f'][1].connect() as c:
                observed=c.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM cases%' AND pid<>pg_backend_pid()").fetchone()
            if observed:break
            time.sleep(.01)
        assert observed
        now[0]=datetime(2100,1,1,tzinfo=timezone.utc);blocker.commit()
        response=future.result(timeout=6)
    assert response.status_code==403 and ledger_count(u)==0 and baseline(u)==before
    evidence('expiry-wait',dict(actual_wait=observed,status=403,audit_events=0,business_unchanged=True))

def test_old_release_withdrawn_is_only_historical_and_unknown_original_read_has_no_write(live):
    u=live;row,old=instance(u);view=u['engine'].read('template-publisher',u['scope'])
    u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command(action='WITHDRAW',expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='SYNTHETIC independent original withdrawal'))
    target=publication(u);before=baseline(u);x=check(u,row,target)
    assert x.status_code==200 and x.json()['check']['original_release_id']==old['release_id']
    assert choose(u,row,x.json(),'KEEP_CURRENT',key='ind-withdraw-history').status_code==200
    assert recover(u,row,'ind-withdraw-history').status_code==200
    assert u['client'].post('/api/template-consumer/instances/'+row['instance_id']+'/resume',headers={'Authorization':'Bearer '+u['f'][2]['fixture-a'],'Idempotency-Key':uuid4().hex},json={}).status_code==403
    assert baseline(u)==before

@pytest.mark.parametrize('changed',['reason','choice'])
def test_request_body_anchor_recomputed_from_single_event(live,changed):
    u=live;row,_=instance(u);target=publication(u);x=check(u,row,target).json();key=uuid4().hex
    event=choose(u,row,x,'KEEP_CURRENT',key=key).json()['event'];event.pop('event_sha256')
    original_request_sha=event['request_sha256']
    if changed=='reason':event['reason']='SYNTHETIC corrupt altered decision reason'
    else:event['choice']='ACK_COMPATIBLE'
    with sqlite3.connect(u['repository'].path) as c:
        c.execute('DROP TRIGGER upgrade_no_update')
        c.execute('UPDATE upgrade_events SET payload=?,hash=?',(canonical(event),sha(event)))
        c.execute(u['repository'].TRIGGERS['UPDATE'])
        assert c.execute('SELECT fp FROM upgrade_events').fetchone()[0]==original_request_sha
    before=baseline(u)
    response=recover(u,row,key)
    evidence('request-anchor-'+changed,dict(damage=changed,status=response.status_code,request_fp_preserved=True,
        event_hash_recomputed=True,immutable_trigger_restored=True,business_unchanged=baseline(u)==before,
        returned_corrupt_value=response.status_code==200 and response.json()['event'][changed]==event[changed]))
    assert response.status_code==409
    assert baseline(u)==before
