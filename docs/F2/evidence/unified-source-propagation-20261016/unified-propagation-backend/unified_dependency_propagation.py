"""Bounded propagation over original registered aggregate source observations.

Shared source identity does not imply shared consumer history. Only a changed
observation starts propagation; a source node's changed flag is descriptive.
"""
from collections import deque
from copy import deepcopy
from . import controlled_plans as cp, typed_source_impact as typed
from .store import Conflict

SCOPE='BOUNDED_MULTI_SOURCE_V1'
PUBLIC_SCOPE='BOUNDED_MULTI_SOURCE_REVISION_PREVIEW'
MAX_NODES=96
MAX_EDGES=128
MAX_OBSERVATIONS=96


def _from_v1(graph):
    """Translate the frozen aggregate compiler without inventing finer facts."""
    if type(graph.get('schema')) is not int or graph['schema']!=1 or graph.get('sha256')!=cp._hash({k:v for k,v in graph.items() if k!='sha256'}):
        raise Conflict('original registered source graph required')
    endpoints=deepcopy(graph['step_endpoints']);step_ids=[s['id'] for s in endpoints]
    nodes=[];observations=[];edges=[];by_key={};by_original={}
    for original in graph['nodes']:
        key=(original['facet'],original['type'])
        if key not in by_key:
            identity=dict(scope=SCOPE,binding=graph['binding'],plan_id=graph['plan_id'],facet=key[0],type=key[1])
            node=dict(id=cp._hash(identity),type=key[1],facet=key[0],aggregate=True,observation_ids=[],changed=False,known=True)
            by_key[key]=node;nodes.append(node)
        node=by_key[key]
        observation=dict(id=cp._hash(dict(scope=SCOPE,source_node_id=node['id'],original_node_id=original['id'])),
            source_node_id=node['id'],original_node_id=original['id'],**{k:deepcopy(v) for k,v in original.items() if k not in ('id','type','facet')})
        observations.append(observation);by_original[original['id']]=observation
        node['observation_ids'].append(observation['id']);node['changed']|=observation['changed'];node['known']&=observation['known']
    for original in graph['edges']:
        edge=deepcopy(original)
        if original['upstream'] in by_original:
            observation=by_original[original['upstream']]
            if original['downstream']!=observation['step_id']:raise Conflict('original source consumer mismatch')
            edge['upstream']=observation['source_node_id'];edge['observation_id']=observation['id']
        elif original['upstream'] not in step_ids or original['downstream'] not in step_ids or original['kind']!='PRECEDES':
            raise Conflict('original compiled predecessor edge required')
        edge['id']=cp._hash(dict(scope=SCOPE,edge=edge));edges.append(edge)
    if len(nodes)+len(endpoints)>MAX_NODES or len(edges)>MAX_EDGES or len(observations)>MAX_OBSERVATIONS:
        raise Conflict('bounded unified dependency graph exceeded')
    # Traverse only original step PRECEDES edges after each changed observation.
    # Never fan out through a shared source node's unchanged consumer edges.
    adjacency={id:[] for id in step_ids}
    for edge in edges:
        if 'observation_id' not in edge:adjacency[edge['upstream']].append(edge)
    roots={o['id'] for o in observations if o['changed']}
    reached=set();paths=[]
    for edge in edges:
        if edge.get('observation_id') not in roots:continue
        queue=deque([(edge['downstream'],[edge['id']])]);seen=set()
        while queue:
            target,path=queue.popleft()
            if target in seen:continue
            seen.add(target);reached.add(target)
            paths.append(dict(observation_id=edge['observation_id'],source_node_id=edge['upstream'],step_id=target,
                reason='DIRECT_SOURCE_CHANGE' if len(path)==1 else 'REGISTERED_PREDECESSOR_CHANGE',edge_ids=path))
            for downstream in adjacency[target]:queue.append((downstream['downstream'],path+[downstream['id']]))
    reasons=list(graph['unknown_reasons'])
    if not graph['unknown_scope'] and (graph['affected']!=[id for id in step_ids if id in reached] or graph['preserved']!=[id for id in step_ids if id not in reached]):
        reasons.append('SOURCE_PARTITION_UNEXPLAINED')
    unknown=bool(graph['unknown_scope'] or reasons)
    result=dict(schema=2,scope=SCOPE,binding=deepcopy(graph['binding']),plan_id=graph['plan_id'],original_graph_sha256=graph['sha256'],
        nodes=nodes,observations=observations,edges=edges,step_endpoints=endpoints,
        changed_node_ids=[n['id'] for n in nodes if n['changed']],changed_observation_ids=[o['id'] for o in observations if o['changed']],
        propagation_paths=paths,affected=step_ids if unknown else [id for id in step_ids if id in reached],
        preserved=[] if unknown else [id for id in step_ids if id not in reached],unknown_scope='THIS_CASE' if unknown else None,
        unknown_reasons=sorted(set(reasons)),new_grants=False,automatic_execution=False)
    return {**result,'sha256':cp._hash(result)}


def build_v1(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies):
    """Frozen schema 2 compiler; schema 1 retains its original implementation."""
    return _from_v1(typed.build_v1(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies))


def build(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies):
    return build_v1(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies)


def enhance(c,parent,result,change,affected):
    """Use the original locked read and original authority/lock blockers."""
    result=deepcopy(result);change=deepcopy(change)
    graph=_from_v1(change['source_impact'])
    change.update(version=4,dependency_propagation=graph)
    change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
    result.update(scope=PUBLIC_SCOPE,dependency_propagation=graph,preview_sha256=change['sha256'])
    if result.get('unknown_scope') or graph['unknown_scope']:
        ids=[s['id'] for s in parent['service_case_plan']['steps']]
        result.update(unknown_scope='THIS_CASE',directly_changed=ids,affected=ids,preserved=[],adoption=None,can_adopt=False)
        result['blocking_reasons']=sorted(set(result['blocking_reasons']+['KNOWN_UNIFIED_DEPENDENCIES_REQUIRED']))
        affected={s['adapter_id'] for s in parent['service_case_plan']['steps']}
    elif result.get('adoption') is not None:
        result['adoption']['dependency_scope']=SCOPE
        result['adoption']['opportunity_proof']['expected_preview_sha256']=change['sha256']
    return result,change,affected


def validate_history(parent,plan,event,previous_dependencies,current_dependencies):
    """Exact graph reconstruction then all original version 2 proof checks."""
    from . import source_change_adoption as original
    patch=event['local_revision'];change=patch['source_change'];request=patch['request']
    if type(change.get('version')) is not int or change['version']!=4 or request.get('dependency_scope')!=SCOPE or request.get('fact_provenance_scope') is not None:
        raise ValueError('unique explicit unified dependency scope required')
    if change.get('sha256')!=cp._hash({k:v for k,v in change.items() if k!='sha256'}) or request['opportunity_proof']['expected_preview_sha256']!=change['sha256']:
        raise ValueError('unified dependency preview binding invalid')
    expected=build_v1(parent,plan,change['before_sources'],change['current_sources'],previous_dependencies,current_dependencies)
    if expected['unknown_scope'] or cp._hash(expected)!=cp._hash(change.get('dependency_propagation')):
        raise ValueError('historical unified dependency proof changed')
    canonical=deepcopy(event);patch=canonical['local_revision'];change=patch['source_change']
    change.pop('dependency_propagation');change['version']=2
    change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
    patch['request'].pop('dependency_scope')
    patch['request']['opportunity_proof']['expected_preview_sha256']=change['sha256']
    return original.validate_history(parent,plan,canonical,previous_dependencies,current_dependencies)
