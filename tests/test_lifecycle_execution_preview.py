"""Original lifecycle commands, actual PostgreSQL shadows and loopback recovery."""
from uuid import UUID,uuid4
from pathlib import Path
import json,pytest
from parkweave import lifecycle_execution_preview as p5,receipt_execution_preview as p4,case_lifecycle as lc,isolated_local_execution as local
from parkweave.api import create_app
from parkweave.store import Store,Denied,Conflict
from test_receipt_execution_preview import receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,snapshot,schema,execute as p4_execute,p1_execute,p2_execute,p3_execute
from test_preparation import headers
OUT=Path('.runtime/p5-local-case-preview/api')
@pytest.fixture
def lifecycle_fixture(receipt_preview_fixture,tmp_path):
    f,p,p1,p2,p3,p4e,a=receipt_preview_fixture
    e=p5.LifecycleExecutionPreview(f[0],(tmp_path/'lifecycle-preview').resolve(),enabled_for_synthetic_preview=True);e.attach_store(f[0])
    return f,p,p1,p2,p3,p4e,e,a

def read(f,p,key=None,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview'+('/recovery/'+key if key else ''),headers=headers(f[2],user))
def body(f,p,mode='REVALIDATE',decision='ACKNOWLEDGE'):
    r=read(f,p);assert r.status_code==200,r.text;x=r.json()
    return dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_source_sha256=x['current_source_sha256'],review_decision=decision,lifecycle_sequence=mode)
def execute(f,p,b=None,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview',headers=headers(f[2],user,key or uuid4().hex),json=b or body(f,p))

@pytest.mark.parametrize('mode',list(p5.SEQUENCES))
def test_actual_original_commands_local_close_reopen_and_previous_bytes(lifecycle_fixture,monkeypatch,mode):
    f,p,p1,p2,p3,p4e,e,a=lifecycle_fixture
    for fn in (p1_execute,p2_execute,p3_execute,p4_execute):assert fn(f,p).status_code==201
    previous=[x.path.read_bytes() for x in (p1,p2,p3,p4e)]+[a[2].repository.path.read_bytes()];before=snapshot(f);columns=schema(f[1]);calls=[];connections=[];original=lc.command
    def command(store,token,id,key,data):
        c=store.connection;raw=c._raw
        assert raw.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
        assert {r['relname'] for r in raw.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}==set(p5.TABLES)
        actor=store.auth(c,token)['id'];assert actor.startswith('preview-owner-') and not actor.startswith('preview-executor-')
        calls.append(data.action);connections.append(raw);return original(store,token,id,key,data)
    monkeypatch.setattr(lc,'command',command)
    response=execute(f,p,body(f,p,mode));assert response.status_code==201,response.text
    d=response.json()['result'];artifact=d['artifact'];final=artifact['lifecycle_final']
    assert d['state']=='SUCCEEDED' and calls==list(p5.SEQUENCES[mode]) and all(c.closed for c in connections)
    assert [v['action'] for v in artifact['lifecycle_events']]==calls
    assert len(artifact['lifecycle_ledger'])==1 and len(artifact['p2_resource_mapping'])==2
    assert d['not_previewed']==[] and d['required_goals']==['LOCAL_CASE_RECORD_RECHECK','外部正式成果'] and d['coverage_state']=='PARTIAL_PREVIEW'
    assert not d['case_goal_completed'] and d['formal_writes']==0 and not d['new_grants']
    if mode=='REVALIDATE_CLOSE_REOPEN':
        assert final['local_record_state']=='REOPENED' and final['cycle']==2 and final['case_state']=='REOPENED'
        assert final['verification_current'] is False and final['verified_snapshot_sha256'] is None and set(final['required_rechecks'])==set(lc.RECHECKS)
        assert artifact['lifecycle_attempts'][-1]['result']['verification_current'] is None
        assert artifact['lifecycle_attempts'][-2]['result']['case_state']=='WAITING_CONFIRMATION'
    else:assert final['case_state']=='WAITING_CONFIRMATION' and final['verification_current'] is True
    assert len(artifact['outbox'])==4 and all(o['state']=='PENDING' for o in artifact['outbox']) and artifact['notices']==[]
    assert snapshot(f)==before and schema(f[1])==columns
    assert [x.path.read_bytes() for x in (p1,p2,p3,p4e)]+[a[2].repository.path.read_bytes()]==previous
    assert e.path.stat().st_mode&0o777==0o600 and e.root.stat().st_mode&0o777==0o700


def test_request_changes_refuses_original_revalidation_without_ack_repair(lifecycle_fixture,monkeypatch):
    f,p,_,_,_,_,e,a=lifecycle_fixture;original=lc.command;calls=[]
    def command(*args):calls.append(args[-1].action);return original(*args)
    monkeypatch.setattr(lc,'command',command);before=snapshot(f)
    r=execute(f,p,body(f,p,'REVALIDATE_CLOSE_REOPEN','REQUEST_CHANGES'));assert r.status_code==201,r.text;d=r.json()['result'];art=d['artifact']
    assert d['state']=='FAILED' and art['error']=='LIFECYCLE_PREREQUISITE_FAILED' and art['p5_state']=='FAILED' and calls==['REVALIDATE']
    assert art['p4_state']=='CHANGES_REQUESTED' and not art['local_current_at_execution'] and not art['lifecycle_events'] and not art['lifecycle_ledger']
    assert art['lifecycle_final']['local_record_state']=='NOT_STARTED' and d['not_previewed']==['P5'] and snapshot(f)==before


def test_true_concurrent_same_key_cas_explicit_sequence_and_cold_http_get(lifecycle_fixture):
    from concurrent.futures import ThreadPoolExecutor
    from test_new_enterprise_local_chain import actual_http
    f,p,_,_,_,_,e,a=lifecycle_fixture;b=body(f,p,'REVALIDATE_CLOSE_REOPEN');key=uuid4().hex;before=snapshot(f)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:e.execute(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,p5.Execute(**b)),range(2)))
    assert results[0]['result']==results[1]['result'] and len(read(f,p).json()['history'])==1
    previous=e.path.read_bytes();s=Store(f[0].dsn);a[2].attach_store(s);f[0]._isolated_local_execution.attach_store(s);p5.LifecycleExecutionPreview(s,e.root,enabled_for_synthetic_preview=True).attach_store(s)
    with actual_http(create_app(s)) as (client,requests):
        r=client.get('/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview/recovery/'+key,headers=headers(f[2]));assert r.status_code==200 and r.json()['result']==results[0]['result']
        assert {x['method'] for x in requests}=={'GET'}
    assert execute(f,p,{**b,'lifecycle_sequence':'REVALIDATE'},key).status_code==409
    assert execute(f,p,{**b,'expected_preparation_revision':b['expected_preparation_revision']+1}).status_code==409
    assert execute(f,p,{**b,'expected_request_revision':b['expected_request_revision']+1}).status_code==409
    assert execute(f,p,{**b,'expected_source_sha256':'0'*64}).status_code==409
    assert e.path.read_bytes()==previous and snapshot(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-a','prep-specialist-fixture-a'])
def test_role_tenant_and_owner_scope(lifecycle_fixture,user):
    f,p,_,_,_,_,e,a=lifecycle_fixture;b=body(f,p);before=snapshot(f);data=e.path.read_bytes()
    assert read(f,p,user=user).status_code==execute(f,p,b,user=user).status_code==403
    assert snapshot(f)==before and e.path.read_bytes()==data

@pytest.mark.parametrize('change',['owner_execute','owner_read','executor_read','assignment','reviewer','hold','lease','proof','adapter'])
def test_current_qualification_before_history_and_idempotency(lifecycle_fixture,change):
    from datetime import timedelta
    f,p,_,_,_,_,e,a=lifecycle_fixture;b=body(f,p);key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==201,r.text
    if change=='lease':a[3][0]+=timedelta(minutes=11)
    elif change=='proof':a[2].proof=None
    elif change=='adapter':f[0]._isolated_local_execution=None
    else:
        with f[1].connect() as c:
            if change.startswith('owner_'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',change.removeprefix('owner_').upper()))
            elif change=='executor_read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            elif change=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a' AND run_id=%s",(p['run_id'],))
            elif change=='reviewer':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
            elif change=='hold':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    data=e.path.read_bytes();before=snapshot(f)
    assert read(f,p,key).status_code==execute(f,p,b,key).status_code==403
    assert data==e.path.read_bytes() and snapshot(f)==before

@pytest.mark.parametrize('change',['receipt_hash','material_hash','resource_revision','resource_disabled','expired','claim','members','owner_execute','executor_read'])
def test_real_original_shadow_prerequisites_refuse_without_repair(lifecycle_fixture,monkeypatch,change):
    f,p,_,_,_,_,e,a=lifecycle_fixture;before=snapshot(f);original=e._after_receipt
    def after(private,tokens,id,artifact,sequence):
        c=private.connection._raw
        if change=='receipt_hash':c.execute("UPDATE service_step_receipts SET source_sha256=%s",('0'*64,))
        elif change=='material_hash':c.execute("UPDATE preparation_evidence SET source_sha256=%s",('0'*64,))
        elif change=='resource_revision':c.execute('UPDATE synthetic_resources SET revision=revision+1')
        elif change=='resource_disabled':c.execute('UPDATE synthetic_resources SET enabled=false')
        elif change=='expired':c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 hours',ends_at=clock_timestamp()-interval '1 hour'")
        elif change=='claim':c.execute('DELETE FROM resource_case_claims')
        elif change=='members':c.execute('DELETE FROM synthetic_resource_combination_members')
        elif change=='owner_execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='EXECUTE'",(artifact['p1']['owner_id'],))
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(artifact['executor_id'],))
        return original(private,tokens,id,artifact,sequence)
    monkeypatch.setattr(e,'_after_receipt',after)
    r=execute(f,p,body(f,p,'REVALIDATE_CLOSE'))
    if change=='members':assert r.status_code==409,r.text;assert read(f,p).json()['history']==[]
    elif change in ('owner_execute','executor_read'):assert r.status_code==403,r.text;assert read(f,p).json()['history']==[]
    else:
        assert r.status_code==201,r.text;d=r.json()['result'];assert d['state']=='FAILED' and d['artifact']['p5_state']=='FAILED' and not d['artifact']['lifecycle_events']
    assert snapshot(f)==before


def test_closed_sql_default_off_frozen_contract_and_required_mode(lifecycle_fixture):
    f,p,_,_,_,_,e,a=lifecycle_fixture;data=body(f,p);del data['lifecycle_sequence'];before=snapshot(f)
    assert execute(f,p,data).status_code==422
    assert execute(f,p,{**body(f,p),'lifecycle_sequence':'CLOSE_LOCAL_RECORD'}).status_code==422
    assert execute(f,p,{**body(f,p),'success':True}).status_code==422
    frozen=json.loads(Path('docs/F2/P5LocalCasePreviewSQLContract.json').read_text());assert frozen['sql']==sorted(p5.LIFECYCLE_SQL) and frozen['tables']==list(p5.TABLES)
    assert p4.CONTRACT=='61037dc0e1675e112fec756bf3b96ef5db4afd11b8dd9981ba0a32a7354db1ad' and len(p4.TABLES)==28 and len(p4.RECEIPT_SQL)==112
    with f[1].connect() as c:
        closed=p4._Connection(c,p5.LIFECYCLE_SQL)
        for query in ('DELETE FROM cases','UPDATE public.cases SET state=\'FULFILLED\'','SELECT * FROM principals; SELECT * FROM cases'):
            with pytest.raises(Denied):closed.execute(query)
    f[0]._isolated_lifecycle_execution_preview=None
    assert read(f,p).status_code==execute(f,p,{**data,'lifecycle_sequence':'REVALIDATE'}).status_code==403
    assert snapshot(f)==before

@pytest.mark.parametrize('change',['receipt_reopen','material_change','revision','cycle','source_hash'])
def test_late_change_between_original_read_and_close_preserves_first_event(lifecycle_fixture,monkeypatch,change):
    from parkweave import executor_receipts as er,preparation as prep
    f,p,_,_,_,_,e,a=lifecycle_fixture;before=snapshot(f);original=lc.command
    def command(private,token,id,key,data):
        if data.action=='CLOSE_LOCAL_RECORD':
            c=private.connection._raw
            if change=='receipt_reopen':
                step=c.execute('SELECT * FROM service_receipt_steps').fetchone()
                er.command(private,token,step['id'],uuid4().hex,er.Command(action='REOPEN',expected_revision=step['revision'],receipt_sha256=er._current(private.connection,step)['source_sha256'],reason='SYNTHETIC late receipt reopen'))
            elif change=='material_change':c.execute("UPDATE preparation_evidence SET text=text||' late'")
            elif change=='revision':data=data.model_copy(update={'expected_revision':0})
            elif change=='cycle':data=data.model_copy(update={'expected_cycle':2})
            else:data=data.model_copy(update={'expected_snapshot_sha256':'0'*64})
        return original(private,token,id,key,data)
    monkeypatch.setattr(lc,'command',command)
    r=execute(f,p,body(f,p,'REVALIDATE_CLOSE'));assert r.status_code==201,r.text;art=r.json()['result']['artifact']
    assert art['p5_state']=='FAILED' and [x['action'] for x in art['lifecycle_events']]==['REVALIDATE']
    assert art['lifecycle_ledger'][0]['state']=='READY' and art['lifecycle_ledger'][0]['revision']==1
    if change in ('receipt_reopen','material_change'):assert art['lifecycle_final']['verification_current'] is False
    assert snapshot(f)==before


def test_saved_commit_then_lost_response_restores_get_without_reexecution(lifecycle_fixture,monkeypatch):
    from parkweave import isolated_execution_preview as ep
    f,p,_,_,_,_,e,a=lifecycle_fixture;b=body(f,p,'REVALIDATE_CLOSE');key=uuid4().hex;comparison=e._comparison;calls=[];original=lc.command
    def command(*args):calls.append(args[-1].action);return original(*args)
    monkeypatch.setattr(lc,'command',command)
    # The first comparison follows shadow execution before INSERT; lose only the postcommit comparison.
    comparisons=[0]
    def after(*args):
        comparisons[0]+=1
        if comparisons[0]==2:raise ep.Unavailable('SYNTHETIC committed reply lost')
        return comparison(*args)
    monkeypatch.setattr(e,'_comparison',after);before=snapshot(f)
    assert execute(f,p,b,key).status_code==503 and calls==['REVALIDATE','CLOSE_LOCAL_RECORD']
    monkeypatch.setattr(e,'_comparison',comparison);data=e.path.read_bytes()
    for _ in range(2):
        r=read(f,p,key);assert r.status_code==200 and r.json()['status']=='COMMITTED' and r.json()['result']['artifact']['p5_state']=='LOCAL_RECORD_CLOSED'
    assert e.path.read_bytes()==data and calls==['REVALIDATE','CLOSE_LOCAL_RECORD'] and snapshot(f)==before


def test_new_unissued_store_cannot_restore_or_write_p5(lifecycle_fixture):
    from fastapi.testclient import TestClient
    f,p,_,_,_,_,e,a=lifecycle_fixture;b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
    s=Store(f[0].dsn);p5.LifecycleExecutionPreview(s,e.root,enabled_for_synthetic_preview=True).attach_store(s);client=TestClient(create_app(s));data=e.path.read_bytes()
    assert client.get('/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview/recovery/'+key,headers=headers(f[2])).status_code==403
    assert client.post('/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview',headers=headers(f[2],'fixture-a',key),json=b).status_code==403
    assert e.path.read_bytes()==data


def test_actual_upstream_resource_failure_retains_all_not_executed_stages(lifecycle_fixture):
    f,p,_,_,_,_,e,a=lifecycle_fixture
    with f[1].connect() as c:c.execute("UPDATE synthetic_resources SET enabled=false WHERE id IN (%s,%s)",tuple(__import__('parkweave.resource_execution_preview',fromlist=['RESOURCES']).RESOURCES))
    before=snapshot(f);r=execute(f,p);assert r.status_code==201,r.text;d=r.json()['result']
    assert d['state']=='FAILED' and d['artifact']['p2_state']=='FAILED' and d['artifact']['p3_state']=='NOT_EXECUTED' and d['artifact']['p4_state']=='NOT_EXECUTED' and d['artifact']['p5_state']=='NOT_EXECUTED'
    assert d['not_previewed']==['P3','P4','P5'] and d['coverage_state']=='PARTIAL_PREVIEW' and snapshot(f)==before


def test_source_material_version_change_keeps_immutable_old_p5_and_rebinds_explicitly(lifecycle_fixture):
    from test_isolated_execution_preview import add
    f,p,_,_,_,_,e,a=lifecycle_fixture;b=body(f,p,'REVALIDATE_CLOSE');key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==201,r.text;old=r.json()['result'];data=e.path.read_bytes()
    current=add(f,p,text='SYNTHETIC revised explicit P5 material').json();before=snapshot(f)
    r=read(f,current,key);assert r.status_code==200 and r.json()['result']==old and r.json()['history'][0]['source_state']=='STALE'
    assert execute(f,current,b).status_code==409 and e.path.read_bytes()==data
    r=execute(f,current,body(f,current,'REVALIDATE'));assert r.status_code==201,r.text
    new=r.json()['result'];assert new['binding']['source_sha256']!=old['binding']['source_sha256'] and new['binding']['slots']!=old['binding']['slots']
    history=read(f,current).json()['history'];assert len(history)==2 and history[0]['document']==old and history[0]['source_state']=='STALE' and history[1]['source_state']=='SNAPSHOT_MATCH' and snapshot(f)==before


def test_immutable_storage_and_recomputed_reopen_false_positive_refused(lifecycle_fixture):
    import sqlite3
    from parkweave import isolated_execution_preview as ep,preparation as prep
    f,p,_,_,_,_,e,a=lifecycle_fixture;r=execute(f,p,body(f,p,'REVALIDATE_CLOSE_REOPEN'));assert r.status_code==201,r.text
    with e._database() as db:
        row=dict(db.execute('SELECT * FROM previews').fetchone())
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE previews SET document=?',(row['document'],))
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM previews')
    doc=json.loads(row['document']);doc['artifact']['lifecycle_final']['verification_current']=True;doc['sha256']=ep._sha({k:v for k,v in doc.items() if k!='sha256'});row['document']=prep.canonical(doc);row['proof']=prep.canonical({k:doc[k] for k in p5.PROOF_FIELDS})
    with pytest.raises(Conflict):e._document(row)
