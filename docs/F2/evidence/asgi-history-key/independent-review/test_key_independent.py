"""New independent original-key probes; synthetic memory and isolated PG only."""
from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4
import json
import pytest
from fastapi.testclient import TestClient
from parkweave import history_summary as hs, case_fact_clarifications as facts
from parkweave.api import create_app
from test_preparation import preparation_fixture, headers
from test_fact_history_read_source_store import selected, memory_reader, snapshot
from test_history_summary import seal

def url(p,stage='P4',case=None):
    return f"/api/cases/{case or p['case_id']}/preparations/{p['preparation_id']}/history-summary/{stage}"

def register(reader,p,key):
    id=p['preparation_id']; baseline=reader.baselines[id]
    doc=json.loads(deepcopy(reader.records[id][0])['document'])
    doc['id']=str(uuid4()); doc['request_key']=key
    row=seal(doc,hs._checks(reader.stage,baseline.namespace))
    anchor=hs.RecordAnchor(doc['id'],key,hs.row_sha256(row),baseline.records[0].source_sha256)
    reader.records[id]=(*reader.records[id],row)
    reader.baselines[id]=replace(baseline,records=(*baseline.records,anchor))

def no_effect_except_audit(f,before,delta=0):
    after=snapshot(f)
    assert len(after.pop('authorization_audit')) == len(before['authorization_audit'])+delta
    assert after == {k:v for k,v in before.items() if k!='authorization_audit'}

def rejected(response,*secrets):
    assert response.status_code==403,response.text
    assert response.json()=={'detail':'record unavailable or authorization denied'}
    assert all(secret not in response.text for secret in secrets if secret)
    assert response.headers['cache-control']=='no-store'

@pytest.mark.parametrize('key,valid', [('R',True),('K'*128,True),('A0._:-z',True),
    ('K'*129,False),('',False),(' literal',False),('literal ',False),('private/key',False),
    ('private+key',False),('私密键',False),('literal\nkey',False),('%41',False)])
def test_ascii_exact_boundaries_and_generic_denial(preparation_fixture,monkeypatch,key,valid):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4')
    if valid:register(reader,p,key)
    else:
        def forbidden(*args,**kwargs):raise AssertionError('invalid key accessed history')
        monkeypatch.setattr(reader,'_rows',forbidden)
    before=snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p),headers=headers(f[2]),params={'request_key':key})
    if valid:
        assert r.status_code==200,r.text
        assert r.json()['status']=='COMMITTED'
        assert r.json()['request_key']==key and r.json()['result']['request_key']==key
        assert r.json()['result']['state']=='FAILED'
    else:rejected(r,key,'synthetic-key')
    no_effect_except_audit(f,before,0 if valid else 1)

@pytest.mark.parametrize('query',['request_key=synthetic-key&request_key=absent',
    'request_key=synthetic-key&request_key=synthetic-key',
    '%72equest_key=synthetic-key&request_key=absent'])
def test_duplicates_rejected_including_encoded_parameter_name(preparation_fixture,monkeypatch,query):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4')
    def forbidden(*args,**kwargs):raise AssertionError('duplicate key entered reader')
    monkeypatch.setattr(reader,'read_case',forbidden)
    before=snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p)+'?'+query,headers=headers(f[2]))
    rejected(r,'synthetic-key','absent')
    no_effect_except_audit(f,before,1)

@pytest.mark.parametrize('stage',['P4','P5'])
def test_exact_existing_missing_late_and_omitted_envelopes(preparation_fixture,stage):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,stage);key='Exact-Key._:07'
    register(reader,p,key);before=snapshot(f);initial_records=deepcopy(reader.records)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        full=client.get(url(p,stage),headers=headers(f[2])).json()
        assert not {'request_key','status','result'} & full.keys()
        for requested,hit in [(key,True),(key.swapcase(),False),('late-key',False)]:
            r=client.get(url(p,stage),headers=headers(f[2]),params={'request_key':requested})
            assert r.status_code==200,r.text
            data=r.json();assert data['history']==full['history']
            assert data['case_id']==p['case_id'] and data['stage']==stage
            assert data['request_key']==requested
            assert data['status']==('COMMITTED' if hit else 'NOT_OBSERVED')
            assert data['result']==(full['history'][1]['summary'] if hit else None)
            assert not data['automatically_replayed'] and not data['execution_available']
            assert not data['new_grants'] and data['formal_writes']==0
            assert data['execution_qualification']=='NOT_EVALUATED'
            if hit:assert data['result']['state']=='FAILED'
            for private in ('PRIVATE ERROR','proof','artifact','source_snapshot','source_excerpt','choices'):
                assert private not in json.dumps(data)
        assert reader.records==initial_records
        register(reader,p,'late-key')
        r=client.get(url(p,stage),headers=headers(f[2]),params={'request_key':'late-key'})
        assert r.status_code==200,r.text
        assert r.json()['status']=='COMMITTED' and r.json()['result']['state']=='FAILED'
        assert r.json()['result']==r.json()['history'][2]['summary']
        assert not r.json()['automatically_replayed'] and r.json()['formal_writes']==0
        assert client.get(url(p,stage),headers=headers(f[2])).json()['history']==r.json()['history']
    no_effect_except_audit(f,before)

@pytest.mark.parametrize('key',['synthetic-key','private-missing-key'])
@pytest.mark.parametrize('field',facts.FIELDS)
def test_present_and_absent_key_require_each_current_field(preparation_fixture,monkeypatch,key,field):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4')
    f[1].revoke_field('fixture-a',field,'READ')
    def forbidden(*args,**kwargs):raise AssertionError('key bypassed current private-source READ')
    monkeypatch.setattr(f[0],'facts_query',forbidden)
    monkeypatch.setattr(reader,'_rows',forbidden)
    before=snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p),headers=headers(f[2]),params={'request_key':key})
    rejected(r,key,'synthetic-key');no_effect_except_audit(f,before,1)

@pytest.mark.parametrize('key',['synthetic-key','private-missing-key'])
@pytest.mark.parametrize('change',['read','source_version','baseline_expiry','late_history'])
def test_key_cannot_skip_after_projection_guard(preparation_fixture,monkeypatch,key,change):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4');original=hs.summaries
    def change_after_projection(*args,**kwargs):
        result=original(*args,**kwargs)
        if change=='baseline_expiry':
            b=reader.baselines[p['preparation_id']]
            reader.baselines[p['preparation_id']]=replace(b,valid_until=b.valid_from)
        elif change=='late_history':register(reader,p,'private-missing-key')
        else:
            with f[1].connect() as c:
                if change=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                else:c.execute("UPDATE fact_assertions SET revision=revision+1 WHERE field_name='region'")
        return result
    monkeypatch.setattr(hs,'summaries',change_after_projection)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p),headers=headers(f[2]),params={'request_key':key})
    rejected(r,key,'synthetic-key')

@pytest.mark.parametrize('key',['synthetic-key','private-missing-key'])
def test_wrong_case_rejects_before_source_or_history(preparation_fixture,monkeypatch,key):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4')
    def forbidden(*args,**kwargs):raise AssertionError('wrong Case touched private source/history')
    monkeypatch.setattr(f[0],'facts_query',forbidden)
    monkeypatch.setattr(reader,'_rows',forbidden)
    before=snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p,case=uuid4()),headers=headers(f[2]),params={'request_key':key})
    rejected(r,key,'synthetic-key');no_effect_except_audit(f,before,1)

@pytest.mark.parametrize('key',[None,'private-missing-key'])
def test_key_addition_preserves_route_stage_pin(preparation_fixture,monkeypatch,key):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4');other=memory_reader(f,p,'P5')
    original=reader.read_case
    def switched(*args,**kwargs):
        reader.stage=other.stage;reader.baselines=other.baselines;reader.records=other.records
        return original(*args,**kwargs)
    monkeypatch.setattr(reader,'read_case',switched)
    before=snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p),headers=headers(f[2]),params={} if key is None else {'request_key':key})
    rejected(r,key,'synthetic-key');no_effect_except_audit(f,before,1)

def test_missing_key_cannot_accept_unanchored_extra_row(preparation_fixture):
    f=preparation_fixture;p=selected(f);reader=memory_reader(f,p,'P4')
    reader.records[p['preparation_id']]+= (deepcopy(reader.records[p['preparation_id']][0]),)
    before=snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        r=client.get(url(p),headers=headers(f[2]),params={'request_key':'private-missing-key'})
    rejected(r,'private-missing-key','synthetic-key');no_effect_except_audit(f,before,1)

def test_default_none_cannot_be_registered_by_key(preparation_fixture):
    f=preparation_fixture;p=selected(f);before=snapshot(f)
    with TestClient(create_app(f[0])) as client:
        r=client.get(url(p),headers=headers(f[2]),params={'request_key':'synthetic-key','summary_reader':'P4'})
    rejected(r,'synthetic-key');no_effect_except_audit(f,before,1)
