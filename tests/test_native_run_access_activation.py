"""Actual owned PG / ASGI activation, effective consumers and bounded races."""
from concurrent.futures import ThreadPoolExecutor
from copy import copy,deepcopy
from datetime import datetime,timedelta,timezone
import hashlib,json,os
from pathlib import Path
from time import monotonic,sleep
from types import SimpleNamespace
from uuid import UUID,uuid4

from fastapi.testclient import TestClient
import psycopg
import pytest

from parkweave import native_run_access as native, native_run_access_activation as activation
from parkweave import dispatch_notices as notices, registered_dependencies as dependencies
from parkweave.api import create_app
from parkweave.store import Store,Denied,Conflict
from conftest import fixture as owned_fixture
from test_native_run_access import native_fixture,body,act,snapshot,APPROVER
from test_preparation import headers,preparation_fixture,command as material,filled
from test_executor_receipts import receipt_fixture,create as legacy_receipt,act as receipt_command
from test_service_dispatches import offer,command as dispatch_command,read as dispatch_read
from test_dispatch_notices import drain,inbox,act as notice_command
from test_case_resources import link_fixture
from test_f2_t07_full_chain import Chain


def path(a):return '/api/runs/'+a[1]['run_id']+'/access'


def decisions(a,seconds=300):
    f,parent,bridge,_=a
    if bridge.read(f[2]['fixture-a'],UUID(parent['run_id']))['state']=='APPROVED':
        d=body(a,'REVOKE')
        r=f[3].post(path(a)+'/commands',headers=headers(f[2],key=uuid4().hex),json=d.model_dump(mode='json'));assert r.status_code==200,r.text
    now=datetime.now(timezone.utc)
    d=body(a,'REQUEST',requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(seconds=seconds)).isoformat(),timezone='UTC'))
    r=f[3].post(path(a)+'/commands',headers=headers(f[2],key='request-'+uuid4().hex),json=d.model_dump(mode='json'));assert r.status_code==200,r.text
    d=body(a,'APPROVE')
    r=f[3].post(path(a)+'/commands',headers=headers(f[2],APPROVER,'approve-'+uuid4().hex),json=d.model_dump(mode='json'));assert r.status_code==200,r.text
    value=r.json()
    permit=activation.issue_activation_test_permit(f[1],f[1]._case_fact_fixture_receipt,bridge.test_permit,
        run_id=UUID(parent['run_id']),lease_id=UUID(value['lease_id']),approver_id=APPROVER,
        executor_id='executor-a',validity=value['request']['approved_validity'])
    bridge.activation_permit=permit
    return permit


@pytest.fixture
def activation_fixture(native_fixture,request):
    a=native_fixture
    activation.install_owned_test_activation_storage(a[0][1],a[0][1]._case_fact_fixture_receipt)
    decisions(a,request.param if hasattr(request,'param') else 300)
    yield a
    out=os.environ.get('PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR')
    if out:
        p=Path(out);p.mkdir(parents=True,exist_ok=True)
        target=p/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]+'.json')
        assert not target.exists(),'actual activation evidence cannot overwrite a prior window'
        with a[0][1].connect() as c:
            owned=c.execute('SELECT current_database() database,current_user owner,pg_postmaster_start_time() started').fetchone()
            run=c.execute('SELECT id,state,revision,success_scope,native_run_access_protocol,native_run_access_activation FROM runs WHERE id=%s',(a[1]['run_id'],)).fetchone()
            assignments=c.execute('SELECT * FROM run_assignments WHERE run_id=%s',(a[1]['run_id'],)).fetchall()
        with a[0][0].connect() as c:
            app=c.execute("SELECT current_user app_role,has_table_privilege(current_user,'run_assignments','UPDATE') can_update_assignments,has_table_privilege(current_user,'principals','UPDATE') can_update_identity").fetchone()
        target.write_text(json.dumps(dict(test_id=request.node.nodeid,scope='OWNED_SYNTHETIC_NATIVE_ACTIVATION_PG_ASGI',
            owned_postgres=owned,application=app,run=run,assignments=assignments,
            production_policy_adopted=False,browser_attempts=0,formal_AT35=False),indent=2,default=str)+'\n')


@pytest.fixture
def other_owned_fixture(pg,request):
    yield from owned_fixture.__wrapped__(pg,request)


def test_foreign_business_store_cannot_borrow_issued_owner_writer(activation_fixture,other_owned_fixture):
    a=activation_fixture;f,_,bridge,_=a;before=business(a)
    wrong=Store(other_owned_fixture[0].dsn)
    wrong._native_run_access=native.NativeRunAccess(wrong,test_permit=bridge.test_permit,
                                                   activation_permit=bridge.activation_permit)
    with TestClient(create_app(wrong)) as client:
        result=client.post(path(a)+'/activate',headers=headers(f[2],key='foreign-store'),json=activation_body(a))
    assert result.status_code==403
    assert business(a)==before


def activation_body(a,**changes):
    view=a[0][3].get(path(a),headers=headers(a[0][2])).json()
    data=dict(action='ACTIVATE',lease_id=view['lease_id'],expected_revision=view['revision'],
        expected_run_revision=view['run_revision'],expected_activation_revision=view['activation_revision'],
        expected_authority_sha256=view['authority_sha256'],activation_policy_sha256=view['activation_policy_sha256'],
        confirm_activate=True,reason='SYNTHETIC owner activates exact explicitly approved test lease')
    return {**data,**changes}


def activate(a,data=None,key=None,user='fixture-a'):
    return a[0][3].post(path(a)+'/activate',headers=headers(a[0][2],user,key or uuid4().hex),json=data or activation_body(a))


def accepted(a):
    assert activate(a).status_code==200
    r=offer(a[0],a[1])[0];assert r.status_code==201,r.text
    r=dispatch_command(a[0],r.json(),'ACCEPT');assert r.status_code==200,r.text
    return r.json()


def business(a):
    with a[0][1].connect() as c:
        return {t:c.execute('SELECT row_to_json(t) value FROM '+t+' t ORDER BY row_to_json(t)::text').fetchall()
                for t in ('runs','run_assignments','service_dispatches','service_dispatch_offers','service_dispatch_events',
                          'service_receipt_steps','service_receipt_events','service_step_receipts','dispatch_notice_outbox','dispatch_notices')}


def wait_parent(owner,run_id,expected=1):
    deadline=monotonic()+4
    while monotonic()<deadline:
        with owner.connect() as c:
            rows=c.execute("""SELECT pid,query,wait_event_type FROM pg_stat_activity
                WHERE datname=current_database() AND wait_event_type='Lock'
                AND query LIKE %s""",('%FROM preparations WHERE%',)).fetchall()
        if len(rows)>=expected:
            out=os.environ.get('PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR')
            if out:
                p=Path(out);p.mkdir(parents=True,exist_ok=True)
                (p/('lock-wait-'+uuid4().hex+'.json')).write_text(json.dumps(dict(
                    run_id=str(run_id),database=owner._case_fact_fixture_receipt.database_name,
                    observed_at_utc=datetime.now(timezone.utc).isoformat(),required_waiters=expected,
                    actual_pg_waiters=rows),indent=2,default=str)+'\n')
            return rows
        sleep(.02)
    raise AssertionError('actual owned PG parent lock waiter not observed')


def test_default_closed_forged_permit_and_cold_store_do_not_activate(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a;data=activation_body(a);before=business(a)
    real=bridge.activation_permit
    for value in (None,copy(real)):
        bridge.activation_permit=value
        assert activate(a,data).status_code==403
        assert business(a)==before
    bridge.activation_permit=real
    with TestClient(create_app(Store(f[0].dsn))) as cold:
        assert cold.post(path(a)+'/activate',headers=headers(f[2],key='closed'),json=data).status_code==403
    assert business(a)==before


def test_effective_assignment_actual_run_dispatch_accept_receipt_notices_and_dependencies(activation_fixture):
    a=activation_fixture;f,parent,bridge,before=a
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    result=activate(a,key='actual-activation');assert result.status_code==200,result.text
    receipt=result.json();assert receipt['actual_assignment_written'] and receipt['actual_run_access']
    assert not receipt['production_policy_adopted']
    view=f[3].get(path(a),headers=headers(f[2])).json();assert view['actual_run_access'] and not view['activation_pending']
    assert view['history'][-1]['projection_state']=='NON_EFFECTIVE'
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==200
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'unassigned')).status_code==403
    catalogue=f[3].get('/api/service-dispatches/catalog',params={'preparation_id':parent['preparation_id']},headers=headers(f[2],APPROVER))
    assert catalogue.status_code==200,catalogue.text
    assert catalogue.json()['executors']==[{'id':'executor-a'}]
    with f[0].connect() as c:
        p=c.execute('SELECT * FROM preparations WHERE id=%s',(parent['preparation_id'],)).fetchone()
        values=dependencies.collections(f[0],c,p);assert values['existing_access']['known'] and values['existing_access']['count']==1
    r=offer(f,parent)[0];assert r.status_code==201,r.text;dispatch=r.json()
    assert len(f[3].get('/api/service-dispatches',headers=headers(f[2],'executor-a')).json()['items'])==1
    drain(f);item=inbox(f,'executor-a').json()['items'][0]
    assert notice_command(f,'executor-a',item,'OPEN').status_code==200
    r=dispatch_command(f,dispatch,'ACCEPT');assert r.status_code==200,r.text;dispatch=r.json()
    step=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a'));assert step.status_code==200,step.text
    r=receipt_command(f,step.json(),'SUBMIT');assert r.status_code==200,r.text
    assert len(f[3].get('/api/executor-receipts',headers=headers(f[2],'executor-a')).json()['items'])==1
    after=snapshot(f[1]);assert all(before[t]==after[t] for t in before if t!='run_assignments')
    with f[0].connect() as c:
        assert not c.execute("SELECT has_table_privilege(current_user,'run_assignments','UPDATE') ok").fetchone()['ok']
        assert c.execute('SELECT max(version) n FROM schema_version').fetchone()['n']==32


def test_revoke_invalidates_every_live_consumer_and_preserves_original_receipt(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a;data=activation_body(a)
    r=activate(a,data,'activation-key');assert r.status_code==200;original=r.json()
    r=offer(f,parent)[0];assert r.status_code==201;dispatch=r.json();drain(f)
    notice=inbox(f,'executor-a').json()['items'][0]
    assert act(a,'REVOKE')['state']=='REVOKED'
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    assert dispatch_command(f,dispatch,'ACCEPT').status_code==403
    assert dispatch_read(f,dispatch,'executor-a').status_code==403
    assert f[3].get('/api/service-dispatches',headers=headers(f[2],'executor-a')).json()['items']==[]
    assert f[3].get('/api/executor-receipts',headers=headers(f[2],'executor-a')).json()['items']==[]
    assert inbox(f,'executor-a').json()['items']==[]
    assert notice_command(f,'executor-a',notice,'OPEN').status_code==403
    assert legacy_receipt(f,parent)[0].status_code==403
    with f[0].connect() as c:assert not f[0].assigned_executors(c,UUID(parent['run_id']),'park-a','org-a')
    recovered=f[3].get(path(a)+'/commands/activation-key',headers=headers(f[2])).json()
    assert recovered['receipt']==original and recovered['actual_run_access'] is False
    with TestClient(create_app(Store(f[0].dsn))) as cold:
        assert cold.get(path(a)+'/commands/activation-key',headers=headers(f[2])).json()['receipt']==original


def test_pending_old_outbox_rechecks_revoked_lease_without_fabricating_withdraw(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;assert activate(a).status_code==200
    r=offer(f,parent)[0];assert r.status_code==201
    assert act(a,'REVOKE')['state']=='REVOKED';drain(f)
    assert inbox(f,'executor-a').json()['items']==[]
    with f[1].connect() as c:
        executor=c.execute("SELECT state FROM dispatch_notice_outbox WHERE recipient_id='executor-a'").fetchone()
        assert executor['state']=='SUPPRESSED'
        assert [x['action'] for x in c.execute('SELECT action FROM service_dispatch_events ORDER BY revision').fetchall()]==['OFFER']


@pytest.mark.parametrize('user',['executor-a','unassigned','fixture-b','fixture-c',APPROVER,'prep-specialist-fixture-b'])
def test_activation_requires_current_exact_enterprise_owner(activation_fixture,user):
    a=activation_fixture;before=business(a);assert activate(a,user=user).status_code==403;assert business(a)==before


@pytest.mark.parametrize('changes',[{'confirm_activate':False},{'confirm_activate':1},{'confirm_activate':'true'},
    {'lease_id':str(uuid4())},{'expected_activation_revision':9},{'activation_policy_sha256':'f'*64},{'expected_authority_sha256':'f'*64}])
def test_strict_confirmation_and_stale_activation_bindings(activation_fixture,changes):
    a=activation_fixture;before=business(a);r=activate(a,activation_body(a,**changes));assert r.status_code in (409,422),r.text;assert business(a)==before


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_original_key_or_activation_cas(activation_fixture,same_key):
    a=activation_fixture;data=activation_body(a);keys=['one','one' if same_key else 'two']
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda k:activate(a,data,k),keys))
    if same_key:assert [r.status_code for r in responses]==[200,200] and responses[0].json()==responses[1].json()
    else:assert sorted(r.status_code for r in responses)==[200,409]
    assert len(business(a)['run_assignments'])==1
    assert len(a[2].read(a[0][2]['fixture-a'],UUID(a[1]['run_id']))['activation_history'])==1


@pytest.mark.parametrize('failure',['event','assignment'])
def test_atomic_activation_failure_rolls_back_event_and_assignment(activation_fixture,failure):
    a=activation_fixture;before=business(a)
    table='runs' if failure=='event' else 'run_assignments'
    operation='UPDATE OF native_run_access_activation' if failure=='event' else 'INSERT'
    with a[0][1].connect() as c:
        c.execute("CREATE FUNCTION activation_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'SYNTHETIC activation atomic failure'; END $$")
        c.execute('CREATE TRIGGER activation_fail BEFORE '+operation+' ON '+table+' FOR EACH ROW EXECUTE FUNCTION activation_fail()')
    with pytest.raises(psycopg.errors.RaiseException):activate(a)
    assert business(a)==before


def test_cold_rebound_live_provider_and_no_implicit_read_activation(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a,key='recover-only').status_code==200;before=business(a)
    cold=Store(f[0].dsn);cold._native_run_access=native.NativeRunAccess(cold,test_permit=bridge.test_permit,activation_permit=bridge.activation_permit)
    with TestClient(create_app(cold)) as client:
        assert client.get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==200
        recovered=client.get(path(a)+'/commands/recover-only',headers=headers(f[2])).json();assert recovered['found'] and recovered['actual_run_access']
    with TestClient(create_app(Store(f[0].dsn))) as default:
        assert default.get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
        assert default.get(path(a)+'/commands/recover-only',headers=headers(f[2])).json()['actual_run_access'] is False
    assert business(a)==before


@pytest.mark.parametrize('table,actor,capability',[('principals','fixture-a',None),('principals','executor-a',None),
    ('preparation_grants','fixture-a','PREPARE'),('capability_grants','executor-a','READ'),('capability_grants',APPROVER,'READ')])
def test_revoke_regrant_generation_cannot_revive_original_lease(activation_fixture,table,actor,capability):
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a).status_code==200
    predicate='id=%s' if table=='principals' else 'principal_id=%s AND capability=%s'
    args=(actor,) if capability is None else (actor,capability)
    for active in (False,True):
        with f[1].connect() as c:
            f[1].lock_principal(c,actor,exclusive=True);c.execute('UPDATE '+table+' SET active=%s WHERE '+predicate,(active,*args))
        assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    view=bridge.read(f[2]['fixture-a'],UUID(parent['run_id']))
    with pytest.raises(Conflict):activation.issue_activation_test_permit(f[1],f[1]._case_fact_fixture_receipt,bridge.test_permit,
        run_id=UUID(parent['run_id']),lease_id=UUID(view['lease_id']),approver_id=APPROVER,executor_id='executor-a',validity=view['request']['approved_validity'])


def test_unguarded_autocommit_and_temporary_schema_cannot_use_lease(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a).status_code==200
    for autocommit in (False,True):
        with psycopg.connect(f[0].dsn,row_factory=psycopg.rows.dict_row,autocommit=autocommit) as c:
            p=c.execute("SELECT * FROM principals WHERE id='executor-a'").fetchone()
            assert not f[0].assignment_allowed(c,p,UUID(parent['run_id']),track=False)
    with f[0].connect() as c:
        p=c.execute("SELECT * FROM principals WHERE id='executor-a'").fetchone()
        c.execute('CREATE TEMP TABLE native_shadow_probe(value integer)');c.execute('SET LOCAL search_path TO pg_temp,public')
        assert not f[0].assignment_allowed(c,p,UUID(parent['run_id']),track=False)


@pytest.mark.parametrize('mutation',['null','json_null','delete','rewrite_history'])
def test_native_provenance_and_event_history_cannot_be_downgraded(activation_fixture,mutation):
    a=activation_fixture;assert activate(a).status_code==200;before=business(a)
    with pytest.raises(psycopg.errors.RaiseException):
        with a[0][1].connect() as c:
            if mutation=='null':c.execute('UPDATE run_assignments SET native_access=NULL')
            elif mutation=='json_null':c.execute("UPDATE run_assignments SET native_access='null'::jsonb")
            elif mutation=='delete':c.execute('DELETE FROM run_assignments')
            else:c.execute("UPDATE runs SET native_run_access_activation=jsonb_set(native_run_access_activation,'{events,0,reason}','\"rewritten\"'::jsonb) WHERE id=%s",(a[1]['run_id'],))
    assert business(a)==before


@pytest.mark.parametrize('active',[True,False])
def test_existing_legacy_assignment_is_never_overwritten(activation_fixture,active):
    a=activation_fixture;f,parent,_,_=a;f[1].assign_status('executor-a',UUID(parent['run_id']),active)
    cold=Store(f[0].dsn)
    with cold.connect() as c:
        p=c.execute("SELECT * FROM principals WHERE id='executor-a'").fetchone()
        assert cold.assignment_allowed(c,p,UUID(parent['run_id'])) is active
    before=business(a);assert activate(a).status_code==403;assert business(a)==before


def test_original_key_collision_with_decision_and_changed_activation_body(activation_fixture):
    a=activation_fixture;data=activation_body(a);r=activate(a,data,key='activation');assert r.status_code==200
    assert activate(a,{**data,'reason':'different'},key='activation').status_code==409
    d=body(a,'REVOKE');r=a[0][3].post(path(a)+'/commands',headers=headers(a[0][2],key='activation'),json=d.model_dump(mode='json'));assert r.status_code==409
    assert activate(a,data,key='activation').json()['action']=='ACTIVATE'


def test_material_change_after_real_parent_lock_wait_refuses_activation(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;data=activation_body(a)
    with f[1].connect() as lock:
        lock.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(activate,a,data,'wait-source')
            observed=wait_parent(f[1],parent['run_id']);assert observed[0]['wait_event_type']=='Lock'
            lock.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(parent['preparation_id'],));lock.commit()
            assert pending.result().status_code in (403,409)
    assert not business(a)['run_assignments']


@pytest.mark.parametrize('activation_fixture',[2],indirect=True)
def test_expiry_after_real_parent_lock_wait_refuses_activation(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;data=activation_body(a)
    with f[1].connect() as lock:
        lock.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(activate,a,data,'wait-expiry');wait_parent(f[1],parent['run_id'])
            lock.execute('SELECT pg_sleep(2.1)');lock.commit()
            assert pending.result().status_code==403
    assert not business(a)['run_assignments']


@pytest.mark.parametrize('activation_fixture',[3],indirect=True)
def test_real_expiry_during_receipt_endpoint_rolls_back_all_business_writes(activation_fixture):
    from owned_connection_diagnostics import stage
    a=activation_fixture;f,_,_,_=a;d=accepted(a)
    step=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json();before=business(a)
    with f[1].connect() as c:
        c.execute('CREATE FUNCTION receipt_expire() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(3.1); RETURN NEW; END $$')
        c.execute('CREATE TRIGGER receipt_expire BEFORE INSERT ON service_receipt_events FOR EACH ROW EXECUTE FUNCTION receipt_expire()')
    with stage('EXPIRED_RECEIPT_SUBMIT_403'):
        r=receipt_command(f,step,'SUBMIT');assert r.status_code==403,r.text
    with stage('POST_403_OWNER_BUSINESS_SNAPSHOT'):
        assert business(a)==before
    with stage('POST_403_ACTUAL_ACCESS_REFUSED'):
        assert f[3].get(path(a)+'/commands/absent',headers=headers(f[2])).json()['actual_run_access'] is False


def test_active_legacy_receipt_create_and_submit_use_native_scope(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;assert activate(a).status_code==200
    r=legacy_receipt(f,parent)[0];assert r.status_code==201,r.text
    r=receipt_command(f,r.json(),'SUBMIT');assert r.status_code==200,r.text
    assert r.json()['current_receipt']['actor_id']=='executor-a'


def test_cancelled_case_preserves_lease_history_but_stops_business_writes(activation_fixture):
    from test_case_cancellation import post as cancel
    a=activation_fixture;f,parent,_,_=a;assert activate(a).status_code==200
    r=offer(f,parent)[0];assert r.status_code==201;dispatch=r.json()
    assert cancel(f,parent).status_code==200
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==200
    read=dispatch_read(f,dispatch,'executor-a');assert read.status_code==200 and read.json()['case_cancelled']
    assert dispatch_command(f,dispatch,'ACCEPT').status_code==409
    assert offer(f,parent,revision=dispatch['revision'])[0].status_code==409
    assert legacy_receipt(f,parent)[0].status_code==409
    view=f[3].get(path(a),headers=headers(f[2])).json();assert view['actual_run_access'] and not view['can_activate']
    assert activate(a).status_code==409


def test_recreated_read_permission_and_cross_run_enablement_are_denied(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a).status_code==200
    other=filled(f)
    data=activation_body(a);data['lease_id']=a[2].read(f[2]['fixture-a'],UUID(parent['run_id']))['lease_id']
    assert f[3].post('/api/runs/'+other['run_id']+'/access/activate',headers=headers(f[2],key='other-run'),json=data).status_code==403
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        old=c.execute("DELETE FROM capability_grants WHERE principal_id='executor-a' AND capability='READ' RETURNING *").fetchone()
        c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id,active,revision) VALUES(%s,%s,%s,%s,%s,%s)',
                  tuple(old[k] for k in ('principal_id','capability','park_id','org_id','active','revision')))
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403


def test_supplied_missing_marker_cannot_escape_native_provenance(activation_fixture):
    a=activation_fixture;f,parent,_,_=a;assert activate(a).status_code==200
    with f[0].connect() as c:
        p=c.execute("SELECT * FROM principals WHERE id='executor-a'").fetchone()
        assignment=c.execute('SELECT * FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchone()
        assignment.pop('native_access')
        assert not f[0].assignment_allowed(c,p,UUID(parent['run_id']),assignment=assignment)


def test_mixed_provider_and_inserted_activation_history_are_rejected(activation_fixture):
    a=activation_fixture;f,parent,bridge,_=a;assert activate(a).status_code==200
    with pytest.raises(psycopg.errors.RaiseException):
        with f[1].connect() as c:
            c.execute("""INSERT INTO runs(id,principal_id,park_id,org_id,input,fingerprint,state,
                revision,native_run_access_activation) SELECT %s,principal_id,park_id,org_id,input,
                fingerprint,state,revision,native_run_access_activation FROM runs WHERE id=%s""",
                (uuid4(),parent['run_id']))
    f[0]._isolated_run_access=object()
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    del f[0]._isolated_run_access
    f[0]._native_run_access=SimpleNamespace(assignment_allowed=lambda *args:True)
    assert f[3].get('/api/runs/'+parent['run_id'],headers=headers(f[2],'executor-a')).status_code==403
    assert f[3].get(path(a),headers=headers(f[2])).status_code==403
    f[0]._native_run_access=bridge


@pytest.mark.parametrize('first',['accept','revoke'])
def test_accept_and_revoke_real_parent_queue_have_one_ordered_winner(activation_fixture,first):
    a=activation_fixture;f,parent,_,_=a;assert activate(a).status_code==200
    r=offer(f,parent)[0];assert r.status_code==201;dispatch=r.json();revoke=body(a,'REVOKE')
    def revoke_call():return f[3].post(path(a)+'/commands',headers=headers(f[2],key='queued-revoke'),json=revoke.model_dump(mode='json'))
    calls={'accept':lambda:dispatch_command(f,dispatch,'ACCEPT'),'revoke':revoke_call}
    with f[1].connect() as lock:
        lock.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=2) as pool:
            earlier=pool.submit(calls[first]);wait_parent(f[1],parent['run_id'])
            later=pool.submit(calls['revoke' if first=='accept' else 'accept']);wait_parent(f[1],parent['run_id'],2)
            lock.commit();r1,r2=earlier.result(),later.result()
    assert r1.status_code==200,r1.text
    assert r2.status_code==(200 if first=='accept' else 403),r2.text
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==(1 if first=='accept' else 0)
    assert not f[3].get(path(a),headers=headers(f[2])).json()['actual_run_access']


def test_whole_ordinary_chain_uses_activation_then_explicit_plan_revision(link_fixture):
    f=link_fixture
    native.install_owned_test_storage(f[1],f[1]._case_fact_fixture_receipt)
    activation.install_owned_test_activation_storage(f[1],f[1]._case_fact_fixture_receipt)
    permit=native.issue_decision_test_permit(f[1],f[1]._case_fact_fixture_receipt,approver_ids={APPROVER})
    bridge=native.NativeRunAccess(f[0],test_permit=permit);f[0]._native_run_access=bridge
    u=Chain(f,f[3],'native-effective-whole-chain');p=u.prepared('native-effective',assigned=False)
    a=(f,p,bridge,snapshot(f[1]));before=u.authority()
    u.adopt(p);u.verify(p,'P1');combo,data=u.resources(p);u.verify(p,'P2')
    decisions(a);assert activate(a,key='whole-chain-activate').status_code==200
    # Existing plan source changes are adopted explicitly; neither activation
    # nor GET rewrites a plan to conceal the new access collection.
    plan=u.get(u.path(p,'/service-case-plan'));assert plan['local_revision_required'] and plan['can_adopt']
    q=plan['current_preview']
    revised=u.post(u.path(p,'/service-case-plan'),dict(expected_preparation_revision=plan['preparation_revision'],
        expected_request_revision=plan['request_revision'],expected_plan_revision=plan['revision'],
        expected_source_sha256=q['source_sha256'],required_goals=q['required_goals'],local_revision=True,
        reason='SYNTHETIC owner adopts exact native activation collection change'),status=201)
    assert revised['plan_id']==plan['plan_id'] and revised['events'][:-1]==plan['events']
    d=u.decision(u.offer(p),'ACCEPT');drain(f);u.verify(p,'P3')
    s=u.receipt_action(u.receipt(d),'SUBMIT');s=u.receipt_action(s,'ACKNOWLEDGE');u.verify(p,'P4')
    u.local(p,'REVALIDATE');u.verify(p,'P5')
    outputs=u.get(u.path(p,'/goal-results'));assert outputs['state']=='LOCAL_OUTPUTS_VERIFIED'
    u.assert_outputs(p,combo,d,s,outputs)
    u.local(p,'CLOSE_LOCAL_RECORD')
    assert f[3].get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')).status_code==200
    assert f[3].get(path(a),headers=headers(f[2])).json()['actual_run_access']
    after=u.authority();assert all(before[t]==after[t] for t in before if t!='run_assignments')
    assert len(after['run_assignments'])==1
    assert after['run_assignments'][0]['native_access']['lease_id']==json.loads(bridge.activation_permit.binding_json)['lease_id']
    out=os.environ.get('PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR')
    if out:
        pth=Path(out)/'whole-chain.json';assert not pth.exists()
        pth.write_text(json.dumps(dict(scope='OWNED_SYNTHETIC_ASGI_NATIVE_ACTIVATION_FULL_LOCAL_CHAIN',
            requests=u.trace,persisted_chain_proofs=u.proofs,goal_results=outputs,
            before_authority=before,after_authority=after,browser_attempts=0,formal_AT35=False),indent=2,default=str)+'\n')
