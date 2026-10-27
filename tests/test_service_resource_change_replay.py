"""Owned PG: V4 resource change, explicit replacement and original output rechecks."""
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4
from test_preparation import headers, preparation_fixture
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain, GOALS, ok, verify
from test_service_selection_replay_acceptance import replay, new_confirmed_parent, adopt_selection, execute_to_receipt, result
from test_case_lifecycle import read as local_read, act as local_command


def test_original_v4_same_resource_time_replacement_bridge(replay):
    r=replay;f=r['f'];store,owner,tokens,api=f
    p,_=new_confirmed_parent(r,'AT33-C-CHANGE');adopt_selection(r,p)
    group,dispatch,receipt=execute_to_receipt(r,p,'AT33-C-CHANGE',3)
    path='/api/preparations/'+p['preparation_id']
    assert result(r,p)['state']=='LOCAL_OUTPUTS_VERIFIED'
    ok(api.post('/api/resource-combinations/'+group['id']+'/cancel',headers=headers(tokens,'fixture-c',uuid4().hex),json={}))
    assert result(r,p)['state']!='LOCAL_OUTPUTS_VERIFIED'
    with owner.connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    body=dict(starts_at=(now+timedelta(hours=5)).isoformat(),ends_at=(now+timedelta(hours=6)).isoformat(),quantity=2,expected_revision=1,ttl_seconds=300,purpose='SYNTHETIC explicit replacement time')
    holds=[ok(api.post('/api/synthetic-resources/'+rid+'/holds',headers=headers(tokens,'fixture-c',uuid4().hex),json=body),201)['hold'] for rid in r['a']['b_resources']]
    new=ok(api.post('/api/resource-combinations',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds])),201)['combination']
    proposal=ok(api.get(path+'/resource-plan-binding',params=dict(candidate_combination_id=new['id']),headers=headers(tokens,'fixture-c')))
    assert proposal['comparison']['can_confirm'],str(proposal['comparison'])
    ok(api.post(path+'/resource-plan-binding/confirm',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(combination_id=new['id'],expected_preparation_revision=p['revision'],expected_link_revision=1,expected_comparison_sha256=proposal['comparison']['sha256'],reason='SYNTHETIC owner explicitly accepts replacement time')),201)
    for adapter in ('P2','P3','P4'):verify(f,p,adapter)
    ok(local_command(f,p,ok(local_read(f,p,user='fixture-c')),'REVALIDATE',user='fixture-c'));verify(f,p,'P5')
    final=result(r,p)
    assert final['state']=='LOCAL_OUTPUTS_VERIFIED' and final['adopted_goals']==GOALS


def prepare_changed(r, marker='AT33-C-PROPOSAL'):
    f=r['f'];p,_=new_confirmed_parent(r,marker);adopt_selection(r,p)
    group,dispatch,receipt=execute_to_receipt(r,p,marker,3)
    old=result(r,p)
    ok(f[3].post('/api/resource-combinations/'+group['id']+'/cancel',headers=headers(f[2],'fixture-c',uuid4().hex),json={}))
    return p,group,old


def proposal_get(r,p,**override):
    with r['f'][1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    params=dict(search_from=(now+timedelta(hours=5)).isoformat(),search_until=(now+timedelta(hours=8)).isoformat());params.update(override)
    return r['f'][3].get('/api/preparations/'+p['preparation_id']+'/resource-time-alternatives',params=params,headers=headers(r['f'][2],'fixture-c'))


def test_case_proposal_original_explicit_slot_loop_and_get_only_recovery(replay):
    from copy import deepcopy
    from service_release_acceptance_support import case_history, authority_snapshot
    from test_service_selection_replay_acceptance import all_public_rows
    r=replay;f=r['f'];store,owner,tokens,api=f
    a,_=new_confirmed_parent(r,'AT33-C-PRESERVE');adopt_selection(r,a);execute_to_receipt(r,a,'AT33-C-PRESERVE',1)
    kept=case_history(owner,a['preparation_id']);kept_result=result(r,a)
    p,old_group,old_result=prepare_changed(r)
    path='/api/preparations/'+p['preparation_id'];authority=authority_snapshot(owner)
    before=all_public_rows(owner)
    proposal=ok(proposal_get(r,p));assert all_public_rows(owner)==before
    assert proposal['state']=='AVAILABLE' and proposal['required_goals']==GOALS
    assert proposal['current_issues'] and not proposal['old_occupancy_released']
    assert proposal['items'] and proposal['business_writes'] is False
    slot=proposal['items'][0];assert slot['starts_at']!=old_group['members'][0]['starts_at']
    # No original write or replacement occurs merely by choosing an option.
    assert all_public_rows(owner)==before
    holds=[];keys=[]
    for member in slot['members']:
        key=uuid4().hex;keys.append(key)
        body={k:member[k] for k in ('starts_at','ends_at','quantity','expected_revision')}
        body.update(ttl_seconds=300,purpose='SYNTHETIC owner explicitly chose proposed replacement slot')
        reply=ok(api.post('/api/synthetic-resources/'+member['resource_id']+'/holds',headers=headers(tokens,'fixture-c',key),json=body),201)
        # Treat POST response as lost: recovery may only GET its exact key.
        recovered=ok(api.get('/api/resource-holds/recovery/'+key,headers=headers(tokens,'fixture-c')))
        assert recovered['status']=='COMMITTED' and recovered['hold']['id']==reply['hold']['id']
        assert recovered['automatically_replayed'] is False
        assert api.get('/api/resource-holds/recovery/'+key,params=dict(expected_fingerprint='0'*64),headers=headers(tokens,'fixture-c')).status_code==409
        holds.append(recovered['hold'])
    group_key=uuid4().hex
    body=dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds])
    group=ok(api.post('/api/resource-combinations',headers=headers(tokens,'fixture-c',group_key),json=body),201)['combination']
    recovered=ok(api.get('/api/resource-combinations/recovery/'+group_key,headers=headers(tokens,'fixture-c')))
    assert recovered['status']=='COMMITTED' and recovered['combination']==group
    compare=ok(api.get(path+'/resource-plan-binding',params=dict(candidate_combination_id=group['id']),headers=headers(tokens,'fixture-c')))
    assert compare['comparison']['can_confirm']
    exact=dict(combination_id=group['id'],expected_preparation_revision=p['revision'],expected_link_revision=1,expected_comparison_sha256=compare['comparison']['sha256'],reason='SYNTHETIC owner confirms actual replacement comparison')
    bad=deepcopy(exact);bad['expected_comparison_sha256']='0'*64
    assert api.post(path+'/resource-plan-binding/confirm',headers=headers(tokens,'fixture-c',uuid4().hex),json=bad).status_code==409
    link_key=uuid4().hex
    linked=ok(api.post(path+'/resource-plan-binding/confirm',headers=headers(tokens,'fixture-c',link_key),json=exact),201)
    recovered=ok(api.get(path+'/resource-link/recovery/'+link_key,headers=headers(tokens,'fixture-c')))
    assert recovered['status']=='COMMITTED' and recovered['record']==linked['event']
    assert recovered['record']['revision']==2
    # The immutable first association and original selected proof remain visible.
    assert linked['history'][0]['record']['combination_id']==old_group['id']
    assert linked['history'][1]['record']['combination_id']==group['id']
    impacted=result(r,p);assert impacted['state']!='LOCAL_OUTPUTS_VERIFIED'
    for adapter in ('P2','P3','P4'):verify(f,p,adapter)
    ok(local_command(f,p,ok(local_read(f,p,user='fixture-c')),'REVALIDATE',user='fixture-c'));verify(f,p,'P5')
    final=result(r,p)
    assert final['state']=='LOCAL_OUTPUTS_VERIFIED' and final['adopted_goals']==GOALS
    assert [row['goal'] for row in final['results']]==GOALS
    assert case_history(owner,a['preparation_id'])==kept and result(r,a)==kept_result
    assert authority_snapshot(owner)==authority and len(r['calls'])==2
    assert all(x['state']=='CANCELLED' for x in [ok(api.get('/api/resource-combinations/'+old_group['id'],headers=headers(tokens,'fixture-c')))['combination']])
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',('fixture-c',group_key)).fetchone()['n']==1
        assert c.execute('SELECT count(*) n FROM case_resource_links WHERE actor_id=%s AND request_key=%s',('fixture-c',link_key)).fetchone()['n']==1
        for key in keys:assert c.execute('SELECT count(*) n FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s',('fixture-c',key)).fetchone()['n']==1
    for url in ('/api/resource-holds/recovery/'+uuid4().hex,'/api/resource-combinations/recovery/'+uuid4().hex,path+'/resource-link/recovery/'+uuid4().hex):
        unknown=ok(api.get(url,headers=headers(tokens,'fixture-c')))
        assert unknown['status']=='NOT_OBSERVED' and unknown['not_observed_does_not_prove_uncommitted']


def test_proposal_capacity_and_buffer_oracle_no_hidden_fallback(replay):
    from test_service_selection_replay_acceptance import all_public_rows
    r=replay;f=r['f'];p,_,_=prepare_changed(r,'AT33-C-CAPACITY');api=f[3];tokens=f[2]
    with f[1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    start=(now+timedelta(hours=5)).isoformat();end=(now+timedelta(hours=6)).isoformat()
    params=dict(search_from=start,search_until=end)
    first=ok(proposal_get(r,p,**params));assert first['state']=='AVAILABLE' and len(first['items'])==1
    rid=first['items'][0]['members'][0]['resource_id']
    held=ok(api.post('/api/synthetic-resources/'+rid+'/holds',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(starts_at=start,ends_at=end,quantity=2,expected_revision=1,ttl_seconds=300,purpose='SYNTHETIC competing owner reservation')),201)['hold']
    before=all_public_rows(f[1]);second=ok(proposal_get(r,p,**params));assert all_public_rows(f[1])==before
    assert second['state']=='NO_SOLUTION' and second['items']==[] and second['available_candidates']==0
    assert second['source_sha256']!=first['source_sha256']
    # Even a slot ending exactly at the other hold's start conflicts with its
    # original five-minute buffers; no unbuffered fallback is manufactured.
    buffered=ok(proposal_get(r,p,search_from=(now+timedelta(hours=4)).isoformat(),search_until=start))
    assert buffered['state']=='NO_SOLUTION' and buffered['items']==[]
    ok(api.post('/api/resource-holds/'+held['id']+'/release',headers=headers(tokens,'fixture-c',uuid4().hex),json={}))
    third=ok(proposal_get(r,p,**params));assert third['state']=='AVAILABLE'


import pytest


@pytest.mark.parametrize('cap',['EXECUTE','HOLD','READ','PREPARE'])
def test_current_permissions_and_historical_recovery_are_separate(replay,cap):
    from test_service_selection_replay_acceptance import all_public_rows
    r=replay;f=r['f'];p,group,_=prepare_changed(r,'AT33-C-REVOKE-'+cap)
    # The original cancel key is a real completed operation whose reply could
    # have been lost, and remains readable after write authority is revoked.
    with f[1].connect() as c:
        key=c.execute("SELECT request_key FROM synthetic_resource_combination_receipts WHERE combination_id=%s AND action='CANCEL'",(group['id'],)).fetchone()['request_key']
        f[1].lock_principal(c,'fixture-c',exclusive=True)
        if cap=='HOLD':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-c' AND capability='HOLD'")
        elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-c' AND capability='PREPARE'")
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-c' AND capability=%s",(cap,))
    before=all_public_rows(f[1]);response=proposal_get(r,p)
    if cap in ('READ','PREPARE'):assert response.status_code==403
    else:
        data=ok(response);assert data['state']=='BLOCKED' and data['items']==[]
        assert ('OWNER_EXECUTE_REQUIRED' if cap=='EXECUTE' else 'RESOURCE_HOLD_PERMISSION_REQUIRED') in data['blockers']
        assert all_public_rows(f[1])==before
    recovered=f[3].get('/api/resource-combinations/recovery/'+key,headers=headers(f[2],'fixture-c'))
    if cap=='READ':assert recovered.status_code==403
    else:assert ok(recovered)['status']=='COMMITTED'


@pytest.mark.parametrize('actor',['fixture-a','fixture-b','prep-specialist-fixture-c','executor-c'])
def test_proposal_cross_scope_and_role_refused(replay,actor):
    r=replay;f=r['f'];p,_,_=prepare_changed(r,'AT33-C-SCOPE')
    with f[1].connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    response=f[3].get('/api/preparations/'+p['preparation_id']+'/resource-time-alternatives',params=dict(search_from=(now+timedelta(hours=5)).isoformat(),search_until=(now+timedelta(hours=8)).isoformat()),headers=headers(f[2],actor))
    assert response.status_code==403


@pytest.mark.parametrize('params',[
    dict(search_from='not-date',search_until='also-invalid'),
    dict(search_from='2027-01-01T01:00:00',search_until='2027-01-01T02:00:00'),
    dict(search_from='2027-01-01T01:00:00Z',search_until='2027-01-01T00:00:00Z'),
    dict(search_from='2027-01-01T01:00:00Z',search_until='2027-01-03T01:00:00Z')])
def test_invalid_time_windows_never_become_advice(replay,params):
    r=replay;f=r['f'];p,_=new_confirmed_parent(r,'AT33-C-INVALID')
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/resource-time-alternatives',params=params,headers=headers(f[2],'fixture-c')).status_code==422
    assert r['calls']==[]


def test_original_hold_lock_wait_commit_then_key_get_without_repost(replay):
    from concurrent.futures import ThreadPoolExecutor
    from time import monotonic, sleep
    from parkweave import resource_holds as rh
    r=replay;f=r['f'];store,owner,tokens,api=f
    rid=r['a']['b_resources'][0]
    with owner.connect() as c:now=c.execute('SELECT clock_timestamp() t').fetchone()['t']
    key=uuid4().hex;body=dict(starts_at=(now+timedelta(hours=7)).isoformat(),ends_at=(now+timedelta(hours=8)).isoformat(),quantity=2,expected_revision=1,ttl_seconds=300,purpose='SYNTHETIC actual PG waiter request')
    with ThreadPoolExecutor(max_workers=2) as pool:
        with owner.connect() as lock:
            rh._lock(lock,rid)
            sent=pool.submit(api.post,'/api/synthetic-resources/'+rid+'/holds',headers=headers(tokens,'fixture-c',key),json=body)
            deadline=monotonic()+2
            observed=False
            while monotonic()<deadline:
                with owner.connect() as c:
                    observed=bool(c.execute("SELECT 1 FROM pg_locks WHERE locktype='advisory' AND NOT granted LIMIT 1").fetchone())
                if observed:break
                sleep(.01)
            assert observed,'real PG advisory lock waiter must be observed'
            recovered=pool.submit(api.get,'/api/resource-holds/recovery/'+key,headers=headers(tokens,'fixture-c'))
            assert not sent.done()
        reply=ok(sent.result(timeout=4),201)
        read=ok(recovered.result(timeout=4));assert read['status']=='COMMITTED'
        assert read['hold']['id']==reply['hold']['id'] and not read['automatically_replayed']
    # A second body under the same key remains an original command conflict.
    changed=dict(body,purpose='SYNTHETIC different body must conflict')
    assert api.post('/api/synthetic-resources/'+rid+'/holds',headers=headers(tokens,'fixture-c',key),json=changed).status_code==409
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s',('fixture-c',key)).fetchone()['n']==1
    other=ok(api.get('/api/resource-holds/recovery/'+key,headers=headers(tokens,'fixture-a')))
    assert other['status']=='NOT_OBSERVED' and 'hold' not in other


def test_second_park_actual_rule_revision_explicit_patch_keeps_old_occupancy(replay):
    from copy import deepcopy
    from parkweave import resource_holds as rh
    from service_release_acceptance_support import case_history, authority_snapshot
    from test_case_goal_results import complete as complete_original_A
    from test_service_selection_replay_acceptance import all_public_rows
    r=replay;f=r['f'];store,owner,tokens,api=f
    a,_,_,_=complete_original_A(f,local=True)
    a_path='/api/preparations/'+a['preparation_id']
    keep=case_history(owner,a['preparation_id'])
    a_result=ok(api.get(a_path+'/goal-results',headers=headers(tokens,'fixture-a')))
    p,_=new_confirmed_parent(r,'AT33-C-ACTUAL-RULE');adopt_selection(r,p)
    old_group,_,_=execute_to_receipt(r,p,'AT33-C-ACTUAL-RULE',3)
    path='/api/preparations/'+p['preparation_id']
    verified=result(r,p);assert verified['state']=='LOCAL_OUTPUTS_VERIFIED'
    with owner.connect() as c:
        saved=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'])
        # Explicit owned fixture resource administrator change, not an app
        # publisher/new Grant. Original lock protocol and source history apply.
        for rid in sorted(r['a']['b_resources']):
            rh._lock(c,rid)
            c.execute('UPDATE synthetic_resources SET revision=revision+1,buffer_seconds=buffer_seconds+60 WHERE id=%s',(rid,))
    authority=authority_snapshot(owner)
    before=all_public_rows(owner)
    affected=ok(api.get(path+'/service-case-plan',headers=headers(tokens,'fixture-c')))
    assert all_public_rows(owner)==before,'V4 changed-source history GET must not persist invalidation'
    expected_changed={s['id'] for s in saved['steps'] if s['adapter_id'] in ('P2','P3','P4','P5')}
    expected_kept={s['id'] for s in saved['steps'] if s['adapter_id']=='P1'}
    assert set(affected['change_impact']['affected'])==expected_changed
    assert set(affected['change_impact']['preserved'])==expected_kept
    proposed=ok(proposal_get(r,p))
    assert proposed['state']=='BLOCKED' and 'DEPENDENCY_REVISION_REQUIRES_EXPLICIT_ADOPT' in proposed['blockers']
    assert result(r,p)['state']!='LOCAL_OUTPUTS_VERIFIED'
    preview=affected['current_preview']
    patch=dict(expected_preparation_revision=p['revision'],expected_request_revision=preview['request_revision'],expected_plan_revision=affected['revision'],expected_source_sha256=preview['source_sha256'],required_goals=GOALS,local_revision=True,reason='SYNTHETIC owner explicitly accepts resource rule revision impact')
    adopted=ok(api.post(path+'/service-case-plan',headers=headers(tokens,'fixture-c',uuid4().hex),json=patch),201)
    assert adopted['plan_id']==affected['plan_id']
    with owner.connect() as c:
        patched=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
    assert patched['steps'][0]==saved['steps'][0]
    assert patched['binding']==saved['binding'] and patched['candidate_consumption']==saved['candidate_consumption']
    assert patched['events'][:-1]==saved['events'] and patched['history']==saved['history']
    proposal=ok(proposal_get(r,p));assert proposal['state']=='AVAILABLE'
    choice=proposal['items'][0];holds=[]
    for member in choice['members']:
        assert member['expected_revision']==2 and member['buffer_seconds']==360
        body={k:member[k] for k in ('starts_at','ends_at','quantity','expected_revision')}
        body.update(ttl_seconds=300,purpose='SYNTHETIC owner chooses revised-rule replacement')
        holds.append(ok(api.post('/api/synthetic-resources/'+member['resource_id']+'/holds',headers=headers(tokens,'fixture-c',uuid4().hex),json=body),201)['hold'])
    group=ok(api.post('/api/resource-combinations',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(members=[dict(hold_id=h['id'],expected_revision=2) for h in holds])),201)['combination']
    comparison=ok(api.get(path+'/resource-plan-binding',params=dict(candidate_combination_id=group['id']),headers=headers(tokens,'fixture-c')))
    assert comparison['comparison']['can_confirm']
    linked=ok(api.post(path+'/resource-plan-binding/confirm',headers=headers(tokens,'fixture-c',uuid4().hex),json=dict(combination_id=group['id'],expected_preparation_revision=p['revision'],expected_link_revision=1,expected_comparison_sha256=comparison['comparison']['sha256'],reason='SYNTHETIC explicit same-resource replacement after actual rule change')),201)
    assert linked['history'][0]['record']['combination_id']==old_group['id']
    assert linked['history'][0]['combination']['state']=='CONFIRMED'
    for adapter in ('P2','P3','P4'):verify(f,p,adapter)
    ok(local_command(f,p,ok(local_read(f,p,user='fixture-c')),'REVALIDATE',user='fixture-c'));verify(f,p,'P5')
    final=result(r,p);assert final['state']=='LOCAL_OUTPUTS_VERIFIED' and final['adopted_goals']==GOALS
    # Independent final DB and original GET prove the new reservation while
    # the old confirmed occupancy remains; replacement never releases it.
    with owner.connect() as c:
        old=c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(old_group['id'],)).fetchone()
        assert old['state']=='CONFIRMED'
        for rid in r['a']['b_resources']:
            rows=c.execute("SELECT resource_revision,state FROM synthetic_resource_holds WHERE resource_id=%s ORDER BY resource_revision",(rid,)).fetchall()
            assert [(h['resource_revision'],h['state']) for h in rows]==[(1,'CONFIRMED'),(2,'CONFIRMED')]
        assert c.execute('SELECT count(*) n FROM case_resource_links WHERE case_id=%s',(p['case_id'],)).fetchone()['n']==2
    assert authority_snapshot(owner)==authority and len(r['calls'])==1
    assert case_history(owner,a['preparation_id'])==keep
    assert ok(api.get(a_path+'/goal-results',headers=headers(tokens,'fixture-a')))==a_result
    actual={row['adapter_id']:row['actual_output'] for row in final['results']}
    assert actual['P2']['combination_id']==group['id']
    assert actual['P2']['resource_link_revision']==2
    evidence=dict(scope='OWNED_SYNTHETIC_SECOND_PARK_RESOURCE_RULE_CHANGE_REPLAY',
        case_id=p['case_id'],park_id='park-b',required_goals=GOALS,
        should_update=['P2','P3','P4','P5'],should_preserve=['P1'],
        resource_revisions=dict(before=1,after=2),buffer_seconds=dict(before=300,after=360),
        old_combination_id=old_group['id'],new_combination_id=group['id'],
        old_combination_still_confirmed=True,old_occupancy_automatically_released=False,
        original_v4_proof_unchanged=True,original_plan_id_unchanged=True,
        original_A_history_and_results_unchanged=True,explicit_local_adopt=True,
        explicit_original_actions=['HOLD','COMBINATION_CONFIRM','RESOURCE_BINDING_COMPARISON_CONFIRM'],
        actual_reverified=['P2','P3','P4','P5'],offline_model_calls=1,real_model_calls=0,
        runtime_authority_rows_changed=0,new_runtime_grants=0,case_goal_completed=False)
    out=Path('.runtime/resource-change-20261014/actual-rule-outcome.json')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(evidence,indent=2)+'\n')


@pytest.mark.parametrize('damage',['goal','candidate','verify_event','step_claim'])
def test_tampered_original_v4_proofs_never_authorize_alternative(replay,damage):
    from psycopg.types.json import Jsonb
    from test_service_selection_replay_acceptance import all_public_rows
    r=replay;f=r['f'];p,_,_=prepare_changed(r,'AT33-C-TAMPER')
    with f[1].connect() as c:
        plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        if damage=='goal':plan['required_goals']=plan['required_goals'][:-1]
        elif damage=='candidate':plan['candidate_consumption']['candidate_sha256']='0'*64
        elif damage=='verify_event':next(e for e in plan['events'] if e['action']=='VERIFY')['fingerprint']='0'*64
        else:plan['steps'][0]['verified_sources']['service_version']=999
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=all_public_rows(f[1]);response=proposal_get(r,p)
    if damage=='step_claim':
        doc=ok(response);assert doc['state']=='BLOCKED' and doc['items']==[]
    else:assert response.status_code==409,response.text
    assert all_public_rows(f[1])==before
