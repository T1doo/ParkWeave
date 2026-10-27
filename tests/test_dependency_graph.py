"""Literal impact answers for explicit graphs; no model, database or authority."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
from parkweave import dependency_graph as dg


def node(id, *, type='PLAN_STEP', case='case-a', source='COMPILED', **extra):
    return dict(id=id, type=type, case_id=case, revision_sha256='a'*64,
                source_kind=source, **extra)


def edge(id, upstream, downstream, kind='PRECEDES', **extra):
    return dict(id=id, upstream=upstream, downstream=downstream, kind=kind,
                source_kind='COMPILED', state='CONFIRMED', **extra)


def graph(nodes, edges=(), **extra):
    return dict(graph_id='graph', revision=1,
                scope=dict(park_id='park', org_id='org', package_id='package'),
                nodes=nodes, edges=list(edges), **extra)


def compare(raw, *, nodes=(), mutate=None):
    current=deepcopy(raw);current['revision']+=1
    for n in current['nodes']:
        if n['id'] in nodes:n['revision_sha256']='b'*64
    if mutate:mutate(current)
    original=deepcopy((raw,current))
    before,after=dg.snapshot(raw),dg.snapshot(current)
    result=dg.preview(before,after)
    assert (raw,current)==original
    assert result['read_only'] is True and result['can_adopt'] is False
    assert result['execution_authorized'] is False and result['authority_verified'] is False
    assert result['sha256']==sha256(json.dumps({k:v for k,v in result.items() if k!='sha256'},
        sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return result


def test_typed_chain_branch_join_has_literal_partition_and_no_numeric_step_assumption():
    raw=graph([node(x) for x in ['rule','left','right','join','tail','unrelated']],[
        edge('a','rule','left','ELIGIBILITY'),edge('b','rule','right','MATERIAL'),
        edge('c','left','join','VERIFIED_BY'),edge('d','right','join','CAPACITY'),
        edge('e','join','tail','PACKAGED_IN')])
    result=compare(raw,nodes=['rule'])
    assert result['definite']==['join','left','right','rule','tail']
    assert result['uncertain']==[] and result['preserved']==['unrelated']
    witness=next(w for w in result['propagation_reasons'] if w['node_id']=='tail')
    assert [e['id'] for e in witness['path']]==['a','c','e']
    assert all(len(w['path'])<=3 for w in result['propagation_reasons'])


@pytest.mark.parametrize('kind',['ELIGIBILITY','MATERIAL','CAPACITY','PRECEDES',
                                  'VERIFIED_BY','PACKAGED_IN','SEMANTIC'])
def test_each_original_edge_type_propagates_multiple_hops(kind):
    first=edge('source-link','source','document',kind)
    if kind=='SEMANTIC':first['state']='CANDIDATE'
    raw=graph([node('source',type='SOURCE'),node('document',type='MATERIAL'),node('check')],[
        first,edge('check-link','document','check','VERIFIED_BY')])
    result=compare(raw,nodes=['source'])
    if kind=='SEMANTIC':
        assert result['definite']==['source'] and result['uncertain']==['check','document']
    else:
        assert result['definite']==['check','document','source'] and not result['uncertain']
    assert not result['preserved']


def test_confirmed_and_candidate_paths_keep_uncertainty_at_join():
    candidate=edge('b','a','maybe');candidate['state']='CANDIDATE'
    raw=graph([node(x) for x in ['a','sure','maybe','join','tail']],[
        edge('a','a','sure'),candidate,edge('c','sure','join'),edge('d','maybe','join'),
        edge('e','join','tail')])
    result=compare(raw,nodes=['a'])
    assert result['definite']==['a','join','sure','tail']
    assert result['uncertain']==['join','maybe','tail']
    assert result['affected']==['a','join','maybe','sure','tail']


def test_shared_source_only_changed_consumer_observation_starts_propagation():
    observed=lambda id:dict(id=id,revision_sha256='a'*64,known=True)
    raw=graph([node('shared',type='SOURCE',case=None,source='ACTUAL_SNAPSHOT'),
               node('one'),node('two',case='case-b'),node('tail')],[
        edge('one-observation','shared','one','MATERIAL',observation=observed('o1')),
        edge('two-observation','shared','two','MATERIAL',observation=observed('o2')),
        edge('tail','one','tail')])
    result=compare(raw,nodes=['shared'],mutate=lambda g:g['edges'][0]['observation'].update(revision_sha256='b'*64))
    assert result['definite']==['one','shared','tail'] and result['preserved']==['two']
    # Shared aggregate metadata alone is not a new observation for either consumer.
    result=compare(raw,nodes=['shared'])
    assert result['definite']==['shared'] and result['preserved']==['one','tail','two']


def test_unchanged_observation_does_not_stop_actual_multi_hop_dependency_change():
    raw=graph([node('request'),node('source',type='MATERIAL'),node('consumer')],[
        edge('input','request','source','PACKAGED_IN'),
        edge('observed','source','consumer','MATERIAL',
             observation=dict(id='obs',revision_sha256='a'*64,known=True))])
    result=compare(raw,nodes=['request'])
    assert result['definite']==['consumer','request','source'] and not result['preserved']


@pytest.mark.parametrize('source',['MODEL_CANDIDATE','UNVERIFIED'])
def test_source_category_change_is_not_hidden_by_unchanged_observation(source):
    raw=graph([node('source',type='SOURCE'),node('consumer')],[
        edge('a','source','consumer',observation=dict(id='obs',revision_sha256='a'*64,known=True))])
    result=compare(raw,mutate=lambda g:g['nodes'][0].update(source_kind=source))
    assert result['uncertain']==['consumer','source'] and not result['preserved']


@pytest.mark.parametrize('before_kind,current_kind',[
    ('MODEL_CANDIDATE','COMPILED'),('COMPILED','MODEL_CANDIDATE')])
def test_source_category_transition_retains_both_versioned_path_witnesses(before_kind,current_kind):
    raw=graph([node('x'),node('s',source=before_kind),node('a')],[
        edge('xs','x','s'),edge('sa','s','a')])
    current=deepcopy(raw);current['revision']=2
    current['nodes'][0]['revision_sha256']='b'*64
    current['nodes'][1]['source_kind']=current_kind
    before,after=dg.snapshot(raw),dg.snapshot(current)
    result=dg.preview(before,after)
    assert 'a' in result['definite'] and 'a' in result['uncertain']
    paths={w['certainty']:w['path'] for w in result['propagation_reasons'] if w['node_id']=='a'}
    sure=after if current_kind=='COMPILED' else before
    candidate=before if before_kind=='MODEL_CANDIDATE' else after
    assert paths['DEFINITE'][-1]['graph_sha256']==sure['sha256']
    assert paths['UNCERTAIN'][-1]['graph_sha256']==candidate['sha256']
    assert paths['DEFINITE'][-1]['edge_sha256']==paths['UNCERTAIN'][-1]['edge_sha256']


@pytest.mark.parametrize('kind,targets,expected',[
    ('NODES',{'node_ids':['a']},['a','b']),
    ('CASES',{'case_ids':['case-a']},['a','b']),
    ('PACKAGE',{},['a','b','other']),
])
def test_explicit_unknown_ranges_do_not_invent_cross_scope_relations(kind,targets,expected):
    raw=graph([node('a'),node('b'),node('other',case='case-b')],[edge('ab','a','b')],
              unknown=[dict(id='unknown',kind=kind,reason='DYNAMIC_UNKNOWN',**targets)])
    result=compare(raw)
    assert result['definite']==[] and result['uncertain']==expected
    assert result['preserved']==(['other'] if kind!='PACKAGE' else [])


def test_removed_unknown_range_remains_an_uncertain_basis_for_this_comparison():
    raw=graph([node('a'),node('b')],unknown=[dict(id='u',kind='NODES',node_ids=['a'],reason='DYNAMIC_UNKNOWN')])
    result=compare(raw,mutate=lambda g:g.update(unknown=[]))
    assert result['uncertain']==['a'] and result['preserved']==['b']


@pytest.mark.parametrize('operation',['add','delete','revision','incomplete'])
def test_collection_membership_fingerprint_and_incomplete_sets(operation):
    raw=graph([node('set',type='CAPACITY_SNAPSHOT',collection=dict(complete=True,members=[
        dict(id='first',revision_sha256='a'*64)])),node('consumer'),node('other')],[
        edge('capacity','set','consumer','CAPACITY')])
    def mutate(g):
        collection=g['nodes'][0]['collection']
        if operation=='add':collection['members'].append(dict(id='unselected',revision_sha256='b'*64))
        if operation=='delete':collection['members'].clear()
        if operation=='revision':collection['members'][0]['revision_sha256']='b'*64
        if operation=='incomplete':collection['complete']=False
    result=compare(raw,mutate=mutate)
    assert result['definite']==['consumer','set'] and result['preserved']==['other']
    assert result['uncertain']==(['consumer','set'] if operation=='incomplete' else [])


def test_unknown_observation_without_content_change_is_not_preserved():
    raw=graph([node('source',type='SOURCE'),node('consumer')],[
        edge('a','source','consumer',observation=dict(id='o',revision_sha256='a'*64,known=False))])
    result=compare(raw)
    assert result['definite']==[] and result['uncertain']==['consumer']
    assert result['preserved']==['source']


def test_removed_and_added_edges_use_both_versions_and_retain_removed_nodes_locks():
    raw=graph([node('source'),node('old',locked_fields=['body']),node('new'),node('tail')],[
        edge('old-link','source','old'),edge('old-tail','old','tail')])
    def mutate(g):
        g['nodes']=[n for n in g['nodes'] if n['id']!='old']
        g['edges']=[edge('new-link','source','new'),edge('new-tail','new','tail')]
    result=compare(raw,mutate=mutate)
    assert result['definite']==['new','old','tail'] and result['preserved']==['source']
    assert result['removed']==['old']
    assert result['lock_conflicts']==[dict(node_id='old',fields=['body'],reason='LOCK_CONFLICT')]


def test_changed_or_removed_manual_locks_use_before_and_current_union_without_writes():
    raw=graph([node('a',locked_fields=['body']),node('b')],[edge('ab','a','b')])
    result=compare(raw,mutate=lambda g:g['nodes'][0].update(locked_fields=['assignment']))
    assert result['affected']==['a','b']
    assert result['lock_conflicts'][0]['fields']==['assignment','body']


def test_order_independent_hash_input_immutability_and_revision_only_no_impact():
    raw=graph([node('b'),node('a',locked_fields=['z','a'],collection=dict(complete=True,members=[
        dict(id='z',revision_sha256='a'*64),dict(id='a',revision_sha256='b'*64)]))],[edge('ab','a','b')])
    copy=deepcopy(raw);copy['nodes'].reverse();copy['nodes'][0]['locked_fields'].reverse()
    copy['nodes'][0]['collection']['members'].reverse()
    original=deepcopy((raw,copy))
    assert dg.snapshot(raw)==dg.snapshot(copy)
    assert (raw,copy)==original
    result=compare(raw)
    assert result['affected']==[] and result['preserved']==['a','b']
    saved=dg.snapshot(raw)
    assert dg.preview(saved,saved)['affected']==[]


def invalid(kind):
    raw=graph([node('a'),node('b')],[edge('ab','a','b')])
    if kind=='cycle':raw['edges'].append(edge('ba','b','a'))
    if kind=='candidate-cycle':
        e=edge('ba','b','a');e['state']='CANDIDATE';raw['edges'].append(e)
    if kind=='dangling':raw['edges'][0]['downstream']='missing'
    if kind=='duplicate-node':raw['nodes'].append(deepcopy(raw['nodes'][0]))
    if kind=='duplicate-edge':raw['edges'].append(deepcopy(raw['edges'][0]))
    if kind=='duplicate-relation':raw['edges'].append(edge('other','a','b'))
    if kind=='duplicate-observation':
        raw['edges'].append(edge('other','a','b','MATERIAL'))
        for e in raw['edges']:e['observation']=dict(id='o',revision_sha256='a'*64,known=True)
    if kind=='duplicate-member':raw['nodes'][0]['collection']=dict(complete=True,members=[dict(id='x',revision_sha256='a'*64)]*2)
    if kind=='bad-hash':raw['nodes'][0]['revision_sha256']='fake'
    if kind=='bool-revision':raw['revision']=True
    if kind=='float-revision':raw['revision']=1.0
    if kind=='unknown-kind':raw['edges'][0]['kind']='DISCOVER'
    if kind=='extra':raw['permit']=True
    if kind=='scope-extra':raw['nodes'][0]['org_id']='other'
    if kind=='step-no-case':raw['nodes'][0]['case_id']=None
    if kind=='semantic-confirmed':raw['edges'][0]['kind']='SEMANTIC'
    if kind=='model-confirmed':raw['edges'][0]['source_kind']='MODEL_CANDIDATE'
    if kind=='unknown-outside':raw['unknown']=[dict(id='u',kind='NODES',node_ids=['missing'],reason='UNKNOWN')]
    if kind=='case-outside':raw['unknown']=[dict(id='u',kind='CASES',case_ids=['other'],reason='UNKNOWN')]
    if kind=='unknown-mixed':raw['unknown']=[dict(id='u',kind='PACKAGE',node_ids=['a'],reason='UNKNOWN')]
    if kind=='node-bound':raw['nodes']=[node('n'+str(i)) for i in range(129)];raw['edges']=[]
    if kind=='member-bound':raw['nodes'][0]['collection']=dict(complete=True,members=[dict(id='m'+str(i),revision_sha256='a'*64) for i in range(257)])
    if kind=='total-member-bound':
        raw['nodes']=[node('n'+str(i),collection=dict(complete=True,members=[
            dict(id='m'+str(j),revision_sha256='a'*64) for j in range(256)])) for i in range(3)]
        raw['edges']=[]
    if kind=='unknown-bound':raw['unknown']=[dict(id='u'+str(i),kind='PACKAGE',reason='UNKNOWN') for i in range(33)]
    if kind=='id-bound':raw['nodes'][0]['id']='n'*81
    if kind=='edge-bound':
        raw['nodes']=[node('n'+str(i)) for i in range(24)]
        raw['edges']=[edge(f'e{i}-{j}',f'n{i}',f'n{j}') for i in range(24) for j in range(i+1,24)][:257]
    return raw


@pytest.mark.parametrize('kind',[
    'cycle','candidate-cycle','dangling','duplicate-node','duplicate-edge','duplicate-relation',
    'duplicate-observation','duplicate-member','bad-hash','bool-revision','float-revision',
    'unknown-kind','extra','scope-extra','step-no-case','semantic-confirmed','model-confirmed',
    'unknown-outside','case-outside','unknown-mixed','node-bound','member-bound',
    'total-member-bound','unknown-bound','id-bound','edge-bound'])
def test_invalid_or_unbounded_graph_is_refused_without_input_changes(kind):
    raw=invalid(kind);saved=deepcopy(raw)
    with pytest.raises(dg.GraphError):dg.snapshot(raw)
    assert raw==saved


@pytest.mark.parametrize('mutation',['scope','graph','node-case','node-type','edge-target',
                                   'observation-rebind','same-revision','old-revision','tampered-hash'])
def test_version_identity_and_hash_cannot_rebind_old_entities(mutation):
    raw=graph([node('a'),node('b'),node('c')],[edge('ab','a','b',
        observation=dict(id='observation',revision_sha256='a'*64,known=True))])
    current=deepcopy(raw);current['revision']=2
    if mutation=='scope':current['scope']['org_id']='other'
    if mutation=='graph':current['graph_id']='other'
    if mutation=='node-case':current['nodes'][0]['case_id']='other'
    if mutation=='node-type':current['nodes'][0]['type']='FACT'
    if mutation=='edge-target':current['edges'][0]['downstream']='c'
    if mutation=='observation-rebind':
        current['edges'][0]['id']='new-edge';current['edges'][0]['downstream']='c'
    if mutation=='same-revision':current['revision']=1;current['nodes'][0]['revision_sha256']='b'*64
    if mutation=='old-revision':current['revision']=1;raw['revision']=2
    before,after=dg.snapshot(raw),dg.snapshot(current)
    if mutation=='tampered-hash':after['nodes'][0]['revision_sha256']='b'*64
    with pytest.raises(dg.GraphError):dg.preview(before,after)


@pytest.mark.parametrize('index',range(1,25))
def test_old_frozen_graph_observations_partition_and_original_hash_are_retained(index):
    from test_unified_dependency_propagation import changed,ids
    from parkweave import unified_dependency_propagation as old
    literal=json.loads(Path('docs/F2/UnifiedSourcePropagationOracle-20261016.json').read_text())
    expected=next(row for row in literal['rows'] if row['id']==f'UP{index:02d}')
    args=changed(index);legacy=old.build_v1(*args);saved=deepcopy(legacy)
    converted=dg.from_unified_v1(legacy);result=converted['preview']
    step_ids={s['id'] for s in args[1]['steps']}
    assert set(result['affected'])&step_ids==set(ids(args[1],expected['affected']))
    assert set(result['preserved'])&step_ids==set(ids(args[1],expected['preserved']))
    assert converted['legacy_sha256']==legacy['sha256'] and legacy==saved
    assert converted['before']['legacy_sha256']==converted['current']['legacy_sha256']==legacy['sha256']


def test_legacy_hash_partition_and_consumer_forgery_never_become_current_proof():
    from test_unified_dependency_propagation import changed
    from parkweave import unified_dependency_propagation as old, controlled_plans as cp
    legacy=old.build_v1(*changed(15))
    for mutation in ['hash','partition','consumer']:
        value=deepcopy(legacy)
        if mutation=='hash':value['sha256']='0'*64
        if mutation=='partition':value['affected']=[]
        if mutation=='consumer':
            value['observations'][0]['step_id']=value['step_endpoints'][-1]['id']
            value['sha256']=cp._hash({k:v for k,v in value.items() if k!='sha256'})
        with pytest.raises(dg.GraphError):dg.from_unified_v1(value)


def test_frozen_legacy_graph_does_not_consult_todays_scope_or_compiler(monkeypatch):
    from test_unified_dependency_propagation import changed
    from parkweave import unified_dependency_propagation as old
    frozen=old.build_v1(*changed(13));saved=deepcopy(frozen)
    monkeypatch.setattr(old,'SCOPE','FUTURE_SCOPE')
    def forbidden(*args,**kwargs):
        raise AssertionError('historical graph must not be recompiled')
    monkeypatch.setattr(old,'build_v1',forbidden)
    converted=dg.from_unified_v1(frozen)
    assert converted['legacy_sha256']==saved['sha256'] and frozen==saved
