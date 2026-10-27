"""Real owned PG waits cross original deadlines; no application clock offsets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from threading import Event
import json,time
import pytest
from parkweave import case_step_assignments as cs,case_lifecycle as life,service_case_steps as plans
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_ordinary_case_steps import ordinary
from test_ordinary_case_goal_results import ordinary_plan
from test_ordinary_case_record_recheck import prepared,closed
from test_case_lifecycle import read,act,counts
from test_service_case_steps import read as plan_read,command
from test_case_step_assignments import ok


@pytest.mark.parametrize('operation',['REVALIDATE','VERIFY_P5'])
@pytest.mark.parametrize('deadline_kind',['first_offer','resource_end'])
def test_actual_final_pg_wait_rechecks_step_and_resource_and_rolls_back(ordinary_plan,monkeypatch,tmp_path,operation,deadline_kind):
    f,_=ordinary_plan
    if deadline_kind=='first_offer':
        monkeypatch.setattr(cs._OrdinaryCaseStep,'_offer_deadline',lambda self,c:cs._now(c)+timedelta(seconds=24))
    else:
        # Set the actual requested resource window before its hold/confirmation/link.
        # Do not edit a bound source or change the resource clock after adoption.
        import test_resource_combinations as pairs
        original_body=pairs.body
        def short_window(*args,**kw):
            data=original_body(*args,**kw)
            with f[1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
            return dict(data,starts_at=(now+timedelta(seconds=4)).isoformat(),ends_at=(now+timedelta(seconds=28)).isoformat())
        monkeypatch.setattr(pairs,'body',short_window)
    p,d,r=prepared(f)
    if operation=='VERIFY_P5':closed(f,p)
    before=ok(read(f,p));plan_before=ok(plan_read(f,p));before_counts=counts(f)
    with f[1].connect() as c:
        deadline=(datetime.fromisoformat(d['assignment_valid_until']) if deadline_kind=='first_offer' else
                  c.execute('SELECT min(ends_at) t FROM synthetic_resource_holds').fetchone()['t'])
    module=life if operation=='REVALIDATE' else plans
    original=module._view;ready=Event();proof=dict(operation=operation,deadline_kind=deadline_kind,
        original_deadline=deadline.isoformat(),clock_offset_used=False,actual_pg_lock_observed=False)
    query="SELECT id FROM operations WHERE run_id=%s AND action='case.create' FOR SHARE /* ordinary_p5_final_wait */"
    def last_wait(*args,**kw):
        value=original(*args,**kw)
        c=args[0] if module is life else args[1]
        # Request starts early. Only the final already-calculated view waits until
        # near the deadline, avoiding an unobserved prelaunch timing assumption.
        remaining=c.execute('SELECT %s-clock_timestamp() t',(deadline,)).fetchone()['t'].total_seconds()
        proof['remaining_after_view']=remaining
        assert remaining>1,'original source must still be current after the full view'
        time.sleep(max(0,remaining-1));ready.set()
        c.execute(query,(p['run_id'],)).fetchone()
        return value
    monkeypatch.setattr(module,'_view',last_wait)
    response=None
    try:
        with f[1].connect() as lock:
            lock.execute("SELECT id FROM operations WHERE run_id=%s AND action='case.create' FOR UPDATE",(p['run_id'],)).fetchone()
            with ThreadPoolExecutor(max_workers=1) as pool:
                def request():
                    proof['request_start_utc']=datetime.now(timezone.utc).isoformat()
                    result=act(f,p,before,'REVALIDATE') if operation=='REVALIDATE' else command(f,p,'P5',row=plan_before)
                    proof.update(status=result.status_code,detail=result.json().get('detail'),request_end_utc=datetime.now(timezone.utc).isoformat())
                    return result
                future=pool.submit(request)
                try:
                    assert ready.wait(40),'final calculated view was not reached'
                    for _ in range(75):
                        with f[1].connect() as c:
                            proof['actual_pg_lock_observed']=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT id FROM operations%%ordinary_p5_final_wait%%'").fetchone())
                        if proof['actual_pg_lock_observed'] or future.done():break
                        time.sleep(.01)
                    assert proof['actual_pg_lock_observed'],'owned final PG row wait required'
                    with f[1].connect() as c:
                        remaining=c.execute('SELECT %s-clock_timestamp() t',(deadline,)).fetchone()['t'].total_seconds()
                    proof['remaining_at_observed_wait']=remaining
                    assert 0<remaining<1.5
                    time.sleep(remaining+.12)
                finally:
                    lock.commit()
                    response=future.result(timeout=10)
        ok(response,403)
        monkeypatch.setattr(module,'_view',original)
        with f[1].connect() as c:
            stored=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        assert stored['revision']==plan_before['revision'] and counts(f)==before_counts
        proof.update(plan_revision_unchanged=True,local_ledger_and_event_counts_unchanged=True,
                     post_expiry_current=ok(read(f,p))['verification_current'])
        assert proof['post_expiry_current'] is not True
    finally:
        (tmp_path/'final-wait-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
