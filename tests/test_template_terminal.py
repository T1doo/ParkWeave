"""Explicit original-key terminal reconciliation on owned PG; GET stays read-only."""
import pytest
from parkweave import service_case_steps
from test_template_consumer import template_consumption,headers,products
from test_template_consumer_planning import preview,adoption,post
from test_template_partial import partial,recover,journal

def unknown(f,monkeypatch,key='terminal-original',commit=True):
    row=partial(f);v=preview(f,row).json();data={**adoption(v),'partial_adoption':True};original=service_case_steps.adopt
    def lost(*a,**kw):
        if commit:original(*a,**kw)
        raise RuntimeError('SYNTHETIC original outcome interrupted')
    monkeypatch.setattr(service_case_steps,'adopt',lost)
    assert post(f,row,'adopt',data,key).status_code==503
    monkeypatch.setattr(service_case_steps,'adopt',original)
    return row,v,data

def finish_body(proof,reason='SYNTHETIC explicitly finish exact original adoption'):
    return dict(expected_body_sha256=proof['body_sha256'],expected_original_request_key=proof['original_request_key'],expected_journal_state=proof['journal_state'],reason=reason)

def finish(f,row,key,data):
    return f['client'].post('/api/template-consumer/instances/'+row['instance_id']+'/planning-finalization',headers=headers(f,key=key),json=data)

def test_committed_unknown_only_explicit_finalize_confirms_journal(template_consumption,monkeypatch):
    f=template_consumption;row,v,data=unknown(f,monkeypatch);before=products(f['owner'],include_audit=True);saved=journal(f)
    r=recover(f,row,'terminal-original');assert r.status_code==200,r.text
    proof=r.json();assert proof['journal_state']=='UNKNOWN' and not proof['journal_terminal']
    assert journal(f)==saved
    reply=finish(f,row,'terminal-original',finish_body(proof));assert reply.status_code==200,reply.text
    assert reply.json()['journal_terminal'] and reply.json()['journal_state']=='CONFIRMED'
    assert reply.json()['journal_read_only'] is False and reply.json()['journal_command'] is True
    read=recover(f,row,'terminal-original').json();assert read['journal_read_only'] is True and read['journal_command'] is False
    assert products(f['owner'],include_audit=True)==before

def test_unobserved_cannot_finish_or_unlock_original_key(template_consumption,monkeypatch):
    f=template_consumption;row,v,data=unknown(f,monkeypatch,commit=False);proof=recover(f,row,'terminal-original').json()
    before=products(f['owner'],include_audit=True);saved=journal(f)
    assert finish(f,row,'terminal-original',finish_body(proof)).status_code==409
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before
    assert post(f,row,'adopt',data,'terminal-original').status_code==409

def advance(f,row,v):
    return f['client'].post('/api/preparations/'+row['preparation_id']+'/commands',headers=headers(f,key='terminal-source-advance'),json={'action':'ADD_EVIDENCE','expected_revision':v['current']['preparation_revision'],'slot':'need_summary','text':'SYNTHETIC current source advances permanently','source_kind':'USER_STATEMENT','source_label':'SYNTHETIC real peer source'})

def test_strict_advanced_source_closes_unknown_key_and_old_raw_send_cannot_commit(template_consumption,monkeypatch):
    from uuid import UUID
    f=template_consumption;row,v,data=unknown(f,monkeypatch,commit=False);assert advance(f,row,v).status_code==200
    p=recover(f,row,'terminal-original').json();assert p['status']=='NOT_COMMITTED_STALE'
    before=products(f['owner'],include_audit=True);r=finish(f,row,'terminal-original',finish_body(p));assert r.status_code==200,r.text
    assert r.json()['journal_terminal'] and r.json()['status']=='NOT_COMMITTED_FINAL'
    assert products(f['owner'],include_audit=True)==before
    from parkweave.store import Conflict
    with pytest.raises(Conflict):service_case_steps.adopt(f['store'],f['tokens']['template-new-enterprise-a'],UUID(row['preparation_id']),p['original_request_key'],service_case_steps.Adopt.model_validate(data),unadopted_only=True)
    saved=journal(f);assert post(f,row,'adopt',data,'terminal-original').status_code==409
    assert journal(f)==saved
    current=preview(f,row).json();assert post(f,row,'adopt',{**adoption(current),'partial_adoption':True},'fresh-reviewed-source').status_code==200

@pytest.mark.parametrize('field',['expected_body_sha256','expected_original_request_key','expected_journal_state'])
def test_finalization_wrong_proof_cannot_mutate_journal(template_consumption,monkeypatch,field):
    f=template_consumption;row,_,_=unknown(f,monkeypatch);p=recover(f,row,'terminal-original').json();data=finish_body(p)
    data[field]='0'*64 if field=='expected_body_sha256' else 'another-inner-key' if field=='expected_original_request_key' else 'ADMITTED'
    saved=journal(f);before=products(f['owner'],include_audit=True)
    assert finish(f,row,'terminal-original',data).status_code==409
    assert journal(f)==saved and products(f['owner'],include_audit=True)==before

def test_finalization_same_body_replay_different_reason_conflict_and_late_unknown_noop(template_consumption,monkeypatch):
    f=template_consumption;row,_,_=unknown(f,monkeypatch);p=recover(f,row,'terminal-original').json();data=finish_body(p)
    assert finish(f,row,'terminal-original',data).status_code==200;saved=journal(f)
    again=finish(f,row,'terminal-original',data);assert again.status_code==200 and again.json()['journal_read_only'] is False and again.json()['journal_command'] is True
    assert finish(f,row,'terminal-original',{**data,'reason':'SYNTHETIC other reason'}).status_code==409
    actor,database=f['consumer']._auth(f['tokens']['template-new-enterprise-a']);instance=f['consumer']._instance(actor,database,row['instance_id'])
    from parkweave.store import digest
    f['consumer']._unknown(instance,'CONFIRM_PLAN_'+digest('terminal-original'))
    assert journal(f)==saved

@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_finalize_after_revocation_cannot_confirm_or_close(template_consumption,monkeypatch,capability):
    f=template_consumption;row,_,_=unknown(f,monkeypatch);data=finish_body(recover(f,row,'terminal-original').json())
    with f['owner'].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',('template-new-enterprise-a',capability))
    saved=journal(f);before=products(f['owner'])
    assert finish(f,row,'terminal-original',data).status_code==403
    assert journal(f)==saved and products(f['owner'])==before

def test_actual_eight_successful_handles_ninth_adoption_and_lost_finish_cold_get(template_consumption):
    import subprocess,selectors,json
    from pathlib import Path
    from test_template_consumer import finish as worker_finish
    from template_candidate_support import ENTERPRISES,grant_snapshot
    f=template_consumption;authority=grant_snapshot(f['owner']);requests=[];summary=None;adopts=0;finalizes=0
    proc=subprocess.Popen(['node','tests/template_terminal_actual.js','template_terminal_actual_capacity',ENTERPRISES[0]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ)
    out=Path('.runtime/template-terminal-20261014');out.mkdir(parents=True,exist_ok=True)
    try:
        while True:
            assert sel.select(timeout=20),'Original terminal capacity bridge stalled'
            line=proc.stdout.readline()
            if not line:break
            msg=json.loads(line)
            if 'request' not in msg:summary=msg;break
            q=msg['request'];o=q['options'];method=o.get('method','GET');data=json.loads(o['body']) if o.get('body') else None;h=headers(f,key=o.get('headers',{}).get('Idempotency-Key'))
            before=products(f['owner'],include_audit=True);saved=journal(f)
            r=f['client'].request(method,q['path'],headers=h,json=data)
            requests.append(dict(method=method,path=q['path'],key=h.get('Idempotency-Key'),body=data,status=r.status_code))
            assert r.status_code<400,(q['path'],r.status_code,r.text)
            if q['path'].endswith('/planning-recovery'):assert journal(f)==saved and products(f['owner'],include_audit=True)==before
            if q['path'].endswith('/planning-finalization'):assert products(f['owner'],include_audit=True)==before
            if method=='POST' and q['path']=='/api/template-consumer/instances':worker_finish(f)
            if method=='POST' and q['path'].endswith('/adopt'):adopts+=1
            if method=='POST' and q['path'].endswith('/planning-finalization'):finalizes+=1
            drop=method=='POST' and (q['path'].endswith('/adopt') and adopts==1 or q['path'].endswith('/planning-finalization') and finalizes==1)
            proc.stdin.write((json.dumps(dict(status=r.status_code,body=r.json(),lost=drop))+'\n').encode());proc.stdin.flush()
        assert proc.wait(timeout=20)==0,proc.stderr.read().decode()
        assert summary and summary['checks']>=30 and summary['cases']==9 and adopts==9 and finalizes==2
        assert grant_snapshot(f['owner'])==authority
        with f['owner'].connect() as c:
            plans=c.execute('SELECT service_case_plan FROM preparations').fetchall();assert len(plans)==9 and all(p['service_case_plan']['partial_adoption'] for p in plans)
        stages=journal(f)['consumer_stages'];closed=[s for s in stages if s['name'].startswith('CONFIRM_PLAN_') and s['result'] and 'consumer_finalization' in s['result']];assert len(closed)==2
    finally:
        (out/'actual-capacity-chain.json').write_text(json.dumps(dict(summary=summary,requests=requests,adopts=adopts,finalizes=finalizes,permission_snapshot_unchanged=grant_snapshot(f['owner'])==authority),indent=2)+'\n')
        sel.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

def test_real_pg_source_wait_then_terminal_cas_beats_delayed_old_raw_send(template_consumption,monkeypatch):
    import time,json
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from parkweave import preparation
    f=template_consumption;row,v,data=unknown(f,monkeypatch,commit=False);p=recover(f,row,'terminal-original').json();entered=Event();release=Event();original=preparation.event
    def held(c,actor,parent,key,fp,action,*a,**kw):
        result=original(c,actor,parent,key,fp,action,*a,**kw)
        if action=='ADD_EVIDENCE':entered.set();assert release.wait(8),'owned source writer release deadline'
        return result
    monkeypatch.setattr(preparation,'event',held);waiting=False
    with ThreadPoolExecutor(max_workers=3) as pool:
        writer=pool.submit(advance,f,row,v);assert entered.wait(4)
        finalizer=pool.submit(finish,f,row,'terminal-original',finish_body(p))
        raw=pool.submit(f['client'].post,'/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key=p['original_request_key']),json=data)
        try:
            with f['owner'].connect() as monitor:
                until=time.monotonic()+3
                while time.monotonic()<until:
                    monitor.execute('SELECT pg_stat_clear_snapshot()')
                    waiting=monitor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM preparations%%FOR UPDATE%%') AS waiting").fetchone()['waiting']
                    if waiting:break
                    time.sleep(.01)
            assert waiting,'original recovery/delayed send did not wait for actual owned PG parent lock'
        finally:release.set()
        assert writer.result(8).status_code==200
        rejected=raw.result(8);assert rejected.status_code==409,rejected.text
        result=finalizer.result(8);assert result.status_code==200,result.text
    proof=recover(f,row,'terminal-original').json();assert proof['journal_terminal'] and proof['status']=='NOT_COMMITTED_FINAL' and proof['instance']['plan_id'] is None
    Path('.runtime/template-terminal-20261014/actual-pg-cas-race.json').write_text(json.dumps(dict(actual_pg_parent_lock_wait=waiting,writer='ADD_EVIDENCE',writer_status=200,delayed_raw_original_key_status=409,finalizer_status=200,journal_state=proof['journal_state'],plan_saved=False),indent=2)+'\n')
