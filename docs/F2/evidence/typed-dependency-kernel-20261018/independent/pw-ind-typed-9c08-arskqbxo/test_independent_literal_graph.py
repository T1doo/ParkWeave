"""Independent literal engineering oracle, planned before implementation review."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from parkweave import dependency_graph as graph


def h(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def n(id, kind='PLAN_STEP', case='case-a', source='COMPILED', **extra):
    return dict(id=id, type=kind, case_id=case, revision_sha256='a'*64,
                source_kind=source, **extra)


def e(up, down, kind='MATERIAL', state='CONFIRMED', source='COMPILED', obs=None, id=None):
    value=dict(id=id or up+'-'+down+'-'+kind, upstream=up, downstream=down,
               kind=kind, state=state, source_kind=source)
    if obs is not None:
        value['observation']=dict(id=obs[0], revision_sha256=obs[1]*64, known=obs[2])
    return value


def g(nodes, edges=(), unknown=()):
    return dict(graph_id='independent', revision=1,
                scope=dict(park_id='park-a', org_id='org-a', package_id='package-a'),
                nodes=nodes, edges=list(edges), unknown=list(unknown))


def run(raw, change=lambda q: None):
    current=deepcopy(raw);current['revision']=2;change(current)
    inputs=deepcopy((raw,current))
    result=graph.preview(graph.snapshot(raw),graph.snapshot(current))
    assert (raw,current)==inputs
    assert result['read_only'] is True and result['can_adopt'] is False
    assert result['execution_authorized'] is False and result['authority_verified'] is False
    assert result['sha256']==h({k:v for k,v in result.items() if k!='sha256'})
    return result


def literal(result, definite, uncertain, preserved, removed=()):
    assert result['definite']==sorted(definite)
    assert result['uncertain']==sorted(uncertain)
    assert result['affected']==sorted(set(definite)|set(uncertain))
    assert result['preserved']==sorted(preserved)
    assert result['removed']==sorted(removed)


def revise(id):
    return lambda q: next(v for v in q['nodes'] if v['id']==id).update(revision_sha256='b'*64)


@pytest.mark.parametrize('changed,definite,preserved',[
    (None,[],['S','A','B','C','D','Z']),
    ('S',['S','A','B','C','D'],['Z']),
    ('B',['B','D'],['S','A','C','Z']),
])
def test_literal_chain_fork_join(changed, definite, preserved):
    raw=g([n(x) for x in ['S','A','B','C','D','Z']], [
        e('S','A'),e('A','B','CAPACITY'),e('A','C','ELIGIBILITY'),
        e('B','D','VERIFIED_BY'),e('C','D','PACKAGED_IN')])
    result=run(raw,revise(changed) if changed else lambda q:None)
    literal(result,definite,[],preserved)


def test_literal_candidate_and_semantic_join_preserve_both_certainties():
    raw=g([n(x) for x in ['S','A','B','D','Z']], [
        e('S','A','PRECEDES'),e('S','B','SEMANTIC',state='CANDIDATE'),
        e('A','D','VERIFIED_BY'),e('B','D','PACKAGED_IN')])
    literal(run(raw,revise('S')),['S','A','D'],['B','D'],['Z'])


@pytest.mark.parametrize('source',['MODEL_CANDIDATE','UNVERIFIED'])
def test_literal_unverified_source_and_candidate_edge_are_never_definite(source):
    raw=g([n('S',kind='SOURCE',case=None,source=source),n('A'),n('B'),n('Z')],[
        e('S','A','CAPACITY'),e('A','B','MATERIAL')])
    literal(run(raw,revise('S')),[],['S','A','B'],['Z'])
    raw['nodes'][0]['source_kind']='COMPILED';raw['edges'][0]['state']='CANDIDATE'
    literal(run(raw,revise('S')),['S'],['A','B'],['Z'])


def test_literal_individual_consumer_observation_and_actual_multihop():
    raw=g([n('S',kind='SOURCE',case=None,source='ACTUAL_SNAPSHOT'),n('A'),
           n('B',case='case-b'),n('C'),n('Z')],[
        e('S','A',obs=('obs-a','a',True)),e('S','B',obs=('obs-b','a',True)),
        e('A','C','PRECEDES')])
    def change(q):
        revise('S')(q);q['edges'][1]['observation']['revision_sha256']='b'*64
    literal(run(raw,change),['S','B'],[],['A','C','Z'])
    literal(run(raw,revise('S')),['S'],[],['A','B','C','Z'])
    raw=g([n('X'),n('S',kind='SOURCE',case=None),n('A'),n('Z')],[
        e('X','S','CAPACITY'),e('S','A',obs=('obs-a','a',True))])
    literal(run(raw,revise('X')),['X','S','A'],[],['Z'])


def test_literal_unknown_observation_and_ranges():
    raw=g([n('S',kind='SOURCE',case=None),n('A'),n('B',case='case-b'),n('Z',case='case-z')],
          [e('S','A',obs=('obs-a','a',False)),e('A','B','PRECEDES')])
    literal(run(raw),[],['A','B'],['S','Z'])
    raw['edges'][0]['observation']['known']=True
    for kind,targets,expected in [
        ('NODES',dict(node_ids=['A']),['A','B']),
        ('CASES',dict(case_ids=['case-a']),['A','B']),
        ('PACKAGE',{},['S','A','B','Z']),
    ]:
        raw['unknown']=[dict(id='u',kind=kind,reason='UNKNOWN',**targets)]
        result=run(raw)
        literal(result,[],expected,sorted({'S','A','B','Z'}-set(expected)))
        removed=run(raw,lambda q:q.update(unknown=[]))
        literal(removed,[],expected,sorted({'S','A','B','Z'}-set(expected)))


@pytest.mark.parametrize('operation',['add','remove','unchanged-order','incomplete'])
def test_literal_collections_and_canonical_order(operation):
    raw=g([n('S',kind='CAPACITY_SNAPSHOT',case=None,collection=dict(complete=True,members=[
        dict(id='m1',revision_sha256='a'*64),dict(id='m2',revision_sha256='b'*64)])),n('A'),n('Z')],
        [e('S','A','CAPACITY')])
    def change(q):
        c=q['nodes'][0]['collection']
        if operation=='add':c['members'].append(dict(id='m3',revision_sha256='c'*64))
        if operation=='remove':c['members'].pop(0)
        if operation=='unchanged-order':c['members'].reverse();q['nodes'].reverse();q['edges'].reverse()
        if operation=='incomplete':c['complete']=False
    result=run(raw,change)
    if operation=='unchanged-order':literal(result,[],[],['S','A','Z'])
    else:literal(result,['S','A'],['S','A'] if operation=='incomplete' else [],['Z'])
    raw['nodes'][0]['collection']['complete']=False
    literal(run(raw),[],['S','A'],['Z'])


def test_literal_two_version_edges_removed_nodes_and_lock_union():
    raw=g([n('S'),n('A',locked_fields=['body']),n('B',locked_fields=['manual']),n('Z',locked_fields=['keep'])],
          [e('S','A'),e('A','B','PRECEDES')])
    def change(q):
        revise('S')(q);q['nodes'][1]['locked_fields']=['decision'];q['edges'].pop(0)
    result=run(raw,change)
    literal(result,['S','A','B'],[],['Z'])
    assert result['lock_conflicts']==[
        dict(node_id='A',fields=['body','decision'],reason='LOCK_CONFLICT'),
        dict(node_id='B',fields=['manual'],reason='LOCK_CONFLICT')]
    def remove(q):
        q['nodes']=[v for v in q['nodes'] if v['id']!='S'];q['edges'].pop(0)
    literal(run(raw,remove),['S','A','B'],[],['Z'],removed=['S'])
    raw['edges'].pop(0)
    literal(run(raw,lambda q:q['edges'].append(e('S','A'))),['A','B'],[],['S','Z'])


def test_source_category_transition_keeps_both_union_certainties():
    # Planned certainty-contract supplement: union includes one candidate source
    # version and one confirmed source version even when the edge bytes match.
    raw=g([n('X'),n('S',kind='SOURCE',case=None,source='MODEL_CANDIDATE'),n('A'),n('Z')],
          [e('X','S','CAPACITY'),e('S','A')])
    def change(q):
        revise('X')(q);q['nodes'][1]['source_kind']='COMPILED'
    result=run(raw,change)
    assert 'A' in result['uncertain']
    assert 'A' in result['definite'], result


@pytest.mark.parametrize('mutation',[
    'dangling','cycle','candidate-cycle','node-id','edge-id','relation','observation-id','member-id',
    'unknown-node','unknown-case','semantic-confirmed','model-confirmed','bad-revision-hash',
    'bool-revision','non-json-object',
])
def test_invalid_structures_are_closed_and_immutable(mutation):
    raw=g([n('S'),n('A'),n('B')],[e('S','A')])
    if mutation=='dangling':raw['edges'][0]['downstream']='absent'
    if mutation in ('cycle','candidate-cycle'):
        raw['edges'].append(e('A','S',state='CANDIDATE' if mutation=='candidate-cycle' else 'CONFIRMED'))
    if mutation=='node-id':raw['nodes'].append(deepcopy(raw['nodes'][0]))
    if mutation=='edge-id':raw['edges'].append(e('A','B',id=raw['edges'][0]['id']))
    if mutation=='relation':raw['edges'].append(e('S','A',id='different'))
    if mutation=='observation-id':
        raw['edges']=[e('S','A',obs=('o','a',True)),e('S','B',obs=('o','a',True))]
    if mutation=='member-id':raw['nodes'][0]['collection']=dict(complete=True,members=[dict(id='m',revision_sha256='a'*64)]*2)
    if mutation=='unknown-node':raw['unknown']=[dict(id='u',kind='NODES',node_ids=['absent'],reason='UNKNOWN')]
    if mutation=='unknown-case':raw['unknown']=[dict(id='u',kind='CASES',case_ids=['absent'],reason='UNKNOWN')]
    if mutation=='semantic-confirmed':raw['edges'][0]['kind']='SEMANTIC'
    if mutation=='model-confirmed':raw['edges'][0]['source_kind']='MODEL_CANDIDATE'
    if mutation=='bad-revision-hash':raw['nodes'][0]['revision_sha256']='A'*64
    if mutation=='bool-revision':raw['revision']=True
    if mutation=='non-json-object':raw['nodes'][0]['revision_sha256']=object()
    saved=repr(raw)
    with pytest.raises(graph.GraphError):graph.snapshot(raw)
    assert repr(raw)==saved


@pytest.mark.parametrize('axis',['nodes','edges','single-members','total-members','unknown','id','locks'])
def test_exact_contract_limits_accept_then_reject(axis):
    if axis=='nodes':raw=g([n('n'+str(i)) for i in range(128)])
    if axis=='edges':
        raw=g([n('n'+str(i)) for i in range(33)],
              [e('n'+str(i),'n'+str(j),id='e'+str(i)+'-'+str(j))
               for i in range(16) for j in range(16,32)])
    if axis=='single-members':raw=g([n('S',collection=dict(complete=True,members=[dict(id='m'+str(i),revision_sha256='a'*64) for i in range(256)]))])
    if axis=='total-members':raw=g([n('n'+str(i),collection=dict(complete=True,members=[dict(id='m'+str(j),revision_sha256='a'*64) for j in range(256)])) for i in range(2)]+[n('extra',collection=dict(complete=True,members=[]))])
    if axis=='unknown':raw=g([n('S')],unknown=[dict(id='u'+str(i),kind='PACKAGE',reason='UNKNOWN') for i in range(32)])
    if axis=='id':raw=g([n('n'*80)])
    if axis=='locks':raw=g([n('S',locked_fields=['f'+str(i) for i in range(16)])])
    assert graph.snapshot(raw)['sha256']
    if axis=='nodes':raw['nodes'].append(n('overflow'))
    if axis=='edges':raw['edges'].append(e('n0','n32',id='overflow'))
    if axis=='single-members':raw['nodes'][0]['collection']['members'].append(dict(id='overflow',revision_sha256='b'*64))
    if axis=='total-members':raw['nodes'][2]['collection']['members'].append(dict(id='overflow',revision_sha256='b'*64))
    if axis=='unknown':raw['unknown'].append(dict(id='overflow',kind='PACKAGE',reason='UNKNOWN'))
    if axis=='id':raw['nodes'][0]['id']+='n'
    if axis=='locks':raw['nodes'][0]['locked_fields'].append('overflow')
    with pytest.raises(graph.GraphError):graph.snapshot(raw)


@pytest.mark.parametrize('mutation',[
    'park','org','package','node-type','node-case','edge-source','edge-target','edge-kind',
    'observation-source','observation-target','observation-edge','same-revision','backwards','hash',
])
def test_versions_cannot_rebind_stable_contract_entities(mutation):
    raw=g([n('S'),n('A'),n('B')],[e('S','A',obs=('o','a',True))]);now=deepcopy(raw);now['revision']=2
    if mutation in ('park','org','package'):now['scope'][mutation+'_id']='other'
    if mutation=='node-type':now['nodes'][0]['type']='FACT'
    if mutation=='node-case':now['nodes'][0]['case_id']='case-other'
    if mutation=='edge-source':now['edges'][0]['upstream']='B'
    if mutation=='edge-target':now['edges'][0]['downstream']='B'
    if mutation=='edge-kind':now['edges'][0]['kind']='CAPACITY'
    if mutation=='observation-source':now['edges'][0].update(id='different',upstream='B')
    if mutation=='observation-target':now['edges'][0].update(id='different',downstream='B')
    if mutation=='observation-edge':now['edges'][0]['id']='different'
    if mutation=='same-revision':now['revision']=1;now['nodes'][0]['revision_sha256']='b'*64
    if mutation=='backwards':raw['revision']=3
    before,current=graph.snapshot(raw),graph.snapshot(now)
    if mutation=='hash':current['sha256']='0'*64
    with pytest.raises(graph.GraphError):graph.preview(before,current)


@pytest.mark.parametrize('scenario,expected,preserved',[
    ('UP13',['P2','P3','P4','P5'],['P1']),
    ('UP20',['P1','P2','P3','P4','P5'],[]),
])
def test_frozen_legacy_literal_observation_and_unknown_contract(scenario,expected,preserved):
    from test_unified_dependency_propagation_literal import scenario as original_scenario
    from parkweave import unified_dependency_propagation as legacy
    args=original_scenario(scenario);frozen=legacy.build_v1(*args);saved=deepcopy(frozen)
    converted=graph.from_unified_v1(frozen);result=converted['preview']
    lookup={v['adapter_id']:v['id'] for v in args[1]['steps']};step_ids=set(lookup.values())
    assert set(result['affected'])&step_ids=={lookup[v] for v in expected}
    assert set(result['preserved'])&step_ids=={lookup[v] for v in preserved}
    assert converted['legacy_sha256']==frozen['sha256']
    assert converted['before']['legacy_sha256']==converted['current']['legacy_sha256']==frozen['sha256']
    assert frozen==saved and frozen['sha256']==h({k:v for k,v in frozen.items() if k!='sha256'})
