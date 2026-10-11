"""In-process ASGI routes + isolated synthetic PG; no HTTP listener/browser."""
from dataclasses import replace
from uuid import uuid4
import inspect
import json

import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app, configured_app
from parkweave import history_summary as hs
from test_history_summary_store import memory_reader
from test_lifecycle_execution_preview import lifecycle_fixture,receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,snapshot,schema,execute as p5_execute,body as p5_body
from test_receipt_execution_preview import execute as p4_execute,body as p4_body
from test_preparation import headers


@pytest.fixture(params=['P4','P5'])
def summary_route(lifecycle_fixture,request):
    f,p,_,_,_,p4e,p5e,_=lifecycle_fixture
    stage=request.param;e=p4e if stage=='P4' else p5e
    key=uuid4().hex
    body=p4_body(f,p,'REQUEST_CHANGES') if stage=='P4' else p5_body(f,p,'REVALIDATE_CLOSE_REOPEN','REQUEST_CHANGES')
    response=p4_execute(f,p,body,key) if stage=='P4' else p5_execute(f,p,body,key)
    assert response.status_code==201,response.text
    cold,reader,baseline=memory_reader(f,p,e,stage)
    path=f"/api/cases/{p['case_id']}/preparations/{p['preparation_id']}/history-summary/{stage}"
    return f,p,cold,reader,baseline,e,key,body,path


def test_default_none_wrong_stage_and_exact_provider_gate_remain_unavailable(summary_route):
    f,p,cold,reader,_,_,key,_,path=summary_route
    assert inspect.signature(create_app).parameters['summary_reader'].default is None
    class Derived(hs.MemoryHistorySummaryReader):pass
    derived=Derived(reader.stage,reader.baselines,reader.records)
    before=snapshot(f)
    for supplied in (None,object(),derived):
        with TestClient(create_app(cold,summary_reader=supplied)) as client:
            response=client.get(path,headers=headers(f[2]))
            assert response.status_code==403 and set(response.json())=={'detail'},response.text
    with TestClient(create_app(cold,summary_reader=reader)) as client:
        other=path[:-2]+('P5' if reader.stage=='P4' else 'P4')
        assert client.get(other,headers=headers(f[2])).status_code==403
        assert client.get(path).status_code==401
        assert client.post(path,headers=headers(f[2],key=key),json={}).status_code==405
    assert snapshot(f)==before


def test_inprocess_current_read_fixed_projection_and_execute_withdrawal(summary_route):
    f,p,cold,reader,b,e,key,body,path=summary_route
    before=snapshot(f);columns=schema(f[1]);old_bytes=e.path.read_bytes()
    with TestClient(create_app(cold,summary_reader=reader)) as client:
        response=client.get(path,params={'request_key':key},headers=headers(f[2]))
        assert response.status_code==200,response.text
        first=response.json();assert first['case_id']==p['case_id'] and first['stage']==reader.stage
        assert first['status']=='COMMITTED' and first['result']==first['history'][0]['summary']
        assert first['summary_only'] is True and first['execution_available'] is False
        assert first['execution_qualification']=='NOT_EVALUATED' and first['formal_writes']==0
        if reader.stage=='P5':
            assert first['result']['state']=='FAILED' and first['result']['past_case_state']=='NEEDS_INPUT'
            assert first['result']['verification_at_execution'] is False
        assert snapshot(f)==before
        f[1].revoke_capability('fixture-a','EXECUTE');withdrawn=snapshot(f)
        response=client.get(path,params={'request_key':key},headers=headers(f[2]))
        assert response.status_code==200 and response.json()==first,response.text
        envelope=client.get(path,headers=headers(f[2])).json()
        assert 'status' not in envelope and 'result' not in envelope
        absent=client.get(path,params={'request_key':'unobserved'},headers=headers(f[2]))
        assert absent.status_code==200 and absent.json()['status']=='NOT_OBSERVED' and absent.json()['result'] is None
        text=json.dumps(first)
        for private in ('document','proof','artifact','PRIVATE','reason','report','text','source_sha256',f[2]['fixture-a'],b.owner,b.run):
            assert private not in text
        route='receipt' if reader.stage=='P4' else 'lifecycle'
        # Injection never registers the old provider or enables its GET/POST.
        setattr(cold,'_isolated_'+route+'_execution_preview',reader)
        cold._isolated_receipt_history=reader
        for suffix in (route+'-execution-preview',route+'-execution-preview/recovery/'+key,'receipt-execution-history','receipt-execution-history/recovery/'+key):
            assert client.get('/api/preparations/'+p['preparation_id']+'/'+suffix,headers=headers(f[2])).status_code==403
        assert client.post('/api/preparations/'+p['preparation_id']+'/'+route+'-execution-preview',headers=headers(f[2],key=key),json=body).status_code==403
        assert snapshot(f)==withdrawn
    assert schema(f[1])==columns and e.path.read_bytes()==old_bytes


@pytest.mark.parametrize('change',['missing','expired','revoked','READ','other_owner','wrong_case','wrong_preparation'])
def test_inprocess_registration_and_current_identity_case_denials(summary_route,change,monkeypatch):
    f,p,cold,reader,b,e,key,_,path=summary_route
    token=headers(f[2])
    if change=='missing':reader.baselines.clear()
    elif change=='expired':reader.baselines[p['preparation_id']]=replace(b,valid_until=b.valid_from)
    elif change=='revoked':reader.baselines[p['preparation_id']]=replace(b,revoked=True)
    elif change=='READ':f[1].revoke_capability('fixture-a','READ')
    elif change=='other_owner':token=headers(f[2],'fixture-b')
    elif change=='wrong_case':path=path.replace(p['case_id'],str(uuid4()))
    else:path=path.replace(p['preparation_id'],str(uuid4()))
    if change in ('READ','other_owner','wrong_case','wrong_preparation'):
        def forbidden(*args,**kwargs):raise AssertionError('history decoded before current identity/Case gate')
        monkeypatch.setattr(hs,'summaries',forbidden)
    before=snapshot(f);old_bytes=e.path.read_bytes()
    with TestClient(create_app(cold,summary_reader=reader)) as client:
        response=client.get(path,params={'request_key':key},headers=token)
        assert response.status_code==403,response.text
        assert response.json()=={'detail':'record unavailable or authorization denied'}
        assert response.headers['cache-control']=='no-store'
    assert snapshot(f)==before and e.path.read_bytes()==old_bytes


@pytest.mark.parametrize('key',['','x'*129,'../private','space key'])
def test_inprocess_summary_key_bound_and_no_history_disclosure(summary_route,key):
    f,_,cold,reader,_,_,_,_,path=summary_route
    with TestClient(create_app(cold,summary_reader=reader)) as client:
        response=client.get(path,params={'request_key':key},headers=headers(f[2]))
        assert response.status_code==422,response.text
        assert 'history' not in response.json()


def test_normal_configured_application_does_not_load_or_register_summary(preparation_fixture,monkeypatch):
    f=preparation_fixture
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn)
    def never(*args,**kwargs):raise AssertionError('normal application must not construct summary reader')
    monkeypatch.setattr(hs.MemoryHistorySummaryReader,'__init__',never)
    with TestClient(configured_app()) as client:
        response=client.get(f'/api/cases/{uuid4()}/preparations/{uuid4()}/history-summary/P5',headers=headers(f[2]))
        assert response.status_code==403 and set(response.json())=={'detail'}


@pytest.mark.parametrize('stage,mode',[('P4','ACKNOWLEDGE'),('P5','REVALIDATE'),('P5','REVALIDATE_CLOSE'),('P5','REVALIDATE_CLOSE_REOPEN')])
def test_inprocess_successful_original_local_close_reopen_preserves_case_boundary(lifecycle_fixture,stage,mode):
    f,p,_,_,_,p4e,p5e,_=lifecycle_fixture
    e=p4e if stage=='P4' else p5e;key='synthetic_original_key-'+uuid4().hex
    data=p4_body(f,p,mode) if stage=='P4' else p5_body(f,p,mode)
    response=p4_execute(f,p,data,key) if stage=='P4' else p5_execute(f,p,data,key)
    assert response.status_code==201,response.text
    cold,reader,_=memory_reader(f,p,e,stage);f[1].revoke_capability('fixture-a','EXECUTE')
    before=snapshot(f);original=e.path.read_bytes()
    path=f"/api/cases/{p['case_id']}/preparations/{p['preparation_id']}/history-summary/{stage}"
    with TestClient(create_app(cold,summary_reader=reader)) as client:
        response=client.get(path,params={'request_key':key},headers=headers(f[2]))
        assert response.status_code==200,response.text
        result=response.json()['result'];assert result['state']=='SUCCEEDED' and result['request_key']==key
        assert result['case_goal_completed'] is False and result['qualification']=='NOT_EVALUATED'
        assert result['external_acceptance']=='NOT_SUBMITTED' and result['offline_fulfillment']=='NO_EVIDENCE'
        if stage=='P5':
            assert result['past_case_state']==('REOPENED' if mode.endswith('REOPEN') else 'WAITING_CONFIRMATION')
            assert result['past_cycle']==(2 if mode.endswith('REOPEN') else 1)
            assert result['verification_at_execution'] is (not mode.endswith('REOPEN'))
    assert snapshot(f)==before and e.path.read_bytes()==original
