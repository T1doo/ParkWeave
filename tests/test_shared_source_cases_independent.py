"""Independent literal shared-source answers through actual HTTP/owned PostgreSQL.

No product impact/closure/compiler constructs the expected Case or step sets.
Administrator mutations below are explicit synthetic external-source/denial seams.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from parkweave.api import create_app
from parkweave.domain import Intake
from parkweave.resource_holds import RESOURCE_ID
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers, create, command as prep_command, add as material_add
from test_case_goal_results import complete, snapshot
from test_service_case_steps import setup, GOALS, verified
from test_service_plan_manual_lock import stored, lock
from test_registered_local_revision import add_resource
from test_source_change_adoption import adopt
from test_new_enterprise_local_chain import actual_http, fresh_chain, publish, new_case, enable_approval, finish_chain

OUT = Path('.runtime/shared-source-cases-independent')
RUN_ID = uuid4().hex
RESOURCE = 'OWNER_RESOURCE_QUERY_SET'
CATALOG = 'SERVICE_CATALOG_REFERENCE'


@pytest.fixture
def shared_http(link_fixture):
    with actual_http(create_app(link_fixture[0])) as (client, traffic):
        yield (*link_fixture[:3], client), traffic


def lookup(f, p, source=RESOURCE, actor='fixture-a', **params):
    return f[3].get('/api/preparations/' + p['preparation_id'] + '/shared-source-cases',
                    headers=headers(f[2], actor), params={'source_kind': source, **params})


def checked(response, p, source=RESOURCE):
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['scope'] == 'CURRENT_OWNER_SHARED_SOURCE_CASES'
    assert (value['preparation_id'], value['case_id'], value['run_id']) == (p['preparation_id'], p['case_id'], p['run_id'])
    assert value['read_only'] and not value['automatically_replayed']
    assert not value['new_grants'] and not value['automatic_execution'] and not value['case_goal_completed']
    assert value['source_kind'] == value['source_ref']['kind'] == source
    for field in ('scope_sha256', 'source_sha256', 'source_epoch_sha256'):
        assert len(value['source_ref'][field]) == 64
    assert value['candidate_limit'] == 32 and len(value['items']) <= value['page_limit'] <= 20
    assert value['has_more'] == (value['next_cursor'] is not None)
    assert len({row['case_id'] for row in value['items']}) == len(value['items'])
    raw = json.dumps(value)
    assert 'PRIVATE_' not in raw and 'current_materials' not in raw and 'verified_sources' not in raw
    return value


def expect(row, original, affected, preserved, *, state, relationship, scenario):
    ids = {s['adapter_id']: s['id'] for s in original['steps']} if original else {}
    want_a = {ids[s] for s in affected}; want_p = {ids[s] for s in preserved}
    got_a = set(row['affected']); got_p = set(row['preserved'])
    record = dict(run_id=RUN_ID, test=os.environ.get('PYTEST_CURRENT_TEST'),
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        scenario=scenario, case_id=row['case_id'], expected_affected=sorted(want_a), actual_affected=sorted(got_a),
        expected_preserved=sorted(want_p), actual_preserved=sorted(got_p),
        expected_state=state, actual_state=row['state'], expected_relationship=relationship, actual_relationship=row['relationship'],
        missed_count=len(want_a-got_a), wrong_count=len(got_a-want_a), wrong_preserved_count=len(want_p^got_p),
        intentional_unknown=state in ('UNKNOWN', 'NO_PLAN', 'NO_PREPARATION'))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / ('oracle-' + RUN_ID + '.jsonl')).open('a') as stream:
        stream.write(json.dumps(record, sort_keys=True) + '\n')
    assert got_a == want_a and got_p == want_p, record
    assert row['state'] == state and row['relationship'] == relationship, record


def no_preparation(f, user='fixture-a'):
    run = f[0].submit(f[2][user], uuid4().hex, Intake(goal='SYNTHETIC PRIVATE_SHARED_UNPREPARED'))
    work = f[0].claim('independent-shared-unprepared'); assert work and str(work['id']) == run
    f[0].finish(work)
    with f[1].connect() as c:
        return dict(c.execute('SELECT id AS case_id,run_id FROM cases WHERE run_id=%s', (run,)).fetchone())


def one_step(f):
    p = setup(f, GOALS[0]); assert adopt(f, p).status_code == 201; verified(f, p, 'P1')
    return p


def by_case(value):
    return {row['case_id']: row for row in value['items']}


def test_resource_reverse_literal_multiple_cases_no_plan_and_unrelated_read_only(shared_http):
    f, _ = shared_http
    p, _, _, _ = complete(f, local=True); q, _, _, _ = complete(f, local=True)
    r = one_step(f); n = create(f)[0]; u = no_preparation(f)
    foreign = [create(f, user)[0] for user in ('fixture-b', 'fixture-c')]
    originals = {x['case_id']: deepcopy(stored(f, x)) for x in (p, q, r)}
    add_resource(f); before = snapshot(f)
    value = checked(lookup(f, p), p); rows = by_case(value)
    assert set(rows) == {x['case_id'] for x in (p, q, r, n)} | {str(u['case_id'])}
    assert all(x['case_id'] not in rows for x in foreign)
    for x in (p, q):
        expect(rows[x['case_id']], originals[x['case_id']], ('P2','P3','P4','P5'), ('P1',), state='CHANGED', relationship='SHARED_SOURCE', scenario='resource_multi')
    expect(rows[r['case_id']], originals[r['case_id']], (), ('P1',), state='NOT_DEPENDENT', relationship='NOT_DEPENDENT', scenario='p1_does_not_read_resources')
    expect(rows[n['case_id']], None, (), (), state='NO_PLAN', relationship='UNKNOWN', scenario='no_plan')
    expect(rows[str(u['case_id'])], None, (), (), state='NO_PREPARATION', relationship='UNKNOWN', scenario='no_preparation')
    assert value['unknown_scope'] == 'CURRENT_OWNER_CASE_SET' and not value['all_cases_checked']
    assert snapshot(f) == before


def test_other_case_material_change_is_not_selected_shared_source_change(shared_http):
    f, _ = shared_http; p, _, _, _ = complete(f, local=True); q, _, _, _ = complete(f, local=True)
    originals = [stored(f, x) for x in (p, q)]
    q = prep_command(f, q, 'REOPEN', reason='SYNTHETIC independent private material change').json()
    material_add(f, q, text='SYNTHETIC PRIVATE_SHARED_CASE_ONLY')
    before = snapshot(f); value = checked(lookup(f, p), p); rows = by_case(value)
    for x, original in zip((p, q), originals):
        expect(rows[x['case_id']], original, (), ('P1','P2','P3','P4','P5'), state='UNCHANGED', relationship='SHARED_SOURCE', scenario='unrelated_material_does_not_change_selected_resource')
    assert snapshot(f) == before


def test_catalog_exact_current_reference_affects_all_original_steps(shared_http):
    f, _ = shared_http; p, _, _, _ = complete(f, local=True); q = one_step(f)
    originals = [stored(f, x) for x in (p, q)]
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET source=source||%s WHERE park_id='park-a' AND version=1", (Jsonb({'independent_revision':'SYNTHETIC_CATALOG_V2'}),))
    before = snapshot(f); value = checked(lookup(f, p, CATALOG), p, CATALOG); rows = by_case(value)
    for x, original in zip((p, q), originals):
        adapters = tuple(s['adapter_id'] for s in original['steps'])
        expect(rows[x['case_id']], original, adapters, (), state='CHANGED', relationship='SHARED_SOURCE', scenario='catalog_exact_reference')
    assert value['all_cases_checked'] and snapshot(f) == before


def test_other_catalog_version_is_not_a_shared_reference(shared_http):
    from parkweave.preparation import SERVICE
    from test_request_intents import save
    f,_ = shared_http; p=one_step(f)
    with f[1].connect() as c:
        c.execute("INSERT INTO preparation_catalog SELECT park_id,service_id,2,name,source,namespace,qualification FROM preparation_catalog WHERE park_id='park-a' AND version=1")
    run=no_preparation(f)
    result=f[3].post('/api/preparations',headers=headers(f[2],key=uuid4().hex),json=dict(run_id=str(run['run_id']),service_id=SERVICE,service_version=2,reviewer_id='prep-specialist-fixture-a'))
    assert result.status_code == 201,result.text
    q=result.json(); q=material_add(f,q).json(); q=material_add(f,q,'material_outline').json()
    q=save(f,q,goals=[GOALS[0]],text='SYNTHETIC current catalog version two request').json()
    q=prep_command(f,q,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC independent v2 check').json()
    q=prep_command(f,q,'CONFIRM',reason='SYNTHETIC explicit v2 confirmation').json()
    assert adopt(f,q).status_code == 201; verified(f,q,'P1'); original=stored(f,q)
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET source=source||%s WHERE park_id='park-a' AND version=1",(Jsonb({'independent_revision':'SYNTHETIC_CATALOG_V1_CHANGED'}),))
    before=snapshot(f); value=checked(lookup(f,p,CATALOG),p,CATALOG)
    expect(by_case(value)[q['case_id']],original,(),('P1',),state='NOT_DEPENDENT',relationship='NOT_DEPENDENT',scenario='different_catalog_version')
    assert snapshot(f) == before


@pytest.mark.parametrize('scope',['owner','case_park','case_org','run_park','run_org'])
def test_candidate_scope_joins_do_not_leak_inconsistent_foreign_case(shared_http,scope):
    f,_=shared_http; p=one_step(f); q=create(f)[0]
    table,column,value={'owner':('runs','principal_id','fixture-b'),'case_park':('cases','park_id','park-b'),
        'case_org':('cases','org_id','org-b'),'run_park':('runs','park_id','park-b'),'run_org':('runs','org_id','org-b')}[scope]
    id=q['run_id'] if table=='runs' else q['case_id']
    with f[1].connect() as c: c.execute('UPDATE '+table+' SET '+column+'=%s WHERE id=%s',(value,id))
    before=snapshot(f); result=checked(lookup(f,p),p)
    assert set(by_case(result)) == {p['case_id']} and snapshot(f) == before


@pytest.mark.parametrize('change',['source','candidate','case'])
def test_mutation_during_multi_case_read_refuses_whole_response(shared_http,monkeypatch,change):
    from parkweave import typed_source_impact
    f,_=shared_http; p=one_step(f); q=one_step(f); reader=typed_source_impact.read; changed=False
    def simultaneous(*args,**kwargs):
        nonlocal changed
        result=reader(*args,**kwargs)
        if not changed:
            changed=True
            if change=='source': add_resource(f)
            elif change=='candidate': no_preparation(f)
            else:
                with f[1].connect() as c: c.execute('UPDATE cases SET goal=goal||%s WHERE id=%s',(' synthetic concurrent change',q['case_id']))
        return result
    monkeypatch.setattr(typed_source_impact,'read',simultaneous)
    response=lookup(f,p)
    assert changed and response.status_code == 409 and 'items' not in response.json(),response.text


def test_missing_verified_baseline_is_unknown_never_no_impact(shared_http):
    f, _ = shared_http; p = setup(f, GOALS[4]); assert adopt(f, p).status_code == 201; verified(f, p, 'P1')
    original = stored(f, p); add_resource(f); before = snapshot(f)
    value = checked(lookup(f, p), p); row = by_case(value)[p['case_id']]
    expect(row, original, ('P1','P2','P3','P4','P5'), (), state='UNKNOWN', relationship='SHARED_SOURCE', scenario='missing_baseline_expands')
    assert not value['all_cases_checked'] and value['unknown_scope'] == 'CURRENT_OWNER_CASE_SET' and snapshot(f) == before


def test_unknown_shared_source_cannot_be_reported_as_unchanged(shared_http):
    f,_=shared_http; p,_,_,_=complete(f,local=True); original=stored(f,p)
    with f[1].connect() as c:
        c.execute('UPDATE synthetic_resources SET source=%s WHERE id=%s',(Jsonb({'kind':'UNKNOWN','private':'PRIVATE_SHARED_SOURCE_BODY'}),RESOURCE_ID))
    before=snapshot(f); value=checked(lookup(f,p),p); row=by_case(value)[p['case_id']]
    expect(row,original,('P1','P2','P3','P4','P5'),(),state='UNKNOWN',relationship='SHARED_SOURCE',scenario='unknown_source_expands')
    assert not value['source_ref']['available'] and not value['all_cases_checked'] and snapshot(f) == before


@pytest.mark.parametrize('actor', ['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_anchor_owner_tenant_park_and_role_refused(shared_http, actor):
    f, _ = shared_http; p = one_step(f); before = snapshot(f)
    result = lookup(f, p, actor=actor)
    assert result.status_code == 403 and 'items' not in result.json() and snapshot(f) == before


@pytest.mark.parametrize('capability', ['READ','PREPARE','ACTIVE','ROLE'])
def test_current_authority_refused_without_business_write(shared_http, capability):
    f, _ = shared_http; p = one_step(f)
    with f[1].connect() as c:
        if capability == 'ACTIVE': c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif capability == 'ROLE': c.execute("UPDATE principals SET role='service_executor' WHERE id='fixture-a'")
        elif capability == 'PREPARE': c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        else: c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    before = snapshot(f); response = lookup(f, p)
    assert response.status_code == 403 and snapshot(f) == before


def test_bounded_pages_are_read_only_and_do_not_claim_preceding_pages_read(shared_http):
    f, _ = shared_http; p = one_step(f); cases = [p] + [create(f)[0] for _ in range(4)]
    before = snapshot(f); cursor = None; seen = []
    for _ in range(5):
        value = checked(lookup(f, p, limit=1, **({'cursor':cursor} if cursor else {})), p)
        assert not value['all_cases_checked']
        seen.extend(row['case_id'] for row in value['items']); cursor = value['next_cursor']
        if not cursor: break
    assert seen == sorted(x['case_id'] for x in cases) and cursor is None and snapshot(f) == before


def test_known_first_page_still_reports_unchecked_remaining_cases(shared_http):
    f,_=shared_http; p=one_step(f); one_step(f); before=snapshot(f)
    value=checked(lookup(f,p,limit=1),p)
    assert value['has_more'] and not value['all_cases_checked']
    assert value['unknown_scope'] == 'CURRENT_OWNER_CASE_SET' and value['state'] == 'UNKNOWN'
    assert snapshot(f) == before


@pytest.mark.parametrize('change', ['source_aba','authority_aba','candidate_add','candidate_aba','case_aba','preparation_aba'])
def test_old_cursor_refuses_source_authority_candidate_and_case_aba(shared_http, change):
    f, _ = shared_http; p = one_step(f); q = create(f)[0]
    first = checked(lookup(f, p, limit=1), p); cursor = first['next_cursor']; assert cursor
    if change == 'candidate_add': no_preparation(f)
    elif change == 'source_aba':
        for delta in (1,-1):
            with f[1].connect() as c: c.execute('UPDATE synthetic_resources SET capacity=capacity+%s WHERE id=%s', (delta,RESOURCE_ID))
    elif change == 'authority_aba':
        for active in (False,True):
            with f[1].connect() as c: c.execute("UPDATE capability_grants SET active=%s WHERE principal_id='fixture-a' AND capability='READ'", (active,))
    elif change == 'candidate_aba':
        for owner in ('fixture-b','fixture-a'):
            with f[1].connect() as c: c.execute('UPDATE runs SET principal_id=%s WHERE id=%s', (owner,q['run_id']))
    elif change == 'case_aba':
        with f[1].connect() as c: original_goal=c.execute('SELECT goal FROM cases WHERE id=%s',(q['case_id'],)).fetchone()['goal']
        for suffix in (' changed',''):
            with f[1].connect() as c: c.execute('UPDATE cases SET goal=%s WHERE id=%s', (original_goal+suffix,q['case_id']))
    else:
        for delta in (1,-1):
            with f[1].connect() as c: c.execute('UPDATE preparations SET revision=revision+%s WHERE id=%s', (delta,q['preparation_id']))
    before = snapshot(f); response = lookup(f, p, limit=1, cursor=cursor)
    assert response.status_code == 409, response.text
    assert snapshot(f) == before


def test_cursor_parameter_conflict_tampering_and_other_anchor_refused(shared_http):
    f, _ = shared_http; p = one_step(f); q = create(f)[0]
    value = checked(lookup(f, p, limit=1), p); cursor = value['next_cursor']; assert cursor
    before = snapshot(f)
    for parent, source, params in [(p,RESOURCE,{'limit':2,'cursor':cursor}), (q,RESOURCE,{'limit':1,'cursor':cursor}), (p,CATALOG,{'limit':1,'cursor':cursor}), (p,RESOURCE,{'limit':1,'cursor':cursor[:-1]+'!'})]:
        result = lookup(f, parent, source, **params); assert result.status_code == 409, result.text
    assert snapshot(f) == before


@pytest.mark.parametrize('params', [{'limit':0},{'limit':21},{'source_kind':'UNKNOWN'},{'cursor':''},{'cursor':'x'*4097}])
def test_query_bounds_are_rejected_by_original_api(shared_http, params):
    f, _ = shared_http; p = one_step(f); before = snapshot(f)
    result = f[3].get('/api/preparations/'+p['preparation_id']+'/shared-source-cases', headers=headers(f[2]), params=params)
    assert result.status_code == 422 and snapshot(f) == before


def test_candidate_overflow_explicit_unknown_never_complete_or_cursor(shared_http):
    f, _ = shared_http; p = one_step(f)
    for _ in range(32): no_preparation(f)
    before = snapshot(f); value = checked(lookup(f,p,limit=20),p)
    assert value['state'] == 'UNKNOWN' and value['unknown_scope'] == 'CURRENT_OWNER_CASE_SET'
    assert not value['enumeration_complete'] and not value['all_cases_checked'] and value['next_cursor'] is None
    assert snapshot(f) == before


def run_html(f, parent, mode, controls, target=None):
    OUT.mkdir(parents=True, exist_ok=True); attempt = mode+'-'+uuid4().hex[:8]; lines=[]; result=None; error=''
    process = subprocess.Popen(['node','tests/shared_source_cases_real_html.js'], cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    selector=selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
    try:
        config=dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],preparation_id=parent['preparation_id'],case_id=parent['case_id'],run_id=parent['run_id'],plan_id=stored(f,target or parent)['id'],mode=mode,target=target or parent)
        process.stdin.write(json.dumps(config)+'\n'); process.stdin.flush()
        while True:
            assert selector.select(timeout=45), 'Original shared-source HTML made no progress within 45 seconds'
            line=process.stdout.readline()
            if not line: break
            lines.append(line); message=json.loads(line)
            if 'control' in message:
                controls[message['control']](); process.stdin.write('{}\n'); process.stdin.flush()
            else: result=message; break
        code=process.wait(timeout=10); error=process.stderr.read(); assert code == 0,error
        assert result and result['scope'] == 'FULL_ORIGINAL_HTML_SHARED_SOURCE_REAL_HTTP_ASGI_OWNED_PG'
        return result
    finally:
        selector.close()
        if process.poll() is None: process.terminate(); process.wait(timeout=5)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines)); (OUT/(attempt+'.stderr.log')).write_text(error+process.stderr.read())


@pytest.mark.parametrize('mode',['positive','lost'])
def test_original_html_shared_source_to_other_case_explicit_six_goal_chain(fresh_chain,mode):
    u=fresh_chain; release=publish(u); p=new_case(u,release,number=0); q=new_case(u,release,number=1)
    enable_approval(u,[p,q]); finish_chain(u,p); finish_chain(u,q,offset=24); f=u['f']
    # q completion changes owner-wide manifests. Explicitly settle p through original local ADOPT/VERIFY.
    from test_registered_local_revision import patch
    current=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2])).json()
    if current['local_revision_required']:
        assert patch(f,p).status_code == 201
        for adapter in ('P2','P3','P4','P5'): verified(f,p,adapter)
    assert lock(f,q,'P1').status_code == 200; old=deepcopy(stored(f,q)); other=deepcopy(stored(f,p))
    def adopted():
        now=stored(f,q); assert now['steps'][0] == old['steps'][0] and now['events'][:-1] == old['events']
        assert stored(f,p) == other
    result=run_html(f,p,mode,{'change_source':lambda:add_resource(f),'after_adopt':adopted},target=q)
    assert len([c for c in result['calls'] if c['method']=='POST']) == 7
    assert stored(f,q)['required_goals'] == old['required_goals'] and len(old['required_goals']) == 6


@pytest.mark.parametrize('mode',['current_403','late_aba','late_403','kind_switch'])
def test_original_html_reverse_current_denial_late_aba_and_source_selection(shared_http,mode):
    f,_=shared_http; p=one_step(f); create(f); old=stored(f,p)
    def authority(active):
        with f[1].connect() as c: c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'",(active,))
    result=run_html(f,p,mode,{'revoke':lambda:authority(False),'restore':lambda:authority(True)})
    assert all(c['method']=='GET' for c in result['calls']) and stored(f,p)['events'] == old['events']


def test_original_html_candidate_overflow_remains_explicit_unknown(shared_http):
    f,_=shared_http; p=one_step(f)
    for _ in range(32): no_preparation(f)
    before=snapshot(f); run_html(f,p,'overflow',{}); assert snapshot(f) == before


@pytest.mark.parametrize('mode',['pagination','pagination_stale'])
def test_original_html_explicit_next_page_and_stale_source_refusal(shared_http,mode):
    f,_=shared_http; p=one_step(f)
    for _ in range(10): no_preparation(f)
    old=stored(f,p); result=run_html(f,p,mode,{'change_source':lambda:add_resource(f)})
    assert all(c['method']=='GET' for c in result['calls']) and stored(f,p) == old
