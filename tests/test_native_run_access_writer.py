"""Actual independent writer process, API-only credentials and owned PG races."""
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import socket
from uuid import UUID,uuid4
from psycopg.types.json import Jsonb
from pydantic import ValidationError
import pytest
from fastapi.testclient import TestClient

from parkweave import native_run_access as native,native_run_access_writer as writer
from parkweave.api import create_app
from parkweave.store import Store,Denied,Conflict
from test_executor_receipts import receipt_fixture
from test_native_run_access import body as old_body,act as old_act,snapshot,APPROVER
from test_native_run_access_activation import activate,activation_body,business,wait_parent,path
from test_preparation import headers,preparation_fixture,command as material
from test_service_dispatches import offer,command as dispatch_command,read as dispatch_read
from test_executor_receipts import create as legacy_receipt,act as receipt_command
from test_dispatch_notices import drain,inbox,command as notice_command
from test_case_resources import link_fixture,group,post as resource_link
from test_resource_combinations import cancel as release_combo
from test_resource_holds import preview,body as resource_body
from test_f2_t07_full_chain import Chain
from writer_reference_support import Harness,start_api


def body(a,action,user=None,**changes):
    if action=='REQUEST':changes.setdefault('confirm_request',True)
    return old_body(a,action,user,**changes)


def act(a,action,user=None,key=None,data=None):
    return old_act(a,action,user,key,data or body(a,action,user))


@pytest.fixture
def writer_fixture(receipt_fixture,request):
    value=Harness(receipt_fixture,request)
    try:yield value
    finally:value.close()


def approve(h,seconds=120):
    now=datetime.now(timezone.utc)
    data=body(h.a,'REQUEST',requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(seconds=seconds)).isoformat(),timezone='UTC'))
    request=act(h.a,'REQUEST',key='writer-request',data=data)
    approval=act(h.a,'APPROVE',key='writer-approve')
    return request,approval


def test_actual_separate_writer_activation_and_no_api_owner_or_key(writer_fixture):
    h=writer_fixture;f=h.f
    assert h.writer_process.pid!=__import__('os').getpid()
    assert set(h.bridge.writer.__dict__)=={'store','_policy_json','_pin_json'}
    assert 'writer_dsn' not in h.bridge.writer._policy_json and 'hmac_sha256' not in h.bridge.writer._policy_json
    approve(h)
    result=activate(h.a,key='writer-activation')
    assert result.status_code==200,result.text
    value=result.json();assert value['actual_assignment_written'] and value['writer_proof']['scheme']==writer.SCHEME
    assert f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(f[2],'executor-a')).status_code==200
    after=snapshot(f[1]);assert all(h.before[t]==after[t] for t in h.before if t!='run_assignments')
    with f[0].connect() as c:
        assert not c.execute("SELECT has_table_privilege(current_user,'run_assignments','UPDATE') value").fetchone()['value']
    assert h.bridge.read(f[2]['fixture-a'],UUID(h.parent['run_id']))['production_installation_verified'] is False


def test_default_cold_store_and_untrusted_endpoints_never_activate(writer_fixture):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    before=business(h.a)
    with TestClient(create_app(Store(h.f[0].dsn))) as cold:
        assert cold.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    pin=h.pin.model_dump();pin['boot_id']=str(uuid4())
    h.f[0]._native_run_access=native.NativeRunAccess(h.f[0],writer=writer.WriterClient(h.f[0],h.bootstrap['policy'],pin))
    assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    h.f[0]._native_run_access=h.bridge
    assert business(h.a)==before


def test_one_policy_cannot_renew_by_new_request_after_revoke(writer_fixture):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    assert act(h.a,'REVOKE',key='revoke')['state']=='REVOKED'
    data=body(h.a,'REQUEST')
    with pytest.raises(Conflict):act(h.a,'REQUEST',key='implicit-renewal',data=data)
    assert h.bridge.read(h.f[2]['fixture-a'],UUID(h.parent['run_id']))['can_request'] is False


def test_current_owner_wrong_tenant_and_nonowner_cannot_use_writer(writer_fixture):
    h=writer_fixture;data=body(h.a,'REQUEST')
    for actor in ('fixture-b','executor-a','unassigned'):
        with pytest.raises(Denied):act(h.a,'REQUEST',user=actor,data=data)
    assert h.bridge.read(h.f[2]['fixture-a'],UUID(h.parent['run_id']))['revision']==0


def test_verify_channel_has_no_sign_sql_or_actor_setter(writer_fixture):
    h=writer_fixture;client=h.bridge.writer
    for op in ('SIGN','SQL','SET_POLICY'):
        with pytest.raises(Denied):writer.WriterClient.rpc(client,op,actor_id='fixture-a',sql='SELECT 1')
    assert writer.WriterClient.rpc(client,'VERIFY',receipts=[{'state':'APPROVED'}]) is False
    assert h.bridge.read(h.f[2]['fixture-a'],UUID(h.parent['run_id']))['revision']==0


@pytest.mark.parametrize('change',[
    {'capability':'EXECUTE'},{'max_access_seconds':3601},{'beneficiary_id':'fixture-a'},
    {'approver_actions':['APPROVE']},{'owner_id':'*'},{'application_role':'postgres'},
    {'database_name':'production'},{'valid_until':'2026-10-12T11:00:00+08:00'},
])
def test_external_policy_rejects_broad_implicit_or_ambiguous_scope(writer_fixture,change):
    h=writer_fixture
    with pytest.raises((ValidationError,Denied)):
        writer.WriterClient(h.f[0],{**h.bootstrap['policy'],**change},h.pin)
    assert not business(h.a)['run_assignments']


@pytest.mark.parametrize('terminal',['REJECT','CANCEL'])
def test_terminal_decision_cannot_renew_single_policy(writer_fixture,terminal):
    h=writer_fixture;act(h.a,'REQUEST');act(h.a,terminal)
    with pytest.raises(Conflict):act(h.a,'REQUEST',key='new-policy-not-issued')


def test_approval_only_shrinks_interval_and_owner_cannot_approve(writer_fixture):
    h=writer_fixture;now=datetime.now(timezone.utc)
    interval=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(seconds=120)).isoformat(),timezone='UTC')
    act(h.a,'REQUEST',data=body(h.a,'REQUEST',requested_validity=interval))
    with pytest.raises(Denied):act(h.a,'APPROVE',user='fixture-a')
    longer={**interval,'valid_until':(now+timedelta(seconds=180)).isoformat()}
    with pytest.raises(Conflict):act(h.a,'APPROVE',data=body(h.a,'APPROVE',approved_validity=longer))
    shorter={**interval,'valid_until':(now+timedelta(seconds=60)).isoformat()}
    assert act(h.a,'APPROVE',data=body(h.a,'APPROVE',approved_validity=shorter))['request']['approved_validity']==shorter


@pytest.mark.parametrize('same_key',[True,False])
def test_actual_writer_concurrent_keys_and_original_recovery(writer_fixture,same_key):
    h=writer_fixture;approve(h);data=activation_body(h.a)
    keys=['same-key','same-key' if same_key else 'other-key']
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda key:activate(h.a,data,key),keys))
    assert sorted(r.status_code for r in results)==([200,200] if same_key else [200,409])
    if same_key:assert results[0].json()==results[1].json()
    assert len(business(h.a)['run_assignments'])==1
    first=next(r.json() for r in results if r.status_code==200)
    original=h.f[3].get(path(h.a)+'/commands/'+first['request_key'],headers=headers(h.f[2])).json()
    assert original['receipt']==first and original['actual_run_access']
    assert activate(h.a,{**data,'reason':'changed'},first['request_key']).status_code==409
    with pytest.raises(Conflict):act(h.a,'REVOKE',key=first['request_key'])
    h.observe('CONCURRENT_KEYS',same_key=same_key,statuses=[r.status_code for r in results])


@pytest.mark.parametrize('failure',['event','assignment'])
def test_private_writer_failure_rolls_back_event_and_assignment(writer_fixture,failure):
    h=writer_fixture;approve(h);before=business(h.a)
    table='runs' if failure=='event' else 'run_assignments'
    operation='UPDATE OF native_run_access_activation' if failure=='event' else 'INSERT'
    with h.f[1].connect() as c:
        c.execute("CREATE FUNCTION writer_atomic_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'SYNTHETIC independent writer atomic failure'; END $$")
        c.execute('CREATE TRIGGER writer_atomic_fail BEFORE '+operation+' ON '+table+' FOR EACH ROW EXECUTE FUNCTION writer_atomic_fail()')
    result=activate(h.a,key='failed-atomic');assert result.status_code==409,result.text
    assert business(h.a)==before
    recovery=h.f[3].get(path(h.a)+'/commands/failed-atomic',headers=headers(h.f[2])).json()
    assert not recovery['found'] and not recovery['actual_assignment_written']


def test_existing_app_json_update_cannot_forge_signed_authority(writer_fixture):
    h=writer_fixture;act(h.a,'REQUEST')
    with h.f[0].connect() as c:
        stored=c.execute('SELECT native_run_access_protocol value FROM runs WHERE id=%s',(h.parent['run_id'],)).fetchone()['value']
        request=stored['request'];lease_id=str(uuid4())
        run=c.execute('SELECT * FROM runs WHERE id=%s',(h.parent['run_id'],)).fetchone()
        request.update(approver_id=APPROVER,approved_validity=request['requested_validity'],
                       approver_authority=h.bridge._authority_snapshot(c,run,APPROVER))
        fake=deepcopy(stored['events'][-1]);fake.update(revision=2,request_key='app-forged',reason='forged copied signature',
            actor_id=APPROVER,action='APPROVE',state='APPROVED',lease_id=lease_id,request=deepcopy(request))
        stored['events'].append(fake);stored.update(revision=2,state='APPROVED',lease_id=lease_id)
        stored['leases']=[dict(id=lease_id,state='NON_EFFECTIVE',request_id=request['request_id'],source=request['source'],validity=request['approved_validity'])]
        c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',(Jsonb(stored),h.parent['run_id']))
    assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    meta=h.f[3].get(path(h.a),headers=headers(h.f[2]));assert meta.status_code==200
    assert not meta.json()['writer_history_verified'] and not meta.json()['actual_run_access']
    assert not meta.json()['can_activate'] and not meta.json()['can_revoke']
    assert activate(h.a,activation_body(h.a,activation_policy_sha256=h.pin.policy_sha256)).status_code==403
    h.observe('APP_JSON_FORGERY',application_update_succeeded=True,business_read_status=403)


@pytest.mark.parametrize('change',['beneficiary_read','materials','expired'])
def test_owner_revoke_survives_stale_target_source_and_lease(writer_fixture,change):
    h=writer_fixture;approve(h,seconds=3 if change=='expired' else 120);assert activate(h.a).status_code==200
    if change=='beneficiary_read':h.f[1].revoke_capability('executor-a','READ')
    elif change=='materials':assert material(h.f,h.parent,'REOPEN',reason='SYNTHETIC changed materials').status_code==200
    else:
        with h.f[1].connect() as c:c.execute('SELECT pg_sleep(3.1)')
    assert act(h.a,'REVOKE',key='stale-revoke')['state']=='REVOKED'
    assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403


@pytest.mark.parametrize('actor,table,cap',[
    ('fixture-a','principals',None),('executor-a','principals',None),
    ('fixture-a','preparation_grants','PREPARE'),('executor-a','capability_grants','READ'),
    (APPROVER,'capability_grants','READ'),
])
def test_regrant_cannot_restore_previous_writer_lease(writer_fixture,actor,table,cap):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    predicate='id=%s' if cap is None else 'principal_id=%s AND capability=%s'
    args=(actor,) if cap is None else (actor,cap)
    for active in (False,True):
        with h.f[1].connect() as c:
            h.f[1].lock_principal(c,actor,exclusive=True)
            c.execute('UPDATE '+table+' SET active=%s WHERE '+predicate,(active,*args))
        assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    with pytest.raises((Denied,Conflict)):act(h.a,'REQUEST',key='cannot-renew-regranted')


@pytest.mark.parametrize('active',[True,False])
def test_writer_never_overwrites_legacy_assignment(writer_fixture,active):
    h=writer_fixture;approve(h);h.f[1].assign_status('executor-a',UUID(h.parent['run_id']),active)
    before=business(h.a);assert activate(h.a).status_code==403
    assert business(h.a)==before


def test_queued_commands_cannot_starve_verify_and_business_commit(writer_fixture):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200;revoke=body(h.a,'REVOKE')
    with h.f[0].connect() as holding:
        target=holding.execute("SELECT * FROM principals WHERE id='executor-a'").fetchone()
        assert h.f[0].assignment_allowed(holding,target,UUID(h.parent['run_id']))
        with ThreadPoolExecutor(max_workers=8) as pool:
            pending=[pool.submit(act,h.a,'REVOKE',key='queued-'+str(n),data=revoke) for n in range(8)]
            h.observe('EIGHT_COMMANDS_PARENT_WAIT',waiters=wait_parent(h.f[1],h.parent['run_id'],8))
            assert h.f[0].assignment_allowed(holding,target,UUID(h.parent['run_id']),track=False)
            holding.commit();results=[]
            for future in pending:
                try:results.append(future.result()['state'])
                except Conflict:results.append('CONFLICT')
    assert results.count('REVOKED')==1 and results.count('CONFLICT')==7


@pytest.mark.parametrize('first',['accept','revoke'])
def test_accept_and_writer_revoke_actual_parent_lock_order(writer_fixture,first):
    h=writer_fixture;approve(h);assert activate(h.a).status_code==200
    offered=offer(h.f,h.parent)[0];assert offered.status_code==201;dispatch=offered.json();revoke=body(h.a,'REVOKE')
    def revoke_call():return h.f[3].post(path(h.a)+'/commands',headers=headers(h.f[2],key='queued-revoke'),json=revoke.model_dump(mode='json'))
    calls={'accept':lambda:dispatch_command(h.f,dispatch,'ACCEPT'),'revoke':revoke_call}
    with h.f[1].connect() as lock:
        lock.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(h.parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=2) as pool:
            earlier=pool.submit(calls[first]);wait_parent(h.f[1],h.parent['run_id'])
            later=pool.submit(calls['revoke' if first=='accept' else 'accept']);wait_parent(h.f[1],h.parent['run_id'],2)
            lock.commit();r1,r2=earlier.result(),later.result()
    assert r1.status_code==200,r1.text
    assert r2.status_code==(200 if first=='accept' else 403),r2.text
    with h.f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==(1 if first=='accept' else 0)
    h.observe('ACCEPT_REVOKE_QUEUE',first=first,statuses=[r1.status_code,r2.status_code])


@pytest.mark.parametrize('change',['materials','expiry'])
def test_activation_checks_changes_after_actual_parent_wait(writer_fixture,change):
    h=writer_fixture;approve(h,seconds=3 if change=='expiry' else 120);data=activation_body(h.a)
    with h.f[1].connect() as lock:
        lock.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(h.parent['preparation_id'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(activate,h.a,data,'waiting-activation')
            h.observe('ACTIVATE_PARENT_WAIT',change=change,waiters=wait_parent(h.f[1],h.parent['run_id']))
            if change=='materials':lock.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(h.parent['preparation_id'],))
            else:lock.execute('SELECT pg_sleep(3.1)')
            lock.commit();assert pending.result().status_code in (403,409)
    assert not business(h.a)['run_assignments']


def test_expiry_at_receipt_commit_rolls_back_real_api_writes(writer_fixture):
    h=writer_fixture;approve(h,seconds=4);assert activate(h.a).status_code==200
    r=offer(h.f,h.parent)[0];assert r.status_code==201
    d=dispatch_command(h.f,r.json(),'ACCEPT');assert d.status_code==200
    step=h.f[3].get('/api/executor-receipts/'+d.json()['receipt_step_id'],headers=headers(h.f[2],'executor-a')).json();before=business(h.a)
    with h.f[1].connect() as c:
        c.execute('CREATE FUNCTION writer_receipt_expire() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(4.1); RETURN NEW; END $$')
        c.execute('CREATE TRIGGER writer_receipt_expire BEFORE INSERT ON service_receipt_events FOR EACH ROW EXECUTE FUNCTION writer_receipt_expire()')
    r=receipt_command(h.f,step,'SUBMIT');assert r.status_code==403,r.text
    assert business(h.a)==before


def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def test_real_api_writer_restart_needs_explicit_rebind(writer_fixture):
    h=writer_fixture;approve(h);original=activate(h.a,key='lost-response').json();before=business(h.a)
    old_pid=h.writer_process.pid;old_pin=h.pin;h.stop(h.writer_process)
    assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    assert h.f[3].get(path(h.a)+'/commands/lost-response',headers=headers(h.f[2])).json()['receipt']==original
    h.start_writer();assert h.writer_process.pid!=old_pid and h.pin.boot_id!=old_pin.boot_id
    # The stale API host pin must reject the newly created writer process.
    assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
    h.bind()
    for enabled in (False,True):
        process,client=start_api(h,free_port(),enabled=enabled)
        try:
            result=client.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a'))
            assert result.status_code==(200 if enabled else 403),result.text
            recovered=client.get(path(h.a)+'/commands/lost-response',headers=headers(h.f[2])).json()
            assert recovered['receipt']==original and recovered['actual_run_access'] is enabled
        finally:client.close();h.stop(process)
    assert business(h.a)==before


@pytest.fixture
def restart_writer_fixture(tmp_path_factory,request):
    import conftest,pgserver
    pg_gen=conftest.pg.__wrapped__(tmp_path_factory);server=next(pg_gen)
    base=conftest.fixture.__wrapped__(server,request);f=next(base)
    f=preparation_fixture.__wrapped__(f);f=receipt_fixture.__wrapped__(f)
    h=Harness(f,request);current=[server]
    def restart():
        previous=current[0];before_pid=previous.get_pid();uri=previous.get_uri()
        with f[1].connect() as c:before=c.execute('SELECT system_identifier::text system_identifier,pg_postmaster_start_time() started FROM pg_control_system()').fetchone()
        previous.cleanup_mode='stop';previous.cleanup()
        current[0]=pgserver.get_server(previous.pgdata,cleanup_mode='delete')
        assert current[0].get_uri()==uri and current[0].get_pid()!=before_pid
        with f[1].connect() as c:after=c.execute('SELECT system_identifier::text system_identifier,pg_postmaster_start_time() started FROM pg_control_system()').fetchone()
        assert before['system_identifier']==after['system_identifier'] and before['started']!=after['started']
        h.observe('OWNED_PHYSICAL_PG_STOP_START',before=before,after=after,before_pid=before_pid,after_pid=current[0].get_pid(),migrate_calls_after_restart=0,seed_calls_after_restart=0)
    try:yield h,restart
    finally:
        h.close();next(base,None);pg_gen.close();current[0].cleanup()


def test_actual_physical_pg_restart_retains_original_lease_without_self_issue(restart_writer_fixture):
    h,restart=restart_writer_fixture;approve(h);original=activate(h.a,key='pg-original').json();before=business(h.a)
    h.stop(h.writer_process);restart()
    with TestClient(create_app(Store(h.f[0].dsn))) as cold:
        assert cold.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==403
        assert cold.get(path(h.a)+'/commands/pg-original',headers=headers(h.f[2])).json()['receipt']==original
    h.start_writer();h.bind();process,client=start_api(h,free_port())
    try:
        assert client.get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==200
        recovered=client.get(path(h.a)+'/commands/pg-original',headers=headers(h.f[2])).json()
        assert recovered['receipt']==original and recovered['actual_run_access']
    finally:client.close();h.stop(process)
    assert business(h.a)==before


def test_cancelled_case_keeps_capacity_and_independent_release(link_fixture,request):
    from test_case_cancellation import post as cancel
    h=Harness(link_fixture,request)
    try:
        approve(h);assert activate(h.a).status_code==200
        g=group(h.f);assert resource_link(h.f,h.parent,g).status_code==201
        dispatched=offer(h.f,h.parent)[0];assert dispatched.status_code==201;dispatch=dispatched.json()
        assert cancel(h.f,h.parent).status_code==200;drain(h.f)
        assert h.f[3].get('/api/runs/'+h.parent['run_id'],headers=headers(h.f[2],'executor-a')).status_code==200
        assert dispatch_read(h.f,dispatch,'executor-a').json()['case_cancelled']
        assert dispatch_command(h.f,dispatch,'ACCEPT').status_code==409
        assert legacy_receipt(h.f,h.parent)[0].status_code==409
        assert inbox(h.f,'executor-a').json()['items']==[]
        assert preview(h.f,resource_body(h.f)).json()['occupied_peak']==1
        assert release_combo(h.f,g['id']).status_code==200
        assert preview(h.f,resource_body(h.f)).json()['occupied_peak']==0
        with h.f[1].connect() as c:
            assert [x['action'] for x in c.execute('SELECT action FROM service_dispatch_events ORDER BY revision').fetchall()]==['OFFER']
        h.observe('CASE_CANCELLED',capacity_before_release=1,capacity_after_release=0,withdraw_fabricated=False)
    finally:h.close()


@pytest.mark.parametrize('value',[None,False,1,'true'])
def test_writer_request_requires_strict_explicit_owner_confirmation(writer_fixture,value):
    h=writer_fixture;data=body(h.a,'REQUEST').model_dump(mode='json')
    if value is None:data.pop('confirm_request')
    else:data['confirm_request']=value
    r=h.f[3].post(path(h.a)+'/commands',headers=headers(h.f[2],key='strict-confirm'),json=data)
    assert r.status_code==(403 if value is None or value is False else 422)
    assert h.bridge.read(h.f[2]['fixture-a'],UUID(h.parent['run_id']))['revision']==0


def test_api_refuses_private_context_and_late_private_binding(writer_fixture):
    h=writer_fixture;private=Store(h.f[1].dsn)
    context=writer.WriterContext(private,h.bootstrap['policy'],bytes.fromhex(h.bootstrap['key']))
    private._native_run_access=native.NativeRunAccess(private,writer=context)
    with pytest.raises(Denied):create_app(private)
    late=Store(h.f[0].dsn);create_app(late)
    with pytest.raises(Denied):
        native.NativeRunAccess(late,writer=writer.WriterContext(late,h.bootstrap['policy'],bytes.fromhex(h.bootstrap['key'])))



def test_reference_writer_full_chain_with_explicit_plan_revision(link_fixture,request):
    f=link_fixture;u=Chain(f,f[3],'separate-writer-whole-chain');p=u.prepared('separate-writer',assigned=False)
    h=Harness(f,request,parent=p)
    try:
        before=u.authority();u.adopt(p);u.verify(p,'P1');combo,_=u.resources(p);u.verify(p,'P2')
        approve(h);assert activate(h.a).status_code==200
        plan=u.get(u.path(p,'/service-case-plan'));q=plan['current_preview']
        assert plan['local_revision_required'] and plan['can_adopt']
        u.post(u.path(p,'/service-case-plan'),dict(expected_preparation_revision=plan['preparation_revision'],
            expected_request_revision=plan['request_revision'],expected_plan_revision=plan['revision'],
            expected_source_sha256=q['source_sha256'],required_goals=q['required_goals'],local_revision=True,
            reason='SYNTHETIC exact separately written access collection adopted'),status=201)
        d=u.decision(u.offer(p),'ACCEPT');drain(f);u.verify(p,'P3')
        s=u.receipt_action(u.receipt(d),'SUBMIT');s=u.receipt_action(s,'ACKNOWLEDGE');u.verify(p,'P4')
        u.local(p,'REVALIDATE');u.verify(p,'P5');outputs=u.get(u.path(p,'/goal-results'))
        assert outputs['state']=='LOCAL_OUTPUTS_VERIFIED';u.assert_outputs(p,combo,d,s,outputs)
        u.local(p,'CLOSE_LOCAL_RECORD')
        assert f[3].get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')).status_code==200
        after=u.authority();assert all(before[t]==after[t] for t in before if t!='run_assignments')
        h.observe('FULL_CHAIN',verified_points=['P1','P2','P3','P4','P5'],local_outputs=outputs['state'],formal_AT35=False)
    finally:h.close()


@pytest.mark.parametrize('operation',['COMMAND','ACTIVATE'])
def test_foreign_unsigned_key_collision_cannot_return_a_fake_receipt(writer_fixture,operation):
    from test_preparation import filled
    from parkweave.native_run_access_activation import Activate
    h=writer_fixture;approve(h)
    data=body(h.a,'REVOKE') if operation=='COMMAND' else Activate.model_validate(activation_body(h.a))
    other=filled(h.f)
    with h.f[0].connect() as c:
        own=c.execute('SELECT native_run_access_protocol value FROM runs WHERE id=%s',(h.parent['run_id'],)).fetchone()['value']
        fake=deepcopy(own['events'][0]);fake.pop('writer_proof')
        fake.update(run_id=other['run_id'],request_key='foreign-key-poison',
            fingerprint=native._hash(dict(run_id=h.parent['run_id'],command=data.model_dump(mode='json'))))
        fake['request']['source'].update(run_id=other['run_id'],case_id=other['case_id'],preparation_id=other['preparation_id'])
        forged=dict(namespace=native.NAMESPACE,revision=1,state='REQUESTED',events=[fake],
                    request=fake['request'],lease_id=None,leases=[])
        c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',(Jsonb(forged),other['run_id']))
    before=business(h.a)
    endpoint='/commands' if operation=='COMMAND' else '/activate'
    r=h.f[3].post(path(h.a)+endpoint,headers=headers(h.f[2],key='foreign-key-poison'),json=data.model_dump(mode='json'))
    assert r.status_code==409,r.text
    assert business(h.a)==before
    assert not h.f[3].get(path(h.a)+'/commands/foreign-key-poison',headers=headers(h.f[2])).json()['found']
    h.observe('FOREIGN_UNSIGNED_KEY_COLLISION',operation=operation,status=r.status_code)


def test_actual_app_database_binding_rejects_borrowed_foreign_writer(writer_fixture,pg,request):
    import conftest
    h=writer_fixture;approve(h);base=conftest.fixture.__wrapped__(pg,request);other=next(base)
    try:
        wrong=Store(other[0].dsn)
        wrong._native_run_access=native.NativeRunAccess(wrong,writer=writer.WriterClient(wrong,h.bootstrap['policy'],h.pin))
        with TestClient(create_app(wrong)) as client:
            result=client.post(path(h.a)+'/activate',headers=headers(h.f[2],key='foreign-db'),json=activation_body(h.a))
        assert result.status_code==403 and not business(h.a)['run_assignments']
    finally:next(base,None)


def test_partial_command_frames_are_bounded_and_cannot_starve_verify(writer_fixture):
    from pathlib import Path
    from time import sleep
    h=writer_fixture;channels=[];capacity_denial=None
    try:
        for _ in range(20):
            channel=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);channel.settimeout(1)
            try:channel.connect(h.pin.command_path)
            except OSError as exc:
                capacity_denial=dict(errno=exc.errno,message=str(exc));channel.close();break
            channels.append(channel)
        sleep(.1)
        status=Path('/proc/'+str(h.writer_process.pid)+'/status').read_text()
        threads=int(next(line.split()[1] for line in status.splitlines() if line.startswith('Threads:')))
        assert threads<=11  # main + two listeners + eight command handlers
        assert h.bridge.writer.rpc('VERIFY',receipts=[]) is True
        h.observe('PARTIAL_FRAME_THREAD_BOUND',connections=len(channels),capacity_denial=capacity_denial,
                  actual_threads=threads,verify_success=True,retry_after_capacity_denial=False)
    finally:
        for channel in channels:channel.close()


def test_external_policy_expiry_closes_new_commands_and_preserves_get_history(receipt_fixture,request):
    h=Harness(receipt_fixture,request,seconds=6)
    try:
        approve(h,seconds=4);original=activate(h.a,key='bounded-policy').json()
        with h.f[1].connect() as c:c.execute('SELECT pg_sleep(6.1)')
        with pytest.raises(Denied):act(h.a,'REVOKE')
        view=h.bridge.read(h.f[2]['fixture-a'],UUID(h.parent['run_id']))
        assert not view['enabled'] and not view['actual_run_access'] and view['writer_history_verified']
        recovered=h.bridge.recover(h.f[2]['fixture-a'],UUID(h.parent['run_id']),'bounded-policy')
        assert recovered['receipt']==original and not recovered['actual_run_access']
        h.observe('EXTERNAL_POLICY_EXPIRED',new_commands_denied=True,history_retained=True,authority_renewed=False)
    finally:h.close()



