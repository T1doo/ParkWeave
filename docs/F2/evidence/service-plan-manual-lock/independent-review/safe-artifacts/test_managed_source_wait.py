"""Original owner reads a plan whose executor has the original bounded READ lease."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import time
from uuid import uuid4
from pathlib import Path
import json
from test_isolated_run_access import access_fixture,act as access_act
from test_executor_receipts import receipt_fixture,act as receipt_act
from test_preparation import preparation_fixture,command as prep_act,headers
from test_service_case_steps import (adopt,verified,GOALS,save)
from test_service_plan_manual_lock import lock
from test_service_plan_recovery import snapshot
from test_case_resources import group,post as link
from test_service_dispatches import offer,command as dispatch_act,REVIEWER
from test_case_lifecycle import read as local_read,act as local_act
from parkweave import resource_combinations as rc

def test_owner_goal_wait_cannot_publish_current_output_after_actual_executor_read_lease_expires(access_fixture):
    a=access_fixture;f,p,bridge,_,_=a
    bridge.clock=lambda:datetime.now(timezone.utc);rc.seed_synthetic(f[1]);now=bridge.clock()
    access_act(a,'REQUEST',requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=10)).isoformat(),timezone='UTC'));access_act(a,'APPROVE')
    r=save(f,p,goals=[GOALS[4]],text='SYNTHETIC managed executor source boundary');assert r.status_code==200;p={**p,'revision':r.json()['revision']}
    p=prep_act(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC source review').json();p=prep_act(f,p,'CONFIRM',reason='SYNTHETIC owner source confirmation').json()
    assert adopt(f,p).status_code==201;verified(f,p,'P1');g=group(f);assert link(f,p,g).status_code==201;verified(f,p,'P2')
    d=offer(f,p)[0];assert d.status_code==201;d=dispatch_act(f,d.json(),'ACCEPT').json();verified(f,p,'P3')
    s=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    s=receipt_act(f,s,'SUBMIT').json();s=receipt_act(f,s,'ACKNOWLEDGE').json();verified(f,p,'P4')
    assert local_act(f,p,local_read(f,p).json(),'REVALIDATE').status_code==200;verified(f,p,'P5');assert lock(f,p,'P3').status_code==200
    access_act(a,'REVOKE');now=bridge.clock();end=now+timedelta(seconds=3)
    access_act(a,'REQUEST',requested_validity=dict(valid_from=now.isoformat(),valid_until=end.isoformat(),timezone='UTC'));access_act(a,'APPROVE')
    def goal():return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))
    initial=goal();assert initial.status_code==200 and initial.json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    before=snapshot(f)
    with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
        block.execute('SELECT preparation_id FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(goal)
        deadline=time.monotonic()+1;waiting=False
        while time.monotonic()<deadline:
            block.execute('SELECT pg_stat_clear_snapshot()');waiting=block.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM case_local_lifecycles%%') AS waiting").fetchone()['waiting']
            if waiting:break
            time.sleep(.01)
        assert waiting
        block.execute('SELECT pg_sleep(greatest(0,extract(epoch from (%s::timestamptz-clock_timestamp())))+.03)',(end,));block.commit();r=pending.result(5)
    assert r.status_code in (200,403) and snapshot(f)==before
    if r.status_code==200:
        x=r.json();assert x['state']!='LOCAL_OUTPUTS_VERIFIED'
        assert all(row['actual_output'] is None and row['state']!='LOCAL_OUTPUT_VERIFIED' for row in x['results'] if row['adapter_id'] in ('P3','P4','P5'))
    else:assert 'actual_output' not in r.text and 'verified_sources' not in r.text
    out=Path('.runtime/independent-service-plan-manual-lock-final-review')
    (out/'managed-source-wait-observation.json').write_text(json.dumps(dict(actual_http_status=r.status_code,
        current_before_last_wait=True,last_lifecycle_source_row_actually_waited=True,actual_executor_read_lease_expired=True,
        no_current_output_after_deadline=True,business_snapshot_unchanged=True,
        owner_own_managed_deadline='NOT_APPLICABLE_ORIGINAL_CONTRACT_EXECUTOR_ONLY'),indent=2)+'\n')
