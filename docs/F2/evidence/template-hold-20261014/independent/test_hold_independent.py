"""Independent owned-PG evidence for the two parent HOLDs; no source edits."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
import json
from pathlib import Path
from parkweave import service_case_steps
from parkweave.store import Conflict
from test_template_consumer import template_consumption, headers
from test_template_consumer_planning import ready, preview, adoption, post
from test_template_partial import recover, journal
from test_template_terminal import unknown, finish_body, finish
from template_candidate_support import ENTERPRISES


def test_first_refusal_remains_unresolved_then_same_inner_original_can_commit(template_consumption, monkeypatch):
    f=template_consumption;row=ready(f);data=adoption(preview(f,row).json());key='ind-hold-first'
    original=service_case_steps.adopt
    def refused(*args,**kwargs):raise Conflict('SYNTHETIC independent first refusal')
    monkeypatch.setattr(service_case_steps,'adopt',refused)
    assert post(f,row,'adopt',data,key).status_code==409
    proof=recover(f,row,key).json();assert proof['journal_state']=='REJECTED_FIRST_SEND'
    assert proof['finalizable'] is False and proof['journal_terminal'] is False
    saved=journal(f)
    assert finish(f,row,key,finish_body(proof)).status_code==409
    assert journal(f)==saved
    monkeypatch.setattr(service_case_steps,'adopt',original)
    result=f['client'].post('/api/preparations/'+row['preparation_id']+'/service-case-plan',headers=headers(f,key=proof['original_request_key']),json=data)
    assert result.status_code==201,result.text
    recovered=recover(f,row,key);assert recovered.status_code==200,recovered.text
    proof=recovered.json();assert proof['status']=='COMMITTED' and not proof['journal_terminal']
    result=finish(f,row,key,finish_body(proof));assert result.status_code==200,result.text
    assert result.json()['journal_terminal'] and result.json()['journal_state']=='CONFIRMED'


def test_revoker_first_before_borrowed_authorization_keeps_journal(template_consumption, monkeypatch):
    f=template_consumption;row,_,_=unknown(f,monkeypatch,key='ind-hold-revoke-first')
    data=finish_body(recover(f,row,'ind-hold-revoke-first').json());saved=journal(f)
    reached=Event();release=Event();auth=f['consumer']._auth
    def pause_auth(token,*args,**kwargs):
        if args or kwargs:
            reached.set();assert release.wait(15)
        return auth(token,*args,**kwargs)
    monkeypatch.setattr(f['consumer'],'_auth',pause_auth)
    with ThreadPoolExecutor(max_workers=1) as pool:
        closing=pool.submit(finish,f,row,'ind-hold-revoke-first',data)
        assert reached.wait(15),'borrowed authorization must be used at final CAS'
        f['owner'].revoke_capability(ENTERPRISES[0],'EXECUTE')
        release.set();result=closing.result(15)
    assert result.status_code==403,result.text
    assert journal(f)==saved,'403 is insufficient: journal must actually remain unchanged'


def test_finalizer_first_holds_pg_authorization_through_sqlite_commit(template_consumption,monkeypatch):
    f=template_consumption;row,_,_=unknown(f,monkeypatch,key='ind-hold-close-first')
    data=finish_body(recover(f,row,'ind-hold-close-first').json())
    reached=Event();release=Event();revoking=Event();revoked=Event()
    connect=f['repository'].connect
    class Proxy:
        def __init__(self,c):self.c=c
        def execute(self,sql,*args):
            if sql.startswith('SELECT * FROM consumer_stages WHERE instance_id=? AND name=?'):
                reached.set();assert release.wait(15)
            return self.c.execute(sql,*args)
        def __getattr__(self,name):return getattr(self.c,name)
    @contextmanager
    def intercept(write=False):
        with connect(write=write) as c:yield Proxy(c) if write else c
    monkeypatch.setattr(f['repository'],'connect',intercept)
    def revoke():
        revoking.set()
        try:f['owner'].revoke_capability(ENTERPRISES[0],'EXECUTE')
        finally:revoked.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        closing=pool.submit(finish,f,row,'ind-hold-close-first',data)
        assert reached.wait(15)
        revocation=pool.submit(revoke);assert revoking.wait(5)
        waits=[];deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with f['owner'].connect() as c:
                waits=c.execute("SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT pg_advisory_xact_lock(%'").fetchall()
            if waits:break
            if revoked.wait(.02):break
        assert waits,'revocation must really wait on the owned PostgreSQL authorization lock'
        assert not revoked.is_set()
        release.set();result=closing.result(15);revocation.result(15)
    assert result.status_code in (200,403),result.text
    stage=[s for s in journal(f)['consumer_stages'] if s['name'].startswith('CONFIRM_PLAN_')][0]
    assert stage['state']=='CONFIRMED','postcommit GET 403 does not undo the proven authorized CAS'
    Path('.runtime/template-hold-20261014/independent/pg-cas.json').write_text(json.dumps(dict(
        real_owned_pg_waits=[dict(wait_event_type=w['wait_event_type'],wait_event=w['wait_event'],blocking_backend_count=len(w['blockers'])) for w in waits],
        response_status=result.status_code,journal_state=stage['state'],revocation_finished=revoked.is_set(),
        final_get_denial_is_not_rollback=True),indent=2)+'\n')
