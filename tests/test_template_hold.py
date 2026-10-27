"""Father HOLD regressions: first refusal is inconclusive; PG authority spans CAS."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time,json
from pathlib import Path
import pytest
from parkweave import service_case_steps
from parkweave.store import Conflict
from test_template_consumer import template_consumption,headers
from test_template_consumer_planning import preview,adoption,post
from test_template_partial import partial,recover,journal
from test_template_terminal import unknown,finish,finish_body
from template_candidate_support import ENTERPRISES

def test_first_refusal_is_not_permanent_and_same_inner_request_can_really_commit(template_consumption,monkeypatch):
    f=template_consumption;row=partial(f);data={**adoption(preview(f,row).json()),'partial_adoption':True};original=service_case_steps.adopt
    def refused(*a,**kw):raise Conflict('SYNTHETIC first definite refusal does not prove permanent noncommit')
    monkeypatch.setattr(service_case_steps,'adopt',refused);assert post(f,row,'adopt',data,'hold-first').status_code==409
    p=recover(f,row,'hold-first').json();assert p['status']=='REFUSED_FIRST_SEND'
    assert p['finalizable'] is False and p['journal_terminal'] is False
    saved=journal(f);assert finish(f,row,'hold-first',finish_body(p)).status_code==409;assert journal(f)==saved
    monkeypatch.setattr(service_case_steps,'adopt',original)
    r=f['client'].post('/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key=p['original_request_key']),json=data)
    assert r.status_code==201,r.text
    observed=recover(f,row,'hold-first');assert observed.status_code==200 and observed.json()['status']=='COMMITTED'
    assert not observed.json()['journal_terminal']
    assert finish(f,row,'hold-first',finish_body(observed.json())).status_code==200


def test_post_check_pre_cas_revocation_must_wait_for_journal_commit(template_consumption,monkeypatch):
    f=template_consumption;row,_,_=unknown(f,monkeypatch);p=recover(f,row,'terminal-original').json();before=journal(f)
    entered=Event();release=Event();original=f['repository'].connect;waiting=False;revoked_before_cas=False;response=None
    class Paused:
        def __init__(self,c):self.c=c
        def __getattr__(self,n):return getattr(self.c,n)
        def execute(self,q,*a,**kw):
            result=self.c.execute(q,*a,**kw)
            if q.startswith('SELECT * FROM consumer_stages WHERE instance_id='):
                entered.set();assert release.wait(8),'CAS pause release deadline'
            return result
    @contextmanager
    def paused(write=False):
        with original(write=write) as c:yield Paused(c) if write else c
    monkeypatch.setattr(f['repository'],'connect',paused)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            finishing=pool.submit(finish,f,row,'terminal-original',finish_body(p));assert entered.wait(4)
            revoke=pool.submit(f['owner'].revoke_capability,ENTERPRISES[0],'EXECUTE')
            try:
                with f['owner'].connect() as monitor:
                    until=time.monotonic()+2
                    while time.monotonic()<until:
                        monitor.execute('SELECT pg_stat_clear_snapshot()')
                        waiting=monitor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%pg_advisory_xact_lock%%' AND cardinality(pg_blocking_pids(pid))>0) AS waiting").fetchone()['waiting']
                        if waiting or revoke.done():break
                        time.sleep(.01)
                revoked_before_cas=revoke.done()
            finally:release.set()
            response=finishing.result(8);revoke.result(8)
        after=journal(f)
        assert waiting and not revoked_before_cas,'authority lock was released after check but before journal CAS; final GET403 cannot undo a committed journal'
        stage=next(s for s in after['consumer_stages'] if s['name'].startswith('CONFIRM_PLAN_'))
        assert stage['state']=='CONFIRMED' and after!=before
        assert response.status_code in (200,403)
    finally:
        Path('.runtime/template-hold-20261014/auth-cas-race.json').write_text(json.dumps(dict(actual_pg_authority_lock_wait=waiting,revocation_committed_before_cas=revoked_before_cas,response_status=response.status_code if response is not None else None,journal_changed=journal(f)!=before,rule='last GET403 does not imply rollback; shared authority must cover journal commit'),indent=2)+'\n')

@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_revocation_after_preliminary_proof_before_held_guard_prevents_cas(template_consumption,monkeypatch,capability):
    f=template_consumption;row,_,_=unknown(f,monkeypatch);proof=recover(f,row,'terminal-original').json();before=journal(f)
    checked=Event();release=Event();original=f['consumer']._auth
    def pause(token,connection=None):
        if connection is not None:
            checked.set();assert release.wait(8),'held authority guard release deadline'
        return original(token,connection=connection)
    monkeypatch.setattr(f['consumer'],'_auth',pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        response=pool.submit(finish,f,row,'terminal-original',finish_body(proof));assert checked.wait(4)
        try:
            with f['owner'].connect() as c:
                f['owner'].lock_principal(c,ENTERPRISES[0],exclusive=True)
                table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
                c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',(ENTERPRISES[0],capability))
        finally:release.set()
        r=response.result(8);assert r.status_code==403,r.text
    assert journal(f)==before


def test_obsolete_first_refusal_terminal_metadata_cannot_be_used_for_cleanup(template_consumption,monkeypatch):
    from parkweave.store import digest
    from parkweave.template_consumer import canonical
    f=template_consumption;row,_,_=unknown(f,monkeypatch,commit=False);p=recover(f,row,'terminal-original').json()
    request=finish_body(p);request['expected_journal_state']='REJECTED_FIRST_SEND'
    meta=dict(original_request_key=p['original_request_key'],body_sha256=p['body_sha256'],state='CLOSED_NOT_COMMITTED',proof_kind='FIRST_DEFINITE_REFUSAL',refusal_code='FIRST_PRODUCT_CONFLICT',request=request,fingerprint=digest(canonical(request)))
    with f['repository'].connect(write=True) as c:
        c.execute("UPDATE consumer_stages SET state='CLOSED_NOT_COMMITTED',result=? WHERE name LIKE 'CONFIRM_PLAN_%'",(json.dumps({'consumer_finalization':meta}),))
    saved=journal(f);assert recover(f,row,'terminal-original').status_code==409
    assert finish(f,row,'terminal-original',request).status_code==409
    assert journal(f)==saved

def test_original_template_page_first_refusal_and_obsolete_terminal_keep_handle():
    import subprocess
    result=subprocess.run(['node','tests/template_hold_guards.js'],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    observed=json.loads(result.stdout);assert observed['result']=='PASS' and observed['checks']==34
    Path('.runtime/template-hold-20261014/ui-guards.json').write_text(json.dumps(observed,indent=2)+'\n')
