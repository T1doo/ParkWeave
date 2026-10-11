"""Actual old P4/P5 documents with current READ; no durable trust enrollment."""
from dataclasses import replace
from datetime import timedelta
from uuid import UUID,uuid4
import sqlite3
import pytest
from fastapi.testclient import TestClient
from parkweave import history_summary as hs, receipt_execution_preview as p4, lifecycle_execution_preview as p5
from parkweave.store import Store,Denied
from parkweave.api import create_app
from test_lifecycle_execution_preview import lifecycle_fixture,receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,snapshot,schema,execute as p5_execute,body as p5_body
from test_receipt_execution_preview import execute as p4_execute,body as p4_body
from test_preparation import headers,add


def memory_reader(f,p,e,stage):
    cold=Store(f[0].dsn)
    with cold.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        context=hs.current_context(cold,c,f[2]['fixture-a'],UUID(p['preparation_id']))
    with sqlite3.connect('file:'+str(e.path)+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=tuple(dict(r) for r in db.execute('SELECT * FROM previews ORDER BY rowid'))
    checks=hs._checks(stage,e.namespace)
    anchors=tuple(hs.RecordAnchor(checks._document(r)['id'],r['request_key'],hs.row_sha256(r),context.source_sha256) for r in rows)
    baseline=hs.TrustedBaseline(stage,checks.storage_scope,e.namespace,checks.document_version,
        checks.execution_contract,context.owner,context.park,context.org,context.preparation,context.case,
        context.run,context.database,context.now-timedelta(minutes=1),context.now+timedelta(minutes=10),False,anchors)
    return cold,hs.MemoryHistorySummaryReader(stage,{context.preparation:baseline},{context.preparation:rows}),baseline


@pytest.mark.parametrize('stage,mode',[('P4','ACKNOWLEDGE'),('P4','REQUEST_CHANGES'),('P5','REVALIDATE'),('P5','REVALIDATE_CLOSE'),('P5','REVALIDATE_CLOSE_REOPEN')])
def test_actual_original_documents_read_without_execution_and_old_http_stays_closed(lifecycle_fixture,stage,mode):
    f,p,_,_,_,p4e,p5e,_=lifecycle_fixture;e=p4e if stage=='P4' else p5e
    key=uuid4().hex
    b=p4_body(f,p,mode) if stage=='P4' else p5_body(f,p,mode)
    response=p4_execute(f,p,b,key) if stage=='P4' else p5_execute(f,p,b,key)
    assert response.status_code==201,response.text
    original=response.json()['result'];assert original['state']=='SUCCEEDED'
    cold,reader,baseline=memory_reader(f,p,e,stage)
    f[1].revoke_capability('fixture-a','EXECUTE')
    with f[1].connect() as c:
        c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
        c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    before=snapshot(f);columns=schema(f[1]);old_bytes=e.path.read_bytes()
    result=reader.read(cold,f[2]['fixture-a'],UUID(p['preparation_id']),key)
    assert result['status']=='COMMITTED' and result['result']['p4_state']==original['artifact']['p4_state']
    if stage=='P5':
        final=original['artifact']['lifecycle_final'];summary=result['result']
        assert summary['past_case_state']==final['case_state'] and summary['past_cycle']==final['cycle']
        assert summary['verification_at_execution'] is final['verification_current']
        assert summary['past_case_state']!='FULFILLED'
    assert reader.read(cold,f[2]['fixture-a'],UUID(p['preparation_id']),'absent')['result'] is None
    route='receipt' if stage=='P4' else 'lifecycle'
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview',headers=headers(f[2])).status_code==403
    assert f[3].post('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview',headers=headers(f[2],key=uuid4().hex),json=b).status_code==403
    # Neither an ordinary Store nor putting this adapter in the old attribute
    # bypasses the existing exact provider type gate.
    with TestClient(create_app(cold)) as client:
        for attached in (False,True):
            if attached:setattr(cold,'_isolated_'+route+'_execution_preview',reader)
            assert client.get('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview',headers=headers(f[2])).status_code==403
            assert client.post('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview',headers=headers(f[2],key=uuid4().hex),json=b).status_code==403
        cold._isolated_receipt_history=reader
        assert client.get('/api/preparations/'+p['preparation_id']+'/receipt-execution-history',headers=headers(f[2])).status_code==403
    assert snapshot(f)==before and schema(f[1])==columns and e.path.read_bytes()==old_bytes
    assert baseline==reader.baselines[p['preparation_id']]


@pytest.mark.parametrize('change',['read','resource_read','inactive','wrong_owner','wrong_tenant','resource_unknown','catalog_unknown','resource_disabled','replacement_db','expired','revoked','missing_baseline','declared_fact','material_stale','resource_stale','material_missing','material_one_slot','material_hash','material_body','material_actor','nonmapping','new_material_stale'])
def test_actual_current_scope_source_revocation_and_legal_version_changes(lifecycle_fixture,change):
    f,p,_,_,_,e,_,_=lifecycle_fixture;key=uuid4().hex
    response=p4_execute(f,p,key=key);assert response.status_code==201,response.text
    cold,reader,b=memory_reader(f,p,e,'P4');token=f[2]['fixture-a'];id=UUID(p['preparation_id'])
    if change=='wrong_owner':token=f[2]['fixture-b']
    elif change in ('replacement_db','expired','revoked'):
        updates={'replacement_db':dict(database=('replacement','1','2')),'expired':dict(valid_until=b.valid_from),'revoked':dict(revoked=True)}
        reader.baselines[p['preparation_id']]=replace(b,**updates[change])
    elif change=='missing_baseline':reader.baselines.clear()
    elif change=='nonmapping':reader.records[p['preparation_id']]=(42,)
    elif change=='new_material_stale':
        response=add(f,p,'need_summary','SYNTHETIC legitimate new material version')
        assert response.status_code==200,response.text
    else:
        with f[1].connect() as c:
            if change=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            elif change=='resource_read':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
            elif change=='inactive':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
            elif change=='wrong_tenant':c.execute("UPDATE principals SET org_id='other' WHERE id='fixture-a'")
            elif change=='resource_unknown':c.execute("UPDATE synthetic_resources SET source='{}'::jsonb")
            elif change=='catalog_unknown':c.execute("UPDATE preparation_catalog SET source='{}'::jsonb")
            elif change=='resource_disabled':c.execute('UPDATE synthetic_resources SET enabled=false')
            elif change=='material_stale':c.execute('UPDATE preparation_evidence SET version=version+1 WHERE preparation_id=%s',(id,))
            elif change=='resource_stale':c.execute('UPDATE synthetic_resources SET revision=revision+1')
            elif change=='material_missing':c.execute('DELETE FROM preparation_evidence WHERE preparation_id=%s',(id,))
            elif change=='material_one_slot':c.execute("DELETE FROM preparation_evidence WHERE preparation_id=%s AND slot='need_summary'",(id,))
            elif change=='material_hash':c.execute("UPDATE preparation_evidence SET source_sha256='invalid' WHERE preparation_id=%s",(id,))
            elif change=='material_body':c.execute("UPDATE preparation_evidence SET text='SYNTHETIC unrecorded tamper' WHERE preparation_id=%s",(id,))
            elif change=='material_actor':c.execute("UPDATE preparation_evidence SET actor_id='fixture-b' WHERE preparation_id=%s",(id,))
            elif change=='declared_fact':
                # Synthetic declaration only, no current fact execution gate.
                c.execute("UPDATE preparations SET fact_clarifications='{}'::jsonb WHERE id=%s",(id,))
    before=snapshot(f);old_bytes=e.path.read_bytes()
    if change.endswith('_stale'):
        result=reader.read(cold,token,id,key)
        assert result['status']=='COMMITTED' and result['history'][0]['source_state']=='STALE'
    else:
        with pytest.raises(Denied):reader.read(cold,token,id,key)
    assert snapshot(f)==before and e.path.read_bytes()==old_bytes


def test_current_read_denial_precedes_corrupt_history_decode(lifecycle_fixture,monkeypatch):
    f,p,_,_,_,e,_,_=lifecycle_fixture
    response=p4_execute(f,p);assert response.status_code==201,response.text
    cold,reader,_=memory_reader(f,p,e,'P4')
    reader.records[p['preparation_id']]=({'document':'PRIVATE MALFORMED'},)
    f[1].revoke_capability('fixture-a','READ')
    def unavailable(*args,**kwargs):raise AssertionError('history decoded before READ')
    monkeypatch.setattr(hs,'summaries',unavailable)
    with pytest.raises(Denied,match='current capability grant required'):
        reader.read(cold,f[2]['fixture-a'],UUID(p['preparation_id']))


@pytest.mark.parametrize('change',['baseline','records','source','read'])
def test_final_guard_rejects_memory_or_noncooperative_source_changes(lifecycle_fixture,monkeypatch,change):
    f,p,_,_,_,e,_,_=lifecycle_fixture
    response=p4_execute(f,p);assert response.status_code==201,response.text
    cold,reader,b=memory_reader(f,p,e,'P4');original=hs.summaries
    def changed(*args,**kwargs):
        result=original(*args,**kwargs)
        if change=='baseline':reader.baselines[p['preparation_id']]=replace(b,revoked=True)
        elif change=='records':reader.records[p['preparation_id']]=()
        else:
            # Deliberate fixture writer ignores cooperative advisory guards.
            with f[1].connect() as c:
                if change=='source':c.execute('UPDATE synthetic_resources SET revision=revision+1')
                else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        return result
    monkeypatch.setattr(hs,'summaries',changed)
    old_bytes=e.path.read_bytes()
    with pytest.raises(Denied):reader.read(cold,f[2]['fixture-a'],UUID(p['preparation_id']))
    assert e.path.read_bytes()==old_bytes
