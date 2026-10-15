"""Literal external source-impact oracles over actual HTTP and owned PostgreSQL.

Expected adapter sets come from the frozen business contract. Product graph,
closure, and impact functions are deliberately not used to construct an oracle.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb

from parkweave.api import create_app
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_preparation import preparation_fixture, headers, command as preparation_command, add as material_add
from test_case_goal_results import complete, snapshot, get as goal_results
from test_service_case_steps import read as plan_read, verified, command as plan_command, setup, GOALS
from test_service_plan_manual_lock import lock, stored
from test_case_lifecycle import read as lifecycle_read, act as lifecycle_command
from test_registered_local_revision import add_resource
from test_case_opportunities import imported, get as opportunities, post as opportunity_command, body as opportunity_body
from test_source_change_adoption import preview, adopt
from test_new_enterprise_local_chain import actual_http, fresh_chain, publish, new_case, enable_approval, finish_chain


OUT = Path('.runtime/typed-source-impact-independent')
ALL_STEPS = ('P1', 'P2', 'P3', 'P4', 'P5')
EXPECTED = {
    'material': (ALL_STEPS, ()),
    'fact': (ALL_STEPS, ()),
    'resource_collection': (('P2', 'P3', 'P4', 'P5'), ('P1',)),
    'resource_rule': (('P2', 'P3', 'P4', 'P5'), ('P1',)),
    'resource_capacity': (('P2', 'P3', 'P4', 'P5'), ('P1',)),
    'run_access': (('P3', 'P4', 'P5'), ('P1', 'P2')),
    'receipt': (('P4', 'P5'), ('P1', 'P2', 'P3')),
    'local_check': (('P5',), ('P1', 'P2', 'P3', 'P4')),
    'unchanged': ((), ALL_STEPS),
    'unknown': (ALL_STEPS, ()),
}
ORACLE_RUN_ID = uuid4().hex


@pytest.fixture
def typed_http(link_fixture):
    with actual_http(create_app(link_fixture[0])) as (client, traffic):
        yield (*link_fixture[:3], client), traffic


def source_impact(f, parent, actor='fixture-a'):
    return f[3].get('/api/preparations/' + parent['preparation_id'] + '/source-impact', headers=headers(f[2], actor))


def assert_partition(value, original, scenario):
    """Compare literal expected sets after mapping stable original UUIDs only."""
    ids = {row['adapter_id']: row['id'] for row in original['steps']}
    affected, preserved = EXPECTED[scenario]
    expected_affected = {ids[adapter] for adapter in affected if adapter in ids}
    expected_preserved = {ids[adapter] for adapter in preserved if adapter in ids}
    actual_affected = set(value['affected'])
    actual_preserved = set(value['preserved'])
    OUT.mkdir(parents=True,exist_ok=True)
    record=dict(run_id=ORACLE_RUN_ID,test=os.environ.get('PYTEST_CURRENT_TEST'),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        scenario=scenario,plan_id=original['id'],expected_affected=sorted(expected_affected),actual_affected=sorted(actual_affected),
        expected_preserved=sorted(expected_preserved),actual_preserved=sorted(actual_preserved),
        missed_count=len(expected_affected-actual_affected),wrong_count=len(actual_affected-expected_affected),
        wrong_preserved_count=len(actual_preserved^expected_preserved),intentional_unknown_expansion=scenario=='unknown',unknown_scope=value.get('unknown_scope'))
    with (OUT/('oracle-'+ORACLE_RUN_ID+'.jsonl')).open('a') as output:output.write(json.dumps(record,sort_keys=True)+'\n')
    assert not expected_affected - actual_affected, ('missed_invalidation', expected_affected - actual_affected)
    assert not actual_affected - expected_affected, ('wrong_invalidation', actual_affected - expected_affected)
    assert actual_preserved == expected_preserved
    assert not actual_affected & actual_preserved
    assert actual_affected | actual_preserved == set(ids.values())


def import_card(f, parent):
    _, view, _ = imported(f, parent)
    return view['cards'][-1]


def refresh_card(f, parent, card):
    result = opportunity_command(f, parent, opportunity_body(opportunities(f, parent).json(), 'REFRESH'))
    assert result.status_code == 200, result.text
    return next(row for row in result.json()['current']['cards'] if row['id'] == card['id'])


def checked_graph(response, parent, original):
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['scope'] == 'CURRENT_OWNER_CASE_SOURCE_IMPACT' and value['read_only'] is True
    assert value['preparation_id'] == parent['preparation_id'] and value['plan_id'] == original['id']
    assert not value['new_grants'] and not value['automatic_execution'] and not value['case_goal_completed']
    graph = value['source_impact']
    assert graph['scope'] == 'REGISTERED_CASE_TYPED_SOURCE_IMPACT' and graph['schema'] == 1
    assert graph['binding']['id'] == parent['preparation_id'] and graph['binding']['case_id'] == parent['case_id']
    assert graph['plan_id'] == original['id']
    assert graph['sha256'] == hashlib.sha256(json.dumps({k:v for k,v in graph.items() if k != 'sha256'}, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    nodes = graph['nodes']; ids = {node['id'] for node in nodes}; steps = {row['id'] for row in original['steps']}
    assert len(nodes) == len(ids) and len(nodes) <= 96 and len(graph['edges']) <= 128
    assert {row['id'] for row in graph['step_endpoints']} == steps
    assert all(row['type'] == 'PLAN_STEP' for row in graph['step_endpoints'])
    assert set(graph['changed_node_ids']) == {node['id'] for node in nodes if node['changed']}
    for node in nodes:
        assert len(node['id']) == 64 and all(c in '0123456789abcdef' for c in node['id'])
        assert node['aggregate'] is True and node['step_id'] in steps
        assert node['type'] in {'SOURCE','REQUEST','MATERIAL','FACT','SERVICE_RULE','RESOURCE','RESERVATION','CAPACITY_SNAPSHOT','RECEIPT','CHECK','RELEASE'}
        assert node['provenance'] in {'ACTUAL_REGISTERED_SOURCE_SNAPSHOT','ORIGINAL_REGISTERED_DEPENDENCY_MANIFEST'}
        if node['facet'] == 'RESOURCE_RULES': assert node['type'] == 'RESOURCE'
        if node['facet'] in {'FACT_PURPOSE_BINDING','SERVICE_RULE'}:
            assert any(edge['upstream'] == node['id'] and edge['kind'] == 'MATERIAL' for edge in graph['edges'])
        for side in ('before', 'current'):
            assert node['date_evidence'][side]['state'] in {'RECORDED', 'UNKNOWN'}
            for interval in node['date_evidence'][side]['intervals']:
                assert set(interval) <= {'open_from','open_until','starts_at','ends_at','expires_at'}
                assert all(datetime.fromisoformat(date).utcoffset() is not None for date in interval.values())
    for edge in graph['edges']:
        assert edge['upstream'] in ids | steps and edge['downstream'] in steps
        assert edge['kind'] in {'MATERIAL','CAPACITY','ELIGIBILITY','VERIFIED_BY','PRECEDES','PACKAGED_IN'}
    precedes = {(edge['upstream'],edge['downstream']) for edge in graph['edges'] if edge['provenance'] == 'COMPILED_REGISTERED_ADAPTER'}
    by_adapter = {row['adapter_id']:row['id'] for row in original['steps']}
    assert precedes == {(by_adapter['P'+str(i)],by_adapter['P'+str(i+1)]) for i in range(1,len(steps))}
    return value, graph


def minimal(f, verify=True):
    p = setup(f, GOALS[0]); assert adopt(f,p).status_code == 201
    if verify: verified(f,p,'P1')
    return p


def test_no_plan_read_does_not_create_opportunity_or_plan(typed_http):
    f,_ = typed_http; p = setup(f,GOALS[0]); before = snapshot(f)
    response = source_impact(f,p); assert response.status_code == 200,response.text
    value = response.json(); assert value['state'] == 'NO_PLAN' and value['plan_id'] is None and value['source_impact'] is None
    assert snapshot(f) == before and opportunities(f,p).json()['cards'] == []


def test_aggregate_baseline_stable_ids_dates_and_read_only_without_opportunity(typed_http):
    f,_ = typed_http; p,_,_,_ = complete(f,local=True); original = stored(f,p); before = snapshot(f)
    value,graph = checked_graph(source_impact(f,p),p,original)
    assert_partition(graph,original,'unchanged'); assert value['state'] == 'UNCHANGED' and graph['unknown_scope'] is None
    assert checked_graph(source_impact(f,p),p,original)[1] == graph and snapshot(f) == before
    material = [node for node in graph['nodes'] if node['facet'] == 'MATERIAL_PACKAGE']
    assert len(material) == 5 and all(node['known'] and node['date_evidence']['before']['state'] == 'UNKNOWN' for node in material)
    assert any(node['date_evidence']['current']['state'] == 'RECORDED' for node in graph['nodes'])
    with f[1].connect() as c: ids = [str(row['id']) for row in c.execute('SELECT id FROM preparation_evidence WHERE preparation_id=%s',(p['preparation_id'],)).fetchall()]
    assert all(id not in json.dumps(graph) for id in ids)
    assert opportunities(f,p).json()['cards'] == []


@pytest.mark.parametrize('scenario',['resource_collection','resource_rule','resource_capacity','run_access','receipt','local_check'])
def test_literal_actual_source_partitions_and_stable_node_ids(typed_http,scenario):
    f,_ = typed_http; p,g,d,s = complete(f,local=True); original = stored(f,p)
    _,old = checked_graph(source_impact(f,p),p,original)
    if scenario == 'resource_collection': add_resource(f)
    elif scenario in {'resource_rule','resource_capacity'}:
        from parkweave.resource_holds import RESOURCE_ID
        with f[1].connect() as c:
            clause = 'buffer_seconds=buffer_seconds+1' if scenario == 'resource_rule' else 'capacity=capacity+1'
            c.execute('UPDATE synthetic_resources SET revision=revision+1,'+clause+' WHERE id=%s',(RESOURCE_ID,))
    elif scenario == 'run_access':
        with f[1].connect() as c: c.execute("INSERT INTO run_assignments(run_id,principal_id,park_id,org_id,active) VALUES(%s,'unassigned','park-a','org-a',true)",(p['run_id'],))
    elif scenario == 'receipt':
        s=receipt_command(f,s,'REOPEN').json();s=receipt_command(f,s,'SUBMIT',text='SYNTHETIC independent typed actual receipt v3').json();ack=receipt_command(f,s,'ACKNOWLEDGE');assert ack.status_code == 200,ack.text
    else:
        response=lifecycle_command(f,p,lifecycle_read(f,p).json(),'REVALIDATE');assert response.status_code == 200,response.text
    before=snapshot(f); value,graph=checked_graph(source_impact(f,p),p,original)
    assert_partition(graph,original,scenario);assert graph['unknown_scope'] is None
    assert graph['changed_node_ids'] and {node['id'] for node in old['nodes']} == {node['id'] for node in graph['nodes']}
    assert snapshot(f) == before and stored(f,p)['events'] == original['events']


def test_material_change_is_scoped_to_this_case_and_never_backfills_ids(typed_http):
    f,_=typed_http;p,_,_,_=complete(f,local=True);q,_,_,_=complete(f,local=True)
    a=stored(f,p);b=stored(f,q);_,old_b=checked_graph(source_impact(f,q),q,b)
    p=preparation_command(f,p,'REOPEN',reason='SYNTHETIC independent source replacement').json();p=material_add(f,p,text='SYNTHETIC PRIVATE_TYPED_MATERIAL_NEW').json()
    before=snapshot(f);_,graph=checked_graph(source_impact(f,p),p,a)
    assert_partition(graph,a,'material');assert graph['unknown_scope'] is None
    assert checked_graph(source_impact(f,q),q,b)[1] == old_b and snapshot(f) == before
    assert {node['id'] for node in graph['nodes']}.isdisjoint({node['id'] for node in old_b['nodes']})
    assert 'PRIVATE_TYPED_MATERIAL_NEW' not in json.dumps(graph)


def test_unselected_competing_fact_changes_aggregate_purpose_without_value_leak(typed_http):
    from test_case_fact_clarifications_integration import declared_and_selected,human_review_and_confirm,complete_and_close,post_fact
    f,_=typed_http;p,selected,_=declared_and_selected(f);p=human_review_and_confirm(f,p);complete_and_close(f,p)
    original=stored(f,p);checked_graph(source_impact(f,p),p,original)
    fact_id=post_fact(f,'region','PRIVATE_TYPED_UNSELECTED_COMPETING_FACT','SYNTHETIC typed unselected assertion')
    before=snapshot(f);value,graph=checked_graph(source_impact(f,p),p,original)
    assert_partition(graph,original,'fact');assert value['state'] == 'UNKNOWN'
    assert any(node['facet'] == 'FACT_PURPOSE_BINDING' and node['changed'] for node in graph['nodes'])
    raw=json.dumps(graph);assert fact_id not in raw and all(id not in raw for id in selected.values()) and 'PRIVATE_TYPED_UNSELECTED_COMPETING_FACT' not in raw
    assert snapshot(f) == before


def test_missing_baseline_expands_this_case_and_blocks_new_adoption(typed_http):
    f,_=typed_http;p=setup(f,GOALS[4]);assert adopt(f,p).status_code == 201;verified(f,p,'P1');card=import_card(f,p);add_resource(f)
    original=stored(f,p);before=snapshot(f);value,graph=checked_graph(source_impact(f,p),p,original)
    assert_partition(graph,original,'unknown');assert graph['unknown_scope'] == 'THIS_CASE' and 'SOURCE_BASE_UNAVAILABLE' in graph['unknown_reasons']
    assert any(not node['known'] and not node['before_present'] for node in graph['nodes'])
    proposed=preview(f,p,card);assert proposed.status_code == 200,proposed.text;assert not proposed.json()['can_adopt']
    assert adopt(f,p,proposed.json()['adoption']).status_code == 409 and snapshot(f) == before


def test_unknown_future_metadata_is_opaque_expands_case_and_cannot_authorize(typed_http,monkeypatch):
    """Negative future-schema seam; known source rows still come from actual PG."""
    from parkweave import service_case_steps
    f,_=typed_http;p,_,_,_=complete(f,local=True);card=import_card(f,p);add_resource(f);original=stored(f,p)
    original_reader=service_case_steps.current_sources
    def future_reader(*args,**kwargs):
        issues,sources,actual=original_reader(*args,**kwargs)
        sources=deepcopy(sources);sources['P4']['PRIVATE_TYPED_UNKNOWN_FIELD']={'value':'PRIVATE_TYPED_UNKNOWN_BODY'}
        return issues,sources,actual
    monkeypatch.setattr(service_case_steps,'current_sources',future_reader)
    before=snapshot(f);_,graph=checked_graph(source_impact(f,p),p,original)
    assert_partition(graph,original,'unknown');assert graph['unknown_scope'] == 'THIS_CASE' and 'UNMAPPED_SOURCE_FIELDS' in graph['unknown_reasons']
    raw=json.dumps(graph);assert 'PRIVATE_TYPED_UNKNOWN_FIELD' not in raw and 'PRIVATE_TYPED_UNKNOWN_BODY' not in raw
    assert any(node['facet'] == 'UNMAPPED_SOURCE_FIELDS' and node['known'] is False and node['fields'] == [] for node in graph['nodes'])
    proposed=preview(f,p,card);assert proposed.status_code == 200,proposed.text;assert proposed.json()['can_adopt'] is False
    assert adopt(f,p,proposed.json()['adoption']).status_code == 409 and snapshot(f) == before


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_graph_current_owner_tenant_and_role_scope(typed_http,actor):
    f,_=typed_http;p=minimal(f);before=snapshot(f)
    assert source_impact(f,p,actor).status_code == 403 and snapshot(f) == before


@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE','ACTIVE'])
def test_graph_current_revocation_and_original_adoption_gate(typed_http,capability):
    f,_=typed_http;p,_,_,_=complete(f,local=True);card=import_card(f,p);add_resource(f);proposed=preview(f,p,card).json();assert proposed['can_adopt']
    with f[1].connect() as c:
        if capability == 'ACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        else:
            table='preparation_grants' if capability == 'PREPARE' else 'capability_grants';revision='' if capability == 'PREPARE' else ',revision=revision+1'
            c.execute('UPDATE '+table+' SET active=false'+revision+" WHERE principal_id='fixture-a' AND capability=%s",(capability,))
    before=snapshot(f);response=source_impact(f,p)
    assert response.status_code == (200 if capability == 'EXECUTE' else 403)
    assert adopt(f,p,proposed['adoption']).status_code == 403 and snapshot(f) == before


def test_v2_graph_proof_aba_idempotency_and_preserved_lock(typed_http):
    f,_=typed_http;p,_,_,_=complete(f,local=True);assert lock(f,p,'P1').status_code == 200;card=import_card(f,p);resource=add_resource(f)
    old=stored(f,p);view,graph=checked_graph(source_impact(f,p),p,old);proposed=preview(f,p,card).json();assert proposed['source_impact'] == graph
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(resource,))
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity-1 WHERE id=%s',(resource,))
    before=snapshot(f);assert adopt(f,p,proposed['adoption']).status_code == 409 and snapshot(f) == before
    fresh=preview(f,p,card).json();assert fresh['preview_sha256'] != proposed['preview_sha256'];key=uuid4().hex
    result=adopt(f,p,fresh['adoption'],key);assert result.status_code == 201,result.text
    now=stored(f,p);proof=now['events'][-1]['local_revision']['source_change'];assert proof['version'] == 2 and proof['source_impact'] == fresh['source_impact']
    assert now['steps'][0] == old['steps'][0] and now['events'][:-1] == old['events']
    before=snapshot(f);assert adopt(f,p,fresh['adoption'],key).status_code == 201
    assert adopt(f,p,{**fresh['adoption'],'reason':'SYNTHETIC conflicting typed reason'},key).status_code == 409 and snapshot(f) == before
    for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
    assert goal_results(f,p).json()['state'] == 'LOCAL_OUTPUTS_VERIFIED' and stored(f,p)['steps'][0] == old['steps'][0]


@pytest.mark.parametrize('damage',['sha','edge'])
def test_damaged_v2_graph_refuses_original_plan_and_result_reads(typed_http,damage):
    from test_service_plan_recovery import recover
    f,_=typed_http;p,_,_,_=complete(f,local=True);card=import_card(f,p);add_resource(f);proposed=preview(f,p,card).json();key=uuid4().hex
    result=adopt(f,p,proposed['adoption'],key);assert result.status_code == 201,result.text
    plan=stored(f,p);graph=plan['events'][-1]['local_revision']['source_change']['source_impact']
    if damage == 'sha':graph['sha256']='0'*64
    else:graph['edges'][0]['downstream']=str(uuid4())
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    before=snapshot(f);assert plan_read(f,p).status_code == recover(f,p,key).status_code == goal_results(f,p).status_code == 409
    assert snapshot(f) == before


def run_html(f,parent,mode,controls):
    OUT.mkdir(parents=True,exist_ok=True);attempt=mode+'-'+uuid4().hex[:8];lines=[];result=None;error=''
    process=subprocess.Popen(['node','tests/typed_source_impact_real_html.js'],cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    try:
        process.stdin.write(json.dumps(dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],preparation_id=parent['preparation_id'],case_id=parent['case_id'],run_id=parent['run_id'],plan_id=stored(f,parent)['id'],mode=mode))+'\n');process.stdin.flush()
        while True:
            assert selector.select(timeout=40),'Original typed-source HTML made no progress within 40 seconds'
            line=process.stdout.readline()
            if not line:break
            lines.append(line);message=json.loads(line)
            if 'control' in message:
                controls[message['control']]();process.stdin.write('{}\n');process.stdin.flush()
            else:result=message;break
        code=process.wait(timeout=10);error=process.stderr.read();assert code == 0,error
        assert result and result['scope'] == 'FULL_ORIGINAL_HTML_TYPED_SOURCE_REAL_HTTP_ASGI_OWNED_PG'
        return result
    finally:
        selector.close()
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(error+process.stderr.read())


@pytest.mark.parametrize('mode',['positive','lost'])
def test_complete_original_html_typed_source_lookup_and_explicit_six_goal_chain(fresh_chain,mode):
    u=fresh_chain;p=new_case(u,publish(u));enable_approval(u,[p]);finish_chain(u,p);f=u['f'];assert lock(f,p,'P1').status_code == 200;old=deepcopy(stored(f,p))
    def adopted():
        now=stored(f,p);assert now['steps'][0] == old['steps'][0] and now['events'][:-1] == old['events'];assert now['events'][-1]['local_revision']['source_change']['version'] == 2
    result=run_html(f,p,mode,{'change_source':lambda:add_resource(f),'after_adopt':adopted})
    assert len([c for c in result['calls'] if c['method'] == 'POST']) == 7
    assert stored(f,p)['required_goals'] == old['required_goals'] and len(old['required_goals']) == 6


@pytest.mark.parametrize('mode',['late_read_aba','late_read_403','open_current_403','open_late_403'])
def test_original_html_typed_graph_current_and_late_403_identity_aba(typed_http,mode):
    f,_=typed_http;p,_,_,_=complete(f,local=True);old=stored(f,p)
    def authority(active):
        with f[1].connect() as c:
            c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'",(active,))
    result=run_html(f,p,mode,{'revoke':lambda:authority(False),'restore':lambda:authority(True)})
    assert all(c['method'] == 'GET' for c in result['calls']) and stored(f,p)['events'] == old['events']
