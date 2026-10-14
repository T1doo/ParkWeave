"""Independent adverse oracles against actual owned PG and original API."""
from datetime import timedelta
from uuid import UUID,uuid4
import pytest
from psycopg.types.json import Jsonb
from test_service_selection_execution_preview import mapped_preview,body,execute,read
from test_service_selection_execution_preview import selection_full_chain,capability_catalog,receipt_fixture,preparation_fixture
from test_service_resource_change_replay import replay,prepare_changed,proposal_get
from test_service_selection_replay_acceptance import all_public_rows
from test_service_selection_full_chain import ok,GOALS
from test_preparation import headers


def test_review_preview_rehashed_mapping_cannot_fallback_or_create_artifact(mapped_preview):
    a=mapped_preview;f=a['f'];data=body(a)
    with f[1].connect() as c:
        row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(a['parent']['preparation_id'],)).fetchone()
        plan=row['service_case_plan']
        target=next(s for s in plan['steps'] if s['adapter_id']=='P2')
        target['contract']['instance_mappings'][0]['resources']['primary']=str(uuid4())
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),a['parent']['preparation_id']))
    before=all_public_rows(f[1]);artifact=a['engine'].path.read_bytes()
    assert execute(a,data).status_code==409
    assert a['engine'].path.read_bytes()==artifact
    assert all_public_rows(f[1])==before


def test_review_preview_unknown_key_is_readonly_even_with_executor_disabled(mapped_preview,monkeypatch):
    a=mapped_preview;f=a['f'];before=all_public_rows(f[1]);artifact=a['engine'].path.read_bytes()
    monkeypatch.setattr(a['engine'],'_run_artifact',lambda *args:pytest.fail('recovery attempted execution'))
    result=ok(read(a,uuid4().hex))
    assert result['status']=='NOT_OBSERVED' and result['automatically_replayed'] is False
    assert all_public_rows(f[1])==before and a['engine'].path.read_bytes()==artifact


def test_review_resource_recovery_actual_commit_cross_kind_and_subject(replay):
    r=replay;f=r['f'];owner=f[1];api=f[3];tokens=f[2]
    with owner.connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    key=uuid4().hex;rid=r['a']['b_resources'][0]
    created=ok(api.post('/api/synthetic-resources/'+rid+'/holds',headers=headers(tokens,'fixture-c',key),json=dict(starts_at=(now+timedelta(hours=9)).isoformat(),ends_at=(now+timedelta(hours=10)).isoformat(),quantity=1,expected_revision=1,ttl_seconds=300,purpose='SYNTHETIC independent lost response')),201)
    before=all_public_rows(owner)
    recovered=ok(api.get('/api/resource-holds/recovery/'+key,headers=headers(tokens,'fixture-c')))
    assert recovered['status']=='COMMITTED' and recovered['hold']['id']==created['hold']['id']
    assert recovered['actor_ref']=='fixture-c' and recovered['request_key']==key
    assert all_public_rows(owner)==before
    assert api.get('/api/resource-combinations/recovery/'+key,headers=headers(tokens,'fixture-c')).status_code==409
    wrong=ok(api.get('/api/resource-holds/recovery/'+key,headers=headers(tokens,'fixture-a')))
    assert wrong['status']=='NOT_OBSERVED' and 'hold' not in wrong and 'receipt' not in wrong
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s',('fixture-c',key)).fetchone()['n']==1


def test_review_proposal_capacity_change_invalidates_original_source_without_writes(replay):
    r=replay;f=r['f'];p,_,_=prepare_changed(r,'INDEPENDENT-C-CAPACITY')
    with f[1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    params=dict(search_from=(now+timedelta(hours=5)).isoformat(),search_until=(now+timedelta(hours=6)).isoformat())
    first=ok(proposal_get(r,p,**params));assert first['state']=='AVAILABLE' and first['required_goals']==GOALS
    member=first['items'][0]['members'][0]
    body={k:member[k] for k in ('starts_at','ends_at','quantity','expected_revision')};body.update(ttl_seconds=300,purpose='SYNTHETIC independent competing claim')
    ok(f[3].post('/api/synthetic-resources/'+member['resource_id']+'/holds',headers=headers(f[2],'fixture-c',uuid4().hex),json=body),201)
    before=all_public_rows(f[1]);second=ok(proposal_get(r,p,**params))
    assert second['state']=='NO_SOLUTION' and second['items']==[]
    assert second['source_sha256']!=first['source_sha256']
    assert second['required_goals']==GOALS and all_public_rows(f[1])==before


def test_review_removed_v4_markers_cannot_attempt_legacy_fixed_resources(mapped_preview,monkeypatch):
    from parkweave import resource_holds as rh
    a=mapped_preview;f=a['f'];data=body(a)
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(a['parent']['preparation_id'],)).fetchone()['service_case_plan']
        plan['adoption_preview'].pop('profile',None)
        plan['binding'].pop('service_selection',None)
        plan.pop('candidate_consumption',None)
        for field in ('candidate_id','expected_candidate_sha256','expected_verification_sha256'):
            plan['adoption_request'].pop(field,None)
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),a['parent']['preparation_id']))
    attempted=[];original=rh._scope
    def track(c,p,id,*args,**kwargs):
        attempted.append(str(id));return original(c,p,id,*args,**kwargs)
    monkeypatch.setattr(rh,'_scope',track)
    saved=a['engine'].path.read_bytes()
    reply=execute(a,data)
    assert reply.status_code==409
    assert str(rh.RESOURCE_ID) not in attempted
    assert a['engine'].path.read_bytes()==saved


def test_review_old_revision_confirmed_occupancy_still_consumes_capacity_after_replacement(replay):
    from test_service_resource_change_replay import test_second_park_actual_rule_revision_explicit_patch_keeps_old_occupancy as execute_original_chain
    execute_original_chain(replay)
    f=replay['f'];before=all_public_rows(f[1])
    for rid in replay['a']['b_resources']:
        with f[1].connect() as c:
            old=c.execute('SELECT * FROM synthetic_resource_holds WHERE resource_id=%s AND resource_revision=1',(rid,)).fetchone()
        preview=ok(f[3].post('/api/synthetic-resources/'+rid+'/preview',headers=headers(f[2],'fixture-c'),json=dict(starts_at=old['starts_at'].isoformat(),ends_at=old['ends_at'].isoformat(),quantity=1)))
        assert preview['occupied_peak']==2 and preview['available'] is False
        assert old['state']=='CONFIRMED'
    assert all_public_rows(f[1])==before
