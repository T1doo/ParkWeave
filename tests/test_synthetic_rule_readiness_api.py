"""Real ASGI boundary for the explicitly enabled owned rule simulation."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.store import Denied
from test_preparation import preparation_fixture,headers
from test_synthetic_rule_readiness import simulation


def test_actual_api_read_explicit_assess_recover_and_scope(simulation):
    f,p,e,adapter,context=simulation
    path='/api/preparations/'+p['preparation_id']+'/synthetic-rule-readiness'
    query=context.model_dump();key=uuid4().hex
    with TestClient(create_app(f[0],synthetic_rule_readiness=adapter)) as api:
        current=api.get(path,params=query,headers=headers(f[2]));assert current.status_code==200,current.text
        value=current.json();assert value['result']['synthetic_simulated_condition_truth']=='TRUE'
        body=dict(context=query,expected_preparation_revision=value['preparation_revision'],expected_source_sha256=value['source_sha256'],reason='SYNTHETIC explicit API assessment')
        first=api.post(path,json=body,headers=headers(f[2],key=key));assert first.status_code==200,first.text
        again=api.post(path,json=body,headers=headers(f[2],key=key));assert again.json()==first.json()
        saved=api.get(path+'/recovery/'+key,params=query,headers=headers(f[2]));assert saved.status_code==200,saved.text
        assert saved.json()['status']=='COMMITTED' and not saved.json()['automatically_replayed']
        conflict=api.post(path,json={**body,'reason':'different'},headers=headers(f[2],key=key));assert conflict.status_code==409
        unknown=api.get(path+'/recovery/not-observed',params=query,headers=headers(f[2]));assert unknown.json()['status']=='NOT_OBSERVED'
        assert api.get(path,params={**query,'as_of':'bad'},headers=headers(f[2])).status_code==422
        assert api.get(path,params=query,headers=headers(f[2],'fixture-b')).status_code==403
        assert api.get(path,params={**query,'binding_id':'client-claimed'},headers=headers(f[2])).status_code==403
    with TestClient(create_app(f[0])) as api:
        assert api.get(path,params=query,headers=headers(f[2])).status_code==403
    with pytest.raises(Denied):create_app(f[0],synthetic_rule_readiness=object())


def test_actual_committed_assessment_lost_reply_recovered_only_by_original_get(simulation,monkeypatch):
    from fastapi import HTTPException
    f,p,e,adapter,context=simulation
    path='/api/preparations/'+p['preparation_id']+'/synthetic-rule-readiness'
    query=context.model_dump();key=uuid4().hex;calls=[];original=adapter.assess
    def lose(*args,**kwargs):
        calls.append(key)
        original(*args,**kwargs)
        raise HTTPException(503,'SYNTHETIC response lost after committed assessment')
    with TestClient(create_app(f[0],synthetic_rule_readiness=adapter)) as api:
        value=api.get(path,params=query,headers=headers(f[2])).json()
        body=dict(context=query,expected_preparation_revision=value['preparation_revision'],expected_source_sha256=value['source_sha256'],reason='SYNTHETIC explicit lost-response assessment')
        monkeypatch.setattr(adapter,'assess',lose)
        response=api.post(path,json=body,headers=headers(f[2],key=key));assert response.status_code==503
        with e.repository.connect(write=True) as c:c.execute('DELETE FROM candidate_releases')
        recovered=api.get(path+'/recovery/'+key,params=query,headers=headers(f[2]));assert recovered.status_code==200,recovered.text
        result=recovered.json();assert result['status']=='COMMITTED' and not result['automatically_replayed']
        assert result['receipt']['result']['synthetic_simulated_condition_truth']=='TRUE'
        assert result['receipt']['current_truth']=='UNKNOWN'
        assert result['current']['current_source_unavailable']
        assert result['current']['result']['synthetic_simulated_condition_truth']=='UNKNOWN'
        assert calls==[key]
        with adapter.journal.connect() as c:assert c.execute('SELECT count(*) FROM simulation_assessments').fetchone()[0]==1
