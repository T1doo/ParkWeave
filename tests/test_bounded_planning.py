"""Registered graph preview and bounded durable metadata; no execution authority."""
from copy import deepcopy
from uuid import uuid4
import pytest
from parkweave import bounded_planning as bp
from parkweave.store import Conflict,Store
from test_preparation import preparation_fixture,create as prepare,headers,add
from test_request_intents import save
from test_executor_receipts import receipt_fixture,ready
from test_case_resources import link_fixture
from test_plan_preview import digest

def read(f,p,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2],user))
def capture(f,p,x=None,key=None,user='fixture-a'):
    x=x or read(f,p,user).json()['current']
    return f[3].post('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2],user,key or uuid4().hex),json={'expected_preparation_revision':x['preparation_revision'],'expected_source_sha256':x['source_sha256']})
def setup(f,goals):
    p,_,_=prepare(f);r=save(f,p,goals=goals);assert r.status_code==200;p={**p,'revision':r.json()['revision']};return p

@pytest.mark.parametrize('goal,n',[('LOCAL_MATERIAL_PREPARATION',1),('LOCAL_CASE_RESOURCE_ASSOCIATION',2),('LOCAL_INTERNAL_ACCEPTANCE',3),('LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',4),('LOCAL_CASE_RECORD_RECHECK',5)])
def test_goals_select_closed_registered_subgraphs(goal,n):
    items,steps=bp.compile([goal]);assert len(steps)==n and items[0]['status']=='SUPPORTED_PREVIEW'
    done=set()
    for s in steps:assert set(s['depends_on'])<=done;done.add(s['id'])

@pytest.mark.parametrize('change',['cycle','unknown_dependency','unknown_adapter','wrong_version','duplicate'])
def test_registry_rejects_cycle_unknown_steps_versions_and_duplicate(change):
    r=deepcopy(bp.REGISTRY)
    if change=='cycle':r[0]['depends_on']=['P5']
    elif change=='unknown_dependency':r[0]['depends_on']=['UNSUPPORTED']
    elif change=='unknown_adapter':r[0]['adapter']='shell.exec'
    elif change=='wrong_version':r[0]['revision']=99
    else:r.append(deepcopy(r[0]))
    with pytest.raises(Conflict):bp.compile(['LOCAL_MATERIAL_PREPARATION'],r)


def test_all_required_goals_preserved_unknown_missing_and_no_get_mutation(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);before=digest(f);x=read(f,p).json()['current'];assert x['state']=='UNKNOWN' and x['required_goals']==[] and x['steps']==[] and digest(f)==before
    p=setup(f,['LOCAL_MATERIAL_PREPARATION','外部正式受理']);before=digest(f);x=read(f,p).json()['current'];assert x['state']=='PARTIAL' and len(x['steps'])==1 and x['goal_coverage'][1]['status']=='UNSUPPORTED' and x['required_goals']==['LOCAL_MATERIAL_PREPARATION','外部正式受理'] and digest(f)==before
    assert not x['executed'] and not x['execution_enabled'] and not x['new_grants'] and not x['case_goal_completed']
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source='{}'::jsonb WHERE service_id=%s",(x['steps'][0]['request_service_ref'],))
    before=digest(f);x=read(f,p).json()['current'];assert x['state']=='UNKNOWN' and x['goal_coverage'][0]['status']=='UNKNOWN' and x['goal_coverage'][1]['status']=='UNSUPPORTED' and digest(f)==before


def test_persistence_idempotency_and_business_fields_unchanged(preparation_fixture):
    f=preparation_fixture;p=setup(f,['LOCAL_CASE_RECORD_RECHECK']);key=uuid4().hex;x=read(f,p).json()['current']
    with f[1].connect() as c:before=c.execute('SELECT revision,state,review_sha256,request_intent FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();grants=c.execute('SELECT * FROM run_assignments').fetchall()
    r=capture(f,p,x,key);assert r.status_code==200,r.text;h=r.json()['history'];assert len(h)==1 and h[0]['state']=='CURRENT'
    assert capture(f,p,x,key).json()['history']==h
    assert bp.read(Store(f[0].dsn),f[2]['fixture-a'],p['preparation_id'])['history']==h
    with f[1].connect() as c:assert c.execute('SELECT revision,state,review_sha256,request_intent FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()==before;assert c.execute('SELECT * FROM run_assignments').fetchall()==grants

@pytest.mark.parametrize('change',['material','request','catalog','registry'])
def test_changes_stale_saved_preview_and_refuse_old_capture_without_history_write(preparation_fixture,change,monkeypatch):
    f=preparation_fixture;p=setup(f,['LOCAL_MATERIAL_PREPARATION']);x=read(f,p).json()['current'];assert capture(f,p,x).status_code==200
    if change=='material':add(f,p)
    elif change=='request':save(f,p,text='SYNTHETIC 改变目标',goals=['LOCAL_CASE_RECORD_RECHECK'])
    elif change=='catalog':
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"2\"}'::jsonb")
    else:
        r=deepcopy(bp.REGISTRY);r[0]['acceptance']='SYNTHETIC changed acceptance';monkeypatch.setattr(bp,'REGISTRY',r)
    before=digest(f);v=read(f,p).json();assert v['history'][0]['state']=='STALE' and digest(f)==before
    assert capture(f,p,x).status_code==409 and digest(f)==before and len(read(f,p).json()['history'])==1

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_other_actor_scope_denied_no_private_plan_or_write(preparation_fixture,user):
    f=preparation_fixture;p=setup(f,['LOCAL_MATERIAL_PREPARATION']);x=read(f,p).json()['current'];before=digest(f)
    assert read(f,p,user).status_code==403 and capture(f,p,x,user=user).status_code==403 and digest(f)==before


def test_execute_revocation_reads_but_cannot_capture_and_key_cannot_cross_case(preparation_fixture):
    f=preparation_fixture;p=setup(f,['LOCAL_MATERIAL_PREPARATION']);other=setup(f,['LOCAL_CASE_RECORD_RECHECK']);key=uuid4().hex;assert capture(f,p,key=key).status_code==200
    before=digest(f);assert capture(f,other,key=key).status_code==409 and digest(f)==before
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=digest(f);assert read(f,p).status_code==200 and capture(f,p).status_code==403 and digest(f)==before


def test_only_preview_metadata_changes_and_history_limit_is_bounded(preparation_fixture):
    f=preparation_fixture;p=setup(f,['LOCAL_MATERIAL_PREPARATION'])
    for _ in range(16):assert capture(f,p).status_code==200
    before=digest(f);assert capture(f,p).status_code==409 and digest(f)==before
    assert len(read(f,p).json()['history'])==16

def test_existing_access_change_stales_preview_without_repair(receipt_fixture):
    f=receipt_fixture;p=ready(f);x=read(f,p).json()['current'];assert capture(f,p,x).status_code==200
    with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    before=digest(f);assert read(f,p).json()['history'][0]['state']=='STALE' and capture(f,p,x).status_code==409 and digest(f)==before

def test_lost_committed_reply_replays_same_key_after_source_change(preparation_fixture):
    f=preparation_fixture;p=setup(f,['LOCAL_MATERIAL_PREPARATION']);x=read(f,p).json()['current'];key=uuid4().hex
    assert capture(f,p,x,key).status_code==200;add(f,p);before=digest(f)
    r=capture(f,p,x,key);assert r.status_code==200 and len(r.json()['history'])==1 and r.json()['history'][0]['state']=='STALE' and digest(f)==before
    assert capture(f,p,key=key).status_code==409 and digest(f)==before


def test_step_action_refs_match_existing_role_contracts():
    assert "CLOSE_LOCAL_RECORD" in bp.ACTIONS["P5"][0]["commands"]
    _,steps=bp.compile(['LOCAL_CASE_RECORD_RECHECK']);assert len(steps)==5
    assert any(a['path']=='/api/service-dispatches/{dispatch_id}/commands' and 'ACCEPT' in a['commands'] for a in bp.ACTIONS['P3'])
    assert all(a['path']=='/api/executor-receipts/{step_id}/commands' for a in bp.ACTIONS['P4'])


def test_case_lifecycle_cycle_changes_stale_preview_without_other_source_mutation(link_fixture):
    from test_case_lifecycle import built,read as lifecycle_read,act as lifecycle_act
    f=link_fixture;p,_,_,_=built(f);x=read(f,p).json()['current'];assert capture(f,p,x).status_code==200
    v=lifecycle_read(f,p).json();r=lifecycle_act(f,p,v,'REVALIDATE');assert r.status_code==200,r.text
    closed=lifecycle_act(f,p,r.json(),'CLOSE_LOCAL_RECORD');assert closed.status_code==200,closed.text
    before=digest(f);assert read(f,p).json()['history'][0]['state']=='STALE' and digest(f)==before
    current=read(f,p).json()['current'];assert capture(f,p,current).status_code==200
    opened=lifecycle_act(f,p,closed.json(),'REOPEN');assert opened.status_code==200,opened.text
    assert read(f,p).json()['history'][-1]['state']=='STALE'


def test_capture_only_changes_preview_column_across_entire_database(preparation_fixture):
    import hashlib,json
    f=preparation_fixture;p=setup(f,['LOCAL_CASE_RECORD_RECHECK'])
    def business():
        with f[1].connect() as c:
            tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='authorization_audit' ORDER BY tablename")]
            data={}
            for table in tables:
                rows=[]
                for row in c.execute('SELECT * FROM "'+table+'"'):
                    row=dict(row)
                    if table=='preparations':row.pop('planning_previews',None)
                    rows.append(json.dumps(row,sort_keys=True,default=str))
                data[table]=sorted(rows)
        return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    before=business();assert capture(f,p).status_code==200 and business()==before


@pytest.mark.parametrize('capability',['READ','PREPARE','inactive'])
def test_current_owner_authority_loss_rejects_read_and_capture(preparation_fixture,capability):
    f=preparation_fixture;p=setup(f,['LOCAL_MATERIAL_PREPARATION']);x=read(f,p).json()['current'];assert capture(f,p,x).status_code==200
    with f[1].connect() as c:
        if capability=='inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        else:
            table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
            c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(capability,))
    before=digest(f);assert read(f,p).status_code==403 and capture(f,p,x).status_code==403 and digest(f)==before
