"""Independent mixed-journal probes; legacy conversion is fixture compatibility only."""
from copy import deepcopy
import hashlib
import json
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from conftest import pg, fixture
from test_typed_source_impact_independent import (
    typed_http, link_fixture, receipt_fixture, preparation_fixture,
    complete, stored, import_card, add_resource, preview, adopt, verified,
    source_impact, checked_graph, assert_partition, plan_read, goal_results,
)
from test_service_plan_recovery import recover
from test_template_upgrade import upgrade_case, publication
from test_template_structure_independent import complete_declared, admit as structural_admit, apply as structural_apply, SIX_GOALS
from test_new_enterprise_local_chain import actual_http
from parkweave.template_isolated_app import create_isolated_template_app


def protocol_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def test_legacy_v1_then_actual_v2_keep_both_original_key_histories(typed_http):
    from parkweave.service_case_steps import Adopt, _adopt_request
    f,_=typed_http;p,_,_,_=complete(f,local=True);card=import_card(f,p);add_resource(f)
    first=preview(f,p,card).json();key1=uuid4().hex;response=adopt(f,p,first['adoption'],key1);assert response.status_code == 201,response.text
    # Compatibility fixture only: reconstruct exactly the retained old v1 wire
    # proof. No new current business fact or historical slot identity is invented.
    plan=stored(f,p);event=plan['events'][-1];change=event['local_revision']['source_change']
    change['version']=1;change.pop('source_impact');change['sha256']=protocol_hash({k:v for k,v in change.items() if k!='sha256'})
    request=event['local_revision']['request'];request['opportunity_proof']['expected_preview_sha256']=change['sha256']
    event['fingerprint']=protocol_hash(dict(preparation_id=p['preparation_id'],action='ADOPT',**_adopt_request(Adopt.model_validate(request))))
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    assert plan_read(f,p).status_code == recover(f,p,key1).status_code == goal_results(f,p).status_code == 200
    for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
    old=deepcopy(stored(f,p));add_resource(f);_,graph=checked_graph(source_impact(f,p),p,old);assert_partition(graph,old,'resource_collection')
    second=preview(f,p,card).json();key2=uuid4().hex;response=adopt(f,p,second['adoption'],key2);assert response.status_code == 201,response.text
    for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
    now=stored(f,p);assert now['events'][:len(old['events'])] == old['events']
    changes=[e['local_revision']['source_change'] for e in now['events'] if e.get('local_revision',{}).get('source_change')]
    assert [x['version'] for x in changes] == [1,2] and 'source_impact' not in changes[0] and changes[1]['source_impact']['sha256'] == graph['sha256']
    assert recover(f,p,key1).json()['status'] == recover(f,p,key2).json()['status'] == 'COMMITTED'
    assert goal_results(f,p).json()['state'] == 'LOCAL_OUTPUTS_VERIFIED'


@pytest.mark.parametrize('source_first',[True,False])
def test_actual_v2_source_and_template_structure_both_orders(upgrade_case,source_first):
    original_u=upgrade_case
    app=create_isolated_template_app(original_u['f'][0],original_u['engine'],original_u['consumer'],original_u['checker'])
    with actual_http(app) as (client,traffic):
        f=(*original_u['f'][:3],client);u={**original_u,'f':f,'client':client}
        row,_,p=complete_declared(u);original=deepcopy(stored(f,p));key=uuid4().hex
        def source_revision():
            card=import_card(f,p);add_resource(f);current=stored(f,p)
            _,graph=checked_graph(source_impact(f,p),p,current);assert_partition(graph,current,'resource_collection')
            proposal=preview(f,p,card);assert proposal.status_code == 200,proposal.text;assert proposal.json()['can_adopt'],proposal.text
            response=adopt(f,p,proposal.json()['adoption'],key);assert response.status_code == 201,response.text
            assert stored(f,p)['events'][-1]['local_revision']['source_change']['version'] == 2
            for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
        def structure_revision():
            target=publication(u,SIX_GOALS,source='1',name='SYNTHETIC typed source independent structural strengthening')
            _,data=structural_admit(u,row,target);response=structural_apply(u,row,data);assert response.status_code == 200,response.text
            for adapter in ('P4','P5'):verified(f,p,adapter)
        if source_first:source_revision();structure_revision()
        else:structure_revision();source_revision()
        now=stored(f,p);assert now['id'] == original['id'] and now['required_goals'] == SIX_GOALS
        assert [s['id'] for s in now['steps']] == [s['id'] for s in original['steps']]
        assert now['events'][:len(original['events'])] == original['events']
        assert plan_read(f,p).status_code == 200 and recover(f,p,key).json()['status'] == 'COMMITTED'
        assert goal_results(f,p).json()['state'] == 'LOCAL_OUTPUTS_VERIFIED'
        assert traffic and all(row['path'].startswith('/api/') for row in traffic)
