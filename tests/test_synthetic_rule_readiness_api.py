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


def test_at22_api_business_date_region_and_reviewed_version_keep_original_history(simulation,tmp_path):
    """One finite HTTP-boundary case; original rule/fact algorithms are reused."""
    from copy import deepcopy
    from datetime import datetime,timedelta
    from hashlib import sha256
    import json
    from parkweave import synthetic_rule_readiness as sr
    from parkweave.rule_publication_candidate_api import create_candidate_app
    from test_case_fact_clarifications_integration import authority,business,preparation_records,assertions

    f,p,engine,adapter,context=simulation
    path='/api/preparations/'+p['preparation_id']+'/synthetic-rule-readiness'
    scope=adapter.bindings[0].scope
    candidate_path='/api/candidate/'+scope.park_id+'/'+scope.org_id+'/'+scope.service_id
    query=context.model_dump();observations=[]
    before=(authority(f),business(f),preparation_records(f),assertions(f))
    def unchanged():assert (authority(f),business(f),preparation_records(f),assertions(f))==before
    def observe(api,label,*,params=None,truth,block=None):
        response=api.get(path,params=params or query,headers=headers(f[2]))
        assert response.status_code==200,response.text
        value=response.json();source=value['sources']
        assert value['result']['synthetic_simulated_condition_truth']==truth
        assert source['current_block']==block
        for flags in (value,value['result']):
            assert flags['formal_review'] is False and flags['business_publication'] is False
            assert flags['qualification_truth']=='UNKNOWN' and flags['qualification_decision']=='NOT_EVALUATED'
        observations.append(dict(stage=label,truth=truth,current_block=source['current_block'],
            context=source['context'],binding=source['binding'],release_id=source['release']['id'],
            rule_revision=source['release']['draft']['spec']['revision'],source_sha256=value['source_sha256'],
            history=[dict(receipt_sha256=x['receipt_sha256'],truth=x['result']['synthetic_simulated_condition_truth'],
                          current_truth=x['current_truth'],state=x['state']) for x in value['history']]))
        unchanged();return value
    def assess(api,value,key):
        response=api.post(path,headers=headers(f[2],key=key),json=dict(context=query,
            expected_preparation_revision=value['preparation_revision'],expected_source_sha256=value['source_sha256'],
            reason='SYNTHETIC AT22 explicit finite API assessment'))
        assert response.status_code==200,response.text
        unchanged();return response.json()
    def reconfigured(binding):
        # Original issued fixture + original exact adapter and same journal.
        # This is explicit simulation configuration, never a LinuxHost issuance.
        return sr.SyntheticRuleReadiness(f[0],f[1],engine,adapter.journal,
            bindings=[binding],enabled_for_isolated_tests=True)

    with TestClient(create_app(f[0],synthetic_rule_readiness=adapter)) as api,TestClient(create_candidate_app(engine)) as candidate:
        initial=observe(api,'reviewed_v1',truth='TRUE');first=assess(api,initial,'at22-v1')
        original_binding=adapter.bindings[0];original_release=initial['sources']['release']
        start=datetime.fromisoformat(original_release['draft']['spec']['validity']['valid_from'])
        before_start={**query,'as_of':(start-timedelta(seconds=1)).isoformat()}
        value=observe(api,'business_date_before_source_start',params=before_start,
                      truth='UNKNOWN',block='EXPIRED_OR_NOT_YET_VALID_SOURCE')
        assert value['sources']['release']['id']==original_binding.release_id
        assert value['history'][0]['receipt_sha256']==first['receipt_sha256']
        assert value['history'][0]['result']==first['result'] and value['history'][0]['current_truth']=='UNKNOWN'
        at_end={**query,'as_of':original_release['validity']['valid_until']}
        observe(api,'business_date_at_source_end',params=at_end,
                truth='UNKNOWN',block='EXPIRED_OR_NOT_YET_VALID_SOURCE')

        wrong_region=reconfigured(original_binding.model_copy(update={'region':'REGION_B','epoch':2}))
        with TestClient(create_app(f[0],synthetic_rule_readiness=wrong_region)) as other:
            value=observe(other,'different_configured_region',truth='UNKNOWN',block='REGION_NOT_APPLICABLE')
            assert value['sources']['region_condition']['truth']=='FALSE'
            assert value['history'][0]['result']==first['result']

        current=candidate.get(candidate_path,headers={'X-Mock-Actor':'fixture-a'})
        assert current.status_code==200,current.text
        draft=deepcopy(current.json()['draft']);draft['spec']['revision']='2'
        draft['spec']['eligibility']['expected']=3
        draft['spec']['source_refs'][0]['revision']='2';draft['sources'][0]['ref']['revision']='2'
        draft['sources'][0]['text']='SYNTHETIC AT22 explicitly changed employee comparison from 17 to 3'
        for action,actor in [('SAVE','fixture-a'),('SUBMIT','fixture-a'),('REVIEW','mock-reviewer'),('PUBLISH','mock-publisher')]:
            current=candidate.get(candidate_path,headers={'X-Mock-Actor':actor});assert current.status_code==200,current.text
            current=current.json();body=dict(action=action,expected_revision=current['revision'],
                expected_content_sha256=current['content_sha256'],reason='SYNTHETIC AT22 explicit '+action)
            if action=='SAVE':body['draft']=draft
            if action=='PUBLISH':body['publish_validity']=original_release['validity']
            response=candidate.post(candidate_path+'/commands',headers={'X-Mock-Actor':actor,'Idempotency-Key':'at22-'+action.lower()},json=body)
            assert response.status_code==200,response.text
            stage=candidate.get(candidate_path,headers={'X-Mock-Actor':'fixture-a'})
            assert stage.status_code==200,stage.text
            stage=stage.json()
            assert stage['state']=={'SAVE':'DRAFT','SUBMIT':'REVIEW_REQUESTED','REVIEW':'REVIEWED','PUBLISH':'PUBLISHED'}[action]
            assert stage['candidate_available'] is (action=='PUBLISH')
            assert len(stage['releases'])==(2 if action=='PUBLISH' else 1)
            value=observe(api,'v2_'+action.lower()+'_old_binding',truth='UNKNOWN',block='CURRENT_SYNTHETIC_REVIEWED_RELEASE_REQUIRED')
            assert value['history'][0]['result']==first['result']
            assert value['sources']['binding']['release_id']==original_binding.release_id

        current=candidate.get(candidate_path,headers={'X-Mock-Actor':'fixture-a'}).json()
        release=current['releases'][-1];assert release['id']!=original_release['id']
        assert release['reviewer_id']=='mock-reviewer' and release['publisher_id']=='mock-publisher'
        revised=reconfigured(original_binding.model_copy(update={'release_id':release['id'],
            'content_sha256':release['content_sha256'],'epoch':2}))
        with TestClient(create_app(f[0],synthetic_rule_readiness=revised)) as new_api:
            value=observe(new_api,'explicitly_bound_reviewed_v2',truth='FALSE')
            assert value['sources']['release']['draft']['spec']['eligibility']['expected']==3
            assert value['sources']['binding']['epoch']==2
            assert value['history'][0]['current_truth']=='UNKNOWN'
            second=assess(new_api,value,'at22-v2')
            recovered=new_api.get(path+'/recovery/at22-v1',params=query,headers=headers(f[2]))
            assert recovered.status_code==200,recovered.text
            recovered=recovered.json()
            assert recovered['status']=='COMMITTED' and recovered['automatically_replayed'] is False
            assert recovered['receipt']['receipt_sha256']==first['receipt_sha256']
            assert recovered['receipt']['result']==first['result'] and recovered['receipt']['current_truth']=='UNKNOWN'
            assert recovered['current']['result']==second['result']
            assert [x['result']['synthetic_simulated_condition_truth'] for x in recovered['current']['history']]==['TRUE','FALSE']
    unchanged()
    with adapter.journal.connect() as c:assert c.execute('SELECT count(*) FROM simulation_assessments').fetchone()[0]==2
    stable=lambda value:sha256(json.dumps(value,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()
    (tmp_path/'at22-api-case.json').write_text(json.dumps(dict(observations=observations,
        historical_v1_receipt_sha256=first['receipt_sha256'],v2_receipt_sha256=second['receipt_sha256'],
        pg_snapshots_unchanged=True,before_pg_sha256=stable(before),after_pg_sha256=stable((authority(f),business(f),preparation_records(f),assertions(f))),
        initialized_by='original isolated synthetic fixture; no root host/writer policy issuance',
        execution='actual ASGI TestClient + original owned temporary PG + candidate/journal SQLite',real_model_calls=0),indent=2)+'\n')
