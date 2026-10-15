"""Actual HTTP/PG, with a labeled future-reader graph-header-only negative seam."""
from copy import deepcopy
import hashlib,json,subprocess
from pathlib import Path
import pytest
from conftest import pg,fixture
from parkweave.api import create_app
from parkweave import typed_source_impact as typed
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture,headers
from test_case_goal_results import complete,snapshot
from test_service_plan_manual_lock import stored
from test_new_enterprise_local_chain import actual_http

OUT=Path('/workspace/ParkWeave/.runtime/shared-source-cases-review')
SHA='bc4f384fa32817ddf3b332f898d59b5b994bfe2f'

@pytest.fixture
def actual_owned_case(link_fixture):
    with actual_http(create_app(link_fixture[0])) as (client,traffic):
        yield (*link_fixture[:3],client),traffic

@pytest.mark.parametrize('label,schema',[('future_integer',2),('boolean_is_not_one',True),('missing_schema',None)])
def test_unknown_graph_header_never_uses_schema_one_facets_or_authorizes(actual_owned_case,monkeypatch,label,schema):
    f,traffic=actual_owned_case
    p,_,_,_=complete(f,local=True);original=deepcopy(stored(f,p));before=snapshot(f);start=len(traffic)
    original_reader=typed.read
    def future_reader(*args,**kwargs):
        view=original_reader(*args,**kwargs)
        # All current owner/source/history checks above ran on actual PG. Only
        # the future current-reader's graph envelope is a deliberate seam. No
        # schema1 node/edge/hash fields remain for the reverse reader to use.
        return {**view,'source_impact':{} if label=='missing_schema' else {'schema':schema}}
    monkeypatch.setattr(typed,'read',future_reader)
    response=f[3].get('/api/preparations/'+p['preparation_id']+'/shared-source-cases',headers=headers(f[2]),params={'source_kind':'OWNER_RESOURCE_QUERY_SET'})
    assert response.status_code==200,response.text
    value=response.json();rows=value['items'];assert len(rows)==1
    row=rows[0];expected=[step['id'] for step in original['steps']]
    assert len(expected)==5 and row['affected']==expected and row['preserved']==[]
    assert value['projection_schema']==1 and value['source_ref']['available'] is True
    assert value['state']=='UNKNOWN' and value['unknown_scope']=='CURRENT_OWNER_CASE_SET' and not value['all_cases_checked']
    assert row['state']=='UNKNOWN' and row['relationship']=='UNKNOWN' and row['source_changed'] is None
    assert row['blocking_reasons']==['SHARED_SOURCE_GRAPH_SCHEMA_UNSUPPORTED']
    assert row['source_impact_schema']==(2 if label=='future_integer' else None) and row['source_impact_sha256'] is None
    assert stored(f,p)==original and snapshot(f)==before
    requests=traffic[start:];assert requests and all(r['method']=='GET' for r in requests)
    record={'scope':'ACTUAL_HTTP_ASGI_OWNED_PG_FUTURE_READER_GRAPH_HEADER_SEAM','source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scenario':label,'expected_affected':expected,'actual_affected':row['affected'],'expected_preserved':[],'actual_preserved':row['preserved'],'missed':len(set(expected)-set(row['affected'])),'wrong':len(set(row['affected'])-set(expected)),'state':row['state'],'schema_exposed':row['source_impact_schema'],'source_query_available':value['source_ref']['available'],'case_history_and_business_unchanged':True,'request_count':len(requests),'methods':sorted({r['method'] for r in requests}),'known_steps_conservatively_all_affected':True,'schema_one_facets_or_hash_used':False,'seam':'Future reader envelope only; original typed reader executed actual scope/proofs/source reads first','no_real_browser_or_models':True}
    assert record['source_sha']==SHA
    (OUT/('schema-'+label+'.json')).write_text(json.dumps(record,indent=2)+'\n')
