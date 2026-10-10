"""Actual independent HTTP/PG failures for frozen ecf5; original fixture only."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json,pytest
from psycopg.types.json import Jsonb
from conftest import fixture,pg
from parkweave.api import create_app
from parkweave.resource_holds import RESOURCE_ID
from test_service_case_steps import preparation_fixture,receipt_fixture,link_fixture,read,adopt,adopt_body,setup,GOALS
from test_case_goal_results import complete,get,snapshot
from test_service_plan_manual_lock import stored
from test_service_plan_recovery import recover
from test_preparation import headers
from test_new_enterprise_local_chain import actual_http
OUT=Path('/workspace/ParkWeave/.runtime/independent-registered-local-revision-projection-final-review/negative-evidence')

@pytest.fixture
def real_f(link_fixture):
    with actual_http(create_app(link_fixture[0])) as (api,requests):yield (*link_fixture[:3],api)

def clone_existing_resource(f,n=1):
    ids=[]
    with f[1].connect() as c:
        for _ in range(n):
            id=uuid4();ids.append(id)
            c.execute('INSERT INTO synthetic_resources(id,park_id,name,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source) SELECT %s,park_id,%s,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source FROM synthetic_resources WHERE id=%s',(id,'SYNTHETIC independent existing resource clone',RESOURCE_ID))
            c.execute('INSERT INTO synthetic_resource_grants(principal_id,resource_id,park_id,org_id,capability,active) SELECT principal_id,%s,park_id,org_id,capability,active FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=%s',(id,'fixture-a',RESOURCE_ID))
    return ids

def patch(f,p):
    view=read(f,p).json();body=adopt_body(f,{**p,'revision':view['preparation_revision']});body.update(expected_plan_revision=view['revision'],local_revision=True,reason='SYNTHETIC independent explicit collection patch')
    response=adopt(f,p,body,uuid4().hex);assert response.status_code==201;return response.json()

def persist(f,p,plan):
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))

def evidence(name,data):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')

def test_one_corrupt_local_event_revision_all_views_must_refuse(real_f):
    f=real_f;p,*_=complete(f);clone_existing_resource(f);patch(f,p);plan=stored(f,p);old=deepcopy(plan['events'][-1]);assert old['action']=='ADOPT' and old['revision']>1
    plan['events'][-1]['revision']=old['revision']+7;persist(f,p,plan);before=snapshot(f)
    r=read(f,p);after_read=snapshot(f);rc=recover(f,p,old['request_key']);rg=get(f,p)
    evidence('structural-revision',dict(exact_sha='d12afaa6258dd89a539e3a859b965ca9441e2111',actual_http=True,pg=True,one_event_revision_changed=True,original_request_and_fingerprint_unchanged=True,ordinary_get_status=r.status_code,recovery_status=rc.status_code,goal_status=rg.status_code,ordinary_get_returned_corrupt_event=bool(r.status_code==200 and r.json()['events'][-1]['revision']==old['revision']+7),ordinary_get_rows_changed=before!=after_read,after_all_rows_changed=before!=snapshot(f)))
    assert (r.status_code,rc.status_code,rg.status_code)==(409,409,409) and snapshot(f)==before

def test_valid_uuid_partition_swap_is_not_original_impact_proof(real_f):
    f=real_f;p,*_=complete(f);clone_existing_resource(f);patch(f,p);plan=stored(f,p);original=deepcopy(plan['events'][-1]);partition=plan['events'][-1]['local_revision'];p1=plan['steps'][0]['id'];p2=plan['steps'][1]['id']
    assert p1 in partition['preserved'] and p2 in partition['affected']
    partition['affected']=[p1 if x==p2 else x for x in partition['affected']];partition['preserved']=[p2 if x==p1 else x for x in partition['preserved']]
    persist(f,p,plan);before=snapshot(f);r=read(f,p);rc=recover(f,p,original['request_key']);rg=get(f,p)
    evidence('valid-impact-swap',dict(exact_sha='d12afaa6258dd89a539e3a859b965ca9441e2111',actual_http=True,pg=True,only_affected_preserved_partition_changed=True,existing_step_uuid_partition_still_complete=True,original_request_fingerprint_and_manifests_unchanged=True,ordinary_get_status=r.status_code,recovery_status=rc.status_code,goal_status=rg.status_code,original_key_marked_committed=rc.status_code==200 and rc.json()['status']=='COMMITTED',all_business_rows_unchanged=snapshot(f)==before))
    assert (r.status_code,rc.status_code,rg.status_code)==(409,409,409) and snapshot(f)==before

def test_legitimate_old_overflow_now_known_requires_all_case_recheck(real_f):
    f=real_f;p=setup(f,GOALS[3]);clones=clone_existing_resource(f,130)
    response=adopt(f,p);assert response.status_code==201;plan=stored(f,p)
    assert plan['dependency_manifest']['collections']['resources']['known'] is False and plan['dependency_manifest']['collections']['resources']['count']==257
    # Remove only the own optional resource membership; original fixture permissions persist.
    with f[1].connect() as c:c.execute('DELETE FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=ANY(%s)',('fixture-a',clones))
    r=read(f,p);assert r.status_code==200;view=r.json();expected={s['id'] for s in plan['steps']};actual=set(view['change_impact']['affected']);before=snapshot(f)
    evidence('saved-unknown-now-known',dict(exact_sha='d12afaa6258dd89a539e3a859b965ca9441e2111',actual_http=True,pg=True,legitimate_initial_adopt_with_real_257_row_overflow=True,no_manifest_tamper_or_monkeypatch=True,saved_resources_known=False,current_preview_resources_known=view['current_preview']['dependency_collections']['resources']['known'],expected_affected_adapters=[s['adapter_id'] for s in plan['steps']],actual_affected_adapters=[s['adapter_id'] for s in plan['steps'] if s['id'] in actual],missed_invalidation=len(expected-actual),wrong_invalidation=len(actual-expected),unknown_scope=view['change_impact']['unknown_scope'],original_events_and_step_contracts_unchanged=stored(f,p)['events']==plan['events'] and [s['contract'] for s in stored(f,p)['steps']]==[s['contract'] for s in plan['steps']]))
    assert actual==expected and view['change_impact']['unknown_scope']=='THIS_CASE'
