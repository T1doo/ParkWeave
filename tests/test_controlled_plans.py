"""Fixed template on actual synthetic PG/API; no arbitrary execution or grants."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import json,os,subprocess,sys
from pathlib import Path
import psycopg,pytest
from parkweave import controlled_plans as cp
from parkweave.store import Store,Conflict
from parkweave.process_env import minimal_environment
from test_preparation import preparation_fixture,headers,command as prep_act
from test_executor_receipts import receipt_fixture,ready,act as receipt_act,create as legacy
from test_case_resources import link_fixture,group,post as link
from test_service_dispatches import offer,command as dispatch_act,REVIEWER
from test_resource_combinations import cancel


def read(f,p,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/controlled-plan',headers=headers(f[2],user))
def create(f,p,user='fixture-a',key=None,**extra):
    data={'template_sha256':cp.TEMPLATE_SHA,'expected_preparation_revision':p['revision'],'required_goals':['LOCAL_SYNTHETIC_COORDINATION_RECORDS'],**extra}
    return f[3].post('/api/preparations/'+p['preparation_id']+'/controlled-plan',headers=headers(f[2],user,key or uuid4().hex),json=data)
def check(f,p,step,key=None,user='fixture-a',row=None,**extra):
    row=row or read(f,p).json();s=next(s for s in row['steps'] if s['id']==step)
    data={'action':'CHECK_STEP','step':step,'expected_revision':row['revision'],'expected_source_sha256':s['source_sha256'],'reason':'SYNTHETIC explicit compatibility check',**extra}
    return f[3].post('/api/preparations/'+p['preparation_id']+'/controlled-plan/commands',headers=headers(f[2],user,key or uuid4().hex),json=data)
def through(f,n=4):
    p=ready(f);assert create(f,p).status_code==201;assert check(f,p,'P1').status_code==200
    g=group(f);assert link(f,p,g).status_code==201
    if n==1:return p,g,None,None
    assert check(f,p,'P2').status_code==200;r,_,_=offer(f,p);assert r.status_code==201,r.text
    d=dispatch_act(f,r.json(),'ACCEPT').json()
    if n==2:return p,g,d,None
    assert check(f,p,'P3').status_code==200
    s=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    s=receipt_act(f,s,'SUBMIT').json();s=receipt_act(f,s,'ACKNOWLEDGE').json()
    if n==3:return p,g,d,s
    assert check(f,p,'P4').status_code==200
    return p,g,d,s

def counts(f):
    with f[1].connect() as c:return [c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('controlled_plans','controlled_plan_events','case_resource_links','service_dispatch_events','service_step_receipts')]

@pytest.mark.parametrize('record,reason',[
    ('resource','EXISTING_CASE_RESOURCE_LINK'),('dispatch','EXISTING_DISPATCH_RECORD'),
    ('receipt','EXISTING_RECEIPT_RECORD')])
def test_template_readiness_matches_historical_create_rejection(link_fixture,record,reason):
    f=link_fixture;p=ready(f)
    if record=='resource':assert link(f,p,group(f)).status_code==201
    elif record=='dispatch':assert offer(f,p)[0].status_code==201
    else:assert legacy(f,p)[0].status_code==201
    before=counts(f);row=read(f,p).json()
    assert row['state']=='NOT_STARTED' and row['plan_id'] is None
    assert row['creation_blockers']==[reason] and not row['can_create']
    counterpart=read(f,p,REVIEWER).json()
    assert counterpart['creation_blockers'] is None and not counterpart['can_create']
    assert create(f,p).status_code==409 and counts(f)==before

def test_unused_case_readiness_respects_current_execute_without_creating(link_fixture):
    f=link_fixture;p=ready(f);before=counts(f);row=read(f,p).json()
    assert row['can_create'] and row['creation_blockers']==[] and counts(f)==before
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    row=read(f,p).json()
    assert not row['can_create'] and row['creation_blockers']==['CURRENT_EXECUTE_AUTHORITY_REQUIRED']
    assert create(f,p).status_code==403 and counts(f)==before

def test_real_fixed_four_step_persistence_no_original_goal_fulfillment(link_fixture):
    f=link_fixture;p,g,d,s=through(f);r=read(f,p).json();assert r['state']=='LOCAL_RECORDS_CHECKED' and r['revision']==5
    assert [s['state'] for s in r['steps']]==['CURRENT']*4 and len(r['history'])==5
    assert not r['case_goal_completed'] and not r['full_original_goal_verified'] and not r['automatic_execution'] and not r['new_grants']
    assert cp.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']))['state']==r['state']
    with f[1].connect() as c:assert c.execute('SELECT state FROM cases WHERE id=%s',(UUID(p['case_id']),)).fetchone()['state']=='NEEDS_INPUT'


def test_existing_api_cannot_bypass_order_and_replays_do_not_revalidate(link_fixture):
    f=link_fixture;p=ready(f);key=uuid4().hex;r=create(f,p,key=key);assert r.status_code==201;g=group(f);before=counts(f)
    assert link(f,p,g).status_code==409 and offer(f,p)[0].status_code==409 and legacy(f,p)[0].status_code==409
    assert counts(f)==before and check(f,p,'P2').status_code==409
    assert create(f,p,key=key).json()['event']==r.json()['event'];old=read(f,p).json();key=uuid4().hex;checked=check(f,p,'P1',key=key,row=old);assert checked.status_code==200
    assert check(f,p,'P1',key=key,row=old).json()['event']==checked.json()['event']
    assert link(f,p,g).status_code==201 and offer(f,p)[0].status_code==409
    assert check(f,p,'P2').status_code==200;r=offer(f,p)[0];assert r.status_code==201;d=dispatch_act(f,r.json(),'ACCEPT').json()
    s=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    before=counts(f);assert receipt_act(f,s,'SUBMIT').status_code==409 and counts(f)==before


@pytest.mark.parametrize('change',['material','resource_end','resource_cancel','resource_rule','assignment','reviewer_grant','owner_resource_grant','receipt_reopen'])
def test_upstream_invalidation_keeps_history_and_actual_business(link_fixture,change):
    f=link_fixture;p,g,d,s=through(f);before=counts(f)
    if change=='material':prep_act(f,{'preparation_id':p['preparation_id'],'revision':p['revision']},'REOPEN',reason='SYNTHETIC new input')
    elif change=='resource_cancel':assert cancel(f,g['id']).status_code==200
    elif change=='receipt_reopen':assert receipt_act(f,s,'REOPEN').status_code==200
    else:
        with f[1].connect() as c:
            if change=='resource_end':c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 seconds',ends_at=clock_timestamp()-interval '1 second' WHERE id=ANY(%s)",([UUID(x['id']) for x in g['members']],))
            elif change=='resource_rule':c.execute('UPDATE synthetic_resources SET revision=revision+1')
            elif change=='assignment':f[1].lock_principal(c,'executor-a',exclusive=True);c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
            elif change=='reviewer_grant':f[1].lock_principal(c,REVIEWER,exclusive=True);c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(REVIEWER,))
            else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    row=read(f,p).json();assert row['state']!='LOCAL_RECORDS_CHECKED' and any(x['state']=='NEEDS_RECHECK' for x in row['steps']);assert len(row['history'])==5 and counts(f)==before
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM service_dispatch_offers WHERE id=%s',(UUID(d['current_offer']['id']),)).fetchone()['state']=='ACCEPTED'
        if change!='resource_cancel':assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(UUID(g['id']),)).fetchone()['state']=='CONFIRMED'


def test_observed_revocation_restore_requires_explicit_recheck_not_old_replay(link_fixture):
    f=link_fixture;p,g,d,s=through(f)
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert read(f,p).json()['steps'][1]['state']=='NEEDS_RECHECK'
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    r=read(f,p).json();assert [x['state'] for x in r['steps']]==['CURRENT','NEEDS_RECHECK','NEEDS_RECHECK','NEEDS_RECHECK']
    assert check(f,p,'P4').status_code==409
    for step in ('P2','P3','P4'):assert check(f,p,step).status_code==200
    assert read(f,p).json()['state']=='LOCAL_RECORDS_CHECKED' and len(read(f,p).json()['history'])==8


@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-b','executor-c','unassigned'])
def test_tenant_or_assignment_cannot_read_create_check(link_fixture,user):
    f=link_fixture;p,g,d,s=through(f);before=counts(f);assert read(f,p,user).status_code==403 and create(f,p,user).status_code==403 and check(f,p,'P1',user=user).status_code==403;assert counts(f)==before


@pytest.mark.parametrize('user',[REVIEWER,'executor-a'])
def test_counterpart_minimal_projection_and_no_check_authority(link_fixture,user):
    f=link_fixture;p,g,d,s=through(f);r=read(f,p,user).json();assert r['source_snapshots'] is None and r['goal'] is None
    assert r['preparation_revision']==p['revision']
    assert all(x['source_sha256'] is None and x['issues'] is None and not x['can_check'] for x in r['steps'])
    assert 'SYNTHETIC explicit compatibility check' not in json.dumps(r) and g['id'] not in json.dumps(r)
    assert create(f,p,user).status_code==403 and check(f,p,'P4',user=user).status_code==403


def test_owner_read_without_execute_and_current_revocation_before_replay(link_fixture):
    f=link_fixture;p,g,d,s=through(f);row=read(f,p).json();f[1].revoke_capability('fixture-a','EXECUTE')
    r=read(f,p);assert r.status_code==200 and not any(x['can_check'] for x in r.json()['steps']);assert check(f,p,'P1',row=row).status_code==403
    f[1].revoke_capability('fixture-a','READ');assert read(f,p).status_code==403


def test_no_assignment_is_blocked_without_new_grants_and_old_flow_not_backfilled(link_fixture):
    f=link_fixture;p=ready(f)
    with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'");before=c.execute('SELECT * FROM capability_grants ORDER BY principal_id,capability').fetchall()
    assert create(f,p).json()['state']=='BLOCKED'
    with f[1].connect() as c:assert c.execute('SELECT * FROM capability_grants ORDER BY principal_id,capability').fetchall()==before
    other=ready(f);# no plan: prior manual flow still works when an assignment exists
    with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=true WHERE principal_id='executor-a'")
    assert offer(f,other)[0].status_code==201 and create(f,other).status_code==409


def test_fixed_hash_input_schema_CAS_and_concurrent_same_key(link_fixture):
    f=link_fixture;p=ready(f);assert create(f,p,template_sha256='0'*64).status_code==409
    assert create(f,p,required_goals=['REAL_FULFILLMENT']).status_code==422 and create(f,p,script='evil').status_code==422
    assert counts(f)[:2]==[0,0];key=uuid4().hex
    data=cp.Create(template_sha256=cp.TEMPLATE_SHA,expected_preparation_revision=p['revision'],required_goals=['LOCAL_SYNTHETIC_COORDINATION_RECORDS'])
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:cp.create(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,data),range(2)))
    assert rows[0]['event']==rows[1]['event'] and counts(f)[:2]==[1,1]
    row=read(f,p).json();assert check(f,p,'P1',row=row,expected_source_sha256='0'*64).status_code==409
    assert check(f,p,'P1',row=row).status_code==200 and check(f,p,'P1',row=row).status_code==409


def test_plan_event_failure_rolls_back_checkpoint_and_process_restart(link_fixture):
    f=link_fixture;p=ready(f);create(f,p);row=read(f,p).json()
    with f[1].connect() as c:c.execute('REVOKE INSERT ON controlled_plan_events FROM parkweave_app')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):check(f,p,'P1',row=row)
    assert read(f,p).json()['revision']==1 and counts(f)[:2]==[1,1]
    with f[1].connect() as c:c.execute('GRANT INSERT ON controlled_plan_events TO parkweave_app')
    step=row['steps'][0];env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH='src')
    # A separate process obtains a snapshot then CHECKs through the actual persistent module.
    source="import os;from uuid import UUID;from parkweave.store import Store;from parkweave import controlled_plans as p;s=Store(os.environ['PARKWEAVE_DSN']);p.command(s,"+repr(f[2]['fixture-a'])+",UUID("+repr(p['preparation_id'])+"),'restart-check',p.Command(action='CHECK_STEP',step='P1',expected_revision=1,expected_source_sha256="+repr(step['source_sha256'])+",reason='SYNTHETIC restart'))"
    crash_source=source.replace('p.command(s,',"p._event=lambda *a,**k:os._exit(76);p.command(s,")
    r=subprocess.run([sys.executable,'-'],input=crash_source,text=True,env=env,capture_output=True,timeout=15);assert r.returncode==76
    assert read(f,p).json()['revision']==1 and counts(f)[:2]==[1,1]
    for _ in range(2):
        r=subprocess.run([sys.executable,'-'],input=source,text=True,env=env,capture_output=True,timeout=15);assert r.returncode==0
    assert read(f,p).json()['revision']==2 and counts(f)[:2]==[1,2]


def test_concurrent_GET_and_checkpoint_no_share_upgrade_deadlock(link_fixture):
    f=link_fixture;p=ready(f);create(f,p)
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(lambda _:cp.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id'])),range(12)))
    assert all(x['revision']==1 for x in rows)
    row=read(f,p).json();step=row['steps'][0];cmd=cp.Command(action='CHECK_STEP',step='P1',expected_revision=1,expected_source_sha256=step['source_sha256'],reason='SYNTHETIC parallel')
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(cp.command,f[0],f[2]['fixture-a'],UUID(p['preparation_id']),'parallel-check',cmd);b=pool.submit(cp.read,f[0],f[2]['fixture-a'],UUID(p['preparation_id']));assert a.result(timeout=10)['revision']==2 and b.result(timeout=10)['revision'] in (1,2)


def test_rejected_write_observation_is_sticky_without_intermediate_GET(link_fixture):
    f=link_fixture;p,g,d,s=through(f,2);assert check(f,p,'P3').status_code==200
    s=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert receipt_act(f,s,'SUBMIT').status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT invalidated_from FROM controlled_plans').fetchone()['invalidated_from']==2
        c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert receipt_act(f,s,'SUBMIT').status_code==409
    assert check(f,p,'P2').status_code==200 and check(f,p,'P3').status_code==200
    assert receipt_act(f,s,'SUBMIT').status_code==200


def test_upgrade_minimal_permissions_no_legacy_backfill(link_fixture):
    f=link_fixture;p=ready(f);assert offer(f,p)[0].status_code==201
    with f[1].connect() as c:
        c.execute('DROP TABLE controlled_plan_events,controlled_plans')
        c.execute('DELETE FROM schema_version WHERE version>=18')
        grants=c.execute('SELECT * FROM capability_grants ORDER BY principal_id,capability').fetchall()
    f[1].migrate();f[1].migrate()
    with f[1].connect() as c:
        roles=Path('src/parkweave/roles.sql').read_text().replace('GRANT CONNECT ON DATABASE parkweave','GRANT CONNECT ON DATABASE '+psycopg.sql.Identifier(c.info.dbname).as_string(c),1)
        c.execute(roles)
        assert c.execute('SELECT * FROM capability_grants ORDER BY principal_id,capability').fetchall()==grants
        assert c.execute('SELECT max(version) n FROM schema_version').fetchone()['n']==28
    assert counts(f)[:2]==[0,0] and create(f,p).status_code==409
    for sql in ('DELETE FROM controlled_plans','UPDATE controlled_plans SET template_sha256=template_sha256','UPDATE controlled_plans SET id=id','DELETE FROM controlled_plan_events','UPDATE controlled_plan_events SET payload=payload','UPDATE capability_grants SET active=active','UPDATE run_assignments SET active=active'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with f[0].connect() as c:c.execute(sql)


def test_old_rejected_observation_cannot_invalidate_new_explicit_checkpoint(link_fixture):
    f=link_fixture;p,g,d,s=through(f)
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    with pytest.raises(cp.PlanBlocked) as captured:
        with f[0].connect() as c:
            parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(UUID(p['preparation_id']),)).fetchone()
            cp.gate(f[0],c,parent,3)
    error=captured.value;cp.persist_rejected_observation(f[0],error)
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    for step in ('P2','P3','P4'):assert check(f,p,step).status_code==200
    cp.persist_rejected_observation(f[0],error)
    assert read(f,p).json()['state']=='LOCAL_RECORDS_CHECKED'


def test_rejected_observation_lock_busy_is_bounded_retry_conflict(link_fixture):
    f=link_fixture;p=ready(f);create(f,p);check(f,p,'P1')
    with f[1].connect() as c:
        row=c.execute('SELECT * FROM controlled_plans').fetchone();row['invalidated_from']=1
        parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(UUID(p['preparation_id']),)).fetchone()
        error=cp.PlanBlocked(parent,row)
        from parkweave.executor_receipts import bounded
        @bounded
        def rejected(store):raise error
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(rejected,f[0])
            with pytest.raises(Conflict,match='observation busy; retry same key'):future.result(timeout=6)
    assert read(f,p).json()['revision']==2


def test_rejected_stale_CHECK_preserves_observed_invalidation_without_GET(link_fixture):
    f=link_fixture;p,g,d,s=through(f);row=read(f,p).json()
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert check(f,p,'P4',row=row,expected_revision=1).status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT invalidated_from FROM controlled_plans').fetchone()['invalidated_from']==2
        c.execute("UPDATE synthetic_resource_grants SET active=true WHERE principal_id='fixture-a' AND capability='HOLD'")
    assert read(f,p).json()['steps'][1]['state']=='NEEDS_RECHECK'


def test_allowed_gate_then_business_conflict_keeps_downstream_observation(link_fixture):
    f=link_fixture;p,g,d,s=through(f)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    # P1 is still valid, so the resource gate passes; duplicate association
    # rejects later. That rejection must still preserve its observed P3 loss.
    assert link(f,p,g,revision=1).status_code==409
    with f[1].connect() as c:
        assert c.execute('SELECT invalidated_from FROM controlled_plans').fetchone()['invalidated_from']==3
        f[1].lock_principal(c,'executor-a',exclusive=True)
        c.execute("UPDATE run_assignments SET active=true WHERE principal_id='executor-a'")
    row=read(f,p).json();assert [x['state'] for x in row['steps']]==['CURRENT','CURRENT','NEEDS_RECHECK','NEEDS_RECHECK']
    for step in ('P3','P4'):assert check(f,p,step).status_code==200
    assert read(f,p).json()['state']=='LOCAL_RECORDS_CHECKED'
