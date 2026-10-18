"""Contract-first probes; original owner/app roles in reviewer-owned fake PG only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,time
import pytest
from parkweave.preparation_access_configuration import Configuration,ExistingPreparationAccess,load
from parkweave.api import configured_app,create_app
from parkweave.store import Store,Denied,Conflict
from test_existing_preparation_access import configuration_fixture,data,OWNER,REVIEWER_ID,TABLES
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_ordinary_case_steps import ordinary
from test_case_step_assignments import prepared,ok,REVIEWER
from test_service_dispatches import offer,command as dispatch_command,read as dispatch_read


def evidence(name,value):
    path=Path(os.environ['PARKWEAVE_INDEPENDENT_ACCESS_EVIDENCE']);path.mkdir(parents=True,exist_ok=True)
    (path/(name+'.json')).write_text(json.dumps(value,sort_keys=True,indent=2,default=str)+'\n')


def snapshot(owner,tables=TABLES):
    with owner.connect() as c:
        rows={table:c.execute('SELECT to_jsonb(t) value FROM public.'+table+' t ORDER BY to_jsonb(t)::text').fetchall() for table in tables}
    encoded=json.dumps(rows,sort_keys=True,default=str).encode()
    return dict(sha256=hashlib.sha256(encoded).hexdigest(),counts={k:len(v) for k,v in rows.items()})


def test_nested_duplicates_and_reference_only_json_leave_a_true_read_only_snapshot(configuration_fixture,tmp_path,monkeypatch):
    f,manager,config,_=configuration_fixture
    original=manager._snapshot;observed={}
    def observe(c,value):
        observed.update(read_only=c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'],isolation=c.execute('SHOW transaction_isolation').fetchone()['transaction_isolation'])
        return original(c,value)
    monkeypatch.setattr(manager,'_snapshot',observe)
    before=snapshot(f[1]);preview=manager.preview(config)
    assert observed==dict(read_only='on',isolation='repeatable read')
    assert preview['read_only'] and preview['status']=='READY_TO_APPLY'
    secret='SYNTHETIC_INVALID_CONFIGURATION_VALUE'
    raw=json.dumps(data())
    cases=[raw.replace('"version": 1}', '"version": 1, "version": 1}'),
           json.dumps({**data(),'catalog':{**data()['catalog'],'token':secret}}),
           json.dumps({**data(),'dsn':secret}),json.dumps({**data(),'catalog':{**data()['catalog'],'version':True}})]
    assert cases[0]!=raw,'nested duplicate must actually be present'
    failures=[]
    for index,value in enumerate(cases):
        path=tmp_path/(str(index)+'.json');path.write_text(value)
        with pytest.raises(ValueError) as exc:load(path)
        assert secret not in str(exc.value)
        failures.append(type(exc.value).__name__)
    assert snapshot(f[1])==before
    evidence('strict-and-read-only',dict(transaction=observed,rejected_cases=failures,read_only=before))


def test_one_missing_grant_keeps_existing_xmin_then_inactive_same_key_is_not_repaired(configuration_fixture):
    f,manager,config,_=configuration_fixture
    with f[1].connect() as c:
        c.execute("INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,'park-a','org-a','PREPARE')",(OWNER,))
        original=c.execute("SELECT *,xmin::text generation FROM preparation_grants WHERE principal_id=%s",(OWNER,)).fetchone()
    protected=tuple(t for t in TABLES if t not in ('preparation_grants','authorization_audit'))
    stable=snapshot(f[1],protected);preview=manager.preview(config)
    assert sorted(x['action'] for x in preview['changes'])==['INSERT','KEEP']
    applied=manager.apply(config,preview['plan_sha256'])
    assert [x['principal_id'] for x in applied['applied']]==[REVIEWER_ID]
    with f[1].connect() as c:
        assert c.execute("SELECT *,xmin::text generation FROM preparation_grants WHERE principal_id=%s",(OWNER,)).fetchone()==original
        audits=c.execute('SELECT principal_id,category,outcome FROM authorization_audit').fetchall()
    assert len(audits)==1 and audits[0]['principal_id']==REVIEWER_ID and audits[0]['outcome']=='ALLOWED'
    assert ':REVIEW_ASSIGNED:' in audits[0]['category'] and preview['plan_sha256'] in audits[0]['category']
    assert snapshot(f[1],protected)==stable
    before=snapshot(f[1]);current=manager.preview(config)
    assert current['status']=='NO_CHANGE' and manager.apply(config,current['plan_sha256'])['status']=='NO_CHANGE'
    assert snapshot(f[1])==before
    with f[1].connect() as c:c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(REVIEWER_ID,))
    blocked_before=snapshot(f[1]);blocked=manager.preview(config)
    assert blocked['status']=='BLOCKED'
    with pytest.raises(Conflict):manager.apply(config,blocked['plan_sha256'])
    assert snapshot(f[1])==blocked_before
    evidence('partial-and-inactive',dict(applied_principal=REVIEWER_ID,original_existing_generation=original['generation'],existing_byte_and_xmin_preserved=True,inactive_not_repaired=True,audit_count=1))


def test_reason_is_a_hidden_fence_and_neither_app_nor_provider_is_owner_authority(configuration_fixture):
    f,manager,config,_=configuration_fixture
    before=snapshot(f[1]);old=manager.preview(config)
    private_reason='SYNTHETIC_INDEPENDENT_REASON_MUST_NOT_BE_ECHOED'
    changed=Configuration(**{**data(),'reason':private_reason})
    new=manager.preview(changed)
    assert old['plan_sha256']!=new['plan_sha256']
    encoded=json.dumps(new)
    assert private_reason not in encoded and all(token not in encoded for token in f[2].values())
    assert 'dsn' not in encoded.lower() and 'token_hash' not in encoded
    with pytest.raises(Conflict):manager.apply(changed,old['plan_sha256'])
    application=ExistingPreparationAccess(Store(f[0].dsn))
    assert application.preview(changed)['plan_sha256']==new['plan_sha256']
    with pytest.raises(Denied):application.apply(changed,new['plan_sha256'])
    for attribute in ('_native_run_access','_isolated_plan_approval','_ordinary_case_step_sources'):
        store=Store(f[1].dsn);setattr(store,attribute,object())
        with pytest.raises(Denied):ExistingPreparationAccess(store)
    assert snapshot(f[1])==before
    evidence('fence-and-owner',dict(reason_bound_not_echoed=True,app_preview_same_state=True,app_apply_denied=True,provider_contexts_denied=3,read_only=before))


def test_actual_capability_row_share_wait_rejects_generation_after_principal_admission(configuration_fixture):
    f,manager,config,_=configuration_fixture;old=manager.preview(config)
    before=snapshot(f[1],('preparation_grants','authorization_audit'))
    proof=dict(actual_pg_wait=False,kind='capability_row_after_principal_locks',clock_offset_used=False)
    try:
        with f[1].connect() as lock:
            # Owned negative SQL deliberately tests the later original row wait,
            # without holding the earlier principal advisory authorization lock.
            lock.execute("UPDATE capability_grants SET revision=revision+1 WHERE principal_id=%s AND capability='EXECUTE'",(OWNER,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                def invoke():
                    proof['request_start_utc']=datetime.now(timezone.utc).isoformat()
                    try:return manager.apply(config,old['plan_sha256'])
                    finally:proof['request_end_utc']=datetime.now(timezone.utc).isoformat()
                future=pool.submit(invoke)
                try:
                    for _ in range(100):
                        with f[1].connect() as c:
                            row=c.execute("SELECT clock_timestamp() now,query,wait_event FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT principal_id,capability FROM public.capability_grants%%FOR SHARE'").fetchone()
                        if row:proof.update(actual_pg_wait=True,observation=dict(row));break
                        if future.done():break
                        time.sleep(.01)
                    assert proof['actual_pg_wait'],'actual later capability FOR SHARE row wait required'
                finally:lock.commit()
                with pytest.raises(Conflict):future.result(timeout=10)
        assert snapshot(f[1],('preparation_grants','authorization_audit'))==before
        assert manager.preview(config)['plan_sha256']!=old['plan_sha256']
        proof.update(result='CONFLICT',old_sha_rejected=True,no_grant_or_audit_write=True)
    finally:evidence('actual-row-wait',proof)


def test_second_original_insert_failure_rolls_back_first_grant_and_audit(configuration_fixture,monkeypatch):
    f,manager,config,_=configuration_fixture;plan=manager.preview(config);before=snapshot(f[1])
    original=manager.store.connect;seen=[]
    class SyntheticSecondInsertFailure(RuntimeError):pass
    class ConnectionObserver:
        def __init__(self,connection):self.connection=connection
        def __getattr__(self,name):return getattr(self.connection,name)
        def execute(self,query,params=None,*args,**kwargs):
            if isinstance(query,str) and query.startswith('INSERT INTO public.preparation_grants('):
                seen.append(params[0])
                if len(seen)==2:raise SyntheticSecondInsertFailure('SYNTHETIC before second original insert')
            return self.connection.execute(query,params,*args,**kwargs)
    @contextmanager
    def observed_connection():
        with original() as connection:yield ConnectionObserver(connection)
    with monkeypatch.context() as patch:
        patch.setattr(manager.store,'connect',observed_connection)
        with pytest.raises(SyntheticSecondInsertFailure):manager.apply(config,plan['plan_sha256'])
    assert seen==[OWNER,REVIEWER_ID]
    assert snapshot(f[1])==before
    assert manager.preview(config)['plan_sha256']==plan['plan_sha256']
    evidence('second-insert-rollback',dict(original_insert_attempts=seen,no_automatic_replay=True,whole_snapshot_unchanged=before))


def test_reinserted_preparation_grant_does_not_revive_marker_in_cold_ordinary_or_default_app(ordinary):
    f,_=ordinary;p=prepared(f,'INITIALIZER_GENERATION');offered=ok(offer(f,p)[0],201)
    with f[1].connect() as c:
        original=c.execute("SELECT xmin::text generation FROM preparation_grants WHERE principal_id='fixture-a' AND capability='PREPARE'").fetchone()['generation']
        marker=c.execute("SELECT payload FROM service_dispatch_events WHERE action='OFFER'").fetchone()['payload']['case_step_assignment']
        c.execute("DELETE FROM preparation_grants WHERE principal_id='fixture-a' AND capability='PREPARE'")
    manager=ExistingPreparationAccess(Store(f[1].dsn));config=Configuration(**data('fixture-a',REVIEWER))
    plan=manager.preview(config);applied=manager.apply(config,plan['plan_sha256'])
    assert [x['capability'] for x in applied['applied']]==['PREPARE']
    with f[1].connect() as c:
        current=c.execute("SELECT xmin::text generation FROM preparation_grants WHERE principal_id='fixture-a' AND capability='PREPARE'").fetchone()['generation']
        assert current!=original
        assert c.execute("SELECT payload FROM service_dispatch_events WHERE action='OFFER'").fetchone()['payload']['case_step_assignment']==marker
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    protected=tuple(t for t in TABLES if t!='authorization_audit')+('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_receipt_events')
    before=snapshot(f[1],protected)
    with f[1].connect() as c:before_audits={row['id'] for row in c.execute('SELECT id FROM authorization_audit')}
    from fastapi.testclient import TestClient
    with TestClient(configured_app()) as api:
        cold=(*f[:3],api);ok(dispatch_command(cold,offered,'ACCEPT'),403)
        history=ok(dispatch_read(cold,offered,'fixture-a'))
        assert history['assignment_valid_until']==offered['assignment_valid_until']
    with TestClient(create_app(Store(f[0].dsn))) as api:
        cold=(*f[:3],api);ok(dispatch_command(cold,offered,'ACCEPT'),403)
    assert snapshot(f[1],protected)==before
    with f[1].connect() as c:
        added=[dict(row) for row in c.execute('SELECT id,principal_id,category,outcome FROM authorization_audit') if row['id'] not in before_audits]
    assert len(added)==2
    assert all((row['principal_id'],row['category'],row['outcome'])==('executor-a','API_AUTHORIZATION','DENIED') for row in added)
    evidence('old-marker-generation',dict(original_generation=original,reinserted_generation=current,original_deadline=offered['assignment_valid_until'],cold_ordinary_denied=True,default_denied=True,marker_unchanged=True,protected_business_snapshot_unchanged=before,expected_denial_audits=added))
