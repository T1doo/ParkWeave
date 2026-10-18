"""Finite source groups from original registered snapshots; no new authority.

The old material and fact proofs are deliberately aggregate. This module never
fills them with today's material IDs, assertion values, or a newly queried source.
"""
from copy import deepcopy
from datetime import datetime
from . import controlled_plans as cp, registered_dependencies as deps
from . import case_opportunities as op, executor_receipts as er, preparation as prep
from .store import Conflict, Denied

SCOPE='REGISTERED_CASE_TYPED_SOURCE_IMPACT'
READ_SCOPE='CURRENT_OWNER_CASE_SOURCE_IMPACT'
PROVENANCE='ACTUAL_REGISTERED_SOURCE_SNAPSHOT'
MAX_NODES=96
MAX_EDGES=128

# facet: (node type, impact edge kind, exhaustive original snapshot fields).
GROUPS_V1={
 'P1':{
  'CASE_BINDING':('SOURCE','PRECEDES',('preparation_id','case_id','run_id','service_id','service_version','owner_id','reviewer_id','template_sha256')),
  'REQUEST_INTENT':('REQUEST','PRECEDES',('goal','required_goals','request_intent','request_intent_sha256')),
  'MATERIAL_PACKAGE':('MATERIAL','MATERIAL',('preparation_revision','preparation_sha256')),
  'FACT_PURPOSE_BINDING':('FACT','MATERIAL',('fact_clarification',)),
  'SERVICE_RULE':('SERVICE_RULE','MATERIAL',('service_catalog',)),
  'OWNER_AUTHORITY':('SOURCE','PRECEDES',('owner_grants',)),
 },
 'P2':{
  'MATERIAL_PACKAGE':('MATERIAL','MATERIAL',('preparation_revision','preparation_sha256')),
  'RESOURCE_ASSOCIATION':('RESOURCE','CAPACITY',('resource_link_id','resource_link_revision','combination_id','combination_state','members')),
  'RESOURCE_RULES':('RESOURCE','CAPACITY',('resource_rules',)),
  'RESERVATION_SOURCES':('RESERVATION','CAPACITY',('hold_sources',)),
  'RESOURCE_AUTHORITY':('SOURCE','CAPACITY',('resource_grants',)),
  'RESOURCE_CATALOG_DECISION':('SERVICE_RULE','CAPACITY',('resource_catalog_decision',)),
  'RESOURCE_QUERY_SET':('CAPACITY_SNAPSHOT','CAPACITY',('resource_collection',)),
 },
 'P3':{
  'MATERIAL_PACKAGE':('MATERIAL','MATERIAL',('preparation_revision','preparation_sha256')),
  'DISPATCH_ACCEPTANCE':('SOURCE','PRECEDES',('dispatch_id','dispatch_revision','offer_id','executor_id','offer_state','acceptance_event','receipt_step_id','receipt_step_preparation_revision','receipt_step_preparation_sha256')),
  'RUN_ACCESS_QUERY_SET':('SOURCE','PRECEDES',('run_access_collection',)),
 },
 'P4':{
  'MATERIAL_PACKAGE':('MATERIAL','MATERIAL',('preparation_revision','preparation_sha256')),
  'RECEIPT_SOURCE':('RECEIPT','VERIFIED_BY',('receipt_step_id','receipt_step_revision','receipt_id','receipt_sha256','receipt_version','receipt_actor_id','receipt_source_kind')),
  'RECEIPT_EVENTS':('RECEIPT','VERIFIED_BY',('receipt_versions','receipt_events')),
 },
 'P5':{
  'CASE_BINDING':('SOURCE','PRECEDES',('sources.preparation_id','sources.case_id','sources.run_id','sources.service_id','sources.service_version','sources.$present')),
  'MATERIAL_PACKAGE':('MATERIAL','MATERIAL',('sources.preparation_revision','sources.preparation_sha256')),
  'FACT_PURPOSE_BINDING':('FACT','MATERIAL',('sources.fact_clarification',)),
  'RESOURCE_ASSOCIATION':('RESOURCE','CAPACITY',('sources.resource_link_id','sources.resource_link_revision','sources.combination_id','sources.combination_state','sources.members')),
  'RESOURCE_CATALOG_DECISION':('SERVICE_RULE','CAPACITY',('sources.resource_catalog_decision',)),
  'DISPATCH_ACCEPTANCE':('SOURCE','PRECEDES',('sources.dispatch_id','sources.dispatch_revision','sources.offer_id','sources.executor_id')),
  'RECEIPT_SOURCE':('RECEIPT','VERIFIED_BY',('sources.receipt_step_id','sources.receipt_step_revision','sources.receipt_id','sources.receipt_sha256')),
  'LOCAL_CHECK':('CHECK','VERIFIED_BY',('local_lifecycle',)),
 },
}
COMMON_V1={
 'TEMPLATE_SOURCE':('RELEASE','PACKAGED_IN',('adopted_template_source',)),
 'TEMPLATE_STRUCTURES':('RELEASE','PACKAGED_IN',('adopted_template_structures',)),
}
COLLECTIONS_V1={
 'resources':('P2','DEPENDENCY_RESOURCE_QUERY_SET','CAPACITY_SNAPSHOT','CAPACITY'),
 'existing_access':('P3','DEPENDENCY_RUN_ACCESS_QUERY_SET','SOURCE','PRECEDES'),
}
COLLECTIONS_V2={
 'service_catalog':('P1','DEPENDENCY_SERVICE_CATALOG_QUERY_SET','SERVICE_RULE','MATERIAL'),
}


def _flatten_v1(adapter,value):
    if not isinstance(value,dict):return {},False
    out={};valid=bool(value)
    if adapter=='P5' and 'sources' not in value:valid=False
    for key,item in value.items():
        if adapter=='P5' and key=='sources':
            if not isinstance(item,dict):valid=False;out['sources']=item
            else:
                out['sources.$present']=True
                out.update({'sources.'+k:v for k,v in item.items()})
        else:out[key]=item
    return out,valid


def _date_evidence_v1(facet,value):
    # Only these original typed resource fields declare dates. Catalog prose,
    # hashes, and fact descriptors do not prove a validity interval.
    rows=[]
    for field in ('resource_rules','hold_sources','members','sources.members'):
        if field in value and value[field] is not None and (not isinstance(value[field],list) or any(not isinstance(r,dict) for r in value[field])):
            return dict(state='UNKNOWN',reason='ORIGINAL_DATE_EVIDENCE_UNAVAILABLE',intervals=[])
    if facet=='RESOURCE_RULES':
        for row in value.get('resource_rules') or []:
            if isinstance(row,dict):rows.append({k:row[k] for k in ('open_from','open_until') if k in row})
    elif facet=='RESERVATION_SOURCES':
        for row in value.get('hold_sources') or []:
            if isinstance(row,dict):rows.append({k:row[k] for k in ('starts_at','ends_at','expires_at') if k in row})
    elif facet=='RESOURCE_ASSOCIATION':
        for row in value.get('sources.members',value.get('members',[])) or []:
            if isinstance(row,dict):rows.append({k:row[k] for k in ('starts_at','ends_at') if k in row})
    if len(rows)>32:return dict(state='UNKNOWN',reason='DATE_EVIDENCE_BOUND_EXCEEDED',intervals=[])
    try:
        for row in rows:
            if not row:raise ValueError()
            for date in row.values():
                if not isinstance(date,str) or len(date)>64 or datetime.fromisoformat(date).utcoffset() is None:raise ValueError()
    except (TypeError,ValueError):return dict(state='UNKNOWN',reason='ORIGINAL_DATE_EVIDENCE_UNAVAILABLE',intervals=[])
    if not rows:return dict(state='UNKNOWN',reason='ORIGINAL_DATE_EVIDENCE_UNAVAILABLE',intervals=[])
    return dict(state='RECORDED',reason='ORIGINAL_RESOURCE_SNAPSHOT_ONLY',intervals=rows)


def _node_v1(binding,plan,step,facet,type,kind,fields,before,current,*,known=True,provenance=PROVENANCE):
    b={k:before[k] for k in fields if k in before};a={k:current[k] for k in fields if k in current}
    id=cp._hash(dict(scope=SCOPE,binding=binding,plan_id=plan['id'],adapter_id=step['adapter_id'],facet=facet))
    node=dict(id=id,type=type,facet=facet,aggregate=True,adapter_id=step['adapter_id'],step_id=step['id'],fields=list(fields),
        before_present=bool(b),current_present=bool(a),before_sha256=cp._hash(b) if b else None,current_sha256=cp._hash(a) if a else None,
        changed=cp._hash(b)!=cp._hash(a),known=bool(known),provenance=provenance,
        date_evidence=dict(before=_date_evidence_v1(facet,b),current=_date_evidence_v1(facet,a)))
    edge=dict(upstream=id,downstream=step['id'],kind=kind,provenance=provenance)
    return node,edge


def build_v1(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies):
    """Pure, reproducible graph from retained original proofs and current reads."""
    binding=op.binding(parent);nodes=[];edges=[];reasons=set();roots=set()
    selected={s['adapter_id'] for s in plan['steps']}
    if not isinstance(before_sources,dict) or set(before_sources)!=selected:reasons.add('SOURCE_BASE_UNAVAILABLE')
    if not isinstance(current_sources,dict) or set(current_sources)!=selected:reasons.add('CURRENT_SOURCE_UNAVAILABLE')
    before_sources=before_sources if isinstance(before_sources,dict) else {}
    current_sources=current_sources if isinstance(current_sources,dict) else {}
    for step in plan['steps']:
        adapter=step['adapter_id']
        if adapter not in GROUPS_V1:raise Conflict('registered source adapter unavailable')
        before,b_valid=_flatten_v1(adapter,before_sources.get(adapter));current,c_valid=_flatten_v1(adapter,current_sources.get(adapter))
        present=adapter in before_sources and adapter in current_sources and b_valid and c_valid
        if not present:reasons.add('SOURCE_BASE_UNAVAILABLE')
        groups={**GROUPS_V1[adapter],**COMMON_V1};known_fields={field for _,_,fields in groups.values() for field in fields}
        unrecognized=(set(before)|set(current))-known_fields
        if unrecognized:reasons.add('UNMAPPED_SOURCE_FIELDS')
        for facet,(type,kind,fields) in groups.items():
            shape=True
            for values in (before,current):
                for field in fields:
                    value=values.get(field)
                    if field.split('.')[-1] in ('resource_rules','hold_sources','resource_grants','receipt_versions','receipt_events','members') and field in values:
                        nullable=field.split('.')[-1]=='members'
                        if not (value is None and nullable) and (not isinstance(value,list) or len(value)>256 or any(not isinstance(r,dict) for r in value)):shape=False
                    if field.split('.')[-1] in ('resource_collection','run_access_collection') and field in values:
                        if not isinstance(value,dict) or value.get('known') is not True:shape=False
            if not shape:reasons.add('SOURCE_GROUP_SHAPE_UNAVAILABLE')
            node,edge=_node_v1(binding,plan,step,facet,type,kind,fields,before,current,known=present and shape)
            nodes.append(node);edges.append(edge)
            if node['changed']:roots.add(adapter)
        if unrecognized:
            # Unknown names and contents are never projected as UI text.
            b={'unmapped':{k:before[k] for k in sorted(unrecognized) if k in before}}
            a={'unmapped':{k:current[k] for k in sorted(unrecognized) if k in current}}
            node,edge=_node_v1(binding,plan,step,'UNMAPPED_SOURCE_FIELDS','SOURCE','PRECEDES',('unmapped',),b,a,known=False)
            node['fields']=[];nodes.append(node);edges.append(edge)
        for facet in ('FACT_PURPOSE_BINDING',):
            source=current.get('fact_clarification',current.get('sources.fact_clarification'))
            if source is not None and (not isinstance(source,dict) or source.get('satisfied') is not True):reasons.add('CURRENT_FACT_SOURCE_UNAVAILABLE')
    for name,(adapter,facet,type,kind) in {**COLLECTIONS_V1,**COLLECTIONS_V2}.items():
        if name in COLLECTIONS_V2 and not any(name in (v or {}).get('collections',{}) for v in (previous_dependencies,current_dependencies)):
            continue  # Preserve old V1 source graphs and history byte-for-byte.
        if adapter not in selected:continue
        step=next(s for s in plan['steps'] if s['adapter_id']==adapter)
        prior=(previous_dependencies or {}).get('collections',{}).get(name)
        current=(current_dependencies or {}).get('collections',{}).get(name)
        known=bool(isinstance(prior,dict) and isinstance(current,dict) and prior.get('known') is True and current.get('known') is True)
        if not known:reasons.add('DEPENDENCY_COLLECTION_UNAVAILABLE')
        node,edge=_node_v1(binding,plan,step,facet,type,kind,(name,),{name:prior},{name:current},known=known,
                        provenance='ORIGINAL_REGISTERED_DEPENDENCY_MANIFEST')
        nodes.append(node);edges.append(edge)
        if node['changed']:roots.add(adapter)
    dependency_affected,dependency_unknown=deps.impact_between(plan['steps'],previous_dependencies,current_dependencies)
    if dependency_unknown:reasons.add('DEPENDENCY_DECLARATION_UNCERTAIN')
    by_adapter={s['adapter_id']:s['id'] for s in plan['steps']}
    for step in plan['steps']:
        for dep in step['depends_on']:
            if dep not in by_adapter:raise Conflict('registered source predecessor unavailable')
            edges.append(dict(upstream=by_adapter[dep],downstream=step['id'],kind='PRECEDES',provenance='COMPILED_REGISTERED_ADAPTER'))
    if len(nodes)>MAX_NODES or len(edges)>MAX_EDGES:raise Conflict('bounded registered source graph exceeded')
    candidate=deps.closure(plan['steps'],roots)|dependency_affected
    if not reasons:
        original_roots={a for a in selected if before_sources[a]!=current_sources[a]}
        original_affected=deps.closure(plan['steps'],original_roots)|dependency_affected
        if candidate!=original_affected:reasons.add('SOURCE_PARTITION_UNEXPLAINED')
    affected=set(selected) if reasons else candidate
    graph=dict(schema=1,scope=SCOPE,binding=binding,plan_id=plan['id'],nodes=nodes,edges=edges,
        step_endpoints=[dict(id=s['id'],type='PLAN_STEP',adapter_id=s['adapter_id']) for s in plan['steps']],
        changed_node_ids=[n['id'] for n in nodes if n['changed']],affected=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected],
        preserved=[s['id'] for s in plan['steps'] if s['adapter_id'] not in affected],
        unknown_scope='THIS_CASE' if reasons else None,unknown_reasons=sorted(reasons))
    return {**graph,'sha256':cp._hash(graph)}


def build(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies):
    """Current compiler. Saved schema 1 always calls frozen build_v1."""
    return build_v1(parent,plan,before_sources,current_sources,previous_dependencies,current_dependencies)


@er.bounded
def read(store,token,id):
    from . import service_case_steps as service, source_change_adoption as adoption
    with store.connect() as c:
        p,parent=service._context(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('original Case owner required')
        if parent['service_id']!=prep.SERVICE:raise Denied('existing synthetic Case required')
        plan=deepcopy(parent.get('service_case_plan'))
        result=dict(scope=READ_SCOPE,read_only=True,automatically_replayed=False,actor_ref=cp._hash(dict(actor_id=p['id'])),
            preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),plan_id=plan['id'] if plan else None,
            plan_revision=plan['revision'] if plan else 0,steps=[dict(id=s['id'],adapter_id=s['adapter_id']) for s in plan['steps']] if plan else [],
            source_impact=None,state='NO_PLAN',blocking_reasons=[],current_source_available=None,qualification_decision='NOT_EVALUATED',new_grants=False,automatic_execution=False,case_goal_completed=False)
        if not plan:return result
        service._recovery_proofs(parent)
        issues,sources,_=service.current_sources(store,c,parent,plan)
        sources={s['adapter_id']:sources[s['adapter_id']] for s in plan['steps']}
        before=adoption.evidence_sources(parent,plan)
        basis,_,_=service.dependency_impact(store,c,parent,plan)
        graph=build(parent,plan,before,sources,plan.get('dependency_manifest'),basis)
        blocking=service._binding_issues(c,parent,plan,store=store)
        if graph['unknown_scope']:blocking.append('KNOWN_CURRENT_SOURCE_GRAPH_REQUIRED')
        # Reuse the original current source safety checks; a read itself never
        # claims those sources are valid or authorizes a subsequent write.
        if any(adoption.unavailable_sources().intersection(v) for v in issues.values()):blocking.append('CURRENT_KNOWN_SOURCE_REQUIRED')
        result.update(source_impact=graph,current_source_available=not blocking,state='UNKNOWN' if graph['unknown_scope'] or blocking else 'CHANGED' if graph['affected'] else 'UNCHANGED',
                      blocking_reasons=sorted(set(blocking)),current_sources_sha256=cp._hash(sources),source_epochs_sha256=adoption.epochs(c,parent))
        prep.grant(store,c,p,'PREPARE')
        return result
