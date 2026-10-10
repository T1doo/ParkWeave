"""Independent lock proof consumers, timed final source waits and browser races."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pathlib import Path
import time
import pytest
from psycopg.types.json import Jsonb
from test_service_plan_manual_lock import (link_fixture,receipt_fixture,preparation_fixture,
    start,lock,stored,read,verified,step,command,GOALS,save,snapshot)
from test_service_plan_recovery import recover
from test_case_goal_results import complete,local_act,local_read
from test_case_goal_results_browser import goal_page,open_case,read_page,wait_held,settle
from test_preparation import headers,command as preparation_act
OUT=Path('.runtime/independent-service-plan-manual-lock-final-review/browser-final-extra')

def result(f,p):return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))

@pytest.mark.parametrize('reader',['goal','recovery'])
def test_locked_resource_deadline_expires_at_actual_last_source_wait(reader,link_fixture):
    f=link_fixture;p,g,d,s=complete(f,local=True)
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '1 minute',ends_at=clock_timestamp()+interval '2 seconds' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],))
    for a in ('P2','P3','P4'):verified(f,p,a)
    assert local_act(f,p,local_read(f,p).json(),'REVALIDATE').status_code==200;verified(f,p,'P5')
    r=lock(f,p,'P2');assert r.status_code==200;key=r.json()['command_receipt']['request_key'];before=snapshot(f)
    with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
        block.execute('SELECT preparation_id FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(p['preparation_id'],))
        pending=pool.submit(result,f,p) if reader=='goal' else pool.submit(recover,f,p,key)
        end=time.monotonic()+1;waiting=False
        while time.monotonic()<end:
            block.execute('SELECT pg_stat_clear_snapshot()');waiting=block.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM case_local_lifecycles%%') AS waiting").fetchone()['waiting']
            if waiting:break
            time.sleep(.01)
        assert waiting
        block.execute("SELECT pg_sleep(greatest(0,extract(epoch from (max(ends_at)-clock_timestamp())))+.03) FROM synthetic_resource_holds WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],));block.commit();r=pending.result(5)
    assert r.status_code==200 and snapshot(f)==before
    if reader=='goal':
        x=r.json();assert x['state']=='UNVERIFIED';row=x['results'][1]
        assert row['next_action']=='READ_ORIGINAL_STEP_AND_UNLOCK' and 'MANUAL_LOCK_CONFLICT_REQUIRES_EXPLICIT_UNLOCK' in row['issues'] and 'RESOURCE_WINDOW_ENDED' in row['issues']
        assert row['actual_output'] is None and row['historical_verification'] and not row['historical_verification']['current']
    else:
        x=r.json();assert x['event']['action']=='LOCK' and step(x['current'],'P2')['state']=='LOCK_CONFLICT'
        assert x['current']['read_only'] and x['current']['binding'] is None and x['current']['event'] is None
        assert all(s['verified_sources'] is None and s['source_sha256'] is None and s['allowed_actions']==[] for s in x['current']['steps'])

@pytest.mark.parametrize('damage',['lock-reference','snapshot','remove-verify-event','duplicate-unlock-key'])
def test_goal_consumer_rejects_damaged_original_lock_ledger(link_fixture,damage):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200;plan=stored(f,p);s=plan['steps'][0]
    if damage=='lock-reference':s['manual_lock']['event_id']=str(uuid4())
    elif damage=='snapshot':s['verified_sources']={'SYNTHETIC':'damaged snapshot'}
    elif damage=='remove-verify-event':
        plan['events'].pop(1);plan['revision']-=1;plan['events'][-1]['revision']-=1
    else:
        assert command(f,p,'P1','UNLOCK').status_code==200;plan=stored(f,p);plan['events'][-1]['request_key']=plan['events'][-2]['request_key']
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=snapshot(f);assert result(f,p).status_code==409 and snapshot(f)==before

@pytest.mark.parametrize('cap',['READ','PREPARE'])
def test_revocation_precedes_locked_goal_proof_and_no_private_output(link_fixture,cap):
    f=link_fixture;p=start(f);assert lock(f,p).status_code==200
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        table='preparation_grants' if cap=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(f);r=result(f,p);assert r.status_code==403 and snapshot(f)==before
    assert 'verified_sources' not in r.text and 'SYNTHETIC PRIVATE' not in r.text and stored(f,p)['steps'][0]['manual_lock']

@pytest.mark.parametrize('denied',[False,True])
def test_late_goal_get_cannot_restore_current_view_after_successful_lock_write(goal_page,denied):
    f,page,errors=goal_page;p=start(f);open_case(page,f,p);held=[]
    def hold(route):
        r=route.fetch();assert r.status==200;held.append((route,r))
    page.route('**/goal-results',hold);page.locator('#goal-results-read').click();wait_held(page,held)
    page.locator('#service-plan-reason').fill('SYNTHETIC independent lock while goal read in flight')
    page.locator('[data-service-action="LOCK"]').click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView.steps[0].manually_locked')
    before=snapshot(f);storage=page.evaluate('JSON.stringify({...localStorage})')
    if denied:held[0][0].fulfill(status=403,json={'error':'SYNTHETIC old context denial'})
    else:held[0][0].fulfill(response=held[0][1])
    page.wait_for_timeout(100)
    assert page.evaluate('goalResultView') is None and page.evaluate('servicePlanView.steps[0].manually_locked') and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors
    page.unroute('**/goal-results',hold);read_page(page)
    assert page.evaluate('goalResultView.state')=='LOCAL_OUTPUTS_VERIFIED' and snapshot(f)==before

def test_actual_locked_goal_source_change_cold_page_is_get_only_and_has_no_stale_output(goal_page):
    f,page,errors=goal_page;p=start(f);assert lock(f,p).status_code==200
    assert preparation_act(f,p,'REOPEN',reason='SYNTHETIC actual source revision').status_code==200
    read(f,p);before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_case(page,f,p);read_page(page)
    row=page.evaluate('goalResultView.results[0]');assert row['next_action']=='READ_ORIGINAL_STEP_AND_UNLOCK' and row['actual_output'] is None and not row['historical_verification']['current']
    assert '人工锁保护' in page.locator('#goal-results-items').inner_text() and '原历史核验保留' in page.locator('#goal-results-items').inner_text()
    assert requests and set(requests)=={'GET'} and snapshot(f)==before and not errors
    OUT.mkdir(parents=True,exist_ok=True)
    for width in (390,320):
        page.set_viewport_size({'width':width,'height':1000});page.locator('#goal-results-items').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#goal-results-panel').screenshot(path=str(OUT/('locked-goal-source-conflict-'+str(width)+'.png')))
