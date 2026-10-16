"""Literal finite-source answers; no database, HTTP, or generated oracle."""
from copy import deepcopy
from uuid import uuid4
import json
from pathlib import Path
import pytest
from parkweave import controlled_plans as cp, registered_dependencies as deps, typed_source_impact as typed
from parkweave import unified_dependency_propagation as unified
from parkweave.store import Conflict


def sample():
    parent={k:str(uuid4()) for k in ('id','case_id','run_id')}
    parent.update(owner_id='owner',park_id='park',org_id='org',service_id='service',namespace='SYNTHETIC')
    steps=[dict(id=str(uuid4()),adapter_id='P'+str(i),depends_on=[] if i==1 else ['P'+str(i-1)]) for i in range(1,6)]
    plan=dict(id=str(uuid4()),steps=steps);parent['service_case_plan']=plan
    before={s['adapter_id']:{'preparation_revision':1,'preparation_sha256':'a'*64} for s in steps[:-1]}
    before['P5']={'sources':{'preparation_revision':1,'preparation_sha256':'a'*64},'local_lifecycle':None}
    values={name:dict(known=True,count=1,sha256='a'*64) for name in ('resources','existing_access')}
    manifest=deps.manifest(steps,values)
    return parent,plan,before,manifest


def ids(plan,adapters):return [s['id'] for s in plan['steps'] if s['adapter_id'] in adapters]


def changed(index):
    parent,plan,before,old=sample();current=deepcopy(before);new=deepcopy(old)
    if index==2:current['P4']['receipt_sha256']='b'*64
    if index==3:current['P3']['dispatch_revision']=2
    if index in (4,5):current['P2']['resource_rules']=[dict(open_from='2026-01-01T00:00:00+00:00',open_until='2027-01-01T00:00:00+00:00')]
    if index in (5,6,12):current['P4']['receipt_sha256']='b'*64
    if index in (6,9):current['P1']['service_catalog']={'revision':2}
    if index==7:
        current['P1']['fact_clarification']={'satisfied':True,'revision':2}
        current['P5']['sources']['fact_clarification']={'satisfied':True,'revision':2}
    if index==8:
        for a in ('P1','P2','P3','P4'):current[a]['preparation_revision']=2
        current['P5']['sources']['preparation_revision']=2
    if index==9:current['P1'].update(preparation_revision=2,fact_clarification={'satisfied':True,'revision':2})
    if index in (10,12):new['collections']['resources'].update(count=2,sha256='b'*64)
    if index in (11,12):new['collections']['existing_access'].update(count=2,sha256='b'*64)
    if index==13:
        before['P1']['preparation_revision']=current['P1']['preparation_revision']=2
        current['P2']['preparation_revision']=2
    if index==14:
        before['P1']['fact_clarification']=current['P1']['fact_clarification']={'satisfied':True,'revision':2}
        before['P5']['sources']['fact_clarification']={'satisfied':True,'revision':1}
        current['P5']['sources']['fact_clarification']={'satisfied':True,'revision':2}
    if index==15:current['P5']['sources']['preparation_revision']=2
    if index==16:
        before['P2']['resource_link_revision']=current['P2']['resource_link_revision']=2
        before['P5']['sources']['resource_link_revision']=1
        current['P5']['sources']['resource_link_revision']=2
    if index==17:current['P5']['local_lifecycle']={'cycle':2}
    if index==18:before.pop('P3')
    if index==19:current['P4']['PRIVATE_POISON_FIELD']={'secret':'PRIVATE_POISON_VALUE'}
    if index==20:new['collections']['resources']['known']=False
    if index==21:new['version']=2
    if index==22:current['P5'].pop('sources')
    if index==23:current['P2']['resource_rules']=[None]
    if index==24:current['P1']['fact_clarification']={'satisfied':False}
    new['sha256']=cp._hash({k:v for k,v in new.items() if k!='sha256'})
    return parent,plan,before,current,old,new


@pytest.mark.parametrize('index',range(1,25))
def test_independent_literal_partition(index):
    oracle=json.loads((Path(__file__).resolve().parents[2]/'unified-propagation-oracle/literal-oracle.json').read_text()) if '.runtime' in str(Path(__file__)) else json.loads(Path('docs/F2/UnifiedPropagationOracle-20261016.json').read_text())
    expected=next(row for row in oracle['rows'] if row['id']==f'UP{index:02d}')
    parent,plan,before,current,old,new=changed(index)
    graph=unified.build_v1(parent,plan,before,current,old,new)
    assert graph['affected']==ids(plan,expected['affected'])
    assert graph['preserved']==ids(plan,expected['preserved'])
    assert graph['unknown_scope']==expected['unknown_scope']
    assert graph['schema']==2 and graph['sha256']==cp._hash({k:v for k,v in graph.items() if k!='sha256'})
    assert 'PRIVATE_POISON' not in json.dumps(graph)


def test_shared_identity_keeps_per_consumer_history_and_only_changed_observation_propagates():
    args=changed(15);graph=unified.build_v1(*args)
    material=[n for n in graph['nodes'] if n['facet']=='MATERIAL_PACKAGE'];assert len(material)==1
    observations=[o for o in graph['observations'] if o['source_node_id']==material[0]['id']]
    assert len(observations)==5
    assert [o['adapter_id'] for o in observations if o['changed']]==['P5']
    assert graph['affected']==ids(args[1],['P5'])
    assert graph['preserved']==ids(args[1],['P1','P2','P3','P4'])
    assert all(p['step_id']==args[1]['steps'][4]['id'] and len(p['edge_ids'])==1 for p in graph['propagation_paths'])
    stable=unified.build_v1(args[0],args[1],args[2],args[2],args[4],args[4])
    assert [n['id'] for n in stable['nodes']]==[n['id'] for n in graph['nodes']]
    assert [o['id'] for o in stable['observations']]==[o['id'] for o in graph['observations']]


def test_each_path_binds_real_changed_observation_then_original_predecessors():
    args=changed(5);graph=unified.build_v1(*args);edges={e['id']:e for e in graph['edges']}
    assert {p['step_id'] for p in graph['propagation_paths']}==set(ids(args[1],['P2','P3','P4','P5']))
    for path in graph['propagation_paths']:
        chain=[edges[id] for id in path['edge_ids']]
        assert chain[0]['observation_id']==path['observation_id']
        assert path['observation_id'] in graph['changed_observation_ids']
        assert chain[-1]['downstream']==path['step_id']
        for previous,current in zip(chain,chain[1:]):
            assert previous['downstream']==current['upstream'] and current['kind']=='PRECEDES' and 'observation_id' not in current


def test_date_evidence_collection_fingerprints_and_original_source_nodes_exact():
    args=changed(4);graph=unified.build_v1(*args);original=typed.build_v1(*args)
    original_nodes={n['id']:n for n in original['nodes']}
    for observation in graph['observations']:
        saved=original_nodes[observation['original_node_id']]
        assert {k:v for k,v in observation.items() if k not in ('id','source_node_id','original_node_id')}=={k:v for k,v in saved.items() if k not in ('id','type','facet')}
    assert next(o for o in graph['observations'] if o['adapter_id']=='P2' and o['fields']==['resource_rules'])['date_evidence']['current']['state']=='RECORDED'
    assert [o['fields'] for o in graph['observations'] if o['provenance']=='ORIGINAL_REGISTERED_DEPENDENCY_MANIFEST']==[['resources'],['existing_access']]


@pytest.mark.parametrize('name',['MAX_NODES','MAX_EDGES','MAX_OBSERVATIONS'])
def test_bounds_fail_without_partial_graph(monkeypatch,name):
    monkeypatch.setattr(unified,name,1)
    with pytest.raises(Conflict,match='bounded'):unified.build_v1(*changed(2))


def test_partition_not_explained_by_observation_is_conservatively_unknown():
    args=changed(2);original=typed.build_v1(*args)
    original.update(affected=[],preserved=[s['id'] for s in args[1]['steps']])
    original['sha256']=cp._hash({k:v for k,v in original.items() if k!='sha256'})
    graph=unified._from_v1(original)
    assert graph['unknown_scope']=='THIS_CASE' and not graph['preserved']
    assert graph['unknown_reasons']==['SOURCE_PARTITION_UNEXPLAINED']


def test_enhance_binds_v4_scope_without_modifying_original_graph_or_input():
    args=changed(2);parent,plan=args[:2];original=typed.build_v1(*args)
    result=dict(scope='old',source_impact=original,unknown_scope=None,blocking_reasons=['ORIGINAL_MANUAL_CONFLICT'],can_adopt=False,
        adoption=dict(opportunity_proof=dict(expected_preview_sha256='a'*64)),affected=original['affected'],preserved=original['preserved'])
    change=dict(version=2,source_impact=original);saved=deepcopy((result,change))
    final,patch,affected=unified.enhance(None,parent,result,change,{'P4','P5'})
    assert (result,change)==saved and patch['source_impact']==original
    assert final['scope']==unified.PUBLIC_SCOPE and patch['version']==4
    assert final['adoption']['dependency_scope']==unified.SCOPE
    assert final['preview_sha256']==patch['sha256']==final['adoption']['opportunity_proof']['expected_preview_sha256']
    assert final['blocking_reasons']==['ORIGINAL_MANUAL_CONFLICT'] and final['can_adopt'] is False
    assert affected=={'P4','P5'}


def test_unknown_never_retains_adoption_and_is_whole_case():
    args=changed(18);original=typed.build_v1(*args)
    result=dict(unknown_scope='THIS_CASE',blocking_reasons=['KNOWN_CURRENT_SOURCE_GRAPH_REQUIRED'],adoption={'unused':True})
    final,patch,affected=unified.enhance(None,args[0],result,dict(source_impact=original),set())
    assert final['adoption'] is None and final['can_adopt'] is False and not final['preserved']
    assert final['affected']==ids(args[1],['P1','P2','P3','P4','P5'])


def event_fixture():
    args=changed(2);graph=unified.build_v1(*args)
    change=dict(version=4,before_sources=args[2],current_sources=args[3],source_impact=typed.build_v1(*args),dependency_propagation=graph)
    change['sha256']=cp._hash(change)
    event=dict(local_revision=dict(source_change=change,request=dict(dependency_scope=unified.SCOPE,opportunity_proof=dict(expected_preview_sha256=change['sha256']))))
    return args,event


def test_history_normalizes_only_new_envelope_before_all_original_validation(monkeypatch):
    from parkweave import source_change_adoption as original
    args,event=event_fixture();saved=deepcopy(event);captured=[]
    def check(parent,plan,canonical,old,new):
        captured.append(canonical);patch=canonical['local_revision'];change=patch['source_change']
        assert change['version']==2 and 'dependency_propagation' not in change and 'dependency_scope' not in patch['request']
        assert change['source_impact']==event['local_revision']['source_change']['source_impact']
        assert change['sha256']==cp._hash({k:v for k,v in change.items() if k!='sha256'})==patch['request']['opportunity_proof']['expected_preview_sha256']
        return {'P4','P5'}
    monkeypatch.setattr(original,'validate_history',check)
    assert unified.validate_history(args[0],args[1],event,args[4],args[5])=={'P4','P5'}
    assert event==saved and len(captured)==1


@pytest.mark.parametrize('mutation',['changed','edge','path','scope','mixed','bool-schema','extra'])
def test_rehashed_history_forgery_rejected_before_original_validation(monkeypatch,mutation):
    from parkweave import source_change_adoption as original
    args,event=event_fixture();patch=event['local_revision'];change=patch['source_change'];graph=change['dependency_propagation']
    if mutation=='changed':graph['observations'][0]['changed']=True
    if mutation=='edge':graph['edges'][0]['downstream']=args[1]['steps'][4]['id']
    if mutation=='path':graph['propagation_paths'][0]['edge_ids']=[]
    if mutation=='scope':patch['request']['dependency_scope']='OTHER'
    if mutation=='mixed':patch['request']['fact_provenance_scope']='EMPLOYEES_USER_ASSERTION_V1'
    if mutation=='bool-schema':graph['schema']=True
    if mutation=='extra':graph['observations'][0]['invented_field']='forged'
    graph['sha256']=cp._hash({k:v for k,v in graph.items() if k!='sha256'})
    change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
    patch['request']['opportunity_proof']['expected_preview_sha256']=change['sha256']
    monkeypatch.setattr(original,'validate_history',lambda *a:pytest.fail('forged history reached original validator'))
    with pytest.raises(ValueError):unified.validate_history(args[0],args[1],event,args[4],args[5])
